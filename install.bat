@echo off
REM One-step install: copy Naksha into your QGIS profile and switch it on.
setlocal enabledelayedexpansion
echo.
echo   Naksha - installing into QGIS
echo   -----------------------------

REM QGIS rewrites QGIS3.ini when it exits, so enabling the plugin while it is
REM running gets silently reverted. Refuse rather than half-install.
tasklist /fi "imagename eq qgis-ltr-bin.exe" 2>nul | find /i "qgis-ltr-bin.exe" >nul
if not errorlevel 1 goto running
tasklist /fi "imagename eq qgis-bin.exe" 2>nul | find /i "qgis-bin.exe" >nul
if not errorlevel 1 goto running

set "PROFILES=%APPDATA%\QGIS\QGIS3\profiles"
if not exist "%PROFILES%" (
    echo   Could not find QGIS at "%PROFILES%".
    echo   Is QGIS installed for this user?
    goto done
)

set "PROFILE=default"
if not exist "%PROFILES%\%PROFILE%" (
    for /d %%P in ("%PROFILES%\*") do (
        if not defined FOUND set "PROFILE=%%~nxP" & set FOUND=1
    )
)
set "TARGET=%PROFILES%\%PROFILE%\python\plugins\naksha"
echo   Profile: %PROFILE%

if not exist "%TARGET%" mkdir "%TARGET%" >nul 2>&1
xcopy /e /i /y /q "%~dp0naksha" "%TARGET%" >nul
if errorlevel 1 (
    echo   Copy failed. Is QGIS closed, and do you have write access?
    goto done
)
echo   Copied plugin files.

set "INI=%PROFILES%\%PROFILE%\QGIS\QGIS3.ini"
findstr /c:"naksha=true" "%INI%" >nul 2>&1
if errorlevel 1 (
    findstr /c:"[PythonPlugins]" "%INI%" >nul 2>&1
    if errorlevel 1 (
        echo.>> "%INI%"
        echo [PythonPlugins]>> "%INI%"
    )
    powershell -NoProfile -Command "$p='%INI%'; $c=Get-Content -LiteralPath $p; $c=$c -replace '^\[PythonPlugins\]$',\"[PythonPlugins]`nnaksha=true\"; Set-Content -LiteralPath $p -Value $c -Encoding utf8"
    echo   Enabled Naksha.
) else (
    echo   Already enabled.
)

echo.
echo   Done. Start QGIS and look for the teal N in the toolbar.
goto done

:running
echo   QGIS is running. Please close it and run this again -
echo   QGIS overwrites its settings on exit, which would undo the install.

:done
echo.
pause
