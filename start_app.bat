@echo off
echo ===========================================
echo 🐔 Starting CHICKEN TWIN System...
echo ===========================================

:: Check for virtual environment (optional but good practice)
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

echo.
echo 1. Starting Backend Server (Port 5000)...
start "Chicken Twin Server" cmd /k "python server.py"

echo.
echo 2. Starting AI Monitor Agent (Port 8765)...
start "Chicken Twin AI Agent" cmd /k "python monitor.py"

echo.
echo 3. Opening Application...
timeout /t 3 >nul
explorer "http://localhost:5000/demo.html"

echo.
echo ===========================================
echo ✅ System Started!
echo    - Server: http://localhost:5000
echo    - WebSocket: ws://localhost:8765
echo ===========================================
pause
