@echo off
setlocal EnableDelayedExpansion
title TagToolSH!
cd /d "%~dp0"

set "BASEDIR=%~dp0"
set "APP_DATA=%BASEDIR%app_data"
set "PYDIR=%APP_DATA%\python"
set "LIBSDIR=%APP_DATA%\libs"
set "EMBEDW=%PYDIR%\pythonw.exe"
set "EMBED=%PYDIR%\python.exe"

set "PYVER=3.12.7"
set "PYSHORT=312"
set "ZIPNAME=python-%PYVER%-embed-amd64.zip"
set "URL=https://www.python.org/ftp/python/%PYVER%/%ZIPNAME%"
set "TMPZIP=%TEMP%\%ZIPNAME%"
set "GETPIP=%TEMP%\get-pip.py"

REM ------------------------------------------------------------------
REM  FAST PATH: everything already installed? Just launch.
REM ------------------------------------------------------------------
if exist "%EMBEDW%" (
    if exist "%LIBSDIR%\PySide6\__init__.py" (
        start "" "%EMBEDW%" "%BASEDIR%main.py" %*
        exit /b 0
    )
)

REM ------------------------------------------------------------------
REM  SLOW PATH: first run or missing deps.
REM ------------------------------------------------------------------
echo ============================================================
echo  TagToolSH! - First-Run Setup
echo ============================================================
echo.
echo  Setting up the portable Python runtime and dependencies.
echo  This happens once. Subsequent launches will be instant.
echo.

if not exist "%PYDIR%\python.exe" (
    echo [1/4] Downloading Python %PYVER% embeddable...
    if not exist "%APP_DATA%" mkdir "%APP_DATA%"
    if not exist "%PYDIR%" mkdir "%PYDIR%"

    powershell -NoProfile -Command ^
        "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%TMPZIP%' -UseBasicParsing } catch { exit 1 }"
    if not exist "%TMPZIP%" (
        echo.
        echo  ERROR: Could not download portable Python.
        echo         Check your internet connection and try again.
        echo.
        goto :fallback_or_die
    )

    echo [2/4] Extracting to %PYDIR% ...
    powershell -NoProfile -Command ^
        "Expand-Archive -Path '%TMPZIP%' -DestinationPath '%PYDIR%' -Force"
    if not exist "%PYDIR%\python.exe" (
        echo.
        echo  ERROR: Extraction failed.
        echo.
        goto :fallback_or_die
    )

    echo [3/4] Enabling site-packages in embedded runtime...
    set "PTHFILE=%PYDIR%\python%PYSHORT%._pth"
    if exist "!PTHFILE!" (
        (
            echo python%PYSHORT%.zip
            echo .
            echo import site
            echo ..\libs
        ) > "!PTHFILE!"
    )

    echo [4/4] Bootstrapping pip...
    powershell -NoProfile -Command ^
        "try { Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GETPIP%' -UseBasicParsing } catch { exit 1 }"
    if not exist "%GETPIP%" (
        echo.
        echo  ERROR: Could not download get-pip.py.
        echo.
        goto :fallback_or_die
    )
    "%PYDIR%\python.exe" "%GETPIP%" --no-warn-script-location

    del /q "%TMPZIP%" 2>nul
    del /q "%GETPIP%" 2>nul
) else (
    echo [1/4] Portable Python already present - skipping download.
    echo [2/4] Skipping extraction.
    echo [3/4] Skipping _pth rewrite.
    echo [4/4] Skipping pip bootstrap.
)

if not exist "%LIBSDIR%\PySide6\__init__.py" (
    echo.
    echo Installing project dependencies into app_data\libs ...
    echo (PySide6, pyscard, ndeflib, psutil - this may take a minute)
    echo.
    if not exist "%LIBSDIR%" mkdir "%LIBSDIR%"

    "%PYDIR%\python.exe" -m pip install --upgrade pip --no-warn-script-location
    "%PYDIR%\python.exe" -m pip install --target "%LIBSDIR%" --upgrade ^
        PySide6 pyscard ndeflib psutil --no-warn-script-location

    if errorlevel 1 (
        echo.
        echo  ERROR: Dependency installation failed.
        echo         See the error above. Common causes:
        echo           - No internet connection
        echo           - Corporate firewall blocking pip
        echo.
        goto :fallback_or_die
    )
) else (
    echo.
    echo Dependencies already installed - skipping.
)

echo.
echo ============================================================
echo  Setup complete. Launching TagToolSH!...
echo ============================================================
start "" "%EMBEDW%" "%BASEDIR%main.py" %*
exit /b 0

:fallback_or_die
echo.
echo Attempting to use a system-installed Python instead...
echo.

set "PYW="
set "PY="

where py >nul 2>nul
if %errorlevel%==0 (
    for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
    for /f "delims=" %%i in ('py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do set "PYW=%%i"
)
if not defined PY (
    where python >nul 2>nul
    if %errorlevel%==0 (
        for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
        for /f "delims=" %%i in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do set "PYW=%%i"
    )
)

if not defined PY (
    echo.
    echo ============================================================
    echo  SETUP FAILED and no system Python was found.
    echo ============================================================
    echo.
    echo To run this application you need one of:
    echo.
    echo   1. An internet connection on this machine for the
    echo      one-time portable Python download, OR
    echo   2. A system-installed Python 3.10 or newer.
    echo      Download: https://www.python.org/downloads/
    echo      Check "Add Python to PATH" during install.
    echo.
    echo Alternatively, run the setup on a machine with internet,
    echo then copy the entire TagToolSH folder (including app_data)
    echo to this machine. It will run offline from the copied files.
    echo.
    pause
    exit /b 1
)

echo Found system Python: %PY%
echo Note: portable setup will be reattempted next launch.
echo.

if defined PYW if exist "%PYW%" (
    start "" "%PYW%" "%BASEDIR%main.py" %*
    exit /b 0
)

"%PY%" "%BASEDIR%main.py" %*
if errorlevel 1 (
    echo.
    echo Application exited with an error. Press any key to close.
    pause >nul
)
