"""
run_examples.py
---------------
Runs all 3 worked examples through the full pipeline.
No API credits needed — uses hardcoded specs.

Usage:
    python run_examples.py              # ARXML + C code
    python run_examples.py --arxml-only # ARXML only
"""

import sys
from pathlib import Path
from src.orchestrator import Orchestrator
from src.models import SWCSpec

EXAMPLES = {
    "SpeedSensor": {
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
    },
    "BrakeActuator": {
        "swc_name": "BrakeActuator",
        "category": "APPLICATION",
        "ports": [{
            "name": "BrakeCommandPort",
            "direction": "P",
            "interface_name": "BrakeCommandInterface",
            "data_element": "BrakeTorque",
            "data_type": "float32",
        }],
        "runnables": [
            {"name": "Run5ms", "period_ms": 5,
             "accesses": [{"port": "BrakeCommandPort", "mode": "write"}]},
            {"name": "InitBrakeActuator", "period_ms": -1, "accesses": []},
        ],
        "init_runnable": "InitBrakeActuator",
    },
    "CanGateway": {
        "swc_name": "CanGateway",
        "category": "APPLICATION",
        "ports": [
            {"name": "EngineSpeedIn", "direction": "R",
             "interface_name": "EngineSpeedInterface",
             "data_element": "EngineSpeed", "data_type": "uint16"},
            {"name": "ThrottleIn", "direction": "R",
             "interface_name": "ThrottleInterface",
             "data_element": "ThrottlePosition", "data_type": "uint8"},
            {"name": "EngineSpeedOut", "direction": "P",
             "interface_name": "EngineSpeedOutInterface",
             "data_element": "EngineSpeedFwd", "data_type": "uint16"},
            {"name": "ThrottleOut", "direction": "P",
             "interface_name": "ThrottleOutInterface",
             "data_element": "ThrottlePositionFwd", "data_type": "uint8"},
        ],
        "runnables": [
            {"name": "Run1ms", "period_ms": 1,
             "accesses": [
                 {"port": "EngineSpeedIn",  "mode": "read"},
                 {"port": "ThrottleIn",     "mode": "read"},
                 {"port": "EngineSpeedOut", "mode": "write"},
                 {"port": "ThrottleOut",    "mode": "write"},
             ]},
            {"name": "InitCanGateway", "period_ms": -1, "accesses": []},
        ],
        "init_runnable": "InitCanGateway",
    },
}


def run_all(arxml_only: bool = False):
    mode = "ARXML only" if arxml_only else "ARXML + C code"
    print(f"\n== Phase 6: Worked Examples ({mode}) ==\n")

    results = []
    for name, spec_data in EXAMPLES.items():
        print(f"--- {name} ---")
        spec = SWCSpec(**spec_data)
        folder = name.lower().replace("sensor", "_sensor").replace(
            "actuator", "_actuator").replace("gateway", "_gateway")
        orch = Orchestrator(
            output_dir=Path("examples") / folder,
            arxml_only=arxml_only,
        )
        result = orch.run_from_spec(spec)
        results.append((name, result))

        if result.ok():
            print(f"[OK]   {name} — {result.elapsed_s}s")
            for p in result.arxml_paths:
                print(f"       {p.name}")
            for p in result.c_code_paths:
                print(f"       {p.name}")
        else:
            print(f"[FAIL] {name} — {result.message}")
        print()

    print("== Summary ==")
    passed = 0
    for name, result in results:
        status = "PASS" if result.ok() else "FAIL"
        if result.ok():
            passed += 1
        print(f"  {status}  {name}  ({result.elapsed_s}s)")

    print(f"\n{passed}/{len(results)} examples passed")


if __name__ == "__main__":
    arxml_only = "--arxml-only" in sys.argv
    run_all(arxml_only=arxml_only)
