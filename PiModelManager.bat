@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
start "" pythonw.exe "%SCRIPT_DIR%desktop_app.py"
