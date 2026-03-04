@echo off
setlocal

:: ============================================================
:: AirType - Build Android APK + Windows EXE
:: Usage:  build.bat                    (both, Android debug)
::         build.bat android            (Android debug only)
::         build.bat android release    (Android release only)
::         build.bat windows            (Windows only)
:: ============================================================

set "ROOT=%~dp0"
set "FAILED="
set "BUILD_ANDROID=1"
set "BUILD_WINDOWS=1"
set "ANDROID_VARIANT=debug"

if /i "%~1"=="android" (
    set "BUILD_WINDOWS="
    if /i "%~2"=="release" set "ANDROID_VARIANT=release"
)
if /i "%~1"=="windows" set "BUILD_ANDROID="

if defined BUILD_ANDROID (
    call "%ROOT%build_android.bat" %ANDROID_VARIANT%
    if errorlevel 1 set "FAILED=1"
)

if defined BUILD_WINDOWS (
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
if defined BUILD_ANDROID (
    if /i "%ANDROID_VARIANT%"=="release" (
        echo  APK: %ROOT%android\app\build\outputs\apk\release\app-release-unsigned.apk
    ) else (
        echo  APK: %ROOT%android\app\build\outputs\apk\debug\app-debug.apk
    )
)
if defined BUILD_WINDOWS echo  EXE: %ROOT%windows\dist\AirType.exe
echo ============================================================

endlocal
exit /b 0
