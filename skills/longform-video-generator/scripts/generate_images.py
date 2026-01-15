#!/usr/bin/env python3
"""
Image generation using fal.ai Nano Banana Pro and Flux models.
Used for storyboard frames and image-to-video source images.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))
from fal_wrapper import FalClient, FalConfig, MODELS


def generate_image(
    client: FalClient,
    prompt: str,
    output_path: Path,
    model: str = "nano_banana_pro",
    aspect_ratio: str = "16:9",
    resolution: str = "1K",
    output_format: str = "png",
    num_images: int = 1
) -> Dict[str, Any]:
    """
    Generate an image from a text prompt.

    Args:
        client: FalClient instance
        prompt: Text description of the image
        output_path: Where to save the image
        model: Model key from MODELS dict
        aspect_ratio: Image aspect ratio
        resolution: "1K", "2K", or "4K"
        output_format: "png", "jpeg", or "webp"
        num_images: Number of images to generate

    Returns:
        Dict with image URL and metadata
    """
    model_id = MODELS.get(model, model)

    # Nano Banana Pro API spec - the best image model
    # Allowed aspect_ratio: 21:9, 16:9, 3:2, 4:3, 5:4, 1:1, 4:5, 3:4, 2:3, 9:16
    # Allowed resolution: 1K, 2K, 4K (4K is 2x price)
    # Allowed output_format: jpeg, png, webp
    arguments = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "output_format": output_format,
        "num_images": num_images
    }

    print(f"Generating image with {model_id}...")
    print(f"  Prompt: {prompt[:100]}...")

    result = client.generate(model_id, arguments)

    # Handle different response formats
    images = result.get("images", [])
    if not images and "image" in result:
        images = [result["image"]]

    if images:
        image_url = images[0].get("url")
        if image_url:
            print(f"  Downloading to {output_path}...")
            client.download_file(image_url, output_path)
            return {
                "success": True,
                "url": image_url,
                "local_path": str(output_path),
                "prompt": prompt,
                "model": model_id,
                "all_images": [img.get("url") for img in images]
            }

    return {
        "success": False,
        "error": "No image URL in response",
        "response": result
    }


def generate_storyboard(
    client: FalClient,
    frames: List[Dict[str, Any]],
    output_dir: Path,
    model: str = "nano_banana_pro",
    aspect_ratio: str = "16:9",
    resolution: str = "1K",
    style_prefix: str = ""
) -> List[Dict[str, Any]]:
    """
    Generate a storyboard sequence of images.

    Args:
        client: FalClient instance
        frames: List of frame descriptions (dicts with 'prompt' key or strings)
        output_dir: Directory to save images
        model: Image model to use
        aspect_ratio: Aspect ratio for all frames
        resolution: Resolution for all frames
        style_prefix: Style text to prepend to all prompts

    Returns:
        List of generation results
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for idx, frame in enumerate(frames):
        print(f"\n[Frame {idx + 1}/{len(frames)}]")

        if isinstance(frame, dict):
            prompt = frame.get("prompt", "")
            frame_model = frame.get("model", model)
            frame_aspect = frame.get("aspect_ratio", aspect_ratio)
        else:
            prompt = str(frame)
            frame_model = model
            frame_aspect = aspect_ratio

        # Apply style prefix
        if style_prefix:
            prompt = f"{style_prefix}. {prompt}"

        output_path = output_dir / f"frame_{idx:03d}.png"

        result = generate_image(
            client=client,
            prompt=prompt,
            output_path=output_path,
            model=frame_model,
            aspect_ratio=frame_aspect,
            resolution=resolution
        )

        result["frame_index"] = idx
        results.append(result)

    return results


def generate_image_with_reference(
    client: FalClient,
    prompt: str,
    reference_urls: List[str],
    output_path: Path,
    aspect_ratio: str = "16:9",
    resolution: str = "1K",
    output_format: str = "png",
    num_images: int = 1
) -> Dict[str, Any]:
    """
    Generate an image using reference images for consistency (characters, objects, scenes).
    Uses nano-banana-pro/edit endpoint.

    Args:
        client: FalClient instance
        prompt: Text description incorporating the reference
        reference_urls: List of reference image URLs to maintain consistency
        output_path: Where to save the image
        aspect_ratio: Image aspect ratio (auto, 1:1, 16:9, 9:16, etc.)
        resolution: "1K", "2K", or "4K"
        output_format: "png", "jpeg", or "webp"
        num_images: Number of images to generate

    Returns:
        Dict with image URL and metadata
    """
    model_id = MODELS.get("nano_banana_pro_edit", "fal-ai/nano-banana-pro/edit")

    arguments = {
        "prompt": prompt,
        "image_urls": reference_urls,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "output_format": output_format,
        "num_images": num_images
    }

    print(f"Generating image with reference using {model_id}...")
    print(f"  Prompt: {prompt[:100]}...")
    print(f"  References: {len(reference_urls)} image(s)")

    result = client.generate(model_id, arguments)

    # Handle different response formats
    images = result.get("images", [])
    if not images and "image" in result:
        images = [result["image"]]

    if images:
        image_url = images[0].get("url")
        if image_url:
            print(f"  Downloading to {output_path}...")
            client.download_file(image_url, output_path)
            return {
                "success": True,
                "url": image_url,
                "local_path": str(output_path),
                "prompt": prompt,
                "model": model_id,
                "reference_urls": reference_urls,
                "all_images": [img.get("url") for img in images]
            }

    return {
        "success": False,
        "error": "No image URL in response",
        "response": result
    }


