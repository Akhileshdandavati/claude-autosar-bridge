r"""
models.py
---------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\models.py

Layer 1 — Pydantic v2 data models.
SWCSpec is the validated intermediate representation
between Claude's JSON output and the ARXML generator.

All AUTOSAR naming constraints are enforced here so
errors are caught before any file is written.
"""

import re
from pydantic import BaseModel, field_validator, model_validator
from typing import Literal, List


# ── Constants ─────────────────────────────────────────────────────────
VALID_PERIODS = {0, 1, 2, 5, 10, 20, 50, 100}   # ms; 0 = event-triggered, -1 = init
VALID_DATA_TYPES = {"uint8", "uint16", "uint32", "sint8", "sint16", "float32"}
PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


# ── Helpers ───────────────────────────────────────────────────────────
def is_pascal(name: str) -> bool:
    return bool(PASCAL_CASE_RE.match(name))


# ── Sub-models ────────────────────────────────────────────────────────
class AccessSpec(BaseModel):
    """A runnable's access to a port — read or write."""
    port: str
    mode: Literal["read", "write"]

    @field_validator("port")
    @classmethod
    def port_must_be_pascal(cls, v: str) -> str:
        if not is_pascal(v):
            raise ValueError(f"Port name '{v}' must be PascalCase (e.g. SpeedPort)")
        return v


class PortSpec(BaseModel):
    """A single SWC port — provider (P) or requirer (R)."""
    name: str
    direction: Literal["P", "R"]
    interface_name: str
    data_element: str
    data_type: Literal["uint8", "uint16", "uint32", "sint8", "sint16", "float32"]

    @field_validator("name", "interface_name", "data_element")
    @classmethod
    def must_be_pascal(cls, v: str) -> str:
        if not is_pascal(v):
            raise ValueError(f"'{v}' must be PascalCase (e.g. SpeedPort, SpeedSensorInterface)")
        return v


class RunnableSpec(BaseModel):
    """A single runnable entity inside the SWC internal behavior."""
    name: str
    period_ms: int          # ms; 0 = event-triggered; -1 = init runnable
    accesses: List[AccessSpec]

    @field_validator("name")
    @classmethod
    def name_must_be_pascal(cls, v: str) -> str:
        if not is_pascal(v):
            raise ValueError(f"Runnable name '{v}' must be PascalCase")
        return v

    @field_validator("period_ms")
    @classmethod
    def valid_period(cls, v: int) -> int:
        allowed = VALID_PERIODS | {-1}
        if v not in allowed:
            raise ValueError(
                f"period_ms={v} is invalid. "
                f"Use one of {sorted(VALID_PERIODS)} for periodic, "
                f"0 for event-triggered, or -1 for init runnable."
            )
        return v


# ── Top-level model ───────────────────────────────────────────────────
class SWCSpec(BaseModel):
    """
    Complete specification for one AUTOSAR Application SWC.
    Produced by Claude, validated here, consumed by ARXMLGenerator.
    """
    swc_name: str
    category: Literal["APPLICATION"]
    ports: List[PortSpec]
    runnables: List[RunnableSpec]
    init_runnable: str

    @field_validator("swc_name", "init_runnable")
    @classmethod
    def must_be_pascal(cls, v: str) -> str:
        if not is_pascal(v):
            raise ValueError(f"'{v}' must be PascalCase")
        return v

    @field_validator("ports")
    @classmethod
    def at_least_one_port(cls, v: List[PortSpec]) -> List[PortSpec]:
        if len(v) == 0:
            raise ValueError("SWC must have at least one port")
        return v

    @field_validator("runnables")
    @classmethod
    def at_least_one_runnable(cls, v: List[RunnableSpec]) -> List[RunnableSpec]:
        if len(v) == 0:
            raise ValueError("SWC must have at least one runnable")
        return v

    @model_validator(mode="after")
    def init_runnable_must_exist(self) -> "SWCSpec":
        """init_runnable must match the name of one of the runnables."""
        names = {r.name for r in self.runnables}
        if self.init_runnable not in names:
            raise ValueError(
                f"init_runnable '{self.init_runnable}' does not match "
                f"any runnable name. Available: {names}"
            )
        return self

    @model_validator(mode="after")
    def runnable_accesses_must_reference_valid_ports(self) -> "SWCSpec":
        """Every port referenced in runnable accesses must exist in ports list."""
        port_names = {p.name for p in self.ports}
        for r in self.runnables:
            for acc in r.accesses:
                if acc.port not in port_names:
                    raise ValueError(
                        f"Runnable '{r.name}' references port '{acc.port}' "
                        f"which does not exist. Available ports: {port_names}"
                    )
        return self


# ── Quick self-test (run this file directly to verify) ────────────────
if __name__ == "__main__":
    test_data = {
        "swc_name": "SpeedSensor",
        "category": "APPLICATION",
        "ports": [
            {
                "name": "SpeedPort",
                "direction": "R",
                "interface_name": "SpeedSensorInterface",
                "data_element": "VehicleSpeed",
                "data_type": "uint16",
            }
        ],
        "runnables": [
            {
                "name": "Run10ms",
                "period_ms": 10,
                "accesses": [{"port": "SpeedPort", "mode": "read"}],
            },
            {
                "name": "InitSpeedSensor",
                "period_ms": -1,
                "accesses": [],
            },
        ],
        "init_runnable": "InitSpeedSensor",
    }

    spec = SWCSpec(**test_data)
    print(f"[OK] SWCSpec valid: {spec.swc_name}")
    print(f"     ports     : {[p.name for p in spec.ports]}")
    print(f"     runnables : {[r.name for r in spec.runnables]}")