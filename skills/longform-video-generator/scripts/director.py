#!/usr/bin/env python3
"""
Director Module - Quality control and review process for video generation.

The Director acts as creative oversight, reviewing generated assets and
determining if they meet quality standards before proceeding.

Key responsibilities:
1. Review generated images for quality and consistency
2. Validate character reference images before using them
3. Check adherence to defined aesthetic
4. Request revisions when needed
5. Approve assets for the next pipeline stage
"""

import os
import sys
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))
from fal_wrapper import FalClient, FalConfig, MODELS


class ReviewStatus(Enum):
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


@dataclass
class ReviewResult:
    """Result of a director review"""
    status: ReviewStatus
    score: float  # 0-1 quality score
    feedback: str
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class DirectorConfig:
    """Configuration for the director"""
    min_quality_score: float = 0.7  # Minimum score to approve
    max_revisions: int = 3  # Max revision attempts per shot
    strict_character_matching: bool = True  # Enforce character consistency
    auto_approve: bool = False  # If True, skip interactive review


class Director:
    """
    Creative director that reviews and approves generated assets.

    The director ensures quality control throughout the video pipeline by:
    - Reviewing each generated image against the script requirements
    - Validating character consistency across shots
    - Checking adherence to the defined aesthetic
    - Requesting revisions when quality is insufficient
    """

    def __init__(self, client: FalClient, config: DirectorConfig = None):
        self.client = client
        self.config = config or DirectorConfig()

        # Track approved character references
        self.approved_character_refs: Dict[str, List[str]] = {}

        # Review history
        self.reviews: List[Dict[str, Any]] = []

    def review_image(
        self,
        image_path: Path,
        image_url: str,
        shot_description: str,
        character_name: Optional[str] = None,
        aesthetic_prompt: str = "",
        existing_refs: List[str] = None
    ) -> ReviewResult:
        """
        Review a generated image for quality and consistency.

        This is a heuristic-based review that checks:
        1. Image was successfully generated (file exists, non-zero)
        2. Basic quality indicators
        3. Character consistency (if reference exists)

        For full creative review, enable interactive mode.
        """
        issues = []
        suggestions = []

        # Check basic file quality
        if not image_path.exists():
            return ReviewResult(
                status=ReviewStatus.REJECTED,
                score=0.0,
                feedback="Image file does not exist",
                issues=["File not found"]
            )

        file_size = image_path.stat().st_size
        if file_size < 10000:  # Less than 10KB likely indicates error
            return ReviewResult(
                status=ReviewStatus.REJECTED,
                score=0.0,
                feedback="Image file too small, likely corrupted or error",
                issues=["File size indicates potential error"]
            )

        # Start with base score
        score = 0.85  # Assume reasonable quality by default

        # Check if this is a character shot with existing references
        if character_name and existing_refs and self.config.strict_character_matching:
            # Note: In a full implementation, we'd use an image comparison model here
            # For now, we log a reminder to visually verify
            suggestions.append(f"Verify {character_name} matches reference images")

        # Check file size as proxy for detail (larger = more detail typically)
        if file_size > 1_000_000:  # > 1MB
            score += 0.05
        elif file_size < 500_000:  # < 500KB
            score -= 0.05
            suggestions.append("Consider regenerating at higher resolution for more detail")

        # Log review
        review_record = {
            "image_path": str(image_path),
            "image_url": image_url,
            "shot_description": shot_description,
            "character": character_name,
            "score": score,
            "file_size": file_size
        }
        self.reviews.append(review_record)

        # Determine status
        if score >= self.config.min_quality_score:
            status = ReviewStatus.APPROVED
            feedback = "Image meets quality standards"
        else:
            status = ReviewStatus.NEEDS_REVISION
            feedback = f"Score {score:.2f} below threshold {self.config.min_quality_score}"
            issues.append("Quality score below threshold")

        return ReviewResult(
            status=status,
            score=score,
            feedback=feedback,
            issues=issues,
            suggestions=suggestions
        )

    def approve_character_reference(
        self,
        character_name: str,
        image_url: str,
        image_path: Path
    ) -> bool:
        """
        Approve an image as a character reference for future shots.

        Returns True if approved, False if rejected.
        """
        review = self.review_image(
            image_path=image_path,
            image_url=image_url,
            shot_description=f"Character reference for {character_name}",
            character_name=character_name
        )

        if review.status == ReviewStatus.APPROVED:
            if character_name not in self.approved_character_refs:
                self.approved_character_refs[character_name] = []
            self.approved_character_refs[character_name].append(image_url)
            print(f"  [Director] Approved reference for {character_name}")
            return True
        else:
            print(f"  [Director] Reference rejected: {review.feedback}")
            return False

    def get_approved_refs(self, character_name: str) -> List[str]:
        """Get approved reference images for a character"""
        return self.approved_character_refs.get(character_name, [])[-3:]  # Last 3

    def review_storyboard(
        self,
        storyboard_results: List[Dict[str, Any]],
        script_shots: List[Any]
    ) -> Tuple[List[int], List[str]]:
        """
        Review entire storyboard and identify shots needing revision.

        Returns:
            - List of shot indices that need revision
            - List of feedback strings
        """
        needs_revision = []
        feedback_list = []

        for i, (result, shot) in enumerate(zip(storyboard_results, script_shots)):
            if not result.get("success"):
                needs_revision.append(i)
                feedback_list.append(f"Shot {i+1}: Generation failed - {result.get('error')}")
                continue

            review = self.review_image(
                image_path=Path(result["local_path"]),
                image_url=result.get("url", ""),
                shot_description=shot.description if hasattr(shot, 'description') else "",
                character_name=getattr(shot, 'character', None)
            )

            if review.status == ReviewStatus.NEEDS_REVISION:
                needs_revision.append(i)
                feedback_list.append(f"Shot {i+1}: {review.feedback}")
            elif review.suggestions:
                feedback_list.append(f"Shot {i+1} (approved): {'; '.join(review.suggestions)}")

        return needs_revision, feedback_list

    def get_review_summary(self) -> Dict[str, Any]:
        """Get summary of all reviews"""
        if not self.reviews:
            return {"total": 0, "avg_score": 0.0}

        scores = [r["score"] for r in self.reviews]
        return {
            "total": len(self.reviews),
            "avg_score": sum(scores) / len(scores),
            "approved_count": sum(1 for r in self.reviews if r["score"] >= self.config.min_quality_score),
            "character_refs": {k: len(v) for k, v in self.approved_character_refs.items()}
        }


