#!/usr/bin/env python3
"""SKRATCHA skin generator: draws every picture with Pillow and writes Plugin Skins/TUI.json + Q-Links.json.

    make_ui.py <params.json> <out skins dir> <preview dir> <jf_logo.png> <fonts dir>

The JSON components follow the patterns of skins that already run on MPC OS 3.10 (Crate Rippa on a Live III):
background images, film-strip knobs (also used as live displays), toggle and segment buttons, value labels.
"""
import json
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

PARAMS, OUT, PREV, LOGO, FONTS = sys.argv[1:6]
os.makedirs(OUT, exist_ok=True)
os.makedirs(PREV, exist_ok=True)
params = json.load(open(PARAMS))["params"]
P = {p["name"]: p["index"] for p in params}
SS = 2   # supersampling for drawing

W, H = 1280, 628


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), int(size))


F_BOLD = "Rajdhani-Bold.ttf"
F_SEMI = "Rajdhani-SemiBold.ttf"
F_MED = "Rajdhani-Medium.ttf"
F_TIT = "TitilliumWeb-Bold.ttf"

# palette
SILVER_HI = (214, 216, 218)
SILVER = (186, 189, 192)
SILVER_LO = (140, 143, 147)
BLACK = (14, 14, 15)
INK = (32, 33, 35)
RED = (255, 52, 34)
RED_DIM = (90, 22, 18)
GREEN = (60, 230, 110)
AMBER = (255, 181, 46)
GOLD = (212, 166, 74)

# platter geometry (tab coordinates)
CX, CY = 318, 314
R_PLATTER = 296
R_STROBE_IN, R_STROBE_OUT = 276, 292
R_MAT = 272
R_REC = 262
R_LABEL = 86
LABEL_TILE = 180
LABEL_FRAMES = 72
STROBE_FRAMES = 8
STROBE_DOTS = 90


def save(img, name):
    img.save(os.path.join(OUT, name), optimize=True)
    return name


