@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AirType - Build Windows EXE
:: Usage:  build_windows.bat
:: Output: windows\dist\AirType-X.Y.Z.exe  (version from build.gradle.kts)
:: ============================================================

set "ROOT=%~dp0"

:: --- Read version from build.gradle.kts ---
:: Split `versionName = "X.Y.Z"` on `=`, take the right side, strip spaces and quotes.
set "VERSION="
set "GRADLE_FILE=%ROOT%android\app\build.gradle.kts"
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /r /c:"versionName *=" "%GRADLE_FILE%"`) do set "VRAW=%%b"
set "VRAW=!VRAW: =!"
set "VERSION=!VRAW:"=!"
if "!VERSION!"=="" (
    echo [FAIL] Could not read versionName from %GRADLE_FILE%
    endlocal
    exit /b 1
)

set "AIRTYPE_VARIANT_NAME=AirType-%VERSION%"

echo.
echo ============================================================
echo  Building Windows EXE  [v%VERSION%]
echo ============================================================
echo.

pushd "%ROOT%windows"
python -m PyInstaller build.spec --noconfirm
set "PYI_ERR=%errorlevel%"
popd

if %PYI_ERR% neq 0 (
    echo.
    echo [FAIL] Windows build failed.
    if not defined SKIP_PAUSE pause
    endlocal
    exit /b 1
)

echo.
echo [OK] EXE: windows\dist\AirType-%VERSION%.exe

if not defined SKIP_PAUSE pause
endlocal
exit /b 0
