# Validation status

## Passed locally

- CLI entrypoint runs from source.
- Synthetic 8-second video can be analyzed.
- A ~1-second perceptual motion moment is selected first, then wrapped in a ~3-second Live Photo envelope.
- Cover JPG and trimmed MOV are emitted.
- Batch-oriented manifest is emitted.
- Selector test rejects fully static footage and strongly chaotic/noisy footage in favor of moderate motion.
- 3 automated `unittest` tests pass in the current Linux/ffmpeg environment.

## Designed but not yet independently executed here

- GitHub Actions Linux job (will run after repository push).
- GitHub Actions macOS job (will run after repository push).
- macOS Live Photo finalization using the MIT `make-live-photo` backend.
- Importing the resulting pair into macOS Photos.
- Sync/AirDrop to iPhone and verification that Xiaohongshu recognizes it as a Live Photo.

## Why the distinction matters

The current Linux environment can validate video selection, trimming and cover-frame extraction. True Apple Live Photo packaging depends on macOS frameworks / Apple-compatible metadata, so end-to-end validation must run on macOS and ideally be verified in Photos/iPhone.
