# Longform Video Generator

A Claude Code skill for generating complete long-form videos from text prompts using AI. Orchestrates video generation, image generation, audio synthesis, and professional motion graphics into polished final videos.

## Features

- **AI Video Generation**: Veo 3.1, Veo 3, Kling Pro via fal.ai
- **Image Generation**: Nano Banana Pro, Flux Ultra for storyboards
- **Audio**: ElevenLabs music, sound effects, and voiceover with word-level timestamps
- **Motion Graphics**: Lottie animations, SVG overlays, lower thirds with transparency
- **Timeline Assembly**: Voiceover-driven video editing with automatic clip timing
- **Professional Editing**: Proper audio mixing, fade transitions, color extraction

## Installation

### As a Claude Code Plugin

Add to your Claude Code plugins:

```bash
# Add the plugin
claude plugins add chadboyda/longform-video-generator
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/chadboyda/longform-video-generator.git

# Copy to your Claude Code skills directory
cp -r longform-video-generator/skills/longform-video-generator ~/.claude/skills/
```

### Dependencies

```bash
# Python dependencies
pip install requests pillow numpy

# For Lottie rendering (choose one)
pip install rlottie-python[full]
# OR
npm install -g puppeteer-lottie-cli

# FFmpeg (required)
brew install ffmpeg  # macOS
# apt install ffmpeg  # Linux
```

### API Keys

```bash
export FAL_KEY="your-fal-api-key"
export ELEVENLABS_API_KEY="your-elevenlabs-key"  # Optional, for audio
```

## Quick Start

### Generate a Video from Prompt

```python
from scripts.generate_longform import generate_from_prompt
from pathlib import Path

results = generate_from_prompt(
    api_key="your-fal-key",
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

### Add Motion Graphics

```python
from scripts.overlay_manager import create_branded_video
from pathlib import Path

result = create_branded_video(
    video_path=Path("video.mp4"),
    output_path=Path("branded.mp4"),
    logo_path=Path("logo.png"),
    cta_text="Visit example.com",
    lower_thirds=[
        {"name": "John Smith", "title": "CEO", "start": 2.0, "duration": 5.0}
    ]
)
```

### Search for Lottie Animations

```python
from scripts.lottie_search import UnifiedLottieSearch

search = UnifiedLottieSearch()

# Search by keyword
results = search.search("success", limit=10)

# Get curated by category
results = search.get_curated("money")  # business, subscribe, arrow, success, loading, social, money, tech, people

# Find for video concept
results = search.find_for_concept("SaaS product launch")
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

## Key Features

### Voiceover-Driven Timeline

When creating videos with voiceover, the voiceover timing drives video clip timing:

1. Generate voiceover with ElevenLabs (includes word timestamps)
2. Parse sentence timing from alignment data
3. Trim each video clip to match its voiceover segment
4. Concatenate with smooth transitions
5. Mix voiceover + background music at proper levels

### Professional Motion Graphics

- **Lottie Animations**: Vector animations with transparency
- **Lower Thirds**: Auto-generated name/title graphics
- **Color Extraction**: K-means clustering to match overlay colors to video
- **Safe Margins**: Proper TV-safe positioning

### FFmpeg Best Practices

Critical rules for animated overlays:

```python
# CORRECT: Video continues after overlay ends
overlay_filter = f"overlay={x}:{y}:eof_action=pass:enable='between(t,{start},{end})'"

# WRONG: Video freezes when overlay ends
overlay_filter = f"overlay={x}:{y}:shortest=1"
```

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

## License

MIT License - see LICENSE file for details.

## Author

[@chadboyda](https://github.com/chadboyda)
