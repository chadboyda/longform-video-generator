#!/usr/bin/env python3
"""
Professional video generation pipeline.
Orchestrates: Script → Storyboard → Video → Audio → Assembly

Fully generic - takes a JSON script file as input.
Includes Director review process for quality control.
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))
from fal_wrapper import FalClient, FalConfig, MODELS
from story_generator import VideoScript, Shot, load_script
from director import Director, DirectorConfig, ReviewStatus
from audio_mixer import AudioMixer, AudioMixConfig
from elevenlabs_client import ElevenLabsClient, VoiceoverResult
from timeline_assembler import TimelineAssembler, assemble_with_timing


@dataclass
class PipelineConfig:
    """Configuration for the video pipeline"""
    output_dir: Path
    image_model: str = "nano_banana_pro"
    video_model: str = "veo31_i2v"
    resolution: str = "720p"
    aspect_ratio: str = "16:9"
    generate_voiceover: bool = True
    generate_music: bool = True
    enable_director: bool = True  # Enable quality review
    max_revisions: int = 2  # Max regeneration attempts
    elevenlabs_api_key: Optional[str] = None  # For direct ElevenLabs API calls
    voiceover_voice: str = "josh"  # ElevenLabs voice


class VideoPipeline:
    """
    Professional video generation pipeline.

    Flow:
    1. Load script from JSON file (with aesthetic, characters, shots)
    2. Generate storyboard images (Nano Banana Pro)
       - Director reviews each image
       - Uses nano-banana-pro/edit for character consistency
    3. Generate videos from storyboard images (Veo 3.1 i2v)
    4. Generate audio tracks (voiceover, music)
    5. Assemble final video with proper layering
    """

    def __init__(self, client: FalClient, config: PipelineConfig, script: VideoScript):
        self.client = client
        self.config = config
        self.script = script

        # Initialize director for quality control
        director_config = DirectorConfig(
            min_quality_score=0.7,
            max_revisions=config.max_revisions,
            auto_approve=not config.enable_director
        )
        self.director = Director(client, director_config)

        # Create directory structure
        self.dirs = {
            "project": config.output_dir,
            "storyboard": config.output_dir / "storyboard",
            "video_clips": config.output_dir / "video_clips",
            "audio": config.output_dir / "audio",
            "temp": config.output_dir / "temp",
            "output": config.output_dir / "output"
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)

    def generate_storyboard_image(self, shot: Shot, shot_index: int, revision: int = 0) -> Dict[str, Any]:
        """
        Generate a storyboard image with director review.
        Uses character references for consistency when available.
        """

        # Build complete prompt with aesthetic
        full_prompt = self.script.get_full_prompt(shot)

        print(f"  [Storyboard {shot_index + 1}] Generating image...")
        if revision > 0:
            print(f"    (Revision {revision})")
        print(f"    Prompt: {full_prompt[:100]}...")

        # Check for character references
        character = shot.character
        ref_urls = []
        if character:
            ref_urls = self.director.get_approved_refs(character)
            if ref_urls:
                print(f"    Using {len(ref_urls)} reference(s) for: {character}")

        try:
            if ref_urls:
                # Use nano-banana-pro/edit for character consistency
                model_id = MODELS.get("nano_banana_pro_edit", "fal-ai/nano-banana-pro/edit")
                arguments = {
                    "prompt": full_prompt,
                    "image_urls": ref_urls,
                    "aspect_ratio": self.config.aspect_ratio,
                    "resolution": "1K",
                    "num_images": 1,
                    "output_format": "png"
                }
            else:
                # Standard generation
                model_id = MODELS.get(self.config.image_model, self.config.image_model)
                arguments = {
                    "prompt": full_prompt,
                    "aspect_ratio": self.config.aspect_ratio,
                    "resolution": "1K",
                    "num_images": 1,
                    "output_format": "png"
                }

            result = self.client.generate(model_id, arguments, use_cache=False)

            images = result.get("images", [])
            if images and images[0].get("url"):
                output_path = self.dirs["storyboard"] / f"frame_{shot_index:03d}.png"
                image_url = images[0]["url"]
                self.client.download_file(image_url, output_path)

                # Director review
                review = self.director.review_image(
                    image_path=output_path,
                    image_url=image_url,
                    shot_description=shot.description,
                    character_name=character,
                    aesthetic_prompt=self.script.aesthetic.to_prompt_suffix(),
                    existing_refs=ref_urls
                )

                if review.status == ReviewStatus.APPROVED:
                    # Approve as character reference if first appearance
                    if character and not ref_urls:
                        self.director.approve_character_reference(character, image_url, output_path)
                        print(f"    [Director] First {character} appearance approved as reference")

                    return {
                        "success": True,
                        "url": image_url,
                        "local_path": str(output_path),
                        "shot_index": shot_index,
                        "character": character,
                        "review_score": review.score
                    }
                elif review.status == ReviewStatus.NEEDS_REVISION and revision < self.config.max_revisions:
                    print(f"    [Director] Revision needed: {review.feedback}")
                    return self.generate_storyboard_image(shot, shot_index, revision + 1)
                else:
                    # Proceed with warning
                    print(f"    [Director] Warning: {review.feedback}")
                    return {
                        "success": True,
                        "url": image_url,
                        "local_path": str(output_path),
                        "shot_index": shot_index,
                        "character": character,
                        "review_score": review.score,
                        "warning": review.feedback
                    }

        except Exception as e:
            print(f"    Error: {e}")

        return {"success": False, "error": str(e) if 'e' in dir() else "Unknown error", "shot_index": shot_index}

    def generate_video_from_image(self, shot: Shot, image_path: Path, shot_index: int) -> Dict[str, Any]:
        """Generate video from storyboard image"""

        # Build motion prompt
        motion_parts = []
        if shot.camera_movement.value != "static":
            motion_parts.append(shot.camera_movement.value)
        if shot.motion_prompt:
            motion_parts.append(shot.motion_prompt)
        motion_prompt = ". ".join(motion_parts) if motion_parts else "subtle natural movement"

        print(f"  [Video {shot_index + 1}] Generating from storyboard...")
        print(f"    Motion: {motion_prompt[:80]}...")

        # Upload image
        try:
            import fal_client as fal
            image_url = fal.upload_file(str(image_path))
        except Exception as e:
            print(f"    Error uploading image: {e}")
            import base64
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            image_url = f"data:image/png;base64,{image_data}"

        model_id = MODELS.get(self.config.video_model, self.config.video_model)

        # Veo only supports 4s, 6s, 8s
        raw_duration = shot.duration_seconds
        if raw_duration <= 5:
            duration = 4
        elif raw_duration <= 7:
            duration = 6
        else:
            duration = 8
        duration_str = f"{duration}s"

        arguments = {
            "prompt": motion_prompt,
            "image_url": image_url,
            "duration": duration_str,
            "aspect_ratio": self.config.aspect_ratio,
        }

        try:
            result = self.client.generate(model_id, arguments, use_cache=False)

            video = result.get("video", {})
            if video.get("url"):
                output_path = self.dirs["video_clips"] / f"clip_{shot_index:03d}.mp4"
                self.client.download_file(video["url"], output_path)
                return {
                    "success": True,
                    "url": video["url"],
                    "local_path": str(output_path),
                    "shot_index": shot_index,
                    "duration": duration
                }
        except Exception as e:
            print(f"    Error: {e}")

        return {"success": False, "error": str(e) if 'e' in dir() else "Unknown error", "shot_index": shot_index}

    def generate_voiceover(self) -> Dict[str, Any]:
        """
        Generate voiceover audio with word-level timestamps.

        Uses ElevenLabs API directly to get precise timing for
        video synchronization.
        """
        vo_parts = []
        for shot in self.script.shots:
            if shot.voiceover:
                vo_parts.append(shot.voiceover)

        if not vo_parts:
            return {"success": False, "error": "No voiceover text in script"}

        full_voiceover = " ".join(vo_parts)
        print(f"  [Voiceover] Generating narration with timestamps...")
        print(f"    Text: {full_voiceover[:100]}...")

        # Use ElevenLabs directly if API key provided
        if self.config.elevenlabs_api_key:
            try:
                client = ElevenLabsClient(self.config.elevenlabs_api_key)
                output_path = self.dirs["audio"] / "voiceover.mp3"

                result = client.generate_voiceover_with_timestamps(
                    full_voiceover,
                    output_path,
                    voice=self.config.voiceover_voice
                )

                if result.success:
                    # Map sentences to shot timings
                    shot_timings = self._map_sentences_to_shots(result.sentences, vo_parts)

                    # Save timing data
                    timing_path = self.dirs["audio"] / "voiceover_timing.json"
                    import json
                    with open(timing_path, "w") as f:
                        json.dump({
                            "duration": result.duration,
                            "shots": shot_timings,
                            "sentences": [{"text": s.text, "start": s.start, "end": s.end} for s in result.sentences]
                        }, f, indent=2)

                    print(f"    Duration: {result.duration:.2f}s")
                    print(f"    Sentences: {len(result.sentences)}")

                    return {
                        "success": True,
                        "local_path": str(output_path),
                        "duration": result.duration,
                        "shot_timings": shot_timings
                    }
                else:
                    print(f"    ElevenLabs error: {result.error}")
            except Exception as e:
                print(f"    ElevenLabs error: {e}")

        # Fallback to fal.ai
        print("    Falling back to fal.ai TTS (no timestamps)...")
        model_id = MODELS.get("elevenlabs_tts", "fal-ai/elevenlabs/tts/turbo-v2.5")

        arguments = {
            "text": full_voiceover,
            "voice": "Brian",
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": 0.95
        }

        try:
            result = self.client.generate(model_id, arguments, use_cache=False)
            audio = result.get("audio", {})
            if audio.get("url"):
                output_path = self.dirs["audio"] / "voiceover.mp3"
                self.client.download_file(audio["url"], output_path)
                return {"success": True, "url": audio["url"], "local_path": str(output_path)}
        except Exception as e:
            print(f"    Error: {e}")

        return {"success": False, "error": str(e) if 'e' in dir() else "Unknown error"}

    def _map_sentences_to_shots(self, sentences, vo_parts) -> List[Dict]:
        """Map generated sentences back to shot voiceovers for timing."""
        shot_timings = []
        sentence_idx = 0

        for shot_idx, shot_vo in enumerate(vo_parts):
            shot_start = None
            shot_end = None

            # Find sentences that belong to this shot
            remaining = shot_vo.lower()
            while sentence_idx < len(sentences) and remaining:
                sentence = sentences[sentence_idx]
                sent_text = sentence.text.lower().rstrip('.')

                # Check if sentence is part of this shot's voiceover
                if sent_text in remaining or remaining.startswith(sent_text[:min(10, len(sent_text))]):
                    if shot_start is None:
                        shot_start = sentence.start
                    shot_end = sentence.end
                    remaining = remaining.replace(sent_text, '', 1).strip(' .')
                    sentence_idx += 1
                else:
                    break

            if shot_start is not None:
                shot_timings.append({
                    "shot": shot_idx + 1,
                    "text": shot_vo,
                    "start": shot_start,
                    "end": shot_end,
                    "duration": shot_end - shot_start
                })

        return shot_timings

    def generate_music(self, retry_count: int = 0) -> Dict[str, Any]:
        """Generate background music with self-healing on content policy failures"""

        music_prompt = self.script.music_style
        if self.script.music_mood_progression:
            music_prompt += f". Mood progression: {', '.join(self.script.music_mood_progression)}"

        # Self-healing: sanitize prompt on retry
        if retry_count > 0:
            # Remove potentially flagged words and simplify
            flagged_words = [
                "bass drop", "drop", "explosive", "intense", "heavy", "aggressive",
                "dark", "tension", "powerful drums", "massive", "epic battle"
            ]
            clean_prompt = music_prompt.lower()
            for word in flagged_words:
                clean_prompt = clean_prompt.replace(word.lower(), "")
            # Rebuild with safe alternatives
            music_prompt = f"Inspiring instrumental music, building energy, uplifting and motivational, cinematic quality"
            print(f"    [Self-heal] Retry {retry_count} with sanitized prompt")

        total_duration_ms = sum(s.duration_seconds for s in self.script.shots) * 1000
        total_duration_ms = int(min(total_duration_ms + 5000, 300000))

        print(f"  [Music] Generating background track...")
        print(f"    Style: {music_prompt[:80]}...")

        model_id = MODELS.get("elevenlabs_music", "fal-ai/elevenlabs/music")

        arguments = {
            "prompt": music_prompt,
            "music_length_ms": total_duration_ms,
            "force_instrumental": True,
            "output_format": "mp3_44100_128"
        }

        try:
            result = self.client.generate(model_id, arguments, use_cache=False)

            audio = result.get("audio", {})
            if audio.get("url"):
                output_path = self.dirs["audio"] / "background_music.mp3"
                self.client.download_file(audio["url"], output_path)
                return {"success": True, "url": audio["url"], "local_path": str(output_path)}
        except Exception as e:
            error_str = str(e).lower()
            # Self-heal: retry with sanitized prompt on content policy violation
            if "content" in error_str or "policy" in error_str or "flagged" in error_str:
                if retry_count < 2:
                    print(f"    [Self-heal] Content policy error, retrying with cleaner prompt...")
                    return self.generate_music(retry_count + 1)
            print(f"    Error: {e}")

        return {"success": False, "error": str(e) if 'e' in dir() else "Unknown error"}

    def assemble_video(
        self,
        video_clips: List[Path],
        voiceover_path: Optional[Path],
        music_path: Optional[Path],
        shot_timings: Optional[List[Dict]] = None,
        voiceover_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Assemble final video with timeline-based synchronization.

        If shot_timings provided (from ElevenLabs timestamps):
        - Trims each video clip to match voiceover timing
        - Ensures perfect audio/video sync

        Otherwise falls back to simple concatenation.
        """
        final_path = self.dirs["output"] / f"{self.script.title}.mp4"

        # Use timeline assembler if we have timing data
        if shot_timings and voiceover_path and voiceover_duration:
            print(f"  [Assembly] Timeline-based assembly with {len(video_clips)} clips...")

            segments = [
                {"text": t["text"], "start": t["start"], "end": t["end"]}
                for t in shot_timings
            ]

            result = assemble_with_timing(
                segments,
                video_clips,
                voiceover_path,
                voiceover_duration,
                final_path,
                music_path=music_path,
                temp_dir=self.dirs["temp"]
            )

            return result

        # Fallback: simple concatenation without timing
        print(f"  [Assembly] Simple concatenation of {len(video_clips)} clips...")

        concat_path = self.dirs["temp"] / "concatenated.mp4"
        list_file = self.dirs["temp"] / "concat_list.txt"

        with open(list_file, 'w') as f:
            for clip in video_clips:
                f.write(f"file '{clip.absolute()}'\n")

        concat_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(concat_path)
        ]

        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    Concat error: {result.stderr[:200]}")
            return {"success": False, "error": "Failed to concatenate videos"}

        # Audio mixing
        audio_config = AudioMixConfig(
            voice_volume=1.0,
            music_volume=0.18,
            target_sample_rate=48000,
            target_channels=2
        )

        mixer = AudioMixer(audio_config)

        if voiceover_path and voiceover_path.exists() and music_path and music_path.exists():
            print("    Mixing voiceover and music...")
            result = mixer.mix_voice_and_music(
                concat_path,
                voiceover_path,
                music_path,
                final_path
            )
        elif voiceover_path and voiceover_path.exists():
            print("    Adding voiceover...")
            result = mixer.mix_voice_only(
                concat_path,
                voiceover_path,
                final_path
            )
        else:
            import shutil
            shutil.copy(concat_path, final_path)
            result = {"success": True, "local_path": str(final_path)}

        if result.get("success") and final_path.exists():
            return {"success": True, "local_path": str(final_path)}

        return result if not result.get("success") else {"success": False, "error": "Final video not created"}

    def run(self) -> Dict[str, Any]:
        """Run the complete pipeline"""

        results = {
            "script": self.script.to_dict(),
            "storyboard": [],
            "videos": [],
            "voiceover": None,
            "music": None,
            "output": None,
            "director_summary": None,
            "errors": []
        }

        print("\n" + "=" * 60)
        print("PHASE 1: GENERATING STORYBOARD IMAGES")
        print("=" * 60)

        storyboard_images = []
        for i, shot in enumerate(self.script.shots):
            result = self.generate_storyboard_image(shot, i)
            results["storyboard"].append(result)
            if result.get("success"):
                storyboard_images.append(Path(result["local_path"]))
            else:
                results["errors"].append(f"Storyboard {i}: {result.get('error')}")

        if not storyboard_images:
            results["errors"].append("No storyboard images generated")
            return results

        print("\n" + "=" * 60)
        print("PHASE 2: GENERATING VIDEOS FROM STORYBOARD")
        print("=" * 60)

        video_clips = []
        for i, (shot, image_path) in enumerate(zip(self.script.shots, storyboard_images)):
            result = self.generate_video_from_image(shot, image_path, i)
            results["videos"].append(result)
            if result.get("success"):
                video_clips.append(Path(result["local_path"]))
            else:
                results["errors"].append(f"Video {i}: {result.get('error')}")

        if not video_clips:
            results["errors"].append("No video clips generated")
            return results

        print("\n" + "=" * 60)
        print("PHASE 3: GENERATING AUDIO")
        print("=" * 60)

        voiceover_path = None
        music_path = None
        shot_timings = None
        voiceover_duration = None

        if self.config.generate_voiceover:
            vo_result = self.generate_voiceover()
            results["voiceover"] = vo_result
            if vo_result.get("success"):
                voiceover_path = Path(vo_result["local_path"])
                shot_timings = vo_result.get("shot_timings")
                voiceover_duration = vo_result.get("duration")

        if self.config.generate_music:
            music_result = self.generate_music()
            results["music"] = music_result
            if music_result.get("success"):
                music_path = Path(music_result["local_path"])

        print("\n" + "=" * 60)
        print("PHASE 4: ASSEMBLING FINAL VIDEO")
        print("=" * 60)

        assembly_result = self.assemble_video(
            video_clips,
            voiceover_path,
            music_path,
            shot_timings=shot_timings,
            voiceover_duration=voiceover_duration
        )
        results["output"] = assembly_result

        # Director summary
        results["director_summary"] = self.director.get_review_summary()

        if assembly_result.get("success"):
            print("\n" + "=" * 60)
            print("PIPELINE COMPLETE")
            print("=" * 60)
            print(f"Output: {assembly_result['local_path']}")

        return results


