#!/usr/bin/env python3
"""SKRATCHA 2.2 skin: ten turntable eras (look, record, label), STUDIO / BATTLE / PADS layouts with a visible
ANSICHT button, the hidden round light for the era, mirrored pads in BATTLE, a folder-tree browser with sliders and
double tap, the teacher with a basics tour and an MPC picture, and a SETUP page that is exactly the 16 Q-Links.

    ui22.py <params.json> <out skins dir> <preview dir> <jf_logo.png> <fonts dir>
"""
import json
import math
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui2 as U
import ui21 as V
from ui2 import (M, PB, O3, RD, _np, Image, ImageDraw, ImageFilter, font, save, F_BOLD, F_SEMI, F_MED, F_TIT, W, H,
                 OUT, PREV, P, define, act, comp, bounds, focus_comp, label_data, filmstrip, def_display, def_toggle,
                 def_segment, def_slider, def_readout, Tab, DEFS, cond, def_knob_named, def_text, AMBER, GREEN,
                 _region_rect, CX, CY, R_REC, Z_MAT, PITCH_X, PITCH_Y, PITCH_W, PITCH_H)
from ui21 import func_pad, glow_only, arrow_key, row_img, sel_bar_strip, hit_strip, adv_frame, strip_of, RED, CYAN, WHITE

NSTY = 10
BATTLE_SCALE = 0.6
BDX = [0, 795]
LESSONS = [p_["choices"] for p_ in M.params if p_["name"] == "Lesson"][0]

# ten eras: plinth, record (vinyl), label colours, logo colour (always the JF logo)
DESIGNS = [
    {"plinth": "oak", "title": "1912 GRAMMOPHON", "vinyl": {"col": [0.03, 0.025, 0.02], "rough": 0.20, "kind": "plain"},
     "label": [0.80, 0.72, 0.52], "logo": [0.26, 0.15, 0.07], "logo_metal": False, "label_text": "SKRATCHA GRAMMOPHON  ·  78 RPM  ·  1912"},
    {"plinth": "bakelite", "title": "1935 SCHELLACK", "vinyl": {"col": [0.018, 0.016, 0.014], "rough": 0.10, "kind": "plain"},
     "label": [0.07, 0.11, 0.40], "logo": [0.88, 0.88, 0.90], "label_text": "SKRATCHA SHELLAC  ·  78 RPM  ·  ELECTRICAL"},
    {"plinth": "mahogany", "title": "1955 ROEHRENTRUHE", "vinyl": {"col": [0.014, 0.014, 0.016], "rough": 0.14, "kind": "plain"},
     "label": [0.36, 0.05, 0.06], "logo": [0.93, 0.86, 0.66], "logo_metal": False, "label_text": "SKRATCHA HIGH FIDELITY  ·  33 1/3  ·  MONO"},
    {"plinth": "leather", "title": "1965 KOFFER", "vinyl": {"col": [0.50, 0.03, 0.04], "rough": 0.10, "kind": "plain"},
     "label": [0.94, 0.93, 0.90], "logo": [0.75, 0.05, 0.06], "logo_metal": False, "label_text": "SKRATCHA BEAT  ·  45 / 33  ·  RED VINYL"},
    {"plinth": "walnut", "title": "1974 RIEMEN", "vinyl": {"col": [0.014, 0.014, 0.016], "rough": 0.14, "kind": "plain"},
     "label": [0.88, 0.40, 0.05], "label2": [0.95, 0.75, 0.10], "logo": [0.26, 0.11, 0.04], "logo_metal": False,
     "label_text": "SKRATCHA SOUL  ·  33 1/3 RPM  ·  STEREO 1974"},
    {"plinth": "silver", "title": "1978 DIRECT DRIVE", "vinyl": {"col": [0.014, 0.014, 0.016], "rough": 0.14, "kind": "plain"},
     "label": [0.42, 0.045, 0.05], "logo": [1.0, 0.80, 0.42]},
    {"plinth": "black", "title": "1986 BATTLE", "vinyl": {"col": [0.014, 0.014, 0.016], "rough": 0.13, "kind": "splatter", "col2": [0.85, 0.85, 0.85]},
     "label": [0.93, 0.93, 0.91], "logo": [0.04, 0.04, 0.05], "logo_metal": False, "label_text": "WHITE LABEL  ·  PROMO ONLY  ·  JJ DA PLUG  ·  1986"},
    {"plinth": "gunmetal", "title": "1996 SCRATCH PRO", "vinyl": {"col": [0.10, 0.02, 0.16], "rough": 0.11, "kind": "marble", "col2": [0.45, 0.20, 0.60]},
     "label": [0.03, 0.03, 0.035], "logo": [1.0, 0.78, 0.30], "label_text": "SKRATCHA TOOLS  ·  SUPER BREAKS  ·  1996"},
    {"plinth": "white", "title": "2006 DVS TIMECODE", "vinyl": {"col": [0.06, 0.24, 0.62], "rough": 0.08, "kind": "timecode", "col2": [0.35, 0.65, 0.95]},
     "label": [0.96, 0.96, 0.97], "logo": [0.06, 0.30, 0.75], "logo_metal": False, "label_text": "CONTROL VINYL  ·  TIMECODE  ·  SIDE A  ·  2006"},
    {"plinth": "glass", "title": "2026 NEON FUTURE", "vinyl": {"col": [0.012, 0.012, 0.016], "rough": 0.10, "kind": "plain"}, "neon": True,
     "label": [0.75, 0.05, 0.60], "label2": [0.05, 0.70, 0.90], "logo": [1.0, 1.0, 1.0], "logo_glow": True,
     "label_text": "SKRATCHA FUTURE  ·  33 1/3  ·  HYPER STEREO  ·  2026"},
]


def lay_is(l):
    return "IndexedEnabling/%d/3/Parameter %d" % (l, P["Layout"])


def deck_is(d):
    return "IndexedEnabling/%d/2/Parameter %d" % (d, P["Deck"])


def mode_is(m):
    return "IndexedEnabling/%d/2/Parameter %d" % (m, P["Mode"])


def cstyle_is(s):
    return "IndexedEnabling/%d/%d/Parameter %d" % (s, NSTY, P["Style"])


def dstyle_is(d, s):
    return "IndexedEnabling/%d/%d/Parameter %d" % (s, NSTY, P["A Style" if d == 0 else "B Style"])


def lesson_is(i):
    return "IndexedEnabling/%d/%d/Parameter %d" % (i, len(LESSONS), P["Lesson"])


def quant(img):
    """palette PNG with alpha: label film strips shrink ~4x"""
    return img.quantize(colors=256, method=Image.Quantize.FASTOCTREE)


# ---------------------------------------------------------------- rendering (in worker processes)
def render_design(i):
    D = DESIGNS[i]
    img, maps, hits, rgb = U.draw_deck(D["plinth"], D)
    strip, frames, rect = U.draw_label_frames(maps, hits, D)
    out = {"bg": img, "label": frames, "label_rect": rect}
    if i == 5:   # the reference deck: strobe ring, tone arm, panel
        M._DECK.update(maps=maps, hx=hits[0], hy=hits[1], hz=hits[2], rgb=rgb)
        sstrip, sframes = M.draw_strobe_frames()
        arm, arect = M.draw_tonearm()
        out.update(strobe=sframes, strobe_rect=M._DECK["strobe_rect"], arm=arm, arm_rect=arect)
    return out


def lane_strip(lesson, w=560, h=120, step_w=70.0):
    path, fader = lesson["path"], lesson["fader"]
    S = 2
    ph_x = 90.0
    frames = []
    for k in range(32):
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], 10 * S, fill=(8, 8, 9, 255), outline=(44, 45, 48, 255), width=2 * S)
        shift = k / 4.0 * step_w
        y_of = lambda v: (14 + (1 - (v + 1) / 2) * 62) * S
        pts = []
        for b in range(-1, 3):
            for st in range(8):
                x0 = ph_x + (b * 8 + st) * step_w - shift
                if x0 > w + step_w or x0 + step_w < -step_w:
                    continue
                a_, b_ = path[st], path[st + 1]
                for j in range(11):
                    f = j / 10
                    v = a_ + (b_ - a_) * (0.5 - 0.5 * math.cos(math.pi * f))
                    pts.append(((x0 + f * step_w) * S, y_of(v)))
                for hh in range(2):
                    fp = fader[st * 2 + hh]
                    xa, xb = (x0 + hh * step_w / 2 + 2) * S, (x0 + (hh + 1) * step_w / 2 - 2) * S
                    if fp == 1:
                        d.rounded_rectangle([xa, (h - 30) * S, xb, (h - 12) * S], 4 * S, fill=AMBER + (255,))
                    elif fp == 0:
                        d.rounded_rectangle([xa, (h - 24) * S, xb, (h - 18) * S], 3 * S, fill=(70, 70, 74, 255))
                    else:
                        d.rounded_rectangle([xa, (h - 25) * S, xb, (h - 17) * S], 3 * S, fill=(150, 110, 40, 150))
                if st % 2 == 0:
                    d.line([(x0 * S, 8 * S), (x0 * S, (h - 36) * S)], fill=(60, 62, 66, 255) if st else (130, 132, 138, 255), width=S)
        pts.sort(key=lambda p: p[0])
        if len(pts) > 1:
            d.line(pts, fill=GREEN + (255,), width=4 * S, joint="curve")
        dim = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(dim).rectangle([2 * S, 2 * S, ph_x * S, (h - 2) * S], fill=(0, 0, 0, 120))
        img.alpha_composite(dim)
        d = ImageDraw.Draw(img)
        d.line([(ph_x * S, 6 * S), (ph_x * S, (h - 6) * S)], fill=(255, 255, 255, 230), width=3 * S)
        d.text((8 * S, 6 * S), "JETZT", font=font(F_BOLD, 11 * S), fill=(255, 255, 255, 200), anchor="la")
        d.text(((w - 10) * S, 6 * S), "VOR", font=font(F_SEMI, 11 * S), fill=(120, 200, 140, 255), anchor="ra")
        d.text(((w - 10) * S, 66 * S), "ZURUECK", font=font(F_SEMI, 11 * S), fill=(120, 200, 140, 255), anchor="ra")
        d.text(((w - 10) * S, (h - 30) * S), "TON", font=font(F_SEMI, 11 * S), fill=AMBER + (255,), anchor="rb")
        frames.append(img.resize((w, h), Image.LANCZOS))
    return strip_of(frames), frames


