# SKRATCHA – by JJ DA PLUG

Scratch turntable plugin for MPC standalone (official MPC Plugin SDK). See `plugin/README.md`.

- `plugin/` – the SDK project (source, hand-made skin, built-in samples)
- `tools/` – skin generator (`make_ui.py`, photo-real drawing in `real_draw.py`), sample synth, scratch test harness
- Every push to `main` builds arm32 + arm64 in GitHub Actions and publishes a release with the plugin folder as a zip.
