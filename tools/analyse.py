#!/usr/bin/env python3
"""Analyse SKRATCHA probe renders: L = 1 kHz tone, R = position ramp (-1..1 over 15 s of the record).

Reports per file:
  * speed taken from the ramp (file samples per output sample), and how smooth it is
    ("jitter": the part of the speed curve above 40 Hz, i.e. stepping the ear hears as zipper / graininess)
  * how well the tone follows the speed (measured vs expected frequency)
  * aliasing: tone energy left when the expected frequency is above 20 kHz (should be gone)
  * clicks: largest sample-to-sample jump of the tone channel relative to its level
and writes a PNG plot.
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, hilbert, stft

SR = 44100
N_REC = 15 * SR        # record length in samples
RAMP_PER_SAMPLE = 2.0 / (N_REC - 1)


def analyse(path, plot=None):
    sr, x = wavfile.read(path)
    L = x[:, 0].astype(np.float64)
    R = x[:, 1].astype(np.float64)
    fader = np.abs(L) + np.abs(R) > 0   # silent where nothing plays
    # position from the ramp; unwrap the loop (ramp jumps by 2)
    pos = np.unwrap(R * np.pi, discont=np.pi) / np.pi / RAMP_PER_SAMPLE
    speed = np.gradient(pos)
    sos = butter(4, 40 / (SR / 2), output="sos")
    smooth = sosfiltfilt(sos, speed)
    moving = np.abs(smooth) > 0.05
    jitter = speed - smooth
    jitter_rel = np.sqrt(np.mean((jitter[moving] / np.maximum(np.abs(smooth[moving]), 0.05)) ** 2)) * 100

    # tone frequency via the analytic signal (only where the tone is clearly present)
    a = hilbert(L)
    inst_f = np.gradient(np.unwrap(np.angle(a))) * SR / (2 * np.pi)
    amp = np.abs(a)
    expected = 1000.0 * np.abs(smooth)
    ok = moving & (amp > 0.1) & (expected > 150) & (expected < 15000)
    inst_s = sosfiltfilt(butter(2, 200 / (SR / 2), output="sos"), inst_f)
    err_cents = 1200 * np.log2(np.maximum(np.abs(inst_s[ok]), 1) / expected[ok])
    follow = np.median(np.abs(err_cents)) if ok.any() else float("nan")

    # aliasing: where the tone would be above 20 kHz it must be (nearly) gone
    hi = np.abs(speed) * 1000 > 21000
    lvl_hi = 20 * np.log10(np.sqrt(np.mean(L[hi] ** 2)) + 1e-12) if hi.sum() > 100 else None
    lvl_ref = 20 * np.log10(np.sqrt(np.mean(L[ok] ** 2)) + 1e-12) if ok.any() else None

    d = np.abs(np.diff(L))
    click = np.max(d)

    print("%-26s peak speed %5.1fx  speed jitter %5.2f%%  tone follows speed within %5.1f cents (median)  "
          "aliasing %s  max step %.3f"
          % (path, np.max(np.abs(smooth)), jitter_rel, follow,
             ("%.1f dB below tone" % (lvl_ref - lvl_hi)) if lvl_hi is not None and lvl_ref is not None else "n/a (never >21 kHz)",
             click))
    if plot:
        t = np.arange(len(L)) / SR
        fig, ax = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
        ax[0].plot(t, speed, lw=0.4, color="#999", label="speed (raw)")
        ax[0].plot(t, smooth, lw=1.2, color="#d4372c", label="speed (40 Hz)")
        ax[0].set_ylabel("speed (x normal)"); ax[0].legend(loc="upper right"); ax[0].grid(alpha=.3)
        ax[1].plot(t, jitter, lw=0.4, color="#2c6fd4"); ax[1].set_ylabel("jitter"); ax[1].grid(alpha=.3)
        f, tt, Z = stft(L, SR, nperseg=1024, noverlap=768)
        ax[2].pcolormesh(tt, f / 1000, 20 * np.log10(np.abs(Z) + 1e-7), vmin=-110, vmax=-10, shading="auto", cmap="magma")
        ax[2].set_ylabel("kHz"); ax[2].set_xlabel("s")
        fig.suptitle(path)
        fig.tight_layout(); fig.savefig(plot, dpi=90); plt.close(fig)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        analyse(p, p.replace(".wav", ".png"))
