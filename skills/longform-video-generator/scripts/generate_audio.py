#!/usr/bin/env python3
"""
Audio generation using fal.ai ElevenLabs models.
Supports music, sound effects, and text-to-speech.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))
from fal_wrapper import FalClient, FalConfig, MODELS


def generate_music(
    client: FalClient,
    prompt: str,
    output_path: Path,
    duration_ms: Optional[int] = None,
    force_instrumental: bool = False,
    output_format: str = "mp3_44100_128"
) -> Dict[str, Any]:
    """
    Generate music from a text description.

    Args:
        client: FalClient instance
        prompt: Text description of the music
        output_path: Where to save the audio file
        duration_ms: Duration in milliseconds (3000-600000)
        force_instrumental: Guarantee no vocals
        output_format: Audio format (mp3_44100_128, etc.)

    Returns:
        Dict with audio URL and metadata
    """
    arguments = {
        "prompt": prompt,
        "force_instrumental": force_instrumental,
        "output_format": output_format
    }

    if duration_ms:
        arguments["music_length_ms"] = duration_ms

    print(f"Generating music...")
    print(f"  Prompt: {prompt[:100]}...")

    result = client.generate(MODELS["elevenlabs_music"], arguments)

    audio = result.get("audio", {})
    audio_url = audio.get("url")

    if audio_url:
        print(f"  Downloading to {output_path}...")
        client.download_file(audio_url, output_path)
        return {
            "success": True,
            "url": audio_url,
            "local_path": str(output_path),
            "prompt": prompt,
            "type": "music"
        }

    return {
        "success": False,
        "error": "No audio URL in response",
        "response": result
    }


def generate_sound_effect(
    client: FalClient,
    text: str,
    output_path: Path,
    duration_seconds: Optional[float] = None,
    prompt_influence: float = 0.3,
    output_format: str = "mp3_44100_128"
) -> Dict[str, Any]:
    """
    Generate a sound effect from a text description.

    Args:
        client: FalClient instance
        text: Text description of the sound effect
        output_path: Where to save the audio file
        duration_seconds: Duration in seconds (0.5-22)
        prompt_influence: How closely to follow the prompt (0-1)
        output_format: Audio format

    Returns:
        Dict with audio URL and metadata
    """
    arguments = {
        "text": text,
        "prompt_influence": prompt_influence,
        "output_format": output_format
    }

    if duration_seconds:
        arguments["duration_seconds"] = duration_seconds

    print(f"Generating sound effect...")
    print(f"  Description: {text[:100]}...")

    result = client.generate(MODELS["elevenlabs_sfx"], arguments)

    audio = result.get("audio", {})
    audio_url = audio.get("url")

    if audio_url:
        print(f"  Downloading to {output_path}...")
        client.download_file(audio_url, output_path)
        return {
            "success": True,
            "url": audio_url,
            "local_path": str(output_path),
            "text": text,
            "type": "sfx"
        }

    return {
        "success": False,
        "error": "No audio URL in response",
        "response": result
    }


def generate_speech(
    client: FalClient,
    text: str,
    output_path: Path,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",  # Default voice
    model: str = "elevenlabs_tts",
    stability: float = 0.5,
    similarity_boost: float = 0.75
) -> Dict[str, Any]:
    """
    Generate speech from text using TTS.

    Args:
        client: FalClient instance
        text: Text to speak
        output_path: Where to save the audio file
        voice_id: ElevenLabs voice ID
        model: TTS model ("elevenlabs_tts" or "kokoro_tts")
        stability: Voice stability (0-1)
        similarity_boost: Voice similarity boost (0-1)

    Returns:
        Dict with audio URL and metadata
    """
    model_id = MODELS.get(model, model)

    if "kokoro" in model_id:
        arguments = {
            "text": text
        }
    else:
        arguments = {
            "text": text,
            "voice_id": voice_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost
            }
        }

    print(f"Generating speech...")
    print(f"  Text: {text[:100]}...")

    result = client.generate(model_id, arguments)

    audio = result.get("audio", {})
    audio_url = audio.get("url")

    if audio_url:
        print(f"  Downloading to {output_path}...")
        client.download_file(audio_url, output_path)
        return {
            "success": True,
            "url": audio_url,
            "local_path": str(output_path),
            "text": text,
            "type": "tts"
        }

    return {
        "success": False,
        "error": "No audio URL in response",
        "response": result
    }


def generate_audio_assets(
    client: FalClient,
    assets: List[Dict[str, Any]],
    output_dir: Path
) -> List[Dict[str, Any]]:
    """
    Generate multiple audio assets from a list of specifications.

    Args:
        client: FalClient instance
        assets: List of asset specs with 'type', 'prompt'/'text', and optional params
        output_dir: Directory to save audio files

    Returns:
        List of generation results
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for idx, asset in enumerate(assets):
        print(f"\n[Audio {idx + 1}/{len(assets)}]")

        asset_type = asset.get("type", "music")
        filename = asset.get("filename", f"audio_{idx:03d}.mp3")
        output_path = output_dir / filename

        if asset_type == "music":
            result = generate_music(
                client=client,
                prompt=asset.get("prompt", ""),
                output_path=output_path,
                duration_ms=asset.get("duration_ms"),
                force_instrumental=asset.get("force_instrumental", False)
            )
        elif asset_type == "sfx":
            result = generate_sound_effect(
                client=client,
                text=asset.get("text", asset.get("prompt", "")),
                output_path=output_path,
                duration_seconds=asset.get("duration_seconds"),
                prompt_influence=asset.get("prompt_influence", 0.3)
            )
        elif asset_type == "tts":
            result = generate_speech(
                client=client,
                text=asset.get("text", ""),
                output_path=output_path,
                voice_id=asset.get("voice_id", "JBFqnCBsd6RMkjVDRZzb"),
                model=asset.get("model", "elevenlabs_tts")
            )
        else:
            result = {"success": False, "error": f"Unknown audio type: {asset_type}"}

        result["asset_index"] = idx
        result["asset_type"] = asset_type
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Generate audio using fal.ai ElevenLabs")
    subparsers = parser.add_subparsers(dest="command", help="Audio type")

    # Music subcommand
    music_parser = subparsers.add_parser("music", help="Generate music")
    music_parser.add_argument("prompt", help="Music description")
    music_parser.add_argument("-o", "--output", default="music.mp3", help="Output file")
    music_parser.add_argument("-d", "--duration", type=int, help="Duration in milliseconds")
    music_parser.add_argument("--instrumental", action="store_true", help="Force instrumental")

    # Sound effects subcommand
    sfx_parser = subparsers.add_parser("sfx", help="Generate sound effect")
    sfx_parser.add_argument("text", help="Sound effect description")
    sfx_parser.add_argument("-o", "--output", default="sfx.mp3", help="Output file")
    sfx_parser.add_argument("-d", "--duration", type=float, help="Duration in seconds")
    sfx_parser.add_argument("--influence", type=float, default=0.3, help="Prompt influence")

    # TTS subcommand
    tts_parser = subparsers.add_parser("tts", help="Generate speech")
    tts_parser.add_argument("text", help="Text to speak")
    tts_parser.add_argument("-o", "--output", default="speech.mp3", help="Output file")
    tts_parser.add_argument("--voice", default="JBFqnCBsd6RMkjVDRZzb", help="Voice ID")
    tts_parser.add_argument("--model", default="elevenlabs_tts",
                           choices=["elevenlabs_tts", "kokoro_tts"], help="TTS model")

    # Batch subcommand
    batch_parser = subparsers.add_parser("batch", help="Generate multiple audio assets")
    batch_parser.add_argument("assets_file", help="JSON file with audio assets")
    batch_parser.add_argument("-o", "--output-dir", default="audio", help="Output directory")

    args = parser.parse_args()

    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("Error: Set FAL_KEY environment variable")
        sys.exit(1)

    config = FalConfig(api_key=api_key)
    client = FalClient(config)

    if args.command == "music":
        result = generate_music(
            client=client,
            prompt=args.prompt,
            output_path=Path(args.output),
            duration_ms=args.duration,
            force_instrumental=args.instrumental
        )
    elif args.command == "sfx":
        result = generate_sound_effect(
            client=client,
            text=args.text,
            output_path=Path(args.output),
            duration_seconds=args.duration,
            prompt_influence=args.influence
        )
    elif args.command == "tts":
        result = generate_speech(
            client=client,
            text=args.text,
            output_path=Path(args.output),
            voice_id=args.voice,
            model=args.model
        )
    elif args.command == "batch":
        with open(args.assets_file) as f:
            assets = json.load(f)
        results = generate_audio_assets(
            client=client,
            assets=assets,
            output_dir=Path(args.output_dir)
        )
        results_path = Path(args.output_dir) / "results.json"
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {results_path}")
        return
    else:
        parser.print_help()
        sys.exit(1)

    if result["success"]:
        print(f"\nAudio saved to: {result['local_path']}")
    else:
        print(f"\nError: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