def down(img, size=None):
    if size is None:
        size = (img.width // SS, img.height // SS)
    return img.resize(size, Image.LANCZOS)


def lin_grad(w, h, stops, vertical=True):
    """stops: list of (pos 0..1, (r,g,b[,a]))"""
    img = Image.new("RGBA", (w, h))
    px = img.load()
    n = h if vertical else w
    cols = []
    for i in range(n):
        t = i / max(1, n - 1)
        for k in range(len(stops) - 1):
            p0, c0 = stops[k]; p1, c1 = stops[k + 1]
            if p0 <= t <= p1:
                u = (t - p0) / max(1e-9, p1 - p0)
                c = tuple(int(c0[j] + (c1[j] - c0[j]) * u) for j in range(len(c0)))
                if len(c) == 3: c = c + (255,)
                cols.append(c); break
        else:
            c = stops[-1][1]; cols.append(c if len(c) == 4 else c + (255,))
    for i, c in enumerate(cols):
        if vertical:
            for x in range(w): px[x, i] = c
        else:
            for y in range(h): px[i, y] = c
    return img


def brushed(w, h, base, seed=7, strength=10):
    import random
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(img)
    for y in range(h):
        v = rnd.randint(-strength, strength)
        c = tuple(max(0, min(255, base[i] + v)) for i in range(3))
        d.line([(0, y), (w, y)], fill=c)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def text(d, xy, s, f, fill, anchor="la", spacing=0):
    if spacing:
        x, y = xy
        if anchor[0] == "m":
            total = sum(d.textlength(ch, font=f) + spacing for ch in s) - spacing
            x -= total / 2; anchor = "l" + anchor[1]
        for ch in s:
            d.text((x, y), ch, font=f, fill=fill, anchor=anchor)
            x += d.textlength(ch, font=f) + spacing
    else:
        d.text(xy, s, font=f, fill=fill, anchor=anchor)


def rounded(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def jf_logo(height, colour=GOLD, shine=True):
    lg = Image.open(LOGO).convert("RGBA")
    lg = lg.crop(lg.getbbox())
    w = int(lg.width * height / lg.height)
    lg = lg.resize((w, height), Image.LANCZOS)
    a = lg.split()[3]
    if shine:
        g = lin_grad(w, height, [(0, (250, 222, 150)), (0.45, colour), (0.55, (170, 120, 40)), (1, (236, 196, 110))])
    else:
        g = Image.new("RGBA", (w, height), colour + (255,))
    g.putalpha(a)
    return g


# ======================================================================================================
# pictures
# ======================================================================================================

def draw_deck_bg():
    S = SS
    img = brushed(W * S, H * S, (196, 198, 201), seed=3, strength=7).convert("RGBA")
    d = ImageDraw.Draw(img)
    # bevel around the plinth
    d.rectangle([0, 0, W * S - 1, H * S - 1], outline=(120, 122, 125), width=3 * S)
    d.line([(3 * S, 3 * S), (W * S - 4 * S, 3 * S)], fill=(236, 238, 240), width=2 * S)

    # platter well shadow
    sh = Image.new("L", (W * S, H * S), 0)
    ImageDraw.Draw(sh).ellipse([(CX - R_PLATTER - 6) * S, (CY - R_PLATTER + 4) * S, (CX + R_PLATTER + 10) * S, (CY + R_PLATTER + 16) * S], fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(14 * S))
    img = Image.composite(Image.new("RGBA", img.size, (40, 40, 42, 255)), img, sh)
    d = ImageDraw.Draw(img)

    # platter rim: polished aluminium ring with a bevel
    def ring(r_out, r_in, c_top, c_bot):
        box_o = [(CX - r_out) * S, (CY - r_out) * S, (CX + r_out) * S, (CY + r_out) * S]
        g = lin_grad(2 * r_out * S, 2 * r_out * S, [(0, c_top), (0.5, c_bot), (1, c_top)], vertical=False)
        g2 = lin_grad(2 * r_out * S, 2 * r_out * S, [(0, c_top), (1, c_bot)])
        g = Image.blend(g, g2, 0.5)
        m = Image.new("L", g.size, 0)
        md = ImageDraw.Draw(m)
        md.ellipse([0, 0, 2 * r_out * S - 1, 2 * r_out * S - 1], fill=255)
        o = (r_out - r_in) * S
        md.ellipse([o, o, 2 * r_out * S - 1 - o, 2 * r_out * S - 1 - o], fill=0)
        img.paste(g, (int(box_o[0]), int(box_o[1])), m)
    ring(R_PLATTER, R_STROBE_OUT, (238, 240, 242), (150, 153, 157))
    ring(R_STROBE_OUT, R_STROBE_IN, (120, 123, 127), (78, 80, 84))        # strobe band (dots drawn live)
    ring(R_STROBE_IN, R_MAT, (210, 212, 215), (140, 143, 147))
    d = ImageDraw.Draw(img)
    # rubber mat / slipmat
    d.ellipse([(CX - R_MAT) * S, (CY - R_MAT) * S, (CX + R_MAT) * S, (CY + R_MAT) * S], fill=(20, 20, 22))
    # vinyl with grooves
    vin = Image.new("RGBA", (2 * R_REC * S, 2 * R_REC * S), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vin)
    c = R_REC * S
    vd.ellipse([0, 0, 2 * c - 1, 2 * c - 1], fill=(12, 12, 13))
    import random
    rnd = random.Random(11)
    r = R_REC - 3
    while r > R_LABEL + 10:
        shade = 16 + rnd.randint(0, 9)
        if (R_REC - r) % 47 < 2:       # track gaps (smoother bands)
            shade = 30
        vd.ellipse([c - r * S, c - r * S, c + r * S, c + r * S], outline=(shade, shade, shade + 1), width=1)
        r -= 0.75
    # run-out and lead-in
    vd.ellipse([c - (R_LABEL + 10) * S, c - (R_LABEL + 10) * S, c + (R_LABEL + 10) * S, c + (R_LABEL + 10) * S], fill=(22, 22, 24))
    # static sheen: two soft light wedges (light from top-left), like light on a real record
    sheen = Image.new("L", vin.size, 0)
    sd = ImageDraw.Draw(sheen)
    sd.pieslice([0, 0, 2 * c - 1, 2 * c - 1], 200, 240, fill=95)
    sd.pieslice([0, 0, 2 * c - 1, 2 * c - 1], 20, 60, fill=55)
    sheen = sheen.filter(ImageFilter.GaussianBlur(22 * S))
    circ = Image.new("L", vin.size, 0); ImageDraw.Draw(circ).ellipse([0, 0, 2 * c - 1, 2 * c - 1], fill=255)
    sheen = ImageChops.multiply(sheen, circ)
    vin = Image.composite(Image.new("RGBA", vin.size, (200, 205, 215, 255)), vin, sheen.point(lambda v: v * 0.55))
    vin.putalpha(circ)
    img.alpha_composite(vin, ((CX - R_REC) * S, (CY - R_REC) * S))
    d = ImageDraw.Draw(img)

    # strobe lamp (pop-up light, bottom left) with its red glow toward the rim
    lx, ly = 44, 486
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([(lx - 60) * S, (ly - 60) * S, (lx + 60) * S, (ly + 60) * S], fill=(255, 40, 20, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(26 * S))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)
    d.ellipse([(lx - 20) * S, (ly - 20) * S, (lx + 20) * S, (ly + 20) * S], fill=(70, 72, 76), outline=(30, 30, 32), width=2 * S)
    d.ellipse([(lx - 12) * S, (ly - 12) * S, (lx + 12) * S, (ly + 12) * S], fill=(255, 70, 40))
    d.ellipse([(lx - 6) * S, (ly - 9) * S, (lx + 2) * S, (ly - 3) * S], fill=(255, 200, 180))

    # tone arm base plate (right of the platter)
    bx, by = 708, 120
    d.ellipse([(bx - 62) * S, (by - 62) * S, (bx + 62) * S, (by + 62) * S], fill=(166, 169, 173), outline=(110, 112, 116), width=2 * S)
    d.ellipse([(bx - 46) * S, (by - 46) * S, (bx + 46) * S, (by + 46) * S], fill=(40, 41, 44))
    # anti-skate and height dials (decor)
    for (dx, dy, rr) in [(774, 50, 18), (772, 226, 22)]:
        d.ellipse([(dx - rr) * S, (dy - rr) * S, (dx + rr) * S, (dy + rr) * S], fill=(28, 28, 30), outline=(150, 152, 156), width=2 * S)
        d.line([dx * S, (dy - rr + 4) * S, dx * S, (dy - 4) * S], fill=(220, 222, 226), width=2 * S)
    # arm rest
    d.rounded_rectangle([(758) * S, (330) * S, (780) * S, (380) * S], radius=6 * S, fill=(30, 30, 32))
    # cue lever slot
    d.rounded_rectangle([(744) * S, (420) * S, (790) * S, (470) * S], radius=6 * S, fill=(175, 178, 182), outline=(110, 112, 116), width=S)
    text(d, (767 * S, 482 * S), "CUE", font(F_SEMI, 12 * S), INK, "mm")

    # right panel: dark inset
    px0, py0, px1, py1 = 808, 14, 1176, 614
    rounded(d, [px0 * S, py0 * S, px1 * S, py1 * S], 14 * S, fill=(26, 27, 29), outline=(90, 92, 96), width=2 * S)
    # brand
    text(d, (px0 * S + 22 * S, 30 * S), "SKRATCHA", font(F_BOLD, 52 * S), (240, 240, 242), "la", spacing=3 * S)
    text(d, (px0 * S + 24 * S, 88 * S), "DIRECT DRIVE  ·  SCRATCH TURNTABLE", font(F_SEMI, 15 * S), (150, 152, 156), "la", spacing=1 * S)
    d.line([(px0 + 22) * S, 112 * S, (px1 - 22) * S, 112 * S], fill=(70, 72, 76), width=S)
    # record window (LCD)
    rounded(d, [(px0 + 22) * S, 126 * S, (px1 - 22) * S, 186 * S], 8 * S, fill=(10, 9, 6), outline=(70, 60, 30), width=S)
    text(d, ((px0 + 34) * S, 134 * S), "RECORD", font(F_SEMI, 12 * S), (150, 120, 50), "la", spacing=S)
    # pitch / status window
    rounded(d, [(px0 + 22) * S, 198 * S, (px1 - 22) * S, 244 * S], 8 * S, fill=(10, 9, 6), outline=(70, 60, 30), width=S)
    text(d, ((px0 + 34) * S, 208 * S), "PITCH", font(F_SEMI, 12 * S), (150, 120, 50), "la", spacing=S)
    # knob captions
    kx = [px0 + 30 + i * 84 for i in range(4)]
    for x, lab in zip(kx, ["SMOOTH", "RANGE", "CATCH", "LEVEL"]):
        text(d, ((x + 40) * S, 266 * S), lab, font(F_SEMI, 13 * S), (180, 182, 186), "mm", spacing=S)
    d.line([(px0 + 22) * S, 404 * S, (px1 - 22) * S, 404 * S], fill=(70, 72, 76), width=S)
    text(d, ((px0 + 22) * S, 412 * S), "FADER", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    text(d, ((px0 + 176) * S, 474 * S), "TOUCH STRIP", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    d.line([(px0 + 22) * S, 532 * S, (px1 - 22) * S, 532 * S], fill=(70, 72, 76), width=S)
    pads = "1 START/STOP   2 CUT   3 HOLD   4 CUE   5 SET CUE   6 REV   7 33/45   8 FADER   9–16 HOT CUES"
    # wrap pad legend into two lines
    text(d, ((px0 + 22) * S, 540 * S), "PADS  1 START/STOP · 2 CUT · 3 HOLD · 4 CUE", font(F_MED, 15 * S), (220, 222, 226), "la")
    text(d, ((px0 + 22) * S, 562 * S), "5 SET CUE · 6 REV · 7 33/45 · 8 FADER", font(F_MED, 15 * S), (220, 222, 226), "la")
    text(d, ((px0 + 22) * S, 584 * S), "9–16 HOT CUES  (SET CUE + PAD = STORE)", font(F_MED, 15 * S), (220, 222, 226), "la")

    # pitch fader slot and scale (far right)
    fx0, fy0, fx1, fy1 = 1190, 120, 1262, 520
    rounded(d, [fx0 * S, (fy0 - 6) * S, fx1 * S, (fy1 + 6) * S], 10 * S, fill=(170, 173, 177), outline=(110, 112, 116), width=S)
    d.rounded_rectangle([(fx0 + 31) * S, (fy0 + 10) * S, (fx0 + 41) * S, (fy1 - 10) * S], radius=4 * S, fill=(18, 18, 20))
    f12 = font(F_SEMI, 12 * S)
    for k, lab in [(8, "+8"), (4, "+4"), (0, "0"), (-4, "-4"), (-8, "-8")]:
        y = fy0 + 20 + (8 - k) / 16 * (fy1 - fy0 - 40)
        d.line([(fx0 + 6) * S, y * S, (fx0 + 20) * S, y * S], fill=INK, width=S)
        text(d, ((fx0 + 4) * S, (y - 9) * S), lab, f12, INK, "ls")
    text(d, ((fx0 + fx1) / 2 * S, (fy1 + 26) * S), "PITCH ADJ.", font(F_SEMI, 13 * S), INK, "mm")
    text(d, ((fx0 + fx1) / 2 * S, (fy0 - 22) * S), "%", font(F_SEMI, 14 * S), INK, "mm")
    # 33 / 45 caption, start/stop caption
    text(d, (76 * S, 524 * S), "", font(F_SEMI, 12 * S), INK, "mm")
    out = down(img)
    return out


def draw_tonearm():
    S = SS
    w, h = 340, 540
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = 470, 20                  # image origin in tab coordinates
    def T(x, y): return ((x - ox) * S, (y - oy) * S)
    pivot = (708, 120)
    # shadow first
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    pts = [(708, 120), (700, 300), (650, 420), (566, 486)]
    sd.line([T(x + 10, y + 12) for x, y in pts], fill=(0, 0, 0, 120), width=14 * S, joint="curve")
    sh = sh.filter(ImageFilter.GaussianBlur(7 * S))
    img.alpha_composite(sh)
    d = ImageDraw.Draw(img)
    # counterweight behind the pivot
    d.rounded_rectangle([T(686, 26)[0], T(686, 26)[1], T(730, 70)[0], T(730, 70)[1]], radius=10 * S, fill=(60, 62, 66), outline=(20, 20, 22), width=2 * S)
    for k in range(6):
        y = 30 + k * 7
        d.line([T(688, y), T(728, y)], fill=(95, 98, 103), width=S)
    d.line([T(708, 70), T(708, 120)], fill=(170, 173, 177), width=10 * S)
    # pivot
    d.ellipse([T(686, 98), T(730, 142)], fill=(205, 208, 212), outline=(70, 72, 76), width=2 * S)
    d.ellipse([T(698, 110), T(718, 130)], fill=(40, 41, 44))
    # S-shaped arm tube (polished): draw as dark outline + bright core
    curve = []
    for i in range(41):
        t = i / 40
        # cubic bezier pivot -> headshell
        p0, p1, p2, p3 = (708, 128), (712, 300), (660, 380), (566, 482)
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
        curve.append((x, y))
    d.line([T(x, y) for x, y in curve], fill=(90, 92, 96), width=12 * S, joint="curve")
    d.line([T(x, y) for x, y in curve], fill=(222, 224, 228), width=8 * S, joint="curve")
    d.line([T(x - 1.5, y - 1.5) for x, y in curve], fill=(255, 255, 255), width=2 * S, joint="curve")
    # headshell with finger lift
    hx, hy = 566, 482
    shell = [(hx - 30, hy - 10), (hx + 6, hy - 20), (hx + 14, hy + 4), (hx - 22, hy + 22)]
    d.polygon([T(x, y) for x, y in shell], fill=(30, 30, 32), outline=(150, 152, 156))
    d.line([T(hx - 26, hy - 4), T(hx - 52, hy + 4)], fill=(200, 202, 206), width=4 * S)    # finger lift
    d.rectangle([T(hx - 16, hy + 6), T(hx - 4, hy + 14)], fill=(210, 160, 60))              # cartridge
    return down(img), (ox, oy, w, h)


def draw_label_frames():
    """the rotating centre: record label with the gold JF logo (no lettering) and a white cue sticker"""
    S = 3
    size = LABEL_TILE * S
    c = size // 2
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    rL = R_LABEL * S
    d.ellipse([c - rL, c - rL, c + rL, c + rL], fill=(16, 16, 18))
    d.ellipse([c - rL + 4 * S, c - rL + 4 * S, c + rL - 4 * S, c + rL - 4 * S], outline=(160, 120, 50), width=2 * S)
    d.ellipse([c - rL + 9 * S, c - rL + 9 * S, c + rL - 9 * S, c + rL - 9 * S], outline=(70, 55, 25), width=S)
    lg = jf_logo(int(118 * S))
    base.alpha_composite(lg, (c - lg.width // 2 - 4 * S, c - lg.height // 2))
    # white sticker on the record just outside the label: the DJ's cue mark
    stick = [(c - 4 * S, c - rL - 2 * S), (c + 4 * S, c - rL - 2 * S), (c + 4 * S, c - rL + 22 * S), (c - 4 * S, c - rL + 22 * S)]
    d = ImageDraw.Draw(base)
    d.polygon(stick, fill=(245, 245, 240))
    # spindle (symmetric)
    sp = 9 * S
    frames = []
    shade = Image.new("L", (size, size), 0)
    sdr = ImageDraw.Draw(shade)
    sdr.pieslice([c - rL, c - rL, c + rL, c + rL], 200, 250, fill=70)
    shade = shade.filter(ImageFilter.GaussianBlur(14 * S))
    for k in range(LABEL_FRAMES):
        ang = k * 360.0 / (LABEL_FRAMES - 1)     # frame 0 and the last frame are the same picture (wrap)
        fr = base.rotate(-ang, resample=Image.BICUBIC, center=(c, c))
        fr = Image.composite(Image.new("RGBA", fr.size, (255, 255, 255, 255)), fr, shade.point(lambda v: v * 0.5 if True else 0))
        # keep alpha of the rotated label
        a = base.rotate(-ang, resample=Image.BICUBIC, center=(c, c)).split()[3]
        fr.putalpha(a)
        fd = ImageDraw.Draw(fr)
        fd.ellipse([c - sp, c - sp, c + sp, c + sp], fill=(205, 208, 212), outline=(90, 92, 96), width=S)
        fd.ellipse([c - sp // 2, c - sp // 2 - S, c, c - S], fill=(255, 255, 255))
        frames.append(fr.resize((LABEL_TILE, LABEL_TILE), Image.LANCZOS))
    strip = Image.new("RGBA", (LABEL_TILE, LABEL_TILE * LABEL_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * LABEL_TILE))
    return strip, frames


def draw_strobe_frames():
    S = SS
    size = 2 * R_STROBE_OUT
    frames = []
    for k in range(STROBE_FRAMES):
        img = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = R_STROBE_OUT * S
        phase = k / (STROBE_FRAMES - 1)      # one dot period across the strip
        rmid = (R_STROBE_IN + R_STROBE_OUT) / 2 * S
        for i in range(STROBE_DOTS):
            a = 2 * math.pi * (i + phase) / STROBE_DOTS - math.pi / 2
            x = c + rmid * math.cos(a); y = c + rmid * math.sin(a)
            r = 3.4 * S
            # dots lit red by the strobe lamp: brighter toward the lamp (bottom left)
            lamp = 0.55 + 0.45 * max(0.0, math.cos(a - math.radians(135)))
            col = (int(150 + 105 * lamp), int(40 + 60 * lamp), int(30 + 40 * lamp), 255)
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
        frames.append(down(img, (size, size)))
    strip = Image.new("RGBA", (size, size * STROBE_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * size))
    return strip, frames


def draw_knob_strip(size=80, frames=64, accent=RED):
    S = 3
    out = []
    for k in range(frames):
        v = k / (frames - 1)
        img = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = size * S / 2
        r_ring = c - 3 * S
        # arc track and value
        a0, a1 = 135, 405
        d.arc([c - r_ring, c - r_ring, c + r_ring, c + r_ring], a0, a1, fill=(60, 62, 66), width=4 * S)
        if v > 0.003:
            d.arc([c - r_ring, c - r_ring, c + r_ring, c + r_ring], a0, a0 + (a1 - a0) * v, fill=accent, width=4 * S)
        # knurled silver cap
        rc = c - 12 * S
        d.ellipse([c - rc - 2 * S, c - rc + 3 * S, c + rc + 2 * S, c + rc + 7 * S], fill=(0, 0, 0, 120))
        g = lin_grad(int(2 * rc), int(2 * rc), [(0, (236, 238, 241)), (0.5, (176, 179, 183)), (1, (120, 123, 127))])
        m = Image.new("L", g.size, 0); ImageDraw.Draw(m).ellipse([0, 0, g.width - 1, g.height - 1], fill=255)
        img.paste(g, (int(c - rc), int(c - rc)), m)
        d = ImageDraw.Draw(img)
        for i in range(48):
            a = 2 * math.pi * i / 48
            d.line([(c + (rc - 1) * math.cos(a), c + (rc - 1) * math.sin(a)), (c + (rc - 5 * S) * math.cos(a), c + (rc - 5 * S) * math.sin(a))], fill=(130, 133, 137), width=S)
        rt = rc - 7 * S
        g2 = lin_grad(int(2 * rt), int(2 * rt), [(0, (246, 247, 249)), (1, (160, 163, 167))])
        m2 = Image.new("L", g2.size, 0); ImageDraw.Draw(m2).ellipse([0, 0, g2.width - 1, g2.height - 1], fill=255)
        img.paste(g2, (int(c - rt), int(c - rt)), m2)
        d = ImageDraw.Draw(img)
        ang = math.radians(a0 + (a1 - a0) * v)
        d.line([(c + 6 * S * math.cos(ang), c + 6 * S * math.sin(ang)), (c + (rt - 2 * S) * math.cos(ang), c + (rt - 2 * S) * math.sin(ang))], fill=(20, 20, 22), width=3 * S)
        out.append(img.resize((size, size), Image.LANCZOS))
    strip = Image.new("RGBA", (size, size * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * size))
    return strip, out


def draw_pitch_fader(w=72, h=400, frames=41):
    S = 2
    out = []
    travel_top, travel_bot = 20, h - 20
    for k in range(frames):
        v = k / (frames - 1)              # 0 = -100 % (bottom ... ) -> Technics: minus at top? use + down like the real deck
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        y = travel_bot - v * (travel_bot - travel_top)      # drag up = faster, like the finger expects
        # zero LED (green) when centred
        if abs(v - 0.5) < 0.5 / (frames - 1):
            d.ellipse([(w - 16) * S, (h / 2 - 5) * S, (w - 6) * S, (h / 2 + 5) * S], fill=GREEN)
        else:
            d.ellipse([(w - 16) * S, (h / 2 - 5) * S, (w - 6) * S, (h / 2 + 5) * S], fill=(30, 70, 40))
        # cap: black ridged fader knob
        cx = 36
        d.rounded_rectangle([(cx - 26) * S, (y - 16 + 3) * S, (cx + 26) * S, (y + 16 + 3) * S], radius=5 * S, fill=(0, 0, 0, 110))
        d.rounded_rectangle([(cx - 26) * S, (y - 16) * S, (cx + 26) * S, (y + 16) * S], radius=5 * S, fill=(26, 26, 28), outline=(90, 92, 96), width=S)
        for i in range(-3, 4):
            d.line([(cx - 20) * S, (y + i * 4) * S, (cx + 20) * S, (y + i * 4) * S], fill=(60, 62, 66), width=S)
        d.line([(cx - 24) * S, y * S, (cx + 24) * S, y * S], fill=(240, 240, 240), width=2 * S)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_key(w, h, label, on, led=True, sub=None, style="silver"):
    S = 3
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * S, 5 * S, (w - 2) * S, (h - 1) * S], radius=6 * S, fill=(0, 0, 0, 110))
    if style == "silver":
        g = lin_grad((w - 4) * S, (h - 6) * S, [(0, (240, 242, 244)), (1, (160, 163, 167))] if not on else [(0, (210, 212, 215)), (1, (140, 143, 147))])
        tc = INK
    else:
        g = lin_grad((w - 4) * S, (h - 6) * S, [(0, (60, 62, 66)), (1, (28, 28, 30))] if not on else [(0, (48, 50, 54)), (1, (20, 20, 22))])
        tc = (230, 232, 236)
    m = Image.new("L", g.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, g.width - 1, g.height - 1], radius=6 * S, fill=255)
    img.paste(g, (2 * S, (2 if not on else 3) * S), m)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * S, (2 if not on else 3) * S, (w - 2) * S, (h - 4 + (0 if not on else 1)) * S], radius=6 * S, outline=(90, 92, 96), width=S)
    fs = 19 if len(label) <= 6 else 16
    ty = h / 2 + (0 if not on else 1) + (4 if led else 0)
    text(d, (w / 2 * S, ty * S), label, font(F_BOLD, fs * S), tc, "mm", spacing=S)
    if sub:
        text(d, (w / 2 * S, (h - 9) * S), sub, font(F_SEMI, 10 * S), tc, "mm")
    if led:
        lc = RED if on else RED_DIM
        d.rounded_rectangle([(w / 2 - 12) * S, 9 * S, (w / 2 + 12) * S, 14 * S], radius=2 * S, fill=lc)
        if on:
            gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(gl).rounded_rectangle([(w / 2 - 16) * S, 6 * S, (w / 2 + 16) * S, 17 * S], radius=4 * S, fill=(255, 60, 40, 140))
            img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(4 * S)))
    return img.resize((w, h), Image.LANCZOS)


def draw_led_strip(w=170, h=26, frames=33):
    out = []
    S = 2
    for k in range(frames):
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, (w - 1) * S, (h - 1) * S], radius=6 * S, fill=(10, 10, 11), outline=(60, 62, 66), width=S)
        n = frames - 1
        for i in range(n):
            x0 = (6 + i * (w - 12) / n) * S
            x1 = (6 + (i + 1) * (w - 12) / n - 1.5) * S
            col = (40, 30, 10)
            if k > 0:
                dist = abs(i - (k - 1))
                if dist == 0: col = AMBER
                elif dist == 1: col = (170, 110, 25)
                elif dist == 2: col = (90, 60, 15)
            d.rectangle([x0, 6 * S, x1, (h - 6) * S], fill=col)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_cut_led(w=150, h=40):
    out = []
    for k in range(2):
        S = 3
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, (w - 1) * S, (h - 1) * S], radius=8 * S, fill=(10, 10, 11), outline=(60, 62, 66), width=S)
        col = GREEN if k == 1 else RED
        lab = "OPEN" if k == 1 else "CUT"
        d.ellipse([12 * S, (h / 2 - 8) * S, 28 * S, (h / 2 + 8) * S], fill=col)
        gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).ellipse([6 * S, (h / 2 - 14) * S, 34 * S, (h / 2 + 14) * S], fill=col + (120,))
        img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(5 * S)))
        d = ImageDraw.Draw(img)
        text(d, (44 * S, h / 2 * S), lab, font(F_BOLD, 20 * S), col, "lm", spacing=2 * S)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * 2), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_hslider(w, h, frames, accent=AMBER):
    out = []
    S = 2
    for k in range(frames):
        v = k / (frames - 1)
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, (h / 2 - 6) * S, (w - 1) * S, (h / 2 + 6) * S], radius=5 * S, fill=(12, 12, 13), outline=(70, 72, 76), width=S)
        x = 14 + v * (w - 28)
        d.rounded_rectangle([4 * S, (h / 2 - 3) * S, x * S, (h / 2 + 3) * S], radius=3 * S, fill=accent)
        d.rounded_rectangle([(x - 12) * S, 3 * S, (x + 12) * S, (h - 3) * S], radius=5 * S, fill=(205, 208, 212), outline=(90, 92, 96), width=S)
        d.line([x * S, 7 * S, x * S, (h - 7) * S], fill=(30, 30, 32), width=2 * S)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_setup_bg():
    S = SS
    img = brushed(W * S, H * S, (196, 198, 201), seed=5, strength=7).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W * S - 1, H * S - 1], outline=(120, 122, 125), width=3 * S)
    panels = [(20, 16, 628, 300, "MOTOR"), (652, 16, 1260, 300, "TOUCH STRIP"),
              (20, 320, 628, 612, "FADER  ·  SOUND  ·  RECORDS"), (652, 320, 1260, 612, "SCRATCH  (STRIP IN Q-LINK MODE)")]
    for x0, y0, x1, y1, t in panels:
        rounded(d, [x0 * S, y0 * S, x1 * S, y1 * S], 14 * S, fill=(26, 27, 29), outline=(90, 92, 96), width=2 * S)
        text(d, ((x0 + 20) * S, (y0 + 14) * S), t, font(F_BOLD, 20 * S), (235, 236, 238), "la", spacing=2 * S)
    lab = lambda x, y, s: text(d, (x * S, y * S), s, font(F_SEMI, 13 * S), (180, 182, 186), "mm", spacing=S)
    # MOTOR captions
    lab(90, 70, "START TIME"); lab(210, 70, "BRAKE TIME")
    text(d, (300 * S, 66 * S), "PITCH RANGE", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    text(d, (300 * S, 176 * S), "RECORD END", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    # STRIP captions
    lab(722, 70, "RANGE"); lab(842, 70, "SMOOTH")
    text(d, (932 * S, 66 * S), "DIRECTION", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    text(d, (932 * S, 176 * S), "LET GO WHEN", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    text(d, (672 * S, 258 * S), "CENTER: strip springs back = hand off.  TIMEOUT: no move for 0.12 s = hand off.", font(F_MED, 14 * S), (150, 152, 156), "la")
    # FADER/SOUND captions
    text(d, (40 * S, 370 * S), "CUT CURVE", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    lab(110, 470, "CRACKLE"); lab(230, 470, "CATCH")
    text(d, (300 * S, 466 * S), "PAD BASE NOTE", font(F_SEMI, 13 * S), (180, 182, 186), "la", spacing=S)
    text(d, (40 * S, 586 * S), "Own WAVs: MPC Documents/SKRATCHA  or  the plugin folder /My Samples", font(F_MED, 14 * S), (150, 152, 156), "la")
    # SCRATCH panel text
    t2 = ["Touch strip mode PITCH BEND works best (14 bit).",
          "Q-LINK mode: touch the SCRATCH bar first, then use the strip.",
          "A Q-Link knob on SCRATCH scratches too.",
          "",
          "MPC: SHIFT + TOUCH STRIP opens the strip settings."]
    for i, s in enumerate(t2):
        text(d, (672 * S, (470 + i * 24) * S), s, font(F_MED, 16 * S), (210, 212, 216), "la")
    return down(img)


def draw_info_bg():
    S = SS
    img = Image.new("RGBA", (W * S, H * S), (16, 16, 17, 255))
    d = ImageDraw.Draw(img)
    # soft vignette ring like a record
    for r in range(330, 120, -6):
        sh = 20 + int(10 * ((r // 6) % 2))
        d.ellipse([(640 - r) * S, (300 - r) * S, (640 + r) * S, (300 + r) * S], outline=(sh, sh, sh + 1), width=S)
    d.ellipse([(640 - 160) * S, (300 - 160) * S, (640 + 160) * S, (300 + 160) * S], fill=(12, 12, 13))
    d.ellipse([(640 - 160) * S, (300 - 160) * S, (640 + 160) * S, (300 + 160) * S], outline=(160, 120, 50), width=3 * S)
    lg = jf_logo(250 * S)
    img.alpha_composite(lg, (int(640 * S - lg.width / 2 - 6 * S), int(300 * S - lg.height / 2)))
    text(d, (640 * S, 492 * S), "SKRATCHA", font(F_BOLD, 40 * S), (240, 240, 242), "mm", spacing=4 * S)
    text(d, (640 * S, 528 * S), "CREATOR: JJ DA PLUG", font(F_SEMI, 20 * S), GOLD, "mm", spacing=2 * S)
    text(d, (640 * S, 556 * S), "VERSION 1.0.0  ·  MPC PLUGIN SDK", font(F_MED, 15 * S), (140, 142, 146), "mm", spacing=S)
    steps = ["1  Touch strip: set it to PITCH BEND", "2  Touch the strip = hand on the record", "3  Move = scratch, lift = motor takes over",
             "4  Pad 1 START/STOP, pad 2 CUT", "5  Pad 9–16 hot cues"]
    for i, s in enumerate(steps):
        text(d, (40 * S, (60 + i * 30) * S), s, font(F_MED, 17 * S), (200, 202, 206), "la")
    tips = ["SMOOTH: lower = sharper, higher = softer", "RANGE: how far one stroke turns the record",
            "CATCH: how fast the motor grabs the record", "Record your scratches: the MPC records", "the strip as MIDI (pitch bend)."]
    for i, s in enumerate(tips):
        text(d, (1240 * S, (60 + i * 30) * S), s, font(F_MED, 17 * S), (200, 202, 206), "ra")
    return down(img)


# ======================================================================================================
# TUI.json builders (patterns proven on MPC OS 3.10)
# ======================================================================================================
DEFS = []
DEF_KEYS = set()


def bounds(x, y, w, h, focus="No", vis="Always"):
    return {"version": 2, "acceptsHWFocus": focus, "showWhenDataModelInvalid": "Show", "whenVisible": vis,
            "boundsType": "Absolute", "bounds": "%d %d %d %d" % (x, y, w, h), "additionalInvalidatingHandles": []}


def act(on, handler, handle="Data", extra=""):
    return {"version": 2, "onAction": on, "handler": handler, "handleName": handle, "additionalData": extra,
            "handle remapping": {"version": 1, "map": []}}


def comp(name, ctype, data, b):
    return {"version": 2, "componentData": {"version": 1, "name": name, "type": ctype, "data": data},
            "handle remapping": {"version": 1, "map": []}, "bounds": b}


def focus_comp(w, h):
    return comp("Focus", "Focus", {"version": 1, "backgroundColour": "00000000", "outlineColour": "00000000",
                                   "backgroundInset": 2.0, "outlineThickness": 0.0}, bounds(0, 0, w, h, vis="WhenFocussed"))


def define(key, actions, comps, ignore_mouse=False):
    if key in DEF_KEYS:
        return key
    DEF_KEYS.add(key)
    DEFS.append({"key": key, "value": {
        "version": 4, "actions": actions,
        "backgroundData": {"version": 1, "focussed": {"version": 1, "colour": "0", "image": ""}, "unfocussed": {"version": 1, "colour": "0", "image": ""}},
        "ignoreMousePresses": ignore_mouse, "disableCoarseDataWheel": False, "repeats": 1, "hideQLinkBounds": True,
        "componentsData": comps}})
    return key


def label_data(size, colour, style="Bold", just="horizontallyCentred verticallyCentred"):
    return {"version": 1, "textStyle": {"version": 1, "font": {"version": 1, "name": "Titillium Web", "style": style, "height": float(size)},
            "colour": colour, "justification": just, "case": "Original"}, "type": "Value", "handleName": "Data"}


def filmstrip(fn, frames, drag="Vertical"):
    return {"version": 5, "knobType": "FilmStrip", "filmStrip": fn, "numFrames": frames, "invert": False, "dragOrientation": drag, "handleName": "Data"}


# component kinds -------------------------------------------------------------------------------
def def_display(key, fn, frames, w, h):
    """a film strip that follows a parameter, not touchable (live displays)"""
    return define(key, [], [comp("Meter", "Knob", filmstrip(fn, frames), bounds(0, 0, w, h))], ignore_mouse=True)


def def_knob(key, fn, frames, size, label_h=22, val_colour="fff4f1ea"):
    acts = [act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "", "knob overlay"), act("Enter Pressed", "Show Overlay", "", "knob overlay")]
    comps = [focus_comp(size, size + label_h),
             comp("Knob", "Knob", filmstrip(fn, frames), bounds(0, 0, size, size)),
             comp("Value", "Label", label_data(15, val_colour, "SemiBold"), bounds(-10, size, size + 20, label_h))]
    return define(key, acts, comps)


def def_slider(key, fn, frames, w, h, drag, value_box=None, val_colour="ffffb52e", val_size=16):
    acts = [act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "", "knob overlay"), act("Enter Pressed", "Show Overlay", "", "knob overlay")]
    comps = [focus_comp(w, h), comp("Slider", "Knob", filmstrip(fn, frames, drag), bounds(0, 0, w, h))]
    if value_box:
        comps.append(comp("Value", "Label", label_data(val_size, val_colour, "Bold"), bounds(*value_box)))
    return define(key, acts, comps)


def def_toggle(key, on_fn, off_fn, w, h):
    acts = [act("Mouse Down", "Toggle Switch"), act("Enter Pressed", "Toggle Switch")]
    comps = [focus_comp(w, h), comp("Button", "Button", {"version": 2, "onImage": on_fn, "offImage": off_fn, "buttonId": 1,
                                                       "numButtonsInGroup": 1, "handleName": "Data", "gestureBehaviour": "Instant"}, bounds(0, 0, w, h))]
    return define(key, acts, comps)


def def_segment(key, on_fn, off_fn, w, h, idx, n):
    acts = [act("Mouse Down", "Q-Link")]
    comps = [comp("Button", "Button", {"version": 2, "onImage": on_fn, "offImage": off_fn, "buttonId": idx,
                                       "numButtonsInGroup": n, "handleName": "Data", "gestureBehaviour": "Instant"}, bounds(0, 0, w, h))]
    return define(key, acts, comps)


def def_readout(key, w, h, size, colour, just="left verticallyCentred", touch=False):
    acts = [act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "", "knob overlay"), act("Enter Pressed", "Show Overlay", "", "knob overlay")] if touch else []
    return define(key, acts, [comp("Value", "Label", label_data(size, colour, "Bold", just), bounds(0, 0, w, h))], ignore_mouse=not touch)


def def_jog(key, fn, size):
    """invisible absolute-angle knob over the platter: turning a finger on the screen turns the record"""
    acts = [act("Mouse Down", "Q-Link")]
    return define(key, acts, [comp("Jog", "Knob", filmstrip(fn, 2, "AbsoluteRotaryKnob"), bounds(0, 0, size, size))])


# placement into a tab -----------------------------------------------------------------------------
class Tab:
    def __init__(self, name, bg):
        self.name = name
        self.items = [comp("Background", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": bg}, bounds(0, 0, W, H))]
        self.preview = []    # (x, y, image) in drawing order

    def image(self, name, fn, x, y, w, h):
        self.items.append(comp(name, "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": fn}, bounds(x, y, w, h)))

    def place(self, key, param, x, y, w, h, extra_map=None, name=""):
        c = comp(name, key, {"version": 1, "handleName": "Data"}, bounds(x, y, w, h))
        m = [{"key": "Data", "value": "Parameter %d" % param}] if param is not None else []
        if extra_map:
            m += extra_map
        c["handle remapping"]["map"] = m
        self.items.append(c)

    def root(self):
        return {"key": "%s|%s" % (self.name, self.name), "value": {
            "version": 4, "actions": [],
            "backgroundData": {"version": 1, "focussed": {"version": 1, "colour": "ff0e0e0f", "image": ""}, "unfocussed": {"version": 1, "colour": "ff0e0e0f", "image": ""}},
            "ignoreMousePresses": False, "disableCoarseDataWheel": False, "repeats": 1, "hideQLinkBounds": True,
            "componentsData": self.items}}


# ======================================================================================================
# build
# ======================================================================================================
# ======================================================================================================
# PHOTO-REAL VERSIONS (override the flat drawings above)
# ======================================================================================================
import numpy as _np
import real_draw as RD


def _engrave(d, xy, s, f, anchor="la", light=(255, 255, 255, 150), ink=(38, 39, 42, 255), spacing=0):
    x, y = xy
    text(d, (x, y + 1.3 * SS), s, f, light, anchor, spacing)
    text(d, (x, y), s, f, ink, anchor, spacing)


def _print(d, xy, s, f, col=(232, 233, 236, 235), anchor="la", spacing=0):
    text(d, xy, s, f, col, anchor, spacing)


def _lcd(img, box, S):
    """dark glass window with a faint diagonal reflection"""
    x0, y0, x1, y1 = [int(v * S) for v in box]
    w, h = x1 - x0, y1 - y0
    xx, yy = RD.grid(w, h)
    v = 0.035 + 0.02 * (yy / h)
    refl = _np.exp(-(((xx / w) - (yy / h) * 0.6 - 0.18) / 0.10) ** 2) * 0.06
    rgb = _np.dstack([v + refl, v * 0.95 + refl, v * 0.75 + refl])
    m, dist = None, None
    r = 9 * S
    cx = _np.clip(xx, r, w - r); cy = _np.clip(yy, r, h - r)
    dist = _np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) - r
    m = 1 - RD.smoothstep(-1, 1, dist)
    inner = RD.smoothstep(-6 * S, 0, dist) * 0.5                        # inner shadow at the bezel
    rgb = rgb * (1 - inner[..., None])
    glass = RD.to_rgba(rgb, m)
    img.alpha_composite(glass, (x0, y0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=(70, 72, 76, 255), width=max(1, S))
    return d


def draw_deck_bg():
    S = SS
    Wp, Hp = W * S, H * S
    rgb = RD.brushed_plate(Wp, Hp, (0.735, 0.745, 0.76), seed=3, grain=0.03)
    alpha = _np.ones((Hp, Wp), _np.float32)
    xx, yy = RD.grid(Wp, Hp)
    # soft studio light: vignette toward the edges
    vig = 1 - 0.10 * ((xx / Wp - 0.35) ** 2 + (yy / Hp - 0.3) ** 2)
    rgb *= vig[..., None]

    # platter well shadow (the platter sits proud of the plinth)
    pm = RD.disc_mask(_np.sqrt((xx - CX * S) ** 2 + (yy - CY * S) ** 2), R_PLATTER * S)
    sh = RD.shadow_layer(pm, 12 * S, 0.60, 7 * S, 11 * S)
    rgb *= (1 - sh)[..., None]

    # platter + mat
    size = 2 * R_PLATTER * S
    prgb, pa = RD.platter(size, R_PLATTER * S, R_STROBE_OUT * S, R_STROBE_IN * S, R_MAT * S)
    ox, oy = (CX - R_PLATTER) * S, (CY - R_PLATTER) * S
    sub_rgb = rgb[oy:oy + size, ox:ox + size]
    sub_a = alpha[oy:oy + size, ox:ox + size]
    sub_rgb, sub_a = RD.comp(sub_rgb, sub_a, prgb, pa)
    # record shadow on the mat
    c = size / 2
    lx, ly = RD.grid(size, size, c, c)
    lr = _np.sqrt(lx * lx + ly * ly)
    rec_m = RD.disc_mask(lr, R_REC * S)
    rs = RD.shadow_layer(rec_m, 3 * S, 0.85, 2 * S, 4 * S) * RD.disc_mask(lr, R_MAT * S)
    sub_rgb = sub_rgb * (1 - rs)[..., None]
    # the record
    vsize = 2 * R_REC * S
    vrgb, va = RD.vinyl(vsize, R_REC, R_LABEL + 6, seed=11)
    vo = (size - vsize) // 2
    s2_rgb, s2_a = RD.comp(sub_rgb[vo:vo + vsize, vo:vo + vsize], sub_a[vo:vo + vsize, vo:vo + vsize], vrgb, va)
    sub_rgb[vo:vo + vsize, vo:vo + vsize] = s2_rgb
    rgb[oy:oy + size, ox:ox + size] = sub_rgb
    img = RD.to_rgba(rgb, alpha)
    d = ImageDraw.Draw(img)

    # strobe lamp: chrome pop-up housing with a red lens and its glow on the platter rim
    lx0, ly0 = 44, 486
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([(lx0 - 70) * S, (ly0 - 90) * S, (lx0 + 110) * S, (ly0 + 50) * S], fill=(255, 40, 20, 70))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30 * S)))
    hous = RD.metal_disc(48 * S, base=0.58, power=8)
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shd).ellipse([(lx0 - 22) * S, (ly0 - 18) * S, (lx0 + 30) * S, (ly0 + 30) * S], fill=(0, 0, 0, 150))
    img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(5 * S)))
    img.alpha_composite(hous, ((lx0 - 24) * S, (ly0 - 24) * S))
    d = ImageDraw.Draw(img)
    RD.led_lens(d, lx0 * S, ly0 * S, 13 * S, (255, 60, 34), True, img)
    d = ImageDraw.Draw(img)

    # tone-arm base: satin plate, gimbal well, anti-skate dial, height ring, arm rest, cue lever
    bx, by = 708, 120
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shd).ellipse([(bx - 66) * S, (by - 60) * S, (bx + 74) * S, (by + 76) * S], fill=(0, 0, 0, 140))
    img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(9 * S)))
    img.alpha_composite(RD.metal_disc(128 * S, base=0.66, power=6, rim_dark=0.18), ((bx - 64) * S, (by - 64) * S))
    img.alpha_composite(RD.metal_disc(100 * S, base=0.12, power=6, rim_dark=0.05), ((bx - 50) * S, (by - 50) * S))
    d = ImageDraw.Draw(img)
    # height-adjust ring with scale
    hx, hy = 770, 226
    img.alpha_composite(RD.metal_disc(56 * S, base=0.20, power=6, rim_dark=0.1), ((hx - 28) * S, (hy - 28) * S))
    d = ImageDraw.Draw(img)
    f9 = font(F_SEMI, 9 * S)
    for k in range(0, 7):
        a = math.radians(-120 + k * 40)
        d.line([((hx + 21 * math.cos(a)) * S, (hy + 21 * math.sin(a)) * S), ((hx + 26 * math.cos(a)) * S, (hy + 26 * math.sin(a)) * S)], fill=(230, 230, 230, 255), width=S)
    d.line([(hx * S, (hy - 16) * S), (hx * S, (hy - 4) * S)], fill=(255, 255, 255, 255), width=2 * S)
    # anti-skate dial
    ax_, ay_ = 776, 48
    img.alpha_composite(RD.metal_disc(40 * S, base=0.15, power=6, rim_dark=0.05), ((ax_ - 20) * S, (ay_ - 20) * S))
    d = ImageDraw.Draw(img)
    d.line([(ax_ * S, (ay_ - 15) * S), (ax_ * S, (ay_ - 6) * S)], fill=(255, 255, 255, 255), width=2 * S)
    # arm rest (black rubber cradle) and cue lever
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shd).rounded_rectangle([760 * S, 338 * S, 790 * S, 392 * S], radius=8 * S, fill=(0, 0, 0, 150))
    img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(4 * S)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([756 * S, 330 * S, 782 * S, 384 * S], radius=8 * S, fill=(22, 22, 24, 255))
    d.rounded_rectangle([762 * S, 336 * S, 776 * S, 352 * S], radius=5 * S, fill=(48, 48, 52, 255))
    img.alpha_composite(RD.key_cap(52, 56, "", False, os.path.join(FONTS, F_BOLD), led=False).resize((52 * S, 56 * S), Image.LANCZOS), (741 * S, 418 * S))
    d = ImageDraw.Draw(img)
    _engrave(d, (767 * S, 486 * S), "CUE", font(F_SEMI, 12 * S), "mm")

    # ---- right faceplate: black anodised aluminium with chamfer and screws
    px0, py0, px1, py1 = 808, 14, 1176, 614
    pw, ph = (px1 - px0) * S, (py1 - py0) * S
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shd).rounded_rectangle([(px0 + 3) * S, (py0 + 6) * S, (px1 + 5) * S, (py1 + 8) * S], radius=16 * S, fill=(0, 0, 0, 170))
    img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(8 * S)))
    an = RD.anodised(pw, ph)
    ax2, ay2 = RD.grid(pw, ph)
    r = 16 * S
    cxp = _np.clip(ax2, r, pw - r); cyp = _np.clip(ay2, r, ph - r)
    dist = _np.sqrt((ax2 - cxp) ** 2 + (ay2 - cyp) ** 2) - r
    m = 1 - RD.smoothstep(-1, 1, dist)
    cham = RD.smoothstep(-4 * S, 0, dist)
    an = an + (cham * _np.clip(1 - (ax2 / pw + ay2 / ph), 0, 1) * 0.25)[..., None] - (cham * _np.clip((ax2 / pw + ay2 / ph) - 1, 0, 1) * 0.1)[..., None]
    img.alpha_composite(RD.to_rgba(an, m), (px0 * S, py0 * S))
    d = ImageDraw.Draw(img)
    for sx, sy in [(px0 + 14, py0 + 14), (px1 - 14, py0 + 14), (px0 + 14, py1 - 14), (px1 - 14, py1 - 14)]:
        RD.screw(d, sx * S, sy * S, 5 * S)
    _print(d, ((px0 + 24) * S, 30 * S), "SKRATCHA", font(F_BOLD, 50 * S), (238, 238, 240, 255), spacing=3 * S)
    _print(d, ((px0 + 26) * S, 86 * S), "DIRECT DRIVE  ·  SCRATCH TURNTABLE", font(F_SEMI, 14 * S), (150, 152, 156, 255), spacing=S)
    d.line([(px0 + 22) * S, 110 * S, (px1 - 22) * S, 110 * S], fill=(60, 62, 66, 255), width=S)
    d = _lcd(img, (px0 + 22, 124, px1 - 22, 188), S)
    _print(d, ((px0 + 34) * S, 132 * S), "RECORD", font(F_SEMI, 11 * S), (150, 118, 48, 255), spacing=S)
    d = _lcd(img, (px0 + 22, 196, px1 - 22, 246), S)
    _print(d, ((px0 + 34) * S, 206 * S), "PITCH", font(F_SEMI, 11 * S), (150, 118, 48, 255), spacing=S)
    kx = [px0 + 30 + i * 84 for i in range(4)]
    for x, lab in zip(kx, ["SMOOTH", "RANGE", "CATCH", "LEVEL"]):
        _print(d, ((x + 40) * S, 266 * S), lab, font(F_SEMI, 13 * S), (200, 202, 206, 255), "mm", spacing=S)
    d.line([(px0 + 22) * S, 404 * S, (px1 - 22) * S, 404 * S], fill=(60, 62, 66, 255), width=S)
    _print(d, ((px0 + 22) * S, 412 * S), "FADER", font(F_SEMI, 13 * S), (200, 202, 206, 255), spacing=S)
    _print(d, ((px0 + 176) * S, 474 * S), "TOUCH STRIP", font(F_SEMI, 13 * S), (200, 202, 206, 255), spacing=S)
    d.line([(px0 + 22) * S, 532 * S, (px1 - 22) * S, 532 * S], fill=(60, 62, 66, 255), width=S)
    fm = font(F_MED, 15 * S)
    _print(d, ((px0 + 22) * S, 540 * S), "PADS  1 START/STOP · 2 CUT · 3 HOLD · 4 CUE", fm)
    _print(d, ((px0 + 22) * S, 562 * S), "5 SET CUE · 6 REV · 7 33/45 · 8 FADER", fm)
    _print(d, ((px0 + 22) * S, 584 * S), "9–16 HOT CUES  (SET CUE + PAD = STORE)", fm)

    # ---- pitch control plate (far right): satin aluminium strip with a deep slot and printed scale
    fx0, fy0, fx1, fy1 = 1188, 106, 1264, 536
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shd).rounded_rectangle([(fx0 + 2) * S, (fy0 + 5) * S, (fx1 + 4) * S, (fy1 + 7) * S], radius=10 * S, fill=(0, 0, 0, 140))
    img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(6 * S)))
    fw, fh = (fx1 - fx0) * S, (fy1 - fy0) * S
    plate = RD.brushed_plate(fw, fh, (0.70, 0.71, 0.725), seed=9, grain=0.025)
    gx, gy = RD.grid(fw, fh)
    rr_ = 10 * S
    cxp = _np.clip(gx, rr_, fw - rr_); cyp = _np.clip(gy, rr_, fh - rr_)
    dist = _np.sqrt((gx - cxp) ** 2 + (gy - cyp) ** 2) - rr_
    pm2 = 1 - RD.smoothstep(-1, 1, dist)
    cham = RD.smoothstep(-3 * S, 0, dist)
    plate += (cham * 0.15 * _np.clip(1 - gy / fh * 2, -1, 1))[..., None]
    # slot
    sx0, sx1 = 31 * S, 41 * S
    slot = ((gx > sx0) & (gx < sx1) & (gy > 26 * S) & (gy < fh - 26 * S)).astype(_np.float32)
    slot = RD.blur_np(slot, 0.8)
    depth = 0.04 + 0.05 * _np.clip((gx - sx0) / (sx1 - sx0), 0, 1)
    plate = plate * (1 - slot[..., None]) + (slot * depth)[..., None]
    img.alpha_composite(RD.to_rgba(plate, pm2), (fx0 * S, fy0 * S))
    d = ImageDraw.Draw(img)
    f12 = font(F_SEMI, 12 * S)
    for k, lab in [(8, "+8"), (4, "+4"), (0, "0"), (-4, "-4"), (-8, "-8")]:
        yk = 122 + 20 + (8 - k) / 16 * (520 - 120 - 40)
        d.line([(fx0 + 6) * S, yk * S, (fx0 + 20) * S, yk * S], fill=(40, 40, 44, 255), width=S)
        _engrave(d, ((fx0 + 4) * S, (yk - 9) * S), lab, f12, "ls")
    _engrave(d, ((fx0 + fx1) / 2 * S, (fy1 + 18) * S), "PITCH ADJ.", font(F_SEMI, 13 * S), "mm")
    _engrave(d, ((fx0 + fx1) / 2 * S, (fy0 - 12) * S), "%", font(F_SEMI, 14 * S), "mm")
    # captions beside the speed keys and start key (engraved into the plinth)
    return down(img)


