@echo off
chcp 65001 >nul 2>&1
echo.
echo ==========================================
echo   SHADOWING ENGLISH STUDIO
echo   Trình duyệt tự động mở tại: http://localhost:5000
echo   Nhấn Ctrl+C để tắt.
echo ==========================================
echo.
cd /d "%~dp0"
start http://localhost:5000
python app.py
pause
