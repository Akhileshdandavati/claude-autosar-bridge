# Claude x MATLAB AUTOSAR Bridge

An agentic pipeline that takes a natural language software component description, generates AUTOSAR-compliant ARXML files, and imports them directly into MATLAB's AUTOSAR Blockset — automatically.

---

## What it does

```
"Create a SpeedSensor SWC with a 10ms runnable"
                    ↓
            Claude API (Layer 1)
                    ↓
         ARXML Generator (Layer 2)
         datatypes.arxml
         interfaces.arxml
         component.arxml
                    ↓
         MATLAB Bridge (Layer 3)
         Simulink model created
                    ↓
              ✅ Done in ~19s
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Anthropic Claude (claude-sonnet-4) |
| ARXML | Python + autosarfactory |
| MATLAB | MATLAB R2025a + AUTOSAR Blockset |
| Validation | Pydantic v2 + xmlschema |
| Bridge | MATLAB Engine API for Python |

---

## Quick Start

**Requirements:** Python 3.11, MATLAB R2025a with AUTOSAR Blockset

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/claude-autosar-bridge.git
cd claude-autosar-bridge

# 2. Create venv with Python 3.11 (required — MATLAB R2025a needs 3.11)
py -3.11 -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install MATLAB Engine API
cd "C:\Program Files\MATLAB\R2025a\extern\engines\python"
python setup.py install
cd back to project

# 5. Set up API key
copy .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 6. Run smoke tests
python -m tests.smoke_claude
python -m tests.smoke_matlab
```

---

## Usage

**Test without API credits (uses hardcoded SpeedSensor spec):**
```bash
python -m src.orchestrator --test
```

**Test ARXML generation only (no MATLAB):**
```bash
python -m src.orchestrator --test --no-matlab
```

**Full pipeline with natural language prompt (requires API credits):**
```bash
python -m src.orchestrator "Create a SpeedSensor SWC with one R-port for vehicle speed uint16 and a 10ms runnable"
```

**From existing spec file:**
```bash
python -m src.orchestrator --from-spec output/SpeedSensor/spec.json
```

---

## Project Structure

```
claude-autosar-bridge/
├── src/
│   ├── orchestrator.py        # Main pipeline controller (CLI entry point)
│   ├── claude_client.py       # Layer 1: Claude API wrapper
│   ├── prompt_templates.py    # Layer 1: System prompt + few-shot examples
│   ├── models.py              # Layer 1: Pydantic SWCSpec validation
│   ├── arxml_generator.py     # Layer 2: ARXML file generator
│   ├── schema_validator.py    # Layer 2: XSD validation
│   ├── matlab_bridge.py       # Layer 3: MATLAB Engine API wrapper
│   └── feedback_loop.py       # Layer 4: Self-correction loop (Phase 5)
├── matlab_scripts/
│   ├── import_autosar_arxml.m # ARXML import + Simulink model creation
│   ├── run_simulation.m       # Simulink simulation runner
│   ├── generate_rte_code.m    # AUTOSAR C code generation
│   └── parse_errors.m        # MATLAB error classifier
├── tests/
│   ├── smoke_claude.py        # Claude API connection test
│   └── smoke_matlab.py        # MATLAB engine connection test
├── .env.example               # API key template
└── requirements.txt
```

---

## Key Technical Findings

Working through this project uncovered several non-obvious AUTOSAR + MATLAB requirements:

- **autosarfactory submodule** — the real API is `autosarfactory.autosarfactory`, not the top-level package
- **Schema version** — autosarfactory defaults to 00053 but MATLAB R2025a max is 00051 — requires post-save text patch
- **DEST attribute** — `BASE-TYPE-REF` must use `DEST="SW-BASE-TYPE"` not `DEST="SwBaseType"`
- **isService property** — MATLAB's `arxml.importer` requires `IS-SERVICE` set on every `SenderReceiverInterface`
- **MATLAB function caching** — always run `clear all` + `rehash toolboxcache` after engine start
- **JVM required** — AUTOSAR Blockset needs JVM; always start engine without `-nojvm`

---

## Author

**Akhilesh Dandavati**
M.S. Electrical & Computer Engineering — Michigan Technological University

---

## License

MIT