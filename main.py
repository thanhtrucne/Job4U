"""
Entry point – run with:
    python main.py
or:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
import uvicorn
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
