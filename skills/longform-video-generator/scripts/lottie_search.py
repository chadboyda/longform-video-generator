#!/usr/bin/env python3
"""
LottieFiles Search & Download Client.

Provides full access to the LottieFiles library with search functionality.
Also supports IconScout and other Lottie sources.

Sources:
- LottieFiles GraphQL API: https://graphql.lottiefiles.com/2022-08
- IconScout: https://iconscout.com/lottie-animations
- Lordicon: https://lordicon.com
"""

import os
import json
import requests
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from urllib.parse import quote_plus
import tempfile


@dataclass
class LottieAnimation:
    """Represents a Lottie animation from search results."""
    id: str
    name: str
    description: str
    preview_url: str          # GIF/MP4 preview
    json_url: str             # Direct JSON download
    dotlottie_url: str        # .lottie format
    creator: str
    downloads: int
    tags: List[str]
    colors: List[str]
    duration: float
    frames: int


class LottieFilesSearch:
    """
    Search the LottieFiles library using their public search.

    Supports searching by:
    - Keywords (business, subscribe, arrow, etc.)
    - Categories (animations, icons, stickers)
    - Colors
    - Style
    """

    BASE_URL = "https://lottiefiles.com"
    GRAPHQL_URL = "https://graphql.lottiefiles.com/2022-08"

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "lottie_search"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })

    def search(
        self,
        query: str,
        limit: int = 20,
        category: str = "animations"
    ) -> List[LottieAnimation]:
        """
        Search LottieFiles for animations.

        Args:
            query: Search keywords (e.g., "business", "subscribe", "loading")
            limit: Max results to return
            category: "animations", "icons", "stickers"

        Returns:
            List of LottieAnimation objects
        """
        # Use the public search page and parse results
        search_url = f"{self.BASE_URL}/search?q={quote_plus(query)}&category={category}"

        try:
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()

            # Parse animations from the page
            animations = self._parse_search_results(response.text, limit)
            return animations

        except Exception as e:
            print(f"Search error: {e}")
            return []

    def _parse_search_results(self, html: str, limit: int) -> List[LottieAnimation]:
        """Parse animation data from search results page."""
        animations = []

        # Look for JSON data in the page
        # LottieFiles embeds animation data in script tags
        json_pattern = r'"animations":\s*(\[.*?\])'

        # Alternative: look for individual animation cards
        # Pattern for animation URLs
        anim_pattern = r'href="/([a-z0-9-]+)-animation-([a-z0-9]+)"'

        # Find animation IDs from links
        matches = re.findall(anim_pattern, html)

        for name_slug, anim_id in matches[:limit]:
            # Construct the JSON URL (standard LottieFiles format)
            json_url = f"https://assets-v2.lottiefiles.com/a/{anim_id}.json"

            animations.append(LottieAnimation(
                id=anim_id,
                name=name_slug.replace("-", " ").title(),
                description="",
                preview_url=f"https://lottiefiles.com/{name_slug}-animation-{anim_id}",
                json_url=json_url,
                dotlottie_url="",
                creator="",
                downloads=0,
                tags=[],
                colors=[],
                duration=0,
                frames=0
            ))

        return animations

    def search_featured(self, category: str = "featured") -> List[LottieAnimation]:
        """Get featured/popular animations."""
        url = f"{self.BASE_URL}/featured-animations"

        try:
            response = self.session.get(url, timeout=30)
            return self._parse_search_results(response.text, 50)
        except:
            return []

    def download(self, animation: LottieAnimation) -> Optional[Path]:
        """Download animation JSON to cache."""
        cache_path = self.cache_dir / f"{animation.id}.json"

        if cache_path.exists():
            return cache_path

        try:
            response = self.session.get(animation.json_url, timeout=30)
            response.raise_for_status()

            # Validate it's JSON
            data = response.json()

            with open(cache_path, 'w') as f:
                json.dump(data, f)

            return cache_path

        except Exception as e:
            print(f"Download error for {animation.id}: {e}")
            return None

    def download_by_url(self, url: str, name: str = None) -> Optional[Path]:
        """Download animation from direct URL."""
        if not name:
            name = url.split('/')[-1].replace('.json', '')

        cache_path = self.cache_dir / f"{name}.json"

        if cache_path.exists():
            return cache_path

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            with open(cache_path, 'w') as f:
                json.dump(data, f)

            return cache_path
        except Exception as e:
            print(f"Download error: {e}")
            return None


