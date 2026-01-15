#!/usr/bin/env python3
"""
Professional Design System for Motion Graphics.

Implements broadcast-quality typography, color extraction, and overlay design
following industry best practices for video production.

References:
- https://blog.frame.io/2017/12/04/create-lower-thirds-titles-that-dont-suck/
- https://riverside.fm/blog/lower-thirds
- https://www.numberanalytics.com/blog/art-lower-thirds-motion-graphics-guide

Design Philosophy:
- Clean, minimal aesthetics (current trend)
- High contrast for readability
- Proper typography hierarchy
- Color harmony with video content
- Subtle, professional animations
"""

import os
import subprocess
import json
import requests
import colorsys
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import tempfile

# Try to import image processing libraries
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import numpy as np
    from sklearn.cluster import KMeans
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class DesignStyle(Enum):
    """Pre-defined design styles for different use cases."""
    MINIMAL = "minimal"           # Clean, white text, subtle shadow
    CORPORATE = "corporate"       # Professional, brand colors
    CREATIVE = "creative"         # Bold, colorful
    CINEMATIC = "cinematic"       # Film-style, elegant
    TECH = "tech"                 # Modern, gradient accents
    NEWS = "news"                 # Traditional broadcast style


@dataclass
class ColorPalette:
    """Extracted or defined color palette for design harmony."""
    primary: str = "#FFFFFF"      # Main text color
    secondary: str = "#B0B0B0"    # Subtitle/secondary text
    accent: str = "#3498db"       # Highlight/accent color
    background: str = "#000000"   # Background (often transparent)
    shadow: str = "#000000"       # Shadow color

    # Extracted from video
    dominant: List[str] = field(default_factory=list)

    @classmethod
    def from_hex(cls, hex_color: str) -> 'ColorPalette':
        """Generate a harmonious palette from a single accent color."""
        # Parse hex
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16)

        # Convert to HSV for manipulation
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)

        # Generate complementary colors
        def hsv_to_hex(h, s, v):
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

        return cls(
            primary="#FFFFFF",
            secondary="#CCCCCC",
            accent=f"#{hex_color}",
            background="rgba(0,0,0,0.7)",
            shadow="#000000"
        )


@dataclass
class Typography:
    """Typography settings for professional text rendering."""
    # Font families (in order of preference)
    primary_font: str = "Inter"
    fallback_fonts: List[str] = field(default_factory=lambda: [
        "SF Pro Display", "Helvetica Neue", "Arial", "sans-serif"
    ])

    # Sizes (in pixels for 1080p)
    name_size: int = 54           # Primary name/title
    title_size: int = 36          # Secondary title/role
    caption_size: int = 28        # Small text/captions

    # Weights
    name_weight: str = "600"      # Semi-bold for names
    title_weight: str = "400"     # Regular for titles

    # Spacing (CSS-like values)
    letter_spacing: float = 0.02  # 2% of font size
    line_height: float = 1.3      # 130% of font size

    # Effects
    shadow_offset: Tuple[int, int] = (2, 2)
    shadow_blur: int = 4
    shadow_opacity: float = 0.5


@dataclass
class LowerThirdDesign:
    """Complete design specification for a lower third."""
    # Content
    name: str = ""
    title: str = ""

    # Dimensions (relative to 1080p)
    width: int = 600
    height: int = 100
    padding: int = 20

    # Accent bar
    accent_bar_width: int = 4
    accent_bar_visible: bool = True

    # Background
    background_opacity: float = 0.0  # 0 = transparent, 1 = solid
    background_blur: int = 0         # Blur radius for frosted glass effect

    # Colors
    palette: ColorPalette = field(default_factory=ColorPalette)

    # Typography
    typography: Typography = field(default_factory=Typography)

    # Animation (for reference)
    animation_style: str = "slide_fade"  # slide_fade, fade, slide, typewriter


