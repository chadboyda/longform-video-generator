# Overlay Selection Guide

## Overlay Types

### When to Use Each Overlay Type

| Type | Use When | Example |
|------|----------|---------|
| **Lower Third** | Introducing a person on screen, showing credentials | "John Smith, CEO" |
| **Chyron** | Same as lower third (broadcast term) | Speaker identification |
| **Logo/Bug** | Brand presence, watermark throughout video | Corner network logo |
| **CTA** | Call-to-action, drive viewer action | "Visit sumo.com" |
| **Banner** | Breaking news, alerts, section headers | "LAUNCHING TODAY" |
| **Ticker** | Multiple headlines, scrolling info | News crawler |
| **Lottie** | Visual emphasis, engagement, celebration | Animated checkmark |

### Decision Tree

```
Is there a person speaking on screen?
├── Yes → Lower Third (show name/title)
└── No → Skip lower third

Is this a news/update/announcement style video?
├── Yes → Consider Banner (headline) or Ticker (multiple items)
└── No → Skip banners

Should viewers take action?
├── Yes → CTA near end of video
└── No → Skip CTA

Want visual engagement/emphasis?
├── Yes → Lottie animation at key moments
└── No → Skip Lottie

Need persistent branding?
├── Yes → Logo/Bug in corner
└── No → Skip logo
```

### Content-Based Selection

**Product Launch / Announcement**
- Banner at start: "NEW: Product Name"
- Lottie: Success/celebration at reveal
- CTA at end: "Get it now at..."

**Interview / Testimonial**
- Lower third: Speaker name and title
- Logo bug: Company branding
- CTA at end (optional)

**Tutorial / How-To**
- Lower thirds at section changes
- Arrow Lottie: Point to UI elements
- No banners (not news style)

**News / Update**
- Banner: Headline at top
- Ticker: Additional headlines scrolling
- Lower third: Reporter/anchor name

**Promotional / Commercial**
- Lottie: Animated accents
- CTA: Strong call-to-action
- Logo bug: Brand presence
- No lower thirds unless featuring a person

## Timing Guidelines

| Overlay | Duration | When |
|---------|----------|------|
| Lower Third | 4-6s | When person first appears |
| Banner | 3-5s | At announcement moment |
| Ticker | Video length | Throughout for news |
| Logo Bug | Video length | Entire video or key sections |
| CTA | 4-6s | Last 10-15s of video |
| Lottie | 2-4s | At key moments |

## Critical FFmpeg Rules

### Animated Overlays Must Not Freeze Video

```python
# CORRECT: Video continues after overlay ends
overlay_filter = f"overlay={x}:{y}:eof_action=pass:enable='between(t,{start},{end})'"

# WRONG: Video freezes when overlay ends
overlay_filter = f"overlay={x}:{y}:shortest=1"
```

### Complete FFmpeg Command for WebM Overlay

```bash
ffmpeg -y \
  -i video.mp4 \
  -stream_loop -1 -c:v libvpx-vp9 -i animation.webm \
  -filter_complex "[1:v]format=rgba,trim=duration=5,setpts=PTS-STARTPTS,
    fade=t=in:st=0:d=0.5:alpha=1,fade=t=out:st=4.5:d=0.5:alpha=1[ov];
    [0:v][ov]overlay=x:y:eof_action=pass:enable='between(t,3,8)'" \
  -c:v libx264 -c:a copy output.mp4
```

Key flags:
- `-stream_loop -1`: Loop overlay infinitely
- `eof_action=pass`: Continue main video when overlay ends
- `enable='between(...)'`: Control visibility timing
- NO `-shortest` flag

## LottieFiles URL Format

Working: `assets*.lottiefiles.com/packages/*.json`
Blocked (403): `assets-v2.lottiefiles.com/a/*`
