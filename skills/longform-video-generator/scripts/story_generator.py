#!/usr/bin/env python3
"""
Generic story and script generation for long-form videos.
Creates structured narratives with scenes, dialog, shot descriptions, and aesthetics.

This module provides the data structures for video scripts.
Scripts can be created programmatically or loaded from JSON files.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class ShotType(Enum):
    EXTREME_CLOSE_UP = "extreme close-up"
    CLOSE_UP = "close-up"
    MEDIUM_CLOSE_UP = "medium close-up"
    MEDIUM_SHOT = "medium shot"
    MEDIUM_WIDE = "medium wide shot"
    WIDE_SHOT = "wide shot"
    EXTREME_WIDE = "extreme wide shot"
    ESTABLISHING = "establishing shot"


class CameraMovement(Enum):
    STATIC = "static"
    PAN_LEFT = "slow pan left"
    PAN_RIGHT = "slow pan right"
    TILT_UP = "tilt up"
    TILT_DOWN = "tilt down"
    DOLLY_IN = "dolly in"
    DOLLY_OUT = "dolly out"
    TRACKING = "tracking shot"
    CRANE = "crane shot"
    HANDHELD = "handheld"
    ZOOM_IN = "slow zoom in"
    ZOOM_OUT = "slow zoom out"


@dataclass
class Aesthetic:
    """
    Visual aesthetic definition for a video project.
    Incorporated into every image and video prompt for consistency.
    """
    name: str = "Default"
    film_stock: str = "cinematic film look"
    lens: str = "shallow depth of field"
    focal_length: str = "50mm"
    aperture: str = "f/2.0"
    lighting: str = "soft natural light"
    color_grade: str = "balanced cinematic grade"
    grain: str = "subtle film grain"
    colors: List[str] = field(default_factory=lambda: ["natural", "balanced"])

    def to_prompt_suffix(self) -> str:
        """Generate prompt suffix capturing the aesthetic"""
        parts = [
            self.film_stock,
            self.lens,
            f"shot at {self.focal_length} {self.aperture}",
            self.lighting,
            self.color_grade,
            self.grain,
            f"color palette: {', '.join(self.colors)}"
        ]
        return ". ".join(parts)

    @classmethod
    def from_dict(cls, data: Dict) -> "Aesthetic":
        return cls(
            name=data.get("name", "Default"),
            film_stock=data.get("film_stock", "cinematic film look"),
            lens=data.get("lens", "shallow depth of field"),
            focal_length=data.get("focal_length", "50mm"),
            aperture=data.get("aperture", "f/2.0"),
            lighting=data.get("lighting", "soft natural light"),
            color_grade=data.get("color_grade", "balanced cinematic grade"),
            grain=data.get("grain", "subtle film grain"),
            colors=data.get("colors", ["natural", "balanced"])
        )


@dataclass
class Shot:
    """A single shot/scene in the video"""
    scene_number: int
    description: str
    duration_seconds: float

    # Visual details for image generation
    image_prompt: str
    style_keywords: List[str] = field(default_factory=list)

    # Camera and framing
    shot_type: ShotType = ShotType.MEDIUM_SHOT
    camera_movement: CameraMovement = CameraMovement.STATIC

    # Motion description for video generation
    motion_prompt: str = ""

    # Audio
    voiceover: Optional[str] = None
    sound_effects: List[str] = field(default_factory=list)

    # Continuity
    key_elements: List[str] = field(default_factory=list)
    transition_to_next: str = "cut"

    # Character tracking for visual consistency
    character: Optional[str] = None


@dataclass
class VideoScript:
    """Complete video script with all scenes"""
    title: str
    target_duration_seconds: int

    # Story structure
    hook: str = ""
    premise: str = ""
    call_to_action: str = ""

    # Visual style
    aesthetic: Aesthetic = field(default_factory=Aesthetic)

    # Audio
    music_style: str = ""
    music_mood_progression: List[str] = field(default_factory=list)

    # Scenes
    shots: List[Shot] = field(default_factory=list)

    # Characters and settings for consistency
    characters: Dict[str, str] = field(default_factory=dict)
    settings: Dict[str, str] = field(default_factory=dict)

    def get_full_prompt(self, shot: Shot) -> str:
        """Build complete prompt for a shot with aesthetic and character info"""
        parts = []

        # Add character description if specified
        if shot.character and shot.character in self.characters:
            parts.append(self.characters[shot.character])

        # Add shot's image prompt
        parts.append(shot.image_prompt)

        # Add style keywords
        if shot.style_keywords:
            parts.append(", ".join(shot.style_keywords))

        # Add shot type
        parts.append(f"{shot.shot_type.value} framing")

        # Add aesthetic
        parts.append(self.aesthetic.to_prompt_suffix())

        return ". ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "title": self.title,
            "target_duration_seconds": self.target_duration_seconds,
            "hook": self.hook,
            "premise": self.premise,
            "call_to_action": self.call_to_action,
            "aesthetic": {
                "name": self.aesthetic.name,
                "film_stock": self.aesthetic.film_stock,
                "lens": self.aesthetic.lens,
                "focal_length": self.aesthetic.focal_length,
                "aperture": self.aesthetic.aperture,
                "lighting": self.aesthetic.lighting,
                "color_grade": self.aesthetic.color_grade,
                "grain": self.aesthetic.grain,
                "colors": self.aesthetic.colors
            },
            "music_style": self.music_style,
            "music_mood_progression": self.music_mood_progression,
            "characters": self.characters,
            "settings": self.settings,
            "shots": [
                {
                    "scene_number": s.scene_number,
                    "description": s.description,
                    "duration_seconds": s.duration_seconds,
                    "image_prompt": s.image_prompt,
                    "style_keywords": s.style_keywords,
                    "shot_type": s.shot_type.value,
                    "camera_movement": s.camera_movement.value,
                    "motion_prompt": s.motion_prompt,
                    "voiceover": s.voiceover,
                    "sound_effects": s.sound_effects,
                    "key_elements": s.key_elements,
                    "transition_to_next": s.transition_to_next,
                    "character": s.character
                }
                for s in self.shots
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoScript":
        """Create from dictionary (loaded from JSON)"""

        # Parse aesthetic
        aesthetic_data = data.get("aesthetic", {})
        aesthetic = Aesthetic.from_dict(aesthetic_data)

        # Parse characters
        characters = {}
        char_data = data.get("characters", {})
        for name, info in char_data.items():
            if isinstance(info, dict):
                characters[name] = info.get("description", "")
            else:
                characters[name] = str(info)

        # Parse settings
        settings = data.get("settings", {})

        # Parse shots
        shots = []
        for s in data.get("shots", []):
            # Parse shot type
            shot_type_str = s.get("shot_type", "medium shot").replace("-", " ").replace("_", " ")
            try:
                shot_type = ShotType(shot_type_str)
            except ValueError:
                shot_type = ShotType.MEDIUM_SHOT

            # Parse camera movement
            cam_move_str = s.get("camera_movement", "static").replace("-", " ").replace("_", " ")
            try:
                camera_movement = CameraMovement(cam_move_str)
            except ValueError:
                camera_movement = CameraMovement.STATIC

            shot = Shot(
                scene_number=s.get("scene_number", len(shots) + 1),
                description=s.get("description", ""),
                duration_seconds=s.get("duration_seconds", 5),
                image_prompt=s.get("image_prompt", ""),
                style_keywords=s.get("style_keywords", []),
                shot_type=shot_type,
                camera_movement=camera_movement,
                motion_prompt=s.get("motion_prompt", ""),
                voiceover=s.get("voiceover"),
                sound_effects=s.get("sound_effects", []),
                key_elements=s.get("key_elements", []),
                transition_to_next=s.get("transition_to_next", "cut"),
                character=s.get("character")
            )
            shots.append(shot)

        # Parse music
        music_data = data.get("music", {})
        music_style = music_data.get("style", data.get("music_style", ""))
        music_progression = music_data.get("mood_progression", data.get("music_mood_progression", []))

        return cls(
            title=data.get("title", "Untitled"),
            target_duration_seconds=data.get("target_duration_seconds", 30),
            hook=data.get("hook", ""),
            premise=data.get("premise", ""),
            call_to_action=data.get("call_to_action", ""),
            aesthetic=aesthetic,
            music_style=music_style,
            music_mood_progression=music_progression,
            characters=characters,
            settings=settings,
            shots=shots
        )


def save_script(script: VideoScript, path: str):
    """Save script to JSON file"""
    with open(path, 'w') as f:
        json.dump(script.to_dict(), f, indent=2)


def load_script(path: str) -> VideoScript:
    """Load script from JSON file"""
    with open(path) as f:
        return VideoScript.from_dict(json.load(f))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Load and print script from file
        script = load_script(sys.argv[1])
        print(json.dumps(script.to_dict(), indent=2))
    else:
        print("Usage: python story_generator.py <script.json>")
        print("\nCreate a JSON script file with the following structure:")
        print(json.dumps({
            "title": "My Video",
            "target_duration_seconds": 30,
            "hook": "Opening hook line",
            "premise": "What the video is about",
            "call_to_action": "Ending CTA",
            "aesthetic": {
                "name": "Style Name",
                "film_stock": "Film emulation description",
                "lens": "Lens character",
                "lighting": "Lighting style",
                "color_grade": "Color treatment",
                "colors": ["color1", "color2"]
            },
            "characters": {
                "main": {
                    "description": "Character visual description"
                }
            },
            "music": {
                "style": "Music description",
                "mood_progression": ["mood1", "mood2"]
            },
            "shots": [
                {
                    "scene_number": 1,
                    "description": "What happens",
                    "duration_seconds": 5,
                    "character": "main",
                    "shot_type": "medium close-up",
                    "camera_movement": "static",
                    "image_prompt": "Visual description",
                    "motion_prompt": "Movement description",
                    "voiceover": "Narration text"
                }
            ]
        }, indent=2))
