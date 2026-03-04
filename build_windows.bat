@echo off
setlocal

:: ============================================================
:: AirType - Build Windows EXE
:: Usage:  build_windows.bat
:: Output: windows\dist\AirType.exe
:: ============================================================

set "ROOT=%~dp0"

echo.
echo ============================================================
echo  Building Windows EXE
echo ============================================================
echo.

pushd "%ROOT%windows"
python -m PyInstaller build.spec --noconfirm
set "PYI_ERR=%errorlevel%"
popd

if %PYI_ERR% neq 0 (
    echo.
    echo [FAIL] Windows build failed.
    endlocal
    exit /b 1
)

echo.
echo [OK] EXE: windows\dist\AirType.exe

endlocal
exit /b 0
