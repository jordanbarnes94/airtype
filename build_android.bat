@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AirType - Build Android APK / AAB
:: Pass argument to skip menu: debug, release, bundle
:: ============================================================

set "ROOT=%~dp0"
set "VARIANT=%~1"

:: --- Interactive menu if no argument ---
if not "%VARIANT%"=="" goto :start

echo.
echo  AirType - Android Build
echo  ========================
echo  1. Debug APK
echo  2. Release APK
echo  3. Release AAB ^(Google Play^)
echo.
set /p "CHOICE=Select [1-3]: "
if "%CHOICE%"=="1" set "VARIANT=debug"
if "%CHOICE%"=="2" set "VARIANT=release"
if "%CHOICE%"=="3" set "VARIANT=bundle"
if "%VARIANT%"=="" (
    echo Invalid selection.
    if not defined SKIP_PAUSE pause
    exit /b 1
)

:start
set "BUNDLE=0"
if /i "%VARIANT%"=="bundle" (set "VARIANT=release" & set "BUNDLE=1")

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

:: --- Read versionName from build.gradle.kts ---
set "VERSION="
set "GRADLE_FILE=%ROOT%android\app\build.gradle.kts"
if not exist "%GRADLE_FILE%" (
    echo [FAIL] build.gradle.kts not found: %GRADLE_FILE%
        exit /b 1
)
:: Split `versionName = "X.Y.Z"` on `=`, take the right side, strip spaces and quotes.
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /r /c:"versionName *=" "%GRADLE_FILE%"`) do set "VRAW=%%b"
set "VRAW=!VRAW: =!"
set "VERSION=!VRAW:"=!"
if "!VERSION!"=="" (
    echo [FAIL] Could not read versionName from %GRADLE_FILE%
        exit /b 1
)

echo.
echo ============================================================
if "%BUNDLE%"=="1" (
    echo  Building Android AAB [bundle/release]
) else (
    echo  Building Android APK [%VARIANT%]
)
echo  Version:      %VERSION%
echo  JAVA_HOME:    %JAVA_HOME%
echo  ANDROID_HOME: %ANDROID_HOME%
echo ============================================================
echo.

set "GRADLE_CMD=assembleDebug"
if /i "%VARIANT%"=="release" set "GRADLE_CMD=assembleRelease"
if "%BUNDLE%"=="1" set "GRADLE_CMD=bundleRelease"

pushd "%ROOT%android"
call .\gradlew.bat %GRADLE_CMD%
set "GRADLE_ERR=%errorlevel%"
popd

if %GRADLE_ERR% neq 0 (
    echo.
    echo [FAIL] Android build failed.
    if not defined SKIP_PAUSE pause
    endlocal
    exit /b 1
)

echo.
if "%BUNDLE%"=="1" (
    echo [OK] AAB: android\app\build\outputs\bundle\release\AirType-release.aab
) else if /i "%VARIANT%"=="release" (
    echo [OK] APK: android\app\build\outputs\apk\release\AirType-%VERSION%.apk
) else (
    echo [OK] APK: android\app\build\outputs\apk\debug\AirType-debug.apk
)

if not defined SKIP_PAUSE pause
endlocal
exit /b 0

:trim
setlocal enabledelayedexpansion
call set "val=%%%1%%"
for /f "tokens=*" %%x in ("%val%") do set "val=%%x"
endlocal & set "%1=%val%"
goto :eof
