# Coqui TTS Setup Guide

## The Problem

Coqui TTS requires **Python 3.9-3.11**. Your current environment has Python 3.13, which is incompatible.

## Solutions

### Option 1: Use pyenv to install Python 3.11 (Recommended)

```bash
# Install pyenv (if not already installed)
brew install pyenv

# Install Python 3.11
pyenv install 3.11.8

# Set Python 3.11 for this project
cd Audria_server
pyenv local 3.11.8

# Recreate Poetry environment
poetry env remove --all
poetry install

# Verify Python version
poetry run python --version  # Should show 3.11.x

# Install TTS
poetry add TTS==0.21.3
```

### Option 2: Use Docker (Isolated Environment)

Create a `Dockerfile.tts` for TTS processing:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install TTS==0.21.3

# Copy your voice processing scripts
COPY app/services/voice_service.py .

CMD ["python", "-c", "from TTS.api import TTS; print('TTS ready')"]
```

Build and run:
```bash
docker build -f Dockerfile.tts -t audria-tts .
docker run audria-tts
```

### Option 3: Use an External TTS API (Alternative)

If you can't use Python 3.11, consider these alternatives:

1. **ElevenLabs** (paid, high quality voice cloning)
   - API: `https://api.elevenlabs.io/v1/`
   - Best for production

2. **OpenAI TTS** (paid)
   - Uses `openai` Python package
   - Simple but no voice cloning

3. **Google Cloud Text-to-Speech** (paid)
   - Professional grade
   - Limited voice cloning

4. **Mozilla TTS** (Coqui's predecessor)
   - Also requires Python < 3.12

## Current Status

Without TTS installed:
- ✅ Voice file uploads work (files are saved)
- ✅ Voice metadata is stored
- ❌ Voice cloning (requires TTS)
- ❌ Speech generation (requires TTS)

## Quick Fix for Development

For development without TTS, the app will:
1. Accept voice uploads
2. Store reference audio files
3. Return an error message when trying to clone/generate

## Verifying Installation

After installing TTS:

```bash
poetry run python -c "from TTS.api import TTS; print('✅ TTS available')"
```

If this prints "✅ TTS available", voice cloning will work.

## First Run Note

The first time you use voice cloning, TTS will download the XTTS-v2 model (~1.5GB). This is a one-time download.

## Troubleshooting

### "No module named 'TTS'"
- TTS is not installed
- Check Python version: `poetry run python --version`
- Must be Python 3.9-3.11

### "Model download failed"
- Check internet connection
- Try manually: `poetry run tts --list_models`

### "CUDA/GPU errors"
- TTS works on CPU (slower)
- For GPU: install `torch` with CUDA support

## Resources

- Coqui TTS GitHub: https://github.com/coqui-ai/TTS
- Coqui Documentation: https://tts.readthedocs.io/
- pyenv: https://github.com/pyenv/pyenv