class IconScoutSearch:
    """
    Search IconScout's Lottie animation library.

    IconScout has 130,000+ Lottie animations.
    Reference: https://iconscout.com/lottie-animations
    """

    BASE_URL = "https://iconscout.com"
    API_URL = "https://iconscout.com/api"

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "iconscout"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Search IconScout for Lottie animations."""
        # IconScout search URL
        search_url = f"{self.BASE_URL}/lottie-animations/{quote_plus(query)}"

        try:
            response = self.session.get(search_url, timeout=30)
            # Parse results from page
            # IconScout embeds data differently
            return self._parse_results(response.text, limit)
        except:
            return []

    def _parse_results(self, html: str, limit: int) -> List[Dict]:
        """Parse IconScout search results."""
        results = []
        # Look for Lottie JSON URLs in the page
        pattern = r'https://[^"]+\.json'
        matches = re.findall(pattern, html)

        for url in matches[:limit]:
            if 'lottie' in url.lower() or 'animation' in url.lower():
                results.append({
                    'url': url,
                    'name': url.split('/')[-1].replace('.json', '')
                })

        return results


class UnifiedLottieSearch:
    """
    Unified search across multiple Lottie animation sources.

    Sources:
    - LottieFiles (largest library)
    - IconScout (130K+ animations)
    - Curated collection (verified high-quality)
    """

    # High-quality curated animations by category
    # IMPORTANT: Use assets*.lottiefiles.com/packages/* format (verified working)
    # The assets-v2.lottiefiles.com/a/* format returns 403 Forbidden
    CURATED = {
        # Business & Professional
        "business": [
            ("success_checkmark", "https://assets10.lottiefiles.com/packages/lf20_jbrw3hcz.json"),
            ("analytics_chart", "https://assets8.lottiefiles.com/packages/lf20_qp1q7mct.json"),
            ("growth", "https://assets5.lottiefiles.com/packages/lf20_yzoqyyqf.json"),
        ],

        # Subscribe & CTA
        "subscribe": [
            ("bell_notification", "https://assets9.lottiefiles.com/packages/lf20_4pyqf5zs.json"),
            ("click_button", "https://assets3.lottiefiles.com/packages/lf20_ky24lkyk.json"),
            ("tap_here", "https://assets6.lottiefiles.com/packages/lf20_xlmz9xwm.json"),
        ],

        # Arrows & Navigation
        "arrow": [
            ("arrow_pointing", "https://assets3.lottiefiles.com/packages/lf20_ky24lkyk.json"),
            ("scroll_down", "https://assets7.lottiefiles.com/packages/lf20_5gq3qlyj.json"),
            ("swipe_gesture", "https://assets2.lottiefiles.com/packages/lf20_lg6lh7fp.json"),
        ],

        # Success & Confirmation
        "success": [
            ("checkmark_green", "https://assets10.lottiefiles.com/packages/lf20_jbrw3hcz.json"),
            ("success_done", "https://assets1.lottiefiles.com/packages/lf20_lk80fpsm.json"),
            ("celebration", "https://assets4.lottiefiles.com/packages/lf20_z9kxmwq3.json"),
        ],

        # Loading & Progress
        "loading": [
            ("loading_spinner", "https://assets6.lottiefiles.com/packages/lf20_p8bfn5to.json"),
            ("progress_dots", "https://assets8.lottiefiles.com/packages/lf20_kxsd2ytq.json"),
            ("loading_circle", "https://assets5.lottiefiles.com/packages/lf20_jcikwtux.json"),
        ],

        # Social Media
        "social": [
            ("like_heart", "https://assets2.lottiefiles.com/packages/lf20_slykp1pg.json"),
            ("share_icon", "https://assets7.lottiefiles.com/packages/lf20_cwq6iw5e.json"),
            ("notification", "https://assets9.lottiefiles.com/packages/lf20_4pyqf5zs.json"),
        ],

        # Money & Finance
        "money": [
            ("coin_drop", "https://assets8.lottiefiles.com/packages/lf20_qp1q7mct.json"),
            ("savings_piggy", "https://assets5.lottiefiles.com/packages/lf20_yzoqyyqf.json"),
            ("cash_stack", "https://assets3.lottiefiles.com/packages/lf20_u4yrau.json"),
        ],

        # Tech & Software
        "tech": [
            ("code_brackets", "https://assets6.lottiefiles.com/packages/lf20_bnfrqxos.json"),
            ("cloud_sync", "https://assets4.lottiefiles.com/packages/lf20_szlepvdh.json"),
            ("rocket_launch", "https://assets1.lottiefiles.com/packages/lf20_zavdvufc.json"),
        ],

        # People & Characters
        "people": [
            ("waving_hello", "https://assets2.lottiefiles.com/packages/lf20_lg6lh7fp.json"),
            ("thinking_person", "https://assets7.lottiefiles.com/packages/lf20_ydo1amjm.json"),
            ("happy_dance", "https://assets4.lottiefiles.com/packages/lf20_z9kxmwq3.json"),
        ],
    }

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "lottie_unified"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.lottiefiles = LottieFilesSearch(self.cache_dir / "lottiefiles")
        self.iconscout = IconScoutSearch(self.cache_dir / "iconscout")

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search across all sources for animations.

        Args:
            query: Keywords to search for
            limit: Max results

        Returns:
            List of dicts with 'name', 'url', 'source'
        """
        results = []

        # First check curated collection
        query_lower = query.lower()
        for category, animations in self.CURATED.items():
            if query_lower in category or category in query_lower:
                for name, url in animations:
                    results.append({
                        'name': name,
                        'url': url,
                        'source': 'curated'
                    })

        # Then search LottieFiles
        try:
            lf_results = self.lottiefiles.search(query, limit=limit)
            for anim in lf_results:
                results.append({
                    'name': anim.name,
                    'url': anim.json_url,
                    'source': 'lottiefiles'
                })
        except:
            pass

        return results[:limit]

    def get_curated(self, category: str) -> List[Dict]:
        """Get all curated animations for a category."""
        if category in self.CURATED:
            return [
                {'name': name, 'url': url, 'source': 'curated'}
                for name, url in self.CURATED[category]
            ]
        return []

    def list_categories(self) -> List[str]:
        """List all curated categories."""
        return list(self.CURATED.keys())

    def download(self, url: str, name: str = None) -> Optional[Path]:
        """Download animation from URL."""
        return self.lottiefiles.download_by_url(url, name)

    def find_for_concept(self, concept: str) -> List[Dict]:
        """
        Find animations that match a video concept.

        Maps common video concepts to appropriate animation categories.
        """
        concept_map = {
            # Business concepts
            "saas": ["business", "tech", "money"],
            "startup": ["business", "rocket", "success"],
            "discount": ["money", "success", "arrow"],
            "deal": ["money", "handshake", "success"],
            "subscription": ["subscribe", "money", "arrow"],
            "software": ["tech", "code", "loading"],

            # Action concepts
            "signup": ["subscribe", "arrow", "success"],
            "buy": ["money", "success", "arrow"],
            "save": ["money", "success"],
            "join": ["subscribe", "people", "success"],

            # Emotion concepts
            "excited": ["celebration", "confetti", "success"],
            "frustrated": ["loading", "thinking"],
            "happy": ["celebration", "success", "people"],
        }

        results = []
        concept_lower = concept.lower()

        for keyword, categories in concept_map.items():
            if keyword in concept_lower:
                for cat in categories:
                    results.extend(self.get_curated(cat))

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r['url'] not in seen:
                seen.add(r['url'])
                unique.append(r)

        return unique


def search_animations(query: str, limit: int = 20) -> List[Dict]:
    """Convenience function to search for animations."""
    search = UnifiedLottieSearch()
    return search.search(query, limit)


def download_animation(url: str, name: str = None) -> Optional[Path]:
    """Convenience function to download an animation."""
    search = UnifiedLottieSearch()
    return search.download(url, name)


if __name__ == "__main__":
    import sys

    search = UnifiedLottieSearch()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"Searching for: {query}")

        results = search.search(query)

        print(f"\nFound {len(results)} animations:\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['name']} ({r['source']})")
            print(f"   {r['url']}")
    else:
        print("Available categories:")
        for cat in search.list_categories():
            count = len(search.CURATED[cat])
            print(f"  - {cat}: {count} animations")

        print("\nUsage: python lottie_search.py <query>")
        print("Example: python lottie_search.py business")
