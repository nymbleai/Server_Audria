"""
Render-compatible startup script for Audria API
Reads PORT from environment and starts uvicorn server
"""
import os
import uvicorn
from app.main import app

if __name__ == "__main__":
    # Render provides PORT environment variable
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Starting Audria API server...")
    print(f"📍 Binding to {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