def draw_tonearm():
    S = 3
    w, h = 340, 540
    ox, oy = 470, 20
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    def T(x, y): return ((x - ox) * S, (y - oy) * S)
    curve = RD.bezier((708, 128), (712, 300), (660, 380), (566, 482), 120)
    pts = [T(x, y) for x, y in curve]
    # cast shadow (light from the top left: shadow falls bottom right, softer further from the pivot)
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shd)
    sd.line([(x + 14 * S, y + 16 * S) for x, y in pts], fill=(0, 0, 0, 150), width=13 * S, joint="curve")
    hx, hy = 566, 482
    sd.polygon([T(x + 14, y + 16) for x, y in [(hx - 34, hy - 12), (hx + 8, hy - 24), (hx + 18, hy + 6), (hx - 24, hy + 26)]], fill=(0, 0, 0, 150))
    sd.ellipse([T(686 + 14, 26 + 16), T(730 + 14, 72 + 16)], fill=(0, 0, 0, 150))
    img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(7 * S)))
    d = ImageDraw.Draw(img)
    # counterweight: black knurled cylinder with a chrome end ring
    cw = Image.new("RGBA", ((46) * S, (50) * S), (0, 0, 0, 0))
    cx_, cy_ = RD.grid(cw.width, cw.height)
    u = (cx_ / cw.width) * 2 - 1
    v = 0.10 + 0.20 * _np.exp(-((u + 0.45) / 0.18) ** 2) + 0.05 * _np.cos(u * 1.4)
    kn = 0.5 + 0.5 * _np.sin(cy_ / S * 2 * _np.pi / 3.0)
    v = v * (0.75 + 0.25 * kn)
    rr = 7 * S
    ccx = _np.clip(cx_, rr, cw.width - rr); ccy = _np.clip(cy_, rr, cw.height - rr)
    dd = _np.sqrt((cx_ - ccx) ** 2 + (cy_ - ccy) ** 2) - rr
    cwa = 1 - RD.smoothstep(-1, 1, dd)
    cw = RD.to_rgba(_np.dstack([v, v, v * 1.03]), cwa)
    img.alpha_composite(cw, T(686, 24))
    d = ImageDraw.Draw(img)
    RD.draw_tube(img, [T(708, y) for y in _np.linspace(74, 112, 12)], 4.5 * S, S)
    # gimbal: chrome ring + dark bearing
    img.alpha_composite(RD.metal_disc(48 * S, base=0.70, power=12, rim_dark=0.30), T(684, 96))
    img.alpha_composite(RD.metal_disc(22 * S, base=0.10, power=6, rim_dark=0.02), T(697, 109))
    # the arm tube
    RD.draw_tube(img, pts, 6.2 * S, S)
    d = ImageDraw.Draw(img)
    # headshell (black, with chrome finger lift) and cartridge
    shell = [(hx - 32, hy - 10), (hx + 7, hy - 21), (hx + 15, hy + 4), (hx - 23, hy + 23)]
    d.polygon([T(x, y) for x, y in shell], fill=(26, 26, 28, 255), outline=(120, 122, 126, 255))
    d.line([T(hx - 30, hy - 8), T(hx + 5, hy - 18)], fill=(90, 92, 96, 255), width=S)
    RD.draw_tube(img, [T(hx - 28 - t * 26, hy - 4 + t * 8) for t in _np.linspace(0, 1, 12)], 2.2 * S, S)
    d = ImageDraw.Draw(img)
    cart = [(hx - 18, hy + 4), (hx - 2, hy - 1), (hx + 2, hy + 12), (hx - 14, hy + 17)]
    d.polygon([T(x, y) for x, y in cart], fill=(16, 16, 18, 255), outline=(70, 70, 74, 255))
    d.polygon([T(x, y) for x, y in [(hx - 15, hy + 7), (hx - 6, hy + 4), (hx - 4, hy + 9), (hx - 13, hy + 12)]], fill=(200, 140, 40, 255))
    return down(img, (w, h)), (ox, oy, w, h)


