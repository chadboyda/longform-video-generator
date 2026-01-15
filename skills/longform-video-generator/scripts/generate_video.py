#!/usr/bin/env python3
"""
Video clip generation using fal.ai Veo 3.1 and other video models.
Supports text-to-video and image-to-video generation.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# Import from same directory
sys.path.insert(0, str(Path(__file__).parent))
from fal_wrapper import FalClient, FalConfig, MODELS


def generate_video_clip(
    client: FalClient,
    prompt: str,
    output_path: Path,
    model: str = "veo31_fast",
    duration: str = "8s",
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    generate_audio: bool = True,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a single video clip.

    Args:
        client: FalClient instance
        prompt: Text description of the video
        output_path: Where to save the video
        model: Model key from MODELS dict
        duration: "4s", "6s", or "8s"
        resolution: "720p" or "1080p"
        aspect_ratio: "16:9" or "9:16"
        generate_audio: Whether to generate audio
        negative_prompt: What to avoid in the video
        seed: Random seed for reproducibility
        image_url: Optional image URL for image-to-video

    Returns:
        Dict with video URL and metadata
    """
    model_id = MODELS.get(model, model)

    arguments = {
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "generate_audio": generate_audio,
        "auto_fix": True,
    }

    if negative_prompt:
        arguments["negative_prompt"] = negative_prompt
    if seed is not None:
        arguments["seed"] = seed
    if image_url:
        arguments["image_url"] = image_url
        # Switch to image-to-video model if needed
        if "i2v" not in model:
            if "veo31" in model:
                model_id = MODELS["veo31_i2v"]
            elif "veo3" in model:
                model_id = MODELS["veo3_i2v"]

    print(f"Generating video with {model_id}...")
    print(f"  Prompt: {prompt[:100]}...")

    result = client.generate(model_id, arguments)

    # Download video
    video_data = result.get("video", {})
    video_url = video_data.get("url")

    if video_url:
        print(f"  Downloading to {output_path}...")
        client.download_file(video_url, output_path)
        return {
            "success": True,
            "url": video_url,
            "local_path": str(output_path),
            "prompt": prompt,
            "model": model_id
        }
    else:
        return {
            "success": False,
            "error": "No video URL in response",
            "response": result
        }


def generate_video_sequence(
    client: FalClient,
    scenes: List[Dict[str, Any]],
    output_dir: Path,
    model: str = "veo31_fast",
    default_duration: str = "8s",
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    generate_audio: bool = True
) -> List[Dict[str, Any]]:
    """
    Generate a sequence of video clips from scene descriptions.

    Args:
        client: FalClient instance
        scenes: List of scene dicts with 'prompt' and optional overrides
        output_dir: Directory to save video clips
        model: Default model to use
        default_duration: Default duration per clip
        resolution: Video resolution
        aspect_ratio: Video aspect ratio
        generate_audio: Whether to generate audio

    Returns:
        List of generation results
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for idx, scene in enumerate(scenes):
        print(f"\n[Scene {idx + 1}/{len(scenes)}]")

        prompt = scene.get("prompt", scene) if isinstance(scene, dict) else scene
        duration = scene.get("duration", default_duration) if isinstance(scene, dict) else default_duration
        scene_model = scene.get("model", model) if isinstance(scene, dict) else model
        image_url = scene.get("image_url") if isinstance(scene, dict) else None
        negative = scene.get("negative_prompt") if isinstance(scene, dict) else None

        output_path = output_dir / f"scene_{idx:03d}.mp4"

        result = generate_video_clip(
            client=client,
            prompt=prompt,
            output_path=output_path,
            model=scene_model,
            duration=duration,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            generate_audio=generate_audio,
            negative_prompt=negative,
            image_url=image_url
        )

        result["scene_index"] = idx
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Generate video clips using fal.ai")
    parser.add_argument("prompt", nargs="?", help="Video prompt (or use --scenes)")
    parser.add_argument("-o", "--output", default="output.mp4", help="Output file path")
    parser.add_argument("-m", "--model", default="veo31_fast",
                       choices=["veo3", "veo3_fast", "veo31_fast", "kling_pro", "minimax"],
                       help="Video model to use")
    parser.add_argument("-d", "--duration", default="8s", choices=["4s", "6s", "8s"],
                       help="Video duration")
    parser.add_argument("-r", "--resolution", default="720p", choices=["720p", "1080p"],
                       help="Video resolution")
    parser.add_argument("-a", "--aspect", default="16:9", choices=["16:9", "9:16"],
                       help="Aspect ratio")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio generation")
    parser.add_argument("--image", help="Input image URL for image-to-video")
    parser.add_argument("--negative", help="Negative prompt")
    parser.add_argument("--seed", type=int, help="Random seed")
    parser.add_argument("--scenes", help="JSON file with scene descriptions")
    parser.add_argument("--scenes-dir", default="scenes", help="Output directory for scenes")

    args = parser.parse_args()

    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("Error: Set FAL_KEY environment variable")
        sys.exit(1)

    config = FalConfig(
        api_key=api_key,
        output_dir=Path(args.output).parent if not args.scenes else Path(args.scenes_dir)
    )
    client = FalClient(config)

    if args.scenes:
        # Generate sequence from JSON file
        with open(args.scenes) as f:
            scenes = json.load(f)

        results = generate_video_sequence(
            client=client,
            scenes=scenes,
            output_dir=Path(args.scenes_dir),
            model=args.model,
            default_duration=args.duration,
            resolution=args.resolution,
            aspect_ratio=args.aspect,
            generate_audio=not args.no_audio
        )

        # Save results
        results_path = Path(args.scenes_dir) / "results.json"
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {results_path}")

    elif args.prompt:
        # Generate single video
        result = generate_video_clip(
            client=client,
            prompt=args.prompt,
            output_path=Path(args.output),
            model=args.model,
            duration=args.duration,
            resolution=args.resolution,
            aspect_ratio=args.aspect,
            generate_audio=not args.no_audio,
            negative_prompt=args.negative,
            seed=args.seed,
            image_url=args.image
        )

        if result["success"]:
            print(f"\nVideo saved to: {result['local_path']}")
        else:
            print(f"\nError: {result.get('error')}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
