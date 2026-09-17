#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up MDIN Frontend..."
if [ ! -f ".env" ]; then
    cp .env.example .env
fi

npm install

echo "Frontend setup complete!"
echo "Run 'npm run dev' to start the development server on http://localhost:5173"