def draw_label_frames():
    S = 3
    size = LABEL_TILE * S
    c = size / 2.0
    rL = R_LABEL * S
    xx, yy = RD.grid(size, size, c, c)
    rr = _np.sqrt(xx * xx + yy * yy)
    th = _np.arctan2(yy, xx)
    # static lighting over the label (does not rotate): soft gradient + gloss wedge of the paper
    light = 1.0 + 0.18 * (-(xx + yy) / (2 * rL)) + 0.10 * RD.aniso(th, 6)
    # rotating layers, built once and rotated per frame
    lg = Image.open(LOGO).convert("RGBA")
    lg = lg.crop(lg.getbbox())
    lh = int(116 * S); lw = int(lg.width * lh / lg.height)
    lg = lg.resize((lw, lh), Image.LANCZOS)
    logo_mask = Image.new("L", (size, size), 0)
    logo_mask.paste(lg.split()[3], (int(c - lw / 2 - 4 * S), int(c - lh / 2)))
    sticker = Image.new("L", (size, size), 0)
    ImageDraw.Draw(sticker).rounded_rectangle([c - 4.5 * S, c - rL - 3 * S, c + 4.5 * S, c - rL + 22 * S], radius=1.5 * S, fill=255)
    ring = Image.new("L", (size, size), 0)
    rd = ImageDraw.Draw(ring)
    rd.ellipse([c - rL + 4 * S, c - rL + 4 * S, c + rL - 4 * S, c + rL - 4 * S], outline=255, width=int(2.2 * S))
    rd.ellipse([c - rL + 9 * S, c - rL + 9 * S, c + rL - 9 * S, c + rL - 9 * S], outline=150, width=S)
    grain = RD.noise(size, size, 77, 0.6)
    frames = []
    for k in range(LABEL_FRAMES):
        ang = k * 360.0 / (LABEL_FRAMES - 1)
        lm = _np.asarray(logo_mask.rotate(-ang, resample=Image.BICUBIC, center=(c, c))).astype(_np.float32) / 255
        sm = _np.asarray(sticker.rotate(-ang, resample=Image.BICUBIC, center=(c, c))).astype(_np.float32) / 255
        gm = _np.asarray(ring.rotate(-ang, resample=Image.BICUBIC, center=(c, c))).astype(_np.float32) / 255
        gr = _np.asarray(Image.fromarray((grain * 255).astype(_np.uint8)).rotate(-ang, resample=Image.BILINEAR, center=(c, c))).astype(_np.float32) / 255
        base = (0.045 + 0.02 * (gr - 0.5)) * light
        rgb = _np.dstack([base, base, base * 1.05])
        # gold foil: colour from a screen-fixed environment, so the sheen stays while the logo turns
        foil = 0.62 + 0.30 * _np.cos((xx * 0.8 + yy) / (rL * 0.55) + 0.6) + 0.25 * RD.aniso(th, 20)
        gold = _np.dstack([0.95 * foil + 0.05, 0.74 * foil, 0.36 * foil])
        emboss = _np.roll(_np.roll(lm, S, 0), S, 1) - lm          # shadow edge
        rgb = rgb * (1 - lm[..., None]) + gold * lm[..., None]
        rgb -= (_np.clip(emboss, 0, 1) * 0.25)[..., None]
        rgb = rgb * (1 - gm[..., None] * 0.9) + (gold * 0.85) * gm[..., None] * 0.9
        # sticker: white paper with a tiny shadow
        ssh = RD.blur_np(_np.roll(_np.roll(sm, S, 0), S, 1), 1.2 * S) * 0.6
        rgb *= (1 - ssh)[..., None]
        paper = 0.90 * light
        rgb = rgb * (1 - sm[..., None]) + _np.dstack([paper, paper, paper * 0.97]) * sm[..., None]
        alpha = _np.maximum(RD.disc_mask(rr, rL, 1.2), sm)
        img = RD.to_rgba(rgb, alpha)
        # spindle: chrome, symmetric
        sp = RD.metal_disc(int(20 * S), base=0.75, power=16, rim_dark=0.35)
        img.alpha_composite(sp, (int(c - 10 * S), int(c - 10 * S)))
        frames.append(img.resize((LABEL_TILE, LABEL_TILE), Image.LANCZOS))
    strip = Image.new("RGBA", (LABEL_TILE, LABEL_TILE * LABEL_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * LABEL_TILE))
    return strip, frames


def draw_strobe_frames():
    S = SS
    size = 2 * R_STROBE_OUT
    frames = []
    lamp_angle = math.atan2(486 - CY, 44 - CX)
    for k in range(STROBE_FRAMES):
        phase = k / (STROBE_FRAMES - 1)
        fr = RD.strobe_dots(size * S, R_STROBE_IN * S, R_STROBE_OUT * S, phase, STROBE_DOTS, lamp_angle, S)
        frames.append(down(fr, (size, size)))
    strip = Image.new("RGBA", (size, size * STROBE_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * size))
    return strip, frames


def draw_knob_strip(size=80, frames=64, accent=RED):
    out = [RD.rubber_knob(size, k / (frames - 1)) for k in range(frames)]
    strip = Image.new("RGBA", (size, size * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * size))
    return strip, out


def draw_pitch_fader(w=72, h=396, frames=41):
    S = 3
    out = []
    travel_top, travel_bot = 20, h - 20
    for k in range(frames):
        v = k / (frames - 1)
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        y = travel_bot - v * (travel_bot - travel_top)
        RD.led_lens(d, (w - 11) * S, h / 2 * S, 4.5 * S, (60, 235, 110), abs(v - 0.5) < 0.5 / (frames - 1), img)
        cx = 36
        # fader cap: shadow, ridged black plastic, chrome centre line
        shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shd).rounded_rectangle([(cx - 26) * S, (y - 14) * S, (cx + 30) * S, (y + 22) * S], radius=6 * S, fill=(0, 0, 0, 170))
        img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(4 * S)))
        cw_, ch_ = 54 * S, 34 * S
        gx, gy = RD.grid(cw_, ch_)
        t = gy / ch_
        ridges = 0.5 + 0.5 * _np.cos(gy / S * 2 * _np.pi / 3.4)
        val = 0.07 + 0.10 * (1 - t) * ridges + 0.10 * _np.exp(-((t - 0.25) / 0.12) ** 2)
        rr_ = 5 * S
        cxp = _np.clip(gx, rr_, cw_ - rr_); cyp = _np.clip(gy, rr_, ch_ - rr_)
        dist = _np.sqrt((gx - cxp) ** 2 + (gy - cyp) ** 2) - rr_
        m = 1 - RD.smoothstep(-1, 1, dist)
        val += RD.smoothstep(-2 * S, 0, dist) * 0.08 * (1 - t)
        img.alpha_composite(RD.to_rgba(_np.dstack([val, val, val * 1.04]), m), ((cx - 27) * S, int((y - 17) * S)))
        d = ImageDraw.Draw(img)
        d.line([(cx - 24) * S, y * S, (cx + 24) * S, y * S], fill=(235, 236, 238, 255), width=int(2.2 * S))
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_key(w, h, label, on, led=True, sub=None, style="silver"):
    return RD.key_cap(w, h, label, on, os.path.join(FONTS, F_BOLD), led=led, style=style)


def draw_led_strip(w=170, h=28, frames=33):
    out = []
    S = 3
    n = frames - 1
    for k in range(frames):
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, (w - 1) * S, (h - 1) * S], radius=6 * S, fill=(8, 8, 9, 255), outline=(64, 66, 70, 255), width=S)
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for i in range(n):
            x0 = (6 + i * (w - 12) / n) * S
            x1 = (6 + (i + 1) * (w - 12) / n - 1.6) * S
            lvl = 0.0
            if k > 0:
                dist = abs(i - (k - 1))
                lvl = {0: 1.0, 1: 0.55, 2: 0.25}.get(dist, 0.0)
            col = (int(40 + 215 * lvl), int(26 + 155 * lvl), int(8 + 38 * lvl))
            d.rectangle([x0, 7 * S, x1, (h - 7) * S], fill=col + (255,))
            d.rectangle([x0, 7 * S, x1, 10 * S], fill=(255, 255, 255, int(30 + 60 * lvl)))
            if lvl > 0.5:
                gd.rectangle([x0 - 3 * S, 2 * S, x1 + 3 * S, (h - 2) * S], fill=(255, 170, 40, 120))
        img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(3 * S)))
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_cut_led(w=150, h=40):
    out = []
    S = 3
    for k in range(2):
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, (w - 1) * S, (h - 1) * S], radius=8 * S, fill=(8, 8, 9, 255), outline=(64, 66, 70, 255), width=S)
        col = (60, 235, 110) if k == 1 else (255, 52, 34)
        d = RD.led_lens(d, 20 * S, h / 2 * S, 7 * S, col, True, img)
        text(d, (40 * S, h / 2 * S), "OPEN" if k == 1 else "CUT", font(F_BOLD, 20 * S), col + (255,), "lm", spacing=2 * S)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * 2), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_hslider(w, h, frames, accent=AMBER):
    out = []
    S = 3
    for k in range(frames):
        v = k / (frames - 1)
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, (h / 2 - 7) * S, (w - 1) * S, (h / 2 + 7) * S], radius=6 * S, fill=(6, 6, 7, 255), outline=(70, 72, 76, 255), width=S)
        x = 16 + v * (w - 32)
        d.rounded_rectangle([5 * S, (h / 2 - 2) * S, x * S, (h / 2 + 2) * S], radius=2 * S, fill=accent + (255,))
        shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shd).rounded_rectangle([(x - 12) * S, 6 * S, (x + 16) * S, (h - 1) * S], radius=6 * S, fill=(0, 0, 0, 160))
        img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(3 * S)))
        cap = RD.key_cap(28, h - 8, "", False, os.path.join(FONTS, F_BOLD), led=False).resize((28 * S, (h - 8) * S), Image.LANCZOS)
        img.alpha_composite(cap, (int((x - 14) * S), 2 * S))
        d = ImageDraw.Draw(img)
        d.line([x * S, 10 * S, x * S, (h - 14) * S], fill=(40, 40, 44, 255), width=2 * S)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def _faceplate(img, box, S, title):
    x0, y0, x1, y1 = box
    pw, ph = (x1 - x0) * S, (y1 - y0) * S
    shd = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shd).rounded_rectangle([(x0 + 3) * S, (y0 + 6) * S, (x1 + 5) * S, (y1 + 8) * S], radius=16 * S, fill=(0, 0, 0, 160))
    img.alpha_composite(shd.filter(ImageFilter.GaussianBlur(8 * S)))
    an = RD.anodised(pw, ph, seed=x0 + y0)
    ax2, ay2 = RD.grid(pw, ph)
    r = 16 * S
    cxp = _np.clip(ax2, r, pw - r); cyp = _np.clip(ay2, r, ph - r)
    dist = _np.sqrt((ax2 - cxp) ** 2 + (ay2 - cyp) ** 2) - r
    m = 1 - RD.smoothstep(-1, 1, dist)
    cham = RD.smoothstep(-4 * S, 0, dist)
    an = an + (cham * _np.clip(1 - (ax2 / pw + ay2 / ph), 0, 1) * 0.25)[..., None]
    img.alpha_composite(RD.to_rgba(an, m), (x0 * S, y0 * S))
    d = ImageDraw.Draw(img)
    for sx, sy in [(x0 + 13, y0 + 13), (x1 - 13, y0 + 13), (x0 + 13, y1 - 13), (x1 - 13, y1 - 13)]:
        RD.screw(d, sx * S, sy * S, 4.5 * S)
    _print(d, ((x0 + 30) * S, (y0 + 14) * S), title, font(F_BOLD, 20 * S), (236, 237, 240, 255), spacing=2 * S)
    return d


def draw_setup_bg():
    S = SS
    rgb = RD.brushed_plate(W * S, H * S, (0.735, 0.745, 0.76), seed=5, grain=0.03)
    img = RD.to_rgba(rgb)
    for box, t in [((20, 16, 628, 300), "MOTOR"), ((652, 16, 1260, 300), "TOUCH STRIP"),
                   ((20, 320, 628, 612), "FADER  ·  SOUND  ·  RECORDS"), ((652, 320, 1260, 612), "SCRATCH  (STRIP IN Q-LINK MODE)")]:
        d = _faceplate(img, box, S, t)
    d = ImageDraw.Draw(img)
    lab = lambda x, y, s: _print(d, (x * S, y * S), s, font(F_SEMI, 13 * S), (200, 202, 206, 255), "mm", spacing=S)
    lal = lambda x, y, s: _print(d, (x * S, y * S), s, font(F_SEMI, 13 * S), (200, 202, 206, 255), "la", spacing=S)
    lab(90, 70, "START TIME"); lab(210, 70, "BRAKE TIME")
    lal(300, 66, "PITCH RANGE"); lal(300, 176, "RECORD END")
    lab(722, 70, "RANGE"); lab(842, 70, "SMOOTH")
    lal(932, 66, "DIRECTION"); lal(932, 176, "LET GO WHEN")
    _print(d, (672 * S, 262 * S), "CENTER: strip springs back = hand off.  TIMEOUT: no move for 0.12 s = hand off.", font(F_MED, 14 * S), (150, 152, 156, 255))
    lal(40, 370, "CUT CURVE")
    lab(110, 470, "CRACKLE"); lab(230, 470, "CATCH")
    lal(300, 466, "PAD BASE NOTE")
    _print(d, (40 * S, 586 * S), "Own WAVs: MPC Documents/SKRATCHA  or  the plugin folder /My Samples", font(F_MED, 14 * S), (150, 152, 156, 255))
    for i, s in enumerate(["Touch strip mode PITCH BEND works best (14 bit).",
                           "Q-LINK mode: touch the SCRATCH bar first, then use the strip.",
                           "A Q-Link knob on SCRATCH scratches too.", "",
                           "MPC: SHIFT + TOUCH STRIP opens the strip settings."]):
        _print(d, (672 * S, (472 + i * 24) * S), s, font(F_MED, 16 * S), (214, 216, 220, 255))
    return down(img)


def draw_info_bg():
    S = SS
    img = RD.to_rgba(RD.anodised(W * S, H * S, base=(0.055, 0.056, 0.06), seed=8))
    # a real record in the middle with the gold JF label
    R = 250
    vsize = 2 * R * S
    vrgb, va = RD.vinyl(vsize, R, 100, seed=31)
    cx, cy = 640, 300
    xx, yy = RD.grid(W * S, H * S)
    rm = RD.disc_mask(_np.sqrt((xx - cx * S) ** 2 + (yy - cy * S) ** 2), R * S)
    sh = RD.shadow_layer(rm, 14 * S, 0.8, 8 * S, 12 * S)
    base = _np.asarray(img).astype(_np.float32) / 255
    base[..., :3] *= (1 - sh)[..., None]
    img = Image.fromarray((base * 255).astype(_np.uint8), "RGBA")
    img.alpha_composite(RD.to_rgba(vrgb, va), ((cx - R) * S, (cy - R) * S))
    # label (reuse the deck label artwork, larger and without the sticker)
    lab_r = 96
    lsize = 2 * lab_r * S
    lx, ly = RD.grid(lsize, lsize, lsize / 2, lsize / 2)
    lr = _np.sqrt(lx * lx + ly * ly)
    th = _np.arctan2(ly, lx)
    light = 1.0 + 0.18 * (-(lx + ly) / (2 * lab_r * S)) + 0.10 * RD.aniso(th, 6)
    b = 0.045 * light
    lab = RD.to_rgba(_np.dstack([b, b, b * 1.05]), RD.disc_mask(lr, lab_r * S, 1.2))
    d = ImageDraw.Draw(lab)
    d.ellipse([5 * S, 5 * S, lsize - 5 * S, lsize - 5 * S], outline=(196, 152, 68, 255), width=int(2.5 * S))
    lg = jf_logo(int(140 * S))
    lab.alpha_composite(lg, (int(lsize / 2 - lg.width / 2 - 4 * S), int(lsize / 2 - lg.height / 2)))
    img.alpha_composite(lab, ((cx - lab_r) * S, (cy - lab_r) * S))
    d = ImageDraw.Draw(img)
    text(d, (640 * S, 576 * S), "SKRATCHA  ·  CREATOR: JJ DA PLUG", font(F_BOLD, 24 * S), (240, 240, 242), "mm", spacing=3 * S)
    text(d, (640 * S, 606 * S), "VERSION 1.0.0  ·  MPC PLUGIN SDK", font(F_MED, 14 * S), (140, 142, 146), "mm", spacing=S)
    steps = ["1  Touch strip: set it to PITCH BEND", "2  Touch the strip = hand on the record", "3  Move = scratch, lift = motor takes over",
             "4  Pad 1 START/STOP, pad 2 CUT", "5  Pad 9–16 hot cues"]
    for i, s in enumerate(steps):
        text(d, (34 * S, (60 + i * 30) * S), s, font(F_MED, 17 * S), (205, 207, 211), "la")
    tips = ["SMOOTH: lower = sharper, higher = softer", "RANGE: how far one stroke turns the record",
            "CATCH: how fast the motor grabs the record", "Record your scratches: the MPC records", "the strip as MIDI (pitch bend)."]
    for i, s in enumerate(tips):
        text(d, (1246 * S, (60 + i * 30) * S), s, font(F_MED, 17 * S), (205, 207, 211), "ra")
    return down(img)



# ======================================================================================================
# PHYSICALLY BASED VERSIONS (override everything above): maps + studio lighting via pbr.py
# ======================================================================================================
import numpy as _np
import cv2 as _cv2
import pbr as PB


def _text_mask(w, h, items):
    """items: (x, y, text, font, anchor, spacing) in pixel coords of this map -> float mask"""
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for (x, y, s, f, anchor, sp) in items:
        text(d, (x, y), s, f, 255, anchor, sp)
    return _np.asarray(m).astype(_np.float32) / 255.0


