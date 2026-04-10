"""
feedback_loop.py
----------------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\feedback_loop.py

Layer 4 — Agentic self-correction loop.
If XSD validation returns errors, builds a re-prompt and
asks Claude to fix the SWCSpec JSON.
Max 5 iterations by default. Returns best result on convergence.

This layer activates automatically in the orchestrator when
ARXML generation fails XSD validation.
Requires API credits to run.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5


class FeedbackLoop:
    """
    Self-correction loop that asks Claude to fix a SWCSpec
    when ARXML generation or validation fails.

    Flow:
        1. Orchestrator generates ARXML from SWCSpec
        2. XSD validation finds errors
        3. FeedbackLoop builds a targeted re-prompt
        4. Claude returns a corrected SWCSpec
        5. Repeat up to MAX_ITERATIONS times
    """

    def __init__(self, claude_client, arxml_generator_cls):
        self.claude = claude_client
        self.arxml_generator_cls = arxml_generator_cls

    def run(self, user_prompt: str, output_dir: Path) -> dict:
        """
        Run the full feedback loop from a user prompt.

        Args:
            user_prompt: Original natural language SWC description.
            output_dir:  Directory to write ARXML files into.

        Returns:
            dict with keys: status, spec, arxml_paths, iterations
        """
        from src.arxml_generator import ARXMLGenerator
        from src.schema_validator import validate_all, all_valid, format_errors

        spec = self.claude.send_prompt(user_prompt)
        prev_json = spec.model_dump_json()

        for iteration in range(1, MAX_ITERATIONS + 1):
            logger.info("[FeedbackLoop] Iteration %d/%d", iteration, MAX_ITERATIONS)

            # Generate ARXML
            gen = ARXMLGenerator(spec, output_dir)
            arxml_paths = gen.generate_all()

            # Validate
            val_results = validate_all(arxml_paths)
            if all_valid(val_results):
                logger.info("[FeedbackLoop] Converged on iteration %d", iteration)
                return {
                    "status": "OK",
                    "spec": spec,
                    "arxml_paths": arxml_paths,
                    "iterations": iteration,
                }

            # Build feedback and re-prompt Claude
            errors = [format_errors(val_results)]
            logger.warning("[FeedbackLoop] Errors: %s", errors)
            feedback_prompt = self.build_feedback_prompt(
                user_prompt, prev_json, errors
            )
            spec = self.claude.send_prompt(feedback_prompt)
            prev_json = spec.model_dump_json()

        logger.error("[FeedbackLoop] Did not converge after %d iterations", MAX_ITERATIONS)
        return {
            "status": "ERROR",
            "spec": spec,
            "arxml_paths": [],
            "iterations": MAX_ITERATIONS,
        }

    def build_feedback_prompt(
        self, original: str, prev_json: str, errors: list
    ) -> str:
        """
        Build a targeted re-prompt asking Claude to fix specific errors.

        Args:
            original:  Original user prompt.
            prev_json: JSON of the previous SWCSpec that failed.
            errors:    List of error strings from XSD validation.

        Returns:
            A new prompt string for Claude.
        """
        error_block = "\n".join(f"- {e}" for e in errors)
        return (
            f"The following AUTOSAR SWC specification produced validation errors.\n\n"
            f"Original request: {original}\n\n"
            f"Previous specification (JSON):\n{prev_json}\n\n"
            f"Validation errors:\n{error_block}\n\n"
            f"Please fix the specification to resolve these errors and return "
            f"a corrected JSON following the same schema."
        )
