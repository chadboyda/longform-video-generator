# fal.ai API Reference

## Authentication

```bash
export FAL_KEY="your-api-key"
```

## Image Models

### Nano Banana Pro (SOTA - Use This)
- **Endpoint**: `fal-ai/nano-banana-pro`
- **Pricing**: $0.15/image (4K is 2x)

**Parameters**:
| Parameter | Type | Default | Allowed Values |
|-----------|------|---------|----------------|
| `prompt` | string | required | 3-50000 chars |
| `num_images` | int | 1 | 1-4 |
| `aspect_ratio` | enum | "1:1" | 21:9, 16:9, 3:2, 4:3, 5:4, 1:1, 4:5, 3:4, 2:3, 9:16 |
| `resolution` | enum | "1K" | 1K, 2K, 4K |
| `output_format` | enum | "png" | jpeg, png, webp |

```python
result = fal_client.subscribe("fal-ai/nano-banana-pro", arguments={
    "prompt": "A serene beach at sunset, cinematic lighting",
    "aspect_ratio": "16:9",
    "resolution": "1K",
    "num_images": 1
})
# Response: {"images": [{"url": "...", "width": ..., "height": ...}]}
```

### Nano Banana Pro Edit (Character Consistency)
- **Endpoint**: `fal-ai/nano-banana-pro/edit`
- **Pricing**: $0.15/image (4K is 2x)
- **Use for**: Editing existing images AND maintaining character/object consistency across shots

**Key Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | string | required | Text description incorporating references |
| `image_urls` | array | required | URLs of reference images (up to 3 recommended) |
| `aspect_ratio` | enum | "auto" | auto, 21:9, 16:9, 3:2, 4:3, 5:4, 1:1, 4:5, 3:4, 2:3, 9:16 |
| `resolution` | enum | "1K" | 1K, 2K, 4K |
| `output_format` | enum | "png" | jpeg, png, webp |
| `num_images` | int | 1 | 1-4 |

```python
# Character consistency example - use reference from previous shot
result = fal_client.subscribe("fal-ai/nano-banana-pro/edit", arguments={
    "prompt": "Same person from reference, now standing at window, golden sunrise light",
    "image_urls": ["https://fal.ai/stored/previous_shot_url.png"],
    "aspect_ratio": "16:9",
    "resolution": "1K"
})
```

**Best Practice for Character Consistency**:
1. Generate first appearance of character with standard nano-banana-pro
2. Store the resulting image URL
3. For subsequent shots with same character, use nano-banana-pro/edit with stored URL as reference
4. Include descriptive reference in prompt: "Same person from reference image..."

## Video Models

### Veo 3.1 Image-to-Video (Recommended)
- **Endpoint**: `fal-ai/veo3.1/image-to-video`
- **Pricing**: $0.40/sec (audio on), $0.20/sec (audio off)

**Parameters**:
| Parameter | Type | Default | Allowed Values |
|-----------|------|---------|----------------|
| `prompt` | string | required | max 20000 chars (motion description) |
| `image_url` | string | required | URL of input image |
| `aspect_ratio` | enum | "auto" | auto, 16:9, 9:16 |
| `duration` | enum | "8s" | **4s, 6s, 8s ONLY** |
| `resolution` | enum | "720p" | 720p, 1080p |
| `generate_audio` | bool | true | true, false |
| `auto_fix` | bool | false | true, false |

```python
result = fal_client.subscribe("fal-ai/veo3.1/image-to-video", arguments={
    "prompt": "Camera slowly zooms in, subject turns head",
    "image_url": "https://example.com/image.png",
    "duration": "8s",  # MUST be 4s, 6s, or 8s
    "resolution": "720p",
    "generate_audio": True
})
# Response: {"video": {"url": "..."}}
```

### Veo 3.1 Fast (Text-to-Video)
- **Endpoint**: `fal-ai/veo3.1/fast`
- **Pricing**: $0.15/sec

### Kling 2.6 Pro
- **Endpoint**: `fal-ai/kling-video/v2.6/pro/image-to-video`
- **Duration**: 5s or 10s

## Audio Models

### ElevenLabs Music
- **Endpoint**: `fal-ai/elevenlabs/music`

**Parameters**:
| Parameter | Type | Default | Allowed Values |
|-----------|------|---------|----------------|
| `prompt` | string | - | Music description |
| `music_length_ms` | int | - | 3000-600000 (3sec to 10min) |
| `force_instrumental` | bool | false | true, false |
| `output_format` | enum | "mp3_44100_128" | mp3_*, pcm_*, opus_* |

```python
result = fal_client.subscribe("fal-ai/elevenlabs/music", arguments={
    "prompt": "Inspiring orchestral, piano-driven, building crescendo",
    "music_length_ms": 30000,  # 30 seconds
    "force_instrumental": True
})
# Response: {"audio": {"url": "..."}}
```

### ElevenLabs TTS
- **Endpoint**: `fal-ai/elevenlabs/tts/turbo-v2.5`

**Parameters**:
| Parameter | Type | Default | Allowed Values |
|-----------|------|---------|----------------|
| `text` | string | required | max 5000 chars |
| `voice` | string | "Rachel" | Aria, Roger, Sarah, Laura, Charlie, George, Brian, Daniel, etc. |
| `stability` | float | 0.5 | 0-1 |
| `similarity_boost` | float | 0.75 | 0-1 |
| `speed` | float | 1.0 | 0.7-1.2 |

```python
result = fal_client.subscribe("fal-ai/elevenlabs/tts/turbo-v2.5", arguments={
    "text": "Welcome to AppSumo, where entrepreneurs launch.",
    "voice": "Brian",  # NOT voice_id!
    "stability": 0.5,
    "similarity_boost": 0.75,
    "speed": 0.95
})
# Response: {"audio": {"url": "..."}}
```

### ElevenLabs Sound Effects
- **Endpoint**: `fal-ai/elevenlabs/sound-effects`

**Parameters**:
| Parameter | Type | Default | Allowed Values |
|-----------|------|---------|----------------|
| `text` | string | required | SFX description |
| `duration_seconds` | float | - | 0.5-22 |
| `prompt_influence` | float | 0.3 | 0-1 |

## Common Errors

### Duration Error (Veo)
```json
{"detail": [{"msg": "unexpected value; permitted: '4s', '6s', '8s'"}]}
```
**Fix**: Only use "4s", "6s", or "8s" for duration.

### Rate Limits
- Max 2 concurrent requests per user
- Implement exponential backoff

## Best Practices

1. **Always use Nano Banana Pro** for image generation
2. **Use image-to-video** (not text-to-video) for visual consistency
3. **Duration must be 4s, 6s, or 8s** for Veo models
4. **Use voice preset names** for TTS (not voice_id)
5. **Check API specs** before calling any model