def _maps(w, h, albedo=(0.5, 0.5, 0.5), H=0.0, rough=0.5, metal=0.0):
    A = _np.ones((h, w, 3), _np.float32) * _np.array(albedo, _np.float32)
    return A, _np.full((h, w), H, _np.float32), _np.full((h, w), rough, _np.float32), _np.full((h, w), metal, _np.float32)


def _put(A, Hm, Rm, Mm, mask, albedo=None, H=None, rough=None, metal=None, add_H=None):
    m = mask
    if albedo is not None:
        alb = _np.asarray(albedo, _np.float32)
        if alb.ndim == 1:
            alb = alb[None, None, :]
        A[:] = A * (1 - m[..., None]) + alb * m[..., None]
    if H is not None:
        Hm[:] = Hm * (1 - m) + H * m
    if add_H is not None:
        Hm[:] = Hm + add_H * m
    if rough is not None:
        Rm[:] = Rm * (1 - m) + rough * m
    if metal is not None:
        Mm[:] = Mm * (1 - m) + metal * m


SILVER = PB.srgb_to_lin([0.80, 0.81, 0.83])
SILVER_BRIGHT = PB.srgb_to_lin([0.93, 0.94, 0.95])
PAINT_WHITE = PB.srgb_to_lin([0.86, 0.87, 0.88])
INK_DARK = PB.srgb_to_lin([0.12, 0.12, 0.13])
ANOD = PB.srgb_to_lin([0.10, 0.10, 0.11])
AMBER_LIN = PB.srgb_to_lin([0.62, 0.45, 0.16])


def _glow(img, cx, cy, rad, colour, alpha=150):
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=colour + (alpha,))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(rad * 0.45)))


def draw_deck_bg():
    S = SS
    w, h = W * S, H * S
    A, Hm, Rm, Mm = _maps(w, h, SILVER, 0.0, 0.30, 1.0)
    x, y = PB.grid(w, h)
    # --- plinth: satin brushed aluminium with micro grain and a rounded front/edge
    Hm += PB.brushed(w, h, 1, length=400, strength=0.16) + PB.white(w, h, 2) * 0.015 + PB.fbm(w, h, 2, 4, 120.0) * 0.3
    edge = PB.rrect(x, y, 0, 0, w, h, 10 * S)
    Hm += PB.dome(edge, 0, 1) - 4 * S * (1 - PB.smoothstep(-6 * S, 0, edge)) * 0  # (flat; outline by AO)
    Rm += PB.fbm(w, h, 3, 3, 40.0) * 0.05

    # --- platter
    px, py = x - CX * S, y - CY * S
    r = _np.sqrt(px * px + py * py)
    th = _np.arctan2(py, px)
    lip = PB.ring(r, R_STROBE_OUT * S, R_PLATTER * S)
    band = PB.ring(r, R_STROBE_IN * S, R_STROBE_OUT * S)
    step = PB.ring(r, R_MAT * S, R_STROBE_IN * S)
    mat = PB.disc(r, R_MAT * S)
    rec = PB.disc(r, R_REC * S)
    lathe = PB.radial_value(r, 5, scale=0.7, amp=0.06 * S, smooth=2)
    outer_round = PB.dome(r - R_PLATTER * S, 5 * S, 5 * S)                 # rounded outer edge
    _put(A, Hm, Rm, Mm, lip, SILVER_BRIGHT, 14 * S, 0.10, 1.0)
    Hm[:] = Hm + lip * (lathe + (outer_round - 5 * S))
    _put(A, Hm, Rm, Mm, band, PB.srgb_to_lin([0.58, 0.59, 0.61]), None, 0.28, 1.0)
    Hm[:] = Hm * (1 - band) + band * (11 * S + (r - R_STROBE_IN * S) / ((R_STROBE_OUT - R_STROBE_IN) * S) * 3 * S + lathe * 0.5)
    _put(A, Hm, Rm, Mm, step, SILVER_BRIGHT, 13 * S, 0.14, 1.0)
    Hm[:] = Hm + step * lathe
    ridges = _np.sin(r * 2 * _np.pi / (3.2 * S)) * 0.5 * S
    _put(A, Hm, Rm, Mm, mat, PB.srgb_to_lin([0.035, 0.035, 0.038]), 9 * S, 0.80, 0.0)
    Hm[:] = Hm + mat * (ridges + PB.fbm(w, h, 7, 3, 8.0) * 0.25 * S)
    # --- the record: glossy vinyl, micro-grooves broken into tracks, bevelled edge, smooth run-out
    rr = r / S
    gaps = _np.sort(PB.rng(11).uniform(R_LABEL + 22, R_REC - 8, 6))
    gap = _np.zeros_like(r)
    for g in gaps:
        gap = _np.maximum(gap, _np.exp(-((rr - g) / 1.3) ** 2))
    runout = PB.ring(r, (R_LABEL + 2) * S, (R_LABEL + 14) * S, 1.5)
    groove_amp = (1 - gap) * (1 - runout) * 0.28 * S
    grooves = PB.radial_value(r, 13, scale=0.9, amp=1.0, smooth=1) * groove_amp * 0.25
    grooves += PB.radial_value(r, 17, scale=0.5, amp=0.25 * S, smooth=3) * (1 - runout)
    warp = PB.fbm(w, h, 19, 3, 300.0) * 1.2 * S                                 # a record is never perfectly flat
    rec_edge = PB.dome(r - R_REC * S, 2.0 * S, 3 * S)
    _put(A, Hm, Rm, Mm, rec, PB.srgb_to_lin([0.018, 0.018, 0.020]), None, 0.16, 0.0)
    Hm[:] = Hm * (1 - rec) + rec * (9 * S + rec_edge + grooves + warp)
    Rm[:] = Rm * (1 - rec) + rec * (0.16 + 0.10 * (1 - gap) * (1 - runout) - 0.08 * runout)
    # spiral lead-out groove in the run-out
    spiral = _np.abs(((rr - (R_LABEL + 8)) - (th / (2 * _np.pi)) * 3.0) % 3.0 - 1.5) < 0.22
    Hm[:] = Hm - (spiral & (runout > 0.5)) * 0.5 * S

    # --- strobe lamp housing (chrome dome) with a red lens
    lx, ly = 44 * S, 486 * S
    lr_ = _np.sqrt((x - lx) ** 2 + (y - ly) ** 2)
    housing = PB.disc(lr_, 24 * S)
    _put(A, Hm, Rm, Mm, housing, SILVER_BRIGHT, None, 0.06, 1.0)
    Hm[:] = Hm * (1 - housing) + housing * PB.dome(lr_ - 24 * S, 9 * S, 10 * S)
    lens = PB.disc(lr_, 13 * S)
    _put(A, Hm, Rm, Mm, lens, PB.srgb_to_lin([0.55, 0.05, 0.03]), None, 0.05, 0.0)
    Hm[:] = Hm + lens * PB.dome(lr_ - 13 * S, 4 * S, 6 * S)

    # --- tone-arm base plate, gimbal well, dials, arm rest, cue lever
    bx, by = 708 * S, 120 * S
    br = _np.sqrt((x - bx) ** 2 + (y - by) ** 2)
    bth = _np.arctan2(y - by, x - bx)
    plate = PB.disc(br, 64 * S)
    _put(A, Hm, Rm, Mm, plate, SILVER, None, 0.16, 1.0)
    Hm[:] = Hm * (1 - plate) + plate * (PB.dome(br - 64 * S, 10 * S, 6 * S) + PB.rings(br, 23, 0.8 * S, 0.4, 0.12 * S))
    well = PB.disc(br, 50 * S)
    _put(A, Hm, Rm, Mm, well, PB.srgb_to_lin([0.03, 0.03, 0.035]), 6 * S, 0.45, 0.2)
    for (dx_, dy_, rd_) in [(776, 48, 20), (770, 226, 28)]:
        dr = _np.sqrt((x - dx_ * S) ** 2 + (y - dy_ * S) ** 2)
        dm = PB.disc(dr, rd_ * S)
        dth = _np.arctan2(y - dy_ * S, x - dx_ * S)
        knurl = _np.cos(dth * 60) * 0.35 * S * PB.ring(dr, (rd_ - 4) * S, rd_ * S)
        _put(A, Hm, Rm, Mm, dm, PB.srgb_to_lin([0.06, 0.06, 0.065]), None, 0.35, 0.3)
        Hm[:] = Hm * (1 - dm) + dm * (PB.dome(dr - rd_ * S, 9 * S, 4 * S) + knurl)
        mark = (_np.abs(x - dx_ * S) < 1.2 * S) & (y < dy_ * S - 6 * S) & (y > (dy_ - rd_ + 4) * S)
        _put(A, Hm, Rm, Mm, mark.astype(_np.float32), PAINT_WHITE, None, 0.5, 0.0)
    ar = PB.rrect(x, y, 756 * S, 330 * S, 782 * S, 384 * S, 9 * S)
    arm_rest = 1 - PB.smoothstep(-1, 1, ar)
    _put(A, Hm, Rm, Mm, arm_rest, PB.srgb_to_lin([0.03, 0.03, 0.032]), None, 0.7, 0.0)
    Hm[:] = Hm * (1 - arm_rest) + arm_rest * (PB.dome(ar, 12 * S, 6 * S) - 5 * S * (1 - PB.smoothstep(-14 * S, -8 * S, ar)))
    cl = PB.rrect(x, y, 742 * S, 420 * S, 792 * S, 472 * S, 8 * S)
    cue = 1 - PB.smoothstep(-1, 1, cl)
    _put(A, Hm, Rm, Mm, cue, SILVER_BRIGHT, None, 0.22, 1.0)
    Hm[:] = Hm * (1 - cue) + cue * PB.dome(cl, 8 * S, 5 * S)
    engr = _text_mask(w, h, [(767 * S, 486 * S, "CUE", font(F_SEMI, 12 * S), "mm", 0)])
    Hm[:] = Hm - engr * 0.8 * S
    _put(A, Hm, Rm, Mm, engr, INK_DARK, None, 0.6, 0.0)

    # --- right faceplate: black anodised, brushed, chamfered, screws, LCD glass, white print
    px0, py0, px1, py1 = 808 * S, 14 * S, 1176 * S, 614 * S
    fd = PB.rrect(x, y, px0, py0, px1, py1, 16 * S)
    face = 1 - PB.smoothstep(-1, 1, fd)
    _put(A, Hm, Rm, Mm, face, ANOD, None, 0.30, 0.55)
    Hm[:] = Hm * (1 - face) + face * (PB.dome(fd, 7 * S, 4 * S) + PB.brushed(w, h, 31, 160, 0.5) * 0.6)
    for sx, sy in [(px0 + 14 * S, py0 + 14 * S), (px1 - 14 * S, py0 + 14 * S), (px0 + 14 * S, py1 - 14 * S), (px1 - 14 * S, py1 - 14 * S)]:
        sr_ = _np.sqrt((x - sx) ** 2 + (y - sy) ** 2)
        sm = PB.disc(sr_, 5.5 * S)
        _put(A, Hm, Rm, Mm, sm, SILVER, None, 0.25, 1.0)
        Hm[:] = Hm * (1 - sm) + sm * (7 * S + PB.dome(sr_ - 5.5 * S, 2.5 * S, 3 * S))
        slot = sm * ((_np.abs((x - sx) - (y - sy)) < 1.1 * S) | (_np.abs((x - sx) + (y - sy)) < 1.1 * S))
        Hm[:] = Hm - slot * 1.6 * S
    for (a0, b0, a1, b1) in [(830, 124, 1154, 188), (830, 196, 1154, 246)]:
        ld = PB.rrect(x, y, a0 * S, b0 * S, a1 * S, b1 * S, 9 * S)
        lcd = 1 - PB.smoothstep(-1, 1, ld)
        _put(A, Hm, Rm, Mm, lcd, PB.srgb_to_lin([0.012, 0.011, 0.008]), 4 * S, 0.04, 0.0)
    print_items = [
        ((808 + 24) * S, 30 * S, "SKRATCHA", font(F_BOLD, 50 * S), "la", 3 * S),
        ((808 + 26) * S, 86 * S, "DIRECT DRIVE  ·  SCRATCH TURNTABLE", font(F_SEMI, 14 * S), "la", S),
        ((808 + 22) * S, 412 * S, "FADER", font(F_SEMI, 13 * S), "la", S),
        ((808 + 176) * S, 474 * S, "TOUCH STRIP", font(F_SEMI, 13 * S), "la", S),
        ((808 + 22) * S, 540 * S, "PADS  1 START/STOP · 2 CUT · 3 HOLD · 4 CUE", font(F_MED, 15 * S), "la", 0),
        ((808 + 22) * S, 562 * S, "5 SET CUE · 6 REV · 7 33/45 · 8 FADER", font(F_MED, 15 * S), "la", 0),
        ((808 + 22) * S, 584 * S, "9–16 HOT CUES  (SET CUE + PAD = STORE)", font(F_MED, 15 * S), "la", 0)]
    for i, lab in enumerate(["SMOOTH", "RANGE", "CATCH", "LEVEL"]):
        print_items.append(((838 + i * 84 + 40) * S, 266 * S, lab, font(F_SEMI, 13 * S), "mm", S))
    pm = _text_mask(w, h, print_items)
    _put(A, Hm, Rm, Mm, pm, PAINT_WHITE, None, 0.55, 0.0)
    Hm[:] = Hm + pm * 0.15 * S
    lab_m = _text_mask(w, h, [((808 + 34) * S, 132 * S, "RECORD", font(F_SEMI, 11 * S), "la", S),
                              ((808 + 34) * S, 206 * S, "PITCH", font(F_SEMI, 11 * S), "la", S)])
    _put(A, Hm, Rm, Mm, lab_m, AMBER_LIN * 0.6, None, 0.5, 0.0)
    for yl in (110, 404, 532):
        lm = ((_np.abs(y - yl * S) < 0.7 * S) & (x > (808 + 22) * S) & (x < (1176 - 22) * S)).astype(_np.float32)
        Hm[:] = Hm - lm * 0.4 * S

    # --- pitch plate: satin aluminium strip, deep slot, printed scale
    fx0, fy0, fx1, fy1 = 1188 * S, 106 * S, 1264 * S, 536 * S
    pd = PB.rrect(x, y, fx0, fy0, fx1, fy1, 10 * S)
    pplate = 1 - PB.smoothstep(-1, 1, pd)
    _put(A, Hm, Rm, Mm, pplate, SILVER, None, 0.26, 1.0)
    Hm[:] = Hm * (1 - pplate) + pplate * (PB.dome(pd, 5 * S, 4 * S) + PB.brushed(w, h, 41, 90, 0.8, vertical=True) * 0.8)
    slot = ((x > fx0 + 31 * S) & (x < fx0 + 41 * S) & (y > fy0 + 26 * S) & (y < fy1 - 26 * S)).astype(_np.float32)
    slot = PB.blur(slot, 0.7 * S)
    _put(A, Hm, Rm, Mm, slot, PB.srgb_to_lin([0.01, 0.01, 0.01]), -6 * S, 0.9, 0.0)
    scale = []
    for k, lab in [(8, "+8"), (4, "+4"), (0, "0"), (-4, "-4"), (-8, "-8")]:
        yk = 122 + 20 + (8 - k) / 16 * (520 - 120 - 40)
        scale.append(((1188 + 4) * S, (yk - 9) * S, lab, font(F_SEMI, 12 * S), "ls", 0))
        tick = ((_np.abs(y - yk * S) < 0.7 * S) & (x > (1188 + 6) * S) & (x < (1188 + 20) * S)).astype(_np.float32)
        _put(A, Hm, Rm, Mm, tick, INK_DARK, None, 0.6, 0.0)
    scale += [((1188 + 1264) / 2 * S, (536 + 18) * S, "PITCH ADJ.", font(F_SEMI, 13 * S), "mm", 0),
              ((1188 + 1264) / 2 * S, (106 - 12) * S, "%", font(F_SEMI, 14 * S), "mm", 0)]
    sc = _text_mask(w, h, scale)
    _put(A, Hm, Rm, Mm, sc, INK_DARK, None, 0.6, 0.0)
    Hm[:] = Hm - sc * 0.5 * S

    an = rec * (1 - gap * 0.85) * (1 - runout) * 0.70 + (lip + step) * 0.75 + band * 0.4
    rgb, _ = PB.shade(A, Hm, Rm, Mm, normal_strength=1.0, shadows=True, ao=True, shadow_steps=34, ao_radius=14 * S, ao_strength=0.05,
                      aniso=(an, CX * S, CY * S, 1.0))
    img = PB.to_image(rgb)
    # emission: red strobe lamp and its glow toward the platter rim
    _glow(img, lx + 16 * S, ly - 20 * S, 90 * S, (255, 40, 20), 70)
    _glow(img, lx, ly, 20 * S, (255, 60, 30), 200)
    d = ImageDraw.Draw(img)
    d.ellipse([lx - 9 * S, ly - 9 * S, lx + 9 * S, ly + 9 * S], fill=(255, 92, 60, 230))
    d.ellipse([lx - 6 * S, ly - 8 * S, lx, ly - 3 * S], fill=(255, 225, 210, 220))
    return down(img)


def draw_label_frames():
    S = 3
    size = LABEL_TILE * S
    c = size / 2.0
    rL = R_LABEL * S
    lg = Image.open(LOGO).convert("RGBA")
    lg = lg.crop(lg.getbbox())
    lh = int(116 * S); lw = int(lg.width * lh / lg.height)
    lg = lg.resize((lw, lh), Image.LANCZOS)
    logo = Image.new("L", (size, size), 0)
    logo.paste(lg.split()[3], (int(c - lw / 2 - 4 * S), int(c - lh / 2)))
    sticker = Image.new("L", (size, size), 0)
    ImageDraw.Draw(sticker).rounded_rectangle([c - 4.5 * S, c - rL - 3 * S, c + 4.5 * S, c - rL + 22 * S], radius=1.5 * S, fill=255)
    ringm = Image.new("L", (size, size), 0)
    rd = ImageDraw.Draw(ringm)
    rd.ellipse([c - rL + 4 * S, c - rL + 4 * S, c + rL - 4 * S, c + rL - 4 * S], outline=255, width=int(2.4 * S))
    rd.ellipse([c - rL + 9 * S, c - rL + 9 * S, c + rL - 9 * S, c + rL - 9 * S], outline=160, width=S)
    paper = PB.fbm(size, size, 71, 5, 24.0) * 0.18 * S + PB.white(size, size, 72) * 0.04 * S
    paper_img = Image.fromarray(_np.clip(paper * 40 + 128, 0, 255).astype(_np.uint8))
    x, y = PB.grid(size, size, c, c)
    r = _np.sqrt(x * x + y * y)
    gold = PB.srgb_to_lin([1.0, 0.80, 0.42])
    frames = []
    for k in range(LABEL_FRAMES):
        ang = k * 360.0 / (LABEL_FRAMES - 1)
        rot = lambda im, res=Image.BICUBIC: _np.asarray(im.rotate(-ang, resample=res, center=(c, c))).astype(_np.float32) / 255.0
        lm, sm, gm = rot(logo), rot(sticker), rot(ringm)
        pp = (rot(paper_img, Image.BILINEAR) - 0.5) * (40 / 255.0) * 255 / 40 * 0.18 * S
        A, Hm, Rm, Mm = _maps(size, size, PB.srgb_to_lin([0.035, 0.035, 0.04]), 0.0, 0.70, 0.0)
        Hm += pp
        foil = _np.maximum(lm, gm)
        emb = PB.blur(foil, 0.8 * S) * 0.9 * S                                    # foil is pressed in slightly raised
        _put(A, Hm, Rm, Mm, foil, gold, None, 0.18, 1.0)
        Hm += emb + foil * PB.fbm(size, size, 73, 3, 10.0) * 0.06 * S
        _put(A, Hm, Rm, Mm, sm, PB.srgb_to_lin([0.86, 0.86, 0.83]), None, 0.75, 0.0)
        Hm += PB.blur(sm, 0.6 * S) * 0.6 * S
        # spindle (chrome, symmetric)
        sp = PB.disc(r, 9 * S)
        _put(A, Hm, Rm, Mm, sp, PB.srgb_to_lin([0.95, 0.95, 0.96]), None, 0.05, 1.0)
        Hm[:] = Hm * (1 - sp) + sp * (PB.dome(r - 9 * S, 14 * S, 9 * S))
        rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=10, ao_radius=4 * S, ao_strength=0.05)
        alpha = _np.maximum(PB.disc(r, rL, 1.2), sm)
        frames.append(PB.to_image(rgb, alpha).resize((LABEL_TILE, LABEL_TILE), Image.LANCZOS))
    strip = Image.new("RGBA", (LABEL_TILE, LABEL_TILE * LABEL_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * LABEL_TILE))
    return strip, frames


