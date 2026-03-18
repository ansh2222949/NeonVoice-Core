@echo off
setlocal
title NeonAI Controller
color 0A

echo =====================================
echo        NeonAI System Boot
echo =====================================
echo.

:: ---------------------------------------
:: 1️⃣ CHECK OLLAMA SERVICE
:: ---------------------------------------
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] Ollama Service: ACTIVE
) else (
    echo [WARN] Ollama Service: STOPPED. Starting now...
    start "Ollama Service" cmd /c ollama serve
    timeout /t 4 >nul
)

:: ---------------------------------------
:: 2️⃣ CHECK GPT-SoVITS API
:: ---------------------------------------
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "api_v2.py" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [INFO] GPT-SoVITS API: ACTIVE
) else (
    if defined GPT_SOVITS_DIR (
        if exist "%GPT_SOVITS_DIR%\api_v2.py" (
            echo [WARN] GPT-SoVITS API: STOPPED. Starting now...
            cd /d %GPT_SOVITS_DIR%
            start "GPT-SoVITS API" cmd /k python api_v2.py
            timeout /t 6 >nul
        ) else (
            echo [WARN] GPT_SOVITS_DIR is set but api_v2.py was not found. Skipping TTS API startup.
        )
    ) else (
        echo [INFO] GPT_SOVITS_DIR not set. Skipping TTS API startup.
    )
)

:: ---------------------------------------
:: 3️⃣ START NEON SERVER
:: ---------------------------------------
echo [INFO] Launching Neon Brain Engine...
cd /d %~dp0
start "NeonAI Server" cmd /k python server.py

:: ---------------------------------------
:: 4️⃣ OPEN DASHBOARD
:: ---------------------------------------
echo [INFO] Opening Dashboard...
timeout /t 4 >nul
start http://localhost:5000

echo.
echo [SUCCESS] NeonAI is Fully Operational.
echo =====================================
pause
