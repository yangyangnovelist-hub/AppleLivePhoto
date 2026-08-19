from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from PIL import Image

from .utils import ensure_tool, run, video_info


@dataclass
class FrameMetric:
    index: int
    timestamp: float
    motion: float
    changed_fraction: float
    sharpness: float


@dataclass
class WindowChoice:
    # Apple-compatible playback container (normally ~3 s)
    start_index: int
    end_index: int
    start_time: float
    end_time: float
    # Perceptual "moment" inside that container (normally ~0.8–1.2 s)
    moment_start_index: int
    moment_end_index: int
    moment_start_time: float
    moment_end_time: float
    moment_duration: float
    avg_motion: float
    motion_std: float
    avg_changed_fraction: float
    score: float
    keyframe_index: int
    keyframe_time: float
    keyframe_motion: float
    keyframe_changed_fraction: float
    keyframe_sharpness: float


def _gray_array(path: Path) -> np.ndarray:
    img = Image.open(path).convert("L")
    return np.asarray(img, dtype=np.float32) / 255.0


def _sharpness(arr: np.ndarray) -> float:
    gx = np.abs(np.diff(arr, axis=1)).mean()
    gy = np.abs(np.diff(arr, axis=0)).mean()
    return float(gx + gy)


def sample_video(video_path: Path, sample_fps: float = 4.0, scale_width: int = 320) -> list[FrameMetric]:
    """Sample frames for cheap temporal scoring.

    4 fps is deliberate: a Live Photo *feels* like one moment even though the
    Apple capture envelope is ~3 seconds. We need sub-second resolution to find
    the moment, not merely a coarse 3-second block.
    """
    ensure_tool("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="openlive_frames_") as tmp:
        tmpdir = Path(tmp)
        pattern = tmpdir / "frame_%05d.jpg"
        vf = f"fps={sample_fps},scale={scale_width}:-1"
        run(["ffmpeg", "-y", "-v", "error", "-i", str(video_path), "-vf", vf, str(pattern)])
        frame_files = sorted(tmpdir.glob("frame_*.jpg"))
        metrics: list[FrameMetric] = []
        prev = None
        for i, f in enumerate(frame_files):
            arr = _gray_array(f)
            if prev is not None:
                diff = np.abs(arr - prev)
                motion = float(diff.mean())
                changed_fraction = float((diff > 0.05).mean())
            else:
                motion = 0.0
                changed_fraction = 0.0
            metrics.append(
                FrameMetric(
                    index=i,
                    timestamp=i / sample_fps,
                    motion=motion,
                    changed_fraction=changed_fraction,
                    sharpness=_sharpness(arr),
                )
            )
            prev = arr
        return metrics


def _moment_score(
    chunk: list[FrameMetric],
    motion_floor: float,
    motion_ceiling: float,
    changed_fraction_ceiling: float,
) -> tuple[float, float, float, float]:
    body = chunk[1:] if len(chunk) > 1 else chunk
    motions = np.array([m.motion for m in body], dtype=np.float32)
    changed = np.array([m.changed_fraction for m in body], dtype=np.float32)
    avg_motion = float(motions.mean()) if len(motions) else 0.0
    motion_std = float(motions.std()) if len(motions) else 0.0
    avg_changed = float(changed.mean()) if len(changed) else 0.0

    # Enough movement to register as "alive", but reject shake/cuts/noise.
    activation = 1.0 - math.exp(-avg_motion / max(motion_floor, 1e-6))
    motion_penalty = math.exp(-max(avg_motion - motion_ceiling, 0.0) * 55.0)
    coverage_penalty = math.exp(-max(avg_changed - changed_fraction_ceiling, 0.0) * 7.0)
    stability = math.exp(-motion_std * 30.0)

    # Slightly reward a clean, sharp still opportunity inside the moving moment.
    sharpness = max((m.sharpness for m in chunk), default=0.0)
    sharp_reward = 1.0 + min(sharpness, 0.25) * 0.6

    score = activation * motion_penalty * coverage_penalty * (0.72 + 0.28 * stability) * sharp_reward
    return score, avg_motion, motion_std, avg_changed


def pick_best_window(
    metrics: list[FrameMetric],
    target_seconds: float = 3.0,
    moment_seconds: float = 1.0,
    sample_fps: float = 4.0,
    motion_floor: float = 0.002,
    motion_ceiling: float = 0.025,
    changed_fraction_ceiling: float = 0.25,
) -> WindowChoice:
    """Find one *moment* first, then wrap it in a Live-Photo-length envelope.

    Apple's native Live Photos record ~1.5 s before + ~1.5 s after shutter, but
    aesthetically they read as a single instant. So selection should NOT look
    for three seconds of continuous action. It should find ~1 second of useful
    micro-motion, pick a crisp keyframe, then add quiet temporal context around it.
    """
    if len(metrics) < 4:
        raise RuntimeError("Not enough sampled frames to analyze video.")

    moment_frames = max(2, int(round(moment_seconds * sample_fps)))
    container_frames = max(moment_frames, int(round(target_seconds * sample_fps)))

    best_payload = None
    for start in range(0, len(metrics) - moment_frames + 1):
        chunk = metrics[start : start + moment_frames]
        score, avg_motion, motion_std, avg_changed = _moment_score(
            chunk, motion_floor, motion_ceiling, changed_fraction_ceiling
        )

        key_candidates = chunk[1:-1] if len(chunk) > 2 else chunk
        key = max(
            key_candidates,
            key=lambda x: (x.sharpness * 2.0) - (x.motion * 0.9) - (x.changed_fraction * 0.08),
        )

        # Prefer the active moment not to sit at the very beginning/end of source.
        edge_margin = min(key.index, max(0, len(metrics) - 1 - key.index))
        edge_reward = min(1.0, edge_margin / max(1.0, sample_fps * 0.75))
        score *= 0.9 + 0.1 * edge_reward

        payload = (score, avg_motion, motion_std, avg_changed, chunk, key)
        if best_payload is None or payload[0] > best_payload[0]:
            best_payload = payload

    if best_payload is None:
        raise RuntimeError("Could not pick a candidate moment.")

    score, avg_motion, motion_std, avg_changed, moment_chunk, key = best_payload

    # Build a ~3 second envelope centered on the keyframe. The meaningful motion
    # remains short; the rest acts like natural pre/post shutter context.
    half = container_frames // 2
    start_index = max(0, key.index - half)
    end_index = start_index + container_frames - 1
    if end_index >= len(metrics):
        end_index = len(metrics) - 1
        start_index = max(0, end_index - container_frames + 1)

    start_time = metrics[start_index].timestamp
    # End is expressed as a playback boundary rather than just the final sample timestamp.
    end_time = min(metrics[-1].timestamp + (1.0 / sample_fps), start_time + target_seconds)

    return WindowChoice(
        start_index=start_index,
        end_index=end_index,
        start_time=start_time,
        end_time=end_time,
        moment_start_index=moment_chunk[0].index,
        moment_end_index=moment_chunk[-1].index,
        moment_start_time=moment_chunk[0].timestamp,
        moment_end_time=moment_chunk[-1].timestamp + (1.0 / sample_fps),
        moment_duration=moment_seconds,
        avg_motion=avg_motion,
        motion_std=motion_std,
        avg_changed_fraction=avg_changed,
        score=score,
        keyframe_index=key.index,
        keyframe_time=key.timestamp,
        keyframe_motion=key.motion,
        keyframe_changed_fraction=key.changed_fraction,
        keyframe_sharpness=key.sharpness,
    )


def analyze_video(
    video_path: Path,
    sample_fps: float = 4.0,
    target_seconds: float = 3.0,
    moment_seconds: float = 1.0,
) -> dict:
    info = video_info(video_path)
    metrics = sample_video(video_path, sample_fps=sample_fps)
    window = pick_best_window(
        metrics,
        target_seconds=target_seconds,
        moment_seconds=moment_seconds,
        sample_fps=sample_fps,
    )
    return {
        "video": str(video_path),
        "video_info": info,
        "sample_fps": sample_fps,
        "target_seconds": target_seconds,
        "moment_seconds": moment_seconds,
        "window": asdict(window),
        "sample_count": len(metrics),
    }
