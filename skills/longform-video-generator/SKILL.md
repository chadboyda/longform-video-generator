---
name: longform-video-generator
description: |
  Generate complete long-form videos from a single prompt using fal.ai APIs.
  Orchestrates video generation (Veo 3.1, Kling), image generation (Nano Banana Pro),
  audio (ElevenLabs music/SFX/TTS), and ffmpeg stitching.

  Use when: (1) Creating multi-scene videos from text prompts, (2) Generating
  AI videos with background music, (3) Building video content pipelines,
  (4) Image-to-video workflows, (5) Any task requiring fal.ai video/audio generation.

  Triggers: "generate video", "create longform video", "make AI video",
  "fal.ai video", "Veo video", "video from prompt", "stitch video clips"
---

# Long-Form Video Generator

Generate complete videos from prompts using fal.ai models and ffmpeg.

## Quick Start

```bash
# Set API key
export FAL_KEY="your-fal-api-key"

# Generate 3-scene video from prompt
python scripts/generate_longform.py "A day in Tokyo, from sunrise to neon-lit night" \
  -n 3 -m veo31_fast -r 720p
```

## Workflow

### 1. Single Prompt → Full Video

```python
from scripts.generate_longform import generate_from_prompt

results = generate_from_prompt(
    api_key="your-key",
    prompt="Epic mountain adventure documentary",
    output_dir=Path("./output"),
    num_scenes=5,
    scene_duration="8s",
    video_model="veo31_fast",
    include_music=True,
    style="cinematic, drone footage, epic landscapes"
)
print(f"Video: {results['output']}")
```

### 2. Structured Concept → Video

Create `concept.json`:
```json
{
  "title": "Tech Product Launch",
  "scenes": [
    {"prompt": "Sleek smartphone rotating on white background, product showcase", "duration": "6s"},
    {"prompt": "Hand picking up phone, tapping screen, UI animations visible", "duration": "8s"},
    {"prompt": "Person smiling using phone outdoors, lifestyle shot", "duration": "8s"},
    {"prompt": "Product logo reveal with particle effects", "duration": "4s"}
  ],
  "music_prompt": "Modern electronic music, upbeat and innovative, tech commercial vibe",
  "style": "clean, professional, high-end commercial"
}
```

Run:
```bash
python scripts/generate_longform.py --concept-file concept.json -m veo31_fast
```

### 3. Individual Components

**Video only**:
```bash
python scripts/generate_video.py "Golden retriever running in meadow" -o dog.mp4 -d 8s
```

**Batch scenes**:
```bash
python scripts/generate_video.py --scenes scenes.json --scenes-dir ./clips
```

**Images for storyboard**:
```bash
python scripts/generate_images.py "Futuristic cityscape" -o city.png -m nano_banana_pro
```

**Music**:
```bash
python scripts/generate_audio.py music "Cinematic orchestral, epic trailer" -o music.mp3
```

**Sound effects**:
```bash
python scripts/generate_audio.py sfx "Thunder rumbling" -o thunder.mp3
```

**Stitch clips**:
```bash
python scripts/stitch_video.py concat clip1.mp4 clip2.mp4 clip3.mp4 -o final.mp4
python scripts/stitch_video.py concat --transitions *.mp4 -o final_with_fades.mp4
```

**Add music to video**:
```bash
python scripts/stitch_video.py audio video.mp4 music.mp3 -o final.mp4 --volume 0.3
```

## Available Models

| Type | Model | ID | Cost | Best For |
|------|-------|-----|------|----------|
| Video | Veo 3.1 Fast | `veo31_fast` | $0.15/s | Speed, cost |
| Video | Veo 3 | `veo3` | $0.40/s | Quality |
| Video | Kling Pro | `kling_pro` | ~$0.10/s | Motion |
| Image | Nano Banana Pro | `nano_banana_pro` | $0.15/img | Photorealism |
| Image | Flux Ultra | `flux_ultra` | $0.06/img | Artistic |
| Audio | ElevenLabs Music | `elevenlabs_music` | varies | Background |
| Audio | ElevenLabs SFX | `elevenlabs_sfx` | varies | Effects |

## Prompting Tips

Good prompts include: **Subject** + **Action** + **Setting** + **Style** + **Camera**

```
A young woman walking through neon-lit Tokyo streets at night,
rain-slicked pavement reflecting colorful signs,
cinematic, blade runner aesthetic, tracking shot,
shallow depth of field, 4K quality
```

See `references/prompting_guide.md` for detailed guidance.

## Output Structure

