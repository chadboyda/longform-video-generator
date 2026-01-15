# AI Video Artifact Detection Guide

## Common AI Generation Artifacts

When reviewing AI-generated video clips, watch for these issues:

### Temporal Artifacts (Objects Appearing/Disappearing)
- **Object pop-in/out**: Phone in hand suddenly vanishes, coffee cup appears/disappears
- **Clothing changes**: Sleeve length changes, accessories appear/vanish
- **Background morphing**: Elements in background shift position or transform

### Human Figure Artifacts
- **Extra limbs**: Extra fingers, arms blending together
- **Mirrored selves**: Same person duplicated in frame
- **Face morphing**: Facial features shift unnaturally between frames
- **Hand issues**: Wrong number of fingers, hands merging with objects

### Physics Violations
- **Impossible motion**: Objects moving through each other
- **Gravity issues**: Items floating, falling wrong direction
- **Liquid behavior**: Water/drinks behaving unnaturally
- **Shadow inconsistencies**: Shadows moving independently or wrong direction

### Visual Quality Issues
- **Blurry regions**: Parts of frame losing detail unexpectedly
- **Texture swimming**: Textures sliding/morphing across surfaces
- **Edge bleeding**: Color bleeding between objects
- **Resolution drops**: Sudden quality changes in parts of frame

## Review Workflow

### Quick Review (Contact Sheet)
```python
from video_review import generate_contact_sheet
sheet = generate_contact_sheet(video_path)
# View sheet to spot obvious issues
```

### Detailed Review (Frame Strips)
```python
from video_review import VideoReviewer
reviewer = VideoReviewer()
strips = reviewer.generate_visual_review_strip(video_path)
# View strips to catch temporal anomalies
```

### Targeted Review (Problem Frames)
```python
# Extract frames at suspicious timestamps
frames = reviewer.extract_review_frames(
    video_path,
    focus_times=[2.5, 3.0, 3.5]  # Around detected issue
)
```

## Decision Matrix

| Issue Type | Severity | Action |
|------------|----------|--------|
| Black frames | High | Regenerate clip |
| Frozen frames | High | Regenerate clip |
| Object pop-in/out | Medium | Regenerate if noticeable |
| Extra fingers | Medium | Regenerate if prominent |
| Mirrored person | High | Regenerate clip |
| Texture swim | Low | Accept if subtle |
| Minor blur | Low | Accept |

## Prompt Improvement Tips

When regenerating clips due to artifacts:

1. **For object issues**: Add explicit object descriptions
   - Bad: "Person using phone"
   - Better: "Person holding smartphone in right hand throughout scene"

2. **For physics issues**: Specify realistic motion
   - Bad: "Coffee being poured"
   - Better: "Coffee pouring smoothly from pot into mug, steam rising"

3. **For human figures**: Be specific about appearance
   - Bad: "Person walking"
   - Better: "Single person walking forward, both hands visible, natural gait"

4. **For consistency**: Use reference frames
   - Use image-to-video with a clean starting frame
   - Specify key visual elements that must remain constant
