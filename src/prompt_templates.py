r"""
prompt_templates.py
-------------------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\prompt_templates.py

Layer 1 — System prompt and few-shot examples for Claude API.

SYSTEM_PROMPT tells Claude:
  1. Role      — AUTOSAR Classic R22-11 expert
  2. Format    — return ONLY JSON, no markdown, no preamble
  3. Schema    — exact field names, types, and constraints
  4. Rules     — PascalCase, valid periods, port references

FEW_SHOT_EXAMPLES are injected as prior turns in the
messages list so Claude has concrete correct examples
before seeing the real user prompt.
"""


# ── System prompt ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an AUTOSAR Classic R22-11 software architect.

When given a component description, return ONLY a JSON object.
No markdown fences, no explanation, no preamble. Just the raw JSON.

=== JSON SCHEMA ===
{
  "swc_name":      string,   // PascalCase, e.g. "SpeedSensor"
  "category":      "APPLICATION",
  "ports": [
    {
      "name":           string,         // PascalCase, e.g. "SpeedPort"
      "direction":      "P" | "R",      // P = Provider/Sender, R = Requirer/Receiver
      "interface_name": string,         // PascalCase, e.g. "SpeedSensorInterface"
      "data_element":   string,         // PascalCase, e.g. "VehicleSpeed"
      "data_type":      "uint8" | "uint16" | "uint32" | "sint8" | "sint16" | "float32"
    }
  ],
  "runnables": [
    {
      "name":       string,   // PascalCase, e.g. "Run10ms"
      "period_ms":  integer,  // 1/2/5/10/20/50/100 for periodic, 0 = event, -1 = init
      "accesses":   [{"port": string, "mode": "read" | "write"}]
    }
  ],
  "init_runnable": string    // must match the name of one runnable with period_ms = -1
}

=== HARD RULES ===
1. ALL names (swc_name, port names, interface names, runnable names) must be PascalCase.
2. period_ms must be one of: -1, 0, 1, 2, 5, 10, 20, 50, 100.
   -1 means init runnable (called once at startup).
   0  means event-triggered (no periodic timer).
3. Every port referenced in runnable accesses must exist in the ports list.
4. init_runnable must equal the name of the runnable with period_ms = -1.
5. Provider ports (P) are written to. Requirer ports (R) are read from.
6. Return ONLY the JSON object. Nothing else."""


# ── Few-shot examples ─────────────────────────────────────────────────
# These are injected as prior assistant turns so Claude has
# concrete correct examples before the real user prompt.
#
# Format: list of (user_prompt, expected_json_string) tuples.

FEW_SHOT_EXAMPLES = [
    (
        # ── Example 1: Simple sensor SWC ─────────────────────────
        "Create an AUTOSAR SWC called SpeedSensor with one R-port "
        "for vehicle speed (uint16) and a 10ms periodic runnable.",

        """{
  "swc_name": "SpeedSensor",
  "category": "APPLICATION",
  "ports": [
    {
      "name": "SpeedPort",
      "direction": "R",
      "interface_name": "SpeedSensorInterface",
      "data_element": "VehicleSpeed",
      "data_type": "uint16"
    }
  ],
  "runnables": [
    {
      "name": "Run10ms",
      "period_ms": 10,
      "accesses": [{"port": "SpeedPort", "mode": "read"}]
    },
    {
      "name": "InitSpeedSensor",
      "period_ms": -1,
      "accesses": []
    }
  ],
  "init_runnable": "InitSpeedSensor"
}"""
    ),

    (
        # ── Example 2: Actuator SWC with provider port ───────────
        "Create an AUTOSAR SWC called BrakeActuator. It should have "
        "a P-port for brake torque command (float32) and a 5ms runnable.",

        """{
  "swc_name": "BrakeActuator",
  "category": "APPLICATION",
  "ports": [
    {
      "name": "BrakeCommandPort",
      "direction": "P",
      "interface_name": "BrakeCommandInterface",
      "data_element": "BrakeTorque",
      "data_type": "float32"
    }
  ],
  "runnables": [
    {
      "name": "Run5ms",
      "period_ms": 5,
      "accesses": [{"port": "BrakeCommandPort", "mode": "write"}]
    },
    {
      "name": "InitBrakeActuator",
      "period_ms": -1,
      "accesses": []
    }
  ],
  "init_runnable": "InitBrakeActuator"
}"""
    ),

    (
        # ── Example 3: Gateway SWC with multiple ports ───────────
        "Create a CAN gateway SWC called CanGateway with two R-ports "
        "(engine speed uint16, throttle uint8) and two P-ports "
        "(forwarded speed uint16, forwarded throttle uint8). "
        "Use a 1ms runnable.",

        """{
  "swc_name": "CanGateway",
  "category": "APPLICATION",
  "ports": [
    {
      "name": "EngineSpeedIn",
      "direction": "R",
      "interface_name": "EngineSpeedInterface",
      "data_element": "EngineSpeed",
      "data_type": "uint16"
    },
    {
      "name": "ThrottleIn",
      "direction": "R",
      "interface_name": "ThrottleInterface",
      "data_element": "ThrottlePosition",
      "data_type": "uint8"
    },
    {
      "name": "EngineSpeedOut",
      "direction": "P",
      "interface_name": "EngineSpeedOutInterface",
      "data_element": "EngineSpeedFwd",
      "data_type": "uint16"
    },
    {
      "name": "ThrottleOut",
      "direction": "P",
      "interface_name": "ThrottleOutInterface",
      "data_element": "ThrottlePositionFwd",
      "data_type": "uint8"
    }
  ],
  "runnables": [
    {
      "name": "Run1ms",
      "period_ms": 1,
      "accesses": [
        {"port": "EngineSpeedIn",  "mode": "read"},
        {"port": "ThrottleIn",     "mode": "read"},
        {"port": "EngineSpeedOut", "mode": "write"},
        {"port": "ThrottleOut",    "mode": "write"}
      ]
    },
    {
      "name": "InitCanGateway",
      "period_ms": -1,
      "accesses": []
    }
  ],
  "init_runnable": "InitCanGateway"
}"""
    ),
]


def build_messages(user_prompt: str) -> list[dict]:
    """
    Build the full messages list for the Claude API call.
    Injects few-shot examples as prior turns before the real prompt.

    Args:
        user_prompt: The user's natural language SWC description.

    Returns:
        List of message dicts ready for client.messages.create(messages=...)
    """
    messages = []

    # Inject each few-shot example as a prior user/assistant exchange
    for user_ex, assistant_ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user",      "content": user_ex})
        messages.append({"role": "assistant", "content": assistant_ex})

    # Append the real user prompt last
    messages.append({"role": "user", "content": user_prompt})

    return messages


# ── Quick self-test ───────────────────────────────────────────────────
if __name__ == "__main__":
    msgs = build_messages("Create a throttle controller SWC with a 20ms runnable.")
    print(f"[OK] build_messages returned {len(msgs)} message(s)")
    print(f"     first role : {msgs[0]['role']}")
    print(f"     last  role : {msgs[-1]['role']}")
    print(f"     last  content preview: {msgs[-1]['content'][:60]}")