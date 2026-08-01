@echo off
chcp 65001 >nul 2>&1
echo Installing required Python packages...
pip install flask edge-tts faster-whisper imageio-ffmpeg PyAV soundfile pillow numpy torch
echo.
echo Complete! Run START.bat to start.
pause
