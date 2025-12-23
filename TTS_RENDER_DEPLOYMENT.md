# Coqui TTS Deployment on Render

## Problem

The error "Coqui TTS not available and no fallback available" occurs because:
1. TTS is not installed in the production environment
2. TTS requires system dependencies (LLVM, cmake) that aren't in the Dockerfile
3. TTS is marked as optional in `pyproject.toml`

## Solutions

### Option 1: Install TTS in Dockerfile (Recommended for Production)

Update `Dockerfile` to install TTS and its dependencies:

```dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    COQUI_TOS_AGREED=1

# Install system dependencies for TTS
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        cmake \
        git \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.7.1

# Configure Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=0 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies including TTS
RUN poetry install --only=main --no-root && rm -rf $POETRY_CACHE_DIR

# Install TTS separately (if not in pyproject.toml)
RUN pip install TTS==0.21.3 numpy>=1.21.0

# ... rest of Dockerfile
```

**Note:** This will significantly increase build time and image size (~2GB+).

### Option 2: Use External TTS Service (Recommended for Production)

Instead of installing TTS on Render, use an external service:

#### A. ElevenLabs API (Best Quality)

1. Sign up at https://elevenlabs.io
2. Get API key
3. Update `voice_service.py` to use ElevenLabs API

#### B. OpenAI TTS (Simple)

1. Add OpenAI API key to Render environment variables
2. Use OpenAI's TTS API instead of Coqui

#### C. Google Cloud TTS

1. Set up Google Cloud credentials
2. Use Google Cloud TTS API

### Option 3: Separate TTS Service (Microservices)

Deploy TTS as a separate service:

1. Create a separate Render service just for TTS
2. Use a smaller instance (TTS doesn't need to run 24/7)
3. Call TTS service via HTTP from main API

### Option 4: Disable Voice Features (Temporary)

If TTS is not critical, you can:

1. Hide voice cloning UI when TTS is unavailable
2. Show a message: "Voice features coming soon"
3. Keep the rest of the app functional

## Current Status

**What Works:**
- ✅ Voice file uploads (files are saved)
- ✅ Voice metadata storage
- ✅ Voice listing

**What Doesn't Work:**
- ❌ Voice cloning (requires TTS)
- ❌ Speech generation (requires TTS)

## Quick Fix: Update requirements.txt

Add TTS to `requirements.txt`:

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
python-dotenv==1.0.0
pydantic[email]==2.5.0
pydantic-settings==2.1.0
supabase==2.3.0
numpy>=1.21.0
TTS==0.21.3
```

**But:** This won't work without system dependencies in Dockerfile.

## Recommended Approach

For production on Render, I recommend **Option 2A (ElevenLabs)** or **Option 3 (Separate Service)**:

1. **ElevenLabs** - Best quality, easy integration, pay-per-use
2. **Separate Service** - More control, can scale independently

## Testing Locally

To test TTS locally:

```bash
cd Audria_server
poetry add TTS==0.21.3
poetry install
export COQUI_TOS_AGREED=1
poetry run python -c "from TTS.api import TTS; print('✅ TTS available')"
```

If this works locally but not on Render, it's a deployment configuration issue.

