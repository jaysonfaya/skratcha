#!/usr/bin/env python3
"""Synthesise SKRATCHA's built-in records (own sounds, no third-party material) into <out>/Samples/*.wav."""
import os
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

SR = 44100
rng = np.random.default_rng(1200)


def norm(x, peak=0.89):
    x = x - np.mean(x)
    return x * (peak / (np.max(np.abs(x)) + 1e-9))


def env_adsr(n, a, d, s, r):
    t = np.arange(n) / SR
    e = np.ones(n) * s
    ai = int(a * SR); di = int(d * SR); ri = int(r * SR)
    e[:ai] = np.linspace(0, 1, ai, endpoint=False)
    e[ai:ai + di] = np.linspace(1, s, di, endpoint=False)
    if ri > 0:
        e[-ri:] *= np.linspace(1, 0, ri)
    return e


def glottal(f0, n):
    """band-rich voice source: a smoothed saw with jitter, like vocal folds."""
    f = f0 * (1 + 0.004 * rng.standard_normal(n).cumsum() / np.sqrt(np.arange(1, n + 1)))
    ph = np.cumsum(f / SR) % 1.0
    src = 1.0 - 2.0 * ph
    b, a = butter(1, 4000 / (SR / 2))
    return lfilter(b, a, src)


def formant(x, freqs, bws, gains):
    y = np.zeros_like(x)
    for f, bw, g in zip(freqs, bws, gains):
        r = np.exp(-np.pi * bw / SR)
        th = 2 * np.pi * f / SR
        a = [1, -2 * r * np.cos(th), r * r]
        b = [1 - r]
        y += g * lfilter(b, a, x)
    return y


def formant_glide(x, f_from, f_to, bws, gains, chunk=256):
    """time-varying formants: process in chunks and interpolate."""
    y = np.zeros_like(x)
    n = len(x)
    zi = [np.zeros(2) for _ in f_from]
    for start in range(0, n, chunk):
        t = start / max(1, n - 1)
        seg = x[start:start + chunk]
        out = np.zeros_like(seg)
        for k in range(len(f_from)):
            f = f_from[k] + (f_to[k] - f_from[k]) * t
            r = np.exp(-np.pi * bws[k] / SR)
            th = 2 * np.pi * f / SR
            o, zi[k] = lfilter([1 - r], [1, -2 * r * np.cos(th), r * r], seg, zi=zi[k])
            out += gains[k] * o
        y[start:start + chunk] = out
    return y


def ahh():
    n = int(1.3 * SR)
    f0 = 220 * (1 + 0.012 * np.sin(2 * np.pi * 5.2 * np.arange(n) / SR))
    src = glottal(f0, n) + 0.02 * rng.standard_normal(n)
    v = formant(src, [800, 1150, 2900, 3900], [80, 90, 120, 130], [1.0, 0.6, 0.25, 0.12])
    return norm(v * env_adsr(n, 0.03, 0.15, 0.85, 0.25))


def ooh_wah():
    n = int(0.9 * SR)
    f0 = np.linspace(260, 200, n)
    src = glottal(f0, n)
    v = formant_glide(src, [350, 600, 2400], [800, 1200, 2700], [70, 80, 110], [1.0, 0.5, 0.2])
    return norm(v * env_adsr(n, 0.02, 0.1, 0.9, 0.18))


def stab():
    n = int(0.75 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in [130.81, 155.56, 196.0, 261.63, 311.13, 392.0]:   # C minor stack
        for det in (-0.004, 0.0, 0.005):
            ph = (f * (1 + det) * t + rng.random()) % 1.0
            x += 1.0 - 2.0 * ph
    b, a = butter(2, 3500 / (SR / 2))
    x = lfilter(b, a, x)
    x += 0.5 * lfilter(*butter(2, [2000 / (SR / 2), 8000 / (SR / 2)], btype="band"), rng.standard_normal(n)) * np.exp(-t * 40)
    return norm(x * np.exp(-t * 4.0) * env_adsr(n, 0.004, 0.05, 1.0, 0.05))


def tone():
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    return norm(np.sin(2 * np.pi * 1000 * t) * env_adsr(n, 0.005, 0.0, 1.0, 0.01), 0.7)


def kick(n):
    t = np.arange(n) / SR
    f = 48 + 120 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) + 0.3 * rng.standard_normal(n) * np.exp(-t * 300)


