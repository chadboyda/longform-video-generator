#!/usr/bin/env python3
"""
Timeline-based video assembly with voiceover synchronization.

Key principle: Voiceover timing drives video timing.
- Generate voiceover first to get exact word timestamps
- Use timestamps to determine clip durations
- Trim video clips to match voiceover segments
- Assemble with perfect audio/video sync
"""

import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class TimelineSegment:
    """A segment in the timeline (one shot)"""
    index: int
    voiceover_text: str
    vo_start: float          # Voiceover start time (seconds)
    vo_end: float            # Voiceover end time (seconds)
    video_path: Optional[Path] = None
    trimmed_video_path: Optional[Path] = None

    @property
    def duration(self) -> float:
        return self.vo_end - self.vo_start


@dataclass
class Timeline:
    """Complete timeline for video assembly"""
    segments: List[TimelineSegment] = field(default_factory=list)
    voiceover_path: Optional[Path] = None
    voiceover_duration: float = 0.0
    music_path: Optional[Path] = None

    @property
    def total_duration(self) -> float:
        return self.voiceover_duration


class TimelineAssembler:
    """
    Assembles video based on voiceover timing.

    Flow:
    1. Build timeline from voiceover timestamps
    2. Trim each video clip to match its voiceover segment duration
    3. Concatenate trimmed clips
    4. Mix audio (voiceover + music)
    5. Output final video
    """

    def __init__(self, temp_dir: Path, output_dir: Path):
        self.temp_dir = temp_dir
        self.output_dir = output_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_timeline(
        self,
        voiceover_segments: List[Dict],  # [{"text": "...", "start": 0.0, "end": 3.5}, ...]
        video_clips: List[Path],
        voiceover_path: Path,
        voiceover_duration: float,
        music_path: Optional[Path] = None
    ) -> Timeline:
        """
        Build timeline from voiceover timestamps and video clips.

        Args:
            voiceover_segments: List of dicts with text, start, end times
            video_clips: List of video clip paths (one per segment)
            voiceover_path: Path to full voiceover audio
            voiceover_duration: Total voiceover duration
            music_path: Optional background music
        """
        timeline = Timeline(
            voiceover_path=voiceover_path,
            voiceover_duration=voiceover_duration,
            music_path=music_path
        )

        for i, (segment, clip_path) in enumerate(zip(voiceover_segments, video_clips)):
            timeline.segments.append(TimelineSegment(
                index=i,
                voiceover_text=segment.get("text", ""),
                vo_start=segment.get("start", 0),
                vo_end=segment.get("end", 0),
                video_path=clip_path
            ))

        return timeline

    def trim_clip_to_duration(
        self,
        input_path: Path,
        output_path: Path,
        target_duration: float,
        min_duration: float = 2.0
    ) -> bool:
        """
        Trim a video clip to match target duration.

        Rules:
        - NEVER loop or repeat clips
        - If clip is longer than needed: trim it
        - If clip is shorter than needed: use full clip (don't extend)
        - Enforce minimum duration for smooth cuts
        """
        # Get source clip duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(input_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)

        try:
            probe_data = json.loads(result.stdout)
            source_duration = float(probe_data["format"]["duration"])
        except (json.JSONDecodeError, KeyError):
            source_duration = 4.0  # Default assumption

        # Enforce minimum duration to avoid jumpy cuts
        effective_duration = max(target_duration, min_duration)

        # Use the shorter of: target duration or source duration
        # NEVER extend/loop - just use what we have
        final_duration = min(effective_duration, source_duration)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-t", str(final_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an",  # Remove audio from clip
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def prepare_timeline_clips(self, timeline: Timeline, min_duration: float = 2.5) -> bool:
        """
        Prepare all clips by trimming to match voiceover timing.

        Enforces minimum duration to avoid jumpy cuts.
        """
        print("  [Timeline] Preparing clips to match voiceover timing...")
        print(f"    Minimum clip duration: {min_duration}s")

        for segment in timeline.segments:
            if not segment.video_path or not segment.video_path.exists():
                print(f"    WARNING: Missing video for segment {segment.index}")
                continue

            trimmed_path = self.temp_dir / f"trimmed_{segment.index:03d}.mp4"
            vo_duration = segment.duration

            # Enforce minimum for smooth cuts
            effective_duration = max(vo_duration, min_duration)

            if vo_duration < min_duration:
                print(f"    Clip {segment.index}: {vo_duration:.2f}s VO -> {effective_duration:.2f}s visual (extended for smooth cut)")
            else:
                print(f"    Clip {segment.index}: {effective_duration:.2f}s")

            if self.trim_clip_to_duration(segment.video_path, trimmed_path, effective_duration, min_duration):
                segment.trimmed_video_path = trimmed_path
            else:
                print(f"    ERROR: Failed to trim clip {segment.index}")
                segment.trimmed_video_path = segment.video_path

        return True

    def concatenate_clips(self, timeline: Timeline, output_path: Path) -> bool:
        """
        Concatenate all trimmed clips into a single video.
        """
        print("  [Timeline] Concatenating clips...")

        # Create concat list
        concat_list = self.temp_dir / "concat_timeline.txt"
        with open(concat_list, "w") as f:
            for segment in timeline.segments:
                if segment.trimmed_video_path and segment.trimmed_video_path.exists():
                    f.write(f"file '{segment.trimmed_video_path.absolute()}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-movflags", "+faststart",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def _create_outro_sequence(
        self,
        video_path: Path,
        current_duration: float,
        target_duration: float,
        cta_text: str = ""
    ) -> Optional[Path]:
        """
        Create a professional outro sequence when video is shorter than audio.

        Creates:
        1. Fade last 1.5s of video to black
        2. Black screen for remaining audio
        3. Professional ending like movie trailers
        """
        gap = target_duration - current_duration
        fade_start = max(0, current_duration - 1.5)

        # Get video dimensions
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            str(video_path)
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        try:
            stream = json.loads(probe_result.stdout)["streams"][0]
            width, height = stream["width"], stream["height"]
        except:
            width, height = 1280, 720

        # Step 1: Create black video for the gap
        black_path = self.temp_dir / "black_outro.mp4"
        black_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s={width}x{height}:d={gap + 0.5}:r=24",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            str(black_path)
        ]
        subprocess.run(black_cmd, capture_output=True)

        # Step 2: Add fade-out to main video
        faded_path = self.temp_dir / "video_faded.mp4"
        fade_cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", f"fade=t=out:st={fade_start}:d=1.5:color=black",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an",
            str(faded_path)
        ]
        fade_result = subprocess.run(fade_cmd, capture_output=True)

        if fade_result.returncode != 0:
            return None

        # Step 3: Concatenate faded video + black
        concat_list = self.temp_dir / "outro_concat.txt"
        with open(concat_list, "w") as f:
            f.write(f"file '{faded_path.absolute()}'\n")
            f.write(f"file '{black_path.absolute()}'\n")

        output_path = self.temp_dir / "video_with_outro.mp4"
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-t", str(target_duration),
            str(output_path)
        ]

        result = subprocess.run(concat_cmd, capture_output=True, text=True)

        if result.returncode == 0 and output_path.exists():
            print(f"    Created fade-out with {gap:.1f}s black (audio continues)")
            return output_path

        return None

    def mix_final_audio(
        self,
        video_path: Path,
        voiceover_path: Path,
        music_path: Optional[Path],
        output_path: Path,
        music_volume: float = 0.15
    ) -> bool:
        """
        Mix voiceover and music onto video with proper levels.
        """
        print("  [Timeline] Mixing audio...")

        if music_path and music_path.exists():
            # Mix voiceover + music
            # Normalize sample rates and mix
            filter_complex = (
                f"[1:a]aresample=48000[vo];"
                f"[2:a]aresample=48000,volume={music_volume}[music];"
                f"[vo][music]amix=inputs=2:duration=first:normalize=0[audio]"
            )

            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(voiceover_path),
                "-i", str(music_path),
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[audio]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "256k",
                "-ar", "48000",
                "-movflags", "+faststart",
                str(output_path)
            ]
        else:
            # Just voiceover
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(voiceover_path),
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "256k",
                "-ar", "48000",
                "-movflags", "+faststart",
                str(output_path)
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    Audio mix error: {result.stderr[:200]}")

        return result.returncode == 0

    def assemble(
        self,
        timeline: Timeline,
        output_path: Path,
        music_volume: float = 0.15
    ) -> Dict[str, Any]:
        """
        Full assembly pipeline:
        1. Trim clips to match voiceover timing
        2. Concatenate clips
        3. Ensure video >= voiceover duration
        4. Mix audio
        5. Output final video
        """
        print("\n  [Timeline] Starting assembly...")
        print(f"    Voiceover duration: {timeline.voiceover_duration:.2f}s")
        print(f"    Segments: {len(timeline.segments)}")

        # Step 1: Prepare clips
        if not self.prepare_timeline_clips(timeline):
            return {"success": False, "error": "Failed to prepare clips"}

        # Step 2: Concatenate
        concat_path = self.temp_dir / "timeline_concat.mp4"
        if not self.concatenate_clips(timeline, concat_path):
            return {"success": False, "error": "Failed to concatenate clips"}

        # Verify concat duration
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(concat_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        try:
            video_duration = float(json.loads(result.stdout)["format"]["duration"])
        except:
            video_duration = 0

        print(f"    Video duration: {video_duration:.2f}s")

        # Step 2.5: If video is shorter than voiceover, create proper outro
        final_video_path = concat_path
        if video_duration < timeline.voiceover_duration:
            gap = timeline.voiceover_duration - video_duration + 1.5
            print(f"    Video short by {gap:.1f}s - creating professional outro...")

            # Create a proper ending sequence:
            # 1. Fade last segment to black over 1.5s
            # 2. Add outro card for remaining time
            final_video_path = self._create_outro_sequence(
                concat_path,
                video_duration,
                timeline.voiceover_duration + 0.5,
                timeline.segments[-1].voiceover_text if timeline.segments else ""
            )
            if final_video_path:
                video_duration = timeline.voiceover_duration + 0.5
            else:
                final_video_path = concat_path  # Fallback

        # Step 3: Mix audio
        if not self.mix_final_audio(
            final_video_path,
            timeline.voiceover_path,
            timeline.music_path,
            output_path,
            music_volume
        ):
            return {"success": False, "error": "Failed to mix audio"}

        print(f"  [Timeline] Assembly complete: {output_path}")

        return {
            "success": True,
            "local_path": str(output_path),
            "duration": timeline.voiceover_duration,
            "video_duration": video_duration
        }


def assemble_with_timing(
    voiceover_segments: List[Dict],
    video_clips: List[Path],
    voiceover_path: Path,
    voiceover_duration: float,
    output_path: Path,
    music_path: Optional[Path] = None,
    temp_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Convenience function for timeline-based assembly.
    """
    temp = temp_dir or output_path.parent / "temp"
    output_dir = output_path.parent

    assembler = TimelineAssembler(temp, output_dir)

    timeline = assembler.build_timeline(
        voiceover_segments,
        video_clips,
        voiceover_path,
        voiceover_duration,
        music_path
    )

    return assembler.assemble(timeline, output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Timeline-based video assembly")
    parser.add_argument("--timing-json", required=True, help="JSON file with voiceover timing")
    parser.add_argument("--clips-dir", required=True, help="Directory with video clips")
    parser.add_argument("--voiceover", required=True, help="Voiceover audio file")
    parser.add_argument("--music", help="Background music file")
    parser.add_argument("-o", "--output", required=True, help="Output video file")

    args = parser.parse_args()

    # Load timing data
    with open(args.timing_json) as f:
        timing = json.load(f)

    # Get video clips
    clips_dir = Path(args.clips_dir)
    clips = sorted(clips_dir.glob("clip_*.mp4"))

    result = assemble_with_timing(
        timing["segments"],
        clips,
        Path(args.voiceover),
        timing["duration"],
        Path(args.output),
        Path(args.music) if args.music else None
    )

    if result["success"]:
        print(f"Assembled: {result['local_path']}")
    else:
        print(f"Error: {result.get('error')}")