def draw_strobe_frames():
    S = SS
    size = 2 * R_STROBE_OUT * S
    c = size / 2.0
    x, y = PB.grid(size, size, c, c)
    r = _np.sqrt(x * x + y * y)
    th = _np.arctan2(y, x)
    rmid = (R_STROBE_IN + R_STROBE_OUT) / 2 * S
    lamp_angle = math.atan2(486 - CY, 44 - CX)
    frames = []
    for k in range(STROBE_FRAMES):
        phase = k / (STROBE_FRAMES - 1)
        # distance to the nearest dot centre on the ring
        a = (th + _np.pi / 2) * STROBE_DOTS / (2 * _np.pi) - phase
        frac = a - _np.round(a)
        ds = _np.sqrt((frac * 2 * _np.pi * rmid / STROBE_DOTS) ** 2 + (r - rmid) ** 2)
        dot = PB.disc(ds, 3.4 * S, 0.8)
        lamp = _np.clip(_np.cos(th - lamp_angle), 0, 1) ** 1.5
        A, Hm, Rm, Mm = _maps(size, size, PB.srgb_to_lin([0.75, 0.75, 0.77]), 0.0, 0.08, 1.0)
        Hm = PB.dome(ds - 3.4 * S, 2.2 * S, 3.4 * S) * dot
        rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=False, ao=False)
        # the strobe lamp tints the dots red (toward the lamp)
        tint = _np.dstack([0.55 + 1.6 * lamp, 0.20 + 0.15 * lamp, 0.16 + 0.10 * lamp])
        rgb = rgb * tint
        img = PB.to_image(rgb, dot)
        frames.append(down(img, (2 * R_STROBE_OUT, 2 * R_STROBE_OUT)))
    strip = Image.new("RGBA", (2 * R_STROBE_OUT, 2 * R_STROBE_OUT * STROBE_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * 2 * R_STROBE_OUT))
    return strip, frames


def _tube_height(w, h, pts, radius):
    """height map of a cylinder along a polyline (pts in pixel coords)"""
    m = _np.full((h, w), 1e9, _np.float32)
    canvas = _np.zeros((h, w), _np.uint8)
    pts_i = _np.round(_np.asarray(pts)).astype(_np.int32)
    _cv2.polylines(canvas, [pts_i.reshape(-1, 1, 2)], False, 255, thickness=int(radius * 2 + 4))
    dist = _cv2.distanceTransform(255 - _cv2.polylines(_np.zeros((h, w), _np.uint8), [pts_i.reshape(-1, 1, 2)], False, 255, 1), _cv2.DIST_L2, 5)
    inside = dist < radius
    hh = _np.where(inside, _np.sqrt(_np.clip(radius ** 2 - dist ** 2, 0, None)), 0).astype(_np.float32)
    mask = PB.smoothstep(radius + 0.8, radius - 0.8, dist).astype(_np.float32)
    return hh, mask


def draw_tonearm():
    S = 3
    w, h = 340, 540
    ox, oy = 470, 20
    Wp, Hp = w * S, h * S
    def T(px_, py_): return ((px_ - ox) * S, (py_ - oy) * S)
    A, Hm, Rm, Mm = _maps(Wp, Hp, PB.srgb_to_lin([0.95, 0.95, 0.96]), 0.0, 0.05, 1.0)
    alpha = _np.zeros((Hp, Wp), _np.float32)
    x, y = PB.grid(Wp, Hp)
    base_h = 30 * S
    # counterweight: knurled black cylinder (axis vertical)
    cx0, cy0 = T(686, 24); cx1, cy1 = T(730, 72)
    cwd = PB.rrect(x, y, cx0, cy0, cx1, cy1, 8 * S)
    cw = 1 - PB.smoothstep(-1, 1, cwd)
    u = _np.clip((x - (cx0 + cx1) / 2) / ((cx1 - cx0) / 2), -1, 1)
    cyl = _np.sqrt(_np.clip(1 - u * u, 0, 1)) * 22 * S
    kn = _np.cos((y - cy0) / S * 2 * _np.pi / 2.6) * 0.5 * S
    _put(A, Hm, Rm, Mm, cw, PB.srgb_to_lin([0.05, 0.05, 0.055]), None, 0.35, 0.4)
    Hm[:] = Hm * (1 - cw) + cw * (base_h + cyl + kn)
    alpha = _np.maximum(alpha, cw)
    # short chrome stub to the pivot
    stub = [T(708, yy) for yy in _np.linspace(70, 112, 20)]
    th_, tm_ = _tube_height(Wp, Hp, stub, 4.5 * S)
    _put(A, Hm, Rm, Mm, tm_, PB.srgb_to_lin([0.96, 0.96, 0.97]), None, 0.05, 1.0)
    Hm[:] = _np.maximum(Hm, (base_h + th_) * tm_)
    alpha = _np.maximum(alpha, tm_)
    # gimbal: polished ring around a dark bearing
    gx, gy = T(708, 120)
    gr = _np.sqrt((x - gx) ** 2 + (y - gy) ** 2)
    gimbal = PB.disc(gr, 24 * S)
    _put(A, Hm, Rm, Mm, gimbal, PB.srgb_to_lin([0.9, 0.9, 0.92]), None, 0.08, 1.0)
    Hm[:] = Hm * (1 - gimbal) + gimbal * (base_h + PB.dome(gr - 24 * S, 14 * S, 10 * S) + PB.rings(gr, 3, 0.8 * S, 0.3, 0.1 * S))
    bear = PB.disc(gr, 10 * S)
    _put(A, Hm, Rm, Mm, bear, PB.srgb_to_lin([0.03, 0.03, 0.035]), None, 0.4, 0.3)
    alpha = _np.maximum(alpha, gimbal)
    # S-shaped arm tube
    curve = RD.bezier((708, 128), (712, 300), (660, 380), (566, 482), 160)
    pts = [T(px_, py_) for px_, py_ in curve]
    th_, tm_ = _tube_height(Wp, Hp, pts, 6.2 * S)
    _put(A, Hm, Rm, Mm, tm_, PB.srgb_to_lin([0.96, 0.96, 0.97]), None, 0.04, 1.0)
    Hm[:] = Hm * (1 - tm_) + tm_ * (base_h + th_)
    alpha = _np.maximum(alpha, tm_)
    # headshell, finger lift and cartridge
    hx, hy = 566, 482
    shell = _np.zeros((Hp, Wp), _np.uint8)
    _cv2.fillPoly(shell, [_np.array([T(xx, yy) for xx, yy in [(hx - 32, hy - 10), (hx + 7, hy - 21), (hx + 15, hy + 4), (hx - 23, hy + 23)]], _np.int32)], 255)
    shm = PB.blur(shell.astype(_np.float32) / 255, 0.8)
    shd_ = _cv2.distanceTransform(shell, _cv2.DIST_L2, 5)
    _put(A, Hm, Rm, Mm, shm, PB.srgb_to_lin([0.04, 0.04, 0.045]), None, 0.30, 0.2)
    Hm[:] = Hm * (1 - shm) + shm * (base_h - 6 * S + _np.minimum(shd_, 4 * S))
    alpha = _np.maximum(alpha, shm)
    lift = [T(hx - 28 - t * 26, hy - 4 + t * 8) for t in _np.linspace(0, 1, 20)]
    th_, tm_ = _tube_height(Wp, Hp, lift, 2.3 * S)
    _put(A, Hm, Rm, Mm, tm_, PB.srgb_to_lin([0.95, 0.95, 0.96]), None, 0.05, 1.0)
    Hm[:] = _np.maximum(Hm, (base_h - 4 * S + th_) * tm_)
    alpha = _np.maximum(alpha, tm_)
    cart = _np.zeros((Hp, Wp), _np.uint8)
    _cv2.fillPoly(cart, [_np.array([T(xx, yy) for xx, yy in [(hx - 18, hy + 4), (hx - 2, hy - 1), (hx + 2, hy + 12), (hx - 14, hy + 17)]], _np.int32)], 255)
    cm = PB.blur(cart.astype(_np.float32) / 255, 0.8)
    _put(A, Hm, Rm, Mm, cm, PB.srgb_to_lin([0.02, 0.02, 0.022]), None, 0.5, 0.0)
    Hm[:] = Hm + cm * 3 * S
    acc = _np.zeros((Hp, Wp), _np.uint8)
    _cv2.fillPoly(acc, [_np.array([T(xx, yy) for xx, yy in [(hx - 15, hy + 7), (hx - 6, hy + 4), (hx - 4, hy + 9), (hx - 13, hy + 12)]], _np.int32)], 255)
    _put(A, Hm, Rm, Mm, acc.astype(_np.float32) / 255, PB.srgb_to_lin([0.75, 0.45, 0.08]), None, 0.3, 0.6)
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=12, ao_radius=3 * S, ao_strength=0.04)
    arm = PB.to_image(rgb, alpha)
    # cast shadow onto the deck below (soft, offset away from the key light)
    sh = PB.blur(_np.roll(_np.roll(alpha, int(14 * S), 0), int(12 * S), 1), 6 * S) * 0.62
    shadow = PB.to_image(_np.zeros((Hp, Wp, 3), _np.float32), sh)
    out = Image.new("RGBA", (Wp, Hp), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(arm)
    return out.resize((w, h), Image.LANCZOS), (ox, oy, w, h)


def draw_knob_strip(size=80, frames=64, accent=RED):
    S = 3
    Wp = size * S
    c = Wp / 2.0
    x, y = PB.grid(Wp, Wp, c, c)
    r = _np.sqrt(x * x + y * y)
    th = _np.arctan2(y, x)
    rk = c - 11 * S
    rc = rk * 0.74
    # static parts of the knob (identical in every frame except the pointer rotation)
    out = []
    a0, a1 = math.radians(135), math.radians(405)
    for k in range(frames):
        v = k / (frames - 1)
        ang = a0 + (a1 - a0) * v
        A, Hm, Rm, Mm = _maps(Wp, Wp, PB.srgb_to_lin([0.03, 0.03, 0.032]), 0.0, 0.6, 0.0)
        skirt = PB.disc(r, rk)
        # the knurling turns with the knob
        knurl = _np.cos((th - ang) * 40) * 0.6 * S * PB.ring(r, rc + 2 * S, rk)
        Hm = skirt * (PB.dome(r - rk, 16 * S, 5 * S) + knurl)
        cap = PB.disc(r, rc)
        Hm = Hm * (1 - cap) + cap * (17 * S + PB.dome(r - rc, 3 * S, rc) + PB.fbm(Wp, Wp, 9, 3, 6.0) * 0.08 * S)
        Rm = Rm * (1 - cap) + cap * 0.42
        # pointer: white inlay that turns with the knob
        px_ = x * math.cos(-ang) - y * math.sin(-ang)
        py_ = x * math.sin(-ang) + y * math.cos(-ang)
        ptr = ((px_ > rc * 0.25) & (px_ < rk * 0.97) & (_np.abs(py_) < 1.5 * S)).astype(_np.float32)
        ptr = PB.blur(ptr, 0.6)
        A = A * (1 - ptr[..., None]) + PB.srgb_to_lin([0.92, 0.92, 0.88]) * ptr[..., None]
        rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=10, ao_radius=3 * S, ao_strength=0.05)
        knob = PB.to_image(rgb, skirt)
        img = Image.new("RGBA", (Wp, Wp), (0, 0, 0, 0))
        # drop shadow
        sh = PB.blur(_np.roll(_np.roll(skirt, int(4 * S), 0), int(3 * S), 1), 4 * S) * 0.7
        img.alpha_composite(PB.to_image(_np.zeros((Wp, Wp, 3), _np.float32), sh))
        # LED ring (15 LEDs) behind
        d = ImageDraw.Draw(img)
        r_led = c - 4.5 * S
        lit = v * 14
        for i in range(15):
            aa = a0 + (a1 - a0) * i / 14
            lx, ly = c + r_led * math.cos(aa), c + r_led * math.sin(aa)
            RD.led_lens(d, lx, ly, 2.3 * S, (255, 120, 30), v > 0.004 and i <= lit + 1e-6, img)
            d = ImageDraw.Draw(img)
        img.alpha_composite(knob)
        out.append(img.resize((size, size), Image.LANCZOS))
    strip = Image.new("RGBA", (size, size * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * size))
    return strip, out


def _key_pbr(w, h, label, on, led=True, style="silver"):
    S = 3
    Wp, Hp = w * S, h * S
    x, y = PB.grid(Wp, Hp)
    press = 1.4 * S if on else 0.0
    dist = PB.rrect(x, y, 3 * S, 3 * S + press, Wp - 3 * S, Hp - 6 * S + press, 7 * S)
    body = 1 - PB.smoothstep(-1, 1, dist)
    if style == "silver":
        A, Hm, Rm, Mm = _maps(Wp, Hp, PB.srgb_to_lin([0.78, 0.79, 0.81]), 0.0, 0.28, 1.0)
        Hm = body * (PB.dome(dist, 10 * S, 5 * S) + PB.brushed(Wp, Hp, 51, 40, 0.5) * 0.5)
        ink = PB.srgb_to_lin([0.10, 0.10, 0.11])
    else:
        A, Hm, Rm, Mm = _maps(Wp, Hp, PB.srgb_to_lin([0.05, 0.05, 0.055]), 0.0, 0.55, 0.0)
        Hm = body * (PB.dome(dist, 10 * S, 5 * S) + PB.fbm(Wp, Hp, 52, 4, 4.0) * 0.18 * S)       # soft-touch rubber
        ink = PB.srgb_to_lin([0.85, 0.86, 0.88])
    fs = (18 if len(label) <= 6 else 15) * S
    ty = (h / 2 + (5 if led else 0)) * S + press - 2 * S
    tm = _text_mask(Wp, Hp, [(Wp / 2, ty, label, ImageFont.truetype(os.path.join(FONTS, F_BOLD), fs), "mm", 0)])
    A = A * (1 - tm[..., None]) + ink * tm[..., None]
    Hm = Hm - tm * 0.6 * S
    Rm = Rm * (1 - tm) + tm * 0.6
    Mm = Mm * (1 - tm)
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=8, ao_radius=2 * S, ao_strength=0.05)
    if on:
        rgb *= 0.92
    key = PB.to_image(rgb, body)
    img = Image.new("RGBA", (Wp, Hp), (0, 0, 0, 0))
    sh = PB.blur(_np.roll(_np.roll(body, int((4 if not on else 2.5) * S), 0), int(2 * S), 1), 3.5 * S) * 0.75
    img.alpha_composite(PB.to_image(_np.zeros((Hp, Wp, 3), _np.float32), sh))
    img.alpha_composite(key)
    if led:
        d = ImageDraw.Draw(img)
        RD.led_lens(d, Wp / 2, 11 * S + press, 3.3 * S, (255, 46, 26), on, img)
    return img.resize((w, h), Image.LANCZOS)


def draw_key(w, h, label, on, led=True, sub=None, style="silver"):
    return _key_pbr(w, h, label, on, led, style)


def draw_pitch_fader(w=72, h=396, frames=41):
    S = 3
    out = []
    travel_top, travel_bot = 20, h - 20
    cw_, ch_ = 54 * S, 34 * S
    gx, gy = PB.grid(cw_, ch_)
    dist = PB.rrect(gx, gy, 0, 0, cw_, ch_, 5 * S)
    capm = 1 - PB.smoothstep(-1, 1, dist)
    ridges = _np.cos(gy / S * 2 * _np.pi / 3.4) * 0.5 * S
    A, Hm, Rm, Mm = _maps(cw_, ch_, PB.srgb_to_lin([0.03, 0.03, 0.033]), 0.0, 0.45, 0.0)
    Hm = capm * (PB.dome(dist, 12 * S, 6 * S) + ridges * PB.smoothstep(-24 * S, -6 * S, dist))
    line = (_np.abs(gy - ch_ / 2) < 1.2 * S) & (dist < -3 * S)
    A[line] = PB.srgb_to_lin([0.92, 0.92, 0.93]); Mm[line] = 1.0; Rm[line] = 0.1; Hm[line] += 0.8 * S
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=8, ao_radius=2 * S)
    cap = PB.to_image(rgb, capm)
    capsh = PB.to_image(_np.zeros((ch_, cw_, 3), _np.float32), PB.blur(capm, 4 * S) * 0.75)
    for k in range(frames):
        v = k / (frames - 1)
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        yv = travel_bot - v * (travel_bot - travel_top)
        RD.led_lens(d, (w - 11) * S, h / 2 * S, 4.5 * S, (60, 235, 110), abs(v - 0.5) < 0.5 / (frames - 1), img)
        img.alpha_composite(capsh, (int(12 * S), int((yv - 17 + 5) * S)))
        img.alpha_composite(cap, (int(9 * S), int((yv - 17) * S)))
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def _faceplate_maps(A, Hm, Rm, Mm, x, y, box, S, seed):
    x0, y0, x1, y1 = [v * S for v in box]
    fd = PB.rrect(x, y, x0, y0, x1, y1, 16 * S)
    face = 1 - PB.smoothstep(-1, 1, fd)
    _put(A, Hm, Rm, Mm, face, ANOD, None, 0.30, 0.55)
    Hm[:] = Hm * (1 - face) + face * (PB.dome(fd, 7 * S, 4 * S) + PB.brushed(A.shape[1], A.shape[0], seed, 160, 0.5) * 0.6)
    for sx, sy in [(x0 + 13 * S, y0 + 13 * S), (x1 - 13 * S, y0 + 13 * S), (x0 + 13 * S, y1 - 13 * S), (x1 - 13 * S, y1 - 13 * S)]:
        sr_ = _np.sqrt((x - sx) ** 2 + (y - sy) ** 2)
        sm = PB.disc(sr_, 5 * S)
        _put(A, Hm, Rm, Mm, sm, SILVER, None, 0.25, 1.0)
        Hm[:] = Hm * (1 - sm) + sm * (7 * S + PB.dome(sr_ - 5 * S, 2.5 * S, 3 * S))
        slot = sm * ((_np.abs((x - sx) - (y - sy)) < 1.0 * S) | (_np.abs((x - sx) + (y - sy)) < 1.0 * S))
        Hm[:] = Hm - slot * 1.5 * S


