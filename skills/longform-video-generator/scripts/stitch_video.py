#!/usr/bin/env python3
"""
Video stitching and post-processing using ffmpeg.
Concatenates video clips, adds audio tracks, and applies effects.
"""

import os
import sys
import json
import subprocess
import tempfile
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any


def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg is not installed or not in PATH")
        print("Install with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
        return False


def get_video_info(video_path: Path) -> Dict[str, Any]:
    """Get video metadata using ffprobe"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    return {}


def concatenate_videos_demuxer(
    video_paths: List[Path],
    output_path: Path,
    reencode: bool = False
) -> bool:
    """
    Concatenate videos using the concat demuxer (fastest, no re-encoding).
    Best for videos with same codec, resolution, and frame rate.

    Args:
        video_paths: List of video file paths in order
        output_path: Output video path
        reencode: Force re-encoding (slower but handles different formats)

    Returns:
        True if successful
    """
    # Create temporary file list
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for path in video_paths:
            f.write(f"file '{path.absolute()}'\n")
        list_file = f.name

    try:
        if reencode:
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
                str(output_path)
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                str(output_path)
            ]

        print(f"Concatenating {len(video_paths)} videos...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False

        print(f"Output saved to: {output_path}")
        return True

    finally:
        os.unlink(list_file)


def concatenate_videos_filter(
    video_paths: List[Path],
    output_path: Path
) -> bool:
    """
    Concatenate videos using the concat filter (handles different formats).
    Re-encodes all videos for compatibility.

    Args:
        video_paths: List of video file paths in order
        output_path: Output video path

    Returns:
        True if successful
    """
    # Build filter complex string
    inputs = []
    filter_parts = []

    for i, path in enumerate(video_paths):
        inputs.extend(["-i", str(path)])
        filter_parts.append(f"[{i}:v][{i}:a]")

    filter_complex = "".join(filter_parts) + f"concat=n={len(video_paths)}:v=1:a=1[outv][outa]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ]

    print(f"Concatenating {len(video_paths)} videos with filter...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False

    print(f"Output saved to: {output_path}")
    return True


def add_audio_track(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    replace_audio: bool = False,
    audio_volume: float = 1.0,
    mix_volume: float = 0.3
) -> bool:
    """
    Add or mix audio track with video.

    Args:
        video_path: Input video path
        audio_path: Audio track to add
        output_path: Output video path
        replace_audio: If True, replace original audio; if False, mix
        audio_volume: Volume of added audio (0-2)
        mix_volume: Volume of original audio when mixing (0-2)

    Returns:
        True if successful
    """
    if replace_audio:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path)
        ]
    else:
        # Mix audio tracks
        filter_complex = (
            f"[0:a]volume={mix_volume}[a0];"
            f"[1:a]volume={audio_volume}[a1];"
            f"[a0][a1]amix=inputs=2:duration=first[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

    print(f"Adding audio track...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False

    print(f"Output saved to: {output_path}")
    return True


def add_crossfade_transitions(
    video_paths: List[Path],
    output_path: Path,
    fade_duration: float = 0.5
) -> bool:
    """
    Concatenate videos with crossfade transitions between clips.

    Args:
        video_paths: List of video file paths
        output_path: Output video path
        fade_duration: Duration of crossfade in seconds

    Returns:
        True if successful
    """
    if len(video_paths) < 2:
        print("Need at least 2 videos for transitions")
        return False

    # This is complex - build filter chain for crossfades
    inputs = []
    for path in video_paths:
        inputs.extend(["-i", str(path)])

    # Build filter complex for crossfades
    n = len(video_paths)
    filter_parts = []

    # First, trim and prepare all clips
    for i in range(n):
        filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}];")
        filter_parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}];")

    # Apply crossfades sequentially
    current_v = "v0"
    current_a = "a0"

    for i in range(1, n):
        next_v = f"v{i}"
        next_a = f"a{i}"
        out_v = f"xv{i}" if i < n - 1 else "outv"
        out_a = f"xa{i}" if i < n - 1 else "outa"

        filter_parts.append(
            f"[{current_v}][{next_v}]xfade=transition=fade:duration={fade_duration}:offset=7[{out_v}];"
        )
        filter_parts.append(
            f"[{current_a}][{next_a}]acrossfade=d={fade_duration}[{out_a}];"
        )

        current_v = out_v
        current_a = out_a

    filter_complex = "".join(filter_parts).rstrip(";")

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ]

    print(f"Adding crossfade transitions...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        # Fallback to simple concatenation
        print("Falling back to simple concatenation...")
        return concatenate_videos_demuxer(video_paths, output_path, reencode=True)

    print(f"Output saved to: {output_path}")
    return True


def normalize_videos(
    video_paths: List[Path],
    output_dir: Path,
    target_resolution: str = "1280x720",
    target_fps: int = 24
) -> List[Path]:
    """
    Normalize videos to same resolution and frame rate.

    Args:
        video_paths: List of input video paths
        output_dir: Directory for normalized videos
        target_resolution: Target resolution (WxH)
        target_fps: Target frame rate

    Returns:
        List of normalized video paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_paths = []

    width, height = target_resolution.split("x")

    for i, path in enumerate(video_paths):
        output_path = output_dir / f"normalized_{i:03d}.mp4"

        cmd = [
            "ffmpeg", "-y", "-i", str(path),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={target_fps}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]

        print(f"Normalizing video {i + 1}/{len(video_paths)}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            normalized_paths.append(output_path)
        else:
            print(f"Warning: Failed to normalize {path}: {result.stderr}")
            normalized_paths.append(path)  # Use original

    return normalized_paths


def create_video_from_image(
    image_path: Path,
    output_path: Path,
    duration: float = 5.0,
    zoom_effect: bool = False
) -> bool:
    """
    Create a video from a static image with optional Ken Burns effect.

    Args:
        image_path: Input image path
        output_path: Output video path
        duration: Duration in seconds
        zoom_effect: Apply slow zoom (Ken Burns) effect

    Returns:
        True if successful
    """
    if zoom_effect:
        # Ken Burns slow zoom effect
        filter_vf = (
            f"scale=8000:-1,zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={int(duration * 24)}:s=1280x720:fps=24"
        )
    else:
        filter_vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-vf", filter_vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]

    print(f"Creating video from image...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Video stitching and processing")
    subparsers = parser.add_subparsers(dest="command", help="Operation type")

    # Concatenate subcommand
    concat_parser = subparsers.add_parser("concat", help="Concatenate videos")
    concat_parser.add_argument("videos", nargs="+", help="Video files to concatenate")
    concat_parser.add_argument("-o", "--output", default="output.mp4", help="Output file")
    concat_parser.add_argument("--reencode", action="store_true", help="Force re-encoding")
    concat_parser.add_argument("--filter", action="store_true", help="Use filter method")
    concat_parser.add_argument("--transitions", action="store_true", help="Add crossfades")
    concat_parser.add_argument("--fade", type=float, default=0.5, help="Fade duration")

    # Add audio subcommand
    audio_parser = subparsers.add_parser("audio", help="Add audio track")
    audio_parser.add_argument("video", help="Input video")
    audio_parser.add_argument("audio", help="Audio track to add")
    audio_parser.add_argument("-o", "--output", default="output.mp4", help="Output file")
    audio_parser.add_argument("--replace", action="store_true", help="Replace original audio")
    audio_parser.add_argument("--volume", type=float, default=1.0, help="Added audio volume")
    audio_parser.add_argument("--mix-volume", type=float, default=0.3, help="Original audio volume when mixing")

    # Normalize subcommand
    norm_parser = subparsers.add_parser("normalize", help="Normalize videos")
    norm_parser.add_argument("videos", nargs="+", help="Videos to normalize")
    norm_parser.add_argument("-o", "--output-dir", default="normalized", help="Output directory")
    norm_parser.add_argument("-r", "--resolution", default="1280x720", help="Target resolution")
    norm_parser.add_argument("--fps", type=int, default=24, help="Target FPS")

    # Image to video subcommand
    img_parser = subparsers.add_parser("img2vid", help="Create video from image")
    img_parser.add_argument("image", help="Input image")
    img_parser.add_argument("-o", "--output", default="output.mp4", help="Output file")
    img_parser.add_argument("-d", "--duration", type=float, default=5.0, help="Duration")
    img_parser.add_argument("--zoom", action="store_true", help="Add Ken Burns zoom")

    args = parser.parse_args()

    if not check_ffmpeg():
        sys.exit(1)

    if args.command == "concat":
        video_paths = [Path(v) for v in args.videos]
        if args.transitions:
            success = add_crossfade_transitions(video_paths, Path(args.output), args.fade)
        elif args.filter:
            success = concatenate_videos_filter(video_paths, Path(args.output))
        else:
            success = concatenate_videos_demuxer(video_paths, Path(args.output), args.reencode)

    elif args.command == "audio":
        success = add_audio_track(
            Path(args.video),
            Path(args.audio),
            Path(args.output),
            replace_audio=args.replace,
            audio_volume=args.volume,
            mix_volume=args.mix_volume
        )

    elif args.command == "normalize":
        normalized = normalize_videos(
            [Path(v) for v in args.videos],
            Path(args.output_dir),
            args.resolution,
            args.fps
        )
        print(f"Normalized {len(normalized)} videos to {args.output_dir}/")
        success = True

    elif args.command == "img2vid":
        success = create_video_from_image(
            Path(args.image),
            Path(args.output),
            args.duration,
            args.zoom
        )

    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
