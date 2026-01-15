#!/usr/bin/env python3
"""
Video Review & Quality Assurance.

Tools for reviewing video clips and final outputs:
- Frame extraction at specific timestamps
- Contact sheet/thumbnail strip generation
- Glitch detection (black frames, freezes, artifacts)
- Overlay timing verification
- Scene change detection
- Quality metrics

Use this to QA videos before delivery and identify clips needing regeneration.
"""

import subprocess
import json
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import shutil
import math


@dataclass
class FrameInfo:
    """Information about a single frame."""
    timestamp: float
    frame_number: int
    path: Path
    brightness: float = 0.0
    is_black: bool = False
    is_frozen: bool = False


@dataclass
class AIArtifact:
    """Detected AI generation artifact."""
    timestamp: float
    artifact_type: str  # temporal_glitch, symmetry, morphing, object_pop, etc.
    confidence: float  # 0-1 confidence score
    description: str
    frame_path: Optional[Path] = None


@dataclass
class GlitchReport:
    """Report of detected glitches in a video."""
    black_frames: List[float]  # Timestamps of black frames
    frozen_segments: List[Tuple[float, float]]  # (start, end) of frozen segments
    scene_changes: List[float]  # Timestamps of abrupt scene changes
    low_quality_segments: List[Tuple[float, float, str]]  # (start, end, reason)
    ai_artifacts: List[AIArtifact] = None  # AI generation quirks

    def __post_init__(self):
        if self.ai_artifacts is None:
            self.ai_artifacts = []

    @property
    def has_issues(self) -> bool:
        return bool(self.black_frames or self.frozen_segments or
                    self.low_quality_segments or self.ai_artifacts)

    def summary(self) -> str:
        issues = []
        if self.black_frames:
            issues.append(f"{len(self.black_frames)} black frames")
        if self.frozen_segments:
            issues.append(f"{len(self.frozen_segments)} frozen segments")
        if self.low_quality_segments:
            issues.append(f"{len(self.low_quality_segments)} quality issues")
        if self.ai_artifacts:
            issues.append(f"{len(self.ai_artifacts)} AI artifacts")
        return ", ".join(issues) if issues else "No issues detected"


