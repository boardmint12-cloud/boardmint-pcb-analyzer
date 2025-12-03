"""
Vercel Serverless Function Entry Point for FastAPI Backend
"""
import sys
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Import the FastAPI app
from main import app

# Vercel expects a handler or the app itself
# For Vercel, we just export the app
handler = app