def mpc_hint(w=290, h=250):
    """the MPC seen from above: Q-Links, touch strip, 16 pads; each frame lights what to touch now"""
    S = 2
    frames = []
    # pad index 1..16 -> (col, row) with pad 1 bottom left
    def pad_xy(n):
        c, r = (n - 1) % 4, 3 - (n - 1) // 4
        return 92 + c * 46, 70 + r * 44
    plans = {   # frame: (pads {n: colour}, strip mode, qlink, caption)
        0: ({12: GREEN}, None, None, "PAD 12"), 1: ({12: RED}, None, None, "PAD 12"),
        2: ({n: AMBER for n in range(1, 9)}, None, None, "PAD 1-8"), 3: ({}, "touch", None, "STRIP"),
        4: ({}, "move", None, "VOR / ZURUECK"), 5: ({}, "lift", None, "LOSLASSEN"),
        6: ({9: RED}, None, None, "PAD 9 HALTEN"), 7: ({}, None, "right", "Q-LINK 1"),
        8: ({14: AMBER}, None, None, "PAD 14"), 9: ({13: AMBER}, None, "left", "PAD 13 + Q-LINK 1"),
        10: ({n: GREEN for n in range(1, 17)}, None, None, "FERTIG!"),
        11: ({}, "move", None, "STRIP"), 12: ({}, "slow", None, "STRIP LANGSAM"),
        13: ({9: AMBER}, "move", None, "STRIP + PAD 9"), 14: ({9: AMBER}, "move", None, "STRIP + PAD 9"),
        15: ({9: RED}, "slow", None, "PAD 9 TIPPEN"), 16: ({}, "tear", None, "STRIP"),
    }
    for k in range(17):
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([2 * S, 2 * S, (w - 2) * S, (h - 2) * S], 14 * S, fill=(30, 31, 34, 255), outline=(70, 72, 76, 255), width=2 * S)
        d.rounded_rectangle([14 * S, 12 * S, 150 * S, 52 * S], 4 * S, fill=(10, 14, 20, 255), outline=(60, 62, 66, 255), width=S)
        d.text((82 * S, 32 * S), "SKRATCHA", font=font(F_BOLD, 11 * S), fill=(255, 181, 46, 255), anchor="mm")
        pads, strip, ql, cap = plans[k]
        for q in range(4):
            qx = 170 + q * 30
            col = (255, 181, 46) if (ql and q == 0) else (90, 92, 96)
            d.ellipse([(qx - 11) * S, 22 * S, (qx + 11) * S, 44 * S], fill=(18, 18, 20, 255), outline=col + (255,), width=2 * S)
            d.text((qx * S, 52 * S), "Q%d" % (q + 1), font=font(F_SEMI, 8 * S), fill=(150, 152, 156, 255), anchor="ma")
        if ql:
            ax = 170
            dx = 1 if ql == "right" else -1
            d.line([((ax - 14 * dx) * S, 64 * S), ((ax + 18 * dx) * S, 64 * S)], fill=(255, 181, 46, 255), width=3 * S)
            d.polygon([((ax + 24 * dx) * S, 64 * S), ((ax + 14 * dx) * S, 58 * S), ((ax + 14 * dx) * S, 70 * S)], fill=(255, 181, 46, 255))
        # touch strip (vertical, left of the pads)
        sc = (60, 235, 110) if strip else (70, 72, 76)
        d.rounded_rectangle([26 * S, 72 * S, 58 * S, 236 * S], 8 * S, fill=(14, 14, 15, 255), outline=sc + (255,), width=2 * S)
        if strip in ("touch", "move", "slow", "tear"):
            d.ellipse([30 * S, 140 * S, 54 * S, 164 * S], fill=(60, 235, 110, 230))
        if strip in ("move", "slow", "tear"):
            for sgn in (-1, 1):
                if strip == "tear" and sgn == 1:
                    for o in (0, 14):
                        d.polygon([(42 * S, (178 + o) * S), (35 * S, (168 + o) * S), (49 * S, (168 + o) * S)], fill=(255, 255, 255, 255))
                    continue
                y0 = 152 + sgn * (36 if strip != "slow" else 22)
                d.polygon([(42 * S, (y0 + sgn * 10) * S), (34 * S, y0 * S), (50 * S, y0 * S)], fill=(255, 255, 255, 255))
        if strip == "lift":
            d.ellipse([60 * S, 120 * S, 80 * S, 140 * S], outline=(60, 235, 110, 255), width=2 * S)
            d.line([(62 * S, 150 * S), (76 * S, 112 * S)], fill=(255, 255, 255, 255), width=2 * S)
        for n in range(1, 17):
            px, py = pad_xy(n)
            col = pads.get(n)
            if col:
                g = Image.new("RGBA", img.size, (0, 0, 0, 0))
                ImageDraw.Draw(g).rounded_rectangle([(px - 4) * S, (py - 4) * S, (px + 44) * S, (py + 42) * S], 7 * S, fill=col + (150,))
                img.alpha_composite(g.filter(ImageFilter.GaussianBlur(5 * S)))
                d = ImageDraw.Draw(img)
            d.rounded_rectangle([px * S, py * S, (px + 40) * S, (py + 38) * S], 5 * S, fill=(col + (255,)) if col else (52, 54, 58, 255),
                                outline=(20, 20, 22, 255), width=S)
            d.text(((px + 5) * S, (py + 3) * S), str(n), font=font(F_BOLD, 9 * S), fill=(20, 20, 22, 255) if col else (150, 152, 156, 255), anchor="la")
        d.text((w / 2 * S, (h - 4) * S), cap, font=font(F_BOLD, 13 * S), fill=(255, 255, 255, 255), anchor="md")
        frames.append(img.resize((w, h), Image.LANCZOS))
    return strip_of(frames), frames


def meter_strip(w=150, h=26, n=11):
    frames = []
    for k in range(n):
        img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i in range(10):
            x0 = (4 + i * (w - 8) / 10) * 2
            col = (60, 235, 110) if i < 6 else ((255, 200, 60) if i < 8 else (255, 90, 60))
            on = i < k
            d.rounded_rectangle([x0, 4, x0 + ((w - 8) / 10 - 3) * 2, h * 2 - 4], 4, fill=col + ((255,) if on else (50,)))
        frames.append(img.resize((w, h), Image.LANCZOS))
    return strip_of(frames), frames