def generate_storyboard_with_character_consistency(
    client: FalClient,
    frames: List[Dict[str, Any]],
    output_dir: Path,
    character_refs: Dict[str, str] = None,
    aspect_ratio: str = "16:9",
    resolution: str = "1K",
    style_prefix: str = ""
) -> List[Dict[str, Any]]:
    """
    Generate storyboard with character consistency using reference images.

    Args:
        client: FalClient instance
        frames: List of frame dicts with 'prompt' and optional 'character' key
        output_dir: Directory to save images
        character_refs: Dict mapping character names to their reference image URLs
        aspect_ratio: Aspect ratio for all frames
        resolution: Resolution for all frames
        style_prefix: Style text to prepend to all prompts

    Returns:
        List of generation results
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    character_refs = character_refs or {}
    generated_character_refs = {}  # Track generated character images

    for idx, frame in enumerate(frames):
        print(f"\n[Frame {idx + 1}/{len(frames)}]")

        if isinstance(frame, dict):
            prompt = frame.get("prompt", "")
            character = frame.get("character")
            frame_aspect = frame.get("aspect_ratio", aspect_ratio)
        else:
            prompt = str(frame)
            character = None
            frame_aspect = aspect_ratio

        # Apply style prefix
        if style_prefix:
            prompt = f"{style_prefix}. {prompt}"

        output_path = output_dir / f"frame_{idx:03d}.png"

        # Check if we have reference images for this character
        ref_urls = []
        if character:
            if character in character_refs:
                ref_urls.append(character_refs[character])
            if character in generated_character_refs:
                ref_urls.extend(generated_character_refs[character])

        if ref_urls:
            # Use reference-based generation for consistency
            result = generate_image_with_reference(
                client=client,
                prompt=prompt,
                reference_urls=ref_urls[-3:],  # Use up to 3 most recent refs
                output_path=output_path,
                aspect_ratio=frame_aspect,
                resolution=resolution
            )
        else:
            # First appearance - generate fresh and track as reference
            result = generate_image(
                client=client,
                prompt=prompt,
                output_path=output_path,
                model="nano_banana_pro",
                aspect_ratio=frame_aspect,
                resolution=resolution
            )

        # Track this as a reference for future frames with same character
        if result.get("success") and character and result.get("url"):
            if character not in generated_character_refs:
                generated_character_refs[character] = []
            generated_character_refs[character].append(result["url"])

        result["frame_index"] = idx
        result["character"] = character
        results.append(result)

    return results


def generate_style_consistent_frames(
    client: FalClient,
    base_prompt: str,
    frame_variations: List[str],
    output_dir: Path,
    model: str = "nano_banana_pro",
    aspect_ratio: str = "16:9",
    style_description: str = ""
) -> List[Dict[str, Any]]:
    """
    Generate multiple frames with consistent style.

    Args:
        client: FalClient instance
        base_prompt: Base scene/subject description
        frame_variations: List of variations for each frame
        output_dir: Directory to save images
        model: Image model to use
        aspect_ratio: Aspect ratio for all frames
        style_description: Style description to maintain consistency

    Returns:
        List of generation results
    """
    frames = []
    for variation in frame_variations:
        if style_description:
            prompt = f"{style_description}. {base_prompt}. {variation}"
        else:
            prompt = f"{base_prompt}. {variation}"
        frames.append({"prompt": prompt})

    return generate_storyboard(
        client=client,
        frames=frames,
        output_dir=output_dir,
        model=model,
        aspect_ratio=aspect_ratio
    )


def main():
    parser = argparse.ArgumentParser(description="Generate images using fal.ai")
    parser.add_argument("prompt", nargs="?", help="Image prompt (or use --frames)")
    parser.add_argument("-o", "--output", default="output.png", help="Output file path")
    parser.add_argument("-m", "--model", default="nano_banana_pro",
                       choices=["nano_banana_pro"],
                       help="Image model to use (Nano Banana Pro is SOTA)")
    parser.add_argument("-a", "--aspect", default="16:9",
                       choices=["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
                       help="Aspect ratio")
    parser.add_argument("-r", "--resolution", default="1K", choices=["1K", "2K", "4K"],
                       help="Resolution (Nano Banana Pro only)")
    parser.add_argument("-n", "--num", type=int, default=1, help="Number of images")
    parser.add_argument("--frames", help="JSON file with frame descriptions")
    parser.add_argument("--frames-dir", default="storyboard", help="Output directory for frames")
    parser.add_argument("--style", default="", help="Style prefix for all prompts")

    args = parser.parse_args()

    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("Error: Set FAL_KEY environment variable")
        sys.exit(1)

    config = FalConfig(
        api_key=api_key,
        output_dir=Path(args.output).parent if not args.frames else Path(args.frames_dir)
    )
    client = FalClient(config)

    if args.frames:
        # Generate storyboard from JSON file
        with open(args.frames) as f:
            frames = json.load(f)

        results = generate_storyboard(
            client=client,
            frames=frames,
            output_dir=Path(args.frames_dir),
            model=args.model,
            aspect_ratio=args.aspect,
            resolution=args.resolution,
            style_prefix=args.style
        )

        # Save results
        results_path = Path(args.frames_dir) / "results.json"
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {results_path}")

    elif args.prompt:
        # Generate single image
        result = generate_image(
            client=client,
            prompt=args.prompt,
            output_path=Path(args.output),
            model=args.model,
            aspect_ratio=args.aspect,
            resolution=args.resolution,
            num_images=args.num
        )

        if result["success"]:
            print(f"\nImage saved to: {result['local_path']}")
            if args.num > 1:
                print(f"All URLs: {result.get('all_images', [])}")
        else:
            print(f"\nError: {result.get('error')}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
