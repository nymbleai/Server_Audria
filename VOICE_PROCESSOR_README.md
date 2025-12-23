# Voice Processor Module - Implementation Guide

## Overview

The voice processor module has been successfully integrated into the Audria backend. It provides voice cloning and speech generation capabilities using Coqui TTS, integrated with the media library.

## Installation

### 1. Install Dependencies

```bash
cd Audria_server
poetry install
```

This will install:
- `TTS==0.21.3` - Coqui TTS library for voice cloning
- `numpy>=1.21.0` - Required by TTS

### 2. Set Environment Variables

Add to your `.env` file:

```bash
# Voice processing configuration
VOICE_UPLOAD_FOLDER=./uploads/voices
TTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2
COQUI_TOS_AGREED=1
```

### 3. Agree to Coqui TOS

The module automatically sets `COQUI_TOS_AGREED=1`, but you may need to set it in your environment:

```bash
export COQUI_TOS_AGREED=1
```

## API Endpoints

All endpoints are available at `/api/voices` and require authentication.

### 1. Upload Voice

**POST** `/api/voices/upload`

Upload and process a voice file for cloning.

**Request:**
- `audio_file` (file): Audio file (WAV, MP3, M4A, OGG, FLAC, AAC)
- `voice_name` (form): Name for the voice (e.g., "John", "Mom")
- `voice_type` (form, optional): Type of voice (default: "custom")
- `user_id` (form, optional): User ID (defaults to authenticated user)
- `test_text` (form, optional): Text for test audio generation

**Response:**
```json
{
  "success": true,
  "voice_id": "local_user123_John_1234567890",
  "voice_name": "John",
  "voice_type": "custom",
  "reference_path": "./uploads/voices/local_user123_John_1234567890/reference.wav",
  "test_path": "./uploads/voices/local_user123_John_1234567890/test.wav",
  "message": "Voice 'John' created successfully using Coqui TTS"
}
```

**Example (curl):**
```bash
curl -X POST "http://localhost:8000/api/voices/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "audio_file=@voice_sample.wav" \
  -F "voice_name=John" \
  -F "voice_type=custom"
```

### 2. Generate Speech

**POST** `/api/voices/generate`

Generate speech from text using a cloned voice.

**Request:**
```json
{
  "text": "Hello, this is a test of the voice cloning system.",
  "voice_id": "local_user123_John_1234567890",
  "language": "en",
  "return_audio_data": false
}
```

**Response:**
```json
{
  "success": true,
  "file_path": "./uploads/voices/temp/generated_local_user123_John_1234567890_1234567890.wav",
  "message": "Audio generated successfully"
}
```

### 3. Generate Speech (File Download)

**GET** `/api/voices/generate/{voice_id}?text=Hello&language=en`

Generate speech and return the audio file directly.

**Response:** Audio file (WAV format)

### 4. List Voices

**GET** `/api/voices`

List all voices for the authenticated user.

**Response:**
```json
{
  "success": true,
  "voices": [
    {
      "voice_id": "local_user123_John_1234567890",
      "voice_name": "John",
      "reference_path": "./uploads/voices/local_user123_John_1234567890/reference.wav",
      "test_path": "./uploads/voices/local_user123_John_1234567890/test.wav",
      "created_at": "2025-01-22T14:30:00"
    }
  ]
}
```

### 5. Get Voice Info

**GET** `/api/voices/{voice_id}`

Get detailed information about a specific voice.

**Response:**
```json
{
  "success": true,
  "voice_info": {
    "voice_id": "local_user123_John_1234567890",
    "voice_dir": "./uploads/voices/local_user123_John_1234567890",
    "reference_exists": true,
    "test_exists": true,
    "reference_size": 1234567,
    "reference_created": "2025-01-22T14:30:00"
  }
}
```

### 6. Delete Voice

**DELETE** `/api/voices/{voice_id}`

Delete a voice and all its associated files.

**Response:**
```json
{
  "success": true,
  "message": "Voice local_user123_John_1234567890 deleted successfully"
}
```

## Usage Examples

### Python Client Example

