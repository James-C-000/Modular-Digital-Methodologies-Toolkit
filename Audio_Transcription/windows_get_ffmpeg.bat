@echo off
REM ============================================================================
REM This script installs FFMPEG using winget and adds its bin folder to the PATH.
REM It assumes the winget package "Gyan.FFmpeg" is available.
REM If the installation folder is different, update the FFMPEG_BIN variable accordingly.
REM ============================================================================

echo Installing FFMPEG using winget...
REM The -e flag ensures an exact match for the package id.
winget install -e --id Gyan.FFmpeg

REM Give winget a moment to finish installation.
timeout /t 5 >nul

REM Set the expected installation path.
REM Change this path if your installed ffmpeg is located elsewhere.
set "FFMPEG_BIN=C:\Program Files\ffmpeg\bin"

REM Verify that ffmpeg.exe exists in the expected location.
if exist "%FFMPEG_BIN%\ffmpeg.exe" (
    echo FFMPEG was installed successfully at: %FFMPEG_BIN%
) else (
    echo ERROR: FFMPEG not found at %FFMPEG_BIN%. Please verify the installation.
    pause
    exit /b 1
)

REM Check if the FFMPEG_BIN is already in the user PATH.
echo %PATH% | find /I "%FFMPEG_BIN%" >nul
if %ERRORLEVEL%==0 (
    echo FFMPEG bin folder is already in the PATH.
) else (
    echo Adding FFMPEG bin folder to the user PATH...
    REM Append FFMPEG_BIN to the current PATH.
    setx PATH "%PATH%;%FFMPEG_BIN%"
    echo FFMPEG bin folder added to PATH.
)

echo.
echo Installation complete.
echo You may need to restart your command prompt or computer for changes to take effect.
pause
