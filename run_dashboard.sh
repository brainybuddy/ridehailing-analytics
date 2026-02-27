#!/bin/bash

# Lagos Ride-Hailing Analytics Dashboard Launcher

echo "=========================================="
echo "Lagos Ride-Hailing Analytics Dashboard"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
    echo ""
    echo "Installing dependencies..."
    ./venv/bin/pip install -r requirements.txt
    echo ""
fi

echo "✓ Using virtual environment"
echo ""

# Launch dashboard
echo "Starting dashboard..."
echo "The dashboard will open in your browser at http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo "=========================================="
echo ""

./venv/bin/streamlit run dashboard.py
