r"""
claude_client.py
----------------
FOLDER : claude-autosar-integration\src\
FILE   : src\claude_client.py

Layer 1 — Wrapper around Anthropic Claude API.

Responsibilities:
  - Send prompt to Claude using SYSTEM_PROMPT + few-shot messages
  - Parse raw response text as JSON
  - Validate JSON against SWCSpec Pydantic model
  - Retry on transient errors with exponential backoff (via tenacity)
  - Return a validated SWCSpec on success
  - Raise descriptive exceptions on failure

Usage:
    from src.claude_client import ClaudeClient
    client = ClaudeClient()
    spec = client.send_prompt("Create a SpeedSensor SWC with 10ms runnable")
    print(spec.swc_name)
"""

import os
import json
import logging

import anthropic
from pydantic import ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from dotenv import load_dotenv

from src.models import SWCSpec
from src.prompt_templates import SYSTEM_PROMPT, build_messages

load_dotenv()

logger = logging.getLogger(__name__)

MODEL         = "claude-sonnet-4-20250514"
MAX_TOKENS    = 1024
MAX_RETRIES   = 3


# ── Custom exceptions ─────────────────────────────────────────────────
class ClaudeJSONError(Exception):
    """Claude returned a response that could not be parsed as JSON."""


class ClaudeSchemaError(Exception):
    """Claude returned valid JSON but it failed Pydantic SWCSpec validation."""


class ClaudeAuthError(Exception):
    """API key is invalid or missing."""


# ── Retry decorator — retries on transient network/rate errors only ───
def _make_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


# ── Main client ───────────────────────────────────────────────────────
class ClaudeClient:
    """
    Sends AUTOSAR SWC specifications to Claude and returns
    validated SWCSpec objects.
    """

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ClaudeAuthError(
                "ANTHROPIC_API_KEY not set. "
                "Add it to your .env file or pass api_key= explicitly."
            )
        self.client = anthropic.Anthropic(api_key=key)
        logger.info("ClaudeClient initialised (model=%s)", MODEL)

    def send_prompt(self, user_prompt: str) -> SWCSpec:
        """
        Send a natural language SWC description to Claude.

        Args:
            user_prompt: Plain English description of the SWC.

        Returns:
            Validated SWCSpec Pydantic model.

        Raises:
            ClaudeJSONError   — response was not valid JSON
            ClaudeSchemaError — JSON did not match SWCSpec schema
            ClaudeAuthError   — API key invalid
            anthropic.RateLimitError — after all retries exhausted
        """
        logger.info("Sending prompt: %s", user_prompt[:80])
        raw = self._call_api(user_prompt)
        data = self._parse_json(raw)
        spec = self._validate_schema(data)
        logger.info("SWCSpec validated: %s (%d ports, %d runnables)",
                    spec.swc_name, len(spec.ports), len(spec.runnables))
        return spec

    def send_feedback_prompt(
        self,
        original_prompt: str,
        previous_json: str,
        errors: list[str],
    ) -> SWCSpec:
        """
        Send a correction prompt to Claude when MATLAB or XSD validation failed.
        Includes the original prompt, previous JSON, and error list.

        Args:
            original_prompt: The user's original SWC description.
            previous_json:   Claude's previous (broken) JSON output as a string.
            errors:          List of error strings from MATLAB or XSD validator.

        Returns:
            Corrected, validated SWCSpec.
        """
        error_block = "\n".join(f"  - {e}" for e in errors)
        feedback_prompt = (
            f"Your previous JSON output caused the following errors:\n"
            f"{error_block}\n\n"
            f"Original request:\n{original_prompt}\n\n"
            f"Your previous output:\n{previous_json}\n\n"
            f"Return ONLY the corrected JSON. Fix ALL errors listed above."
        )
        logger.warning("Sending feedback prompt with %d errors", len(errors))
        return self.send_prompt(feedback_prompt)

    # ── Private helpers ───────────────────────────────────────────────
    @_make_retry()
    def _call_api(self, user_prompt: str) -> str:
        """Call Claude API. Retried automatically on transient errors."""
        try:
            msg = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=build_messages(user_prompt),
            )
            return msg.content[0].text.strip()
        except anthropic.AuthenticationError as e:
            raise ClaudeAuthError(
                "Invalid API key — check ANTHROPIC_API_KEY in .env"
            ) from e

    def _parse_json(self, raw: str) -> dict:
        """Parse raw Claude response as JSON, stripping markdown fences if present."""
        # Strip markdown code fences if Claude accidentally added them
        cleaned = raw
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Remove first line (```json or ```) and last line (```)
            cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ClaudeJSONError(
                f"Claude response is not valid JSON.\n"
                f"Parse error: {e}\n"
                f"Raw response (first 500 chars):\n{raw[:500]}"
            ) from e

    def _validate_schema(self, data: dict) -> SWCSpec:
        """Validate parsed JSON dict against SWCSpec Pydantic model."""
        try:
            return SWCSpec(**data)
        except ValidationError as e:
            raise ClaudeSchemaError(
                f"JSON does not match SWCSpec schema.\n"
                f"Validation errors:\n{e}\n"
                f"Received data: {json.dumps(data, indent=2)}"
            ) from e


# ── Quick self-test (requires API key + credits) ──────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\n== ClaudeClient self-test ==")
    try:
        client = ClaudeClient()
        spec = client.send_prompt(
            "Create an AUTOSAR SWC called ThrottleController "
            "with one R-port for throttle position (uint8) "
            "and a 20ms runnable."
        )
        print(f"[OK] swc_name     : {spec.swc_name}")
        print(f"[OK] ports        : {[p.name for p in spec.ports]}")
        print(f"[OK] runnables    : {[r.name for r in spec.runnables]}")
        print(f"[OK] init_runnable: {spec.init_runnable}")
        print("\nRESULT: PASSED")
    except ClaudeAuthError as e:
        print(f"[FAIL] Auth: {e}")
    except ClaudeJSONError as e:
        print(f"[FAIL] JSON: {e}")
    except ClaudeSchemaError as e:
        print(f"[FAIL] Schema: {e}")
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")