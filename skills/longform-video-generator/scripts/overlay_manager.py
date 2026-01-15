#!/usr/bin/env python3
"""
Intelligent Overlay Manager for Video Production.

Automatically determines optimal placement, timing, and styling for
motion graphics overlays based on video content and context.

Uses professional design system for broadcast-quality results.

Overlay Types:
- Lower thirds (speaker names, titles)
- Logo watermarks
- Call-to-action (CTAs)
- Scene transitions
- Captions/subtitles
- Animated accents

Reference: https://riverside.fm/blog/lower-thirds
Reference: https://blog.frame.io/2017/12/04/create-lower-thirds-titles-that-dont-suck/
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from motion_graphics import (
    OverlayConfig, OverlayPosition, OverlayTiming,
    MotionGraphicsCompositor, TextOverlayGenerator,
    add_motion_graphics, MotionGraphicsResult
)

from design_system import (
    ColorExtractor, FFmpegTextRenderer, ProfessionalTextRenderer,
    LowerThirdDesign, ColorPalette, Typography, DesignStyle, LottieLibrary
)


class OverlayType(Enum):
    """Types of overlays for different use cases."""
    LOWER_THIRD = "lower_third"       # Name/title identification
    LOGO_WATERMARK = "logo_watermark" # Brand logo
    CTA = "cta"                       # Call to action
    TITLE_CARD = "title_card"         # Scene/section titles
    TRANSITION = "transition"         # Scene transitions
    CAPTION = "caption"               # Subtitles/captions
    ACCENT = "accent"                 # Decorative animations
    CUSTOM = "custom"                 # User-defined


class ContentContext(Enum):
    """Video content context for intelligent placement."""
    TALKING_HEAD = "talking_head"     # Person speaking to camera
    B_ROLL = "b_roll"                 # Supplementary footage
    PRODUCT_SHOT = "product_shot"     # Product showcase
    LANDSCAPE = "landscape"           # Scenery/environment
    ACTION = "action"                 # Dynamic/motion content
    INTERVIEW = "interview"           # Multi-person dialogue
    PRESENTATION = "presentation"     # Slides/screen share
    INTRO = "intro"                   # Opening sequence
    OUTRO = "outro"                   # Closing sequence


@dataclass
class OverlayTemplate:
    """Pre-configured overlay template for common use cases."""
    name: str
    type: OverlayType
    position: OverlayPosition
    default_duration: float = 4.0
    fade_in: float = 0.3
    fade_out: float = 0.3
    scale: float = 1.0
    lottie_url: Optional[str] = None  # LottieFiles URL
    local_asset: Optional[Path] = None


# Pre-built templates for common overlay types
OVERLAY_TEMPLATES = {
    # Lower thirds
    "lower_third_simple": OverlayTemplate(
        name="Simple Lower Third",
        type=OverlayType.LOWER_THIRD,
        position=OverlayPosition.LOWER_THIRD_LEFT,
        default_duration=5.0,
        fade_in=0.4,
        fade_out=0.4
    ),
    "lower_third_modern": OverlayTemplate(
        name="Modern Lower Third",
        type=OverlayType.LOWER_THIRD,
        position=OverlayPosition.LOWER_THIRD_LEFT,
        default_duration=5.0,
        fade_in=0.5,
        fade_out=0.3,
        lottie_url="https://lottiefiles.com/animations/lower-third"
    ),

    # Logo watermarks
    "logo_corner_br": OverlayTemplate(
        name="Logo Bottom Right",
        type=OverlayType.LOGO_WATERMARK,
        position=OverlayPosition.BOTTOM_RIGHT,
        default_duration=0,  # 0 = entire video
        scale=0.8
    ),
    "logo_corner_tr": OverlayTemplate(
        name="Logo Top Right",
        type=OverlayType.LOGO_WATERMARK,
        position=OverlayPosition.TOP_RIGHT,
        default_duration=0,
        scale=0.7
    ),

    # CTAs
    "cta_subscribe": OverlayTemplate(
        name="Subscribe CTA",
        type=OverlayType.CTA,
        position=OverlayPosition.BOTTOM_RIGHT,
        default_duration=4.0,
        fade_in=0.3,
        fade_out=0.3
    ),
    "cta_link": OverlayTemplate(
        name="Link CTA",
        type=OverlayType.CTA,
        position=OverlayPosition.BOTTOM_CENTER,
        default_duration=5.0
    ),

    # Transitions
    "transition_fade": OverlayTemplate(
        name="Fade Transition",
        type=OverlayType.TRANSITION,
        position=OverlayPosition.FULLSCREEN,
        default_duration=1.0
    ),
}


@dataclass
class OverlayPlan:
    """A planned overlay to be applied to video."""
    type: OverlayType
    source: Optional[Path] = None        # Asset path (Lottie, PNG, etc.)
    position: OverlayPosition = OverlayPosition.LOWER_THIRD_LEFT
    start_time: float = 0.0
    duration: float = 4.0
    fade_in: float = 0.3
    fade_out: float = 0.3
    scale: float = 1.0
    text_content: Optional[Dict] = None  # For generated text overlays
    template: Optional[str] = None       # Template name to use


@dataclass
class VideoSegment:
    """A segment of video with associated metadata."""
    index: int
    start: float
    end: float
    text: str = ""                       # Voiceover/script text
    context: ContentContext = ContentContext.B_ROLL
    speaker: Optional[str] = None
    speaker_title: Optional[str] = None


class OverlayManager:
    """
    Manages overlay planning and application for video production.

    Features:
    - Intelligent placement based on content context
    - Automatic timing calculation
    - Template-based overlay generation
    - Text overlay generation
    """

    def __init__(
        self,
        temp_dir: Optional[Path] = None,
        assets_dir: Optional[Path] = None
    ):
        self.temp_dir = temp_dir or Path("/tmp/overlay_manager")
        self.assets_dir = assets_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.compositor = MotionGraphicsCompositor(self.temp_dir)
        self.text_gen = TextOverlayGenerator(self.temp_dir)

        self.overlay_plans: List[OverlayPlan] = []

    def analyze_segment_context(self, segment: VideoSegment) -> ContentContext:
        """
        Analyze segment text/metadata to determine content context.

        Used for intelligent overlay placement.
        """
        text_lower = segment.text.lower()

        # Check for intro/outro markers
        if segment.index == 0 or any(w in text_lower for w in ["welcome", "hello", "hi ", "hey "]):
            return ContentContext.INTRO
        if any(w in text_lower for w in ["thank", "goodbye", "subscribe", "follow", "link"]):
            return ContentContext.OUTRO

        # Check for product mentions
        if any(w in text_lower for w in ["product", "feature", "tool", "app", "software"]):
            return ContentContext.PRODUCT_SHOT

        # Check for interview/dialogue markers
        if segment.speaker:
            return ContentContext.TALKING_HEAD

        # Default to B-roll
        return ContentContext.B_ROLL

    def plan_lower_third(
        self,
        name: str,
        title: str = "",
        start_time: float = 0,
        duration: float = 5.0,
        position: OverlayPosition = OverlayPosition.LOWER_THIRD_LEFT
    ) -> OverlayPlan:
        """Plan a lower third text overlay."""
        return OverlayPlan(
            type=OverlayType.LOWER_THIRD,
            position=position,
            start_time=start_time,
            duration=duration,
            fade_in=0.4,
            fade_out=0.4,
            text_content={"name": name, "title": title}
        )

    def plan_logo_watermark(
        self,
        logo_path: Path,
        position: OverlayPosition = OverlayPosition.BOTTOM_RIGHT,
        duration: float = 0,  # 0 = entire video
        scale: float = 0.15
    ) -> OverlayPlan:
        """Plan a logo watermark overlay."""
        return OverlayPlan(
            type=OverlayType.LOGO_WATERMARK,
            source=logo_path,
            position=position,
            start_time=0,
            duration=duration,
            scale=scale,
            fade_in=0.5,
            fade_out=0.5
        )

    def plan_cta(
        self,
        text: str,
        start_time: float,
        duration: float = 4.0,
        position: OverlayPosition = OverlayPosition.BOTTOM_CENTER,
        source: Optional[Path] = None
    ) -> OverlayPlan:
        """Plan a call-to-action overlay."""
        return OverlayPlan(
            type=OverlayType.CTA,
            source=source,
            position=position,
            start_time=start_time,
            duration=duration,
            fade_in=0.3,
            fade_out=0.3,
            text_content={"text": text}
        )

    def plan_lottie_overlay(
        self,
        lottie_path: Path,
        position: OverlayPosition,
        start_time: float = 0,
        duration: float = 4.0,
        scale: float = 1.0
    ) -> OverlayPlan:
        """Plan a Lottie animation overlay."""
        return OverlayPlan(
            type=OverlayType.ACCENT,
            source=lottie_path,
            position=position,
            start_time=start_time,
            duration=duration,
            scale=scale
        )

    def auto_plan_overlays(
        self,
        segments: List[VideoSegment],
        video_duration: float,
        logo_path: Optional[Path] = None,
        cta_text: Optional[str] = None,
        include_lower_thirds: bool = True
    ) -> List[OverlayPlan]:
        """
        Automatically plan overlays based on video segments.

        Intelligent placement rules:
        - Lower thirds appear at speaker introductions
        - Logo watermark throughout (if provided)
        - CTA near the end (if provided)
        - Avoid overlapping overlays
        """
        plans = []

        # 1. Logo watermark (entire video)
        if logo_path and logo_path.exists():
            plans.append(self.plan_logo_watermark(
                logo_path,
                position=OverlayPosition.BOTTOM_RIGHT,
                duration=video_duration
            ))

        # 2. Lower thirds for speakers
        if include_lower_thirds:
            shown_speakers = set()

            for segment in segments:
                if segment.speaker and segment.speaker not in shown_speakers:
                    # Show lower third at first appearance
                    plans.append(self.plan_lower_third(
                        name=segment.speaker,
                        title=segment.speaker_title or "",
                        start_time=segment.start + 0.5,  # Slight delay
                        duration=5.0
                    ))
                    shown_speakers.add(segment.speaker)

        # 3. CTA near the end
        if cta_text:
            cta_start = max(0, video_duration - 8)  # 8 seconds from end
            plans.append(self.plan_cta(
                text=cta_text,
                start_time=cta_start,
                duration=6.0,
                position=OverlayPosition.BOTTOM_CENTER
            ))

        self.overlay_plans = plans
        return plans

    def generate_text_overlays(self) -> Dict[int, Path]:
        """Generate text-based overlays (lower thirds, CTAs) as PNGs."""
        generated = {}

        for i, plan in enumerate(self.overlay_plans):
            if plan.text_content and plan.type == OverlayType.LOWER_THIRD:
                png_path = self.text_gen.create_lower_third(
                    name=plan.text_content.get("name", ""),
                    title=plan.text_content.get("title", "")
                )
                if png_path:
                    plan.source = png_path
                    generated[i] = png_path

            elif plan.text_content and plan.type == OverlayType.CTA:
                png_path = self.text_gen.create_lower_third(
                    name=plan.text_content.get("text", ""),
                    title="",
                    bg_color="rgba(52,152,219,0.9)",  # Blue background
                    accent_color="#2ecc71"  # Green accent
                )
                if png_path:
                    plan.source = png_path
                    generated[i] = png_path

        return generated

    def apply_overlays(
        self,
        video_path: Path,
        output_path: Path,
        video_duration: float = 0
    ) -> MotionGraphicsResult:
        """
        Apply all planned overlays to video.
        """
        # Generate text overlays first
        self.generate_text_overlays()

        # Convert plans to overlay configs
        overlays = []
        for plan in self.overlay_plans:
            if not plan.source:
                continue

            # Handle duration=0 (entire video)
            duration = plan.duration if plan.duration > 0 else video_duration

            overlays.append({
                "source": str(plan.source),
                "position": plan.position.value,
                "start_time": plan.start_time,
                "duration": duration,
                "fade_in": plan.fade_in,
                "fade_out": plan.fade_out,
                "scale": plan.scale
            })

        if not overlays:
            return MotionGraphicsResult(
                success=False,
                error="No overlays to apply"
            )

        return add_motion_graphics(
            video_path,
            output_path,
            overlays,
            temp_dir=self.temp_dir
        )


def create_branded_video(
    video_path: Path,
    output_path: Path,
    logo_path: Optional[Path] = None,
    cta_text: Optional[str] = None,
    lower_thirds: Optional[List[Dict]] = None,
    lottie_overlays: Optional[List[Dict]] = None,
    match_video_colors: bool = True,
    style: DesignStyle = DesignStyle.MINIMAL
) -> MotionGraphicsResult:
    """
    Create a professionally branded video with high-quality overlays.

    Uses FFmpeg drawtext for broadcast-quality text rendering with:
    - Proper typography (clean sans-serif fonts)
    - Professional shadow effects
    - Smooth fade animations
    - Color matching to video content

    Args:
        video_path: Input video
        output_path: Output video
        logo_path: Brand logo (PNG/SVG)
        cta_text: Call-to-action text
        lower_thirds: List of {"name": "...", "title": "...", "start": 0.0}
        lottie_overlays: List of {"path": "...", "position": "...", "start": 0.0}
        match_video_colors: Extract accent colors from video
        style: Design style (MINIMAL, CORPORATE, CINEMATIC, etc.)

    Example:
        create_branded_video(
            video_path=Path("video.mp4"),
            output_path=Path("branded.mp4"),
            logo_path=Path("logo.png"),
            cta_text="Visit sumo.com",
            lower_thirds=[
                {"name": "John Smith", "title": "CEO", "start": 2.0}
            ]
        )
    """
    print(f"  [Design] Creating professionally branded video...")

    # Get video duration and dimensions
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        video_duration = float(json.loads(result.stdout)["format"]["duration"])
    except:
        video_duration = 60.0

    # Extract colors from video for design harmony
    palette = ColorPalette()
    if match_video_colors:
        try:
            extractor = ColorExtractor()
            palette = extractor.extract_from_video(video_path)
            print(f"    Extracted accent color: {palette.accent}")
        except Exception as e:
            print(f"    Color extraction skipped: {e}")

    # Use FFmpeg drawtext for professional text overlays
    text_overlays = []

    # Add lower thirds
    if lower_thirds:
        for lt in lower_thirds:
            text_overlays.append({
                "name": lt.get("name", ""),
                "title": lt.get("title", ""),
                "start": lt.get("start", 2.0),
                "duration": lt.get("duration", 5.0)
            })
            print(f"    Lower third: {lt.get('name')} @ {lt.get('start', 2.0)}s")

    # Add CTA as lower third at end
    if cta_text:
        cta_start = max(0, video_duration - 8)
        text_overlays.append({
            "name": cta_text,
            "title": "",
            "start": cta_start,
            "duration": 6.0
        })
        print(f"    CTA: {cta_text} @ {cta_start}s")

    # Apply text overlays using FFmpeg (professional quality)
    current_video = video_path

    if text_overlays:
        renderer = FFmpegTextRenderer()
        temp_output = output_path.parent / "temp_text_overlay.mp4"

        if renderer.apply_text_overlay(current_video, temp_output, text_overlays):
            current_video = temp_output
            print(f"    Applied {len(text_overlays)} text overlays")
        else:
            print("    WARNING: Text overlay failed, continuing without")

    # Apply logo watermark if provided
    if logo_path and logo_path.exists():
        manager = OverlayManager()
        manager.overlay_plans.append(
            manager.plan_logo_watermark(logo_path, duration=video_duration, scale=0.12)
        )

        # Use motion graphics compositor for logo
        result = manager.apply_overlays(current_video, output_path, video_duration)

        # Clean up temp file
        if current_video != video_path and current_video.exists():
            current_video.unlink()

        return result

    # Apply Lottie overlays if provided
    if lottie_overlays:
        overlays = []
        for lov in lottie_overlays:
            overlays.append({
                "source": lov["path"],
                "position": lov.get("position", "lower_third_left"),
                "start_time": lov.get("start", 0),
                "duration": lov.get("duration", 4.0),
                "scale": lov.get("scale", 1.0)
            })

        result = add_motion_graphics(current_video, output_path, overlays)

        # Clean up temp file
        if current_video != video_path and current_video.exists():
            current_video.unlink()

        return result

    # If only text overlays, copy to final output
    if current_video != video_path:
        import shutil
        shutil.move(str(current_video), str(output_path))

    return MotionGraphicsResult(
        success=True,
        output_path=output_path,
        duration=video_duration,
        overlays_applied=len(text_overlays)
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Overlay Manager")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("-o", "--output", required=True, help="Output video file")
    parser.add_argument("--logo", help="Logo file (PNG/SVG)")
    parser.add_argument("--cta", help="Call-to-action text")
    parser.add_argument("--lower-third", action="append", nargs=2,
                        metavar=("NAME", "TITLE"), help="Add lower third")

    args = parser.parse_args()

    lower_thirds = []
    if args.lower_third:
        for i, (name, title) in enumerate(args.lower_third):
            lower_thirds.append({
                "name": name,
                "title": title,
                "start": i * 10  # Stagger by 10 seconds
            })

    result = create_branded_video(
        video_path=Path(args.video),
        output_path=Path(args.output),
        logo_path=Path(args.logo) if args.logo else None,
        cta_text=args.cta,
        lower_thirds=lower_thirds if lower_thirds else None
    )

    if result.success:
        print(f"Success: {result.output_path}")
        print(f"Overlays applied: {result.overlays_applied}")
    else:
        print(f"Error: {result.error}")
