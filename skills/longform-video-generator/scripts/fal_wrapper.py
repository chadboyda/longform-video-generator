#!/usr/bin/env python3
"""
fal.ai API client wrapper for video, image, and audio generation.
Handles authentication, rate limiting, retries, and progress tracking.
"""

import os
import sys
import time
import json
import hashlib
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, List

# Check for fal_client library
try:
    import fal_client
except ImportError:
    print("Installing fal-client...")
    os.system(f"{sys.executable} -m pip install fal-client -q")
    import fal_client


@dataclass
class FalConfig:
    """Configuration for fal.ai client"""
    api_key: str
    max_retries: int = 3
    max_concurrent: int = 2
    cache_dir: Optional[Path] = None
    output_dir: Optional[Path] = None


class RateLimiter:
    """Rate limiter for concurrent API requests"""
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self.active_requests = 0

    def acquire(self):
        while self.active_requests >= self.max_concurrent:
            time.sleep(0.1)
        self.active_requests += 1

    def release(self):
        self.active_requests = max(0, self.active_requests - 1)


class FalClient:
    """Wrapper for fal.ai API with retry logic and caching"""

    def __init__(self, config: FalConfig):
        self.config = config
        os.environ['FAL_KEY'] = config.api_key
        self.rate_limiter = RateLimiter(config.max_concurrent)
        self.cache: Dict[str, Any] = {}

        if config.output_dir:
            config.output_dir.mkdir(parents=True, exist_ok=True)
        if config.cache_dir:
            config.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, model: str, arguments: Dict) -> str:
        """Generate cache key from model and arguments"""
        content = json.dumps({"model": model, **arguments}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _on_queue_update(self, update, progress_callback: Optional[Callable] = None):
        """Handle progress updates during generation"""
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                msg = log.get('message', str(log))
                if progress_callback:
                    progress_callback(msg)
                else:
                    print(f"  Progress: {msg}")

    def generate(
        self,
        model: str,
        arguments: Dict[str, Any],
        progress_callback: Optional[Callable] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate content using fal.ai model with retry logic.

        Args:
            model: Model ID (e.g., "fal-ai/veo3.1/fast")
            arguments: Model-specific arguments
            progress_callback: Optional callback for progress updates
            use_cache: Whether to use caching

        Returns:
            Model response dict
        """
        # Check cache
        cache_key = self._get_cache_key(model, arguments)
        if use_cache and cache_key in self.cache:
            print(f"  Using cached result for {model}")
            return self.cache[cache_key]

        self.rate_limiter.acquire()
        try:
            for attempt in range(self.config.max_retries):
                try:
                    # Use module-level subscribe function
                    result = fal_client.subscribe(
                        model,
                        arguments=arguments,
                        with_logs=True,
                        on_queue_update=lambda u: self._on_queue_update(u, progress_callback)
                    )

                    # Cache result
                    if use_cache:
                        self.cache[cache_key] = result

                    return result

                except Exception as e:
                    error_str = str(e).lower()
                    if "validation" in error_str or "content" in error_str or "policy" in error_str:
                        print(f"  Validation error (content policy): {e}")
                        raise
                    elif "rate" in error_str or "limit" in error_str:
                        wait_time = (2 ** attempt) * 5
                        print(f"  Rate limited. Waiting {wait_time}s...")
                        time.sleep(wait_time)
                    elif attempt == self.config.max_retries - 1:
                        raise
                    else:
                        wait_time = (2 ** attempt) * 2
                        print(f"  Retry {attempt + 1}/{self.config.max_retries} in {wait_time}s: {e}")
                        time.sleep(wait_time)

            raise Exception(f"Max retries exceeded for {model}")
        finally:
            self.rate_limiter.release()

    def download_file(self, url: str, output_path: Path) -> Path:
        """Download a file from URL to local path"""
        response = requests.get(url, stream=True)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return output_path

    def batch_generate(
        self,
        tasks: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple items concurrently respecting rate limits.

        Args:
            tasks: List of dicts with 'model' and 'arguments' keys
            progress_callback: Optional callback for progress updates

        Returns:
            List of results in same order as tasks
        """
        results = [None] * len(tasks)

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent) as executor:
            future_to_idx = {
                executor.submit(
                    self.generate,
                    task['model'],
                    task['arguments'],
                    progress_callback
                ): idx
                for idx, task in enumerate(tasks)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    print(f"  Task {idx} failed: {e}")
                    results[idx] = {"error": str(e)}

        return results


# Model endpoints - per fal.ai API specs
MODELS = {
    # Video models (text-to-video and image-to-video)
    "veo3": "fal-ai/veo3",
    "veo3_fast": "fal-ai/veo3/fast",
    "veo3_i2v": "fal-ai/veo3/image-to-video",
    "veo31_fast": "fal-ai/veo3.1/fast",
    "veo31_i2v": "fal-ai/veo3.1/image-to-video",  # duration: 4s, 6s, 8s only
    "veo31_extend": "fal-ai/veo3.1/fast/extend-video",
    "kling_pro": "fal-ai/kling-video/v2.6/pro/image-to-video",
    "minimax": "fal-ai/minimax-video/video-01-live",

    # Image models - Google Nano Banana Pro (SOTA)
    "nano_banana_pro": "fal-ai/nano-banana-pro",  # text-to-image, $0.15/img
    "nano_banana_pro_edit": "fal-ai/nano-banana-pro/edit",  # image editing

    # Audio models
    "elevenlabs_music": "fal-ai/elevenlabs/music",  # 3000-600000ms duration
    "elevenlabs_sfx": "fal-ai/elevenlabs/sound-effects",
    "elevenlabs_tts": "fal-ai/elevenlabs/tts/turbo-v2.5",  # voices: Aria, Brian, etc.
    "kokoro_tts": "fal-ai/kokoro",
}


if __name__ == "__main__":
    # Test the client
    api_key = os.environ.get("FAL_KEY")
    if not api_key:
        print("Set FAL_KEY environment variable to test")
        sys.exit(1)

    config = FalConfig(api_key=api_key)
    client = FalClient(config)

    print("Testing image generation with Nano Banana Pro...")
    result = client.generate(
        MODELS["nano_banana_pro"],
        {"prompt": "A serene mountain landscape at sunset", "aspect_ratio": "16:9", "resolution": "1K"}
    )
    print(f"Generated image: {result.get('images', [{}])[0].get('url', 'N/A')}")
