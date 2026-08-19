# Validation status

## Passed locally

- CLI entrypoint runs from source.
- Synthetic 8-second video can be analyzed.
- A ~1-second perceptual motion moment is selected first, then wrapped in a ~3-second Live Photo envelope.
- Cover JPG and trimmed MOV are emitted.
- Batch-oriented manifest is emitted.
- Selector test rejects fully static footage and strongly chaotic/noisy footage in favor of moderate motion.
- 3 automated `unittest` tests pass in the local Linux/ffmpeg environment.

## Passed in public GitHub CI

- macOS 14 runner installs the project and dependencies successfully.
- The AppleLivePhoto selector tests pass on macOS.
- The CI generates a synthetic source video, runs `openlive build`, then passes the resulting MOV through the MIT-licensed `nicing/make-live-photo` backend.
- The backend smoke test successfully emits the final Apple-compatible `smoke.jpg`, `smoke.mov`, and `smoke.manifest.json` pair.

## Still pending real-device validation

- Import the generated pair into macOS Photos and confirm it is recognized as a Live Photo asset.
- Sync/AirDrop from Photos to an iPhone.
- Verify playback behavior on iPhone.
- Verify Xiaohongshu recognizes and publishes the asset as an 实况图 / Live Photo.
- Test the selector on a representative corpus of real lifestyle/vlog footage rather than only synthetic fixtures.

## Why the distinction matters

The automated pipeline is now validated through macOS metadata packaging, but a CI runner cannot prove Photos/iPhone/Xiaohongshu UI behavior. The final acceptance gate is therefore a small real-device test matrix, not more synthetic unit tests.
