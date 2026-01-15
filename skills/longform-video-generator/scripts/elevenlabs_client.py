#!/usr/bin/env python3
"""
ElevenLabs API client for text-to-speech with precise timestamps.

Provides word-level timing information for video synchronization.
"""

import os
import json
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class WordTiming:
    """Timing information for a word"""
    text: str
    start: float  # seconds
    end: float    # seconds

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class SentenceTiming:
    """Timing information for a sentence/segment"""
    text: str
    start: float
    end: float
    words: List[WordTiming] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class VoiceoverResult:
    """Result from voiceover generation"""
    success: bool
    audio_path: Optional[Path] = None
    duration: float = 0.0
    sentences: List[SentenceTiming] = field(default_factory=list)
    words: List[WordTiming] = field(default_factory=list)
    raw_alignment: Optional[Dict] = None
    error: Optional[str] = None


class ElevenLabsClient:
    """
    ElevenLabs API client with timestamp support.

    Uses the with-timestamps endpoint to get character-level timing,
    then processes into word-level timing for video synchronization.
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    # Default voices
    VOICES = {
        "adam": "pNInz6obpgDQGcFmaJgB",      # Deep male
        "rachel": "21m00Tcm4TlvDq8ikWAM",    # Female
        "josh": "TxGEqnHWrfWFTfGW9XjX",      # Young male
        "bella": "EXAVITQu4vr4xnSDxMaL",     # Female
        "antoni": "ErXwobaYiN019PkySvjV",    # Male
        "elli": "MF3mGyEYCl7XYWbV9V6O",      # Female
        "sam": "yoZ06aMxZJJ28mfd3POQ",       # Male narrator
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ElevenLabs API key required")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    def generate_voiceover_with_timestamps(
        self,
        text: str,
        output_path: Path,
        voice: str = "josh",
        model_id: str = "eleven_multilingual_v2"
    ) -> VoiceoverResult:
        """
        Generate voiceover with character-level timestamps.

        Returns audio file and timing information for synchronization.
        """
        voice_id = self.VOICES.get(voice, voice)  # Allow voice ID or name

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}/with-timestamps"

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }

        params = {
            "output_format": "mp3_44100_128"
        }

        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                params=params,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()

            # Decode and save audio
            audio_base64 = data.get("audio_base64", "")
            if audio_base64:
                audio_bytes = base64.b64decode(audio_base64)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)

            # Parse alignment into word timings
            alignment = data.get("alignment", {})
            words, sentences = self._parse_alignment(text, alignment)

            # Calculate total duration
            duration = 0.0
            if words:
                duration = words[-1].end

            return VoiceoverResult(
                success=True,
                audio_path=output_path,
                duration=duration,
                sentences=sentences,
                words=words,
                raw_alignment=alignment
            )

        except requests.exceptions.RequestException as e:
            return VoiceoverResult(
                success=False,
                error=f"API request failed: {str(e)}"
            )
        except Exception as e:
            return VoiceoverResult(
                success=False,
                error=f"Error: {str(e)}"
            )

    def _parse_alignment(
        self,
        text: str,
        alignment: Dict
    ) -> tuple[List[WordTiming], List[SentenceTiming]]:
        """
        Parse character-level alignment into word and sentence timings.
        """
        characters = alignment.get("characters", [])
        start_times = alignment.get("character_start_times_seconds", [])
        end_times = alignment.get("character_end_times_seconds", [])

        if not characters or not start_times or not end_times:
            return [], []

        words = []
        current_word = ""
        word_start = None

        for i, char in enumerate(characters):
            if char.strip():  # Non-whitespace
                if word_start is None:
                    word_start = start_times[i]
                current_word += char
            else:  # Whitespace - end of word
                if current_word and word_start is not None:
                    words.append(WordTiming(
                        text=current_word,
                        start=word_start,
                        end=end_times[i - 1] if i > 0 else start_times[i]
                    ))
                current_word = ""
                word_start = None

        # Don't forget last word
        if current_word and word_start is not None:
            words.append(WordTiming(
                text=current_word,
                start=word_start,
                end=end_times[-1]
            ))

        # Group into sentences (split on . ! ?)
        sentences = self._group_into_sentences(text, words)

        return words, sentences

    def _group_into_sentences(
        self,
        text: str,
        words: List[WordTiming]
    ) -> List[SentenceTiming]:
        """Group words into sentences based on punctuation."""
        if not words:
            return []

        sentences = []
        current_sentence_words = []
        current_sentence_text = ""

        for word in words:
            current_sentence_words.append(word)
            current_sentence_text += word.text + " "

            # Check if this word ends a sentence
            if word.text and word.text[-1] in '.!?':
                sentences.append(SentenceTiming(
                    text=current_sentence_text.strip(),
                    start=current_sentence_words[0].start,
                    end=current_sentence_words[-1].end,
                    words=current_sentence_words.copy()
                ))
                current_sentence_words = []
                current_sentence_text = ""

        # Remaining words as final sentence
        if current_sentence_words:
            sentences.append(SentenceTiming(
                text=current_sentence_text.strip(),
                start=current_sentence_words[0].start,
                end=current_sentence_words[-1].end,
                words=current_sentence_words
            ))

        return sentences

    def transcribe_audio(
        self,
        audio_path: Path,
        timestamps_granularity: str = "word"
    ) -> Dict[str, Any]:
        """
        Transcribe audio using Speech-to-Text API.
        Returns word-level timestamps.
        """
        url = f"{self.BASE_URL}/speech-to-text"

        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/mpeg")}
            data = {
                "model_id": "scribe_v1",
                "timestamps_granularity": timestamps_granularity
            }

            headers = {"xi-api-key": self.api_key}

            try:
                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {"error": str(e)}


def generate_voiceover_with_timing(
    text: str,
    output_path: Path,
    api_key: str,
    voice: str = "josh"
) -> VoiceoverResult:
    """
    Convenience function to generate voiceover with timestamps.
    """
    client = ElevenLabsClient(api_key)
    return client.generate_voiceover_with_timestamps(text, output_path, voice)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate voiceover with timestamps")
    parser.add_argument("text", help="Text to convert to speech")
    parser.add_argument("-o", "--output", required=True, help="Output audio file")
    parser.add_argument("-k", "--api-key", required=True, help="ElevenLabs API key")
    parser.add_argument("-v", "--voice", default="josh", help="Voice name or ID")
    parser.add_argument("--json", action="store_true", help="Output timing as JSON")

    args = parser.parse_args()

    result = generate_voiceover_with_timing(
        args.text,
        Path(args.output),
        args.api_key,
        args.voice
    )

    if result.success:
        print(f"Audio saved: {result.audio_path}")
        print(f"Duration: {result.duration:.2f}s")
        print(f"Words: {len(result.words)}")
        print(f"Sentences: {len(result.sentences)}")

        if args.json:
            timing_data = {
                "duration": result.duration,
                "words": [{"text": w.text, "start": w.start, "end": w.end} for w in result.words],
                "sentences": [{"text": s.text, "start": s.start, "end": s.end} for s in result.sentences]
            }
            print(json.dumps(timing_data, indent=2))
        else:
            print("\nSentence timings:")
            for i, s in enumerate(result.sentences):
                print(f"  {i+1}. [{s.start:.2f}s - {s.end:.2f}s] {s.text[:50]}...")
    else:
        print(f"Error: {result.error}")
