r"""
orchestrator.py
---------------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\orchestrator.py

Main pipeline controller — chains all 4 layers together.

Pipeline:
    User prompt (natural language)
        -> Layer 1: ClaudeClient       -> SWCSpec (Pydantic model)
        -> Layer 2: ARXMLGenerator     -> 3 x .arxml files
        -> Layer 3: MatlabBridge       -> Simulink model
        -> Layer 4: FeedbackLoop       -> self-correction on errors

Usage (full pipeline, requires API credits):
    from src.orchestrator import Orchestrator
    result = Orchestrator().run("Create SpeedSensor SWC with 10ms runnable")

Usage (skip Claude, use existing SWCSpec directly):
    from src.orchestrator import Orchestrator
    from src.models import SWCSpec
    spec = SWCSpec(...)
    result = Orchestrator().run_from_spec(spec)

Usage (skip Claude + MATLAB, test ARXML generation only):
    result = Orchestrator().run_arxml_only("Create SpeedSensor SWC...")

CLI:
    python -m src.orchestrator "Create SpeedSensor SWC with 10ms runnable"
    python -m src.orchestrator --arxml-only "Create SpeedSensor SWC..."
    python -m src.orchestrator --from-spec output/my_spec.json
"""

import json
import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Default output directory ───────────────────────────────────────────
DEFAULT_OUTPUT = Path("output") / "generated"


class OrchestratorResult:
    """Structured result from the orchestrator pipeline."""

    def __init__(self):
        self.status: str = "ERROR"          # "OK" or "ERROR"
        self.swc_name: str = ""
        self.arxml_paths: list[Path] = []
        self.matlab_model: str = ""
        self.message: str = ""
        self.iterations: int = 0            # feedback loop iterations used
        self.elapsed_s: float = 0.0

    def ok(self) -> bool:
        return self.status == "OK"

    def __repr__(self):
        return (
            f"OrchestratorResult("
            f"status={self.status}, "
            f"swc={self.swc_name}, "
            f"model={self.matlab_model}, "
            f"iters={self.iterations}, "
            f"elapsed={self.elapsed_s:.1f}s)"
        )