def draw_setup_bg():
    S = SS
    w, h = W * S, H * S
    A, Hm, Rm, Mm = _maps(w, h, SILVER, 0.0, 0.30, 1.0)
    x, y = PB.grid(w, h)
    Hm += PB.brushed(w, h, 61, length=400, strength=0.16) + PB.white(w, h, 62) * 0.015 + PB.fbm(w, h, 62, 4, 120.0) * 0.3
    boxes = [((20, 16, 628, 300), "MOTOR"), ((652, 16, 1260, 300), "TOUCH STRIP"),
             ((20, 320, 628, 612), "FADER  ·  SOUND  ·  RECORDS"), ((652, 320, 1260, 612), "SCRATCH  (STRIP IN Q-LINK MODE)")]
    items = []
    for i, (box, t) in enumerate(boxes):
        _faceplate_maps(A, Hm, Rm, Mm, x, y, box, S, 70 + i)
        items.append(((box[0] + 30) * S, (box[1] + 14) * S, t, font(F_BOLD, 20 * S), "la", 2 * S))
    f13 = font(F_SEMI, 13 * S)
    for (xx, yy, s, anc) in [(90, 70, "START TIME", "mm"), (210, 70, "BRAKE TIME", "mm"), (300, 66, "PITCH RANGE", "la"), (300, 176, "RECORD END", "la"),
                             (722, 70, "RANGE", "mm"), (842, 70, "SMOOTH", "mm"), (932, 66, "DIRECTION", "la"), (932, 176, "LET GO WHEN", "la"),
                             (40, 370, "CUT CURVE", "la"), (110, 470, "CRACKLE", "mm"), (230, 470, "CATCH", "mm"), (300, 466, "PAD BASE NOTE", "la")]:
        items.append((xx * S, yy * S, s, f13, anc, S))
    fm = font(F_MED, 14 * S)
    items.append((672 * S, 262 * S, "CENTER: strip springs back = hand off.  TIMEOUT: no move for 0.12 s = hand off.", fm, "la", 0))
    items.append((40 * S, 586 * S, "Own WAVs: MPC Documents/SKRATCHA  or  the plugin folder /My Samples", fm, "la", 0))
    for i, s in enumerate(["Touch strip mode PITCH BEND works best (14 bit).", "Q-LINK mode: touch the SCRATCH bar first, then use the strip.",
                           "A Q-Link knob on SCRATCH scratches too.", "", "MPC: SHIFT + TOUCH STRIP opens the strip settings."]):
        items.append((672 * S, (472 + i * 24) * S, s, font(F_MED, 16 * S), "la", 0))
    pm = _text_mask(w, h, items)
    _put(A, Hm, Rm, Mm, pm, PAINT_WHITE, None, 0.55, 0.0)
    Hm[:] = Hm + pm * 0.15 * S
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=20, ao_radius=12 * S, ao_strength=0.05)
    return down(PB.to_image(rgb))


def draw_info_bg():
    S = SS
    w, h = W * S, H * S
    A, Hm, Rm, Mm = _maps(w, h, PB.srgb_to_lin([0.05, 0.05, 0.055]), 0.0, 0.35, 0.5)
    x, y = PB.grid(w, h)
    Hm += PB.brushed(w, h, 81, length=160, strength=0.8)
    cx, cy, R = 640 * S, 300 * S, 250 * S
    r = _np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    th = _np.arctan2(y - cy, x - cx)
    rec = PB.disc(r, R)
    rr = r / S
    gaps = _np.sort(PB.rng(33).uniform(118, 244, 6))
    gap = _np.zeros_like(r)
    for g in gaps:
        gap = _np.maximum(gap, _np.exp(-((rr - g) / 1.3) ** 2))
    runout = PB.ring(r, 98 * S, 112 * S, 1.5)
    grooves = PB.radial_value(r, 35, scale=0.9, amp=1.0, smooth=1) * (1 - gap) * (1 - runout) * 0.07 * S
    _put(A, Hm, Rm, Mm, rec, PB.srgb_to_lin([0.018, 0.018, 0.02]), None, 0.16, 0.0)
    Hm[:] = Hm * (1 - rec) + rec * (8 * S + PB.dome(r - R, 2 * S, 3 * S) + grooves + PB.fbm(w, h, 36, 3, 300.0) * 1.2 * S)
    Rm[:] = Rm * (1 - rec) + rec * (0.16 + 0.10 * (1 - gap) * (1 - runout) - 0.08 * runout)
    lab = PB.disc(r, 96 * S)
    _put(A, Hm, Rm, Mm, lab, PB.srgb_to_lin([0.035, 0.035, 0.04]), None, 0.7, 0.0)
    Hm[:] = Hm * (1 - lab) + lab * (8 * S + PB.fbm(w, h, 37, 5, 24.0) * 0.18 * S)
    lg = Image.open(LOGO).convert("RGBA"); lg = lg.crop(lg.getbbox())
    lh = 140 * S; lw = int(lg.width * lh / lg.height)
    lgm = Image.new("L", (w, h), 0)
    lgm.paste(lg.resize((lw, lh), Image.LANCZOS).split()[3], (int(cx - lw / 2 - 4 * S), int(cy - lh / 2)))
    ringm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(ringm).ellipse([cx - 91 * S, cy - 91 * S, cx + 91 * S, cy + 91 * S], outline=255, width=int(2.5 * S))
    foil = _np.maximum(_np.asarray(lgm), _np.asarray(ringm)).astype(_np.float32) / 255
    _put(A, Hm, Rm, Mm, foil, PB.srgb_to_lin([1.0, 0.80, 0.42]), None, 0.18, 1.0)
    Hm[:] = Hm + PB.blur(foil, 0.8 * S) * 0.9 * S
    items = [(640 * S, 576 * S, "SKRATCHA  ·  CREATOR: JJ DA PLUG", font(F_BOLD, 24 * S), "mm", 3 * S),
             (640 * S, 606 * S, "VERSION 1.0.0  ·  MPC PLUGIN SDK", font(F_MED, 14 * S), "mm", S)]
    for i, s in enumerate(["1  Touch strip: set it to PITCH BEND", "2  Touch the strip = hand on the record", "3  Move = scratch, lift = motor takes over",
                           "4  Pad 1 START/STOP, pad 2 CUT", "5  Pad 9–16 hot cues"]):
        items.append((34 * S, (60 + i * 30) * S, s, font(F_MED, 17 * S), "la", 0))
    for i, s in enumerate(["SMOOTH: lower = sharper, higher = softer", "RANGE: how far one stroke turns the record",
                           "CATCH: how fast the motor grabs the record", "Record your scratches: the MPC records", "the strip as MIDI (pitch bend)."]):
        items.append((1246 * S, (60 + i * 30) * S, s, font(F_MED, 17 * S), "ra", 0))
    pm = _text_mask(w, h, items)
    _put(A, Hm, Rm, Mm, pm, PAINT_WHITE, None, 0.55, 0.0)
    an = rec * (1 - gap * 0.85) * (1 - runout) * (1 - lab) * 0.85
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=20, ao_radius=12 * S, ao_strength=0.05, aniso=(an, cx, cy, 1.0))
    return down(PB.to_image(rgb))



# ======================================================================================================
# DJ-DECK LOOK (silver plinth, felt slipmat with a big rotating JF print, 4 rows of strobe dots)
# ======================================================================================================
R_STROBE_IN = 262
R_MAT = 258           # inner polished step 258..262
R_REC = 255           # slipmat radius (also the on-screen jog area)
R_LABEL = 170         # radius of the rotating print tile
LABEL_TILE = 340
LABEL_FRAMES = 48
STROBE_DOTS = 180
STROBE_ROWS = 4

PRINT_COL = PB.srgb_to_lin([0.33, 0.38, 0.47])      # grey-blue print on the felt
FELT_COL = PB.srgb_to_lin([0.050, 0.056, 0.078])


def _felt_height(w, h, seed, S):
    n = PB.white(w, h, seed)
    fib = _cv2.GaussianBlur(n, (0, 0), 0.6 * S) * 0.5 * S + _cv2.GaussianBlur(PB.white(w, h, seed + 1), (0, 0), 1.6 * S) * 0.35 * S
    return fib + PB.fbm(w, h, seed + 2, 3, 80.0) * 0.4 * S


def draw_deck_bg():
    S = SS
    w, h = W * S, H * S
    A, Hm, Rm, Mm = _maps(w, h, SILVER, 0.0, 0.28, 1.0)
    x, y = PB.grid(w, h)
    Hm += PB.brushed(w, h, 1, length=400, strength=0.14) + PB.white(w, h, 2) * 0.012 + PB.fbm(w, h, 2, 4, 160.0) * 0.25
    Rm += PB.fbm(w, h, 3, 3, 60.0) * 0.03

    # ---------------- platter: polished outer lip, wide strobe band (4 rows), polished step, felt slipmat
    px, py = x - CX * S, y - CY * S
    r = _np.sqrt(px * px + py * py)
    lip = PB.ring(r, R_STROBE_OUT * S, R_PLATTER * S)
    band = PB.ring(r, R_STROBE_IN * S, R_STROBE_OUT * S)
    step = PB.ring(r, R_MAT * S, R_STROBE_IN * S)
    mat = PB.disc(r, R_REC * S)
    gapm = PB.ring(r, R_REC * S, R_MAT * S)
    lathe = PB.radial_value(r, 5, scale=0.7, amp=0.05 * S, smooth=2)
    _put(A, Hm, Rm, Mm, lip, SILVER_BRIGHT, 14 * S, 0.08, 1.0)
    Hm[:] = Hm + lip * (lathe + PB.dome(r - R_PLATTER * S, 5 * S, 4 * S) - 5 * S)
    _put(A, Hm, Rm, Mm, band, PB.srgb_to_lin([0.50, 0.51, 0.53]), None, 0.30, 1.0)
    Hm[:] = Hm * (1 - band) + band * (10 * S + (r - R_STROBE_IN * S) / ((R_STROBE_OUT - R_STROBE_IN) * S) * 4 * S + lathe * 0.5)
    _put(A, Hm, Rm, Mm, step, SILVER_BRIGHT, 12 * S, 0.10, 1.0)
    Hm[:] = Hm + step * lathe
    _put(A, Hm, Rm, Mm, gapm, PB.srgb_to_lin([0.02, 0.02, 0.022]), 7 * S, 0.8, 0.0)
    # felt slipmat
    felt = _felt_height(w, h, 7, S)
    _put(A, Hm, Rm, Mm, mat, FELT_COL, None, 0.95, 0.0)
    Hm[:] = Hm * (1 - mat) + mat * (11 * S + felt + PB.dome(r - R_REC * S, 1.5 * S, 3 * S) * 0)
    A[:] = A * (1 + (mat * PB.blur(PB.white(w, h, 9), 0.7 * S) * 0.10)[..., None])
    # thin printed ring on the mat
    pr = PB.ring(r, (R_REC - 26) * S, (R_REC - 24) * S, 0.8)
    _put(A, Hm, Rm, Mm, pr, PRINT_COL * 0.8, None, 0.9, 0.0)

    # ---------------- target light (top left): chrome pop-up disc
    tx, ty = 56 * S, 54 * S
    tr = _np.sqrt((x - tx) ** 2 + (y - ty) ** 2)
    tl = PB.disc(tr, 34 * S)
    _put(A, Hm, Rm, Mm, tl, SILVER_BRIGHT, None, 0.05, 1.0)
    Hm[:] = Hm * (1 - tl) + tl * (PB.dome(tr - 34 * S, 8 * S, 6 * S) + PB.radial_value(tr, 41, 1.2, 0.05 * S))
    tc = PB.disc(tr, 6 * S)
    _put(A, Hm, Rm, Mm, tc, SILVER, None, 0.15, 1.0)
    Hm[:] = Hm - tc * 2 * S

    # ---------------- bottom left: black knurled dial over the strobe lamp, small printed scale
    kx, ky = 50 * S, 470 * S
    kr = _np.sqrt((x - kx) ** 2 + (y - ky) ** 2)
    kth = _np.arctan2(y - ky, x - kx)
    kd = PB.disc(kr, 24 * S)
    _put(A, Hm, Rm, Mm, kd, PB.srgb_to_lin([0.04, 0.04, 0.045]), None, 0.4, 0.2)
    Hm[:] = Hm * (1 - kd) + kd * (PB.dome(kr - 24 * S, 9 * S, 4 * S) + _np.cos(kth * 70) * 0.4 * S * PB.ring(kr, 18 * S, 24 * S))
    km = (_np.abs(x - kx) < 1.2 * S) & (y < ky - 8 * S) & (y > ky - 20 * S)
    _put(A, Hm, Rm, Mm, km.astype(_np.float32), PAINT_WHITE, None, 0.5, 0.0)
    dial_txt = _text_mask(w, h, [((20 + i * 15) * S, 508 * S, s, font(F_SEMI, 9 * S), "la", 0) for i, s in enumerate(["-3", "0", "+3", "%"])])
    _put(A, Hm, Rm, Mm, dial_txt, INK_DARK, None, 0.6, 0.0)

    # ---------------- tone-arm base: large ring housing, recessed well, anti-skate dial, lift lever, arm rest
    bx, by = 708 * S, 124 * S
    br = _np.sqrt((x - bx) ** 2 + (y - by) ** 2)
    ringo = PB.disc(br, 94 * S)
    _put(A, Hm, Rm, Mm, ringo, SILVER_BRIGHT, None, 0.12, 1.0)
    Hm[:] = Hm * (1 - ringo) + ringo * (PB.dome(br - 94 * S, 9 * S, 6 * S) + PB.radial_value(br, 23, 1.0, 0.05 * S))
    well = PB.disc(br, 80 * S)
    _put(A, Hm, Rm, Mm, well, PB.srgb_to_lin([0.16, 0.16, 0.17]), 3 * S, 0.30, 0.8)
    Hm[:] = Hm - well * PB.dome(br - 80 * S, 0, 1) * 0
    # anti-skate dial (black, knurled, white scale)
    ax_, ay_ = 768 * S, 92 * S
    ar_ = _np.sqrt((x - ax_) ** 2 + (y - ay_) ** 2)
    ath = _np.arctan2(y - ay_, x - ax_)
    ad = PB.disc(ar_, 20 * S)
    _put(A, Hm, Rm, Mm, ad, PB.srgb_to_lin([0.035, 0.035, 0.04]), None, 0.35, 0.2)
    Hm[:] = Hm * (1 - ad) + ad * (10 * S + PB.dome(ar_ - 20 * S, 4 * S, 3 * S) + _np.cos(ath * 64) * 0.35 * S * PB.ring(ar_, 16 * S, 20 * S))
    for k in range(7):
        a = math.radians(-210 + k * 40)
        tick = (_np.abs((x - ax_) * math.sin(a) - (y - ay_) * math.cos(a)) < 0.8 * S) & PB.ring(ar_, 9 * S, 14 * S).astype(bool) & (((x - ax_) * math.cos(a) + (y - ay_) * math.sin(a)) > 0)
        _put(A, Hm, Rm, Mm, tick.astype(_np.float32), PAINT_WHITE, None, 0.5, 0.0)
    # arm-lift lever (black, angled)
    lev = _np.zeros((h, w), _np.uint8)
    _cv2.line(lev, (int(770 * S), int(176 * S)), (int(792 * S), int(214 * S)), 255, int(7 * S))
    levm = PB.blur(lev.astype(_np.float32) / 255, 0.8)
    _put(A, Hm, Rm, Mm, levm, PB.srgb_to_lin([0.03, 0.03, 0.035]), None, 0.35, 0.1)
    Hm[:] = Hm + levm * 12 * S
    # arm rest clip
    ar2 = PB.rrect(x, y, 744 * S, 300 * S, 764 * S, 340 * S, 7 * S)
    arest = 1 - PB.smoothstep(-1, 1, ar2)
    _put(A, Hm, Rm, Mm, arest, PB.srgb_to_lin([0.03, 0.03, 0.032]), None, 0.6, 0.0)
    Hm[:] = Hm * (1 - arest) + arest * PB.dome(ar2, 12 * S, 5 * S)

    # ---------------- control area on the same silver plinth (engraved, no separate box)
    px0, py0, px1, py1 = 808 * S, 14 * S, 1176 * S, 614 * S
    sep = ((_np.abs(x - 800 * S) < 0.8 * S) & (y > 24 * S) & (y < 604 * S)).astype(_np.float32)
    Hm[:] = Hm - sep * 0.8 * S
    for (a0, b0, a1, b1) in [(830, 124, 1154, 188), (830, 196, 1154, 246), (948, 438, 1098, 478), (984, 494, 1154, 522)]:
        ld = PB.rrect(x, y, a0 * S, b0 * S, a1 * S, b1 * S, 8 * S)
        lcd = 1 - PB.smoothstep(-1, 1, ld)
        bez = (1 - PB.smoothstep(-1, 1, ld - 3 * S)) - lcd
        _put(A, Hm, Rm, Mm, bez, PB.srgb_to_lin([0.05, 0.05, 0.055]), None, 0.4, 0.3)
        _put(A, Hm, Rm, Mm, lcd, PB.srgb_to_lin([0.012, 0.011, 0.008]), -1 * S, 0.04, 0.0)
    for yl in (110, 404, 532):
        lm = ((_np.abs(y - yl * S) < 0.7 * S) & (x > (808 + 22) * S) & (x < (1176 - 22) * S)).astype(_np.float32)
        Hm[:] = Hm - lm * 0.6 * S
    ink_items = [
        ((808 + 24) * S, 26 * S, "SKRATCHA", font(F_BOLD, 52 * S), "la", 3 * S),
        ((808 + 26) * S, 84 * S, "DIRECT DRIVE SCRATCH TURNTABLE", font(F_SEMI, 14 * S), "la", S),
        ((808 + 22) * S, 412 * S, "FADER", font(F_SEMI, 13 * S), "la", S),
        ((808 + 176) * S, 478 * S, "TOUCH STRIP", font(F_SEMI, 12 * S), "la", S),
        ((808 + 22) * S, 540 * S, "PADS  1 START/STOP · 2 CUT · 3 HOLD · 4 CUE", font(F_MED, 15 * S), "la", 0),
        ((808 + 22) * S, 562 * S, "5 SET CUE · 6 REV · 7 33/45 · 8 FADER", font(F_MED, 15 * S), "la", 0),
        ((808 + 22) * S, 584 * S, "9–16 HOT CUES  (SET CUE + PAD = STORE)", font(F_MED, 15 * S), "la", 0)]
    for i, lab in enumerate(["SMOOTH", "RANGE", "CATCH", "LEVEL"]):
        ink_items.append(((838 + i * 84 + 40) * S, 266 * S, lab, font(F_SEMI, 13 * S), "mm", S))
    tm = _text_mask(w, h, ink_items)
    _put(A, Hm, Rm, Mm, tm, INK_DARK, None, 0.6, 0.0)
    Hm[:] = Hm - tm * 0.4 * S
    lab_m = _text_mask(w, h, [((808 + 34) * S, 132 * S, "RECORD", font(F_SEMI, 11 * S), "la", S),
                              ((808 + 34) * S, 206 * S, "PITCH", font(F_SEMI, 11 * S), "la", S)])
    _put(A, Hm, Rm, Mm, lab_m, AMBER_LIN * 0.6, None, 0.5, 0.0)

    # ---------------- pitch slot directly in the plinth with a printed scale (+ at the top)
    fx0, fy0, fx1, fy1 = 1188 * S, 106 * S, 1264 * S, 536 * S
    slot = ((x > fx0 + 31 * S) & (x < fx0 + 41 * S) & (y > fy0 + 26 * S) & (y < fy1 - 26 * S)).astype(_np.float32)
    slot = PB.blur(slot, 0.7 * S)
    _put(A, Hm, Rm, Mm, slot, PB.srgb_to_lin([0.01, 0.01, 0.01]), -6 * S, 0.9, 0.0)
    scale = []
    for k, lab in [(8, "+8"), (6, "6"), (4, "4"), (2, "2"), (0, "0"), (-2, "2"), (-4, "4"), (-6, "6"), (-8, "-8")]:
        yk = 122 + 20 + (8 - k) / 16 * (520 - 120 - 40)
        scale.append(((1188 + 4) * S, (yk + 4) * S, lab, font(F_SEMI, 10 * S), "ls", 0))
        tick = ((_np.abs(y - yk * S) < 0.6 * S) & (x > (1188 + 18) * S) & (x < (1188 + 26) * S)).astype(_np.float32)
        _put(A, Hm, Rm, Mm, tick, INK_DARK, None, 0.6, 0.0)
    scale += [((1188 + 1264) / 2 * S, (536 + 18) * S, "PITCH ADJ.", font(F_SEMI, 12 * S), "mm", 0)]
    sc = _text_mask(w, h, scale)
    _put(A, Hm, Rm, Mm, sc, INK_DARK, None, 0.6, 0.0)
    zero = (((x - (1188 + 12) * S) ** 2 + (y - 320 * S) ** 2) < (2.6 * S) ** 2).astype(_np.float32)
    _put(A, Hm, Rm, Mm, zero, PB.srgb_to_lin([0.8, 0.12, 0.08]), None, 0.3, 0.0)

    an = (lip + step) * 0.8 + band * 0.4 + ringo * (1 - well) * 0.7
    rgb, _ = PB.shade(A, Hm, Rm, Mm, normal_strength=1.0, shadows=True, ao=True, shadow_steps=34, ao_radius=14 * S, ao_strength=0.05,
                      aniso=(an, CX * S, CY * S, 1.0))
    img = PB.to_image(rgb)
    # the strobe lamp under the dial lights the dots nearby red
    _glow(img, 96 * S, 452 * S, 70 * S, (255, 40, 20), 85)
    return down(img)


