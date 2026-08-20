from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .analyze import pick_best_window, sample_video
from .utils import video_info

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


@dataclass
class SourceScore:
    path: str
    score: float
    archetype: str
    best_moment_score: float
    micro_motion_density: float
    freezeable_density: float
    chaotic_fraction: float
    static_fraction: float
    median_sharpness: float
    portrait: bool
    duration: float
    width: int
    height: int
    reasons: list[str]


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def rank_source_video(
    video_path: Path,
    *,
    sample_fps: float = 2.0,
    target_seconds: float = 3.0,
    moment_seconds: float = 1.0,
) -> SourceScore:
    """Score a *whole source video* before clip extraction.

    This is deliberately different from choosing the best second inside a clip.
    A good source should contain repeated usable micro-moments, preserve at least
    one sharp freeze-frame opportunity, and avoid being mostly dead or chaotic.

    Two visual archetypes are rewarded:

    1. quiet-motion: mostly stable composition with local motion (hair, fabric,
       leaves, hands, sunlight, walking micro-movement);
    2. dynamic-freeze: a more active scene that still contains crisp frames worth
       freezing as the Live Photo cover.
    """
    info = video_info(video_path)
    metrics = sample_video(video_path, sample_fps=sample_fps)
    if len(metrics) < max(4, int(round(target_seconds * sample_fps))):
        raise RuntimeError(f"Source is too short to rank reliably: {video_path}")

    body = metrics[1:]
    motion = np.array([m.motion for m in body], dtype=np.float32)
    changed = np.array([m.changed_fraction for m in body], dtype=np.float32)
    sharpness = np.array([m.sharpness for m in body], dtype=np.float32)

    median_sharpness = float(np.median(sharpness)) if len(sharpness) else 0.0

    # Stable composition + visible local motion: the classic "静止画面动态拍" case.
    micro_motion_mask = (
        (motion >= 0.002)
        & (motion <= 0.025)
        & (changed <= 0.25)
    )

    # More active movement that still yields freezeable frames: "动画面静拍".
    freezeable_mask = (
        (motion >= 0.007)
        & (motion <= 0.045)
        & (changed <= 0.40)
        & (sharpness >= max(median_sharpness * 0.85, 0.001))
    )

    chaotic_mask = (motion > 0.055) | (changed > 0.50)
    static_mask = motion < 0.001

    micro_density = float(micro_motion_mask.mean()) if len(body) else 0.0
    freeze_density = float(freezeable_mask.mean()) if len(body) else 0.0
    chaotic_fraction = float(chaotic_mask.mean()) if len(body) else 1.0
    static_fraction = float(static_mask.mean()) if len(body) else 1.0

    best = pick_best_window(
        metrics,
        target_seconds=target_seconds,
        moment_seconds=moment_seconds,
        sample_fps=sample_fps,
    )
    best_moment_score = _clip01(best.score)

    portrait = bool(info["height"] > info["width"])
    portrait_score = 1.0 if portrait else 0.45
    resolution_score = _clip01(min(info["width"], info["height"]) / 720.0)
    duration_score = _clip01(info["duration"] / max(target_seconds + 1.0, 4.0))
    sharpness_score = _clip01(median_sharpness / 0.055)
    cleanliness_score = 1.0 - _clip01(chaotic_fraction)

    score01 = (
        0.38 * best_moment_score
        + 0.20 * _clip01(micro_density / 0.45)
        + 0.15 * _clip01(freeze_density / 0.30)
        + 0.12 * cleanliness_score
        + 0.06 * sharpness_score
        + 0.04 * portrait_score
        + 0.05 * duration_score
    )

    # A source that is almost entirely frozen is not useful even if one codec or
    # sensor artifact happens to look like motion. Conversely, long quiet shots
    # are allowed as long as they contain genuine micro-motion.
    if static_fraction > 0.92 and micro_density < 0.05:
        score01 *= 0.35

    if micro_density > freeze_density * 1.15:
        archetype = "quiet-motion"
    elif freeze_density > micro_density * 1.15:
        archetype = "dynamic-freeze"
    else:
        archetype = "mixed"

    reasons: list[str] = []
    if best_moment_score >= 0.70:
        reasons.append("strong best moment")
    if micro_density >= 0.25:
        reasons.append("good micro-motion density")
    if freeze_density >= 0.18:
        reasons.append("many freezeable dynamic frames")
    if chaotic_fraction <= 0.08:
        reasons.append("clean/stable camera behavior")
    if portrait:
        reasons.append("portrait source")
    if static_fraction >= 0.75:
        reasons.append("mostly static")
    if chaotic_fraction >= 0.25:
        reasons.append("too much chaos/camera shake")
    if not reasons:
        reasons.append("average source")

    return SourceScore(
        path=str(video_path),
        score=round(score01 * 100.0, 3),
        archetype=archetype,
        best_moment_score=round(best_moment_score, 6),
        micro_motion_density=round(micro_density, 6),
        freezeable_density=round(freeze_density, 6),
        chaotic_fraction=round(chaotic_fraction, 6),
        static_fraction=round(static_fraction, 6),
        median_sharpness=round(median_sharpness, 6),
        portrait=portrait,
        duration=round(float(info["duration"]), 3),
        width=int(info["width"]),
        height=int(info["height"]),
        reasons=reasons,
    )


def rank_source_directory(
    input_dir: Path,
    *,
    sample_fps: float = 2.0,
    target_seconds: float = 3.0,
    moment_seconds: float = 1.0,
    limit: int = 0,
) -> list[dict]:
    videos = [
        p for p in sorted(input_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    ]
    if limit:
        videos = videos[:limit]

    scored: list[SourceScore] = []
    for video in videos:
        try:
            scored.append(
                rank_source_video(
                    video,
                    sample_fps=sample_fps,
                    target_seconds=target_seconds,
                    moment_seconds=moment_seconds,
                )
            )
        except Exception as exc:
            scored.append(
                SourceScore(
                    path=str(video),
                    score=0.0,
                    archetype="unusable",
                    best_moment_score=0.0,
                    micro_motion_density=0.0,
                    freezeable_density=0.0,
                    chaotic_fraction=1.0,
                    static_fraction=1.0,
                    median_sharpness=0.0,
                    portrait=False,
                    duration=0.0,
                    width=0,
                    height=0,
                    reasons=[f"analysis failed: {exc}"],
                )
            )

    scored.sort(key=lambda item: item.score, reverse=True)
    return [dict(rank=index + 1, **asdict(item)) for index, item in enumerate(scored)]