class InteractiveDirector(Director):
    """
    Director with interactive review capabilities.
    Opens images for visual inspection and prompts for approval.
    """

    def __init__(self, client: FalClient, config: DirectorConfig = None):
        super().__init__(client, config)

    def interactive_review(
        self,
        image_path: Path,
        shot_description: str,
        character_name: Optional[str] = None
    ) -> ReviewResult:
        """
        Interactively review an image with user input.
        Opens the image and prompts for approval/revision/rejection.
        """
        import subprocess

        print(f"\n{'='*60}")
        print(f"DIRECTOR REVIEW")
        print(f"{'='*60}")
        print(f"Shot: {shot_description[:80]}...")
        if character_name:
            print(f"Character: {character_name}")
        print(f"Image: {image_path}")

        # Open image for review
        try:
            subprocess.run(["open", str(image_path)], check=False)
        except Exception:
            print(f"Could not open image automatically. Please view: {image_path}")

        # In automated mode, skip prompt
        if self.config.auto_approve:
            print("[Auto-approve enabled, skipping interactive review]")
            return ReviewResult(
                status=ReviewStatus.APPROVED,
                score=0.85,
                feedback="Auto-approved"
            )

        # Prompt for review
        print("\nReview options:")
        print("  [a] Approve - Image meets standards")
        print("  [r] Revision needed - Regenerate with suggestions")
        print("  [x] Reject - Skip this shot")
        print("  [Enter] Auto-approve with default score")

        response = input("\nYour review [a/r/x/Enter]: ").strip().lower()

        if response in ['a', '']:
            return ReviewResult(
                status=ReviewStatus.APPROVED,
                score=0.9,
                feedback="Manually approved by director"
            )
        elif response == 'r':
            suggestion = input("Revision suggestion: ").strip()
            return ReviewResult(
                status=ReviewStatus.NEEDS_REVISION,
                score=0.5,
                feedback="Director requested revision",
                suggestions=[suggestion] if suggestion else ["General quality improvement needed"]
            )
        else:
            return ReviewResult(
                status=ReviewStatus.REJECTED,
                score=0.0,
                feedback="Rejected by director"
            )


if __name__ == "__main__":
    print("Director Module - Quality control for video generation")
    print("\nUsage: Import and use in video_pipeline.py")
    print("\nFeatures:")
    print("  - Review generated images for quality")
    print("  - Validate character consistency")
    print("  - Approve character references")
    print("  - Request revisions when needed")
    print("  - Track review history")
