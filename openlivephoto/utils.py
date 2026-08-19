from __future__ import annotations

import json
import math
import shutil
import subprocess
import uuid
from pathlib import Path


def ensure_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required tool not found in PATH: {name}")
    return path


def run(cmd: list[str], capture_output: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, capture_output=capture_output)


def ffprobe_json(path: Path) -> dict:
    ensure_tool("ffprobe")
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        capture_output=True,
    )
    return json.loads(result.stdout)


def video_info(path: Path) -> dict:
    data = ffprobe_json(path)
    vstreams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    if not vstreams:
        raise RuntimeError(f"No video stream found in {path}")
    stream = vstreams[0]
    duration = float(stream.get("duration") or data.get("format", {}).get("duration") or 0.0)
    fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1"
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 0.0
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    return {
        "duration": duration,
        "fps": fps,
        "width": width,
        "height": height,
        "rotation": stream.get("tags", {}).get("rotate"),
    }


def make_uuid() -> str:
    return str(uuid.uuid4())


def sanitize_stem(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text).strip("_") or "asset"


def closest_ratio_crop(width: int, height: int, ratio: str) -> str | None:
    if not ratio:
        return None
    rw, rh = [int(x) for x in ratio.split(":")]
    target = rw / rh
    source = width / height
    if abs(source - target) < 0.01:
        return None
    if source > target:
        crop_w = math.floor(height * target)
        x = math.floor((width - crop_w) / 2)
        return f"crop={crop_w}:{height}:{x}:0"
    crop_h = math.floor(width / target)
    y = math.floor((height - crop_h) / 2)
    return f"crop={width}:{crop_h}:0:{y}"