def snare(n):
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    nz = lfilter(*butter(2, 1500 / (SR / 2), btype="high"), rng.standard_normal(n)) * np.exp(-t * 14)
    return 0.5 * body + 0.8 * nz


def hat(n, open_=False):
    t = np.arange(n) / SR
    nz = lfilter(*butter(2, 7000 / (SR / 2), btype="high"), rng.standard_normal(n))
    return 0.35 * nz * np.exp(-t * (8 if open_ else 55))


def brk():
    bpm = 92
    beat = 60.0 / bpm
    bars = 2
    n = int(bars * 4 * beat * SR)
    x = np.zeros(n)
    step = beat / 4

    def put(sig, at):
        i = int(at * SR)
        j = min(n, i + len(sig))
        x[i:j] += sig[:j - i]
    pat_k = [0, 6, 8, 10, 16, 22, 24, 27]
    pat_s = [4, 12, 20, 28, 15, 31]
    for b in range(bars * 16):
        put(hat(int(0.25 * SR), open_=(b % 8 == 6)) * (0.9 if b % 2 == 0 else 0.55), b * step + (0.012 if b % 2 else 0))
    for k in pat_k:
        put(kick(int(0.5 * SR)), k * step)
    for s_ in pat_s:
        put(snare(int(0.35 * SR)) * (0.45 if s_ in (15, 31) else 1.0), s_ * step)
    x = np.tanh(1.4 * x)
    return norm(x)


def bass_drop():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    f = 55 + 40 * np.exp(-t * 3)
    x = np.tanh(1.8 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * env_adsr(n, 0.005, 0.2, 0.8, 0.5)
    return norm(x)


def fresh():
    """'fresh': a breathy f, a bright 'reh' vowel and a 'sh' tail (the classic scratch word, own synthesis)"""
    nf, nv, ns = int(0.09 * SR), int(0.32 * SR), int(0.22 * SR)
    f_ = lfilter(*butter(2, [2500 / (SR / 2), 9000 / (SR / 2)], btype="band"), rng.standard_normal(nf)) * np.linspace(0.2, 0.6, nf)
    src = glottal(np.linspace(240, 205, nv), nv) + 0.03 * rng.standard_normal(nv)
    v = formant_glide(src, [420, 1300, 2500], [560, 1850, 2650], [70, 90, 120], [1.0, 0.7, 0.3]) * env_adsr(nv, 0.015, 0.08, 0.8, 0.08)
    v = v / (np.max(np.abs(v)) + 1e-9)
    sh = lfilter(*butter(2, [1800 / (SR / 2), 6500 / (SR / 2)], btype="band"), rng.standard_normal(ns)) * env_adsr(ns, 0.03, 0.05, 0.8, 0.12)
    sh = sh / (np.max(np.abs(sh)) + 1e-9) * 0.55
    f_ = f_ / (np.max(np.abs(f_)) + 1e-9) * 0.4
    return norm(np.concatenate([f_, v, sh]))


def horn():
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for f in [233.08, 293.66, 349.23, 466.16]:            # Bb major horn stab
        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t * 3, 0, 1)
        ph = np.cumsum(f * vib / SR) % 1.0
        x += 1.0 - 2.0 * ph
    x = formant(x, [700, 1200, 2600], [200, 260, 400], [1.0, 0.8, 0.3])
    x = np.tanh(2.0 * x / (np.max(np.abs(x)) + 1e-9))
    return norm(x * env_adsr(n, 0.03, 0.12, 0.8, 0.35))


