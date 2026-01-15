#!/usr/bin/env python3
"""
Aesthetic System for Video Production.
Defines comprehensive visual treatment parameters that get incorporated into all prompts.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class FilmStock(Enum):
    """Film stock emulations for consistent visual feel"""
    KODAK_PORTRA_400 = "Kodak Portra 400 film emulation, warm skin tones, soft pastels, gentle contrast"
    KODAK_PORTRA_800 = "Kodak Portra 800 film emulation, warmer tones, slightly more grain, dreamy"
    FUJI_PRO_400H = "Fuji Pro 400H film emulation, cooler greens, muted tones, soft highlights"
    KODAK_EKTAR_100 = "Kodak Ektar 100 film emulation, vivid saturated colors, fine grain, punchy"
    CINESTILL_800T = "CineStill 800T film emulation, tungsten balanced, halation around highlights, cinematic"
    KODAK_VISION3_500T = "Kodak Vision3 500T cinema film, balanced colors, rich shadows, professional"
    ARRI_ALEXA_LOG = "ARRI Alexa Log-C look, wide dynamic range, natural skin tones, filmic"


class LensCharacter(Enum):
    """Lens characteristics that affect the visual feel"""
    VINTAGE_COOKE = "vintage Cooke lens, soft focus edges, warm flare, gentle bokeh swirl"
    ZEISS_MASTER_PRIME = "Zeiss Master Prime, clinical sharpness, neutral rendering, perfect bokeh"
    PANAVISION_PRIMO = "Panavision Primo lens, cinematic flare, natural skin tones, creamy bokeh"
    LEICA_SUMMILUX = "Leica Summilux lens, dreamy wide open, sharp stopped down, smooth bokeh"
    CANON_K35 = "Canon K35 vintage lens, warm organic look, subtle chromatic aberration, character"
    HELIOS_44 = "Helios 44 lens, distinctive swirly bokeh, vintage Soviet character, dreamy"


class LightingStyle(Enum):
    """Lighting setups and moods"""
    GOLDEN_HOUR = "golden hour natural light, warm sun at 15-degree angle, soft shadows, magical"
    SOFT_WINDOW = "soft diffused window light, large source, gentle wraparound, flattering"
    PRACTICAL_WARM = "practical warm lighting, desk lamps, warm bulbs, cozy intimate feel"
    FILM_NOIR = "film noir lighting, high contrast, dramatic shadows, single hard source"
    MODERN_NATURAL = "modern natural light, bright airy, fill bounce, contemporary clean"
    MAGIC_HOUR = "magic hour twilight, mixed warm and cool, neon reflections, cinematic"
    REMBRANDT = "Rembrandt lighting, triangle on cheek, dramatic but beautiful, portrait"


class ColorGrade(Enum):
    """Color grading treatments"""
    WARM_NOSTALGIC = "warm nostalgic grade, lifted blacks, orange shadows, teal highlights, memory feel"
    CLEAN_MODERN = "clean modern grade, neutral whites, subtle contrast, contemporary"
    TEAL_ORANGE = "teal and orange cinematic grade, complementary contrast, blockbuster look"
    PASTEL_SOFT = "soft pastel grade, desaturated colors, lifted shadows, dreamy ethereal"
    RICH_FILMIC = "rich filmic grade, deep blacks, saturated mids, creamy highlights"
    VINTAGE_WARM = "vintage warm grade, faded blacks, amber cast, 70s nostalgia"


@dataclass
class VisualAesthetic:
    """
    Complete visual aesthetic definition for a video project.
    This gets incorporated into every image and video prompt.
    """
    name: str
    description: str

    # Film and Camera
    film_stock: FilmStock = FilmStock.KODAK_PORTRA_400
    lens_character: LensCharacter = LensCharacter.VINTAGE_COOKE
    focal_length: str = "50mm"  # Primary focal length
    aperture: str = "f/2.0"  # Primary aperture for depth of field

    # Lighting
    lighting_style: LightingStyle = LightingStyle.SOFT_WINDOW
    key_light_direction: str = "45 degrees camera left"
    lighting_ratio: str = "2:1"  # Key to fill ratio

    # Color
    color_grade: ColorGrade = ColorGrade.WARM_NOSTALGIC
    primary_colors: List[str] = field(default_factory=lambda: ["warm amber", "soft cream", "muted teal"])
    accent_colors: List[str] = field(default_factory=lambda: ["golden yellow", "dusty rose"])

    # Texture
    film_grain: str = "subtle fine grain"  # none, subtle, moderate, heavy
    grain_intensity: float = 0.3  # 0-1

    # Additional style notes
    highlights: str = "soft creamy rolloff"
    shadows: str = "lifted with warm tones"
    contrast: str = "medium-low, gentle"
    saturation: str = "slightly muted, natural"

    # Camera movement tendencies
    movement_style: str = "smooth, deliberate, motivated"
    preferred_shots: List[str] = field(default_factory=lambda: ["medium close-up", "close-up", "over-shoulder"])

    def to_prompt_suffix(self) -> str:
        """Generate a prompt suffix that captures the aesthetic"""
        parts = [
            self.film_stock.value,
            self.lens_character.value,
            f"shot at {self.focal_length} {self.aperture}",
            self.lighting_style.value,
            self.color_grade.value,
            f"{self.film_grain}, {self.highlights}, {self.shadows}",
            f"colors: {', '.join(self.primary_colors)}"
        ]
        return ". ".join(parts)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "film_stock": self.film_stock.name,
            "lens_character": self.lens_character.name,
            "focal_length": self.focal_length,
            "aperture": self.aperture,
            "lighting_style": self.lighting_style.name,
            "color_grade": self.color_grade.name,
            "primary_colors": self.primary_colors,
            "film_grain": self.film_grain,
            "prompt_suffix": self.to_prompt_suffix()
        }


# Pre-defined aesthetics for common styles
AESTHETICS = {
    "nostalgic_warm": VisualAesthetic(
        name="Nostalgic Warm",
        description="Warm, inviting, feel-good aesthetic with vintage film quality",
        film_stock=FilmStock.KODAK_PORTRA_400,
        lens_character=LensCharacter.VINTAGE_COOKE,
        focal_length="85mm",
        aperture="f/1.8",
        lighting_style=LightingStyle.GOLDEN_HOUR,
        color_grade=ColorGrade.WARM_NOSTALGIC,
        primary_colors=["warm amber", "soft cream", "honey gold"],
        accent_colors=["dusty rose", "sage green"],
        film_grain="subtle organic grain",
        highlights="soft blooming highlights",
        shadows="lifted warm shadows, never crushed",
        contrast="low-medium, gentle transitions",
        saturation="natural, slightly warm-shifted",
        movement_style="slow, deliberate, contemplative",
        preferred_shots=["medium close-up", "close-up with shallow DOF", "intimate two-shot"]
    ),

    "clean_modern": VisualAesthetic(
        name="Clean Modern",
        description="Contemporary, bright, aspirational aesthetic",
        film_stock=FilmStock.ARRI_ALEXA_LOG,
        lens_character=LensCharacter.ZEISS_MASTER_PRIME,
        focal_length="35mm",
        aperture="f/2.8",
        lighting_style=LightingStyle.MODERN_NATURAL,
        color_grade=ColorGrade.CLEAN_MODERN,
        primary_colors=["clean white", "soft gray", "natural wood"],
        film_grain="minimal digital clean",
        highlights="controlled, detailed",
        shadows="open, detailed",
        contrast="medium, balanced",
        movement_style="smooth gimbal, dynamic but controlled"
    ),

    "cinematic_indie": VisualAesthetic(
        name="Cinematic Indie",
        description="Independent film aesthetic with character and soul",
        film_stock=FilmStock.KODAK_VISION3_500T,
        lens_character=LensCharacter.CANON_K35,
        focal_length="50mm",
        aperture="f/2.0",
        lighting_style=LightingStyle.PRACTICAL_WARM,
        color_grade=ColorGrade.RICH_FILMIC,
        primary_colors=["deep teal", "warm orange", "creamy skin tones"],
        film_grain="moderate filmic grain",
        highlights="gentle rolloff with character",
        shadows="rich and deep but detailed",
        contrast="medium-high, cinematic",
        movement_style="handheld with intention, intimate"
    ),

    "dreamy_soft": VisualAesthetic(
        name="Dreamy Soft",
        description="Ethereal, romantic, soft-focus aesthetic",
        film_stock=FilmStock.FUJI_PRO_400H,
        lens_character=LensCharacter.HELIOS_44,
        focal_length="58mm",
        aperture="f/2.0",
        lighting_style=LightingStyle.SOFT_WINDOW,
        color_grade=ColorGrade.PASTEL_SOFT,
        primary_colors=["soft lavender", "muted sage", "warm peach"],
        film_grain="subtle dreamy grain",
        highlights="blooming, ethereal",
        shadows="lifted, airy",
        contrast="low, soft",
        saturation="desaturated, pastel",
        movement_style="floating, gentle, dreamlike"
    )
}


def create_solopreneur_aesthetic() -> VisualAesthetic:
    """
    Create the perfect aesthetic for a feel-good solopreneur story.
    Warm, nostalgic, inspiring, real.
    """
    return VisualAesthetic(
        name="Solopreneur Dreams",
        description="Warm, nostalgic aesthetic celebrating the independent spirit. "
                    "Real moments, authentic emotion, the beauty of building something your own.",

        # Film - Portra for beautiful skin tones and warm nostalgic feel
        film_stock=FilmStock.KODAK_PORTRA_400,
        lens_character=LensCharacter.VINTAGE_COOKE,

        # Camera settings for intimate, personal feel
        focal_length="85mm",  # Flattering for portraits, intimate feel
        aperture="f/1.8",  # Shallow depth for dreamy backgrounds

        # Lighting - warm and inviting
        lighting_style=LightingStyle.GOLDEN_HOUR,
        key_light_direction="large window camera left, golden hour sun",
        lighting_ratio="2:1 soft",

        # Color - warm nostalgic palette
        color_grade=ColorGrade.WARM_NOSTALGIC,
        primary_colors=[
            "warm honey amber",
            "soft cream white",
            "gentle terracotta",
            "natural wood brown"
        ],
        accent_colors=[
            "dusty sage green",
            "muted coral",
            "golden yellow"
        ],

        # Texture - organic film feel
        film_grain="subtle organic film grain, visible but not distracting",
        grain_intensity=0.35,

        # Tonal qualities
        highlights="soft blooming highlights with gentle rolloff",
        shadows="lifted warm shadows, never crushed, always retaining detail",
        contrast="low-medium contrast, gentle tonal transitions",
        saturation="naturally warm, skin tones preserved, not oversaturated",

        # Camera movement style
        movement_style="slow, deliberate, contemplative. motivated movements only. "
                       "let moments breathe. lingering on expressions.",
        preferred_shots=[
            "intimate medium close-up",
            "close-up on hands and details",
            "over-shoulder at workspace",
            "profile with window light",
            "wide establishing with subject small in frame"
        ]
    )


if __name__ == "__main__":
    # Demo the solopreneur aesthetic
    aesthetic = create_solopreneur_aesthetic()
    print("=" * 60)
    print(f"AESTHETIC: {aesthetic.name}")
    print("=" * 60)
    print(f"\n{aesthetic.description}\n")
    print("PROMPT SUFFIX:")
    print("-" * 40)
    print(aesthetic.to_prompt_suffix())
    print("\n" + "=" * 60)
