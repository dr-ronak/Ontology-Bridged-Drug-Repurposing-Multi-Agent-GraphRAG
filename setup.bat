@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Pharma GraphRAG - one-time setup
echo ============================================

python --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.10+ was not found on PATH. Install it from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your internet connection and try again.
    pause
    exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env - add your ANTHROPIC_API_KEY there ^(optional^).
)

echo.
echo Setup complete. Start the app with run.bat
pause
endlocal
