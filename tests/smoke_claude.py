"""
tests/smoke_claude.py
---------------------
Phase 0 smoke test for Claude API connection.
Checks: API key -> client init -> API call -> JSON parse -> Pydantic validation

Run:
    python -m tests.smoke_claude
"""

import os
import json
import sys
import time

import anthropic
from pydantic import BaseModel, ValidationError
from typing import Literal, List
from dotenv import load_dotenv

load_dotenv()


# ── Minimal Pydantic models (mirrors src/models.py) ───────────────────────────
class PortSpec(BaseModel):
    name: str
    direction: Literal["P", "R"]
    interface_name: str
    data_element: str
    data_type: Literal["uint8", "uint16", "uint32", "sint8", "sint16", "float32"]


class RunnableSpec(BaseModel):
    name: str
    period_ms: int
    accesses: list


class SWCSpec(BaseModel):
    swc_name: str
    category: Literal["APPLICATION"]
    ports: List[PortSpec]
    runnables: List[RunnableSpec]
    init_runnable: str


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an AUTOSAR Classic R22-11 expert.
Return ONLY a JSON object — no markdown, no explanation, no preamble.

Schema:
{
  "swc_name": string (PascalCase),
  "category": "APPLICATION",
  "ports": [
    {
      "name": string (PascalCase),
      "direction": "P" or "R",
      "interface_name": string,
      "data_element": string,
      "data_type": one of "uint8","uint16","uint32","sint8","sint16","float32"
    }
  ],
  "runnables": [
    {
      "name": string,
      "period_ms": integer,
      "accesses": [{"port": string, "mode": "read" or "write"}]
    }
  ],
  "init_runnable": string
}"""

TEST_PROMPT = (
    "Create an AUTOSAR SWC called SpeedSensor with one R-port "
    "for vehicle speed (uint16) and a 10ms periodic runnable."
)


# ── Test runner ───────────────────────────────────────────────────────────────
def run():
    print("\n" + "=" * 50)
    print("  Claude API smoke test")
    print("=" * 50)

    # 1. Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[FAIL] ANTHROPIC_API_KEY not set.")
        print("       Copy .env.example to .env and fill in your key.")
        sys.exit(1)
    print("[OK]   API key found")

    # 2. Create client
    try:
        client = anthropic.Anthropic(api_key=api_key)
        print("[OK]   anthropic.Anthropic client created")
    except Exception as e:
        print(f"[FAIL] Client init failed: {e}")
        sys.exit(1)

    # 3. Send test request
    print("[...] Sending test prompt to Claude ...")
    t0 = time.time()
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": TEST_PROMPT}],
        )
        elapsed = round(time.time() - t0, 2)
        print(f"[OK]   Response received in {elapsed}s")
    except anthropic.AuthenticationError:
        print("[FAIL] Invalid API key — check ANTHROPIC_API_KEY in your .env")
        sys.exit(1)
    except anthropic.APIConnectionError as e:
        print(f"[FAIL] Network error: {e}")
        sys.exit(1)
    except anthropic.RateLimitError:
        print("[FAIL] Rate limited — wait 60s and retry")
        sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        sys.exit(1)

    # 4. Parse JSON
    raw = msg.content[0].text.strip()
    try:
        data = json.loads(raw)
        print("[OK]   Response is valid JSON")
    except json.JSONDecodeError:
        print(f"[FAIL] Response is not valid JSON. Got:\n{raw[:300]}")
        sys.exit(1)

    # 5. Validate with Pydantic
    try:
        spec = SWCSpec(**data)
        print("[OK]   Pydantic validation passed")
        print(f"       swc_name     : {spec.swc_name}")
        print(f"       ports        : {len(spec.ports)}")
        print(f"       runnables    : {len(spec.runnables)}")
        print(f"       init_runnable: {spec.init_runnable}")
    except ValidationError as e:
        print(f"[FAIL] Pydantic validation failed:\n{e}")
        sys.exit(1)

    print("\nRESULT: Claude API smoke test PASSED")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run()