def main():
    parser = argparse.ArgumentParser(description="Professional video generation pipeline")
    parser.add_argument("script", help="JSON script file defining the video")
    parser.add_argument("-o", "--output", default="./video_output", help="Output directory")
    parser.add_argument("--image-model", default="nano_banana_pro",
                       choices=["nano_banana_pro"])
    parser.add_argument("--video-model", default="veo31_i2v",
                       choices=["veo31_i2v", "veo3_i2v", "kling_pro"])
    parser.add_argument("--no-voiceover", action="store_true")
    parser.add_argument("--no-music", action="store_true")
    parser.add_argument("--no-director", action="store_true", help="Disable director review")
    parser.add_argument("--max-revisions", type=int, default=2, help="Max revision attempts per shot")
    parser.add_argument("--elevenlabs-key", help="ElevenLabs API key for timed voiceover")
    parser.add_argument("--voice", default="josh", help="ElevenLabs voice name")

    args = parser.parse_args()

    api_key = os.environ.get("FAL_KEY")
    elevenlabs_key = args.elevenlabs_key or os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: Set FAL_KEY environment variable")
        sys.exit(1)

    # Load script
    if not Path(args.script).exists():
        print(f"Error: Script file not found: {args.script}")
        sys.exit(1)

    print(f"Loading script: {args.script}")
    script = load_script(args.script)
    print(f"Title: {script.title}")
    print(f"Duration: {script.target_duration_seconds}s")
    print(f"Shots: {len(script.shots)}")
    print(f"Aesthetic: {script.aesthetic.name}")

    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output) / f"video_{timestamp}"

    # Configure pipeline
    config = PipelineConfig(
        output_dir=output_dir,
        image_model=args.image_model,
        video_model=args.video_model,
        generate_voiceover=not args.no_voiceover,
        generate_music=not args.no_music,
        enable_director=not args.no_director,
        max_revisions=args.max_revisions,
        elevenlabs_api_key=elevenlabs_key,
        voiceover_voice=args.voice
    )

    if elevenlabs_key:
        print(f"Using ElevenLabs for timed voiceover (voice: {args.voice})")

    # Initialize client and pipeline
    fal_config = FalConfig(api_key=api_key, max_concurrent=1)
    client = FalClient(fal_config)
    pipeline = VideoPipeline(client, config, script)

    # Run pipeline
    results = pipeline.run()

    # Save results
    results_path = output_dir / "pipeline_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults saved to: {results_path}")

    if results.get("errors"):
        print(f"\nWarnings/Errors: {len(results['errors'])}")
        for err in results["errors"]:
            print(f"  - {err}")

    if results.get("director_summary"):
        summary = results["director_summary"]
        print(f"\nDirector Summary:")
        print(f"  Reviews: {summary.get('total', 0)}")
        print(f"  Avg Score: {summary.get('avg_score', 0):.2f}")
        print(f"  Approved: {summary.get('approved_count', 0)}")

    sys.exit(0 if results.get("output", {}).get("success") else 1)


if __name__ == "__main__":
    main()
