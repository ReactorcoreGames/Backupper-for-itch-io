@echo off
setlocal
cd /d "%~dp0"

set PROJECT_NAME=Backupper-for-itch-io
set RELEASE_DIR=dist\%PROJECT_NAME%
set WORK_DIR=build

:: A running copy locks its files, so find out before anything gets deleted.
:: Full path, because Git Bash puts its unrelated Unix find first on PATH.
tasklist /fi "imagename eq %PROJECT_NAME%.exe" | "%SystemRoot%\System32\find.exe" /i "%PROJECT_NAME%.exe" >nul
if not errorlevel 1 (
  echo ERROR: %PROJECT_NAME%.exe is running. Close it and build again.
  goto :failed
)

echo Building %PROJECT_NAME%...

:: Clean previous build output. config.json and downloaded-backups are never touched.
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
if exist "dist\%PROJECT_NAME%.zip" del /q "dist\%PROJECT_NAME%.zip"
if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"

:: Compile. PyInstaller output goes under build\ so dist\ holds only the release.
python -m PyInstaller --noconfirm --onedir --windowed ^
  --icon "%~dp0assets\icon.ico" ^
  --add-data "%~dp0assets;assets" ^
  --name "%PROJECT_NAME%" ^
  --distpath "%WORK_DIR%\pyinstaller-dist" ^
  --workpath "%WORK_DIR%\pyinstaller-work" ^
  --specpath "%WORK_DIR%" ^
  main.py
if errorlevel 1 goto :failed

:: Assemble the release. promo.md and config.json are private and stay out of it.
mkdir "%RELEASE_DIR%"
xcopy /e /q /y "%WORK_DIR%\pyinstaller-dist\%PROJECT_NAME%\*" "%RELEASE_DIR%\" >nul
if errorlevel 1 goto :failed
copy /y "readme.md" "%RELEASE_DIR%\readme.md" >nul
copy /y "guide.md" "%RELEASE_DIR%\guide.md" >nul
copy /y "LICENSE" "%RELEASE_DIR%\LICENSE" >nul
mkdir "%RELEASE_DIR%\promo"
copy /y "promo\thumbnail_630x500.jpg" "%RELEASE_DIR%\promo\" >nul
copy /y "promo\cover_1280x720.jpg" "%RELEASE_DIR%\promo\" >nul
copy /y "promo\icon_og.jpg" "%RELEASE_DIR%\promo\" >nul
copy /y "promo\screenshot_*.png" "%RELEASE_DIR%\promo\" >nul

if exist "%RELEASE_DIR%\config.json" (
  echo ERROR: config.json ended up in the release. Aborting.
  goto :failed
)

:: Zip it, keeping the project folder as the zip's root.
python tools\make_zip.py dist "%PROJECT_NAME%"
if errorlevel 1 goto :failed
if not exist "dist\%PROJECT_NAME%.zip" goto :failed

echo.
echo Done: dist\%PROJECT_NAME%.zip
exit /b 0

:failed
echo.
echo BUILD FAILED
exit /b 1
