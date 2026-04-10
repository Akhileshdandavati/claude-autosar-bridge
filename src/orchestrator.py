"""
orchestrator.py
---------------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\orchestrator.py

Main pipeline controller — chains all layers together.

Pipeline:
    User prompt (natural language)
        -> Layer 1: ClaudeClient       -> SWCSpec (Pydantic model)
        -> Layer 2: ARXMLGenerator     -> 3 x .arxml files
        -> Layer 3: CCodeGenerator     -> Rte_Types.h, Rte_<swc>.h, <swc>.h, <swc>.c
        -> Layer 4: FeedbackLoop       -> self-correction on errors

Usage (full pipeline, requires API credits):
    from src.orchestrator import Orchestrator
    result = Orchestrator().run("Create SpeedSensor SWC with 10ms runnable")

Usage (skip Claude, use existing SWCSpec directly):
    from src.orchestrator import Orchestrator
    from src.models import SWCSpec
    spec = SWCSpec(...)
    result = Orchestrator().run_from_spec(spec)

CLI:
    python -m src.orchestrator "Create SpeedSensor SWC with 10ms runnable"
    python -m src.orchestrator --from-spec output/SpeedSensor/spec.json
    python -m src.orchestrator --test
"""

import json
import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path("output") / "generated"


class OrchestratorResult:
    """Structured result from the orchestrator pipeline."""

    def __init__(self):
        self.status: str = "ERROR"
        self.swc_name: str = ""
        self.arxml_paths: list[Path] = []
        self.c_code_paths: list[Path] = []
        self.message: str = ""
        self.iterations: int = 0
        self.elapsed_s: float = 0.0

    def ok(self) -> bool:
        return self.status == "OK"

    def __repr__(self):
        return (
            f"OrchestratorResult("
            f"status={self.status}, "
            f"swc={self.swc_name}, "
            f"iters={self.iterations}, "
            f"elapsed={self.elapsed_s:.1f}s)"
        )


class Orchestrator:
    """
    Chains all pipeline layers into a single entry point.

    - Full run:    Claude -> ARXML -> C code (requires API credits)
    - From spec:   SWCSpec -> ARXML -> C code (no API credits needed)
    - ARXML only:  Claude -> ARXML (no C code generation)
    """

    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT,
        max_feedback_iters: int = 5,
        arxml_only: bool = False,
    ):
        self.output_dir = output_dir
        self.max_feedback_iters = max_feedback_iters
        self.arxml_only = arxml_only

    # ── Public entry points ───────────────────────────────────────────
    def run(self, user_prompt: str) -> OrchestratorResult:
        """
        Full pipeline: Claude API -> ARXML -> C code.
        Requires Anthropic API credits.
        """
        result = OrchestratorResult()
        t0 = time.time()

        logger.info("=" * 60)
        logger.info("Orchestrator.run() starting")
        logger.info("Prompt: %s", user_prompt[:80])
        logger.info("=" * 60)

        logger.info("[Layer 1] Calling Claude API ...")
        try:
            from src.claude_client import ClaudeClient
            from dotenv import load_dotenv
            load_dotenv()
            client = ClaudeClient()
            spec = client.send_prompt(user_prompt)
            logger.info("[Layer 1] SWCSpec: %s (%d ports, %d runnables)",
                        spec.swc_name, len(spec.ports), len(spec.runnables))
        except Exception as e:
            result.message = f"Layer 1 failed: {e}"
            logger.error(result.message)
            return result

        return self._run_from_spec_internal(spec, user_prompt, result, t0)

    def run_from_spec(self, spec, save_spec: bool = True) -> OrchestratorResult:
        """
        Skip Claude — start from an existing SWCSpec.
        Useful for testing without API credits.
        """
        result = OrchestratorResult()
        t0 = time.time()
        logger.info("[Orchestrator] run_from_spec: %s", spec.swc_name)

        if save_spec:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            spec_path = self.output_dir / "spec.json"
            spec_path.write_text(spec.model_dump_json(indent=2))
            logger.info("Spec saved: %s", spec_path)

        return self._run_from_spec_internal(spec, spec.swc_name, result, t0)

    # ── Internal pipeline ─────────────────────────────────────────────
    def _run_from_spec_internal(
        self, spec, prompt_or_name: str, result: OrchestratorResult, t0: float
    ) -> OrchestratorResult:

        result.swc_name = spec.swc_name
        swc_output = self.output_dir / spec.swc_name
        swc_output.mkdir(parents=True, exist_ok=True)

        spec_path = swc_output / "spec.json"
        spec_path.write_text(spec.model_dump_json(indent=2))

        prev_json = spec.model_dump_json()
        errors = []

        for iteration in range(1, self.max_feedback_iters + 1):
            result.iterations = iteration
            logger.info("[Iter %d/%d] Starting ...", iteration, self.max_feedback_iters)

            # ── Layer 2: ARXML Generation ─────────────────────────────
            logger.info("[Layer 2] Generating ARXML ...")
            try:
                from src.arxml_generator import ARXMLGenerator
                from src.schema_validator import validate_all, all_valid, format_errors

                gen = ARXMLGenerator(spec, swc_output)
                arxml_paths = gen.generate_all()
                result.arxml_paths = arxml_paths
                logger.info("[Layer 2] Generated: %s", [p.name for p in arxml_paths])

                val_results = validate_all(arxml_paths)
                if not all_valid(val_results):
                    errors = [format_errors(val_results)]
                    logger.warning("[Layer 2] XSD validation failed: %s", errors)
                    spec = self._feedback(spec, prompt_or_name, prev_json, errors)
                    if spec is None:
                        result.message = "Feedback loop exhausted on XSD errors"
                        break
                    prev_json = spec.model_dump_json()
                    continue

                logger.info("[Layer 2] XSD validation passed")

            except Exception as e:
                result.message = f"Layer 2 failed: {e}"
                logger.error(result.message)
                break

            # ── Layer 3: C Code Generation ────────────────────────────
            if self.arxml_only:
                logger.info("[Layer 3] Skipped (arxml_only=True)")
                result.status = "OK"
                result.message = "ARXML generated successfully"
                result.elapsed_s = round(time.time() - t0, 2)
                return result

            logger.info("[Layer 3] Generating C code ...")
            try:
                from src.c_code_generator import CCodeGenerator

                c_out = swc_output / "c_code"
                gen_c = CCodeGenerator.from_spec(spec, c_out)
                c_paths = gen_c.generate_all()
                result.c_code_paths = c_paths
                logger.info("[Layer 3] Generated: %s", [p.name for p in c_paths])

                result.status = "OK"
                result.message = "ARXML and C code generated successfully"
                result.elapsed_s = round(time.time() - t0, 2)
                logger.info("[Orchestrator] SUCCESS in %.1fs after %d iter(s)",
                            result.elapsed_s, iteration)
                return result

            except Exception as e:
                result.message = f"Layer 3 failed: {e}"
                logger.error(result.message)
                break

        result.elapsed_s = round(time.time() - t0, 2)
        return result

    def _feedback(self, spec, original_prompt: str, prev_json: str,
                  errors: list[str]):
        """Layer 4: Ask Claude to fix the spec based on errors."""
        logger.info("[Layer 4] Sending feedback to Claude (%d errors) ...", len(errors))
        try:
            from src.claude_client import ClaudeClient
            from dotenv import load_dotenv
            load_dotenv()
            client = ClaudeClient()
            corrected = client.send_feedback_prompt(original_prompt, prev_json, errors)
            logger.info("[Layer 4] Corrected spec: %s", corrected.swc_name)
            return corrected
        except Exception as e:
            logger.warning("[Layer 4] Feedback failed: %s", e)
            return None


