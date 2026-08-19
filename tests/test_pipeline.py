from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from openlivephoto.analyze import analyze_video
from openlivephoto.build import build_live_bundle


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class PipelineTest(unittest.TestCase):
    def _make_video(self, path: Path, duration: float = 8.0) -> None:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30",
                "-vf", "drawbox=x='100+80*t':y=500:w=120:h=120:color=white@0.8:t=fill",
                "-t", str(duration), "-pix_fmt", "yuv420p", str(path),
            ],
            check=True,
        )

    def test_analyze_selects_valid_window_and_keyframe(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "source.mp4"
            self._make_video(video)
            result = analyze_video(video, sample_fps=4.0, target_seconds=3.0, moment_seconds=1.0)
            window = result["window"]
            self.assertGreaterEqual(window["start_time"], 0)
            self.assertLessEqual(window["keyframe_time"], 8.0)
            self.assertGreaterEqual(window["keyframe_time"], window["start_time"])
            self.assertLessEqual(window["keyframe_time"], window["end_time"])
            self.assertGreater(window["score"], 0)
            self.assertAlmostEqual(window["moment_duration"], 1.0, places=3)
            self.assertLessEqual(window["moment_end_time"] - window["moment_start_time"], 1.25)

    def test_prefers_subtle_motion_over_static_or_chaotic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            static = root / "static.mp4"
            smooth = root / "smooth.mp4"
            chaos = root / "chaos.mp4"
            mixed = root / "mixed.mp4"

            for source, filter_spec in [
                (static, "color=c=gray:size=720x1280:rate=30"),
                (smooth, "testsrc2=size=720x1280:rate=30"),
            ]:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", filter_spec, "-t", "3", "-pix_fmt", "yuv420p", str(source)],
                    check=True,
                )

            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc2=size=720x1280:rate=30",
                    "-vf", "noise=alls=80:allf=t", "-t", "3", "-pix_fmt", "yuv420p", str(chaos),
                ],
                check=True,
            )

            concat_file = root / "list.txt"
            concat_file.write_text(f"file '{static}'\nfile '{smooth}'\nfile '{chaos}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(mixed)],
                check=True,
            )

            result = analyze_video(mixed, sample_fps=4.0, target_seconds=3.0, moment_seconds=1.0)
            window = result["window"]
            self.assertGreaterEqual(window["start_time"], 2.5)
            self.assertLess(window["start_time"], 6.0)
            self.assertLess(window["avg_changed_fraction"], 0.25)

    def test_build_outputs_review_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            video = root / "source.mp4"
            out = root / "dist"
            self._make_video(video)
            bundle = build_live_bundle(
                video,
                out,
                target_seconds=3.0,
                aspect_ratio="3:4",
                sample_fps=4.0,
                moment_seconds=1.0,
            )
            self.assertTrue((bundle / "source_cover.jpg").exists())
            self.assertTrue((bundle / "source.mov").exists())
            manifest = json.loads((bundle / "manifest.json").read_text())
            self.assertEqual(manifest["target_seconds"], 3.0)
            self.assertIn("selected_window", manifest)
            self.assertEqual(manifest["moment_seconds"], 1.0)


if __name__ == "__main__":
    unittest.main()
