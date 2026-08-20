# AppleLivePhoto

[![CI](https://github.com/yangyangnovelist-hub/AppleLivePhoto/actions/workflows/ci.yml/badge.svg)](https://github.com/yangyangnovelist-hub/AppleLivePhoto/actions/workflows/ci.yml)

Open-source CLI for **ranking source videos and batch-producing Apple Live Photo candidates from ordinary video**, with an emphasis on Xiaohongshu / lifestyle content.

The creative rule behind the selector is simple:

> **动画面静拍，静止画面动态拍**
>
> Freeze the dynamic scene at the cleanest instant; let quiet scenes breathe with subtle motion.

A native iPhone Live Photo has an approximately three-second capture envelope, but perceptually it usually reads as one instant. AppleLivePhoto therefore does **not** search for three seconds of continuous action. It first finds a short, useful micro-motion moment (default: ~1 second), chooses the strongest still inside it, then wraps that moment in an approximately three-second pre/post context.

## Source selection comes first

Choosing the **source video itself** is a first-class stage, not a preprocessing detail.

A beautiful three-second cut cannot rescue a bad source. AppleLivePhoto therefore ranks raw videos before moment extraction. The whole-source ranker rewards two useful visual archetypes:

- **quiet-motion** — stable framing with local movement such as hair, fabric, leaves, hands, walking micro-motion, sunlight or shadows;
- **dynamic-freeze** — a more active scene that still contains crisp frames worth freezing as the cover.

It scores each source using:

- quality of its best Live-worthy moment,
- density of usable micro-motion,
- density of freezeable dynamic frames,
- camera/scene cleanliness,
- sharpness,
- portrait orientation and basic technical fitness,
- penalties for footage that is almost entirely static or chaotic.

This means the intended pipeline is:

**source pool → source ranking → best source videos → best moments → keyframes → Live Photo bundles**.

## What it does

Given a folder of source videos, AppleLivePhoto can:

1. **rank whole source videos before cutting anything**,
2. sample frames cheaply with FFmpeg,
3. measure motion, motion coverage, stability and sharpness,
4. reject dead-static and chaotic/noisy segments,
5. choose a short **perceptual moment**,
6. choose a clean **key frame** inside that moment,
7. create a ~3 s MOV envelope around the key frame,
8. export a review bundle containing:
   - `*_cover.jpg`
   - `*_cover.heic` when `heif-enc` is available
   - `*.mov`
   - `manifest.json`
9. optionally rank first and only build from the top-N source videos.

The CLI command is `openlive`.

## Current validation status

Local Linux/FFmpeg tests cover:

- valid moment + keyframe selection,
- preference for moderate motion over static or violently noisy footage,
- cover-frame and MOV bundle creation,
- whole-source ranking that prefers usable subtle-motion footage over static and chaotic alternatives.

True Apple Live Photo packaging is a separate metadata step. The repository includes a macOS GitHub Actions smoke test that uses the MIT-licensed [`nicing/make-live-photo`](https://github.com/nicing/make-live-photo) backend to generate the final Apple-compatible JPG/MOV pair.

See [`STATUS.md`](STATUS.md) for the distinction between automated validation and Apple-device end-to-end validation.

## Why there is still a ~3 second MOV

Apple documents that the Live Photo movie and still image are associated by a shared content identifier. A Live Photo also has a nominated photo time inside the movie. The native capture experience records context around the shutter instant, rather than a conventional three-second video scene.

References:

- Apple AVFoundation — [`livePhotoMovieMetadata`](https://developer.apple.com/documentation/avfoundation/avcapturephotosettings/livephotomoviemetadata)
- Apple LivePhotosKit JS — [`photoTime`](https://developer.apple.com/documentation/livephotoskitjs/livephotoskit.player/phototime)
- [`RhetTbull/makelive`](https://github.com/RhetTbull/makelive) — MIT, Apple Photos-compatible photo/video pairing
- [`nicing/make-live-photo`](https://github.com/nicing/make-live-photo) — MIT, writes the shared content identifier and `still-image-time` metadata track

## Installation

### Requirements

- Python 3.10+
- `ffmpeg`
- `ffprobe`
- Optional: `heif-enc`
- macOS finalization: Xcode Command Line Tools, `ffmpeg`, `exiftool`, PyObjC Quartz, plus an Apple metadata backend such as `make-live-photo`

### Install from source

```bash
git clone https://github.com/yangyangnovelist-hub/AppleLivePhoto.git
cd AppleLivePhoto
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

### Rank source videos first

```bash
openlive rank-sources ./raw-videos \
  --top 20 \
  --write-json ./dist/source-ranking.json
```

The JSON ranking includes:

- overall source score,
- visual archetype (`quiet-motion`, `dynamic-freeze`, or `mixed`),
- best-moment score,
- micro-motion density,
- freezeable-frame density,
- chaotic/static fractions,
- orientation, duration, resolution and human-readable reasons.

### Analyze one video

```bash
openlive analyze path/to/video.mp4
```

The JSON result includes the chosen perceptual moment, the ~3 s container window, the keyframe timestamp, and motion/sharpness metrics.

### Build one candidate bundle

```bash
openlive build path/to/video.mp4 \
  -o ./dist \
  --seconds 3 \
  --moment-seconds 1 \
  --aspect-ratio 3:4
```

Output:

```text
dist/video_livebundle/
├── video_cover.jpg
├── video_cover.heic   # if heif-enc exists
├── video.mov
└── manifest.json
```

### Rank first, then build only the best sources

```bash
openlive batch ./raw-videos \
  -o ./dist \
  --top-sources 20 \
  --seconds 3 \
  --moment-seconds 1 \
  --aspect-ratio 3:4
```

This also writes `dist/source_ranking.json` so the source-selection decision is auditable.

### macOS finalization hint

```bash
openlive finalize-hint \
  ./dist/example_livebundle/example_cover.heic \
  ./dist/example_livebundle/example.mov
```

## Selection model

Each sampled frame records:

- `motion`: mean absolute pixel difference from the previous sample,
- `changed_fraction`: fraction of pixels with a material change,
- `sharpness`: a lightweight gradient-based sharpness proxy.

At the **source-video level**, the ranker measures whether good moments are rare accidents or whether the source repeatedly contains usable material.

At the **moment level**, the selector rewards:

- enough movement to feel alive,
- low motion volatility,
- limited whole-frame change,
- a sharp still opportunity.

It penalizes:

- completely static footage,
- hard cuts / shake / noise,
- broad whole-frame chaos.

The keyframe is selected *inside* the short motion moment, with preference for higher sharpness and lower instantaneous motion.

## Architecture

```text
raw source-video pool
    ↓
whole-source ranking
    ↓
top source videos
    ↓
frame sampling
    ↓
motion + changed-area + sharpness metrics
    ↓
~1 s perceptual moment
    ↓
keyframe selection
    ↓
~3 s Live Photo envelope
    ↓
JPG/HEIC + MOV + manifest
    ↓
macOS Apple metadata finalization
```

## Tests

```bash
python -m unittest discover -s tests -v
```

The public CI runs both:

- Linux source-ranking + selection/bundle tests,
- a macOS smoke test against the open-source Apple metadata backend.

## Roadmap

- [ ] Directly integrate an Apple metadata backend on macOS instead of only printing a finalize hint
- [ ] Semantic source ranking: people / sunlight / candid-life / environment / title-cover relevance
- [ ] Face / subject-aware keyframe scoring
- [ ] Optical-flow motion-region scoring
- [ ] Better detection of intentional camera movement vs subject movement
- [ ] Long-video candidate ranking (top-N moments, not only top-1)
- [ ] Duplicate / near-duplicate source and candidate suppression
- [ ] Real lifestyle/vlog corpus benchmark
- [ ] Real Photos → iPhone → Xiaohongshu end-to-end validation matrix

## License

MIT. See [`LICENSE`](LICENSE).