# ── CLI ───────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    # --test: hardcoded SpeedSensor, no API needed
    if "--test" in args:
        from src.models import SWCSpec
        print("\n== Orchestrator test (no API credits needed) ==\n")
        spec = SWCSpec(**{
            "swc_name": "SpeedSensor",
            "category": "APPLICATION",
            "ports": [{
                "name": "SpeedPort",
                "direction": "R",
                "interface_name": "SpeedSensorInterface",
                "data_element": "VehicleSpeed",
                "data_type": "uint16",
            }],
            "runnables": [
                {"name": "Run10ms", "period_ms": 10,
                 "accesses": [{"port": "SpeedPort", "mode": "read"}]},
                {"name": "InitSpeedSensor", "period_ms": -1, "accesses": []},
            ],
            "init_runnable": "InitSpeedSensor",
        })
        arxml_only = "--arxml-only" in args
        orch = Orchestrator(arxml_only=arxml_only)
        result = orch.run_from_spec(spec)
        print(f"\nResult: {result}")
        if result.ok():
            print("[OK] Pipeline PASSED")
            for p in result.arxml_paths:
                print(f"     {p}")
            for p in result.c_code_paths:
                print(f"     {p}")
        else:
            print(f"[FAIL] {result.message}")
        sys.exit(0 if result.ok() else 1)

    # --from-spec: load existing spec.json
    if "--from-spec" in args:
        idx = args.index("--from-spec")
        spec_path = Path(args[idx + 1])
        from src.models import SWCSpec
        spec = SWCSpec(**json.loads(spec_path.read_text()))
        orch = Orchestrator(arxml_only="--arxml-only" in args)
        result = orch.run_from_spec(spec)
        print(f"\nResult: {result}")
        sys.exit(0 if result.ok() else 1)

    # natural language prompt
    arxml_only = "--arxml-only" in args
    prompt = " ".join(a for a in args if not a.startswith("--"))
    if not prompt:
        print("Error: provide a prompt or use --test")
        sys.exit(1)

    print(f"\n== Orchestrator ==")
    print(f"Prompt    : {prompt}")
    print(f"ARXML only: {arxml_only}\n")

    orch = Orchestrator(arxml_only=arxml_only)
    result = orch.run(prompt)
    print(f"\nResult: {result}")
    print("[OK] Pipeline PASSED" if result.ok() else f"[FAIL] {result.message}")
    sys.exit(0 if result.ok() else 1)


if __name__ == "__main__":
    main()
