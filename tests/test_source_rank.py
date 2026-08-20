from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from openlivephoto.source_rank import rank_source_directory, rank_source_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class SourceRankingTest(unittest.TestCase):
    def _make_static(self, path: Path) -> None:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "color=c=gray:size=720x1280:rate=30",
                "-t", "6", "-pix_fmt", "yuv420p", str(path),
            ],
            check=True,
        )

    def _make_subtle(self, path: Path) -> None:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "color=c=#777777:size=720x1280:rate=30",
                "-vf", "drawbox=x='120+45*t':y=520:w=90:h=90:color=white@0.95:t=fill",
                "-t", "6", "-pix_fmt", "yuv420p", str(path),
            ],
            check=True,
        )

    def _make_chaotic(self, path: Path) -> None:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", "testsrc2=size=720x1280:rate=30",
                "-vf", "noise=alls=85:allf=t",
                "-t", "6", "-pix_fmt", "yuv420p", str(path),
            ],
            check=True,
        )

    def test_whole_source_score_prefers_subtle_usable_footage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            static = root / "static.mp4"
            subtle = root / "subtle.mp4"
            chaotic = root / "chaotic.mp4"
            self._make_static(static)
            self._make_subtle(subtle)
            self._make_chaotic(chaotic)

            s_static = rank_source_video(static, sample_fps=2.0)
            s_subtle = rank_source_video(subtle, sample_fps=2.0)
            s_chaotic = rank_source_video(chaotic, sample_fps=2.0)

            self.assertGreater(s_subtle.score, s_static.score)
            self.assertGreater(s_subtle.score, s_chaotic.score)
            self.assertIn(s_subtle.archetype, {"quiet-motion", "dynamic-freeze", "mixed"})
            self.assertGreater(s_subtle.best_moment_score, 0)

    def test_directory_ranking_returns_best_source_first(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_static(root / "a_static.mp4")
            self._make_subtle(root / "b_subtle.mp4")
            self._make_chaotic(root / "c_chaotic.mp4")

            ranking = rank_source_directory(root, sample_fps=2.0)
            self.assertEqual(len(ranking), 3)
            self.assertEqual(Path(ranking[0]["path"]).name, "b_subtle.mp4")
            self.assertEqual(ranking[0]["rank"], 1)
            self.assertGreater(ranking[0]["score"], ranking[-1]["score"])


if __name__ == "__main__":
    unittest.main()
