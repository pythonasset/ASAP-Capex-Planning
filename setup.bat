@echo off
REM ASAP CAPEX Planning System - Windows Setup Script

echo 🏗️  Setting up ASAP CAPEX Planning System...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Display Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo ✅ Python version: %%i

REM Create virtual environment
echo 📦 Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️  Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Create sample config if it doesn't exist
if not exist config.ini (
    echo ⚙️  Creating sample configuration file...
    (
    echo [SOFTWARE]
    echo registered_to = Your Organization Name
    echo produced_by = Odysseus-imc Pty Ltd
    echo software_name = ASAP CAPEX Planning System
    echo version = 1.0 ^(Beta^)
    echo.
    echo [DISPLAY]
    echo show_registration = true
    echo show_producer = true
    echo show_version = true
    ) > config.ini
)

echo.
echo ✅ Setup complete!
echo.
echo To run the application:
echo   1. Activate the virtual environment:
echo      venv\Scripts\activate
echo   2. Start the application:
echo      streamlit run capex_app.py
echo.
echo 📊 The application will be available at: http://localhost:8501
echo.
echo 🔧 Don't forget to edit config.ini with your organization details!
echo.
pause