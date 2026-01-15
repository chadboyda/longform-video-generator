#!/usr/bin/env python3
"""
Main orchestration script for generating long-form videos.
Takes a single prompt and generates a complete video with multiple scenes,
background music, and optional narration.
"""

import os
import sys
import json
import argparse
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from fal_wrapper import FalClient, FalConfig, MODELS
from generate_video import generate_video_sequence
from generate_images import generate_storyboard
from generate_audio import generate_music, generate_sound_effect, generate_speech
from stitch_video import (
    concatenate_videos_demuxer,
    concatenate_videos_filter,
    add_audio_track,
    normalize_videos,
    create_video_from_image,
    add_crossfade_transitions
)


def create_project_structure(base_dir: Path, project_name: str) -> Dict[str, Path]:
    """Create project directory structure"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = base_dir / f"{project_name}_{timestamp}"

    dirs = {
        "project": project_dir,
        "scenes": project_dir / "scenes",
        "storyboard": project_dir / "storyboard",
        "audio": project_dir / "audio",
        "temp": project_dir / "temp",
        "output": project_dir / "output"
    }

    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    return dirs


def parse_video_concept(concept: str) -> Dict[str, Any]:
    """
    Parse a video concept/prompt into structured scenes and audio.
    This is a simple parser - Claude should generate proper scene breakdowns.

    Args:
        concept: High-level video concept

    Returns:
        Dict with scenes, music_prompt, and metadata
    """
    # Default structure for a simple concept
    return {
        "title": concept[:50] + "..." if len(concept) > 50 else concept,
        "scenes": [
            {"prompt": concept, "duration": "8s"}
        ],
        "music_prompt": f"Background music for: {concept[:100]}",
        "total_duration_target": 60,  # seconds
        "style": "cinematic, high quality, professional"
    }


def generate_longform_video(
    client: FalClient,
    concept: Dict[str, Any],
    dirs: Dict[str, Path],
    video_model: str = "veo31_fast",
    image_model: str = "nano_banana_pro",
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    include_music: bool = True,
    include_transitions: bool = True,
    use_storyboard: bool = False
) -> Dict[str, Any]:
    """
    Generate a complete long-form video from a structured concept.

    Args:
        client: FalClient instance
        concept: Structured video concept with scenes
        dirs: Project directory structure
        video_model: Model for video generation
        image_model: Model for storyboard images
        resolution: Video resolution
        aspect_ratio: Video aspect ratio
        include_music: Generate and add background music
        include_transitions: Add crossfade transitions between scenes
        use_storyboard: Generate storyboard images first for image-to-video

    Returns:
        Dict with results and output paths
    """
    results = {
        "concept": concept,
        "scenes": [],
        "audio": [],
        "storyboard": [],
        "output": None,
        "errors": []
    }

    scenes = concept.get("scenes", [])
    style = concept.get("style", "")

    # Step 1: Generate storyboard images (optional)
    if use_storyboard:
        print("\n" + "=" * 50)
        print("STEP 1: Generating Storyboard Images")
        print("=" * 50)

        storyboard_frames = []
        for scene in scenes:
            prompt = scene.get("prompt", scene) if isinstance(scene, dict) else scene
            if style:
                prompt = f"{style}. {prompt}"
            storyboard_frames.append({"prompt": prompt})

        storyboard_results = generate_storyboard(
            client=client,
            frames=storyboard_frames,
            output_dir=dirs["storyboard"],
            model=image_model,
            aspect_ratio=aspect_ratio
        )
        results["storyboard"] = storyboard_results

        # Update scenes with image URLs for image-to-video
        for i, (scene, sb_result) in enumerate(zip(scenes, storyboard_results)):
            if sb_result.get("success") and sb_result.get("url"):
                if isinstance(scene, dict):
                    scene["image_url"] = sb_result["url"]
                else:
                    scenes[i] = {"prompt": scene, "image_url": sb_result["url"]}

    # Step 2: Generate video clips
    print("\n" + "=" * 50)
    print("STEP 2: Generating Video Scenes")
    print("=" * 50)

    video_results = generate_video_sequence(
        client=client,
        scenes=scenes,
        output_dir=dirs["scenes"],
        model=video_model,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        generate_audio=True  # Generate audio with video for better sync
    )
    results["scenes"] = video_results

    # Collect successful video paths
    video_paths = []
    for vr in video_results:
        if vr.get("success") and vr.get("local_path"):
            video_paths.append(Path(vr["local_path"]))
        else:
            results["errors"].append(f"Scene {vr.get('scene_index', '?')} failed: {vr.get('error', 'Unknown')}")

    if not video_paths:
        results["errors"].append("No video scenes generated successfully")
        return results

    # Step 3: Generate background music (optional)
    music_path = None
    if include_music and concept.get("music_prompt"):
        print("\n" + "=" * 50)
        print("STEP 3: Generating Background Music")
        print("=" * 50)

        # Estimate total video duration
        total_duration_ms = len(video_paths) * 8 * 1000  # Rough estimate

        music_result = generate_music(
            client=client,
            prompt=concept["music_prompt"],
            output_path=dirs["audio"] / "background_music.mp3",
            duration_ms=min(total_duration_ms, 300000),  # Max 5 minutes
            force_instrumental=True
        )
        results["audio"].append(music_result)

        if music_result.get("success"):
            music_path = Path(music_result["local_path"])
        else:
            results["errors"].append(f"Music generation failed: {music_result.get('error')}")

    # Step 4: Normalize and concatenate videos
    print("\n" + "=" * 50)
    print("STEP 4: Stitching Video Scenes")
    print("=" * 50)

    # Normalize videos first if needed
    if len(video_paths) > 1:
        print("Normalizing videos...")
        normalized_paths = normalize_videos(
            video_paths,
            dirs["temp"],
            target_resolution="1280x720" if resolution == "720p" else "1920x1080"
        )
    else:
        normalized_paths = video_paths

    # Concatenate
    concat_output = dirs["temp"] / "concatenated.mp4"

    if include_transitions and len(normalized_paths) > 1:
        success = add_crossfade_transitions(normalized_paths, concat_output)
    else:
        success = concatenate_videos_demuxer(normalized_paths, concat_output, reencode=True)

    if not success:
        # Fallback to filter method
        success = concatenate_videos_filter(normalized_paths, concat_output)

    if not success:
        results["errors"].append("Failed to concatenate videos")
        return results

    # Step 5: Add background music (optional)
    final_output = dirs["output"] / f"{concept.get('title', 'video')[:30].replace(' ', '_')}.mp4"

    if music_path and music_path.exists():
        print("\n" + "=" * 50)
        print("STEP 5: Adding Background Music")
        print("=" * 50)

        success = add_audio_track(
            concat_output,
            music_path,
            final_output,
            replace_audio=False,
            audio_volume=0.3,  # Background music at 30%
            mix_volume=1.0    # Keep original audio at 100%
        )

        if not success:
            print("Warning: Failed to add music, using video without music")
            final_output = concat_output
    else:
        # Just rename/copy the concatenated video
        import shutil
        shutil.copy(concat_output, final_output)

    results["output"] = str(final_output)

    # Summary
    print("\n" + "=" * 50)
    print("GENERATION COMPLETE")
    print("=" * 50)
    print(f"Output: {final_output}")
    print(f"Scenes: {len(video_paths)} generated")
    if results["errors"]:
        print(f"Errors: {len(results['errors'])}")
        for err in results["errors"]:
            print(f"  - {err}")

    return results


def generate_from_prompt(
    api_key: str,
    prompt: str,
    output_dir: Path,
    num_scenes: int = 3,
    scene_duration: str = "8s",
    video_model: str = "veo31_fast",
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    include_music: bool = True,
    style: str = "cinematic, high quality"
) -> Dict[str, Any]:
    """
    Simplified interface: generate a video from a single prompt.

    Args:
        api_key: fal.ai API key
        prompt: Video concept/description
        output_dir: Output directory
        num_scenes: Number of scenes to generate
        scene_duration: Duration per scene
        video_model: Video model to use
        resolution: Video resolution
        aspect_ratio: Aspect ratio
        include_music: Include background music
        style: Style prefix for prompts

    Returns:
        Generation results
    """
    config = FalConfig(api_key=api_key, output_dir=output_dir)
    client = FalClient(config)

    # Create project structure
    dirs = create_project_structure(output_dir, "video_project")

    # Parse the prompt into a concept
    # For simple prompts, we'll just duplicate with variations
    concept = {
        "title": prompt[:50],
        "scenes": [
            {"prompt": f"{style}. {prompt}. Scene {i+1} of {num_scenes}.", "duration": scene_duration}
            for i in range(num_scenes)
        ],
        "music_prompt": f"Cinematic background music for: {prompt[:100]}. Emotional, atmospheric, instrumental.",
        "style": style
    }

    return generate_longform_video(
        client=client,
        concept=concept,
        dirs=dirs,
        video_model=video_model,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        include_music=include_music,
        include_transitions=True,
        use_storyboard=False
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate long-form videos from prompts or structured concepts"
    )

    parser.add_argument("prompt", nargs="?", help="Video concept/prompt")
    parser.add_argument("-o", "--output-dir", default="./video_output",
                       help="Output directory")
    parser.add_argument("-n", "--num-scenes", type=int, default=3,
                       help="Number of scenes")
    parser.add_argument("-d", "--duration", default="8s",
                       choices=["4s", "6s", "8s"], help="Duration per scene")
    parser.add_argument("-m", "--model", default="veo31_fast",
                       choices=["veo3", "veo3_fast", "veo31_fast", "kling_pro"],
                       help="Video model")
    parser.add_argument("-r", "--resolution", default="720p",
                       choices=["720p", "1080p"], help="Resolution")
    parser.add_argument("-a", "--aspect", default="16:9",
                       choices=["16:9", "9:16"], help="Aspect ratio")
    parser.add_argument("--style", default="cinematic, high quality, professional",
                       help="Style prefix for prompts")
    parser.add_argument("--no-music", action="store_true",
                       help="Skip music generation")
    parser.add_argument("--concept-file", help="JSON file with structured concept")

    args = parser.parse_args()

    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("Error: Set FAL_KEY environment variable")
        sys.exit(1)

    output_dir = Path(args.output_dir)

    if args.concept_file:
        # Load structured concept from file
        with open(args.concept_file) as f:
            concept = json.load(f)

        config = FalConfig(api_key=api_key, output_dir=output_dir)
        client = FalClient(config)
        dirs = create_project_structure(output_dir, concept.get("title", "video"))

        results = generate_longform_video(
            client=client,
            concept=concept,
            dirs=dirs,
            video_model=args.model,
            resolution=args.resolution,
            aspect_ratio=args.aspect,
            include_music=not args.no_music
        )

    elif args.prompt:
        results = generate_from_prompt(
            api_key=api_key,
            prompt=args.prompt,
            output_dir=output_dir,
            num_scenes=args.num_scenes,
            scene_duration=args.duration,
            video_model=args.model,
            resolution=args.resolution,
            aspect_ratio=args.aspect,
            include_music=not args.no_music,
            style=args.style
        )
    else:
        parser.print_help()
        sys.exit(1)

    # Save results
    if results.get("output"):
        results_path = Path(results["output"]).parent / "generation_results.json"
        with open(results_path, "w") as f:
            # Make paths serializable
            serializable = {k: str(v) if isinstance(v, Path) else v for k, v in results.items()}
            json.dump(serializable, f, indent=2, default=str)
        print(f"\nResults saved to: {results_path}")

    sys.exit(0 if results.get("output") else 1)


if __name__ == "__main__":
    main()
