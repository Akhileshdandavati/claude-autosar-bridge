@echo off
:: claude-autosar-bridge runner
:: Usage:
::   run.bat test                          - test pipeline with hardcoded SpeedSensor
::   run.bat examples                      - run all 3 worked examples
::   run.bat ccode                         - test C code generator
::   run.bat arxml "Create SpeedSensor..." - ARXML only (no C code)
::   run.bat "Create SpeedSensor SWC..."   - full pipeline (needs API credits)

call .venv\Scripts\activate

if "%~1"=="test" (
    echo [Running pipeline test - no API credits needed]
    python -m src.orchestrator --test

) else if "%~1"=="examples" (
    echo [Running all 3 worked examples]
    python run_examples.py

) else if "%~1"=="ccode" (
    echo [Testing C code generator]
    python -m src.c_code_generator --test

) else if "%~1"=="arxml" (
    echo [Running ARXML only - no C code]
    python -m src.orchestrator --arxml-only %2 %3 %4 %5

) else if "%~1"=="" (
    echo.
    echo claude-autosar-bridge - Usage:
    echo   run.bat test
    echo   run.bat examples
    echo   run.bat ccode
    echo   run.bat arxml "Create SpeedSensor SWC with 10ms runnable"
    echo   run.bat "Create SpeedSensor SWC with 10ms runnable"
    echo.

) else (
    echo [Running full pipeline - requires API credits]
    python -m src.orchestrator %*
)
