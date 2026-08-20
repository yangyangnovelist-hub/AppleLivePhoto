from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyze import analyze_video
from .build import build_live_bundle, finalize_on_macos
from .source_rank import VIDEO_EXTS, rank_source_directory


def cmd_analyze(args: argparse.Namespace) -> int:
    result = analyze_video(
        Path(args.video),
        sample_fps=args.sample_fps,
        target_seconds=args.seconds,
        moment_seconds=args.moment_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_rank_sources(args: argparse.Namespace) -> int:
    ranking = rank_source_directory(
        Path(args.input),
        sample_fps=args.source_sample_fps,
        target_seconds=args.seconds,
        moment_seconds=args.moment_seconds,
        limit=args.limit,
    )
    if args.top:
        ranking = ranking[: args.top]
    payload = {
        "input": str(Path(args.input)),
        "count": len(ranking),
        "ranking": ranking,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.write_json:
        output = Path(args.write_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered)
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

    if args.top_sources:
        ranking = rank_source_directory(
            input_dir,
            sample_fps=args.source_sample_fps,
            target_seconds=args.seconds,
            moment_seconds=args.moment_seconds,
            limit=args.limit,
        )
        selected = [row for row in ranking if row["score"] > 0][: args.top_sources]
        ranking_path = output_dir / "source_ranking.json"
        ranking_path.parent.mkdir(parents=True, exist_ok=True)
        ranking_path.write_text(
            json.dumps({"input": str(input_dir), "ranking": ranking}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        videos = [Path(row["path"]) for row in selected]
    else:
        videos = [
            p for p in sorted(input_dir.rglob("*"))
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS
        ]
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
        description="Rank source videos, select moments, and build Apple Live Photo candidates.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--seconds", type=float, default=3.0, help="Target Live envelope length in seconds.")
    common.add_argument("--sample-fps", type=float, default=4.0, help="Sampling FPS used during moment selection.")
    common.add_argument("--moment-seconds", type=float, default=1.0, help="Meaningful motion moment inside the Live envelope.")
    common.add_argument("--aspect-ratio", default="3:4", help="Crop ratio for export, e.g. 3:4 or 9:16.")

    analyze = sub.add_parser("analyze", parents=[common], help="Analyze one video and print the chosen moment/keyframe.")
    analyze.add_argument("video")
    analyze.set_defaults(func=cmd_analyze)

    rank_sources = sub.add_parser("rank-sources", parents=[common], help="Rank whole source videos before extracting Live moments.")
    rank_sources.add_argument("input", help="Directory containing raw source videos.")
    rank_sources.add_argument("--source-sample-fps", type=float, default=2.0, help="Cheaper FPS used when ranking whole source videos.")
    rank_sources.add_argument("--top", type=int, default=0, help="Only print the top N sources.")
    rank_sources.add_argument("--limit", type=int, default=0, help="Optional max number of source files to scan.")
    rank_sources.add_argument("--write-json", default="", help="Optional path to save the ranking JSON.")
    rank_sources.set_defaults(func=cmd_rank_sources)

    build = sub.add_parser("build", parents=[common], help="Build one Live candidate bundle from a video.")
    build.add_argument("video")
    build.add_argument("-o", "--output", default="./dist", help="Output directory")
    build.set_defaults(func=cmd_build)

    batch = sub.add_parser("batch", parents=[common], help="Batch-build candidate bundles for a directory.")
    batch.add_argument("input")
    batch.add_argument("-o", "--output", default="./dist", help="Output directory")
    batch.add_argument("--limit", type=int, default=0, help="Optional max number of source files to scan/process.")
    batch.add_argument("--top-sources", type=int, default=0, help="Rank first and only build from the top N source videos.")
    batch.add_argument("--source-sample-fps", type=float, default=2.0, help="Sampling FPS for whole-source ranking.")
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
