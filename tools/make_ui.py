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
    prev.alpha_composite(label_frames[9], (CX - LABEL_TILE // 2, CY - LABEL_TILE // 2))

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
        deck.place(knob_def, P[pn], x, 282, 80, 102, name=pn)
        prev.alpha_composite(knob_frames[32], (x, 282))

    # fader section
    on, off, on_i, off_i = key_pair("fader", 110, 52, "FADER", led=True, style="dark")
    deck.place(def_toggle("skFader", on, off, 110, 52), P["Fader"], 830, 432, 110, 52, name="fader")
    prev.alpha_composite(on_i, (830, 432))
    deck.place(def_display("skCutLed", cut_fn, 2, 150, 40), P["Cut LED"], 830, 488 - 2, 150, 40, name="cutled")
    # (the cut LED sits under the FADER key; nudge it right so both are visible)
    deck.items[-1]["bounds"] = bounds(948, 438, 150, 40)
    prev.alpha_composite(cut_frames[1], (948, 438))
    on, off, on_i, off_i = key_pair("rev", 110, 40, "REVERSE", led=True, style="dark")
    deck.place(def_toggle("skRev", on, off, 110, 40), P["Reverse"], 830, 486, 110, 40, name="reverse")
    prev.alpha_composite(off_i, (830, 486))
    deck.place(def_display("skStripLed", led_fn, 33, 170, 28), P["Strip LED"], 984, 494, 170, 28, name="stripled")
    prev.alpha_composite(led_frames[12], (984, 494))

    # preview texts (what the MPC draws as live labels)
    pd_ = ImageDraw.Draw(prev)
    pd_.text((844, 156), "AHH", font=font(F_TIT, 28), fill=AMBER, anchor="lm")
    pd_.text((1144, 220), "+0.00%", font=font(F_TIT, 26), fill=AMBER, anchor="rm")
    for x, v in zip(kx, ["3.0", "180 deg", "90", "-3.0"]):
        pd_.text((x + 40, 393), v, font=font(F_TIT, 15), fill=(244, 241, 234), anchor="mm")
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
