@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AirType - Create GitHub release
:: Usage:  release.bat
:: Reads version from android/app/build.gradle.kts (versionName)
:: Prerequisites: run publish.bat first to build artifacts
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
    echo [FAIL] Could not read versionName from build.gradle.kts
    exit /b 1
)

set "TAG=v%VERSION%"
set "APK=%ROOT%android\app\build\outputs\apk\release\AirType-%VERSION%.apk"
set "AAB=%ROOT%android\app\build\outputs\bundle\release\AirType-release.aab"
set "EXE=%ROOT%windows\dist\AirType-%VERSION%.exe"

echo Using version: %VERSION% (tag: %TAG%)

:: --- Check working tree is clean ---
:: A dirty tree means we'd tag an old commit and push untracked work silently.
for /f "delims=" %%s in ('git -C "%ROOT%" status --porcelain') do (
    set "DIRTY=1"
    goto :dirtyfound
)
:dirtyfound
if defined DIRTY (
    echo.
    echo [WARN] Uncommitted changes detected in the working tree:
    git -C "%ROOT%" status --short
    echo.
    echo The tag will point at the last commit, not these changes.
    set /p "CONT=Continue anyway? [y/N] "
    if /i not "!CONT!"=="y" exit /b 1
)

:: --- Check artifacts exist ---
set "MISSING="
if not exist "%APK%" (echo [WARN] APK not found: %APK% & set "MISSING=1")
if not exist "%AAB%" (echo [WARN] AAB not found: %AAB% & set "MISSING=1")
if not exist "%EXE%" (echo [WARN] EXE not found: %EXE% & set "MISSING=1")

if defined MISSING (
    echo.
    echo Some artifacts are missing. Run publish.bat first.
    set /p "CONT=Continue anyway? [y/N] "
    if /i not "!CONT!"=="y" exit /b 1
)

:: --- Tag ---
echo.
echo ============================================================
echo  Tagging %TAG%
echo ============================================================
git -C "%ROOT%" tag -a "%TAG%" -m "Release %TAG%"
if errorlevel 1 (
    echo [WARN] Tag may already exist, continuing...
)

:: --- Push ---
echo.
echo ============================================================
echo  Pushing to GitHub
echo ============================================================
git -C "%ROOT%" push origin main
git -C "%ROOT%" push origin "%TAG%"

:: --- Create release ---
echo.
echo ============================================================
echo  Creating GitHub release %TAG%
echo ============================================================

set "ASSETS="
if exist "%APK%" set "ASSETS=!ASSETS! "%APK%#AirType-%VERSION%.apk""
if exist "%AAB%" set "ASSETS=!ASSETS! "%AAB%#AirType-release.aab""
if exist "%EXE%" set "ASSETS=!ASSETS! "%EXE%#AirType-%VERSION%.exe""

gh release create "%TAG%" %ASSETS% --title "AirType %TAG%" --notes-file "%ROOT%release_notes.txt"

if errorlevel 1 (
    echo.
    echo [FAIL] GitHub release failed.
    pause
    endlocal
    exit /b 1
)

echo.
echo ============================================================
echo  RELEASE COMPLETE
echo  https://github.com/jordanbarnes94/airtype/releases/tag/%TAG%
echo ============================================================

pause
endlocal
exit /b 0
