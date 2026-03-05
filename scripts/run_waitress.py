import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from waitress import serve
from app import app
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting SmartSearch Backend with Waitress...")
    print(f"✅ Server is running on http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    serve(app, host="0.0.0.0", port=port)