def row_comp(key, w, h, row_fn, clear_strip, dbl_handle):
    """2.3 list row: the whole row is a swipe surface (vertical drag = scroll, bound to Data),
    tap = select (flips the row's own tap parameter on handle Tap), double tap = open / load (handle Dbl)"""
    acts = [act("Mouse Down", "Toggle Switch", "Tap"), act("Double Click", "Toggle Switch", dbl_handle)]
    comps = [comp("Row", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": row_fn}, bounds(0, 0, w, h)),
             comp("Swipe", "Knob", filmstrip(clear_strip, 2, "Vertical"), bounds(0, 0, w, h))]
    return define(key, acts, comps)


def go_key(w, h, kind, on):
    """row end key: a play-style arrow (open folder) or a plus (load the file into the current slot)"""
    S = 3
    img = M._key_pbr(w, h, "", on, led=False, style="dark").resize((w * S, h * S), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    cx, cy = w / 2 * S, (h / 2 - 2) * S
    col = (AMBER + (255,)) if not on else (255, 255, 255, 255)
    a = 10 * S
    if kind == "open":
        d.polygon([(cx - a * 0.6, cy - a), (cx - a * 0.6, cy + a), (cx + a * 0.9, cy)], fill=col)
    else:
        t = 3 * S
        d.rectangle([cx - a, cy - t, cx + a, cy + t], fill=col); d.rectangle([cx - t, cy - a, cx + t, cy + a], fill=col)
    return img.resize((w, h), Image.LANCZOS)


def rec_key(size, on):
    """round REC key: dark rubber with a red dome"""
    S = 4
    n = size * S
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4 * S, 8 * S, n - 4 * S, n], fill=(0, 0, 0, 120))
    d.ellipse([4 * S, 4 * S, n - 4 * S, n - 8 * S], fill=(28, 28, 30, 255), outline=(70, 70, 74, 255), width=2 * S)
    r0 = int(n * 0.28)
    c = n // 2
    base = (230, 40, 36) if on else (150, 28, 26)
    for k in range(r0, 0, -1):
        t = k / r0
        col = tuple(int(v * (0.65 + 0.35 * (1 - t))) for v in base)
        d.ellipse([c - k, c - 4 * S - k, c + k, c - 4 * S + k], fill=col + (255,))
    d.text((c, n - 30 * S), "REC", font=font(F_BOLD, 22 * S), fill=(236, 236, 238, 255), anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


def rec_ring(size):
    S = 4
    n = size * S
    g = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    c = n // 2
    r = int(n * 0.40)
    d.ellipse([c - r, c - 4 * S - r, c + r, c - 4 * S + r], outline=(255, 50, 40, 255), width=8 * S)
    g = g.filter(ImageFilter.GaussianBlur(6 * S))
    d = ImageDraw.Draw(g)
    d.ellipse([c - r, c - 4 * S - r, c + r, c - 4 * S + r], outline=(255, 90, 70, 255), width=3 * S)
    return g.resize((size, size), Image.LANCZOS)


def live_glow(w, h):
    S = 3
    g = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    d.rounded_rectangle([10 * S, 10 * S, (w - 10) * S, (h - 10) * S], 14 * S, fill=(255, 40, 30, 70), outline=(255, 60, 40, 255), width=4 * S)
    g2 = g.filter(ImageFilter.GaussianBlur(5 * S)); g2.alpha_composite(g)
    d = ImageDraw.Draw(g2)
    d.text((w * S / 2, h * S / 2), "LIVE", font=font(F_BOLD, 40 * S), fill=(255, 235, 230, 255), anchor="mm")
    return g2.resize((w, h), Image.LANCZOS)


def meter_bar(w, h, frames=16, segs=24):
    out = []
    for k in range(frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        sw = w / segs
        lit = int(round(segs * k / (frames - 1)))
        for j in range(segs):
            col = (60, 235, 110) if j < segs * 0.66 else ((255, 181, 46) if j < segs * 0.88 else (255, 60, 40))
            a = 255 if j < lit else 40
            d.rounded_rectangle([j * sw + 2, 2, (j + 1) * sw - 2, h - 3], 3, fill=col + (a,))
        out.append(img)
    return strip_of(out), out


def dip_strip(w, h, frames=8, max_alpha=120):
    """the short dim during a design change: frame 0 clear, frame 7 about 47 % dark"""
    out = []
    for k in range(frames):
        a = int(round(max_alpha * (k / (frames - 1)) ** 1.3))
        out.append(Image.new("RGBA", (w, h), (6, 6, 8, a)))
    return strip_of(out)


def swipe_row(key, w, h, strip_fn, frames):
    """2.4 list row: built exactly like the scroll bar (that one works on the MPC):
    vertical drag = scroll (Data), double tap = open / load (Tap)"""
    acts = [act("Mouse Down", "Q-Link"), act("Double Click", "Toggle Switch", "Tap"), act("Enter Pressed", "Toggle Switch", "Tap")]
    comps = [focus_comp(w, h), comp("Swipe", "Knob", filmstrip(strip_fn, frames, "Vertical"), bounds(0, 0, w, h))]
    return define(key, acts, comps)


# ======================================================================================================
def main():
    lessons = V.read_lessons()
    U.CLEAR = save(Image.new("RGBA", (4, 8), (0, 0, 0, 0)), "sk_clear_f2.png")
    CLEAR = U.CLEAR
    knob_strip, knob_frames = M.draw_knob_strip(72, 64)
    knob_fn = save(knob_strip, "sk_knob72_f64.png")
    knobN = def_knob_named("skKnobN72", knob_fn, 64, 72)
    led_s, led_frames = M.draw_led_strip(170, 28, 33)
    led_fn = save(led_s, "sk_stripled_f33.png")

    def hidden(w, h):
        return define("skHidden_%dx%d" % (w, h), [act("Mouse Down", "Toggle Switch")],
                      [comp("Button", "Button", {"version": 2, "onImage": CLEAR, "offImage": CLEAR, "buttonId": 1, "numButtonsInGroup": 1,
                                                 "handleName": "Data", "gestureBehaviour": "Instant"}, bounds(0, 0, w, h))])

    keys = {}

    def key(name, w, h, label, led=True, style="dark"):
        k_ = "%s_%dx%d" % (name, w, h)
        if k_ not in keys:
            on = M.draw_key(w, h, label, True, led, None, style); off = M.draw_key(w, h, label, False, led, None, style)
            keys[k_] = (save(on, "sk_key_%s_on.png" % k_), save(off, "sk_key_%s_off.png" % k_), on, off)
        return keys[k_]

    def pvs(pv):
        return [] if pv is None else (pv if isinstance(pv, list) else [pv])

    def segments(tab, pv, pname, labels, x, y, w, h, gap=6, style="dark", conds=(), first_on=0):
        for i, lab in enumerate(labels):
            nm = ("%s_%d" % (pname, i)).replace(" ", "").replace("/", "").replace("#", "s").lower()
            on, off, on_i, off_i = key(nm, w, h, lab, True, style)
            tab.place(def_segment("skSeg_%s_%dx%d" % (nm, w, h), on, off, w, h, i, len(labels)), P[pname], x + i * (w + gap), y, w, h, name=lab)
            if conds: cond(tab, *conds)
            for p_ in pvs(pv): p_.alpha_composite(on_i if i == first_on else off_i, (x + i * (w + gap), y))

    def toggle(tab, pv, pname, name, label, x, y, w, h, style="dark", conds=(), on_prev=False, momentary=False):
        on, off, on_i, off_i = key(name, w, h, label, True, style)
        tab.place(def_toggle("skTg_%s_%dx%d%s" % (name, w, h, "m" if momentary else ""), off if momentary else on, off, w, h), P[pname], x, y, w, h, name=name)
        if conds: cond(tab, *conds)
        for p_ in pvs(pv): p_.alpha_composite(on_i if on_prev else off_i, (x, y))

    def disp(tab, key_, fn, frames, pname, x, y, w, h, conds=()):
        tab.place(def_display(key_, fn, frames, w, h), P[pname], x, y, w, h, name=key_)
        if conds: cond(tab, *conds)

    def knobs(tab, pv, names, x0, y, step, conds=(), frame=40, vertical=False):
        for i, n_ in enumerate(names):
            x_, y_ = (x0, y + i * step) if vertical else (x0 + i * step, y)
            tab.place(knobN, P[n_], x_, y_, 72, 112, name="k_%s" % n_)
            if conds: cond(tab, *conds)
            for p_ in pvs(pv):
                p_.alpha_composite(knob_frames[frame], (x_, y_ + 20))
                ImageDraw.Draw(p_).text((x_ + 36, y_ + 9), n_, font=font(F_TIT, 13), fill=(216, 218, 222), anchor="mm")

    padimg_cache = {}

    def pimgs(tag, num, label, col, pw, ph, sub=None, big=False):
        k_ = (tag, pw, ph)
        if k_ not in padimg_cache:
            on = func_pad(pw, ph, num, label, True, col, sub, big); off = func_pad(pw, ph, num, label, False, col, sub, big)
            padimg_cache[k_] = (save(on, "sk_pad_%s_%dx%d_on.png" % (tag, pw, ph)), save(off, "sk_pad_%s_%dx%d_off.png" % (tag, pw, ph)), on, off)
        return padimg_cache[k_]

    def latch_pad(tab, pv, tag, num, label, sub, col, pname, ledp, x, y, pw, ph, conds, big=False):
        """a pad that works by touch (tap on / tap off) and also lights while the hardware pad is held"""
        on, off, on_i, off_i = pimgs(tag, num, label, col, pw, ph, sub, big)
        tab.place(def_toggle("skPad_%s_%dx%d" % (tag, pw, ph), on, off, pw, ph), P[pname], x, y, pw, ph, name=tag); cond(tab, *conds)
        gl = glow_only(pw, ph, col)
        disp(tab, "skGlow_%s_%dx%d" % (tag, pw, ph), save(strip_of(gl), "sk_glow_%s_%dx%d_f2.png" % (tag, pw, ph)), 2, ledp, x, y, pw, ph, conds)
        for p_ in pvs(pv): p_.alpha_composite(off_i, (x, y))

    def padmap(tab, pv, x0, y0, pw, ph, cx, cy, conds, big=False):
        X = lambda c: x0 + c * cx
        Y = lambda r: y0 + r * cy
        for c, (tag, num, lab, col, pname, kind, bid) in enumerate([
                ("decka", 13, "DECK A", AMBER, "Deck", "seg", 0), ("deckb", 14, "DECK B", AMBER, "Deck", "seg", 1),
                ("rev", 15, "REVERSE", AMBER, "Reverse", "tog", 1), ("slip", 16, "SLIP", CYAN, "Slip", "tog", 1)]):
            on, off, on_i, off_i = pimgs(tag, num, lab, col, pw, ph, None, big)
            if kind == "seg":
                tab.place(def_segment("skPad_%s_%dx%d" % (tag, pw, ph), on, off, pw, ph, bid, 2), P[pname], X(c), Y(0), pw, ph, name=tag)
            else:
                tab.place(def_toggle("skPad_%s_%dx%d" % (tag, pw, ph), on, off, pw, ph), P[pname], X(c), Y(0), pw, ph, name=tag)
            cond(tab, *conds)
            for p_ in pvs(pv): p_.alpha_composite(on_i if tag == "decka" else off_i, (X(c), Y(0)))
        latch_pad(tab, pv, "cut", 9, "CUT", "TIPPEN / HALTEN", RED, "Cut Latch", "Pad Cut", X(0), Y(1), pw, ph, conds, big)
        latch_pad(tab, pv, "hold", 10, "HOLD", "HAND DRAUF", RED, "Hold Latch", "Pad Hold", X(1), Y(1), pw, ph, conds, big)
        on, off, on_i, off_i = pimgs("cue", 11, "CUE", WHITE, pw, ph, "HOLD+CUE = SETZEN", big)
        tab.place(def_toggle("skPad_cue_%dx%d" % (pw, ph), off, off, pw, ph), P["Cue Tap"], X(2), Y(1), pw, ph, name="cue"); cond(tab, *conds)
        gl = glow_only(pw, ph, WHITE)
        disp(tab, "skPadCueLit_%dx%d" % (pw, ph), save(strip_of(gl), "sk_padglow_white_%dx%d_f2.png" % (pw, ph)), 2, "Pad Cue", X(2), Y(1), pw, ph, conds)
        for p_ in pvs(pv): p_.alpha_composite(off_i, (X(2), Y(1)))
        on, off, on_i, off_i = pimgs("start", 12, "START", GREEN, pw, ph, "STOP", big)
        tab.place(def_toggle("skPad_start_%dx%d" % (pw, ph), on, off, pw, ph), P["Start/Stop"], X(3), Y(1), pw, ph, name="start"); cond(tab, *conds)
        for p_ in pvs(pv): p_.alpha_composite(on_i, (X(3), Y(1)))
        names = ["AHH", "FRESH", "YEAH", "HEY", "UH", "GO", "COME ON", "CHECK IT"]
        for s in range(8):
            c, r = s % 4, (2 if s >= 4 else 3)
            on, off, on_i, off_i = pimgs("slot%d" % (s + 1), s + 1, "", AMBER, pw, ph, None, big)
            tab.place(def_segment("skPad_slot%d_%dx%d" % (s, pw, ph), on, off, pw, ph, s, 8), P["Slot"], X(c), Y(r), pw, ph, name="slot%d" % s); cond(tab, *conds)
            fs = 22 if big else 13
            tab.place(def_text("skSlotName_%dx%d" % (pw, ph), pw - 8, 26, fs, "ffe6e7ea", "horizontallyCentred verticallyCentred"),
                      P["A Slot %d Name" % (s + 1)], X(c) + 4, Y(r) + ph // 2 - (10 if not big else 6), pw - 8, 26, name="sn%d" % s); cond(tab, *conds)
            for p_ in pvs(pv):
                p_.alpha_composite(on_i if s == 0 else off_i, (X(c), Y(r)))
                ImageDraw.Draw(p_).text((X(c) + pw / 2, Y(r) + ph / 2 + (3 if not big else 7)), names[s], font=font(F_TIT, fs), fill=(230, 231, 234), anchor="mm")

    def padmap_battle(tab, pv, x0, y0, pw, ph, cx, cy, conds):
        """BATTLE: left half deck A, right half deck B, mirrored (outer column = START / CUT / slot 3 / slot 1)"""
        X = lambda c: x0 + c * cx
        Y = lambda r: y0 + r * cy
        names = {0: ["AHH", "FRESH", "YEAH", "HEY"], 1: ["BREAK 92", "STAB", "HORN", "BASS DROP"]}
        for d in range(2):
            Ln = "AB"[d]
            col_of = (lambda inner: inner) if d == 0 else (lambda inner: 3 - inner)
            # numbers on the MPC for the outer / inner column of this side
            num = lambda r, inner: (3 - r) * 4 + col_of(inner) + 1
            # top row: START, DECK
            on, off, on_i, off_i = pimgs("bstart%s" % Ln, num(0, 0), "START " + Ln, GREEN, pw, ph)
            tab.place(def_toggle("skBPad_start%s" % Ln, on, off, pw, ph), P["%s Start/Stop" % Ln], X(col_of(0)), Y(0), pw, ph, name="bst%s" % Ln); cond(tab, *conds)
            for p_ in pvs(pv): p_.alpha_composite(off_i, (X(col_of(0)), Y(0)))
            on, off, on_i, off_i = pimgs("bdeck%s" % Ln, num(0, 1), "DECK " + Ln, AMBER, pw, ph)
            tab.place(def_segment("skBPad_deck%s" % Ln, on, off, pw, ph, d, 2), P["Deck"], X(col_of(1)), Y(0), pw, ph, name="bdk%s" % Ln); cond(tab, *conds)
            for p_ in pvs(pv): p_.alpha_composite(on_i if d == 0 else off_i, (X(col_of(1)), Y(0)))
            # row 2: CUT, CUE (touch works for the active deck; the light shows the hardware pad of this side)
            on, off, on_i, off_i = pimgs("bcut%s" % Ln, num(1, 0), "CUT " + Ln, RED, pw, ph)
            tab.image("bcutimg%s" % Ln, off, X(col_of(0)), Y(1), pw, ph); cond(tab, *conds)
            tab.place(def_toggle("skBPad_cut%s" % Ln, on, off, pw, ph), P["Cut Latch"], X(col_of(0)), Y(1), pw, ph, name="bct%s" % Ln); cond(tab, *(tuple(conds) + (deck_is(d),)))
            gl = glow_only(pw, ph, RED)
            disp(tab, "skBGlowCut", save(strip_of(gl), "sk_glow_bcut_f2.png"), 2, "Pad Cut %s" % Ln, X(col_of(0)), Y(1), pw, ph, conds)
            on, off, on_i, off_i = pimgs("bcue%s" % Ln, num(1, 1), "CUE " + Ln, WHITE, pw, ph)
            tab.image("bcueimg%s" % Ln, off, X(col_of(1)), Y(1), pw, ph); cond(tab, *conds)
            tab.place(def_toggle("skBPad_cue%s" % Ln, off, off, pw, ph), P["Cue Tap"], X(col_of(1)), Y(1), pw, ph, name="bcu%s" % Ln); cond(tab, *(tuple(conds) + (deck_is(d),)))
            for p_ in pvs(pv):
                p_.alpha_composite(pimgs("bcut%s" % Ln, num(1, 0), "CUT " + Ln, RED, pw, ph)[3], (X(col_of(0)), Y(1)))
                p_.alpha_composite(off_i, (X(col_of(1)), Y(1)))
            # rows 3 + 4: slots 3 4 / 1 2
            for r, (s_out, s_in) in ((2, (2, 3)), (3, (0, 1))):
                for inner, sl in ((0, s_out), (1, s_in)):
                    on, off, on_i, off_i = pimgs("bslot%s%d" % (Ln, sl + 1), num(r, inner), "", AMBER, pw, ph)
                    x_, y_ = X(col_of(inner)), Y(r)
                    tab.place(def_segment("skBPad_slot%s%d" % (Ln, sl), on, off, pw, ph, sl, 8), P["%s Slot" % Ln], x_, y_, pw, ph, name="bsl%s%d" % (Ln, sl)); cond(tab, *conds)
                    nm = P["Deck A Slot %d" % (sl + 1)] if d == 0 else P["B Slot %d Name" % (sl + 1)]
                    tab.place(def_text("skSlotName_%dx%d" % (pw, ph), pw - 8, 26, 13, "ffe6e7ea", "horizontallyCentred verticallyCentred"), nm, x_ + 4, y_ + ph // 2 - 10, pw - 8, 26,
                              name="bsn%s%d" % (Ln, sl)); cond(tab, *conds)
                    for p_ in pvs(pv):
                        p_.alpha_composite(on_i if sl == 0 else off_i, (x_, y_))
                        ImageDraw.Draw(p_).text((x_ + pw / 2, y_ + ph / 2 + 3), names[d][sl], font=font(F_TIT, 13), fill=(230, 231, 234), anchor="mm")

    def layout_button(tab, pv, x, y, w, conds):
        """visible ANSICHT key: its lower line says what you have now and what one tap gives you"""
        k_ = "ansicht_%d" % w
        if k_ not in keys:
            imgs = []
            for on_ in (True, False):
                im = M._key_pbr(w, 60, "", on_, led=False, style="dark").resize((w * 3, 180), Image.LANCZOS)
                ImageDraw.Draw(im).text((w * 1.5, 46), "ANSICHT WECHSELN", font=font(F_BOLD, 39), fill=(235, 236, 240, 255), anchor="mm")
                imgs.append(im.resize((w, 60), Image.LANCZOS))
            keys[k_] = (save(imgs[1], "sk_key_%s.png" % k_), save(imgs[1], "sk_key_%s.png" % k_), imgs[1], imgs[1])
        fn = keys[k_][0]
        tab.place(def_toggle("skTg_%s" % k_, fn, fn, w, 60), P["Layout Tap"], x, y, w, 60, name="ansicht"); cond(tab, *conds)
        tab.place(def_text("skLayHint_%d" % w, w - 12, 20, 12, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Layout Hint"], x + 6, y + 28, w - 12, 20, name="layhint")
        cond(tab, *conds)
        for p_ in pvs(pv):
            p_.alpha_composite(keys[k_][2], (x, y))
            ImageDraw.Draw(p_).text((x + w / 2, y + 38), "JETZT STUDIO  >  BATTLE", font=font(F_TIT, 12), fill=AMBER, anchor="mm")

    def small_key(name, w, h, label, mom=False):
        k_ = "sk_%s_%dx%d" % (name, w, h)
        if k_ not in keys:
            ims = []
            for on_ in (True, False):
                im = M._key_pbr(w, h, "", on_, led=False, style="dark").resize((w * 3, h * 3), Image.LANCZOS)
                d = ImageDraw.Draw(im)
                if on_ and not mom:
                    d.ellipse([7 * 3, (h / 2 - 3) * 3, 13 * 3, (h / 2 + 3) * 3], fill=(255, 60, 30, 255))
                d.text(((w / 2 + 4) * 3, (h / 2 - 1) * 3), label, font=font(F_BOLD, 11 * 3), fill=(230, 232, 236, 255), anchor="mm")
                ims.append(im.resize((w, h), Image.LANCZOS))
            keys[k_] = (save(ims[0], "sk_%s_on.png" % k_), save(ims[1], "sk_%s_off.png" % k_), ims[0], ims[1])
        return keys[k_]

    # ================= render the ten eras =================
    print("rendering 10 turntables ...", flush=True)
    with Pool(int(os.environ.get("SKR_JOBS", "3"))) as pool:
        R = pool.map(render_design, range(NSTY))
    ref = R[5]
    strobe_frames, (srx, sry, srw, srh) = ref["strobe"], ref["strobe_rect"]
    arm, (ax, ay, aw, ah) = ref["arm"], ref["arm_rect"]
    lrx, lry, lrw, lrh = ref["label_rect"]

    deck = Tab("DECK", save(Image.new("RGB", (W, H), (14, 14, 15)), "sk_bg_black.png"))
    L0, L1, L2 = lay_is(0), lay_is(1), lay_is(2)
    PX = 806
    # ---------------- STUDIO ----------------
    # 2.4: all 10 decks in ONE film strip (frame = the shown style) and every label always present
    # (frame 0 = empty): the design changes by frame, nothing is hidden or shown -> no flash
    deck_strip = strip_of([R[i]["bg"].crop((0, 0, PX + 6, H)).convert("RGB").convert("RGBA") for i in range(NSTY)])
    disp(deck, "skDeckAll", save(deck_strip.convert("RGB"), "sk_decks_f10.jpg" if False else "sk_decks_f10.png"), NSTY, "Shown Style", 0, 0, PX + 6, H, (L0,))
    blank_lab = Image.new("RGBA", R[0]["label"][0].size, (0, 0, 0, 0))
    for i in range(NSTY):
        lab = quant(strip_of([blank_lab] + list(R[i]["label"])))
        disp(deck, "skLabel%d" % i, save(lab, "sk_label%d_f49.png" % i), 49, "Label %d" % i, lrx, lry, lrw, lrh, (L0,))
    panel = ref["bg"].crop((PX, 0, W, H)).convert("RGBA")
    pm = Image.new("L", panel.size, 0)
    ImageDraw.Draw(pm).rounded_rectangle([812 - PX - 1, 5, 1274 - PX + 1, 623], 16, fill=255)
    pbg = Image.new("RGBA", panel.size, (14, 14, 15, 255)); pbg.paste(panel, (0, 0), pm)
    deck.image("panel", save(pbg, "sk_panel.png"), PX, 0, W - PX, H); cond(deck, L0)
    disp(deck, "skStrobe", save(strip_of(strobe_frames), "sk_strobe_f8.png"), 8, "Strobe", srx, sry, srw, srh, (L0,))
    deck.image("Tonearm", save(arm, "sk_tonearm.png"), ax, ay, aw, ah); cond(deck, L0)
    dip_fn = save(dip_strip(PX + 6, H), "sk_dip_f8.png")
    disp(deck, "skDip", dip_fn, 8, "Dip", 0, 0, PX + 6, H, (L0,))
    prevs = []
    for i in (5, 0, 9):
        pv_ = Image.new("RGBA", (W, H), (14, 14, 15, 255))
        pv_.alpha_composite(R[i]["bg"].crop((0, 0, PX + 6, H)), (0, 0)); pv_.alpha_composite(pbg, (PX, 0))
        pv_.alpha_composite(strobe_frames[0], (srx, sry)); pv_.alpha_composite(R[i]["label"][3], (lrx, lry)); pv_.alpha_composite(arm, (ax, ay))
        prevs.append(pv_)
    badge = [save(U.deck_badge(Lt, None), "sk_badge_%s.png" % Lt.lower()) for Lt in "AB"]
    for d in range(2):
        deck.image("badge%d" % d, badge[d], 116, 20, 96, 44); cond(deck, L0, deck_is(d))
    for p_ in prevs: p_.alpha_composite(Image.open(os.path.join(OUT, badge[0])), (116, 20))
    jrx, jry, jrw, jrh = _region_rect(CX, CY, R_REC, Z_MAT)
    jdef = define("skJog", [act("Mouse Down", "Q-Link")], [comp("Jog", "Knob", filmstrip(CLEAR, 2, "AbsoluteRotaryKnob"), bounds(0, 0, jrw, jrh))])
    deck.place(jdef, P["Platter"], jrx, jry, jrw, jrh, name="jog"); cond(deck, L0)
    deck.place(hidden(72, 72), P["Look Tap"], 20, 18, 72, 72, name="look0"); cond(deck, L0)
    toggle(deck, prevs, "Start/Stop", "start", "START·STOP", 16, 548, 132, 58, "silver", (L0,))
    segments(deck, prevs, "Speed", ["33", "45"], 520, 556, 66, 52, gap=6, style="silver", conds=(L0,))
    pf_strip, pf_frames = M.draw_pitch_fader(PITCH_W, PITCH_H, 41)
    deck.place(def_slider("skPitch", save(pf_strip, "sk_pitch_f41.png"), 41, PITCH_W, PITCH_H, "Vertical"), P["Pitch"], PITCH_X, PITCH_Y, PITCH_W, PITCH_H, name="pitch")
    cond(deck, L0)
    for p_ in prevs: p_.alpha_composite(pf_frames[20], (PITCH_X, PITCH_Y))
    layout_button(deck, prevs, 158, 552, 176, (L0,))
    deck.place(def_text("skRecName", 300, 30, 21, "ffffb52e"), P["Record"], 832, 13, 300, 30, name="rec"); cond(deck, L0)
    deck.place(def_text("skDesign", 300, 16, 11, "ffb08a40"), P["Design"], 832, 42, 300, 16, name="design"); cond(deck, L0)
    deck.place(def_text("skPitchRo", 128, 44, 20, "ffffb52e", "right verticallyCentred"), P["Pitch"], 1132, 14, 128, 44, name="pro"); cond(deck, L0)
    padmap(deck, prevs, 822, 68, 106, 62, 112, 69, (L0,))
    knobs(deck, prevs, ["Strip Range", "Fader Curve", "Deck Volume", "Level"], 830, 356, 112, (L0, mode_is(0)))
    knobs(deck, None, ["Smooth", "Catch", "Cut Lag", "Crackle"], 830, 356, 112, (L0, mode_is(1)))
    deck.image("advframe", save(adv_frame(456, 128), "sk_advframe.png"), 816, 342, 456, 128); cond(deck, L0, mode_is(1))
    cf_strip, cf_frames = U.crossfader_strip(340, 72, 61)
    cf_fn = save(cf_strip, "sk_xfader_f61.png")
    deck.place(def_slider("skXFader", cf_fn, 61, 340, 72, "Horizontal"), P["Crossfader"], 860, 476, 340, 72, name="xfader"); cond(deck, L0)
    for p_ in prevs: p_.alpha_composite(cf_frames[8], (860, 476))
    cl_strip, cl_frames = U.led_strip(34, 34, (255, 60, 30))
    cl_fn = save(cl_strip, "sk_cutled_f2.png")
    disp(deck, "skCutLed", cl_fn, 2, "A Cut LED", 813, 494, 34, 34, (L0,))
    disp(deck, "skCutLed", cl_fn, 2, "B Cut LED", 1235, 494, 34, 34, (L0,))
    segments(deck, prevs, "Cut Mode", ["CUT ZU", "CUT AUF"], 822, 554, 86, 36, gap=4, conds=(L0,))
    cv_strip, cv_frames = U.curve_strip(112, 36, 21)
    cv_fn = save(cv_strip, "sk_curve_f21.png")
    disp(deck, "skCurve", cv_fn, 21, "Fader Curve", 1004, 554, 112, 36, (L0,))
    for p_ in prevs: p_.alpha_composite(cv_frames[17], (1004, 554))
    toggle(deck, prevs, "Mode", "advanced", "ADVANCED", 1124, 554, 144, 36, "dark", (L0,))
    disp(deck, "skStripLed", led_fn, 33, "Strip LED", 822, 596, 170, 28, (L0,))
    deck.place(def_text("skTip", 262, 26, 13, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 1002, 596, 262, 26, name="tip"); cond(deck, L0)
    # ADVANCED: compact plate next to the ANSICHT key
    deck.image("advplate", save(V.adv_plate(180, 106), "sk_advplate.png"), 338, 518, 180, 106); cond(deck, L0, mode_is(1))
    advp = [("Hamster", "hamster", "HAMSTER", False), ("After Scratch", "runon", "WEITERLAUF", False), ("Set Cue Tap", "setcue", "CUE SETZEN", True),
            ("Fire", "fireplay", "FIRE=PLAY", False), ("Deck On", "deckon", "DECK ON", False), ("Slip", "slipA", "SLIP", False)]
    for i, (pn, nm, lab, mom) in enumerate(advp):
        x_, y_ = 344 + (i % 2) * 86, 538 + (i // 2) * 28
        on, off, on_i, off_i = small_key(nm, 84, 26, lab, mom)
        deck.place(def_toggle("skSm_%s" % nm, off if mom else on, off, 84, 26), P[pn], x_, y_, 84, 26, name=nm); cond(deck, L0, mode_is(1))
    d_ = ImageDraw.Draw(prevs[0])
    for p_, nm, des in zip(prevs, ["A 1  AHH", "A 1  AHH", "A 1  AHH"], ["1978 DIRECT DRIVE", "1912 GRAMMOPHON", "2026 NEON FUTURE"]):
        dd = ImageDraw.Draw(p_)
        dd.text((842, 28), nm, font=font(F_TIT, 21), fill=AMBER, anchor="lm")
        dd.text((842, 50), des, font=font(F_TIT, 11), fill=(176, 138, 64), anchor="lm")
        dd.text((1258, 36), "+0.00%", font=font(F_TIT, 20), fill=AMBER, anchor="rm")
        for i, v in enumerate(["180 deg", "SHARP 85", "0.0 dB", "-3.0 dB"]):
            dd.text((830 + i * 112 + 36, 458), v, font=font(F_TIT, 14), fill=(244, 241, 234), anchor="mm")
        dd.text((1133, 609), "LEKTION WAEHLEN, DANN START", font=font(F_TIT, 13), fill=AMBER, anchor="mm")
    for i, p_ in enumerate(prevs):
        p_.convert("RGB").save(os.path.join(PREV, "preview_studio_%d.png" % i))
    prevA = prevs[0].copy()
    prevA.alpha_composite(Image.open(os.path.join(OUT, "sk_advframe.png")), (816, 342))
    prevA.alpha_composite(Image.open(os.path.join(OUT, "sk_advplate.png")), (338, 518))
    for i, (pn, nm, lab, mom) in enumerate(advp):
        prevA.alpha_composite(small_key(nm, 84, 26, lab, mom)[2 if lab in ("WEITERLAUF", "FIRE=PLAY", "DECK ON") else 3], (344 + (i % 2) * 86, 538 + (i // 2) * 28))
    prevA.convert("RGB").save(os.path.join(PREV, "preview_studio_advanced.png"))

    # ---------------- BATTLE ----------------
    sc = BATTLE_SCALE
    dw, dh = int(808 * sc), int(628 * sc)
    def battle_items(S):
        f12 = font(F_SEMI, 12 * S)
        return [(640 * S, 26 * S, "SKRATCHA BATTLE", font(F_BOLD, 22 * S), "mm", 3 * S),
                (640 * S, 254 * S, "CROSSFADER", f12, "mm", 2 * S), (500 * S, 312 * S, "A", font(F_BOLD, 20 * S), "mm", 0),
                (780 * S, 312 * S, "B", font(F_BOLD, 20 * S), "mm", 0),
                (200 * S, 600 * S, "LINKS = DECK A", font(F_SEMI, 12 * S), "mm", S), (1080 * S, 600 * S, "RECHTS = DECK B", font(F_SEMI, 12 * S), "mm", S)]
    bbg = V.flat_bg([((489, 6, 791, 376), ""), ((6, 382, 1274, 622), "")], [(498, 48, 782, 86), (498, 92, 782, 130)], battle_items)
    bd = ImageDraw.Draw(bbg)
    bd.rounded_rectangle([506, 282, 786, 290], 4, fill=(4, 4, 4))
    for k in range(11):
        bd.line([(506 + k * 28, 266), (506 + k * 28, 272)], fill=(220, 222, 226), width=1)
    bd.line([(640, 388), (640, 616)], fill=(255, 181, 46), width=2)
    deck.image("bbg", save(bbg, "sk_bg_battle.png"), 0, 0, W, H); cond(deck, L1)
    prevB = bbg.copy()
    lab_small, small_imgs = [], []
    for i in range(NSTY):
        im = R[i]["bg"].crop((0, 0, 808, 628)).copy()
        im.alpha_composite(arm, (ax, ay))
        im = im.resize((dw, dh), Image.LANCZOS)
        fn = None
        lfr = [f.resize((int(lrw * sc), int(lrh * sc)), Image.LANCZOS) for f in R[i]["label"]]
        small_imgs.append(im)
        lab_small.append((fn, save(quant(strip_of([Image.new("RGBA", lfr[0].size, (0, 0, 0, 0))] + lfr)), "sk_label_small%d_f49.png" % i), lfr))
        if i in (5, 6):
            prevB.alpha_composite(im, (BDX[i - 5], 0))
    small_fn = save(strip_of([im_.convert("RGB").convert("RGBA") for im_ in small_imgs]).convert("RGB"), "sk_decks_small_f10.png")
    dip_s_fn = save(dip_strip(dw, dh), "sk_dip_small_f8.png")
    for d in range(2):
        disp(deck, "skDeckSmall%d" % d, small_fn, NSTY, "Shown %s Style" % "AB"[d], BDX[d], 0, dw, dh, (L1,))
    str_s = [f.resize((int(srw * sc), int(srh * sc)), Image.LANCZOS) for f in strobe_frames]
    str_fn = save(strip_of(str_s), "sk_strobe_small_f8.png")
    glow = Image.new("RGBA", (dw, dh), (0, 0, 0, 0)); gl2 = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
    ImageDraw.Draw(gl2).rounded_rectangle([3, 3, dw - 4, dh - 4], 12, outline=AMBER + (255,), width=4)
    glow.alpha_composite(gl2.filter(ImageFilter.GaussianBlur(5))); glow.alpha_composite(gl2)
    glow_fn = save(glow, "sk_deck_glow.png")
    jr = _region_rect(CX, CY, R_REC, Z_MAT)
    pfs = [f.resize((int(PITCH_W * sc), int(PITCH_H * sc)), Image.LANCZOS) for f in pf_frames]
    pfs_fn = save(strip_of(pfs), "sk_pitch_small_f41.png")
    for d in range(2):
        Ln = "AB"[d]
        ox = BDX[d]
        disp(deck, "skStrobeS", str_fn, 8, "%s Strobe" % Ln, ox + int(srx * sc), int(sry * sc), str_s[0].width, str_s[0].height, (L1,))
        for i in range(NSTY):
            fn, lfn, lfr = lab_small[i]
            disp(deck, "skLabelS%d" % i, lfn, 49, "%s Label %d" % (Ln, i), ox + int(lrx * sc), int(lry * sc), lfr[0].width, lfr[0].height, (L1,))
        prevB.alpha_composite(str_s[0], (ox + int(srx * sc), int(sry * sc)))
        prevB.alpha_composite(lab_small[5 + d][2][3], (ox + int(lrx * sc), int(lry * sc)))
        disp(deck, "skDipS%d" % d, dip_s_fn, 8, "%s Dip" % Ln, ox, 0, dw, dh, (L1,))
        deck.image("glow%d" % d, glow_fn, ox, 0, dw, dh); cond(deck, L1, deck_is(d))
        if d == 0: prevB.alpha_composite(glow, (ox, 0))
        jw, jh = int(jr[2] * sc), int(jr[3] * sc)
        jd2 = define("skJogS", [act("Mouse Down", "Q-Link")], [comp("Jog", "Knob", filmstrip(CLEAR, 2, "AbsoluteRotaryKnob"), bounds(0, 0, jw, jh))])
        deck.place(jd2, P["Platter"], ox + int(jr[0] * sc), int(jr[1] * sc), jw, jh, name="jogS%d" % d); cond(deck, L1, deck_is(d))
        deck.place(hidden(48, 48), P["Look Tap"], ox + 10, 10, 48, 48, name="look1%d" % d); cond(deck, L1, deck_is(d))
        toggle(deck, prevB, "%s Start/Stop" % Ln, "startS", "START", ox + 10, 329, 80, 35, "silver", (L1,))
        segments(deck, prevB, "%s Speed" % Ln, ["33", "45"], ox + 312, 333, 40, 31, gap=4, style="silver", conds=(L1,))
        deck.place(def_slider("skPitchS", pfs_fn, 41, pfs[0].width, pfs[0].height, "Vertical"), P["%s Pitch" % Ln], ox + int(PITCH_X * sc), int(PITCH_Y * sc),
                   pfs[0].width, pfs[0].height, name="pitchS%d" % d); cond(deck, L1)
        prevB.alpha_composite(pfs[20], (ox + int(PITCH_X * sc), int(PITCH_Y * sc)))
        deck.place(def_text("skRecNameS", 276, 38, 16, "ffffb52e"), P["%s Record" % Ln], 502, 48 + 44 * d, 276, 38, name="recS%d" % d); cond(deck, L1)
        disp(deck, "skCutLed", cl_fn, 2, "%s Cut LED" % Ln, 488 + d * 270, 319, 34, 34, (L1,))
    deck.place(def_slider("skXFader", cf_fn, 61, 340, 72, "Horizontal"), P["Crossfader"], 470, 250, 340, 72, name="xfaderB"); cond(deck, L1)
    prevB.alpha_composite(cf_frames[30], (470, 250))
    knobs(deck, prevB, ["Fader Curve", "Level"], 540, 138, 140, (L1,))
    segments(deck, prevB, "Cut Mode", ["CUT ZU", "CUT AUF"], 498, 334, 138, 34, gap=6, conds=(L1,))
    padmap_battle(deck, prevB, 402, 386, 112, 56, 120, 60, (L1,))
    disp(deck, "skStripLed", led_fn, 33, "Strip LED", 24, 398, 170, 28, (L1,))
    deck.place(def_text("skTipB", 360, 30, 13, "ffffb52e"), P["Tip"], 24, 432, 360, 30, name="tipB"); cond(deck, L1)
    knobs(deck, prevB, ["Strip Range", "Smooth"], 40, 470, 140, (L1,))
    knobs(deck, prevB, ["A Volume", "B Volume"], 950, 470, 140, (L1,))
    layout_button(deck, prevB, 900, 404, 176, (L1,))
    toggle(deck, prevB, "After Scratch", "runon", "WEITERLAUF", 1086, 418, 170, 44, "dark", (L1,), on_prev=True)
    pb_ = ImageDraw.Draw(prevB)
    pb_.text((506, 67), "A 1  AHH", font=font(F_TIT, 16), fill=AMBER, anchor="lm"); pb_.text((506, 111), "B 1  BREAK 92", font=font(F_TIT, 16), fill=AMBER, anchor="lm")
    prevB.convert("RGB").save(os.path.join(PREV, "preview_battle.png"))

    # ---------------- PADS ----------------
    def pads_items(S):
        return [(1016 * S, 156 * S, "CROSSFADER", font(F_SEMI, 12 * S), "mm", 2 * S),
                (796 * S, 196 * S, "A", font(F_BOLD, 22 * S), "mm", 0), (1238 * S, 196 * S, "B", font(F_BOLD, 22 * S), "mm", 0),
                (110 * S, 52 * S, "SKRATCHA  PADS", font(F_BOLD, 22 * S), "la", 3 * S)]
    pbg2 = V.flat_bg([((10, 10, 760, 618), ""), ((772, 10, 1270, 618), "")], [(782, 22, 1260, 112), (782, 566, 1260, 606)], pads_items)
    pd2 = ImageDraw.Draw(pbg2)
    pd2.ellipse([28, 24, 84, 80], fill=(190, 192, 196), outline=(90, 92, 96), width=2)
    pd2.ellipse([48, 44, 64, 60], fill=(150, 152, 156))
    pd2.rounded_rectangle([876, 206, 1156, 214], 4, fill=(4, 4, 4))
    deck.image("pbg", save(pbg2, "sk_bg_pads.png"), 0, 0, W, H); cond(deck, L2)
    prevP = pbg2.copy()
    deck.place(hidden(72, 72), P["Look Tap"], 20, 16, 72, 72, name="look2"); cond(deck, L2)
    padmap(deck, prevP, 26, 96, 174, 122, 182, 130, (L2,), big=True)
    deck.place(def_text("skRecNameP", 330, 40, 24, "ffffb52e"), P["Record"], 794, 24, 330, 40, name="recP"); cond(deck, L2)
    deck.place(def_text("skDesignP", 330, 20, 12, "ffb08a40"), P["Design"], 794, 62, 330, 20, name="designP"); cond(deck, L2)
    deck.place(def_text("skPitchP", 120, 40, 20, "ffffb52e", "right verticallyCentred"), P["Pitch"], 1130, 28, 120, 40, name="proP"); cond(deck, L2)
    deck.place(def_text("skPhaseP", 450, 24, 13, "ffd8dade"), P["Tip"], 794, 84, 450, 24, name="tipP"); cond(deck, L2)
    deck.place(def_slider("skXFader", cf_fn, 61, 340, 72, "Horizontal"), P["Crossfader"], 840, 174, 340, 72, name="xfaderP"); cond(deck, L2)
    prevP.alpha_composite(cf_frames[8], (840, 174))
    disp(deck, "skCutLed", cl_fn, 2, "A Cut LED", 779, 213, 34, 34, (L2,))
    disp(deck, "skCutLed", cl_fn, 2, "B Cut LED", 1221, 213, 34, 34, (L2,))
    knobs(deck, prevP, ["Strip Range", "Fader Curve", "Deck Volume", "Level"], 790, 262, 120, (L2, mode_is(0)))
    knobs(deck, None, ["Smooth", "Catch", "Cut Lag", "Crackle"], 790, 262, 120, (L2, mode_is(1)))
    deck.image("advframeP", save(adv_frame(476, 128), "sk_advframe_p.png"), 782, 252, 476, 128); cond(deck, L2, mode_is(1))
    segments(deck, prevP, "Cut Mode", ["CUT ZU", "CUT AUF"], 790, 392, 112, 44, gap=6, conds=(L2,))
    toggle(deck, prevP, "Mode", "advanced", "ADVANCED", 1030, 392, 220, 44, "dark", (L2,))
    segments(deck, prevP, "Speed", ["33", "45"], 790, 448, 112, 44, gap=6, conds=(L2,))
    layout_button(deck, prevP, 1030, 444, 220, (L2,))
    disp(deck, "skStripLed", led_fn, 33, "Strip LED", 790, 512, 170, 28, (L2,))
    disp(deck, "skCurveP", cv_fn, 21, "Fader Curve", 1000, 508, 112, 36, (L2,))
    deck.place(def_text("skTipP", 470, 36, 15, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 786, 568, 470, 36, name="tip2"); cond(deck, L2)
    pp_ = ImageDraw.Draw(prevP)
    pp_.text((806, 44), "A 1  AHH", font=font(F_TIT, 24), fill=AMBER, anchor="lm"); pp_.text((1248, 48), "+0.00%", font=font(F_TIT, 20), fill=AMBER, anchor="rm")
    pp_.text((806, 72), "1978 DIRECT DRIVE", font=font(F_TIT, 12), fill=(176, 138, 64), anchor="lm")
    prevP.convert("RGB").save(os.path.join(PREV, "preview_pads.png"))

    # ================= BROWSER =================
    def br_items(S):
        f13 = font(F_SEMI, 13 * S)
        return [(1088 * S, 300 * S, "LADEN IN SLOT (TIPPEN)", f13, "mm", S),
                (240 * S, 600 * S, "WISCHEN = BLAETTERN · 2x TIPPEN / > = OEFFNEN", font(F_MED, 12 * S), "mm", 0),
                (680 * S, 600 * S, "WISCHEN = BLAETTERN · 2x TIPPEN / + = LADEN", font(F_MED, 12 * S), "mm", 0),
                (1088 * S, 492 * S, "WISCH-TEMPO", font(F_SEMI, 12 * S), "mm", S)]
    br_bg = V.flat_bg([((14, 52, 466, 614), ""), ((476, 52, 900, 614), ""), ((912, 52, 1266, 614), "")],
                      [(14, 8, 1266, 46), (26, 64, 400, 524), (488, 64, 834, 524), (926, 560, 1252, 594)], br_items)
    brow = Tab("BROWSER", save(br_bg, "sk_bg_browser.png"))
    bpv = br_bg.copy()
    brow.place(def_text("skPath", 960, 38, 18, "ffffb52e"), P["Path"], 30, 8, 960, 38, name="path")
    on, off, on_i, off_i = key("back", 124, 34, "ZURUECK", False, "dark")
    brow.place(def_toggle("skTg_back", off, off, 124, 34), P["Folder Back"], 1136, 10, 124, 34, name="back")
    bpv.alpha_composite(off_i, (1136, 10))
    row_on, row_off = save(row_img(370, 60, True), "sk_row_on.png"), save(row_img(370, 60, False), "sk_row_off.png")
    row_on2, row_off2 = save(row_img(342, 60, True), "sk_row2_on.png"), save(row_img(342, 60, False), "sk_row2_off.png")
    # swipe surfaces: transparent film strips the size of the touch area (like the working scroll bar)
    row_strip = [save(Image.new("RGBA", (370 - 66, 120), (0, 0, 0, 0)), "sk_swipe0_f2.png"),
                 save(Image.new("RGBA", (342 - 66, 120), (0, 0, 0, 0)), "sk_swipe1_f2.png")]
    go_img = [go_key(60, 56, "open", False), go_key(60, 56, "load", False)]
    go_on = [save(go_key(60, 56, "open", True), "sk_go_open_on.png"), save(go_key(60, 56, "load", True), "sk_go_load_on.png")]
    go_off = [save(go_img[0], "sk_go_open_off.png"), save(go_img[1], "sk_go_load_off.png")]
    for li, (x0, w_, pick, rows_p, sel_p, step_p, pos_p, dbl, ron, roff) in enumerate([
            (30, 370, "Folder Pick", "Folder Row %d", "Folder Sel Row", "Folder Step", "Folder Pos", "Folder Open", row_on, row_off),
            (492, 342, "File Pick", "File Row %d", "File Sel Row", "File Step", "File Pos", "File Load", row_on2, row_off2)]):
        bar_s, bar_f = sel_bar_strip(w_ + 4, 60, 64)
        disp(brow, "skSelBar%d" % li, save(bar_s, "sk_selbar%d_f8.png" % li), 8, sel_p, x0 - 2, 68, w_ + 4, 6 * 64 + 60)
        for r in range(7):
            y = 68 + r * 64
            tap_p = P[("Folder Tap %d" if li == 0 else "File Tap %d") % (r + 1)]
            sw = w_ - 66
            brow.image("rowbg%d%d" % (li, r), roff, x0, y, w_, 60)
            brow.place(def_text("skRowTxt%d" % li, sw - 12, 60, 19, "ffe8e9ec"), P[rows_p % (r + 1)], x0 + 10, y, sw - 12, 60, name="rt%d%d" % (li, r))
            brow.place(swipe_row("skSwipe%d" % li, sw, 60, row_strip[li], 2), P["Folder Scroll" if li == 0 else "File Scroll"], x0, y, sw, 60,
                       extra_map=[{"key": "Tap", "value": "Parameter %d" % tap_p}], name="sw%d%d" % (li, r))
            # the arrow at the end of the row: one tap = open the folder / load the file
            brow.place(def_toggle("skRowGo%d" % li, go_off[li], go_off[li], 60, 56), tap_p, x0 + w_ - 62, y + 2, 60, 56, name="go%d%d" % (li, r))
            bpv.alpha_composite(go_img[li], (x0 + w_ - 62, y + 2))
        # scroll bar: slide to move through the list
        sb_s, sb_f = scrollbar_strip(48, 456)
        brow.place(def_slider("skScroll%d" % li, save(sb_s, "sk_scroll%d_f31.png" % li), 31, 48, 456, "Vertical"), P[pos_p], x0 + w_ + 6 if li == 0 else 840, 66, 48, 456, name="sc%d" % li)
        bpv.alpha_composite(sb_f[30], (x0 + w_ + 6 if li == 0 else 840, 66))
        for k, kind in enumerate(["up", "down", "pgup", "pgdn"]):
            on = save(arrow_key(80, 46, kind, True), "sk_arrow_%s_on.png" % kind); off = save(arrow_key(80, 46, kind, False), "sk_arrow_%s_off.png" % kind)
            xk = (26 if li == 0 else 488) + k * 88
            brow.place(def_segment("skArrow%d_%s" % (li, kind), on, off, 80, 46, k + 1, 5), P[step_p], xk, 532, 80, 46, name="ar%d%s" % (li, kind))
            bpv.alpha_composite(arrow_key(80, 46, kind, False), (xk, 532))
    bar0 = sel_bar_strip(374, 60, 64)[1][1]; bpv.alpha_composite(bar0, (28, 68)); bpv.alpha_composite(sel_bar_strip(346, 60, 64)[1][1], (490, 68))
    bd_ = ImageDraw.Draw(bpv)
    bd_.text((40, 27), "ALLE LAUFWERKE", font=font(F_TIT, 18), fill=AMBER, anchor="lm")
    for r, t in enumerate(["> SKRATCHA SAMPLES", "MY SAMPLES (PLUGIN)", "LAUFWERK MPC-SSD", "LAUFWERK USB STICK", "INTERNE SSD (NVME)", "MPC CONTENT", "SYSTEM - ALLES (/)"]):
        bd_.text((42, 68 + r * 64 + 30), t, font=font(F_TIT, 19), fill=(232, 233, 236), anchor="lm")
    for r, t in enumerate(["> FDR 1941 A", "FDR 1941 B", "FDR 1941 C", "FDR 1941 D", "FDR 1941 E", "FDR 1941 F", "ARMSTRONG 1969 A"]):
        bd_.text((504, 68 + r * 64 + 30), t, font=font(F_TIT, 19), fill=(232, 233, 236), anchor="lm")
    segments(brow, bpv, "Deck", ["DECK A", "DECK B"], 932, 112, 154, 48, gap=8)
    segments(brow, bpv, "Swipe Speed", ["LANGSAM", "NORMAL", "SCHNELL"], 932, 504, 100, 40, gap=8, first_on=1)
    on, off, on_i, off_i = key("oeffnen", 124, 34, "OEFFNEN", False, "dark")
    brow.place(def_toggle("skTg_open", off, off, 124, 34), P["Folder Open"], 1006, 10, 124, 34, name="open"); bpv.alpha_composite(off_i, (1006, 10))
    on, off, on_i, off_i = key("laden", 316, 44, "LADEN IN AKTUELLEN SLOT", False, "dark")
    brow.place(def_toggle("skTg_load", off, off, 316, 44), P["File Load"], 932, 62, 316, 44, name="load"); bpv.alpha_composite(off_i, (932, 62))
    toggle(brow, bpv, "Preview", "preview", "VORHOEREN", 932, 172, 154, 48)
    toggle(brow, bpv, "Auto Preview", "autoprev", "AUTO-HOEREN", 1094, 172, 154, 48, on_prev=True)
    toggle(brow, bpv, "Rescan", "rescan", "NEU LESEN", 932, 230, 154, 40)
    toggle(brow, bpv, "Sub Folders", "subdirs", "UNTERORDNER", 1094, 230, 154, 40, on_prev=True)
    for s in range(8):
        c, r = s % 4, (0 if s >= 4 else 1)
        x, y = 928 + c * 82, 314 + r * 84
        on = func_pad(78, 78, s + 1, "", True); off = func_pad(78, 78, s + 1, "", False)
        brow.place(def_segment("skLoad%d" % s, save(on, "sk_load%d_on.png" % s), save(off, "sk_load%d_off.png" % s), 78, 78, s + 1, 9), P["Load To Slot"], x, y, 78, 78, name="ld%d" % s)
        brow.place(def_text("skLoadName", 74, 30, 11, "ffe6e7ea", "horizontallyCentred verticallyCentred"), P["A Slot %d Name" % (s + 1)], x + 2, y + 34, 74, 30, name="ldn%d" % s)
        bpv.alpha_composite(off, (x, y))
    brow.place(def_text("skBrInfo", 316, 34, 14, "ffd8dade", "horizontallyCentred verticallyCentred"), P["Browser Info"], 930, 560, 316, 34, name="info")
    bd_.text((1088, 577), "DATEI 1/14  ORDNER 1/7", font=font(F_TIT, 14), fill=(216, 218, 222), anchor="mm")
    bpv.convert("RGB").save(os.path.join(PREV, "preview_browser.png"))

    # ================= LIVE: resample + live scratch =================
    def lv_items(S):
        f12, f13 = font(F_SEMI, 12 * S), font(F_SEMI, 13 * S)
        return [(46 * S, 56 * S, "AUFNAHME IN DEN AKTUELLEN SLOT", f13, "la", S),
                (346 * S, 312 * S, "ODER DIE LETZTEN SEKUNDEN HOLEN (GRAB)", f12, "mm", S),
                (686 * S, 56 * S, "LIVE SCRATCH: DIE SPUR LIEGT AUF DEM TELLER", f13, "la", S),
                (686 * S, 300 * S, "QUELLE (KANAL IM SKRATCHA FEED)", f12, "la", S),
                (686 * S, 380 * S, "NACH DEM LOSLASSEN", f12, "la", S),
                (40 * S, 520 * S, "SO GEHT'S:  1. SKRATCHA FEED ALS INSERT AUF EINE SPUR, DEN MASTER ODER DEN EINGANG SETZEN", font(F_MED, 13 * S), "la", 0),
                (40 * S, 546 * S, "2. GLEICHEN KANAL WAEHLEN (FEED 1-4)   3. REC / GRAB NIMMT IN DEN AKTUELLEN SLOT DES AKTIVEN DECKS AUF", font(F_MED, 13 * S), "la", 0),
                (40 * S, 572 * S, "4. LIVE: DER STRIP SCRATCHT DIE SPUR SELBST, LOSLASSEN = SOFORT ZURUECK IM BEAT", font(F_MED, 13 * S), "la", 0),
                (40 * S, 598 * S, "AUFNAHMEN LANDEN IN  MY SAMPLES / SKRATCHA REC  (IM PLUGIN-ORDNER)", font(F_MED, 13 * S), "la", 0)]
    lv_bg = V.flat_bg([((14, 14, 626, 500), ""), ((640, 14, 1266, 500), ""), ((14, 506, 1266, 614), "")],
                      [(40, 236, 600, 280), (680, 236, 1240, 280), (680, 440, 1240, 484)], lv_items)
    livet = Tab("LIVE", save(lv_bg, "sk_bg_live.png"))
    lvpv = lv_bg.copy()
    # REC: big round key + red ring that lights while recording
    rec_off = rec_key(190, False); rec_on = rec_key(190, True)
    rec_off_fn, rec_on_fn = save(rec_off, "sk_rec_off.png"), save(rec_on, "sk_rec_on.png")
    livet.place(def_toggle("skRecKey", rec_off_fn, rec_off_fn, 190, 190), P["Rec Tap"], 40, 74, 190, 190, name="rec")
    disp(livet, "skRecLed", save(strip_of([Image.new("RGBA", (190, 190), (0, 0, 0, 0)), rec_ring(190)]), "sk_recled_f2.png"), 2, "Rec LED", 40, 74, 190, 190)
    lvpv.alpha_composite(rec_off, (40, 74))
    livet.place(def_text("skRecInfo", 360, 44, 20, "ffffb52e"), P["Rec Info"], 250, 110, 360, 44, name="recinfo")
    livet.place(def_text("skRecTgt", 360, 36, 16, "ffd8dade"), P["Record"], 250, 160, 360, 36, name="rectgt")
    for k, lab in enumerate(["LETZTE 2 S", "LETZTE 4 S", "LETZTE 8 S"]):
        on, off, on_i, off_i = key("grab%d" % k, 176, 56, lab, False, "dark")
        livet.place(def_segment("skGrab%d" % k, on, off, 176, 56, k + 1, 4), P["Grab"], 40 + k * 188, 330, 176, 56, name="grab%d" % k)
        lvpv.alpha_composite(off_i, (40 + k * 188, 330))
    livet.place(def_text("skRecHint", 560, 44, 15, "ffd8dade", "horizontallyCentred verticallyCentred"), P["Feed Info"], 40, 236, 560, 44, name="fi1")
    # LIVE
    toggle(livet, lvpv, "Live", "live", "LIVE SCRATCH", 680, 80, 360, 120, "silver")
    disp(livet, "skLiveLed", save(strip_of([Image.new("RGBA", (180, 120), (0, 0, 0, 0)), live_glow(180, 120)]), "sk_liveled_f2.png"), 2, "Live LED", 1052, 80, 180, 120)
    lvpv.alpha_composite(live_glow(180, 120).point(lambda v: v // 4), (1052, 80))
    livet.place(def_text("skFeedInfo", 560, 44, 18, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Feed Info"], 680, 236, 560, 44, name="fi2")
    segments(livet, lvpv, "Feed Source", ["FEED 1", "FEED 2", "FEED 3", "FEED 4"], 680, 318, 134, 52, gap=8)
    segments(livet, lvpv, "Live Release", ["SOFORT ZURUECK", "BLEIBT HINTEN"], 680, 398, 276, 36, gap=8)
    mt_s, mt_f = meter_bar(540, 24)
    disp(livet, "skFeedMeter", save(mt_s, "sk_feedmeter_f16.png"), 16, "Feed Meter", 690, 450, 540, 24)
    lvpv.alpha_composite(mt_f[9], (690, 450))
    ld2 = ImageDraw.Draw(lvpv)
    ld2.text((262, 132), "REC: BEREIT", font=font(F_TIT, 20), fill=AMBER, anchor="lm")
    ld2.text((960, 258), "FEED 1: OK  48 KHZ  ERSETZT", font=font(F_TIT, 18), fill=AMBER, anchor="mm")
    lvpv.convert("RGB").save(os.path.join(PREV, "preview_live.png"))

    # ================= LERNEN =================
    def le_items(S):
        f13 = font(F_SEMI, 13 * S)
        return [(52 * S, 30 * S, "LEKTION", f13, "la", S),
                (386 * S, 316 * S, "LEHRER", font(F_SEMI, 11 * S), "la", S), (386 * S, 360 * S, "DU", font(F_SEMI, 11 * S), "la", S),
                (480 * S, 516 * S, "TON SOLL", font(F_SEMI, 10 * S), "mm", S), (548 * S, 516 * S, "TON IST", font(F_SEMI, 10 * S), "mm", S),
                (418 * S, 516 * S, "SCHRITT", font(F_SEMI, 10 * S), "mm", S), (886 * S, 444 * S, "SYNC", font(F_SEMI, 10 * S), "mm", S),
                (1100 * S, 186 * S, "SO GEHT'S AUF DER MPC", font(F_SEMI, 11 * S), "mm", S)]
    le_bg = V.flat_bg([((14, 14, 356, 614), ""), ((366, 14, 1266, 614), "")], [(376, 22, 1256, 76), (376, 82, 1256, 176), (376, 522, 1256, 562)], le_items)
    lern = Tab("LERNEN", save(le_bg, "sk_bg_lernen.png"))
    lpv = le_bg.copy()
    for i, nm in enumerate(LESSONS):
        on, off, on_i, off_i = key("lesson%d" % i, 300, 56, nm, True, "dark")
        lern.place(def_segment("skLesson%d" % i, on, off, 300, 56, i, len(LESSONS)), P["Lesson"], 34, 46 + i * 66, 300, 56, name="les%d" % i)
        lpv.alpha_composite(on_i if i == 0 else off_i, (34, 46 + i * 66))
    lern.place(def_text("skPhase", 860, 54, 28, "ffffffff", "horizontallyCentred verticallyCentred"), P["Phase"], 386, 22, 860, 54, name="phase")
    lern.place(def_text("skLT1", 850, 44, 22, "ffffb52e"), P["Lesson Text 1"], 392, 86, 850, 44, name="t1")
    lern.place(def_text("skLT2", 850, 44, 22, "ffffb52e"), P["Lesson Text 2"], 392, 130, 850, 44, name="t2")
    for i, les in enumerate(lessons):
        ls, lf = lane_strip(les, 560, 120)
        disp(lern, "skLane%d" % i, save(ls, "sk_lane%d_f32.png" % i), 32, "Lane", 386, 186, 560, 120, (lesson_is(i + 1),))
    ph_ = Image.new("RGBA", (560, 120), (0, 0, 0, 0)); pd_ = ImageDraw.Draw(ph_)
    pd_.rounded_rectangle([0, 0, 559, 119], 10, fill=(8, 8, 9, 255), outline=(44, 45, 48, 255), width=2)
    pd_.text((280, 36), "GRUNDLAGEN: 10 KURZE SCHRITTE", font=font(F_BOLD, 22), fill=(255, 255, 255), anchor="mm")
    pd_.text((280, 70), "OBEN STEHT, WAS DU TUN SOLLST", font=font(F_SEMI, 16), fill=(255, 181, 46), anchor="mm")
    pd_.text((280, 96), "RECHTS LEUCHTET, WO AUF DER MPC  >>", font=font(F_SEMI, 16), fill=(60, 235, 110), anchor="mm")
    lern.image("tourlane", save(ph_, "sk_tourlane.png"), 386, 186, 560, 120); cond(lern, lesson_is(0))
    hs_, hf_ = mpc_hint(290, 250)
    disp(lern, "skHint", save(hs_, "sk_mpchint_f17.png"), 17, "Hint", 956, 196, 290, 250)
    lpv.alpha_composite(hf_[0], (956, 196))
    gs, gf = U.teach_strip(510, 40, GREEN, "")
    ys, yf = U.teach_strip(510, 40, (255, 181, 46), "")
    disp(lern, "skGhost", save(gs, "sk_ghost_f33.png"), 33, "Ghost", 436, 312, 510, 40)
    disp(lern, "skYou", save(ys, "sk_you_f33.png"), 33, "Strip LED", 436, 356, 510, 40)
    bs, bf = U.beat_strip(560, 30)
    disp(lern, "skBeat", save(bs, "sk_beat_f9.png"), 9, "Beat", 386, 404, 560, 30)
    hs, hf = hit_strip(64)
    disp(lern, "skHit", save(hs, "sk_hit_f3.png"), 3, "Step Hit", 386, 442, 64, 64)
    fl, flf = U.led_strip(48, 48, GREEN)
    al, alf = U.led_strip(48, 48, (255, 181, 46))
    disp(lern, "skFadeT", save(fl, "sk_led_green_f2.png"), 2, "Fader Target", 456, 450, 48, 48)
    disp(lern, "skFadeA", save(al, "sk_led_amber_f2.png"), 2, "Cut LED", 524, 450, 48, 48)
    ss_, sf = U.stars_strip(210, 54)
    disp(lern, "skStars", save(ss_, "sk_stars_f4.png"), 4, "Stars", 600, 448, 210, 54)
    ms, mf = meter_strip(130, 26)
    disp(lern, "skSync", save(ms, "sk_sync_f11.png"), 11, "Sync", 822, 456, 130, 26)
    lern.place(def_text("skScore", 290, 40, 16, "ffd8dade", "horizontallyCentred verticallyCentred"), P["Score"], 956, 456, 290, 40, name="score")
    lern.place(def_text("skMsg", 860, 40, 22, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 386, 522, 860, 40, name="msg")
    toggle(lern, lpv, "Lesson Demo", "demo", "DEMO", 386, 568, 170, 44, "silver")
    toggle(lern, lpv, "Lesson Start", "lstart", "UEBEN", 566, 568, 170, 44, "silver")
    toggle(lern, lpv, "Click", "click", "KLICK", 746, 568, 120, 44, "dark", on_prev=True)
    lern.place(U.def_drag_text("skBpm", 170, 44, 20, "ffffb52e", "Vertical", "horizontallyCentred verticallyCentred"), P["Lesson BPM"], 876, 568, 170, 44, name="bpm")
    segments(lern, lpv, "Deck", ["A", "B"], 1056, 568, 92, 44, gap=6)
    ls0, lf0 = lane_strip(lessons[0], 560, 120)
    for img_, pos in [(ph_, (386, 186)), (gf[9], (436, 312)), (yf[12], (436, 356)), (bf[3], (386, 404)), (hf[1], (386, 442)), (flf[1], (456, 450)),
                      (alf[1], (524, 450)), (sf[2], (600, 448)), (mf[7], (822, 456))]:
        lpv.alpha_composite(img_, pos)
    ld_ = ImageDraw.Draw(lpv)
    ld_.text((816, 49), "GRUNDLAGEN - MACH MIT", font=font(F_TIT, 28), fill=(255, 255, 255), anchor="mm")
    ld_.text((400, 108), "1/10  DRUECK START (PAD 12)", font=font(F_TIT, 22), fill=(255, 181, 46), anchor="lm")
    ld_.text((400, 152), "DER TELLER DREHT SICH", font=font(F_TIT, 22), fill=(255, 181, 46), anchor="lm")
    ld_.text((1101, 476), "SCHRITT 1 VON 10", font=font(F_TIT, 16), fill=(216, 218, 222), anchor="mm")
    ld_.text((816, 542), "SCHAU AUFS MPC-BILD: ES LEUCHTET", font=font(F_TIT, 22), fill=(255, 181, 46), anchor="mm")
    ld_.text((961, 590), "80 BPM", font=font(F_TIT, 20), fill=(255, 181, 46), anchor="mm")
    lpv.convert("RGB").save(os.path.join(PREV, "preview_lernen.png"))
    mp = Image.new("RGBA", (290 * 4 + 30, 250), (40, 40, 44, 255))
    for j, k in enumerate([0, 3, 6, 13]):
        mp.alpha_composite(hf_[k], (j * 300, 0))
    mp.convert("RGB").save(os.path.join(PREV, "preview_mpchint.png"))

    # ================= SETUP: 4 rows x 4 knobs = the 16 Q-Links =================
    rows = [("DECK", ["Style", "Fire", "After Scratch", "Layout"]), ("TOUCH STRIP", ["Strip Range", "Smooth", "Catch", "Release"]),
            ("FADER", ["Fader Curve", "Cut Lag", "Cut Speed", "Cut Mode"]), ("MOTOR / KLANG", ["Start Time", "Brake Time", "Pitch Range", "Crackle"])]
    def su_items(S):
        it = []
        for r, (t, _) in enumerate(rows):
            it.append((40 * S, (26 + r * 146) * S, t, font(F_BOLD, 15 * S), "la", 2 * S))
            it.append((40 * S, (44 + r * 146) * S, "Q-LINK %d-%d" % (13 - 4 * r, 16 - 4 * r), font(F_SEMI, 10 * S), "la", S))
        it.append((880 * S, 30 * S, "PER TOUCH", font(F_BOLD, 15 * S), "la", 2 * S))
        it.append((880 * S, 588 * S, "JEDE REIHE = 4 Q-LINKS (OBEN = 13-16)", font(F_MED, 12 * S), "la", 0))
        return it
    su_bg = V.flat_bg([((20, 10, 850, 616), ""), ((862, 10, 1260, 616), "")], [], su_items)
    setup = Tab("SETUP", save(su_bg, "sk_bg_setup.png"))
    spv = su_bg.copy()
    for r, (t, names) in enumerate(rows):
        knobs(setup, spv, names, 190, 22 + r * 146, 165)
    for i, (pn, nm, lab, onp) in enumerate([("Slip", "slipS", "SLIP", False), ("Hamster", "hamsterS", "HAMSTER", False), ("Strip Dir", "sdir", "STRIP INVERT", False),
                                           ("Pad Base", "padbase", "PAD 1 = C#1", False), ("Deck On", "deckonS", "DECK ON", True), ("Reverse", "revS", "REVERSE", False),
                                           ("Click", "clickS", "LEHRER-KLICK", True), ("Auto Preview", "apS", "AUTO-HOEREN", True)]):
        toggle(setup, spv, pn, nm, lab, 880 + (i % 2) * 186, 60 + (i // 2) * 120, 176, 70, "dark", on_prev=onp)
    spv.convert("RGB").save(os.path.join(PREV, "preview_setup.png"))

    # ================= INFO =================
    info_bg = U.draw_info_bg()
    info = Tab("INFO", save(info_bg, "sk_bg_info.png"))
    info_bg.convert("RGB").save(os.path.join(PREV, "preview_info.png"))
    V.icons(info_bg)

    tabs = [deck, brow, livet, lern, setup, info]
    tui = {"pageData": {
        "version": 1,
        "componentDefinitions": {"version": 1, "importFiles": [
            "/usr/share/Akai/Content/Synths/Generic/Generic Knob Overlay.json",
            "/usr/share/Akai/Content/Synths/Generic/Generic Menu Overlay.json"],
            "localComponentDefinitions": DEFS + [t.root() for t in tabs]},
        "info": {"version": 1, "type": "CompleteDescription"},
        "tabs": [{"version": 3, "tabName": t.name, "fnKeyIndex": i, "fnKeySubIndex": 0, "qlinkBoundsData": ["0 0 0 0"],
                  "componentName": "%s|%s" % (t.name, t.name), "initialSize": "0 0 1280 628", "scale": 1.0} for i, t in enumerate(tabs)]}}
    json.dump(tui, open(os.path.join(OUT, "TUI.json"), "w"), indent=1)

    def qmap(rows_):
        m = {}
        order = [[13, 14, 15, 16], [9, 10, 11, 12], [5, 6, 7, 8], [1, 2, 3, 4]]
        for r, row in enumerate(order):
            for c, q in enumerate(row):
                name = rows_[r][c] if r < len(rows_) and c < len(rows_[r]) else None
                m["Q-Link %d" % q] = P[name] if name else -1
        return m
    deck_rows = [["Crossfader", "Fader Curve", "Strip Range", "Level"], ["Pitch", "Deck Volume", "A Volume", "B Volume"],
                 ["Smooth", "Catch", "Cut Lag", "Crackle"], ["Style", "Lesson BPM", "A Pitch", "B Pitch"]]
    br_rows = [["Folder", "File", "Crossfader", "Level"], ["Folder Pos", "File Pos", None, None]]
    le_rows = [["Crossfader", "Lesson BPM", "Strip Range", "Level"], ["Smooth", "Fader Curve", None, None]]
    su_rows = [names for _, names in rows]
    info_rows = [["Crossfader", "Level", "A Pitch", "B Pitch"]]
    live_rows = [["Crossfader", "Strip Range", "Deck Volume", "Level"], ["Feed Source", "Live Release", "A Pitch", "B Pitch"]]
    ql = {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
          "Screen Mode Q-Links": {"version": 4, "map": [
              {"Tab": i + 1, "SubTab": 1, "Bank Direction": "Row", "Q-Links": qmap(r_)} for i, r_ in enumerate([deck_rows, br_rows, live_rows, le_rows, su_rows, info_rows])]},
          "Program Mode Q-Links": qmap(deck_rows)}
    json.dump(ql, open(os.path.join(OUT, "Q-Links.json"), "w"), indent=1)

    total = 0
    for root, _, files in os.walk(OUT):
        for fn in files:
            if fn.endswith(".png"):
                im = Image.open(os.path.join(root, fn))
                total += os.path.getsize(os.path.join(root, fn))
                assert im.height <= 16384, fn
    print("skin written: %d definitions, %d tabs, %.1f MB PNG" % (len(DEFS), len(tabs), total / 1e6))


def scrollbar_strip(w, h, frames=31):
    out = []
    for k in range(frames):
        img = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([w * 0.35 * 2, 4, w * 0.65 * 2, h * 2 - 4], w * 0.3, fill=(30, 30, 33, 255), outline=(60, 62, 66, 255), width=2)
        v = 1 - k / (frames - 1)                # top = first entry
        ty = 8 + v * (h - 16 - 60)
        d.rounded_rectangle([6, ty * 2, w * 2 - 6, (ty + 60) * 2], 12, fill=(255, 181, 46, 230), outline=(255, 230, 160, 255), width=2)
        for j in range(3):
            yy = (ty + 22 + j * 8) * 2
            d.line([(w * 0.3 * 2, yy), (w * 0.7 * 2, yy)], fill=(80, 50, 10, 255), width=3)
        out.append(img.resize((w, h), Image.LANCZOS))
    return strip_of(out), out


if __name__ == "__main__":
    main()
