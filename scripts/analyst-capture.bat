@echo off
REM Windows capture launcher.
REM Easiest auto-start: drop a shortcut to this file in the Startup folder
REM (Win+R -> shell:startup -> paste shortcut).
REM
REM Or use Task Scheduler:
REM   - Trigger: At log on (your user)
REM   - Action:  Start a program -> this .bat
REM   - "Start in" set to the repo root
REM   - "Run only when user is logged on" + "Run with highest privileges" off

cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
analyst capture
