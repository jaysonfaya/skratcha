# SKRATCHA – by JJ DA PLUG

Two scratch turntables with a battle crossfader, drive browser and a scratch teacher, for MPC standalone (official MPC Plugin SDK). See `plugin/README.md` (German user guide).

- `plugin/` – the SDK project (source in `src/`, generated skin in `skins/`, built-in samples in `Content/`)
- `feed/` – SKRATCHA FEED, the insert effect that links a track / the master to SKRATCHA (REC, GRAB, LIVE scratch); `tools/live_test.cpp` tests both together
- `tools/ui24.py` – SKRATCHA 2.4 skin generator (swipe rows, smooth design change, LIVE tab) (uses `ui2.py`, `ui21.py`) (uses the renderers in `make_ui.py`, `pbr.py`, `ortho3d.py`, `real_draw.py`)
  `python3 tools/ui24.py <build/params.json> plugin/skins <preview dir> tools/assets/<jf logo> tools/fonts`
- `tools/fetch_speeches.py` – downloads the public-domain FDR 1941 and Armstrong 1969 recordings from Wikimedia Commons and cuts them into the default samples 01-08 (run in CI)
- `tools/make_samples.py` – synthesises the built-in samples; `tools/scratch_test.cpp` + `analyse.py` – scratch / teacher test harness
- Every push to `main` builds arm32 + arm64 in GitHub Actions and publishes a release with the plugin folder as a zip.