class ColorExtractor:
    """
    Extracts dominant colors from video frames for design harmony.

    Uses K-means clustering to find the most prominent colors.
    Reference: https://medium.com/@isami.dono/extract-dominant-color-of-each-frame
    """

    def __init__(self, n_colors: int = 5):
        self.n_colors = n_colors

    def extract_frame(self, video_path: Path, timestamp: float = 5.0) -> Optional[Path]:
        """Extract a single frame from video at given timestamp."""
        temp_frame = Path(tempfile.mktemp(suffix=".png"))

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(temp_frame)
        ]

        result = subprocess.run(cmd, capture_output=True)
        return temp_frame if temp_frame.exists() else None

    def extract_colors(self, image_path: Path) -> List[str]:
        """Extract dominant colors from an image using K-means."""
        if not HAS_PIL or not HAS_SKLEARN:
            return ["#FFFFFF", "#000000", "#3498db"]

        try:
            img = Image.open(image_path)
            img = img.convert("RGB")

            # Resize for faster processing
            img.thumbnail((200, 200))

            # Convert to numpy array
            pixels = np.array(img).reshape(-1, 3)

            # Remove very dark pixels (letterboxing)
            mask = np.sum(pixels, axis=1) > 30
            pixels = pixels[mask]

            if len(pixels) < self.n_colors:
                return ["#FFFFFF", "#000000", "#3498db"]

            # K-means clustering
            kmeans = KMeans(n_clusters=self.n_colors, random_state=42, n_init=10)
            kmeans.fit(pixels)

            # Get cluster centers and sort by frequency
            colors = kmeans.cluster_centers_.astype(int)
            labels, counts = np.unique(kmeans.labels_, return_counts=True)
            sorted_idx = np.argsort(-counts)

            # Convert to hex
            hex_colors = []
            for idx in sorted_idx:
                r, g, b = colors[idx]
                hex_colors.append(f"#{r:02x}{g:02x}{b:02x}")

            return hex_colors

        except Exception as e:
            print(f"    Color extraction error: {e}")
            return ["#FFFFFF", "#000000", "#3498db"]

    def extract_from_video(
        self,
        video_path: Path,
        timestamps: List[float] = None
    ) -> ColorPalette:
        """Extract color palette from multiple video frames."""
        if timestamps is None:
            timestamps = [5.0, 15.0, 30.0]

        all_colors = []

        for ts in timestamps:
            frame = self.extract_frame(video_path, ts)
            if frame:
                colors = self.extract_colors(frame)
                all_colors.extend(colors)
                frame.unlink()  # Clean up

        # Find most common colors
        if not all_colors:
            return ColorPalette()

        # Simple frequency count
        color_counts = {}
        for c in all_colors:
            color_counts[c] = color_counts.get(c, 0) + 1

        sorted_colors = sorted(color_counts.keys(), key=lambda x: -color_counts[x])

        # Choose accent from mid-range brightness (not too dark, not too white)
        accent = "#3498db"
        for c in sorted_colors:
            hex_val = c.lstrip('#')
            r, g, b = int(hex_val[:2], 16), int(hex_val[2:4], 16), int(hex_val[4:], 16)
            brightness = (r + g + b) / 3
            if 60 < brightness < 200:  # Mid-range
                accent = c
                break

        return ColorPalette(
            primary="#FFFFFF",
            secondary="#CCCCCC",
            accent=accent,
            dominant=sorted_colors[:5]
        )