```python
import requests

# Authentication token
token = "YOUR_AUTH_TOKEN"
headers = {"Authorization": f"Bearer {token}"}
base_url = "http://localhost:8000/api/voices"

# 1. Upload a voice
with open("voice_sample.wav", "rb") as f:
    files = {"audio_file": f}
    data = {
        "voice_name": "John",
        "voice_type": "custom"
    }
    response = requests.post(f"{base_url}/upload", headers=headers, files=files, data=data)
    result = response.json()
    voice_id = result["voice_id"]

# 2. Generate speech
generate_data = {
    "text": "Hello, this is a test.",
    "voice_id": voice_id
}
response = requests.post(f"{base_url}/generate", headers=headers, json=generate_data)
result = response.json()
print(f"Generated audio: {result['file_path']}")

# 3. List all voices
response = requests.get(base_url, headers=headers)
voices = response.json()["voices"]
for voice in voices:
    print(f"{voice['voice_name']}: {voice['voice_id']}")
```

### JavaScript/TypeScript Example

```typescript
const API_URL = "http://localhost:8000/api/voices";
const token = "YOUR_AUTH_TOKEN";

// 1. Upload voice
const formData = new FormData();
formData.append("audio_file", audioFile);
formData.append("voice_name", "John");
formData.append("voice_type", "custom");

const uploadResponse = await fetch(`${API_URL}/upload`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${token}`
  },
  body: formData
});

const uploadResult = await uploadResponse.json();
const voiceId = uploadResult.voice_id;

// 2. Generate speech
const generateResponse = await fetch(`${API_URL}/generate`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    text: "Hello, this is a test.",
    voice_id: voiceId
  })
});

const generateResult = await generateResponse.json();
console.log("Generated audio:", generateResult.file_path);
```

## File Structure

```
Audria_server/
├── app/
│   ├── services/
│   │   └── voice_service.py      # VoiceProcessor class
│   ├── routers/
│   │   └── voices.py             # FastAPI endpoints
│   └── schemas/
│       └── voice.py              # Pydantic schemas
├── uploads/
│   └── voices/                   # Voice storage directory
│       ├── local_user123_John_1234567890/
│       │   ├── reference.wav     # Original voice sample
│       │   └── test.wav         # Generated test audio
│       └── temp/                 # Temporary generated audio
└── VOICE_PROCESSOR_README.md     # This file
```

## Supported Audio Formats

- **WAV** (recommended for best quality)
- **MP3**
- **M4A**
- **OGG**
- **FLAC**
- **AAC**

## Audio File Recommendations

- **Duration**: 10-30 seconds of natural speech
- **Quality**: Clear audio with minimal background noise
- **Format**: WAV format preferred (16kHz+ sample rate)
- **Content**: Natural, conversational speech works best
- **Environment**: Record in a quiet space

## System Requirements

- **Python**: 3.9 or higher
- **RAM**: 8GB minimum (16GB recommended)
- **Disk Space**: 10GB+ free space
- **GPU**: Optional but recommended for faster processing

## Troubleshooting

### TTS Not Initializing

**Error**: `Coqui TTS not initialized`

**Solutions**:
1. Ensure TTS is installed: `poetry install`
2. Set `COQUI_TOS_AGREED=1` in environment
3. Check if models are downloaded (first use will download automatically)
4. Verify sufficient disk space (models are large)

### Out of Memory

**Solutions**:
- Close other applications
- Use smaller TTS models
- Process voices one at a time
- Increase system RAM

### Audio Quality Poor

**Solutions**:
- Use WAV format instead of compressed formats
- Ensure reference audio is clear (no background noise)
- Use 10-30 seconds of natural speech
- Check audio sample rate (16kHz minimum)

### File Not Found Errors

**Solutions**:
- Check file paths are correct
- Ensure upload folder exists
- Verify file permissions
- Check disk space availability

## Integration with Media Library

The voice processor is integrated with the media library:

1. **Upload**: Users can upload voice files through the media library
2. **Storage**: Voices are stored in `./uploads/voices/`
3. **Management**: Voices can be listed, viewed, and deleted through the API
4. **Generation**: Speech can be generated on-demand for any cloned voice

## Security

- All endpoints require authentication via `get_current_user`
- Users can only access their own voices (filtered by `user_id`)
- Voice IDs are prefixed with user ID for isolation
- File uploads are validated for type and size

## Next Steps

1. **Install dependencies**: Run `poetry install`
2. **Set environment variables**: Add to `.env` file
3. **Test the API**: Use the examples above or test via Swagger UI at `/docs`
4. **Integrate with frontend**: Update MediaLibrary.tsx to support voice uploads

## API Documentation

Full API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

Look for the "Voices" tag in the API documentation.

