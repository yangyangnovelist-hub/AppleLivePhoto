from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyze import analyze_video
from .build import build_live_bundle, finalize_on_macos


def cmd_analyze(args: argparse.Namespace) -> int:
    result = analyze_video(
        Path(args.video),
        sample_fps=args.sample_fps,
        target_seconds=args.seconds,
        moment_seconds=args.moment_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    out = build_live_bundle(
        video_path=Path(args.video),
        output_root=Path(args.output),
        target_seconds=args.seconds,
        aspect_ratio=args.aspect_ratio,
        sample_fps=args.sample_fps,
        moment_seconds=args.moment_seconds,
    )
    print(str(out))
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    video_exts = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
    videos = [p for p in sorted(input_dir.rglob("*")) if p.suffix.lower() in video_exts]
    if args.limit:
        videos = videos[: args.limit]
    for video in videos:
        bundle = build_live_bundle(
            video_path=video,
            output_root=output_dir,
            target_seconds=args.seconds,
            aspect_ratio=args.aspect_ratio,
            sample_fps=args.sample_fps,
            moment_seconds=args.moment_seconds,
        )
        print(bundle)
    return 0


def cmd_finalize_hint(args: argparse.Namespace) -> int:
    cmd = finalize_on_macos(Path(args.photo), Path(args.mov))
    if cmd:
        print(" ".join(cmd))
    else:
        print(
            "Install `make-live-photo` or `makelive` on macOS, then finalize "
            "the generated HEIC/JPG and MOV pair."
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openlive",
        description="Select and build Apple Live Photo candidates from video.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--seconds", type=float, default=3.0, help="Target Live envelope length in seconds.")
    common.add_argument("--sample-fps", type=float, default=4.0, help="Sampling FPS used during scoring.")
    common.add_argument("--moment-seconds", type=float, default=1.0, help="Meaningful motion moment inside the Live envelope.")
    common.add_argument("--aspect-ratio", default="3:4", help="Crop ratio for export, e.g. 3:4 or 9:16.")

    analyze = sub.add_parser("analyze", parents=[common], help="Analyze a video and print the chosen moment/keyframe.")
    analyze.add_argument("video")
    analyze.set_defaults(func=cmd_analyze)

    build = sub.add_parser("build", parents=[common], help="Build one Live candidate bundle from a video.")
    build.add_argument("video")
    build.add_argument("-o", "--output", default="./dist", help="Output directory")
    build.set_defaults(func=cmd_build)

    batch = sub.add_parser("batch", parents=[common], help="Batch-build candidate bundles for a directory.")
    batch.add_argument("input")
    batch.add_argument("-o", "--output", default="./dist", help="Output directory")
    batch.add_argument("--limit", type=int, default=0, help="Optional max number of videos to process.")
    batch.set_defaults(func=cmd_batch)

    finalize = sub.add_parser("finalize-hint", help="Print a macOS finalization command if a backend is installed.")
    finalize.add_argument("photo")
    finalize.add_argument("mov")
    finalize.set_defaults(func=cmd_finalize_hint)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