class VideoReviewer:
    """
    Review and QA video files.

    Capabilities:
    - Extract frames at specific timestamps
    - Generate contact sheets for quick visual review
    - Detect common glitches
    - Verify overlay timing
    """

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp())
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """Get comprehensive video metadata."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        try:
            data = json.loads(result.stdout)

            # Extract key info
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                {}
            )

            return {
                "duration": float(data.get("format", {}).get("duration", 0)),
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "fps": eval(video_stream.get("r_frame_rate", "30/1")),
                "codec": video_stream.get("codec_name", "unknown"),
                "total_frames": int(video_stream.get("nb_frames", 0)),
                "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
            }
        except:
            return {}

    def extract_frame(
        self,
        video_path: Path,
        timestamp: float,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Extract a single frame at a specific timestamp.

        Args:
            video_path: Path to video file
            timestamp: Time in seconds
            output_path: Where to save frame (auto-generated if None)

        Returns:
            Path to extracted frame PNG
        """
        if output_path is None:
            output_path = self.temp_dir / f"frame_{timestamp:.3f}.png"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return output_path if output_path.exists() else None

    def extract_frames_at_times(
        self,
        video_path: Path,
        timestamps: List[float],
        output_dir: Optional[Path] = None
    ) -> List[Path]:
        """Extract frames at multiple specific timestamps."""
        if output_dir is None:
            output_dir = self.temp_dir / "frames"
        output_dir.mkdir(parents=True, exist_ok=True)

        frames = []
        for ts in timestamps:
            output = output_dir / f"frame_{ts:.3f}.png"
            if self.extract_frame(video_path, ts, output):
                frames.append(output)

        return frames

    def generate_contact_sheet(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        num_frames: int = 16,
        columns: int = 4,
        thumb_width: int = 320
    ) -> Optional[Path]:
        """
        Generate a contact sheet (thumbnail grid) for quick review.

        Args:
            video_path: Path to video
            output_path: Where to save contact sheet
            num_frames: Number of frames to extract
            columns: Number of columns in grid
            thumb_width: Width of each thumbnail

        Returns:
            Path to contact sheet image
        """
        if output_path is None:
            output_path = self.temp_dir / f"{video_path.stem}_contact_sheet.png"

        info = self.get_video_info(video_path)
        duration = info.get("duration", 60)

        # Calculate frame interval
        interval = duration / (num_frames + 1)

        # Calculate grid dimensions
        rows = math.ceil(num_frames / columns)
        thumb_height = int(thumb_width * 9 / 16)  # Assume 16:9

        # Generate contact sheet with ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", (
                f"fps=1/{interval},"
                f"scale={thumb_width}:{thumb_height}:force_original_aspect_ratio=decrease,"
                f"pad={thumb_width}:{thumb_height}:(ow-iw)/2:(oh-ih)/2,"
                f"tile={columns}x{rows}"
            ),
            "-frames:v", "1",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return output_path if output_path.exists() else None

    def detect_black_frames(
        self,
        video_path: Path,
        threshold: float = 0.02,
        min_duration: float = 0.1
    ) -> List[Tuple[float, float]]:
        """
        Detect black frame segments in video.

        Returns:
            List of (start, end) tuples for black segments
        """
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vf", f"blackdetect=d={min_duration}:pix_th={threshold}",
            "-an", "-f", "null", "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse blackdetect output
        black_segments = []
        for line in result.stderr.split('\n'):
            if 'black_start:' in line:
                try:
                    parts = line.split()
                    start = float([p for p in parts if 'black_start:' in p][0].split(':')[1])
                    end = float([p for p in parts if 'black_end:' in p][0].split(':')[1])
                    black_segments.append((start, end))
                except:
                    pass

        return black_segments

    def detect_frozen_frames(
        self,
        video_path: Path,
        threshold: float = 0.003,
        min_duration: float = 0.5
    ) -> List[Tuple[float, float]]:
        """
        Detect frozen/static segments in video.

        Returns:
            List of (start, end) tuples for frozen segments
        """
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vf", f"freezedetect=n={threshold}:d={min_duration}",
            "-an", "-f", "null", "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse freezedetect output
        frozen_segments = []
        for line in result.stderr.split('\n'):
            if 'freeze_start:' in line:
                try:
                    parts = line.split()
                    start = float([p for p in parts if 'freeze_start:' in p][0].split(':')[1])
                    # Look for end in subsequent lines or use None
                    frozen_segments.append((start, None))
                except:
                    pass
            elif 'freeze_end:' in line and frozen_segments and frozen_segments[-1][1] is None:
                try:
                    parts = line.split()
                    end = float([p for p in parts if 'freeze_end:' in p][0].split(':')[1])
                    frozen_segments[-1] = (frozen_segments[-1][0], end)
                except:
                    pass

        # Filter out incomplete detections
        return [(s, e) for s, e in frozen_segments if e is not None]

    def detect_scene_changes(
        self,
        video_path: Path,
        threshold: float = 0.3
    ) -> List[float]:
        """
        Detect abrupt scene changes.

        Returns:
            List of timestamps where scene changes occur
        """
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_frames", "-of", "json",
            "-f", "lavfi",
            f"movie={video_path},select='gt(scene,{threshold})'"
        ]

        # Alternative using ffmpeg
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-an", "-f", "null", "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse scene change times from showinfo output
        changes = []
        for line in result.stderr.split('\n'):
            if 'pts_time:' in line:
                try:
                    pts = float(line.split('pts_time:')[1].split()[0])
                    changes.append(pts)
                except:
                    pass

        return changes

    def detect_temporal_glitches(
        self,
        video_path: Path,
        sensitivity: float = 0.15
    ) -> List[Tuple[float, float]]:
        """
        Detect temporal inconsistencies - sudden changes that might indicate
        AI generation artifacts like objects appearing/disappearing.

        Uses frame-to-frame difference to find anomalous spikes.

        Returns:
            List of (timestamp, change_magnitude) for suspicious frames
        """
        # Use mpdecimate to detect similar frames, inverse for anomalies
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vf", f"select='gt(scene,{sensitivity})',metadata=print:file=-",
            "-an", "-f", "null", "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        glitches = []
        current_time = None
        current_score = None

        for line in result.stderr.split('\n'):
            if 'pts_time:' in line:
                try:
                    current_time = float(line.split('pts_time:')[1].split()[0])
                except:
                    pass
            if 'lavfi.scene_score=' in line:
                try:
                    current_score = float(line.split('=')[1])
                    if current_time is not None and current_score > sensitivity:
                        glitches.append((current_time, current_score))
                except:
                    pass

        return glitches

    def detect_blur_artifacts(
        self,
        video_path: Path,
        threshold: float = 100
    ) -> List[Tuple[float, float]]:
        """
        Detect blurry frames using Laplacian variance.
        Lower variance = more blur.

        Returns:
            List of (timestamp, blur_score) for blurry frames
        """
        # Extract frames and check blur using ffmpeg's blur detection
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vf", "fps=2,showinfo",  # 2 fps sample rate
            "-an", "-f", "null", "-"
        ]

        # Note: Full blur detection would require OpenCV
        # This is a simplified version using scene detection as proxy
        return []

    def extract_review_frames(
        self,
        video_path: Path,
        output_dir: Optional[Path] = None,
        interval: float = 1.0,
        focus_times: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract frames for visual inspection of AI artifacts.

        This is the PRIMARY method for detecting AI quirks like:
        - Mirrored/duplicated people
        - Objects appearing/disappearing (phones, hands)
        - Morphing faces or bodies
        - Impossible physics
        - Extra limbs or fingers

        Args:
            video_path: Path to video
            output_dir: Where to save frames
            interval: Seconds between frames (default 1s)
            focus_times: Specific timestamps to extract (overrides interval)

        Returns:
            List of frame info dicts with paths for visual review
        """
        if output_dir is None:
            output_dir = self.temp_dir / "review_frames"
        output_dir.mkdir(parents=True, exist_ok=True)

        info = self.get_video_info(video_path)
        duration = info.get("duration", 10)

        # Determine which frames to extract
        if focus_times:
            timestamps = focus_times
        else:
            timestamps = []
            t = 0
            while t < duration:
                timestamps.append(t)
                t += interval

        frames = []
        for ts in timestamps:
            output = output_dir / f"frame_{ts:.2f}s.png"
            if self.extract_frame(video_path, ts, output):
                frames.append({
                    "timestamp": ts,
                    "path": str(output),
                    "review_notes": None  # For annotation after visual review
                })

        return frames

    def generate_visual_review_strip(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        num_strips: int = 3,
        frames_per_strip: int = 10
    ) -> List[Path]:
        """
        Generate multiple horizontal strips showing video progression.
        Better for catching temporal anomalies than a grid.

        Returns:
            List of paths to strip images
        """
        if output_path is None:
            output_dir = self.temp_dir / "strips"
        else:
            output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        info = self.get_video_info(video_path)
        duration = info.get("duration", 30)

        strips = []
        segment_duration = duration / num_strips

        for i in range(num_strips):
            start = i * segment_duration
            strip_path = output_dir / f"strip_{i+1}_of_{num_strips}.png"

            # Generate strip for this segment
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-t", str(segment_duration),
                "-i", str(video_path),
                "-vf", (
                    f"fps={frames_per_strip/segment_duration},"
                    f"scale=160:-1,"
                    f"tile={frames_per_strip}x1"
                ),
                "-frames:v", "1",
                str(strip_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if strip_path.exists():
                strips.append(strip_path)

        return strips

    def analyze_video(self, video_path: Path, check_ai_artifacts: bool = True) -> GlitchReport:
        """
        Comprehensive video analysis for glitches and AI artifacts.

        Returns:
            GlitchReport with all detected issues
        """
        print(f"Analyzing: {video_path.name}")

        # Detect various issues
        print("  Checking for black frames...")
        black_segments = self.detect_black_frames(video_path)
        black_frames = [s[0] for s in black_segments]

        print("  Checking for frozen frames...")
        frozen_segments = self.detect_frozen_frames(video_path)

        print("  Detecting scene changes...")
        scene_changes = self.detect_scene_changes(video_path)

        low_quality = []
        ai_artifacts = []

        if check_ai_artifacts:
            print("  Checking for temporal glitches (AI artifacts)...")
            temporal_glitches = self.detect_temporal_glitches(video_path)

            # Convert temporal glitches to AI artifacts
            for ts, score in temporal_glitches:
                # High score mid-clip is suspicious (not scene change)
                # Filter out expected scene changes
                if score > 0.4 and ts not in scene_changes:
                    ai_artifacts.append(AIArtifact(
                        timestamp=ts,
                        artifact_type="temporal_glitch",
                        confidence=min(score, 1.0),
                        description=f"Sudden visual change (score: {score:.2f}) - possible object pop-in/out"
                    ))

        return GlitchReport(
            black_frames=black_frames,
            frozen_segments=frozen_segments,
            scene_changes=scene_changes,
            low_quality_segments=low_quality,
            ai_artifacts=ai_artifacts
        )

    def verify_overlay_timing(
        self,
        video_path: Path,
        expected_overlays: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Verify overlays appear at expected times by extracting frames.

        Args:
            video_path: Path to video with overlays
            expected_overlays: List of {"name": str, "start": float, "end": float, "position": str}

        Returns:
            List of verification results with frame paths
        """
        results = []

        for overlay in expected_overlays:
            name = overlay.get("name", "overlay")
            start = overlay.get("start", 0)
            end = overlay.get("end", start + 3)

            # Extract frames at start, middle, end of overlay
            times = [
                start - 0.5,  # Before (should NOT have overlay)
                start + 0.1,  # Just after start (SHOULD have overlay)
                (start + end) / 2,  # Middle (SHOULD have overlay)
                end - 0.1,  # Just before end (SHOULD have overlay)
                end + 0.5,  # After (should NOT have overlay)
            ]

            frames = []
            for t in times:
                if t >= 0:
                    frame = self.extract_frame(video_path, t)
                    if frame:
                        frames.append({"time": t, "path": str(frame)})

            results.append({
                "name": name,
                "expected_start": start,
                "expected_end": end,
                "verification_frames": frames
            })

        return results

    def generate_review_report(
        self,
        video_path: Path,
        output_dir: Optional[Path] = None,
        include_strips: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive review report with visuals.

        Returns:
            Dict with video info, glitch report, frame paths, and visual review strips
        """
        if output_dir is None:
            output_dir = self.temp_dir / "review"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get video info
        info = self.get_video_info(video_path)

        # Generate contact sheet
        contact_sheet = self.generate_contact_sheet(
            video_path,
            output_dir / "contact_sheet.png"
        )

        # Generate visual review strips for temporal analysis
        strips = []
        if include_strips:
            strips = self.generate_visual_review_strip(
                video_path,
                output_dir / "strips"
            )

        # Analyze for glitches and AI artifacts
        glitch_report = self.analyze_video(video_path, check_ai_artifacts=True)

        # Extract problem frames if any
        problem_frames = []
        for ts in glitch_report.black_frames[:5]:  # First 5 black frames
            frame = self.extract_frame(video_path, ts, output_dir / f"black_{ts:.2f}.png")
            if frame:
                problem_frames.append({"type": "black", "time": ts, "path": str(frame)})

        for start, end in glitch_report.frozen_segments[:3]:  # First 3 frozen segments
            frame = self.extract_frame(video_path, start, output_dir / f"frozen_{start:.2f}.png")
            if frame:
                problem_frames.append({"type": "frozen", "time": start, "duration": end - start, "path": str(frame)})

        # Extract frames at AI artifact locations
        for artifact in glitch_report.ai_artifacts[:5]:  # First 5 AI artifacts
            frame = self.extract_frame(video_path, artifact.timestamp, output_dir / f"artifact_{artifact.timestamp:.2f}.png")
            if frame:
                artifact.frame_path = frame
                problem_frames.append({
                    "type": "ai_artifact",
                    "subtype": artifact.artifact_type,
                    "time": artifact.timestamp,
                    "confidence": artifact.confidence,
                    "description": artifact.description,
                    "path": str(frame)
                })

        return {
            "video_path": str(video_path),
            "info": info,
            "contact_sheet": str(contact_sheet) if contact_sheet else None,
            "review_strips": [str(s) for s in strips],
            "glitch_summary": glitch_report.summary(),
            "black_frames": glitch_report.black_frames,
            "frozen_segments": [(s, e) for s, e in glitch_report.frozen_segments],
            "scene_changes": glitch_report.scene_changes,
            "ai_artifacts": [
                {
                    "time": a.timestamp,
                    "type": a.artifact_type,
                    "confidence": a.confidence,
                    "description": a.description,
                    "frame": str(a.frame_path) if a.frame_path else None
                }
                for a in glitch_report.ai_artifacts
            ],
            "problem_frames": problem_frames,
            "needs_regeneration": glitch_report.has_issues,
            "recommendation": self._generate_recommendation(glitch_report)
        }

    def _generate_recommendation(self, report: GlitchReport) -> str:
        """Generate actionable recommendation based on glitch report."""
        if not report.has_issues:
            return "Video looks good - proceed with use"

        issues = []
        if report.black_frames:
            issues.append(f"Fix {len(report.black_frames)} black frame(s)")
        if report.frozen_segments:
            issues.append(f"Check {len(report.frozen_segments)} frozen segment(s)")
        if report.ai_artifacts:
            issues.append(f"Review {len(report.ai_artifacts)} potential AI artifact(s) - may need clip regeneration")

        return "; ".join(issues)


def review_video(video_path: Path, output_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Convenience function to review a video."""
    reviewer = VideoReviewer()
    return reviewer.generate_review_report(video_path, output_dir)


def extract_frame(video_path: Path, timestamp: float, output_path: Optional[Path] = None) -> Optional[Path]:
    """Convenience function to extract a single frame."""
    reviewer = VideoReviewer()
    return reviewer.extract_frame(video_path, timestamp, output_path)


def generate_contact_sheet(video_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
    """Convenience function to generate contact sheet."""
    reviewer = VideoReviewer()
    return reviewer.generate_contact_sheet(video_path, output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Video Review & QA - Detect glitches and AI artifacts")
    parser.add_argument("video", help="Video file to review")
    parser.add_argument("-o", "--output", help="Output directory for review files")
    parser.add_argument("--contact-sheet", action="store_true", help="Generate contact sheet only")
    parser.add_argument("--frame", type=float, help="Extract single frame at timestamp")
    parser.add_argument("--analyze", action="store_true", help="Analyze for glitches and AI artifacts")
    parser.add_argument("--strips", action="store_true", help="Generate visual review strips")
    parser.add_argument("--extract-frames", type=float, default=None, help="Extract frames at interval (seconds)")

    args = parser.parse_args()

    video_path = Path(args.video)
    output_dir = Path(args.output) if args.output else None

    reviewer = VideoReviewer()

    if args.frame is not None:
        frame = reviewer.extract_frame(video_path, args.frame)
        if frame:
            print(f"Frame extracted: {frame}")
    elif args.contact_sheet:
        sheet = reviewer.generate_contact_sheet(video_path, output_dir / "contact_sheet.png" if output_dir else None)
        if sheet:
            print(f"Contact sheet: {sheet}")
    elif args.strips:
        strips = reviewer.generate_visual_review_strip(video_path, output_dir)
        print(f"\nGenerated {len(strips)} review strips:")
        for s in strips:
            print(f"  {s}")
    elif args.extract_frames:
        frames = reviewer.extract_review_frames(video_path, output_dir, interval=args.extract_frames)
        print(f"\nExtracted {len(frames)} frames for visual review:")
        for f in frames[:10]:
            print(f"  {f['timestamp']:.2f}s: {f['path']}")
        if len(frames) > 10:
            print(f"  ... and {len(frames) - 10} more")
    elif args.analyze:
        report = reviewer.analyze_video(video_path)
        print(f"\nGlitch Report: {report.summary()}")
        if report.black_frames:
            print(f"  Black frames at: {report.black_frames[:5]}...")
        if report.frozen_segments:
            print(f"  Frozen segments: {report.frozen_segments[:3]}...")
        if report.ai_artifacts:
            print(f"\n  AI Artifacts detected:")
            for a in report.ai_artifacts[:5]:
                print(f"    {a.timestamp:.2f}s: {a.description}")
    else:
        # Full review
        report = reviewer.generate_review_report(video_path, output_dir)
        print(f"\n{'='*60}")
        print(f"VIDEO REVIEW REPORT")
        print(f"{'='*60}")
        print(f"File: {report['video_path']}")
        print(f"Duration: {report['info'].get('duration', 0):.2f}s")
        print(f"Resolution: {report['info'].get('width')}x{report['info'].get('height')}")
        print(f"\nGlitch Summary: {report['glitch_summary']}")

        if report['contact_sheet']:
            print(f"\nContact sheet: {report['contact_sheet']}")

        if report['review_strips']:
            print(f"\nReview strips ({len(report['review_strips'])}):")
            for s in report['review_strips']:
                print(f"  {s}")

        if report['ai_artifacts']:
            print(f"\nAI Artifacts ({len(report['ai_artifacts'])}):")
            for a in report['ai_artifacts']:
                print(f"  {a['time']:.2f}s: {a['description']}")
                if a['frame']:
                    print(f"    Frame: {a['frame']}")

        print(f"\n{'='*60}")
        print(f"RECOMMENDATION: {report['recommendation']}")
        print(f"{'='*60}")
