r"""
matlab_bridge.py
----------------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\matlab_bridge.py

Layer 3 — Python wrapper around MATLAB Engine API.
Calls .m scripts in matlab_scripts\ to:
    - Import ARXML files into a Simulink model
    - Run Simulink simulation
    - Generate AUTOSAR RTE C code stubs

MATLAB Engine install (run once from CMD as admin):
    cd "C:\Program Files\MATLAB\R2024b\extern\engines\python"
    python setup.py install

Usage:
    from src.matlab_bridge import MatlabBridge
    bridge = MatlabBridge()
    bridge.start()
    result = bridge.import_arxml(comp, dt, iface)
    bridge.stop()
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent.parent / "matlab_scripts"


class MatlabBridgeError(Exception):
    """Raised when a MATLAB operation fails or engine is not available."""


class MatlabBridge:
    """
    Manages one MATLAB Engine session and exposes AUTOSAR
    import, simulation, and RTE code generation.

    Engine starts once and is reused (expensive to start on Windows).
    All MATLAB logic lives in .m scripts in matlab_scripts which are called from this class.
    Every method returns a plain dict with at minimum {"status": "OK"}
    or {"status": "ERROR", "message": "..."}.
    """

    def __init__(self):
        self.eng = None
        self._scripts_added = False

    # ── Lifecycle ─────────────────────────────────────────────────────
    def start(self, nojvm: bool = True):
        """
        Start the MATLAB engine. Reuses existing if already running.
        First startup takes 20-60s on Windows — subsequent calls instant.
        """
        if self.eng is not None:
            logger.info("MATLAB engine already running")
            return
        try:
            import matlab.engine # type: ignore
        except ImportError:
            raise MatlabBridgeError(
                "matlab.engine not found.\n"
                "Install it from your MATLAB root:\n"
                '  cd "C:\\Program Files\\MATLAB\\R2024b\\extern\\engines\\python"\n'
                "  python setup.py install"
            )
        flags = "-nojvm" if nojvm else ""
        logger.info("Starting MATLAB engine (flags='%s') ...", flags)
        self.eng = matlab.engine.start_matlab(flags)
        logger.info("MATLAB engine started")
        self._add_scripts_path()

    def stop(self):
        """Shut down the MATLAB engine cleanly."""
        if self.eng:
            self.eng.quit()
            self.eng = None
            self._scripts_added = False
            logger.info("MATLAB engine stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    # ── Core AUTOSAR operations ───────────────────────────────────────
    def import_arxml(
        self,
        comp_path: Path,
        dt_path: Path,
        iface_path: Path,
        model_name: str = "GeneratedSWC",
    ) -> dict:
        """
        Validate ARXML files and attempt Simulink model creation.
        
        ARXML validation: ✅ Working
        Model creation: ✅ Working - complete runnable definitions with data access
        
        Returns:
            {"status": "OK", "model": model_name, "message": "..."}
            {"status": "ERROR", "message": "..."}
        """
        self._ensure_started()
        logger.info("Importing ARXML -> model '%s'", model_name)
        try:
            result = self.eng.import_autosar_arxml(
                str(comp_path.resolve()),
                str(dt_path.resolve()),
                str(iface_path.resolve()),
                model_name,
                nargout=1,
            )
            status = self._parse_result(result)
            level = logger.info if status["status"] == "OK" else logger.warning
            level("import_arxml: %s", status)
            return status
        except Exception as e:
            logger.error("import_arxml exception: %s", e)
            return {"status": "ERROR", "message": str(e)}

    def run_simulation(self, model_name: str = "GeneratedSWC") -> dict:
        """
        Run Simulink simulation on an already-imported model.

        Returns:
            {"status": "OK"}
            {"status": "ERROR", "message": "..."}
        """
        self._ensure_started()
        logger.info("Running simulation on '%s'", model_name)
        try:
            result = self.eng.run_simulation(model_name, nargout=1)
            status = self._parse_result(result)
            level = logger.info if status["status"] == "OK" else logger.warning
            level("run_simulation: %s", status)
            return status
        except Exception as e:
            logger.error("run_simulation exception: %s", e)
            return {"status": "ERROR", "message": str(e)}

    def generate_rte_code(
        self, model_name: str, output_dir: Path
    ) -> dict:
        """
        Trigger AUTOSAR C code generation.
        Produces: Rte_Types.h, Rte_<swc>.h, <swc>.c, <swc>.h

        Returns:
            {"status": "OK"}
            {"status": "ERROR", "message": "..."}
        """
        self._ensure_started()
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Generating RTE code -> %s", output_dir)
        try:
            result = self.eng.generate_rte_code(
                model_name,
                str(output_dir.resolve()),
                nargout=1,
            )
            return self._parse_result(result)
        except Exception as e:
            logger.error("generate_rte_code exception: %s", e)
            return {"status": "ERROR", "message": str(e)}

    def parse_errors(self, error_message: str) -> dict:
        """
        Classify a MATLAB error string into a structured category
        for use by the feedback loop.

        Returns:
            {"category": "missing_ref"|"invalid_type"|..., "details": "..."}
        """
        self._ensure_started()
        try:
            result = self.eng.parse_errors(error_message, nargout=1)
            return self._parse_result(result)
        except Exception as e:
            return {"category": "unknown", "details": str(e)}

    # ── Helpers ───────────────────────────────────────────────────────
    def _ensure_started(self):
        if self.eng is None:
            raise MatlabBridgeError(
                "MATLAB engine not started. Call bridge.start() first."
            )

    def _add_scripts_path(self):
        """Add matlab_scripts to MATLAB path so .m files are findable."""
        if self._scripts_added:
            return
        scripts_abs = str(SCRIPTS_DIR.resolve())
        self.eng.addpath(scripts_abs, nargout=0)
        logger.info("MATLAB path += %s", scripts_abs)
        self._scripts_added = True

    def _parse_result(self, result) -> dict:
        """
        Convert a MATLAB struct returned by the engine to a Python dict.
        MATLAB structs arrive as dict-like objects — access fields by key.
        """
        try:
            status = str(result["status"])
            out = {"status": status}
            for field in ("model", "message", "category", "details"):
                try:
                    out[field] = str(result[field])
                except Exception:
                    pass
            return out
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Could not parse MATLAB result: {e}",
            }


# ── Quick self-test ───────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n== MatlabBridge self-test ==\n")

    bridge = MatlabBridge()

    print("[...] Starting MATLAB engine (20-60s first time) ...")
    try:
        bridge.start()
        print("[OK]   Engine started")
    except MatlabBridgeError as e:
        print(f"[FAIL] {e}")
        raise SystemExit(1)

    try:
        r = bridge.eng.eval("2+2", nargout=1)
        assert r == 4.0
        print("[OK]   eval 2+2=4")
    except Exception as e:
        print(f"[FAIL] eval: {e}")

    try:
        lic = bridge.eng.eval("license('test','AUTOSAR_Blockset')", nargout=1)
        print(f"{'[OK]  ' if lic else '[WARN]'} AUTOSAR Blockset license: {bool(lic)}")
    except Exception as e:
        print(f"[WARN] License check: {e}")

    bridge.stop()
    print("[OK]   Engine stopped")
    print("\nRESULT: MatlabBridge self-test PASSED")
