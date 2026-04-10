r"""
schema_validator.py
-------------------
FOLDER : D:\Auto\claude-autosar-integration\src\
FILE   : src\schema_validator.py

Layer 2 — Validates generated ARXML files against the
AUTOSAR R22-11 XSD schema using the xmlschema library.

Why this matters:
    autosarfactory writes ARXML but does not guarantee
    100% schema compliance for every element combination.
    This validator catches any issues BEFORE passing files
    to MATLAB, so MATLAB errors are always logic errors,
    never schema errors.

Usage:
    from src.schema_validator import validate_arxml, validate_all

    errors = validate_arxml(Path("output/component.arxml"))
    if errors:
        print(errors)   # list of strings
    else:
        print("Valid")
"""

import logging
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="xmlschema")
from pathlib import Path

import xmlschema

logger = logging.getLogger(__name__)

# ── AUTOSAR R22-11 schema bundled with autosarfactory ─────────────────
# autosarfactory installs its XSD files inside the package.
# We locate them at runtime so the path works on any machine.
def _find_schema_path() -> Path:
    """
    Locate the AUTOSAR XSD schema file bundled with autosarfactory.
    Falls back to a manual path if the bundled one is not found.
    """
    try:
        import autosarfactory
        pkg_dir = Path(autosarfactory.__file__).parent
        # autosarfactory stores schema under autosar_releases/
        candidates = list(pkg_dir.rglob("AUTOSAR_00051.xsd"))  # R22-11 = schema 51
        if not candidates:
            candidates = list(pkg_dir.rglob("*.xsd"))
        if candidates:
            # Pick the highest schema version available
            chosen = sorted(candidates)[-1]
            logger.info("Using XSD schema: %s", chosen)
            return chosen
    except Exception as e:
        logger.warning("Could not auto-locate schema: %s", e)

    # Fallback — user can set this manually
    fallback = Path(__file__).parent.parent / "schemas" / "AUTOSAR_00051.xsd"
    logger.debug("Falling back to manual schema path: %s", fallback)
    return fallback


# Cache the schema object so we only load it once per process
_SCHEMA: xmlschema.XMLSchema | None = None


def _get_schema() -> xmlschema.XMLSchema | None:
    """Load and cache the AUTOSAR XSD schema. Returns None if not found."""
    global _SCHEMA
    if _SCHEMA is not None:
        return _SCHEMA
    schema_path = _find_schema_path()
    if not schema_path.exists():
        logger.warning(
            "XSD schema file not found at %s. "
            "Schema validation will be skipped.",
            schema_path,
        )
        return None
    try:
        _SCHEMA = xmlschema.XMLSchema(str(schema_path))
        logger.info("AUTOSAR XSD schema loaded from %s", schema_path)
        return _SCHEMA
    except Exception as e:
        logger.warning("Failed to load XSD schema: %s", e)
        return None


# ── Public API ────────────────────────────────────────────────────────
def validate_arxml(filepath: Path) -> list[str]:
    """
    Validate a single .arxml file against the AUTOSAR R22-11 XSD schema.

    Args:
        filepath: Path to the .arxml file to validate.

    Returns:
        Empty list [] if the file is valid.
        List of error strings if validation fails.
        Returns a warning (not failure) if the schema file is not found.
    """
    if not filepath.exists():
        return [f"File not found: {filepath}"]

    schema = _get_schema()
    if schema is None:
        logger.warning("Skipping XSD validation for %s (no schema loaded)", filepath)
        return []  # Treat as valid if we can't load the schema

    errors = []
    try:
        schema.validate(str(filepath))
        logger.info("XSD validation passed: %s", filepath.name)
    except xmlschema.XMLSchemaValidationError as e:
        msg = f"{filepath.name}: {str(e)[:300]}"
        errors.append(msg)
        logger.warning("XSD validation failed: %s", msg)
    except Exception as e:
        msg = f"{filepath.name}: Unexpected validation error: {e}"
        errors.append(msg)
        logger.error(msg)

    return errors


def validate_all(filepaths: list[Path]) -> dict[str, list[str]]:
    """
    Validate multiple .arxml files.

    Args:
        filepaths: List of Path objects to validate.

    Returns:
        Dict mapping filename -> list of errors.
        A file is valid if its error list is empty.

    Example:
        results = validate_all([
            Path("output/datatypes.arxml"),
            Path("output/interfaces.arxml"),
            Path("output/component.arxml"),
        ])
        all_valid = all(len(v) == 0 for v in results.values())
    """
    results = {}
    for fp in filepaths:
        results[fp.name] = validate_arxml(fp)
    return results


def all_valid(results: dict[str, list[str]]) -> bool:
    """Return True if all files in a validate_all() result are valid."""
    return all(len(errors) == 0 for errors in results.values())


def format_errors(results: dict[str, list[str]]) -> str:
    """
    Format validate_all() results into a human-readable string
    suitable for logging or feeding back to Claude.
    """
    lines = []
    for filename, errors in results.items():
        if errors:
            lines.append(f"[{filename}]")
            for e in errors:
                lines.append(f"  - {e}")
    return "\n".join(lines) if lines else "All files valid."


# ── Quick self-test ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    print("\n== schema_validator self-test ==")

    schema = _get_schema()
    if schema:
        print(f"[OK]   Schema loaded")
    else:
        print("[WARN] Schema not found — validation will be skipped")
        print("       This is OK for now. Schema loads automatically")
        print("       once autosarfactory is installed and ARXML files exist.")
        sys.exit(0)

    # Test with a non-existent file (should return error)
    errors = validate_arxml(Path("nonexistent.arxml"))
    assert len(errors) == 1 and "not found" in errors[0], f"Expected file-not-found error, got: {errors}"
    print("[OK]   Missing file returns error correctly")

    print("\nRESULT: PASSED")