class Orchestrator:
    """
    Chains all 4 pipeline layers into a single entry point.

    Designed to be flexible:
    - Full run: Claude -> ARXML -> MATLAB (requires API credits + MATLAB)
    - ARXML only: Claude -> ARXML (requires API credits, no MATLAB)
    - From spec: SWCSpec -> ARXML -> MATLAB (no API credits needed)
    """

    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT,
        max_feedback_iters: int = 5,
        use_matlab: bool = True,
        nojvm: bool = False,
    ):
        self.output_dir = output_dir
        self.max_feedback_iters = max_feedback_iters
        self.use_matlab = use_matlab
        self.nojvm = nojvm

    # ── Public entry points ───────────────────────────────────────────
    def run(self, user_prompt: str) -> OrchestratorResult:
        """
        Full pipeline: Claude API -> ARXML -> MATLAB.
        Requires API credits and MATLAB with AUTOSAR Blockset.

        Args:
            user_prompt: Natural language SWC description.

        Returns:
            OrchestratorResult with status, paths, model name.
        """
        result = OrchestratorResult()
        t0 = time.time()

        logger.info("=" * 60)
        logger.info("Orchestrator.run() starting")
        logger.info("Prompt: %s", user_prompt[:80])
        logger.info("=" * 60)

        # ── Layer 1: Claude API ───────────────────────────────────────
        logger.info("[Layer 1] Calling Claude API ...")
        try:
            from src.claude_client import ClaudeClient, ClaudeAuthError
            from dotenv import load_dotenv
            load_dotenv()
            client = ClaudeClient()
            spec = client.send_prompt(user_prompt)
            logger.info("[Layer 1] SWCSpec: %s (%d ports, %d runnables)",
                        spec.swc_name, len(spec.ports), len(spec.runnables))
        except ImportError:
            result.message = "claude_client not available"
            return result
        except Exception as e:
            result.message = f"Layer 1 failed: {e}"
            logger.error(result.message)
            return result

        return self._run_from_spec_internal(spec, user_prompt, result, t0)

    def run_from_spec(self, spec, save_spec: bool = True) -> OrchestratorResult:
        """
        Skip Claude — start from an existing SWCSpec.
        Useful for testing without API credits.

        Args:
            spec:       Validated SWCSpec Pydantic object.
            save_spec:  Save spec as JSON to output_dir.
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

    def run_arxml_only(self, user_prompt: str) -> OrchestratorResult:
        """
        Claude -> ARXML only. No MATLAB.
        Useful when MATLAB is not available.
        """
        old = self.use_matlab
        self.use_matlab = False
        result = self.run(user_prompt)
        self.use_matlab = old
        return result

    # ── Internal pipeline ─────────────────────────────────────────────
    def _run_from_spec_internal(
        self, spec, prompt_or_name: str, result: OrchestratorResult, t0: float
    ) -> OrchestratorResult:
        """
        Shared internal pipeline starting from a validated SWCSpec.
        Handles Layer 2 (ARXML), Layer 3 (MATLAB), Layer 4 (feedback).
        """
        result.swc_name = spec.swc_name
        swc_output = self.output_dir / spec.swc_name
        swc_output.mkdir(parents=True, exist_ok=True)

        # Save spec to JSON for reference
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
                logger.info("[Layer 2] ARXML files: %s",
                            [p.name for p in arxml_paths])

                # XSD validation
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

            # ── Layer 3: MATLAB ───────────────────────────────────────
            if not self.use_matlab:
                logger.info("[Layer 3] Skipped (use_matlab=False)")
                result.status = "OK"
                result.message = "ARXML generated (MATLAB skipped)"
                result.elapsed_s = round(time.time() - t0, 2)
                logger.info("[Orchestrator] Done in %.1fs", result.elapsed_s)
                return result

            logger.info("[Layer 3] Importing into MATLAB ...")
            try:
                from src.matlab_bridge import MatlabBridge
                bridge = MatlabBridge()
                bridge.start(nojvm=self.nojvm)

                matlab_result = bridge.import_arxml(
                    arxml_paths[2],  # component.arxml
                    arxml_paths[0],  # datatypes.arxml
                    arxml_paths[1],  # interfaces.arxml
                    spec.swc_name,
                )
                bridge.stop()

                if matlab_result["status"] == "OK":
                    result.status = "OK"
                    result.matlab_model = matlab_result.get("model", spec.swc_name)
                    result.message = matlab_result.get("message", "")
                    result.elapsed_s = round(time.time() - t0, 2)
                    logger.info("[Orchestrator] SUCCESS in %.1fs after %d iter(s)",
                                result.elapsed_s, iteration)
                    return result
                else:
                    # MATLAB error — feed back to Claude
                    errors = [matlab_result.get("message", "Unknown MATLAB error")]
                    logger.warning("[Layer 3] MATLAB error: %s", errors)
                    spec = self._feedback(spec, prompt_or_name, prev_json, errors)
                    if spec is None:
                        result.message = "Feedback loop exhausted on MATLAB errors"
                        bridge.stop()
                        break
                    prev_json = spec.model_dump_json()

            except Exception as e:
                result.message = f"Layer 3 failed: {e}"
                logger.error(result.message)
                break

        result.elapsed_s = round(time.time() - t0, 2)
        return result

    def _feedback(self, spec, original_prompt: str, prev_json: str,
                  errors: list[str]):
        """
        Layer 4: Ask Claude to fix the spec based on errors.
        Returns corrected SWCSpec or None if Claude unavailable.
        """
        logger.info("[Layer 4] Sending feedback to Claude (%d errors) ...",
                    len(errors))
        try:
            from src.claude_client import ClaudeClient
            from dotenv import load_dotenv
            load_dotenv()
            client = ClaudeClient()
            corrected = client.send_feedback_prompt(
                original_prompt, prev_json, errors
            )
            logger.info("[Layer 4] Corrected spec: %s", corrected.swc_name)
            return corrected
        except Exception as e:
            logger.warning("[Layer 4] Feedback failed (no API?): %s", e)
            return None


# ── CLI entry point ───────────────────────────────────────────────────
def main():
    """
    CLI usage:
        python -m src.orchestrator "Create SpeedSensor SWC with 10ms runnable"
        python -m src.orchestrator --arxml-only "Create SpeedSensor SWC"
        python -m src.orchestrator --from-spec output/SpeedSensor/spec.json
        python -m src.orchestrator --test
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    # ── --test: run with hardcoded SpeedSensor spec (no API needed) ───
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
        use_matlab = "--no-matlab" not in args
        orch = Orchestrator(use_matlab=use_matlab, nojvm=False)
        result = orch.run_from_spec(spec)
        print(f"\nResult: {result}")
        if result.ok():
            print("[OK] Pipeline PASSED")
            for p in result.arxml_paths:
                print(f"     {p}")
            if result.matlab_model:
                print(f"     MATLAB model: {result.matlab_model}")
        else:
            print(f"[FAIL] {result.message}")
        sys.exit(0 if result.ok() else 1)

    # ── --from-spec: load existing spec.json ──────────────────────────
    if "--from-spec" in args:
        idx = args.index("--from-spec")
        spec_path = Path(args[idx + 1])
        from src.models import SWCSpec
        spec = SWCSpec(**json.loads(spec_path.read_text()))
        use_matlab = "--no-matlab" not in args
        orch = Orchestrator(use_matlab=use_matlab, nojvm=False)
        result = orch.run_from_spec(spec)
        print(f"\nResult: {result}")
        sys.exit(0 if result.ok() else 1)

    # ── --arxml-only: Claude -> ARXML, no MATLAB ──────────────────────
    arxml_only = "--arxml-only" in args
    if arxml_only:
        args = [a for a in args if a != "--arxml-only"]

    prompt = " ".join(args)
    if not prompt:
        print("Error: provide a prompt or use --test")
        sys.exit(1)

    print(f"\n== Orchestrator ==")
    print(f"Prompt     : {prompt}")
    print(f"ARXML only : {arxml_only}")
    print()

    orch = Orchestrator(
        use_matlab=not arxml_only,
        nojvm=False,
    )
    result = orch.run(prompt)

    print(f"\nResult: {result}")
    if result.ok():
        print("[OK] Pipeline PASSED")
    else:
        print(f"[FAIL] {result.message}")

    sys.exit(0 if result.ok() else 1)


if __name__ == "__main__":
    main()
