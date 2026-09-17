#!/usr/bin/env python3
"""
Standalone runner script for MDIN backend server.
Can be executed from project root via:
    python backend/run.py
Or from backend/ directory via:
    python run.py
"""

import sys
import os
from pathlib import Path
import uvicorn

# Ensure both the project root and backend directory are on sys.path
CURRENT_FILE = Path(__file__).resolve()
BACKEND_DIR = CURRENT_FILE.parent
PROJECT_ROOT = BACKEND_DIR.parent

for path in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from backend.app.config import settings
except ImportError:
    from app.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")
    print(f"Listening on http://{settings.HOST}:{settings.PORT}")
    print(f"CORS enabled for origins: {', '.join(settings.CORS_ORIGINS)}")
    print(f"Interactive API documentation: http://{settings.HOST}:{settings.PORT}/docs")

    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        app_dir=str(PROJECT_ROOT),
    )
