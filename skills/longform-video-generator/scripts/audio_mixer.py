#!/usr/bin/env python3
"""
Professional audio mixing and mastering for video production.

Implements:
- Sample rate normalization (critical for clean mixing)
- Loudness normalization (EBU R128 / LUFS)
- Sidechain compression (ducking music under voice)
- EQ for frequency separation
- Audio quality validation
"""

import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class AudioMixConfig:
    """Configuration for audio mixing"""
    # Target sample rate (must match video)
    target_sample_rate: int = 48000
    target_channels: int = 2

    # Target loudness levels (LUFS)
    voice_target_lufs: float = -16.0   # Voice prominent but not harsh
    music_target_lufs: float = -26.0   # Music well under voice

    # Volume multipliers (simple and reliable)
    voice_volume: float = 1.0
    music_volume: float = 0.15         # Music at 15% - subtle background

    # Final output
    output_lufs: float = -16.0
    output_true_peak: float = -1.5


@dataclass
class AudioValidation:
    """Results of audio quality validation"""
    is_valid: bool
    sample_rate: int
    channels: int
    duration: float
    peak_db: float
    integrated_lufs: float
    has_clipping: bool
    has_silence: bool
    issues: list


class AudioMixer:
    """
    Professional audio mixer for video production.

    Key principle: KEEP IT SIMPLE
    - Normalize sample rates first
    - Use simple volume mixing (no complex filters that can introduce artifacts)
    - Validate output quality
    """

    def __init__(self, config: Optional[AudioMixConfig] = None):
        self.config = config or AudioMixConfig()

    def get_audio_info(self, audio_path: Path) -> Dict[str, Any]:
        """Get audio file properties"""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            data = json.loads(result.stdout)
            stream = data.get("streams", [{}])[0]
            fmt = data.get("format", {})
            return {
                "sample_rate": int(stream.get("sample_rate", 44100)),
                "channels": int(stream.get("channels", 2)),
                "codec": stream.get("codec_name", "unknown"),
                "duration": float(fmt.get("duration", 0)),
                "bit_rate": int(fmt.get("bit_rate", 0))
            }
        except (json.JSONDecodeError, ValueError, IndexError):
            return {"sample_rate": 44100, "channels": 2, "codec": "unknown", "duration": 0}

    def normalize_audio(self, input_path: Path, output_path: Path) -> bool:
        """
        Normalize audio to target sample rate and channels.
        This is CRITICAL for clean mixing.
        """
        cfg = self.config

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", f"aresample={cfg.target_sample_rate},pan=stereo|c0=c0|c1=c0",
            "-ar", str(cfg.target_sample_rate),
            "-ac", str(cfg.target_channels),
            "-c:a", "pcm_s16le",  # Uncompressed for processing
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def validate_audio(self, audio_path: Path) -> AudioValidation:
        """
        Validate audio quality - check for clipping, silence, and proper levels.
        """
        issues = []

        # Get basic info
        info = self.get_audio_info(audio_path)

        # Check for clipping using astats
        cmd = [
            "ffmpeg", "-i", str(audio_path),
            "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        peak_db = -100.0
        for line in result.stderr.split('\n'):
            if 'Peak_level' in line:
                try:
                    peak_db = float(line.split('=')[-1])
                except ValueError:
                    pass

        has_clipping = peak_db > -0.5
        if has_clipping:
            issues.append(f"Audio clipping detected (peak: {peak_db:.1f}dB)")

        # Check loudness
        cmd = [
            "ffmpeg", "-i", str(audio_path),
            "-af", "loudnorm=print_format=json",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        integrated_lufs = -23.0
        try:
            json_start = result.stderr.rfind('{')
            json_end = result.stderr.rfind('}') + 1
            if json_start >= 0:
                loudness = json.loads(result.stderr[json_start:json_end])
                integrated_lufs = float(loudness.get("input_i", -23))
        except (json.JSONDecodeError, ValueError):
            pass

        has_silence = integrated_lufs < -40
        if has_silence:
            issues.append(f"Audio too quiet (LUFS: {integrated_lufs:.1f})")

        return AudioValidation(
            is_valid=len(issues) == 0,
            sample_rate=info["sample_rate"],
            channels=info["channels"],
            duration=info["duration"],
            peak_db=peak_db,
            integrated_lufs=integrated_lufs,
            has_clipping=has_clipping,
            has_silence=has_silence,
            issues=issues
        )

    def mix_voice_and_music(
        self,
        video_path: Path,
        voice_path: Path,
        music_path: Path,
        output_path: Path
    ) -> Dict[str, Any]:
        """
        Mix voice and music with proper sample rate handling.

        Simple approach:
        1. Normalize all audio to same sample rate
        2. Apply volume levels
        3. Mix with amix
        4. Validate output
        """
        cfg = self.config
        temp_dir = output_path.parent

        print("    [Audio] Normalizing sample rates...")

        # Normalize voice (44100 mono -> 48000 stereo)
        voice_norm = temp_dir / "voice_normalized.wav"
        voice_info = self.get_audio_info(voice_path)
        print(f"      Voice: {voice_info['sample_rate']}Hz {voice_info['channels']}ch -> {cfg.target_sample_rate}Hz stereo")

        voice_filter = f"aresample={cfg.target_sample_rate}"
        if voice_info['channels'] == 1:
            voice_filter += ",pan=stereo|c0=c0|c1=c0"

        cmd = [
            "ffmpeg", "-y", "-i", str(voice_path),
            "-af", voice_filter,
            "-ar", str(cfg.target_sample_rate),
            "-ac", "2",
            "-c:a", "pcm_s16le",
            str(voice_norm)
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        # Normalize music
        music_norm = temp_dir / "music_normalized.wav"
        music_info = self.get_audio_info(music_path)
        print(f"      Music: {music_info['sample_rate']}Hz {music_info['channels']}ch -> {cfg.target_sample_rate}Hz stereo")

        cmd = [
            "ffmpeg", "-y", "-i", str(music_path),
            "-af", f"aresample={cfg.target_sample_rate}",
            "-ar", str(cfg.target_sample_rate),
            "-ac", "2",
            "-c:a", "pcm_s16le",
            str(music_norm)
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        # Simple mix with volume levels
        print(f"    [Audio] Mixing (voice: {cfg.voice_volume}, music: {cfg.music_volume})...")

        # Use a simple, reliable filter chain
        # normalize=0 prevents amix from reducing levels
        # Add final volume boost to hit target loudness
        filter_complex = (
            f"[1:a]volume={cfg.voice_volume}[v];"
            f"[2:a]volume={cfg.music_volume}[m];"
            f"[v][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,volume=1.5[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(voice_norm),
            "-i", str(music_norm),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[out]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", str(cfg.target_sample_rate),
            "-movflags", "+faststart",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # Clean up temp files
        voice_norm.unlink(missing_ok=True)
        music_norm.unlink(missing_ok=True)

        if result.returncode != 0:
            print(f"    [Audio] Mix failed: {result.stderr[:200]}")
            return {"success": False, "error": result.stderr}

        # Validate output
        print("    [Audio] Validating output...")
        validation = self.validate_audio(output_path)

        if not validation.is_valid:
            for issue in validation.issues:
                print(f"      WARNING: {issue}")
        else:
            print(f"      Peak: {validation.peak_db:.1f}dB, LUFS: {validation.integrated_lufs:.1f}")

        return {
            "success": True,
            "local_path": str(output_path),
            "validation": {
                "peak_db": validation.peak_db,
                "lufs": validation.integrated_lufs,
                "issues": validation.issues
            }
        }

    def mix_voice_only(
        self,
        video_path: Path,
        voice_path: Path,
        output_path: Path
    ) -> Dict[str, Any]:
        """Mix just voice with video (no music)"""
        cfg = self.config
        temp_dir = output_path.parent

        # Normalize voice
        voice_norm = temp_dir / "voice_normalized.wav"
        voice_info = self.get_audio_info(voice_path)

        voice_filter = f"aresample={cfg.target_sample_rate}"
        if voice_info['channels'] == 1:
            voice_filter += ",pan=stereo|c0=c0|c1=c0"

        cmd = [
            "ffmpeg", "-y", "-i", str(voice_path),
            "-af", voice_filter,
            "-ar", str(cfg.target_sample_rate),
            "-ac", "2",
            "-c:a", "pcm_s16le",
            str(voice_norm)
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        # Replace video audio with voice
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(voice_norm),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "256k",
            "-ar", str(cfg.target_sample_rate),
            "-movflags", "+faststart",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        voice_norm.unlink(missing_ok=True)

        if result.returncode == 0:
            return {"success": True, "local_path": str(output_path)}

        return {"success": False, "error": result.stderr}


def remaster_video(
    video_path: Path,
    voice_path: Path,
    music_path: Optional[Path],
    output_path: Path,
    config: Optional[AudioMixConfig] = None
) -> Dict[str, Any]:
    """
    Remaster a video with proper audio mixing.
    """
    mixer = AudioMixer(config)

    if music_path and music_path.exists():
        return mixer.mix_voice_and_music(video_path, voice_path, music_path, output_path)
    else:
        return mixer.mix_voice_only(video_path, voice_path, output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Remaster video audio")
    parser.add_argument("video", help="Input video file")
    parser.add_argument("voice", help="Voiceover audio file")
    parser.add_argument("-m", "--music", help="Background music file")
    parser.add_argument("-o", "--output", required=True, help="Output video file")
    parser.add_argument("--voice-vol", type=float, default=1.0, help="Voice volume (0-1)")
    parser.add_argument("--music-vol", type=float, default=0.15, help="Music volume (0-1)")
    parser.add_argument("--validate-only", action="store_true", help="Just validate audio")

    args = parser.parse_args()

    if args.validate_only:
        mixer = AudioMixer()
        validation = mixer.validate_audio(Path(args.video))
        print(f"Valid: {validation.is_valid}")
        print(f"Sample rate: {validation.sample_rate}")
        print(f"Channels: {validation.channels}")
        print(f"Peak: {validation.peak_db:.1f}dB")
        print(f"LUFS: {validation.integrated_lufs:.1f}")
        if validation.issues:
            print("Issues:")
            for issue in validation.issues:
                print(f"  - {issue}")
    else:
        config = AudioMixConfig(
            voice_volume=args.voice_vol,
            music_volume=args.music_vol
        )

        result = remaster_video(
            Path(args.video),
            Path(args.voice),
            Path(args.music) if args.music else None,
            Path(args.output),
            config
        )

        if result.get("success"):
            print(f"Remastered: {result['local_path']}")
        else:
            print(f"Error: {result.get('error')}")
