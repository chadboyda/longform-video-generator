#!/usr/bin/env python3
"""
Motion Graphics Engine for Video Production.

Renders Lottie animations, SVGs, and text overlays with transparency support.
Composites overlays onto video using FFmpeg with proper alpha handling.

Supported formats:
- Lottie JSON (.json) - Vector animations
- SVG (.svg) - Scalable vector graphics
- PNG sequences - Frame-by-frame animations
- WebM VP9 - Video with alpha channel

Reference: https://github.com/laggykiller/rlottie-python
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import shutil


class OverlayPosition(Enum):
    """Predefined overlay positions for common motion graphics placements."""
    # Lower thirds (bottom area)
    LOWER_THIRD_LEFT = "lower_third_left"
    LOWER_THIRD_CENTER = "lower_third_center"
    LOWER_THIRD_RIGHT = "lower_third_right"

    # Corners (for logos/watermarks)
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"

    # Center positions
    CENTER = "center"
    TOP_CENTER = "top_center"
    BOTTOM_CENTER = "bottom_center"

    # Full screen (for transitions)
    FULLSCREEN = "fullscreen"

    # Custom (x, y coordinates)
    CUSTOM = "custom"


@dataclass
class OverlayTiming:
    """Timing configuration for overlay appearance."""
    start_time: float = 0.0      # When to show (seconds)
    duration: float = 4.0        # How long to show (seconds)
    fade_in: float = 0.3         # Fade in duration (seconds)
    fade_out: float = 0.3        # Fade out duration (seconds)

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


@dataclass
class OverlayConfig:
    """Configuration for a single overlay element."""
    source: Path                           # Lottie JSON, PNG, SVG, or WebM
    position: OverlayPosition = OverlayPosition.LOWER_THIRD_LEFT
    timing: OverlayTiming = field(default_factory=OverlayTiming)
    scale: float = 1.0                     # Scale factor
    opacity: float = 1.0                   # 0.0 to 1.0
    x_offset: int = 0                      # Horizontal offset from position
    y_offset: int = 0                      # Vertical offset from position
    custom_x: Optional[int] = None         # For CUSTOM position
    custom_y: Optional[int] = None         # For CUSTOM position


@dataclass
class MotionGraphicsResult:
    """Result from motion graphics rendering/compositing."""
    success: bool
    output_path: Optional[Path] = None
    duration: float = 0.0
    overlays_applied: int = 0
    error: Optional[str] = None


class LottieRenderer:
    """
    Renders Lottie animations to PNG sequences with transparency.

    Uses rlottie-python for frame-by-frame rendering.
    Falls back to puppeteer-lottie-cli if available.
    """

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._check_dependencies()

    def _check_dependencies(self):
        """Check for available rendering backends."""
        self.has_rlottie = False
        self.has_puppeteer = False

        try:
            import rlottie_python
            self.has_rlottie = True
        except ImportError:
            pass

        # Check for puppeteer-lottie-cli
        result = subprocess.run(
            ["which", "puppeteer-lottie"],
            capture_output=True, text=True
        )
        self.has_puppeteer = result.returncode == 0

    def render_to_frames(
        self,
        lottie_path: Path,
        output_dir: Path,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: int = 30
    ) -> Dict[str, Any]:
        """
        Render Lottie animation to PNG sequence with transparency.

        Args:
            lottie_path: Path to Lottie JSON file
            output_dir: Directory for output frames
            width: Output width (auto if None)
            height: Output height (auto if None)
            fps: Frames per second

        Returns:
            Dict with frame_count, duration, frame_pattern
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.has_rlottie:
            return self._render_with_rlottie(lottie_path, output_dir, width, height, fps)
        elif self.has_puppeteer:
            return self._render_with_puppeteer(lottie_path, output_dir, width, height)
        else:
            return {"error": "No Lottie renderer available. Install rlottie-python or puppeteer-lottie-cli"}

    def _render_with_rlottie(
        self,
        lottie_path: Path,
        output_dir: Path,
        width: Optional[int],
        height: Optional[int],
        fps: int
    ) -> Dict[str, Any]:
        """Render using rlottie-python."""
        try:
            from rlottie_python import LottieAnimation
            from PIL import Image

            # Load animation
            anim = LottieAnimation.from_file(str(lottie_path))

            # Get animation properties
            total_frames = anim.lottie_animation_get_totalframe()
            anim_fps = anim.lottie_animation_get_framerate()
            duration = anim.lottie_animation_get_duration()
            anim_width, anim_height = anim.lottie_animation_get_size()

            # Use animation dimensions if not specified
            if width is None:
                width = anim_width
            if height is None:
                height = anim_height

            # Calculate frame step for target fps
            frame_step = max(1, int(anim_fps / fps))

            # Render frames
            frame_count = 0
            for i in range(0, total_frames, frame_step):
                # Render frame to buffer
                buffer = anim.lottie_animation_render(frame_num=i, width=width, height=height)

                # Convert to PIL Image (BGRA -> RGBA)
                img = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA")

                # Save with transparency
                frame_path = output_dir / f"frame_{frame_count:04d}.png"
                img.save(frame_path, "PNG")
                frame_count += 1

            return {
                "success": True,
                "frame_count": frame_count,
                "duration": duration,
                "fps": fps,
                "width": width,
                "height": height,
                "frame_pattern": str(output_dir / "frame_%04d.png")
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _render_with_puppeteer(
        self,
        lottie_path: Path,
        output_dir: Path,
        width: Optional[int],
        height: Optional[int]
    ) -> Dict[str, Any]:
        """Render using puppeteer-lottie-cli."""
        cmd = [
            "puppeteer-lottie",
            "-i", str(lottie_path),
            "-o", str(output_dir / "frame_%04d.png"),
            "-b", "transparent"
        ]

        if width:
            cmd.extend(["--width", str(width)])
        if height:
            cmd.extend(["--height", str(height)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return {"success": False, "error": result.stderr}

        # Count generated frames
        frames = list(output_dir.glob("frame_*.png"))

        return {
            "success": True,
            "frame_count": len(frames),
            "frame_pattern": str(output_dir / "frame_%04d.png")
        }

    def frames_to_webm(
        self,
        frame_pattern: str,
        output_path: Path,
        fps: int = 30,
        crf: int = 30
    ) -> bool:
        """
        Convert PNG sequence to WebM with VP9 alpha transparency.

        WebM VP9 supports alpha channel for transparent video overlays.
        """
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", frame_pattern,
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",  # Alpha channel support
            "-crf", str(crf),
            "-b:v", "0",
            "-auto-alt-ref", "0",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0


class MotionGraphicsCompositor:
    """
    Composites motion graphics overlays onto video.

    Handles:
    - Lottie animations (rendered to WebM with alpha)
    - PNG/WebM overlays with transparency
    - Position calculations for various placements
    - Timing and fade effects
    """

    # Safe margins for TV/video (percentage of frame)
    SAFE_MARGIN = 0.05  # 5% margin

    # Lower third positioning (percentage from bottom)
    LOWER_THIRD_Y = 0.15  # 15% from bottom

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.lottie_renderer = LottieRenderer(self.temp_dir)

    def get_video_dimensions(self, video_path: Path) -> Tuple[int, int]:
        """Get video width and height."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        try:
            data = json.loads(result.stdout)
            stream = data["streams"][0]
            return stream["width"], stream["height"]
        except:
            return 1920, 1080  # Default HD

    def calculate_position(
        self,
        overlay_config: OverlayConfig,
        video_width: int,
        video_height: int,
        overlay_width: int,
        overlay_height: int
    ) -> Tuple[int, int]:
        """
        Calculate overlay x, y position based on OverlayPosition.

        Returns (x, y) coordinates for ffmpeg overlay filter.
        """
        pos = overlay_config.position
        margin_x = int(video_width * self.SAFE_MARGIN)
        margin_y = int(video_height * self.SAFE_MARGIN)

        # Apply scale
        scaled_width = int(overlay_width * overlay_config.scale)
        scaled_height = int(overlay_height * overlay_config.scale)

        if pos == OverlayPosition.CUSTOM:
            x = overlay_config.custom_x or 0
            y = overlay_config.custom_y or 0

        elif pos == OverlayPosition.TOP_LEFT:
            x = margin_x
            y = margin_y

        elif pos == OverlayPosition.TOP_RIGHT:
            x = video_width - scaled_width - margin_x
            y = margin_y

        elif pos == OverlayPosition.TOP_CENTER:
            x = (video_width - scaled_width) // 2
            y = margin_y

        elif pos == OverlayPosition.BOTTOM_LEFT:
            x = margin_x
            y = video_height - scaled_height - margin_y

        elif pos == OverlayPosition.BOTTOM_RIGHT:
            x = video_width - scaled_width - margin_x
            y = video_height - scaled_height - margin_y

        elif pos == OverlayPosition.BOTTOM_CENTER:
            x = (video_width - scaled_width) // 2
            y = video_height - scaled_height - margin_y

        elif pos == OverlayPosition.CENTER:
            x = (video_width - scaled_width) // 2
            y = (video_height - scaled_height) // 2

        elif pos == OverlayPosition.LOWER_THIRD_LEFT:
            x = margin_x
            y = int(video_height * (1 - self.LOWER_THIRD_Y)) - scaled_height

        elif pos == OverlayPosition.LOWER_THIRD_CENTER:
            x = (video_width - scaled_width) // 2
            y = int(video_height * (1 - self.LOWER_THIRD_Y)) - scaled_height

        elif pos == OverlayPosition.LOWER_THIRD_RIGHT:
            x = video_width - scaled_width - margin_x
            y = int(video_height * (1 - self.LOWER_THIRD_Y)) - scaled_height

        elif pos == OverlayPosition.FULLSCREEN:
            x = 0
            y = 0

        else:
            x = margin_x
            y = video_height - scaled_height - margin_y

        # Apply offsets
        x += overlay_config.x_offset
        y += overlay_config.y_offset

        return x, y

    def prepare_overlay(
        self,
        config: OverlayConfig,
        video_width: int,
        video_height: int
    ) -> Optional[Path]:
        """
        Prepare overlay for compositing.

        - Lottie: Render to WebM with alpha
        - PNG: Use directly
        - SVG: Rasterize to PNG
        - WebM: Use directly if VP9 with alpha
        """
        source = config.source
        suffix = source.suffix.lower()

        if suffix == ".json":
            # Lottie animation - render to WebM
            frames_dir = self.temp_dir / f"lottie_frames_{source.stem}"

            # Determine target size (scale relative to video)
            target_width = int(video_width * 0.3 * config.scale)  # 30% of video width

            result = self.lottie_renderer.render_to_frames(
                source, frames_dir, width=target_width
            )

            if not result.get("success"):
                print(f"    Failed to render Lottie: {result.get('error')}")
                return None

            # Convert to WebM with alpha
            webm_path = self.temp_dir / f"{source.stem}.webm"
            if self.lottie_renderer.frames_to_webm(
                result["frame_pattern"],
                webm_path,
                fps=result.get("fps", 30)
            ):
                return webm_path
            return None

        elif suffix == ".svg":
            # SVG - rasterize to PNG with transparency
            png_path = self.temp_dir / f"{source.stem}.png"
            target_width = int(video_width * 0.2 * config.scale)

            # Use rsvg-convert or ImageMagick
            cmd = [
                "rsvg-convert",
                "-w", str(target_width),
                "-f", "png",
                "-o", str(png_path),
                str(source)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                # Fallback to ImageMagick
                cmd = [
                    "convert",
                    "-background", "none",
                    "-resize", f"{target_width}x",
                    str(source),
                    str(png_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)

            return png_path if png_path.exists() else None

        elif suffix in [".png", ".webm"]:
            # Already in usable format
            return source

        return None

    def composite_single_overlay(
        self,
        video_path: Path,
        overlay_path: Path,
        config: OverlayConfig,
        output_path: Path
    ) -> bool:
        """
        Composite a single overlay onto video.

        Handles timing, position, opacity, and fade effects.
        """
        video_width, video_height = self.get_video_dimensions(video_path)

        # Get overlay dimensions
        if overlay_path.suffix == ".webm":
            ov_width, ov_height = self.get_video_dimensions(overlay_path)
        else:
            # PNG - probe dimensions
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                str(overlay_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            try:
                data = json.loads(result.stdout)
                ov_width = data["streams"][0]["width"]
                ov_height = data["streams"][0]["height"]
            except:
                ov_width, ov_height = 400, 200

        # Calculate position
        x, y = self.calculate_position(config, video_width, video_height, ov_width, ov_height)

        # Build ffmpeg command
        timing = config.timing

        # Build filter for timing and fades
        overlay_filter = f"overlay={x}:{y}"

        # Add enable condition for timing
        if timing.start_time > 0 or timing.duration > 0:
            overlay_filter += f":enable='between(t,{timing.start_time},{timing.end_time})'"

        # For static PNG, we need to loop it
        if overlay_path.suffix == ".png":
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-loop", "1", "-t", str(timing.duration),
                "-i", str(overlay_path),
                "-filter_complex",
                f"[1:v]format=rgba,fade=t=in:st=0:d={timing.fade_in}:alpha=1,"
                f"fade=t=out:st={timing.duration - timing.fade_out}:d={timing.fade_out}:alpha=1[ov];"
                f"[0:v][ov]{overlay_filter}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy",
                str(output_path)
            ]
        else:
            # WebM/video with alpha - CRITICAL: video must continue after overlay ends
            #
            # Key approach:
            # 1. Loop overlay infinitely (-stream_loop -1) so it never runs out
            # 2. Trim overlay to exact duration in filter graph
            # 3. Use eof_action=pass so main video continues if overlay somehow ends
            # 4. Use enable='between(...)' to control visibility timing
            # 5. NO -shortest flag or shortest=1 option

            # Build overlay filter with:
            # - x,y position
            # - eof_action=pass (continue main video if overlay ends)
            # - enable timing (show only during specified window)
            timed_overlay = (
                f"overlay={x}:{y}"
                f":eof_action=pass"  # CRITICAL: continue main video when overlay ends
                f":enable='between(t,{timing.start_time},{timing.end_time})'"
            )

            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-stream_loop", "-1",              # Loop overlay infinitely
                "-c:v", "libvpx-vp9",              # VP9 decoder for alpha
                "-i", str(overlay_path),
                "-filter_complex",
                # Process overlay: format, trim to duration, reset PTS, add fades
                f"[1:v]format=rgba,"
                f"trim=duration={timing.duration},"
                f"setpts=PTS-STARTPTS,"
                f"fade=t=in:st=0:d={timing.fade_in}:alpha=1,"
                f"fade=t=out:st={timing.duration - timing.fade_out}:d={timing.fade_out}:alpha=1[ov];"
                # Composite: main video continues, overlay appears during window
                f"[0:v][ov]{timed_overlay}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy",
                # NO -shortest flag here - main video length determines output
                str(output_path)
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    Overlay error: {result.stderr[:200]}")

        return result.returncode == 0

    def composite_overlays(
        self,
        video_path: Path,
        overlays: List[OverlayConfig],
        output_path: Path
    ) -> MotionGraphicsResult:
        """
        Composite multiple overlays onto video.

        Applies overlays sequentially, each building on the previous.
        """
        if not overlays:
            return MotionGraphicsResult(
                success=False,
                error="No overlays provided"
            )

        video_width, video_height = self.get_video_dimensions(video_path)
        print(f"  [MotionGraphics] Video: {video_width}x{video_height}")
        print(f"  [MotionGraphics] Applying {len(overlays)} overlays...")

        current_video = video_path
        applied_count = 0

        for i, config in enumerate(overlays):
            print(f"    Overlay {i+1}: {config.source.name} @ {config.position.value}")

            # Prepare overlay (render Lottie, etc.)
            prepared = self.prepare_overlay(config, video_width, video_height)
            if not prepared:
                print(f"    WARNING: Failed to prepare overlay {config.source}")
                continue

            # Composite
            if i == len(overlays) - 1:
                # Last overlay - output to final path
                out = output_path
            else:
                # Intermediate - output to temp
                out = self.temp_dir / f"composite_{i:02d}.mp4"

            if self.composite_single_overlay(current_video, prepared, config, out):
                applied_count += 1
                current_video = out
            else:
                print(f"    WARNING: Failed to composite overlay {i+1}")

        # If no overlays were applied, copy original
        if applied_count == 0:
            shutil.copy(video_path, output_path)

        # Get final duration
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            duration = float(json.loads(result.stdout)["format"]["duration"])
        except:
            duration = 0

        return MotionGraphicsResult(
            success=True,
            output_path=output_path,
            duration=duration,
            overlays_applied=applied_count
        )


class TextOverlayGenerator:
    """
    Generates text-based overlays for lower thirds, titles, and captions.

    Creates PNG images with text that can be composited onto video.
    """

    # Default styling
    DEFAULT_FONT = "Arial"
    DEFAULT_SIZE = 48
    DEFAULT_COLOR = "white"
    DEFAULT_BG_COLOR = "rgba(0,0,0,0.7)"

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def create_lower_third(
        self,
        name: str,
        title: str = "",
        output_path: Optional[Path] = None,
        width: int = 600,
        height: int = 120,
        font: str = DEFAULT_FONT,
        name_size: int = 48,
        title_size: int = 32,
        text_color: str = DEFAULT_COLOR,
        bg_color: str = DEFAULT_BG_COLOR,
        accent_color: str = "#3498db"
    ) -> Path:
        """
        Create a lower third text overlay PNG.

        Format:
        ┌─────────────────────────┐
        │ ▌ Name                  │
        │ ▌ Title/Description     │
        └─────────────────────────┘
        """
        output = output_path or self.temp_dir / f"lower_third_{name.replace(' ', '_')}.png"

        # Use ImageMagick to create
        # Two-tier lower third with accent bar
        cmd = [
            "convert",
            "-size", f"{width}x{height}",
            f"xc:{bg_color}",
            # Accent bar on left
            "-fill", accent_color,
            "-draw", f"rectangle 0,0 8,{height}",
            # Name text
            "-font", font,
            "-pointsize", str(name_size),
            "-fill", text_color,
            "-gravity", "NorthWest",
            "-annotate", "+20+15", name,
        ]

        if title:
            cmd.extend([
                "-pointsize", str(title_size),
                "-fill", "rgba(255,255,255,0.8)",
                "-annotate", f"+20+{15 + name_size + 5}", title,
            ])

        cmd.append(str(output))

        result = subprocess.run(cmd, capture_output=True, text=True)

        return output if output.exists() else None

    def create_title_card(
        self,
        text: str,
        output_path: Optional[Path] = None,
        width: int = 1920,
        height: int = 1080,
        font: str = DEFAULT_FONT,
        font_size: int = 72,
        text_color: str = DEFAULT_COLOR,
        bg_color: str = "transparent"
    ) -> Path:
        """Create a centered title card."""
        output = output_path or self.temp_dir / f"title_{text[:20].replace(' ', '_')}.png"

        cmd = [
            "convert",
            "-size", f"{width}x{height}",
            f"xc:{bg_color}",
            "-font", font,
            "-pointsize", str(font_size),
            "-fill", text_color,
            "-gravity", "Center",
            "-annotate", "+0+0", text,
            str(output)
        ]

        subprocess.run(cmd, capture_output=True)
        return output if output.exists() else None


def add_motion_graphics(
    video_path: Path,
    output_path: Path,
    overlays: List[Dict[str, Any]],
    temp_dir: Optional[Path] = None
) -> MotionGraphicsResult:
    """
    Convenience function to add motion graphics to a video.

    Args:
        video_path: Input video
        output_path: Output video with overlays
        overlays: List of overlay configs as dicts:
            {
                "source": "/path/to/overlay.json",  # Lottie, PNG, SVG, or WebM
                "position": "lower_third_left",     # See OverlayPosition
                "start_time": 2.0,
                "duration": 5.0,
                "fade_in": 0.5,
                "fade_out": 0.5,
                "scale": 1.0,
                "opacity": 1.0
            }
    """
    compositor = MotionGraphicsCompositor(temp_dir)

    configs = []
    for ov in overlays:
        timing = OverlayTiming(
            start_time=ov.get("start_time", 0),
            duration=ov.get("duration", 4),
            fade_in=ov.get("fade_in", 0.3),
            fade_out=ov.get("fade_out", 0.3)
        )

        config = OverlayConfig(
            source=Path(ov["source"]),
            position=OverlayPosition(ov.get("position", "lower_third_left")),
            timing=timing,
            scale=ov.get("scale", 1.0),
            opacity=ov.get("opacity", 1.0),
            x_offset=ov.get("x_offset", 0),
            y_offset=ov.get("y_offset", 0),
            custom_x=ov.get("x"),
            custom_y=ov.get("y")
        )
        configs.append(config)

    return compositor.composite_overlays(video_path, configs, output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Motion Graphics Compositor")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("-o", "--output", required=True, help="Output video file")
    parser.add_argument("--overlay", action="append", help="Overlay file (Lottie JSON, PNG, SVG, WebM)")
    parser.add_argument("--position", default="lower_third_left", help="Overlay position")
    parser.add_argument("--start", type=float, default=0, help="Start time in seconds")
    parser.add_argument("--duration", type=float, default=4, help="Duration in seconds")

    args = parser.parse_args()

    if args.overlay:
        overlays = []
        for ov in args.overlay:
            overlays.append({
                "source": ov,
                "position": args.position,
                "start_time": args.start,
                "duration": args.duration
            })

        result = add_motion_graphics(
            Path(args.video),
            Path(args.output),
            overlays
        )

        if result.success:
            print(f"Success: {result.output_path}")
            print(f"Overlays applied: {result.overlays_applied}")
        else:
            print(f"Error: {result.error}")
