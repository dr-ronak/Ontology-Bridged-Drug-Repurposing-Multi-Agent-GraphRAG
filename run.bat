@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

if not exist "config.py" (
    echo [ERROR] config.py not found in %CD%. Make sure ALL project files are extracted together.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
echo Starting Pharma GraphRAG on http://localhost:8501 ...
python -m streamlit run app.py
endlocal
