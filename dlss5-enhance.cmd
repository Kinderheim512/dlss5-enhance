@echo off
setlocal
set "PYTHONIOENCODING=utf-8"

rem No argument means the interface: pythonw.exe allocates no console at all.
if "%~1"=="" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" -m dlss5_enhance
    exit /b 0
)

"%~dp0.venv\Scripts\python.exe" -m dlss5_enhance %*
exit /b %ERRORLEVEL%