```
video_project_YYYYMMDD_HHMMSS/
├── scenes/           # Individual video clips
├── storyboard/       # Generated images (if used)
├── audio/            # Music and sound effects
├── temp/             # Normalized/intermediate files
├── output/           # Final video
└── generation_results.json
```

## Timeline-Based Assembly (Voiceover-Driven)

When creating videos with voiceover, **voiceover timing drives video timing**.

### Flow
1. Generate voiceover with ElevenLabs (with timestamps)
2. Parse word/sentence timing from alignment data
3. Trim each video clip to match its voiceover segment
4. Concatenate clips with proper transitions
5. Mix audio (voiceover + music)

### ElevenLabs Integration

Use the ElevenLabs API directly for word-level timestamps:

```python
from scripts.elevenlabs_client import ElevenLabsClient

client = ElevenLabsClient(api_key="your-key")
result = client.generate_voiceover_with_timestamps(
    text="Your script here...",
    output_path=Path("voiceover.mp3"),
    voice="josh"  # or: adam, rachel, bella, sam
)

# Access timing data
for sentence in result.sentences:
    print(f"[{sentence.start:.2f}s - {sentence.end:.2f}s] {sentence.text}")
```

### Timeline Assembly

```python
from scripts.timeline_assembler import assemble_with_timing

result = assemble_with_timing(
    voiceover_segments=[{"text": "...", "start": 0.0, "end": 3.5}, ...],
    video_clips=[Path("clip_000.mp4"), ...],
    voiceover_path=Path("voiceover.mp3"),
    voiceover_duration=42.5,
    output_path=Path("final.mp4"),
    music_path=Path("music.mp3")
)
```

## Professional Editing Rules

