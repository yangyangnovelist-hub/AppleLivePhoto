# AppleLivePhoto

[![CI](https://github.com/yangyangnovelist-hub/AppleLivePhoto/actions/workflows/ci.yml/badge.svg)](https://github.com/yangyangnovelist-hub/AppleLivePhoto/actions/workflows/ci.yml)

Open-source CLI for **batch-producing Apple Live Photo candidates from ordinary video**, with an emphasis on Xiaohongshu / lifestyle content.

The creative rule behind the selector is simple:

> **动画面静拍，静止画面动态拍**
>
> Freeze the dynamic scene at the cleanest instant; let quiet scenes breathe with subtle motion.

A native iPhone Live Photo has an approximately three-second capture envelope, but perceptually it usually reads as one instant. AppleLivePhoto therefore does **not** search for three seconds of continuous action. It first finds a short, useful micro-motion moment (default: ~1 second), chooses the strongest still inside it, then wraps that moment in an approximately three-second pre/post context.

## What it does

Given one video, AppleLivePhoto can:

1. sample frames cheaply with FFmpeg,
2. measure motion, motion coverage, stability and sharpness,
3. reject dead-static and chaotic/noisy segments,
4. choose a short **perceptual moment**,
5. choose a clean **key frame** inside that moment,
6. create a ~3 s MOV envelope around the key frame,
7. export a review bundle containing:
   - `*_cover.jpg`
   - `*_cover.heic` when `heif-enc` is available
   - `*.mov`
   - `manifest.json`
8. batch-process a whole directory.

The CLI command is `openlive`.

## Current validation status

Local Linux/FFmpeg tests currently cover:

- valid moment + keyframe selection,
- preference for moderate motion over static or violently noisy footage,
- cover-frame and MOV bundle creation.

True Apple Live Photo packaging is a separate metadata step. The repository includes a macOS GitHub Actions smoke test that uses the MIT-licensed [`nicing/make-live-photo`](https://github.com/nicing/make-live-photo) backend to generate the final Apple-compatible JPG/MOV pair.

See [`STATUS.md`](STATUS.md) for the distinction between locally validated behavior and Apple-device end-to-end validation.

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

### Batch-build a folder

```bash
openlive batch ./videos \
  -o ./dist \
  --seconds 3 \
  --moment-seconds 1 \
  --aspect-ratio 3:4
```

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

The selector rewards:

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
source video
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

- a Linux selection/bundle test job,
- a macOS smoke test against the open-source Apple metadata backend.

## Roadmap

- [ ] Directly integrate an Apple metadata backend on macOS instead of only printing a finalize hint
- [ ] Face / subject-aware keyframe scoring
- [ ] Optical-flow motion-region scoring
- [ ] Better detection of intentional camera movement vs subject movement
- [ ] Long-video candidate ranking (top-N moments, not only top-1)
- [ ] Duplicate / near-duplicate candidate suppression
- [ ] Real Photos → iPhone → Xiaohongshu end-to-end validation matrix

## License

MIT. See [`LICENSE`](LICENSE).
