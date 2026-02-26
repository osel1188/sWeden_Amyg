@echo off
REM ============================================================
REM  TILA - Temporal Interference amygdaLA Launcher
REM  Place this file on the Desktop. Edit PROJECT_ROOT below
REM  to match the project location on this computer.
REM ============================================================

REM --- CONFIGURATION (edit these) ---
set "PROJECT_ROOT=F:\GitHub\sWeden_Amyg"
REM Python executable: use "python" if it's on PATH,
REM or set the full path to a venv/conda python, e.g.:
REM   C:\Users\basil\miniconda3\envs\tila\python.exe
REM   C:\Users\basil\project\.venv\Scripts\python.exe
set "PYTHON=python"

REM --- Launch ---
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo ERROR: Could not find project folder: %PROJECT_ROOT%
    pause
    exit /b 1
)

"%PYTHON%" scripts\03_00_TILA_TI-controller-GUI.py -c config\ti_config.json -p config\participant_config.txt

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
