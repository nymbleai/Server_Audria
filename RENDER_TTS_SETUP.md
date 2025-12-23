# Render Environment Setup for Coqui TTS

## What You Need to Do in Render Dashboard

### Step 1: Add Environment Variables (Optional but Recommended)

Go to your Render service dashboard → **Environment** tab and add:

```
COQUI_TOS_AGREED=1
VOICE_UPLOAD_FOLDER=./uploads/voices
TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
```

**Note:** These have defaults, but setting them explicitly is good practice.

### Step 2: Trigger a Rebuild

The Dockerfile has been updated, but Render needs to rebuild:

**Option A: Automatic (if auto-deploy is enabled)**
- Just push the code changes to your repository
- Render will automatically rebuild

**Option B: Manual Rebuild**
1. Go to Render Dashboard → Your Service
2. Click **Manual Deploy** → **Deploy latest commit**
3. Or click **Clear build cache & deploy**

### Step 3: Monitor the Build

Watch the build logs for:
- ✅ System dependencies installing (cmake, ffmpeg, etc.)
- ✅ TTS installation: `pip install TTS==0.21.3`
- ✅ No errors during TTS installation

### Step 4: Check Runtime Logs

After deployment, check the **Logs** tab for:
```
✅ Coqui TTS module loaded successfully
🔄 Initializing Coqui TTS with model: tts_models/multilingual/multi-dataset/xtts_v2
✅ Coqui TTS initialized successfully
```

If you see errors, check the troubleshooting section below.

## Required Environment Variables in Render

### Already Set in Dockerfile (No Action Needed):
- `COQUI_TOS_AGREED=1` ✅ (automatically set)

### Optional (Have Defaults):
- `VOICE_UPLOAD_FOLDER` - Default: `./uploads/voices`
- `TTS_MODEL` - Default: `tts_models/multilingual/multi-dataset/xtts_v2`

### Your Existing Variables (Keep These):
- `ENVIRONMENT=production`
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `JWT_SECRET_KEY`
- `FRONTEND_URL`
- (All your other existing variables)

## Build Time Expectations

- **First build with TTS:** 15-20 minutes
- **Image size:** ~2-3GB (increased from ~500MB)
- **Build cache:** Render will cache layers, so subsequent builds are faster

## First Request After Deployment

When you first use voice generation:
1. TTS will download the XTTS-v2 model (~1.5GB)
2. This is a **one-time download**
3. First request may take 2-5 minutes
4. Subsequent requests are much faster

## Troubleshooting

### "Coqui TTS not available" After Rebuild

**Check 1: Build Logs**
- Look for TTS installation errors
- Verify Python version is 3.11.x
- Check if all system dependencies installed

**Check 2: Runtime Logs**
- Look for TTS initialization messages
- Check for import errors
- Verify TTS module is loading

**Check 3: Disk Space**
- Render free tier has limited disk space
- TTS model needs ~2GB
- Check if disk is full

### Build Fails

**Error: "Failed to install TTS"**
- Check build logs for specific error
- May need to increase build timeout in Render settings
- Try building with `--no-cache` option

**Error: "Out of memory"**
- TTS installation is memory-intensive
- May need to upgrade Render plan
- Or use a smaller TTS model

### TTS Installs But Doesn't Work

**Check Python Version:**
```python
# In Render logs or via SSH
python --version  # Should be 3.9, 3.10, or 3.11
```

**Test TTS Import:**
```python
# In Render logs or via SSH
python -c "from TTS.api import TTS; print('✅ TTS works')"
```

## Quick Checklist

- [ ] Code changes committed and pushed to repository
- [ ] Render service is set to auto-deploy (or manually triggered rebuild)
- [ ] Build completes successfully (check build logs)
- [ ] Runtime logs show "✅ Coqui TTS module loaded successfully"
- [ ] First voice generation request downloads model successfully
- [ ] Subsequent requests work quickly

## If TTS Still Doesn't Work

1. **Check Render Service Logs** - Look for TTS-related errors
2. **Verify Dockerfile** - Make sure all changes are in the repository
3. **Check Build Logs** - Ensure TTS installed without errors
4. **Test Locally First** - If it works locally, it should work on Render

## Support

If issues persist:
1. Share Render build logs
2. Share Render runtime logs (especially TTS initialization)
3. Check if Python version is correct (3.11.x)

