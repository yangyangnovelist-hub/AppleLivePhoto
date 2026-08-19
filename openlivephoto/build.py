from __future__ import annotations

import json
import shutil
from pathlib import Path

from .analyze import analyze_video
from .utils import closest_ratio_crop, ensure_tool, make_uuid, run, sanitize_stem, video_info


def _maybe_heic(jpg_path: Path, heic_path: Path) -> bool:
    if not shutil.which("heif-enc"):
        return False
    try:
        run(["heif-enc", str(jpg_path), "-o", str(heic_path)])
        return True
    except Exception:
        return False


def build_live_bundle(
    video_path: Path,
    output_root: Path,
    target_seconds: float = 3.0,
    aspect_ratio: str = "3:4",
    sample_fps: float = 4.0,
    moment_seconds: float = 1.0,
) -> Path:
    ensure_tool("ffmpeg")
    video_meta = video_info(video_path)
    analysis = analyze_video(
        video_path,
        sample_fps=sample_fps,
        target_seconds=target_seconds,
        moment_seconds=moment_seconds,
    )
    window = analysis["window"]

    stem = sanitize_stem(video_path.stem)
    bundle_dir = output_root / f"{stem}_livebundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    asset_id = make_uuid()
    clip_path = bundle_dir / f"{stem}.mov"
    cover_jpg = bundle_dir / f"{stem}_cover.jpg"
    cover_heic = bundle_dir / f"{stem}_cover.heic"
    manifest_path = bundle_dir / "manifest.json"

    crop_filter = closest_ratio_crop(video_meta["width"], video_meta["height"], aspect_ratio)
    vf_chain = []
    if crop_filter:
        vf_chain.append(crop_filter)
    vf_for_trim = ",".join(vf_chain) if vf_chain else None

    trim_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{window['start_time']:.3f}",
        "-i", str(video_path),
        "-t", f"{target_seconds:.3f}",
    ]
    if vf_for_trim:
        trim_cmd += ["-vf", vf_for_trim]
    trim_cmd += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-c:a", "aac", str(clip_path),
    ]
    run(trim_cmd)

    cover_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{window['keyframe_time']:.3f}",
        "-i", str(video_path), "-frames:v", "1",
    ]
    if vf_for_trim:
        cover_cmd += ["-vf", vf_for_trim]
    cover_cmd += [str(cover_jpg)]
    run(cover_cmd)

    heic_built = _maybe_heic(cover_jpg, cover_heic)

    manifest = {
        "asset_id": asset_id,
        "input_video": str(video_path),
        "bundle_dir": str(bundle_dir),
        "cover_jpg": str(cover_jpg),
        "cover_heic": str(cover_heic) if heic_built else None,
        "clip_mov": str(clip_path),
        "selected_window": window,
        "analysis": analysis,
        "aspect_ratio": aspect_ratio,
        "target_seconds": target_seconds,
        "moment_seconds": moment_seconds,
        "notes": [
            "This bundle contains the selected still frame and the trimmed motion clip.",
            "To create a true Apple Live Photo pair, finalize on macOS with makelive or make-live-photo.",
            "The selected keyframe follows the principle: animate the static scene, freeze the dynamic scene.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle_dir


def finalize_on_macos(photo_path: Path, mov_path: Path) -> list[str]:
    """Return a suggested finalize command, but do not run it automatically."""
    if shutil.which("make-live-photo"):
        return ["make-live-photo", str(photo_path), str(mov_path)]
    if shutil.which("makelive"):
        return ["makelive", str(photo_path), str(mov_path)]
    return []
