@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AirType - Build
:: Pass argument to skip menu: android, windows
:: ============================================================

set "ROOT=%~dp0"
set "FAILED="
set "TARGET=%~1"

:: --- Interactive menu if no argument ---
if "%TARGET%"=="" (
    echo.
    echo  AirType - Build
    echo  ========================
    echo  1. Android + Windows
    echo  2. Android only
    echo  3. Windows only
    echo.
    set /p "CHOICE=Select [1-3]: "
    if "!CHOICE!"=="1" set "TARGET=all"
    if "!CHOICE!"=="2" set "TARGET=android"
    if "!CHOICE!"=="3" set "TARGET=windows"
    if "!TARGET!"=="" (
        echo Invalid selection.
        exit /b 1
    )
) else (
    if /i "%TARGET%"=="android" set "TARGET=android"
    if /i "%TARGET%"=="windows" set "TARGET=windows"
)

set "SKIP_PAUSE=1"

if /i not "%TARGET%"=="windows" (
    call "%ROOT%build_android.bat"
    if errorlevel 1 set "FAILED=1"
)

if /i not "%TARGET%"=="android" (
    call "%ROOT%build_windows.bat"
    if errorlevel 1 set "FAILED=1"
)

echo.
echo ============================================================
if defined FAILED (
    echo  BUILD COMPLETED WITH ERRORS - check output above
) else (
    echo  BUILD SUCCESSFUL
)
if /i not "%TARGET%"=="windows" (
    echo  See build_android output above for artifact path
)
if /i not "%TARGET%"=="android" (
    echo  EXE: %ROOT%windows\dist\AirType.exe
)
echo ============================================================

pause
endlocal
exit /b 0
