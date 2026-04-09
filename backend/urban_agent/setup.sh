#!/bin/bash

echo "================================================================================"
echo "Intelligent Building Analysis Agent - Setup Script"
echo "================================================================================"
echo ""

# Check Python version
echo "🐍 Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi
echo "✅ Python 3 is available"
echo ""

# Create virtual environment (optional but recommended)
echo "📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi
echo ""

echo "🔧 To activate virtual environment:"
echo "   source venv/bin/activate"
echo ""

# Install dependencies
echo "📥 Installing dependencies..."
echo "   This may take a few minutes..."
echo ""

# Check if uv is available (faster)
if command -v uv &> /dev/null; then
    echo "⚡ Using uv for fast installation..."
    uv pip install -r requirements.txt
else
    echo "📦 Using pip for installation..."
    pip3 install -r requirements.txt
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Dependencies installed successfully"
else
    echo ""
    echo "⚠️  Some dependencies may have failed to install"
    echo "   Please check the error messages above"
fi
echo ""

# Setup config file
echo "⚙️  Setting up configuration..."
if [ ! -f "config.py" ]; then
    if [ -f "config_template.py" ]; then
        cp config_template.py config.py
        echo "✅ Created config.py from template"
        echo ""
        echo "⚠️  IMPORTANT: Edit config.py and add your OpenAI API key!"
        echo "   nano config.py"
        echo "   or"
        echo "   vim config.py"
    else
        echo "❌ config_template.py not found"
    fi
else
    echo "ℹ️  config.py already exists"
fi
echo ""

echo "================================================================================"
echo "✅ Setup Complete!"
echo "================================================================================"
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Activate virtual environment (if created):"
echo "   source venv/bin/activate"
echo ""
echo "2. Edit config.py and add your OpenAI API key:"
echo "   nano config.py"
echo ""
echo "3. Prepare your STL files in a directory, e.g.:"
echo "   mkdir -p stl_files"
echo "   cp /path/to/your/*.stl stl_files/"
echo ""
echo "4. Run the analysis:"
echo "   python full_analysis_with_recording_en.py"
echo ""
echo "5. View results:"
echo "   ls -lht analysis_summary_*.txt"
echo "   python view_llm_interactions_en.py"
echo ""
echo "📚 Documentation:"
echo "   - README_EN.md - Main documentation"
echo "   - QUICK_START_EN.md - Quick start guide"
echo "   - RUN_ALL_TESTS_EN.md - Test execution guide"
echo ""
echo "================================================================================"

