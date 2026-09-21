@echo off
setlocal
set "PYTHONIOENCODING=utf-8"
"%~dp0.venv\Scripts\python.exe" -m dlss5_enhance %*
exit /b %ERRORLEVEL%
