@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AirType - Install APK to a connected Android device via adb
:: Release APK filename is versioned (AirType-X.Y.Z.apk),
:: so we read versionName from build.gradle.kts.
:: ============================================================

set "ROOT=%~dp0"

set /p "MODE=Install which APK? [d]ebug / [r]elease: "

if /i "%MODE%"=="d"       goto debug
if /i "%MODE%"=="debug"   goto debug
if /i "%MODE%"=="r"       goto release
if /i "%MODE%"=="release" goto release

echo Invalid choice: %MODE%
pause
exit /b 1

:debug
set "APK=%ROOT%android\app\build\outputs\apk\debug\AirType-debug.apk"
goto install

:release
set "GRADLE_FILE=%ROOT%android\app\build.gradle.kts"
if not exist "%GRADLE_FILE%" (
    echo [FAIL] build.gradle.kts not found: %GRADLE_FILE%
    pause
    exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /r /c:"versionName *=" "%GRADLE_FILE%"`) do set "VRAW=%%b"
set "VRAW=!VRAW: =!"
set "VERSION=!VRAW:"=!"
if "!VERSION!"=="" (
    echo [FAIL] Could not read versionName from %GRADLE_FILE%
    pause
    exit /b 1
)
set "APK=%ROOT%android\app\build\outputs\apk\release\AirType-!VERSION!.apk"
goto install

:install
if not exist "%APK%" (
    echo ERROR: APK not found: %APK%
    echo Build it first: build_android.bat
    pause
    exit /b 1
)
echo Installing %APK%...
adb install --user 0 -r "%APK%"
pause
endlocal
