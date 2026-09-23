@echo off
setlocal
cd /d "%~dp0"

echo === Installing PyInstaller into .venv ===
".venv\Scripts\python.exe" -m pip install --quiet --upgrade "pyinstaller>=6.0" || goto :error

echo === Building the single-file executable ===
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean dlss5-enhance.spec || goto :error

echo === Copying the configuration next to the executable ===
copy /y config.yaml dist\config.yaml >nul
if not exist "dist\workflows" mkdir "dist\workflows"
copy /y "workflows\README.md" "dist\workflows\README.md" >nul
copy /y "workflows\exemple_dlss5_video.json" "dist\workflows\exemple_dlss5_video.json" >nul
copy /y "workflows\exemple_dlss5_image.json" "dist\workflows\exemple_dlss5_image.json" >nul
copy /y LICENSE dist\LICENSE >nul
copy /y README.md dist\README.md >nul

echo.
echo === Done: dist\DLSS5-Enhance.exe ===
echo Ship the whole dist\ folder (exe + config.yaml + workflows\ + README + LICENSE).
exit /b 0

:error
echo.
echo *** Build failed ***
exit /b 1
