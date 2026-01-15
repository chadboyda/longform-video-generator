---
name: longform-video-generator
description: |
  Generate complete long-form videos from text prompts using AI. Orchestrates
  video generation (Veo 3.1, Kling), image generation (Nano Banana Pro), audio
  (ElevenLabs music/SFX/TTS with timestamps), and professional motion graphics.
  Includes video QA tools for detecting glitches and AI artifacts.

  Use when: (1) Creating multi-scene videos from prompts, (2) Generating AI
  videos with background music, (3) Adding motion graphics/overlays to video,
  (4) Voiceover-driven timeline assembly, (5) Image-to-video workflows,
  (6) Adding Lottie animations, banners, tickers, lower thirds to video,
  (7) Reviewing video clips for quality issues and AI artifacts.

  Triggers: "generate video", "create longform video", "make AI video",
  "fal.ai video", "add overlay", "motion graphics", "lower third",
  "news ticker", "banner overlay", "Lottie animation", "review video",
  "check video quality", "detect glitches", "extract frames"
---

# Long-Form Video Generator

Generate complete videos from prompts using fal.ai models and ffmpeg.

## Quick Start

```bash
export FAL_KEY="your-fal-api-key"
python scripts/generate_longform.py "A day in Tokyo" -n 3 -m veo31_fast
```

## Core Workflows

### 1. Prompt → Video

```python
from scripts.generate_longform import generate_from_prompt

results = generate_from_prompt(
    api_key="key",
    prompt="Epic mountain documentary",
    num_scenes=5,
    video_model="veo31_fast",
    include_music=True
)
```

### 2. Motion Graphics

```python
from scripts.motion_graphics import add_motion_graphics

add_motion_graphics(
    video_path=Path("video.mp4"),
    output_path=Path("with_overlay.mp4"),
    overlays=[{
        "source": "animation.json",
        "position": "bottom_right",
        "start_time": 3.0,
        "duration": 5.0
    }]
)
```

### 3. Broadcast Overlays (Banners/Tickers)

```python
from scripts.motion_graphics import BroadcastOverlays

broadcast = BroadcastOverlays()

# Breaking news banner
broadcast.apply_banner(
    video_path, output_path,
    text="LAUNCHING TODAY: Sumo.com",
    style="breaking",  # breaking, alert, headline, update
    position="top",
    start_time=0,
    duration=5
)

# News ticker
broadcast.apply_ticker(
    video_path, output_path,
    headlines=["50% off SaaS tools", "Lifetime deals available", "Limited time"],
    speed=100
)
```

### 4. Lottie Search

```python
from scripts.lottie_search import UnifiedLottieSearch

search = UnifiedLottieSearch()
results = search.search("success", limit=10)
results = search.get_curated("money")  # business, subscribe, arrow, success, loading, social, money, tech, people
results = search.find_for_concept("SaaS product launch")
```

### 5. Video Review & QA

```python
from scripts.video_review import VideoReviewer, review_video

# Quick review with contact sheet
report = review_video(Path("video.mp4"))
print(report["recommendation"])

# Detailed review
reviewer = VideoReviewer()

# Generate contact sheet for quick visual check
sheet = reviewer.generate_contact_sheet(video_path)

# Generate strips for temporal analysis
strips = reviewer.generate_visual_review_strip(video_path)

# Full analysis (glitches + AI artifacts)
glitch_report = reviewer.analyze_video(video_path)
if glitch_report.ai_artifacts:
    for a in glitch_report.ai_artifacts:
        print(f"{a.timestamp}s: {a.description}")

# Extract frames for visual inspection
frames = reviewer.extract_review_frames(video_path, interval=0.5)
```

See `references/ai_artifacts_guide.md` for common AI artifact types.

## Models

| Type | Model | ID | Best For |
|------|-------|-----|----------|
| Video | Veo 3.1 Fast | `veo31_fast` | Speed, cost |
| Video | Veo 3 | `veo3` | Quality |
| Video | Kling Pro | `kling_pro` | Motion |
| Image | Nano Banana Pro | `nano_banana_pro` | Photorealism |
| Audio | ElevenLabs | `elevenlabs_music` | Background |

## Overlay Types

| Type | When to Use |
|------|-------------|
| **Lower Third** | Person on screen - show name/title |
| **Banner** | Announcements, breaking news, section headers |
| **Ticker** | Scrolling headlines, multiple items |
| **Logo/Bug** | Persistent branding in corner |
| **CTA** | Call-to-action near end |
| **Lottie** | Visual emphasis at key moments |

See `references/overlay_guide.md` for detailed selection guidance.

## Professional Rules

### Video-Audio Sync
- When video < audio: fade to black, continue audio (trailer ending)
- NEVER freeze frame or loop clips

### Audio Mixing
- Normalize to 48kHz before mixing
- Music volume: 15% relative to voiceover
- Use `amix` with `normalize=0`

### Animated Overlays
- Use `eof_action=pass` (video continues after overlay)
- NEVER use `shortest=1` (freezes video)
- Loop with `-stream_loop -1`, trim in filter

## Scripts

| Script | Purpose |
|--------|---------|
| `generate_longform.py` | Single-prompt video generation |
| `motion_graphics.py` | Overlay rendering and compositing |
| `video_review.py` | QA, glitch detection, AI artifact detection |
| `overlay_manager.py` | Intelligent overlay placement |
| `lottie_search.py` | LottieFiles search & download |
| `design_system.py` | Typography & color extraction |
| `timeline_assembler.py` | Voiceover-driven assembly |
| `elevenlabs_client.py` | TTS with timestamps |
| `audio_mixer.py` | Professional mixing |
| `stitch_video.py` | FFmpeg concatenation |

## References

- `references/overlay_guide.md` - Overlay selection and FFmpeg rules
- `references/ai_artifacts_guide.md` - AI artifact detection and prompt fixes
- `references/fal_api_reference.md` - API documentation
- `references/prompting_guide.md` - Video prompt strategies
