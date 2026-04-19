@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AirType - Build all + copy to website
:: Usage:  publish.bat
:: Reads version from android/app/build.gradle.kts (versionName)
:: ============================================================

set "ROOT=%~dp0"
set "FAILED="

:: --- Read version from build.gradle.kts ---
:: Split `versionName = "X.Y.Z"` on `=`, take the right side, strip spaces and quotes.
set "VERSION="
set "GRADLE_FILE=%ROOT%android\app\build.gradle.kts"
for /f "usebackq tokens=1,* delims==" %%a in (`findstr /r /c:"versionName *=" "%GRADLE_FILE%"`) do set "VRAW=%%b"
set "VRAW=!VRAW: =!"
set "VERSION=!VRAW:"=!"
if "!VERSION!"=="" (
    echo [FAIL] Could not read versionName from build.gradle.kts
    exit /b 1
)
echo Using version: %VERSION%

:: --- Read .env ---
set "DEPLOY_DIR="
if exist "%ROOT%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT%.env") do (
        set "%%a=%%b"
    )
)
if "%DEPLOY_DIR%"=="" (
    echo [FAIL] DEPLOY_DIR not set in .env
    exit /b 1
)

set "APK=%ROOT%android\app\build\outputs\apk\release\AirType-%VERSION%.apk"
set "AAB=%ROOT%android\app\build\outputs\bundle\release\AirType-release.aab"
set "EXE=%ROOT%windows\dist\AirType-%VERSION%.exe"

set "SKIP_PAUSE=1"

:: --- Build Android release APK ---
echo.
echo ============================================================
echo  [1/4] Building Android release APK
echo ============================================================
call "%ROOT%build_android.bat" release
if errorlevel 1 (set "FAILED=1" & goto :summary)

:: --- Build Android release AAB ---
echo.
echo ============================================================
echo  [2/4] Building Android release AAB
echo ============================================================
call "%ROOT%build_android.bat" bundle
if errorlevel 1 (set "FAILED=1" & goto :summary)

:: --- Build Windows EXE ---
echo.
echo ============================================================
echo  [3/4] Building Windows EXE
echo ============================================================
call "%ROOT%build_windows.bat"
if errorlevel 1 (set "FAILED=1" & goto :summary)

:: --- Copy to website ---
echo.
echo ============================================================
echo  [4/4] Copying artifacts to %DEPLOY_DIR%
echo ============================================================

if not exist "%DEPLOY_DIR%" mkdir "%DEPLOY_DIR%"

if exist "%APK%" (
    copy /y "%APK%" "%DEPLOY_DIR%\AirType-%VERSION%.apk" >nul
    echo [OK] Copied AirType-%VERSION%.apk
) else (
    echo [FAIL] APK not found: %APK%
    set "FAILED=1"
)

if exist "%EXE%" (
    copy /y "%EXE%" "%DEPLOY_DIR%\AirType-%VERSION%.exe" >nul
    echo [OK] Copied AirType-%VERSION%.exe
) else (
    echo [FAIL] EXE not found: %EXE%
    set "FAILED=1"
)

:summary
echo.
echo ============================================================
if defined FAILED (
    echo  PUBLISH FAILED - check output above
    pause
    endlocal
    exit /b 1
) else (
    echo  PUBLISH SUCCESSFUL  [v%VERSION%]
    echo  APK: %APK%
    echo  AAB: %AAB%
    echo  EXE: %EXE%
    echo  Deployed to: %DEPLOY_DIR%
)
echo ============================================================

pause
endlocal
exit /b 0
