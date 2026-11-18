#!/usr/bin/env python3
"""SKRATCHA default samples from old public-domain radio speeches.

Downloads the recordings from Wikimedia Commons (run in CI, which has internet), cuts them into
short scratchable phrases at the pauses, cleans them up and writes 01..08 into Content/Samples.

  python3 tools/fetch_speeches.py <Content/Samples dir> [--local <dir with the source files>]

Sources (all public domain, see CREDITS.txt):
  * Franklin D. Roosevelt, address to Congress, 8 Dec 1941 (parts 1 + 2) - Public Domain Mark 1.0
  * Neil Armstrong, Apollo 11, 20 Jul 1969 ("one small step") - NASA, public domain
"""
import os
import subprocess
import sys
import urllib.parse
import urllib.request

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
SOURCES = [  # (Commons file, name prefix, phrases to take)
    ("1941 Roosevelt speech pearlharbor p1.ogg", "FDR 1941", 3),
    ("1941 Roosevelt speech pearlharbor p2.ogg", "FDR 1941", 3),
    ("Neil Armstrong small step.wav", "ARMSTRONG 1969", 2),
]
UA = "SKRATCHA-build/2.3 (https://github.com/jaysonfaya/skratcha; MPC plugin default samples) python-urllib"


def fetch(name, dst):
    """direct upload.wikimedia.org URL (md5 path, no redirect), polite User-Agent, retries on 429/5xx"""
    import hashlib
    import time
    fn = name.replace(" ", "_")
    h = hashlib.md5(fn.encode("utf-8")).hexdigest()
    urls = ["https://upload.wikimedia.org/wikipedia/commons/%s/%s/%s" % (h[0], h[:2], urllib.parse.quote(fn)),
            "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn)]
    last = None
    for attempt in range(6):
        url = urls[attempt % 2]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
                f.write(r.read())
            if os.path.getsize(dst) < 20000:
                raise RuntimeError("download too small: " + name)
            print("fetched %s (%d KB)" % (name, os.path.getsize(dst) // 1024))
            return
        except Exception as e:  # noqa: BLE001
            last = e
            print("retry %s: %s" % (name, e))
            time.sleep(5 + 15 * attempt)
    raise RuntimeError("could not download %s: %s" % (name, last))


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def clean(x):
    x = sosfilt(butter(2, 90, "highpass", fs=SR, output="sos"), x)     # rumble / hum
    x = sosfilt(butter(4, 7500, "lowpass", fs=SR, output="sos"), x)    # hiss above the voice
    return x


def phrases(x, n_take):
    """split at pauses: 10 ms RMS envelope, a pause = >= 140 ms below the noise-adaptive threshold"""
    hop = int(0.010 * SR)
    env = np.sqrt(np.convolve(x * x, np.ones(hop) / hop, "same")[::hop] + 1e-12)
    db = 20 * np.log10(env)
    floor, loud = np.percentile(db, 15), np.percentile(db, 95)
    thr = floor + 0.35 * (loud - floor)
    on = db > thr
    segs, i, n = [], 0, len(on)
    while i < n:
        if not on[i]:
            i += 1; continue
        j, gap = i, 0
        while j < n and gap < 14:
            gap = 0 if on[j] else gap + 1
            j += 1
        segs.append((i, j - gap)); i = j
    out = []
    for a, b in segs:
        d = (b - a) * 0.010
        if 0.35 <= d <= 3.2:
            score = np.mean(db[a:b]) + (3.0 if 0.6 <= d <= 2.2 else 0.0)
            out.append((score, a, b))
    out.sort(reverse=True)
    pick = sorted(out[:n_take], key=lambda t: t[1])
    res = []
    for _, a, b in pick:
        s0 = max(0, int((a * 0.010 - 0.030) * SR)); s1 = min(len(x), int((b * 0.010 + 0.060) * SR))
        res.append(x[s0:s1].copy())
    return res


def finish(y):
    f = int(0.004 * SR)
    y[:f] *= np.linspace(0, 1, f); y[-f:] *= np.linspace(1, 0, f)
    pk = np.max(np.abs(y)) + 1e-9
    y = y / pk * 0.89                                  # -1 dBFS
    return (np.clip(y, -1, 1) * 32767).astype(np.int16)


def main():
    out_dir = sys.argv[1]
    local = sys.argv[sys.argv.index("--local") + 1] if "--local" in sys.argv else None
    tmp = local or __import__("tempfile").mkdtemp(prefix="skr_speech_")   # never inside Content (would be packaged)
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    k = 1
    report = []
    for name, prefix, n_take in SOURCES:
        src = os.path.join(tmp, name)
        if not local:
            fetch(name, src)
            __import__("time").sleep(3)
        x = clean(decode(src))
        got = phrases(x, n_take)
        if len(got) < n_take:
            raise RuntimeError("only %d phrases found in %s" % (len(got), name))
        for j, y in enumerate(got):
            fn = "%02d %s %s.wav" % (k, prefix, "ABCDEFGH"[j if "p1" in name or "Armstrong" in name else j + 3])
            wavfile.write(os.path.join(out_dir, fn), SR, finish(y))
            report.append("%-30s %.2f s" % (fn, len(y) / SR))
            k += 1
    print("\n".join(report))


if __name__ == "__main__":
    main()
