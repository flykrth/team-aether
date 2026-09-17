#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "MDIN: Medical-Dental Interoperability Node — Setup Script"
echo "CareStack D-Solve Hackathon 2026"
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Setup Python Virtual Environment & Backend
echo ""
echo "[1/3] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Created virtual environment in .venv/"
else
    echo "Existing virtual environment found in .venv/"
fi

source .venv/bin/activate
echo "Installing backend requirements..."
pip install --upgrade pip
pip install -r backend/requirements.txt

# Create .env if not present
if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    echo "Copied backend/.env.example to backend/.env"
fi

# 2. Setup Frontend Dependencies
echo ""
echo "[2/3] Installing frontend dependencies..."
cd frontend
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Copied frontend/.env.example to frontend/.env"
fi
npm install
cd ..

# 3. Run Backend Verification Tests
echo ""
echo "[3/3] Running backend verification tests..."
source .venv/bin/activate
pytest backend/tests -v

echo ""
echo "=========================================================="
echo "Setup completed successfully!"
echo ""
echo "To run the backend server:"
echo "    source .venv/bin/activate"
echo "    python backend/run.py"
echo "    (API: http://localhost:8000 | Docs: http://localhost:8000/docs)"
echo ""
echo "To run the frontend dev server:"
echo "    cd frontend"
echo "    npm run dev"
echo "    (App: http://localhost:5173)"
echo "=========================================================="
