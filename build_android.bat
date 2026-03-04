@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AirType - Build Android APK / AAB
:: Usage:  build_android.bat             (debug APK, default)
::         build_android.bat debug       (debug APK)
::         build_android.bat release     (release APK - requires signing config)
::         build_android.bat bundle      (release AAB for Google Play)
:: ============================================================

set "ROOT=%~dp0"
set "VARIANT=debug"
set "BUNDLE=0"
if /i "%~1"=="release" set "VARIANT=release"
if /i "%~1"=="debug"   set "VARIANT=debug"
if /i "%~1"=="bundle"  (set "VARIANT=release" & set "BUNDLE=1")

:: --- Resolve JAVA_HOME ---
if not defined JAVA_HOME (
    for /f "tokens=*" %%j in ('java -XshowSettings:property -version 2^>^&1 ^| findstr "java.home"') do (
        for /f "tokens=2 delims==" %%p in ("%%j") do set "JAVA_HOME=%%p"
    )
    call :trim JAVA_HOME
)

:: --- Resolve ANDROID_HOME from local.properties if not set ---
if not defined ANDROID_HOME (
    for /f "tokens=2 delims==" %%a in ('findstr "sdk.dir" "%ROOT%android\local.properties" 2^>nul') do (
        set "ANDROID_HOME=%%a"
    )
    if defined ANDROID_HOME set "ANDROID_HOME=!ANDROID_HOME:\\=\!"
)

echo.
echo ============================================================
if "%BUNDLE%"=="1" (
    echo  Building Android AAB [bundle/release]
) else (
    echo  Building Android APK [%VARIANT%]
)
echo  JAVA_HOME:    %JAVA_HOME%
echo  ANDROID_HOME: %ANDROID_HOME%
echo ============================================================
echo.

pushd "%ROOT%android"
if "%BUNDLE%"=="1" (
    call .\gradlew.bat bundleRelease
) else if /i "%VARIANT%"=="release" (
    call .\gradlew.bat assembleRelease
) else (
    call .\gradlew.bat assembleDebug
)
set "GRADLE_ERR=%errorlevel%"
popd

if %GRADLE_ERR% neq 0 (
    echo.
    echo [FAIL] Android build failed.
    endlocal
    exit /b 1
)

echo.
if "%BUNDLE%"=="1" (
    echo [OK] AAB: android\app\build\outputs\bundle\release\AirType-release.aab
) else if /i "%VARIANT%"=="release" (
    echo [OK] APK: android\app\build\outputs\apk\release\AirType-release.apk
) else (
    echo [OK] APK: android\app\build\outputs\apk\debug\AirType-debug.apk
)

endlocal
exit /b 0

:trim
setlocal enabledelayedexpansion
call set "val=%%%1%%"
for /f "tokens=*" %%x in ("%val%") do set "val=%%x"
endlocal & set "%1=%val%"
goto :eof
