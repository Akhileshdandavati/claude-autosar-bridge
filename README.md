# Claude x AUTOSAR Bridge


An agentic pipeline that takes a natural language software component description,
generates AUTOSAR R22-11 compliant ARXML files, and produces C code skeletons -
replacing tools like Vector DaVinci and Embedded Coder with a free, open source
Python pipeline.

---

## What it does

```
"Create a SpeedSensor SWC that reads vehicle speed as uint16 every 10ms"
                                    |
                            Claude API (Layer 1)
                                    |
                          SWCSpec (Pydantic model)
                                    |
                         ARXML Generator (Layer 2)
                         |-- datatypes.arxml
                         |-- interfaces.arxml
                         +-- component.arxml
                                    |
                         C Code Generator (Layer 3)
                         |-- Rte_Types.h
                         |-- Rte_SpeedSensor.h
                         |-- SpeedSensor.h
                         +-- SpeedSensor.c
                                    |
                              Done in < 1 second
```

---

## Why this exists

In automotive software development, setting up an AUTOSAR software component requires
writing ARXML files by hand in tools like Vector DaVinci or ETAS ISOLAR, then using
commercial code generators to produce C skeletons. This takes 2-4 hours per component
and requires expensive licenses.

This tool reduces that to a single English sentence and under a second of runtime.

The concept is identical to what `cantools` does for CAN bus - parse a structured
description and generate C scaffolding. This project does the same one layer up:
AUTOSAR SWC descriptions instead of DBC signal definitions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Anthropic Claude (claude-sonnet-4) |
| ARXML | Python + autosarfactory |
| C Code | Pure Python generator |
| Validation | Pydantic v2 + xmlschema (AUTOSAR_00051.xsd) |

---

## Quick Start

**Requirements:** Python 3.11

```bash
# 1. Clone
git clone https://github.com/Akhileshdandavati/claude-autosar-bridge.git
cd claude-autosar-bridge

# 2. Create venv with Python 3.11
py -3.11 -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set API key
copy .env.example .env
# Edit .env: ANTHROPIC_API_KEY=sk-ant-...
```

---

## Usage

**Test without API credits (hardcoded SpeedSensor spec):**
```bash
run.bat test
# or
python -m src.orchestrator --test
```

**Run all 3 worked examples:**
```bash
run.bat examples
# or
python run_examples.py
```

**Full pipeline with natural language prompt (requires API credits):**
```bash
run.bat "Create a SpeedSensor SWC with R-port for vehicle speed uint16 and 10ms runnable"
# or
python -m src.orchestrator "Create a SpeedSensor SWC..."
```

---

## Prompt Examples

The pipeline accepts any natural language description of an AUTOSAR SWC.
Here are examples that all work out of the box:

**Simple sensor:**
```
"Create a SpeedSensor SWC with R-port for vehicle speed uint16 and 10ms runnable"
```

**Actuator with P-port:**
```
"BrakeActuator SWC with P-port for brake torque float32 and 5ms periodic runnable"
```

**Multi-port gateway:**
```
"CAN gateway that reads engine speed uint16 and throttle uint8, forwards both, 1ms cycle"
```

**Temperature monitor:**
```
"EngineMonitor SWC with sint16 temperature sensor input, init runnable and 100ms periodic"
```

**Throttle controller:**
```
"ThrottleController with R-ports for pedal position uint16 and engine speed uint16, 2ms periodic"
```

**What Claude understands from a prompt:**
- SWC name
- Port direction (R-port = read/receive, P-port = write/send)
- Data type (uint8, uint16, uint32, sint8, sint16, float32)
- Runnable period (1ms, 5ms, 10ms, 100ms etc.)
- Init runnable (triggered once at startup)

---

## Output Files

For a `SpeedSensor` SWC the pipeline produces:

```
output/generated/SpeedSensor/
|-- datatypes.arxml       # AUTOSAR base types + implementation types
|-- interfaces.arxml      # SenderReceiver interface definitions
|-- component.arxml       # Full SWC: ports, runnables, timing events
+-- c_code/
    |-- Rte_Types.h       # AUTOSAR primitive typedefs
    |-- Rte_SpeedSensor.h # RTE API macros (Rte_IRead / Rte_IWrite)
    |-- SpeedSensor.h     # Runnable declarations
    +-- SpeedSensor.c     # Runnable skeletons - fill in your logic
```

**Example generated C code (`SpeedSensor.c`):**
```c
void SpeedSensor_Run10ms(void)
{
    uint16 VehicleSpeed = Rte_IRead_Run10ms_SpeedPort_VehicleSpeed();
    (void)VehicleSpeed;  /* TODO: use value */
}

void SpeedSensor_InitSpeedSensor(void)
{
    /* TODO: implement */
}
```

---

## Project Structure

```
claude-autosar-bridge/
|-- src/
|   |-- orchestrator.py        # Main pipeline CLI
|   |-- claude_client.py       # Layer 1: Claude API
|   |-- prompt_templates.py    # Layer 1: System prompt + few-shot examples
|   |-- models.py              # Layer 1: Pydantic SWCSpec
|   |-- arxml_generator.py     # Layer 2: ARXML generator
|   |-- schema_validator.py    # Layer 2: XSD validation
|   |-- c_code_generator.py    # Layer 3: C code generator
|   +-- feedback_loop.py       # Layer 4: Self-correction loop
|-- schemas/
|   +-- AUTOSAR_00051.xsd      # AUTOSAR R22-11 schema for validation
|-- examples/
|   |-- speed_sensor/          # R-port, uint16, 10ms - fully verified
|   |-- brake_actuator/        # P-port, float32, 5ms
|   +-- can_gateway/           # Multi-port, 1ms
|-- .github/workflows/
|   +-- ci.yml                 # GitHub Actions CI
|-- run.bat                    # Windows batch runner
|-- run_examples.py            # Batch example runner
+-- requirements.txt
```

---

## Worked Examples

| SWC | Ports | Period | Status |
|---|---|---|---|
| SpeedSensor | R-port uint16 | 10ms | ARXML + C code verified |
| BrakeActuator | P-port float32 | 5ms | ARXML + C code verified |
| CanGateway | 2R + 2P ports | 1ms | ARXML + C code verified |


---

## Comparison with Existing Tools

| Tool | Input | Output | Cost | Open Source |
|---|---|---|---|---|
| Vector DaVinci | GUI config | ARXML | $$$$ | No |
| ETAS ISOLAR | GUI config | ARXML | $$$$ | No |
| Embedded Coder | Simulink model | C code | $$$$ | No |
| **claude-autosar-bridge** | **Plain English** | **ARXML + C code** | **Free*** | **Yes** |

*Requires Anthropic API credits (~$0.003 per SWC)

---

## Key Technical Notes

- **autosarfactory submodule** - real API is `autosarfactory.autosarfactory`
- **Schema version** - capped at 00051 (autosarfactory defaults to 00053)
- **DEST attribute** - `BASE-TYPE-REF` requires `DEST="SW-BASE-TYPE"`
- **isService** - requires `BooleanValueVariationPoint` object, not a Python bool
- **C code generator** - reads from SWCSpec or directly from any ARXML folder

---

## Author

**Akhilesh Dandavati**
M.S. Electrical & Computer Engineering - Michigan Technological University
github.com/Akhileshdandavati

---

## License

MIT
