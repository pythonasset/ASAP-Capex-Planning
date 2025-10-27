#!/bin/bash

# ASAP CAPEX Planning System - Setup Script
# This script sets up the development environment

echo "🏗️  Setting up ASAP CAPEX Planning System..."

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create sample config if it doesn't exist
if [ ! -f config.ini ]; then
    echo "⚙️  Creating sample configuration file..."
    cat > config.ini << EOF
[SOFTWARE]
registered_to = Your Organization Name
produced_by = Odysseus-imc Pty Ltd
software_name = ASAP CAPEX Planning System
version = 1.0 (Beta)

[DISPLAY]
show_registration = true
show_producer = true
show_version = true
EOF
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run the application:"
echo "  1. Activate the virtual environment:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "     venv\\Scripts\\activate"
else
    echo "     source venv/bin/activate"
fi
echo "  2. Start the application:"
echo "     streamlit run capex_app.py"
echo ""
echo "📊 The application will be available at: http://localhost:8501"
echo ""
echo "🔧 Don't forget to edit config.ini with your organization details!"