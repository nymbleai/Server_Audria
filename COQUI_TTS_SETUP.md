# Coqui TTS Setup - Now Enabled

## Changes Made

### 1. **Dockerfile Updated**
- Added system dependencies required for TTS:
  - `cmake` - Build tool
  - `git` - For TTS installation
  - `libsndfile1` - Audio file library
  - `ffmpeg` - Audio processing
  - `libsox-dev` and `sox` - Audio utilities
- Added `COQUI_TOS_AGREED=1` environment variable
- Added explicit TTS installation step

### 2. **requirements.txt Updated**
- Added `numpy>=1.21.0` (required by TTS)
- Added `TTS==0.21.3` (Coqui TTS library)

### 3. **pyproject.toml Updated**
- Uncommented and enabled TTS dependency
- TTS is now a required dependency (not optional)

### 4. **voice_service.py Improved**
- Better error handling and logging
- More detailed error messages for debugging
- Improved TTS initialization feedback

## Deployment Steps

### For Render Deployment:

1. **Commit and Push Changes:**
   ```bash
   git add .
   git commit -m "Enable Coqui TTS support"
   git push
   ```

2. **Render will automatically:**
   - Rebuild the Docker image
   - Install all system dependencies
   - Install TTS library
   - Download the TTS model on first use (~1.5GB)

3. **First Run Notes:**
   - First voice generation will download the XTTS-v2 model
   - This is a one-time download (~1.5GB)
   - Subsequent requests will be faster

### Build Time Considerations:

- **Build time will increase** (~10-15 minutes due to TTS installation)
- **Image size will increase** (~2-3GB due to TTS and model)
- **First request may be slow** (model download)

## Verification

After deployment, check the logs for:
```
✅ Coqui TTS module loaded successfully
🔄 Initializing Coqui TTS with model: tts_models/multilingual/multi-dataset/xtts_v2
✅ Coqui TTS initialized successfully
```

## Troubleshooting

### If TTS still doesn't work:

1. **Check Render logs** for initialization errors
2. **Verify Python version** - Must be 3.9-3.11 (Render should use 3.11.8)
3. **Check disk space** - Model download needs ~2GB free space
4. **Check build logs** - Ensure all dependencies installed successfully

### Common Issues:

**"No module named 'TTS'"**
- TTS installation failed during build
- Check Dockerfile build logs

**"Model download failed"**
- Network issue during model download
- Will retry on next request

**"CUDA/GPU errors"**
- TTS works on CPU (slower but functional)
- GPU not required

## Performance Notes

- **CPU-only TTS** is slower but works fine
- **First generation** takes longer (model loading)
- **Subsequent generations** are faster
- Consider caching generated audio for repeated text

## Environment Variables

Make sure these are set in Render:
- `COQUI_TOS_AGREED=1` (automatically set in Dockerfile)
- `VOICE_UPLOAD_FOLDER=./uploads/voices` (optional, has default)

## Testing Locally

To test before deploying:

```bash
cd Audria_server
poetry install
poetry run python -c "from TTS.api import TTS; print('✅ TTS available')"
```

If this works, TTS will work on Render too.