class ProfessionalTextRenderer:
    """
    Renders broadcast-quality text overlays using Pillow.

    Features:
    - Proper font loading with fallbacks
    - Letter spacing and kerning
    - Professional shadow effects
    - Clean anti-aliasing
    """

    # System font locations
    FONT_PATHS = {
        "darwin": [
            "/System/Library/Fonts",
            "/Library/Fonts",
            "~/Library/Fonts"
        ],
        "linux": [
            "/usr/share/fonts",
            "~/.fonts",
            "~/.local/share/fonts"
        ]
    }

    # Preferred fonts in order
    PREFERRED_FONTS = [
        "Inter-SemiBold.otf", "Inter-Medium.otf", "Inter-Regular.otf",
        "SF-Pro-Display-Semibold.otf", "SF-Pro-Display-Medium.otf",
        "Montserrat-SemiBold.ttf", "Montserrat-Medium.ttf",
        "HelveticaNeue-Medium.otf", "HelveticaNeue.otf",
        "Arial Bold.ttf", "Arial.ttf"
    ]

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.font_cache = {}

    def find_font(self, preferred: List[str] = None) -> Optional[str]:
        """Find the best available font."""
        import platform
        system = platform.system().lower()

        search_paths = self.FONT_PATHS.get(system, self.FONT_PATHS["linux"])
        fonts_to_try = preferred or self.PREFERRED_FONTS

        for font_name in fonts_to_try:
            for base_path in search_paths:
                base = Path(base_path).expanduser()
                if not base.exists():
                    continue

                # Search recursively
                for font_path in base.rglob(font_name):
                    return str(font_path)

        return None

    def load_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Load font with caching."""
        cache_key = (size, bold)
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]

        font_path = self.find_font()

        try:
            if font_path:
                font = ImageFont.truetype(font_path, size)
            else:
                # Fallback to default
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        self.font_cache[cache_key] = font
        return font

    def render_lower_third(
        self,
        design: LowerThirdDesign,
        output_path: Optional[Path] = None,
        scale: float = 1.0
    ) -> Path:
        """
        Render a professional lower third PNG with transparency.

        Design follows broadcast industry best practices:
        - Clean typography hierarchy
        - Subtle shadow for readability
        - Minimal accent bar
        - Proper spacing
        """
        if not HAS_PIL:
            raise RuntimeError("Pillow required for text rendering")

        # Scale dimensions
        width = int(design.width * scale)
        height = int(design.height * scale)
        padding = int(design.padding * scale)
        bar_width = int(design.accent_bar_width * scale)

        # Create image with transparency
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Optional semi-transparent background
        if design.background_opacity > 0:
            bg_alpha = int(design.background_opacity * 255)
            bg_color = (0, 0, 0, bg_alpha)
            draw.rectangle([0, 0, width, height], fill=bg_color)

        # Accent bar
        if design.accent_bar_visible:
            accent_hex = design.palette.accent.lstrip('#')
            accent_rgb = tuple(int(accent_hex[i:i+2], 16) for i in (0, 2, 4))
            draw.rectangle([0, 0, bar_width, height], fill=(*accent_rgb, 255))

        # Load fonts
        name_size = int(design.typography.name_size * scale)
        title_size = int(design.typography.title_size * scale)

        name_font = self.load_font(name_size, bold=True)
        title_font = self.load_font(title_size, bold=False)

        # Calculate positions
        text_x = bar_width + padding if design.accent_bar_visible else padding

        # Parse colors
        primary_hex = design.palette.primary.lstrip('#')
        primary_rgb = tuple(int(primary_hex[i:i+2], 16) for i in (0, 2, 4))

        secondary_hex = design.palette.secondary.lstrip('#')
        secondary_rgb = tuple(int(secondary_hex[i:i+2], 16) for i in (0, 2, 4))

        shadow_hex = design.palette.shadow.lstrip('#')
        shadow_rgb = tuple(int(shadow_hex[i:i+2], 16) for i in (0, 2, 4))

        # Draw name with shadow
        if design.name:
            name_y = padding
            shadow_offset = design.typography.shadow_offset
            shadow_alpha = int(design.typography.shadow_opacity * 255)

            # Shadow
            draw.text(
                (text_x + shadow_offset[0], name_y + shadow_offset[1]),
                design.name,
                font=name_font,
                fill=(*shadow_rgb, shadow_alpha)
            )

            # Main text
            draw.text(
                (text_x, name_y),
                design.name,
                font=name_font,
                fill=(*primary_rgb, 255)
            )

        # Draw title
        if design.title:
            title_y = padding + name_size + int(8 * scale)

            # Shadow
            draw.text(
                (text_x + 1, title_y + 1),
                design.title,
                font=title_font,
                fill=(*shadow_rgb, int(shadow_alpha * 0.7))
            )

            # Main text (slightly dimmer)
            draw.text(
                (text_x, title_y),
                design.title,
                font=title_font,
                fill=(*secondary_rgb, 230)
            )

        # Save
        output = output_path or self.temp_dir / f"lt_{design.name.replace(' ', '_')}.png"
        img.save(output, "PNG")

        return output


class LottieLibrary:
    """
    Fetches and manages Lottie animations from online sources.

    Sources:
    - LottieFiles (https://lottiefiles.com)
    - IconScout (https://iconscout.com/lottie-animations)
    - Local asset library

    Reference: https://cssauthor.com/the-ultimate-list-of-websites-for-free-lottie-animations-download/
    """

    # Curated high-quality Lottie URLs from LottieFiles (verified working)
    CURATED_ANIMATIONS = {
        # Subscribe/CTA buttons
        "subscribe_youtube": "https://assets-v2.lottiefiles.com/a/037147aa-117f-11ee-8487-7ba41981a936/uq2rgrXLUL.json",
        "subscribe_red": "https://assets-v2.lottiefiles.com/a/80865912-1164-11ee-80af-fb2235360c72/qsrnf5uEOZ.json",
        "subscribe_bell": "https://assets-v2.lottiefiles.com/a/efecc80c-e86b-11ee-8af9-973287bbafde/dmSyL867Xu.json",
        "newsletter": "https://assets-v2.lottiefiles.com/a/eb14757a-ed05-11ee-a193-47b6febf7c5f/ayYRj4FKDR.json",

        # Arrows and pointers
        "arrow_right": "https://assets-v2.lottiefiles.com/a/a64d3426-1151-11ee-b280-d3b7a105dcaf/lzv6cGCF5G.json",
        "arrow_right_hand": "https://assets-v2.lottiefiles.com/a/4d364ba8-1173-11ee-9ca0-fb847ee4a934/DYoMdn7ap7.json",
        "arrow_down": "https://assets-v2.lottiefiles.com/a/fc9429da-1173-11ee-b299-b3cef6cc0893/D4UYtTUw6Q.json",
        "scroll_down": "https://assets-v2.lottiefiles.com/a/ee61466a-1176-11ee-b52b-a7ae2a1b3732/ZAgKLik9rw.json",
        "swipe_up": "https://assets-v2.lottiefiles.com/a/c967be44-1152-11ee-b415-2f56a9747014/qJjmNnAhi6.json",

        # Logo animations
        "logo_wave": "https://assets-v2.lottiefiles.com/a/888a7040-1177-11ee-842f-034cc33f6d3d/x5jr6RkJDn.json",
        "logo_teal": "https://assets-v2.lottiefiles.com/a/f54f560e-845a-11ee-8614-4feeace234b5/tM7nAr4BMJ.json",

        # UI elements
        "loading": "https://assets-v2.lottiefiles.com/a/d35e7bbc-1176-11ee-bf08-7b25604dc165/Zp0IWKxNlO.json",
        "chatbot": "https://assets-v2.lottiefiles.com/a/fe807c20-1183-11ee-a7e0-738836ffd98a/aE4Voe86g6.json",
        "profile_icon": "https://assets-v2.lottiefiles.com/a/27103524-3ee9-11f0-89a9-a310fdeaaccb/TKVyi3NmZh.json",
        "crown": "https://assets-v2.lottiefiles.com/a/8c540c4a-ccf1-11ef-8842-0b55f9dd5fdb/kf1zhMyQI1.json",

        # Social
        "instagram_logo": "https://assets-v2.lottiefiles.com/a/7e98032e-1166-11ee-a12e-2b7a0144675a/h0CmZfsNDo.json",
        "cat_purple": "https://assets-v2.lottiefiles.com/a/a7db4a66-da60-11ee-bc26-1f019c3d2af2/i9bQqEgDM7.json",
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "lottie_library"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_animation(self, url: str, name: str = None) -> Optional[Path]:
        """Download a Lottie animation and cache it locally."""
        if not name:
            name = url.split('/')[-1].replace('.json', '')

        cache_path = self.cache_dir / f"{name}.json"

        # Check cache
        if cache_path.exists():
            return cache_path

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Validate it's JSON
            data = response.json()

            # Save to cache
            with open(cache_path, 'w') as f:
                json.dump(data, f)

            return cache_path

        except Exception as e:
            print(f"    Failed to fetch Lottie: {e}")
            return None

    def get_curated(self, animation_type: str) -> Optional[Path]:
        """Get a curated animation by type."""
        url = self.CURATED_ANIMATIONS.get(animation_type)
        if url:
            return self.fetch_animation(url, animation_type)
        return None

    def list_cached(self) -> List[Path]:
        """List all cached animations."""
        return list(self.cache_dir.glob("*.json"))


class FFmpegTextRenderer:
    """
    Renders text directly onto video using FFmpeg drawtext.

    Advantages:
    - No intermediate files
    - Proper font rendering
    - Built-in animation support
    """

    def __init__(self):
        pass

    def create_lower_third_filter(
        self,
        name: str,
        title: str = "",
        position: str = "lower_third_left",
        start_time: float = 0,
        duration: float = 5,
        font: str = "Arial",
        video_width: int = 1920,
        video_height: int = 1080
    ) -> str:
        """
        Generate FFmpeg drawtext filter for a lower third.

        Includes:
        - Fade in/out animation
        - Shadow for readability
        - Proper positioning
        """
        # Calculate positions (5% safe margin)
        margin = int(video_width * 0.05)
        y_position = int(video_height * 0.82)  # Lower third position

        # Font sizes relative to video height
        name_size = int(video_height * 0.05)   # ~54px at 1080p
        title_size = int(video_height * 0.033) # ~36px at 1080p

        # Escape special characters
        name_escaped = name.replace("'", "\\'").replace(":", "\\:")
        title_escaped = title.replace("'", "\\'").replace(":", "\\:")

        # Animation timing
        fade_duration = 0.4
        end_time = start_time + duration

        # Build filter for name
        name_filter = (
            f"drawtext=text='{name_escaped}':"
            f"fontfile=/System/Library/Fonts/Helvetica.ttc:"
            f"fontsize={name_size}:"
            f"fontcolor=white:"
            f"shadowcolor=black@0.6:"
            f"shadowx=2:shadowy=2:"
            f"x={margin}:y={y_position}:"
            f"enable='between(t,{start_time},{end_time})':"
            f"alpha='if(lt(t,{start_time + fade_duration}),(t-{start_time})/{fade_duration},"
            f"if(gt(t,{end_time - fade_duration}),({end_time}-t)/{fade_duration},1))'"
        )

        # Add title if provided
        if title:
            title_y = y_position + name_size + 8
            title_filter = (
                f",drawtext=text='{title_escaped}':"
                f"fontfile=/System/Library/Fonts/Helvetica.ttc:"
                f"fontsize={title_size}:"
                f"fontcolor=white@0.85:"
                f"shadowcolor=black@0.4:"
                f"shadowx=1:shadowy=1:"
                f"x={margin}:y={title_y}:"
                f"enable='between(t,{start_time},{end_time})':"
                f"alpha='if(lt(t,{start_time + fade_duration}),(t-{start_time})/{fade_duration},"
                f"if(gt(t,{end_time - fade_duration}),({end_time}-t)/{fade_duration},1))'"
            )
            return name_filter + title_filter

        return name_filter

    def apply_text_overlay(
        self,
        video_path: Path,
        output_path: Path,
        overlays: List[Dict]
    ) -> bool:
        """
        Apply multiple text overlays to video.

        overlays: [{"name": "...", "title": "...", "start": 0, "duration": 5}, ...]
        """
        # Get video dimensions
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(video_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)

        try:
            data = json.loads(result.stdout)
            width = data["streams"][0]["width"]
            height = data["streams"][0]["height"]
        except:
            width, height = 1920, 1080

        # Build filter chain
        filters = []
        for ov in overlays:
            f = self.create_lower_third_filter(
                name=ov.get("name", ""),
                title=ov.get("title", ""),
                start_time=ov.get("start", 0),
                duration=ov.get("duration", 5),
                video_width=width,
                video_height=height
            )
            filters.append(f)

        filter_chain = ",".join(filters)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", filter_chain,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    FFmpeg error: {result.stderr[:200]}")

        return result.returncode == 0


def create_professional_lower_third(
    video_path: Path,
    output_path: Path,
    name: str,
    title: str = "",
    start_time: float = 2.0,
    duration: float = 5.0,
    match_video_colors: bool = True,
    style: DesignStyle = DesignStyle.MINIMAL
) -> bool:
    """
    Create a single professional lower third on video.

    Uses FFmpeg drawtext for clean, efficient rendering.
    """
    renderer = FFmpegTextRenderer()

    return renderer.apply_text_overlay(
        video_path,
        output_path,
        [{"name": name, "title": title, "start": start_time, "duration": duration}]
    )


if __name__ == "__main__":
    # Test color extraction
    import sys

    if len(sys.argv) > 1:
        video = Path(sys.argv[1])

        print("Extracting colors from video...")
        extractor = ColorExtractor()
        palette = extractor.extract_from_video(video)

        print(f"Dominant colors: {palette.dominant}")
        print(f"Suggested accent: {palette.accent}")

        # Test text rendering
        if HAS_PIL:
            print("\nRendering test lower third...")
            renderer = ProfessionalTextRenderer()

            design = LowerThirdDesign(
                name="John Smith",
                title="CEO & Founder",
                palette=palette
            )

            output = renderer.render_lower_third(design)
            print(f"Output: {output}")