def word(segments, f0s, breath=0.03):
    """formant speech: segments = list of (dur_s, kind, F_from, F_to, gain) with kind 'v' voiced, 'n' noise, 'b' burst, 'm' nasal"""
    out = []
    pit = np.concatenate([np.linspace(a, b, int(d * SR)) for (d, _, _, _, _), (a, b) in zip(segments, f0s)])
    pos = 0
    for (dur, kind, ff, ft, g) in segments:
        n = int(dur * SR)
        if kind in ("v", "m"):
            src = glottal(pit[pos:pos + n], n) + breath * rng.standard_normal(n)
            bws = [70, 90, 120] if kind == "v" else [140, 300, 400]
            y = formant_glide(src, ff, ft, bws, [1.0, 0.6, 0.25] if kind == "v" else [1.0, 0.15, 0.05])
            y = y / (np.max(np.abs(y)) + 1e-9) * g
            e = np.ones(n); a = min(n // 4, int(0.012 * SR)); e[:a] = np.linspace(0, 1, a); e[-a:] = np.linspace(1, 0, a)
            y = y * e
        elif kind == "n":
            lo, hi = ff[0], ft[0]
            y = lfilter(*butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band"), rng.standard_normal(n))
            y = y / (np.max(np.abs(y)) + 1e-9) * g * np.sin(np.linspace(0, np.pi, n)) ** 0.7
        else:   # burst
            y = lfilter(*butter(2, [ff[0] / (SR / 2), ft[0] / (SR / 2)], btype="band"), rng.standard_normal(n)) * np.exp(-np.arange(n) / (0.006 * SR))
            y = y / (np.max(np.abs(y)) + 1e-9) * g
        out.append(y)
        pos += n
    x = np.concatenate(out)
    x = np.tanh(1.6 * x / (np.max(np.abs(x)) + 1e-9))       # a little grit, like a rap vocal
    return norm(x)


def yeah():
    return word([(0.07, "v", [300, 2200, 3000], [450, 2000, 2800], 0.7), (0.22, "v", [450, 2000, 2800], [650, 1500, 2600], 1.0),
                 (0.16, "v", [650, 1500, 2600], [600, 1250, 2500], 0.8)], [(190, 200), (200, 175), (175, 140)])


def hey():
    return word([(0.08, "n", [600], [3500], 0.5), (0.30, "v", [520, 1850, 2600], [380, 2250, 2900], 1.0)], [(220, 220), (225, 245)], breath=0.08)


def uh():
    return word([(0.03, "n", [400], [2500], 0.3), (0.20, "v", [650, 1200, 2500], [600, 1150, 2400], 1.0)], [(150, 150), (150, 120)])


def go():
    return word([(0.025, "b", [300], [2500], 0.9), (0.33, "v", [500, 950, 2400], [360, 720, 2300], 1.0)], [(170, 170), (175, 135)])


def come_on():
    return word([(0.03, "b", [1500], [4000], 0.8), (0.12, "v", [650, 1250, 2500], [600, 1150, 2400], 1.0), (0.07, "m", [260, 1000, 2200], [260, 1000, 2200], 0.5),
                 (0.20, "v", [700, 1100, 2500], [650, 1050, 2450], 1.0), (0.10, "m", [280, 1500, 2500], [260, 1400, 2400], 0.4)],
                [(165, 175), (175, 165), (160, 190), (195, 160), (160, 140)])


def check_it():
    return word([(0.04, "n", [2000], [6000], 0.6), (0.12, "v", [500, 1900, 2600], [450, 2000, 2600], 1.0), (0.03, "b", [1500], [4000], 0.7),
                 (0.10, "v", [400, 2100, 2800], [380, 2200, 2900], 0.9), (0.03, "b", [3000], [7000], 0.6)],
                [(180, 180), (185, 175), (175, 175), (170, 160), (160, 160)])


def main():
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else ".", "Samples")
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith(".wav"):
            os.remove(os.path.join(out, f))
    for name, fn in [("01 AHH", ahh), ("02 FRESH", fresh), ("03 YEAH", yeah), ("04 HEY", hey), ("05 UH", uh), ("06 GO", go),
                     ("07 COME ON", come_on), ("08 CHECK IT", check_it), ("09 BREAK 92", brk), ("10 STAB", stab),
                     ("11 HORN", horn), ("12 BASS DROP", bass_drop), ("13 OOH WAH", ooh_wah), ("14 TONE 1K", tone)]:
        x = fn()
        pad = np.zeros(int(0.05 * SR))   # a short lead-in so a scratch starts from silence
        x = np.concatenate([pad, x, pad])
        wavfile.write(os.path.join(out, name + ".wav"), SR, (x * 32767).astype(np.int16))
        print("%-14s %.2f s" % (name, len(x) / SR))


if __name__ == "__main__":
    main()
