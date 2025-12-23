# Render Port Binding Fix

## Issue
Render service shows: "No open ports detected" even though the build succeeds.

## Root Cause
Render provides a dynamic `$PORT` environment variable, but the service needs to bind to it explicitly.

## Solution

### Option 1: Use start.sh (Recommended)
In Render Dashboard → Your Service → Settings:
- **Start Command**: `./start.sh`

This script reads `$PORT` and passes it to uvicorn.

### Option 2: Manual Start Command
In Render Dashboard → Your Service → Settings:
- **Start Command**: `poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Make sure `$PORT` is expanded (Render should do this automatically).

### Option 3: Use Python Script
Create a `run.py`:
```python
import os
import uvicorn
from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

Then set start command: `poetry run python run.py`

## Verification
After deployment, check logs for:
```
🚀 Starting Audria API server...
📍 Binding to port: [PORT_NUMBER]
INFO:     Uvicorn running on http://0.0.0.0:[PORT] (Press CTRL+C to quit)
```

## Current Status
- ✅ `start.sh` created and executable
- ✅ `app/main.py` updated to read PORT
- ✅ Dockerfile updated
- ⚠️  Need to configure Render to use `start.sh` or set start command