### Clip Duration
- **NEVER loop or repeat clips** - it looks unprofessional
- **Minimum 2.5 seconds per clip** - shorter cuts feel jumpy
- If clip is longer than needed: trim it
- If clip is shorter than needed: use full clip (don't extend)

### Video-Audio Sync
- When video ends before voiceover: create fade-to-black outro
- **NEVER freeze frame** - it's a cop-out
- Add 1.5s fade-out at end, then black screen while audio finishes

### Audio Mixing Best Practices
- **Normalize sample rates first** (44100Hz → 48000Hz)
- **Convert mono to stereo** before mixing
- **Music volume: 15%** relative to voiceover
- Use `amix` with `normalize=0` to prevent level reduction
- Always validate audio quality after mixing

```python
# Proper audio mix filter
filter_complex = (
    "[1:a]aresample=48000[vo];"
    "[2:a]aresample=48000,volume=0.15[music];"
    "[vo][music]amix=inputs=2:duration=first:normalize=0[audio]"
)
```

### Outro Sequence (When Video < Audio)
Instead of freeze frame or abrupt cuts:
1. Fade last 1.5s of video to black
2. Add black screen for remaining audio
3. Result: professional trailer-like ending

## Motion Graphics & Overlays

Professional motion graphics with transparency support for:
- **Lottie animations** (.json) - Vector animations that scale at any resolution
- **SVG graphics** (.svg) - Logos, icons, scalable vectors
- **PNG overlays** (.png) - Static images with alpha channel
- **WebM VP9** (.webm) - Video with transparency

### Dependencies

```bash
pip install rlottie-python[full] pillow
# Or use puppeteer-lottie-cli: npm install -g puppeteer-lottie-cli
```

### Quick Start - Add Overlays

```python
from scripts.overlay_manager import create_branded_video
from pathlib import Path

result = create_branded_video(
    video_path=Path("video.mp4"),
    output_path=Path("branded.mp4"),
    logo_path=Path("logo.png"),         # Watermark
    cta_text="Visit sumo.com",          # Call-to-action
    lower_thirds=[
        {"name": "John Smith", "title": "CEO", "start": 2.0, "duration": 5.0}
    ],
    lottie_overlays=[
        {"path": "subscribe.json", "position": "bottom_right", "start": 30.0}
    ]
)
```

### Overlay Positions

| Position | Description |
|----------|-------------|
| `lower_third_left` | Bottom-left, standard name/title placement |
| `lower_third_center` | Bottom-center, centered text |
| `lower_third_right` | Bottom-right |
| `top_left` / `top_right` | Corner watermarks (logo) |
| `bottom_left` / `bottom_right` | Corner watermarks |
| `center` | Centered (titles, transitions) |
| `fullscreen` | Full-screen overlays |

### Lottie Animation Overlay

```python
from scripts.motion_graphics import add_motion_graphics

result = add_motion_graphics(
    video_path=Path("video.mp4"),
    output_path=Path("with_overlay.mp4"),
    overlays=[{
        "source": "/path/to/animation.json",  # Lottie JSON
        "position": "lower_third_left",
        "start_time": 2.0,
        "duration": 5.0,
        "fade_in": 0.5,
        "fade_out": 0.3,
        "scale": 1.0
    }]
)
```

### Lower Third Text Generation

```python
from scripts.motion_graphics import TextOverlayGenerator

gen = TextOverlayGenerator()
png_path = gen.create_lower_third(
    name="Sarah Johnson",
    title="Product Manager",
    width=600,
    height=120,
    accent_color="#3498db"
)
```

### Timing Best Practices

- **Lower thirds**: 4-6 seconds (enough to read, not overstay)
- **Logo watermarks**: Entire video or key segments
- **CTAs**: 4-6 seconds, near end of video
- **Transitions**: 0.5-1.5 seconds
- **Fade in/out**: 0.3-0.5 seconds for smooth appearance

### Transparency Pipeline

1. **Lottie → PNG sequence** (with alpha via rlottie-python)
2. **PNG sequence → WebM VP9** (preserves alpha channel)
3. **FFmpeg overlay** composites with proper alpha handling

```bash
# Manual WebM with alpha encoding
ffmpeg -i frames_%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -crf 30 overlay.webm

# Composite overlay onto video
ffmpeg -i video.mp4 -i overlay.webm -filter_complex "[0][1]overlay=10:10" output.mp4
```

### Lottie Animation Sources

Use the `lottie_search.py` module to find animations:

```python
from scripts.lottie_search import UnifiedLottieSearch

search = UnifiedLottieSearch()

# Search by keyword
results = search.search("success", limit=10)

# Get curated by category (business, subscribe, arrow, success, loading, social, money, tech, people)
results = search.get_curated("money")

# Find animations for a video concept
results = search.find_for_concept("SaaS discount deal")
```

**URL Format Note**: LottieFiles URLs work with format `assets*.lottiefiles.com/packages/*.json`.
The `assets-v2.lottiefiles.com/a/*` format returns 403 Forbidden.

### Critical FFmpeg Overlay Rules

When compositing animated overlays, follow these rules to avoid video freeze:

1. **NEVER use `shortest=1`** on overlay filter - it stops the entire video when overlay ends
2. **Use `eof_action=pass`** - tells FFmpeg to continue main video after overlay ends
3. **Use `enable='between(t,start,end)'`** - controls when overlay is visible
4. **Loop overlays infinitely** with `-stream_loop -1`, trim in filter graph

```python
# CORRECT: Video continues after overlay ends
overlay_filter = f"overlay={x}:{y}:eof_action=pass:enable='between(t,{start},{end})'"

# WRONG: Video freezes when overlay ends
overlay_filter = f"overlay={x}:{y}:shortest=1"
```

**Complete FFmpeg command for animated WebM overlay:**
```bash
ffmpeg -y \
  -i video.mp4 \
  -stream_loop -1 -c:v libvpx-vp9 -i animation.webm \
  -filter_complex "[1:v]format=rgba,trim=duration=5,setpts=PTS-STARTPTS,
    fade=t=in:st=0:d=0.5:alpha=1,fade=t=out:st=4.5:d=0.5:alpha=1[ov];
    [0:v][ov]overlay=x:y:eof_action=pass:enable='between(t,3,8)'" \
  -c:v libx264 -c:a copy output.mp4
```

## Error Handling

- **Rate limits**: Auto-retries with exponential backoff
- **Content policy**: Enable `auto_fix` or revise prompt
- **Concat failures**: Falls back to filter method
- **Audio static/artifacts**: Check sample rate mismatches
- **Lottie render fails**: Falls back to puppeteer-lottie-cli if available

## References

- `references/fal_api_reference.md` - Full API documentation
- `references/prompting_guide.md` - Detailed prompting strategies

## Script Files

| Script | Purpose |
|--------|---------|
| `video_pipeline.py` | Full pipeline orchestration |
| `elevenlabs_client.py` | ElevenLabs API with timestamps |
| `timeline_assembler.py` | Voiceover-driven video assembly |
| `audio_mixer.py` | Professional audio mixing |
| `motion_graphics.py` | Lottie/SVG/PNG overlay rendering |
| `overlay_manager.py` | Intelligent overlay placement |
| `design_system.py` | Professional typography & color extraction |
| `lottie_search.py` | LottieFiles search & download |
| `generate_longform.py` | Single-prompt video generation |
| `generate_video.py` | Individual video clip generation |
| `generate_audio.py` | Music and SFX generation |
| `stitch_video.py` | FFmpeg video concatenation |