def draw_label_frames():
    """the big JF print on the felt slipmat (turns with the platter) + the spindle"""
    S = 2
    size = LABEL_TILE * S
    c = size / 2.0
    lg = Image.open(LOGO).convert("RGBA")
    lg = lg.crop(lg.getbbox())
    lh = int(276 * S); lw = int(lg.width * lh / lg.height)
    lg = lg.resize((lw, lh), Image.LANCZOS)
    logo = Image.new("L", (size, size), 0)
    logo.paste(lg.split()[3], (int(c - lw / 2 - 6 * S), int(c - lh / 2)))
    x, y = PB.grid(size, size, c, c)
    r = _np.sqrt(x * x + y * y)
    felt = _felt_height(size, size, 7, S)
    felt_img = Image.fromarray(_np.clip(felt / (2 * S) * 60 + 128, 0, 255).astype(_np.uint8))
    speck = Image.fromarray(_np.clip(PB.blur(PB.white(size, size, 91), 0.7 * S) * 50 + 128, 0, 255).astype(_np.uint8))
    frames = []
    for k in range(LABEL_FRAMES):
        ang = k * 360.0 / (LABEL_FRAMES - 1)
        rot = lambda im, res=Image.BICUBIC: _np.asarray(im.rotate(-ang, resample=res, center=(c, c))).astype(_np.float32) / 255.0
        lm = rot(logo)
        fh = (rot(felt_img, Image.BILINEAR) - 0.5) * (255 / 60) * 2 * S
        sp_ = (rot(speck, Image.BILINEAR) - 0.5) * (255 / 50)
        # ink sits on the fibres: coverage varies with the felt
        cover = _np.clip(lm * (0.82 + 0.25 * sp_), 0, 1)
        A, Hm, Rm, Mm = _maps(size, size, PRINT_COL, 0.0, 0.92, 0.0)
        A *= (1 + 0.12 * sp_)[..., None]
        Hm = fh + lm * 0.15 * S
        sp = PB.disc(r, 7 * S)
        _put(A, Hm, Rm, Mm, sp, PB.srgb_to_lin([0.95, 0.95, 0.96]), None, 0.05, 1.0)
        Hm[:] = Hm * (1 - sp) + sp * PB.dome(r - 7 * S, 12 * S, 7 * S)
        rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=False, shadow_steps=8)
        alpha = _np.maximum(cover, sp)
        frames.append(PB.to_image(rgb, alpha).resize((LABEL_TILE, LABEL_TILE), Image.LANCZOS))
    strip = Image.new("RGBA", (LABEL_TILE, LABEL_TILE * LABEL_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * LABEL_TILE))
    return strip, frames


def draw_strobe_frames():
    S = SS
    size = 2 * R_STROBE_OUT * S
    c = size / 2.0
    x, y = PB.grid(size, size, c, c)
    r = _np.sqrt(x * x + y * y)
    th = _np.arctan2(y, x)
    lamp_angle = math.atan2(470 - CY, 50 - CX)
    rows = [R_STROBE_IN + 4.5 + i * (R_STROBE_OUT - R_STROBE_IN - 9) / (STROBE_ROWS - 1) for i in range(STROBE_ROWS)]
    lamp = _np.clip(_np.cos(th - lamp_angle), 0, 1) ** 3
    frames = []
    for k in range(STROBE_FRAMES):
        phase = k / (STROBE_FRAMES - 1)
        Hm = _np.zeros((size, size), _np.float32)
        dots = _np.zeros((size, size), _np.float32)
        for i, rm in enumerate(rows):
            rmid = rm * S
            a = (th + _np.pi / 2) * STROBE_DOTS / (2 * _np.pi) - phase - (0.5 if i % 2 else 0.0)
            frac = a - _np.round(a)
            ds = _np.sqrt((frac * 2 * _np.pi * rmid / STROBE_DOTS) ** 2 + (r - rmid) ** 2)
            d1 = PB.disc(ds, 1.9 * S, 0.7)
            dots = _np.maximum(dots, d1)
            Hm = _np.maximum(Hm, PB.dome(ds - 1.9 * S, 1.3 * S, 1.9 * S) * d1)
        A, _, Rm, Mm = _maps(size, size, PB.srgb_to_lin([0.85, 0.85, 0.87]), 0.0, 0.10, 1.0)
        rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=False, ao=False)
        tint = _np.dstack([1.25 + 3.4 * lamp, 1.25 + 0.1 * lamp, 1.30 + 0.05 * lamp])
        rgb = rgb * tint
        frames.append(down(PB.to_image(rgb, dots), (2 * R_STROBE_OUT, 2 * R_STROBE_OUT)))
    strip = Image.new("RGBA", (2 * R_STROBE_OUT, 2 * R_STROBE_OUT * STROBE_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * 2 * R_STROBE_OUT))
    return strip, frames



def main():
    preview_vals = {}   # param -> normalised value for previews

    # ---- shared pictures ----
    knob_strip, knob_frames = draw_knob_strip(80, 64)
    knob_fn = save(knob_strip, "sk_knob80_f64.png")
    led_strip, led_frames = draw_led_strip(170, 28, 33)
    led_fn = save(led_strip, "sk_stripled_f33.png")
    cut_strip, cut_frames = draw_cut_led(150, 40)
    cut_fn = save(cut_strip, "sk_cutled_f2.png")
    clear = Image.new("RGBA", (4, 8), (0, 0, 0, 0))
    clear_fn = save(clear, "sk_clear_f2.png")

    def key_pair(name, w, h, label, led=True, style="silver", sub=None):
        on = draw_key(w, h, label, True, led, sub, style); off = draw_key(w, h, label, False, led, sub, style)
        return save(on, "sk_key_%s_on.png" % name), save(off, "sk_key_%s_off.png" % name), on, off

    knob_def = def_knob("skKnob80", knob_fn, 64, 80)
    knob_deck = def_knob("skKnob80d", knob_fn, 64, 80, val_colour="ff2a2b2e")

    # ================= DECK =================
    deck_bg = draw_deck_bg()
    deck = Tab("DECK", save(deck_bg, "sk_bg_deck.png"))
    prev = deck_bg.copy()

    strobe_strip, strobe_frames = draw_strobe_frames()
    st_fn = save(strobe_strip, "sk_strobe_%d_f%d.png" % (2 * R_STROBE_OUT, STROBE_FRAMES))
    sd = def_display("skStrobe", st_fn, STROBE_FRAMES, 2 * R_STROBE_OUT, 2 * R_STROBE_OUT)
    deck.place(sd, P["Strobe"], CX - R_STROBE_OUT, CY - R_STROBE_OUT, 2 * R_STROBE_OUT, 2 * R_STROBE_OUT, name="strobe")
    prev.alpha_composite(strobe_frames[0], (CX - R_STROBE_OUT, CY - R_STROBE_OUT))

    label_strip, label_frames = draw_label_frames()
    lb_fn = save(label_strip, "sk_label_%d_f%d.png" % (LABEL_TILE, LABEL_FRAMES))
    ld = def_display("skLabel", lb_fn, LABEL_FRAMES, LABEL_TILE, LABEL_TILE)
    deck.place(ld, P["Angle"], CX - LABEL_TILE // 2, CY - LABEL_TILE // 2, LABEL_TILE, LABEL_TILE, name="label")
    prev.alpha_composite(label_frames[5], (CX - LABEL_TILE // 2, CY - LABEL_TILE // 2))

    arm, (ax, ay, aw, ah) = draw_tonearm()
    deck.image("Tonearm", save(arm, "sk_tonearm.png"), ax, ay, aw, ah)
    prev.alpha_composite(arm, (ax, ay))

    # on-screen platter: absolute rotary knob over the record
    jd = def_jog("skJog", clear_fn, 2 * R_REC)
    deck.place(jd, P["Platter"], CX - R_REC, CY - R_REC, 2 * R_REC, 2 * R_REC, name="jog")

    # START/STOP, 33, 45, reverse
    ss_on, ss_off, ss_on_i, ss_off_i = key_pair("start", 132, 58, "START·STOP", led=True)
    deck.place(def_toggle("skStart", ss_on, ss_off, 132, 58), P["Start/Stop"], 16, 552, 132, 58, name="start")
    prev.alpha_composite(ss_off_i, (16, 552))
    for i, lab in enumerate(["33", "45"]):
        on, off, on_i, off_i = key_pair("sp%s" % lab, 66, 52, lab, led=True)
        deck.place(def_segment("skSpeed%d" % i, on, off, 66, 52, i, 2), P["Speed"], 520 + i * 72, 560, 66, 52, name=lab)
        prev.alpha_composite(on_i if i == 0 else off_i, (520 + i * 72, 560))

    # pitch fader
    pf_strip, pf_frames = draw_pitch_fader(72, 396, 41)
    pf_fn = save(pf_strip, "sk_pitch_72x396_f41.png")
    pdef = def_slider("skPitch", pf_fn, 41, 72, 396, "Vertical")
    deck.place(pdef, P["Pitch"], 1190, 122, 72, 396, name="pitch")
    prev.alpha_composite(pf_frames[20], (1190, 122))

    # record (sample) window: touch + drag left/right picks the record, value text is its name
    rec_def = define("skRecord", [act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "", "knob overlay"), act("Enter Pressed", "Show Overlay", "", "knob overlay")],
                     [focus_comp(324, 60), comp("Pick", "Knob", filmstrip(clear_fn, 2, "Horizontal"), bounds(0, 0, 324, 60)),
                      comp("Value", "Label", label_data(28, "ffffb52e", "Bold", "left verticallyCentred"), bounds(14, 12, 300, 44))])
    deck.place(rec_def, P["Sample"], 830, 126, 324, 60, name="record")
    pitch_ro = def_readout("skPitchRo", 220, 40, 26, "ffffb52e", "right verticallyCentred")
    deck.place(pitch_ro, P["Pitch"], 924, 200, 220, 40, name="pitchro")

    # knobs: SMOOTH, RANGE, CATCH, LEVEL (one Q-Link block)
    kx = [838 + i * 84 for i in range(4)]
    for x, pn in zip(kx, ["Smooth", "Strip Range", "Catch", "Level"]):
        deck.place(knob_deck, P[pn], x, 282, 80, 102, name=pn)
        prev.alpha_composite(knob_frames[32], (x, 282))

    # fader section
    on, off, on_i, off_i = key_pair("fader", 110, 52, "FADER", led=True, style="silver")
    deck.place(def_toggle("skFader", on, off, 110, 52), P["Fader"], 830, 432, 110, 52, name="fader")
    prev.alpha_composite(on_i, (830, 432))
    deck.place(def_display("skCutLed", cut_fn, 2, 150, 40), P["Cut LED"], 830, 488 - 2, 150, 40, name="cutled")
    # (the cut LED sits under the FADER key; nudge it right so both are visible)
    deck.items[-1]["bounds"] = bounds(948, 438, 150, 40)
    prev.alpha_composite(cut_frames[1], (948, 438))
    on, off, on_i, off_i = key_pair("rev", 110, 40, "REVERSE", led=True, style="silver")
    deck.place(def_toggle("skRev", on, off, 110, 40), P["Reverse"], 830, 486, 110, 40, name="reverse")
    prev.alpha_composite(off_i, (830, 486))
    deck.place(def_display("skStripLed", led_fn, 33, 170, 28), P["Strip LED"], 984, 494, 170, 28, name="stripled")
    prev.alpha_composite(led_frames[12], (984, 494))

    # preview texts (what the MPC draws as live labels)
    pd_ = ImageDraw.Draw(prev)
    pd_.text((844, 156), "AHH", font=font(F_TIT, 28), fill=AMBER, anchor="lm")
    pd_.text((1144, 220), "+0.00%", font=font(F_TIT, 26), fill=AMBER, anchor="rm")
    for x, v in zip(kx, ["3.0", "180 deg", "90", "-3.0"]):
        pd_.text((x + 40, 393), v, font=font(F_TIT, 15), fill=(42, 43, 46), anchor="mm")
    prev.convert("RGB").save(os.path.join(PREV, "preview_deck.png"))

    # ================= SETUP =================
    setup_bg = draw_setup_bg()
    setup = Tab("SETUP", save(setup_bg, "sk_bg_setup.png"))
    sprev = setup_bg.copy()
    for (x, y, pn) in [(50, 86, "Start Time"), (170, 86, "Brake Time"), (682, 86, "Strip Range"), (802, 86, "Smooth"),
                       (70, 486, "Crackle"), (190, 486, "Catch")]:
        setup.place(knob_def, P[pn], x, y, 80, 102, name=pn)
        sprev.alpha_composite(knob_frames[24], (x, y))

    def segments(tab, pv, pname, labels, x, y, w, h, gap=6, tag=None):
        for i, lab in enumerate(labels):
            nm = "%s%d" % (tag or pname.replace(" ", ""), i)
            on, off, on_i, off_i = key_pair(nm.lower(), w, h, lab, led=True, style="dark")
            tab.place(def_segment("skSeg_" + nm, on, off, w, h, i, len(labels)), P[pname], x + i * (w + gap), y, w, h, name=lab)
            pv.alpha_composite(on_i if i == 0 else off_i, (x + i * (w + gap), y))

    segments(setup, sprev, "Pitch Range", ["8%", "16%", "50%"], 300, 90, 92, 56)
    segments(setup, sprev, "Loop", ["1X", "LOOP"], 300, 200, 92, 56)
    segments(setup, sprev, "Strip Dir", ["NORMAL", "INVERT"], 932, 90, 140, 56)
    segments(setup, sprev, "Release", ["CENTER", "TIMEOUT"], 932, 200, 140, 56)
    segments(setup, sprev, "Cut Curve", ["SHARP", "MEDIUM", "SOFT"], 40, 394, 120, 56)
    segments(setup, sprev, "Pad Base", ["C1 36", "C#1 37"], 300, 490, 120, 56)
    on, off, on_i, off_i = key_pair("rescan", 150, 56, "RESCAN", led=True, style="dark")
    setup.place(def_toggle("skRescan", on, off, 150, 56), P["Rescan"], 446, 394, 150, 56, name="rescan")
    sprev.alpha_composite(off_i, (446, 394))
    # SCRATCH bar (big horizontal slider) + value
    hs_strip, hs_frames = draw_hslider(560, 64, 61)
    hs_fn = save(hs_strip, "sk_hslider_560x64_f61.png")
    setup.place(def_slider("skScratch", hs_fn, 61, 560, 64, "Horizontal", (0, 64, 560, 30)), P["Scratch"], 676, 370, 560, 96, name="scratch")
    sprev.alpha_composite(hs_frames[30], (676, 370))
    sprev.convert("RGB").save(os.path.join(PREV, "preview_setup.png"))

    # ================= INFO =================
    info_bg = draw_info_bg()
    info = Tab("INFO", save(info_bg, "sk_bg_info.png"))
    info_bg.convert("RGB").save(os.path.join(PREV, "preview_info.png"))

    tabs = [deck, setup, info]
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

    # Q-Links: Row banks (4 knobs per row from the top) so 4- and 8-knob MPCs get the important ones first
    def qmap(rows):
        m = {}
        order = [[13, 14, 15, 16], [9, 10, 11, 12], [5, 6, 7, 8], [1, 2, 3, 4]]
        for r, row in enumerate(order):
            for c, q in enumerate(row):
                name = rows[r][c] if r < len(rows) and c < len(rows[r]) else None
                m["Q-Link %d" % q] = P[name] if name else -1
        return m
    deck_rows = [["Smooth", "Strip Range", "Catch", "Level"], ["Pitch", "Sample", "Start Time", "Brake Time"], ["Scratch", "Crackle", None, None]]
    setup_rows = [["Start Time", "Brake Time", "Strip Range", "Smooth"], ["Crackle", "Catch", "Scratch", "Level"], ["Pitch Range", "Cut Curve", "Release", "Strip Dir"]]
    info_rows = [["Level", "Sample", "Pitch", "Smooth"]]
    ql = {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
          "Screen Mode Q-Links": {"version": 4, "map": [
              {"Tab": i + 1, "SubTab": 1, "Bank Direction": "Row", "Q-Links": qmap(rows)} for i, rows in enumerate([deck_rows, setup_rows, info_rows])]},
          "Program Mode Q-Links": qmap(deck_rows + [["Pitch Range", "Cut Curve", "Release", "Strip Dir"]])}
    json.dump(ql, open(os.path.join(OUT, "Q-Links.json"), "w"), indent=1)

    # licences of the fonts used in the pictures (pictures only; the MPC draws live text in its own fonts)
    print("skin written: %d component definitions, %d tabs" % (len(DEFS), len(tabs)))
    for fn in sorted(os.listdir(OUT)):
        if fn.endswith(".png"):
            im = Image.open(os.path.join(OUT, fn))
            print("  %-34s %4dx%-6d" % (fn, im.width, im.height))


if __name__ == "__main__":
    main()
