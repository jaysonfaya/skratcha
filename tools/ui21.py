#!/usr/bin/env python3
"""SKRATCHA 2.1 skin: three layouts on the DECK tab (STUDIO, BATTLE, PADS; the round light top left switches them),
a 4 x 4 pad map that is exactly the MPC pads, one set of controls for the active deck, a visible ADVANCED panel,
a two-list browser, the teacher with a scrolling pattern lane, and the MPC browser images.

    ui21.py <params.json> <out skins dir> <preview dir> <jf_logo.png> <fonts dir>
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui2 as U
from ui2 import (M, PB, O3, RD, _np, Image, ImageDraw, ImageFilter, font, save, F_BOLD, F_SEMI, F_MED, F_TIT, W, H,
                 OUT, PREV, P, define, act, comp, bounds, focus_comp, label_data, filmstrip, def_display, def_toggle,
                 def_segment, def_slider, def_readout, Tab, DEFS, cond, def_knob_named, def_text, STYLES, AMBER, GREEN,
                 _region_rect, CX, CY, R_REC, Z_MAT, PITCH_X, PITCH_Y, PITCH_W, PITCH_H)

RED = (255, 60, 40)
CYAN = (70, 210, 255)
WHITE = (235, 238, 242)
BATTLE_SCALE = 0.6
BDX = [0, 795]                       # BATTLE: x of deck A and deck B pictures
LESSONS = [p_["choices"] for p_ in M.params if p_["name"] == "Lesson"][0]
LESSON_DATA = None                   # filled from skr_helper.h


def lay_is(l):
    return "IndexedEnabling/%d/3/Parameter %d" % (l, P["Layout"])


def deck_is(d):
    return "IndexedEnabling/%d/2/Parameter %d" % (d, P["Deck"])


def mode_is(m):
    return "IndexedEnabling/%d/2/Parameter %d" % (m, P["Mode"])


def cstyle_is(s):
    return "IndexedEnabling/%d/3/Parameter %d" % (s, P["Style"])


def dstyle_is(d, s):
    return "IndexedEnabling/%d/3/Parameter %d" % (s, P["A Style" if d == 0 else "B Style"])


def lesson_is(i):
    return "IndexedEnabling/%d/%d/Parameter %d" % (i, len(LESSONS), P["Lesson"])


# ======================================================================================================
# pictures
# ======================================================================================================
def func_pad(w, h, num, label, on, col=AMBER, sub=None, big=False):
    """a rubber MPC-style pad: number top left, function in the middle, coloured glow when lit"""
    S = 3
    img = M._key_pbr(w, h, "", on, led=False, style="dark").resize((w * S, h * S), Image.LANCZOS)
    if on:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).rounded_rectangle([5 * S, 5 * S, (w - 5) * S, (h - 8) * S], 8 * S, outline=col + (255,), width=int(3 * S))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(4 * S)))
        img.alpha_composite(g)
        tint = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(tint).rounded_rectangle([8 * S, 8 * S, (w - 8) * S, (h - 11) * S], 6 * S, fill=col + (38,))
        img.alpha_composite(tint)
    d = ImageDraw.Draw(img)
    fn = (15 if big else 11) * S
    d.text((10 * S, 7 * S), str(num), font=font(F_BOLD, fn), fill=(col + (255,)) if on else (120, 122, 126, 255), anchor="la")
    if label:
        fl = (26 if big else (15 if len(label) <= 8 else 13)) * S
        d.text((w / 2 * S, (h / 2 + (2 if sub is None else -4)) * S), label, font=font(F_BOLD, fl),
               fill=(255, 255, 255, 255) if on else (205, 207, 212, 255), anchor="mm")
    if sub:
        d.text((w / 2 * S, (h / 2 + (22 if big else 13)) * S), sub, font=font(F_SEMI, (13 if big else 9) * S), fill=(150, 152, 156, 255), anchor="mm")
    return img.resize((w, h), Image.LANCZOS)


def strip_of(frames):
    w, h = frames[0].size
    st = Image.new("RGBA", (w, h * len(frames)), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        st.paste(fr, (0, k * h))
    return st


def glow_only(w, h, col):
    """frame 1: a lit outline drawn over a pad (for display-only pads and the CUE flash)"""
    S = 3
    off = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([5 * S, 5 * S, (w - 5) * S, (h - 8) * S], 8 * S, outline=col + (255,), width=int(3 * S))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(4 * S)))
    img.alpha_composite(g)
    ImageDraw.Draw(img).rounded_rectangle([8 * S, 8 * S, (w - 8) * S, (h - 11) * S], 6 * S, fill=col + (60,))
    return [off, img.resize((w, h), Image.LANCZOS)]


def arrow_key(w, h, kind, on):
    """UP / DOWN / PAGE UP / PAGE DOWN keys with drawn arrows (no font glyphs needed)"""
    S = 3
    img = M._key_pbr(w, h, "", on, led=False, style="dark").resize((w * S, h * S), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    cx, cy = w / 2 * S, (h / 2 - 2) * S
    up = kind in ("up", "pgup")
    n = 2 if kind.startswith("pg") else 1
    for k in range(n):
        off = (k - (n - 1) / 2) * 9 * S
        a = 9 * S
        if up:
            pts = [(cx - a, cy + off + a * 0.5), (cx + a, cy + off + a * 0.5), (cx, cy + off - a * 0.6)]
        else:
            pts = [(cx - a, cy + off - a * 0.5), (cx + a, cy + off - a * 0.5), (cx, cy + off + a * 0.6)]
        d.polygon(pts, fill=(AMBER + (255,)) if on else (215, 217, 222, 255))
    return img.resize((w, h), Image.LANCZOS)


def row_img(w, h, on):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, w - 2, h - 2], 6, fill=(255, 255, 255, 14 if not on else 40), outline=(255, 255, 255, 22))
    return img


def sel_bar_strip(w, row_h, pitch, rows=7):
    """highlight bar for a list: frame 0 none, frame k = row k"""
    H_ = (rows - 1) * pitch + row_h
    frames = []
    for k in range(rows + 1):
        img = Image.new("RGBA", (w, H_), (0, 0, 0, 0))
        if k > 0:
            y = (k - 1) * pitch
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([0, y, w - 1, y + row_h - 1], 7, fill=(255, 181, 46, 52), outline=(255, 181, 46, 190), width=2)
        frames.append(img)
    return strip_of(frames), frames


def lane_strip(lesson, w=860, h=120):
    """the pattern lane: the line is where your hand goes (up = forward), amber bars = sound on.
    Frame k = the bar has moved k/32 to the left; the white playhead stays at x = 130."""
    path, fader = lesson["path"], lesson["fader"]
    S = 2
    step_w = 100.0
    ph_x = 130.0
    frames = []
    for k in range(32):
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], 10 * S, fill=(8, 8, 9, 255), outline=(44, 45, 48, 255), width=2 * S)
        shift = k / 4.0 * step_w
        y_of = lambda v: (14 + (1 - (v + 1) / 2) * 62) * S
        pts = []
        for b in range(-1, 3):                      # bars before and after
            for st in range(8):
                x0 = ph_x + (b * 8 + st) * step_w - shift
                if x0 > w + step_w or x0 + step_w < -step_w:
                    continue
                a_, b_ = path[st], path[st + 1]
                for j in range(11):
                    f = j / 10
                    v = a_ + (b_ - a_) * (0.5 - 0.5 * math.cos(math.pi * f))
                    pts.append(((x0 + f * step_w) * S, y_of(v)))
                # sound bars (per half step)
                for hh in range(2):
                    fp = fader[st * 2 + hh]
                    xa, xb = (x0 + hh * step_w / 2 + 2) * S, (x0 + (hh + 1) * step_w / 2 - 2) * S
                    if fp == 1:
                        d.rounded_rectangle([xa, (h - 30) * S, xb, (h - 12) * S], 4 * S, fill=AMBER + (255,))
                    elif fp == 0:
                        d.rounded_rectangle([xa, (h - 24) * S, xb, (h - 18) * S], 3 * S, fill=(70, 70, 74, 255))
                    else:
                        d.rounded_rectangle([xa, (h - 25) * S, xb, (h - 17) * S], 3 * S, fill=(150, 110, 40, 150))
                # beat lines
                if st % 2 == 0:
                    lx = x0 * S
                    d.line([(lx, 8 * S), (lx, (h - 36) * S)], fill=(60, 62, 66, 255) if st else (120, 122, 128, 255), width=S)
        pts.sort(key=lambda p: p[0])
        if len(pts) > 1:
            d.line(pts, fill=GREEN + (255,), width=4 * S, joint="curve")
        # past part dimmed
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


def hit_strip(sz=56):
    frames = []
    for k in range(3):
        img = Image.new("RGBA", (sz * 3, sz * 3), (0, 0, 0, 0))
        col = [(40, 40, 44), GREEN, RED][k]
        RD.led_lens(ImageDraw.Draw(img), sz * 1.5, sz * 1.5, sz * 0.52, col, k > 0, img)
        d = ImageDraw.Draw(img)
        if k == 1:
            d.line([(sz * 1.22, sz * 1.52), (sz * 1.42, sz * 1.74), (sz * 1.82, sz * 1.28)], fill=(255, 255, 255, 255), width=int(sz * 0.12))
        elif k == 2:
            d.line([(sz * 1.25, sz * 1.25), (sz * 1.75, sz * 1.75)], fill=(255, 255, 255, 255), width=int(sz * 0.12))
            d.line([(sz * 1.75, sz * 1.25), (sz * 1.25, sz * 1.75)], fill=(255, 255, 255, 255), width=int(sz * 0.12))
        frames.append(img.resize((sz, sz), Image.LANCZOS))
    return strip_of(frames), frames


def adv_frame(w, h):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 7, w - 2, h - 2], 10, outline=AMBER + (220,), width=2)
    d.rounded_rectangle([w - 92, 0, w - 12, 14], 5, fill=AMBER + (255,))
    d.text((w - 52, 7), "ADVANCED", font=font(F_BOLD, 10), fill=(20, 16, 8, 255), anchor="mm")
    return img


def adv_plate(w, h):
    S = 2
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], 12 * S, fill=(14, 14, 15, 238), outline=AMBER + (230,), width=2 * S)
    d.rounded_rectangle([14 * S, -2 * S, 140 * S, 16 * S], 5 * S, fill=AMBER + (255,))
    d.text((77 * S, 7 * S), "ADVANCED", font=font(F_BOLD, 12 * S), fill=(20, 16, 8, 255), anchor="mm")
    return img.resize((w, h), Image.LANCZOS)


def flat_bg(boxes, lcds, items_fn, wells=()):
    return U.panel_page(boxes, lcds, items_fn, wells)


def icons(info_img):
    """MPC browser pictures: round track icon and the Sounds tile (Akai's 'browser_images' convention)"""
    os.makedirs(os.path.join(OUT, "browser_images"), exist_ok=True)
    lp = info_img.crop((640 - 240, 286 - 240, 640 + 240, 286 + 240))
    S = 4
    r = lp.resize((64 * S, 64 * S), Image.LANCZOS).convert("RGBA")
    m = Image.new("L", r.size, 0); ImageDraw.Draw(m).ellipse([0, 0, 64 * S - 1, 64 * S - 1], fill=255)
    r.putalpha(m)
    r.resize((64, 64), Image.LANCZOS).save(os.path.join(OUT, "browser_images", "trackedit.png"))
    tile = Image.new("RGB", (270 * S, 110 * S), (16, 16, 18))
    g = Image.new("RGB", tile.size, (0, 0, 0)); gd = ImageDraw.Draw(g)
    for k in range(110 * S):
        gd.line([(0, k), (270 * S, k)], fill=(int(30 - k / S * 0.12), int(26 - k / S * 0.1), int(22 - k / S * 0.08)))
    tile = g
    rec = lp.resize((100 * S, 100 * S), Image.LANCZOS).convert("RGBA")
    m2 = Image.new("L", rec.size, 0); ImageDraw.Draw(m2).ellipse([0, 0, 100 * S - 1, 100 * S - 1], fill=255)
    rec.putalpha(m2)
    tile.paste(rec, (6 * S, 5 * S), rec)
    d = ImageDraw.Draw(tile)
    d.text((116 * S, 36 * S), "SKRATCHA", font=font(F_BOLD, 30 * S), fill=(245, 240, 230), anchor="lm")
    d.text((118 * S, 64 * S), "SCRATCH TURNTABLES", font=font(F_SEMI, 11 * S), fill=AMBER, anchor="lm")
    d.text((118 * S, 84 * S), "JJ DA PLUG", font=font(F_SEMI, 11 * S), fill=(170, 172, 176), anchor="lm")
    tile.resize((270, 110), Image.LANCZOS).save(os.path.join(OUT, "browser_images", "soundsmode.png"))


def read_lessons():
    """path and fader patterns straight from the engine source, so the lane always matches the teacher"""
    import re
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "src", "skr_helper.h")).read() \
        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin", "src", "skr_helper.h")) \
        else open(os.environ["SKR_HELPER_H"]).read()
    out = []
    for m in re.finditer(r'\{"(\d [A-Z ]+)",\s*"[^"]*",\s*"[^"]*",\s*([\d.]+)f,\s*\{([^}]*)\},\s*\{([^}]*)\},\s*(true|false)\}', src):
        path = [float(v.strip().rstrip("f")) for v in m.group(3).split(",")]
        fad = [int(v) for v in m.group(4).split(",")]
        out.append({"name": m.group(1), "path": path, "fader": fad})
    assert len(out) == len(LESSONS), out
    return out


# ======================================================================================================
def main():
    lessons = read_lessons()
    U.CLEAR = save(Image.new("RGBA", (4, 8), (0, 0, 0, 0)), "sk_clear_f2.png")
    CLEAR = U.CLEAR
    knob_strip, knob_frames = M.draw_knob_strip(72, 64)
    knob_fn = save(knob_strip, "sk_knob72_f64.png")
    knobN = def_knob_named("skKnobN72", knob_fn, 64, 72)
    led_s, led_frames = M.draw_led_strip(170, 28, 33)
    led_fn = save(led_s, "sk_stripled_f33.png")
    clear_btn = define("skHidden", [act("Mouse Down", "Toggle Switch")],
                       [comp("Button", "Button", {"version": 2, "onImage": CLEAR, "offImage": CLEAR, "buttonId": 1, "numButtonsInGroup": 1,
                                                  "handleName": "Data", "gestureBehaviour": "Instant"}, bounds(0, 0, 72, 72))])

    keys = {}

    def key(name, w, h, label, led=True, style="dark"):
        k_ = "%s_%dx%d" % (name, w, h)
        if k_ not in keys:
            on = M.draw_key(w, h, label, True, led, None, style); off = M.draw_key(w, h, label, False, led, None, style)
            keys[k_] = (save(on, "sk_key_%s_on.png" % k_), save(off, "sk_key_%s_off.png" % k_), on, off)
        return keys[k_]

    def pvs(pv):
        return [] if pv is None else (pv if isinstance(pv, list) else [pv])

    def segments(tab, pv, pname, labels, x, y, w, h, gap=6, style="dark", conds=(), first_on=0, ids=None):
        for i, lab in enumerate(labels):
            nm = ("%s_%d" % (pname, i)).replace(" ", "").replace("/", "").replace("#", "s").lower()
            on, off, on_i, off_i = key(nm, w, h, lab, True, style)
            bid = ids[i] if ids else i
            n = len(labels) if not ids else max(ids) + 1
            tab.place(def_segment("skSeg_%s_%dx%d" % (nm, w, h), on, off, w, h, bid, n), P[pname], x + i * (w + gap), y, w, h, name=lab)
            if conds: cond(tab, *conds)
            for p_ in pvs(pv): p_.alpha_composite(on_i if i == first_on else off_i, (x + i * (w + gap), y))

    def toggle(tab, pv, pname, name, label, x, y, w, h, style="dark", conds=(), on_prev=False):
        on, off, on_i, off_i = key(name, w, h, label, True, style)
        tab.place(def_toggle("skTg_%s_%dx%d" % (name, w, h), on, off, w, h), P[pname], x, y, w, h, name=name)
        if conds: cond(tab, *conds)
        for p_ in pvs(pv): p_.alpha_composite(on_i if on_prev else off_i, (x, y))

    def disp(tab, key_, fn, frames, pname, x, y, w, h, conds=()):
        tab.place(def_display(key_, fn, frames, w, h), P[pname], x, y, w, h, name=key_)
        if conds: cond(tab, *conds)

    def knobs(tab, pv, names, x0, y, step, conds=(), frame=40):
        for i, n_ in enumerate(names):
            tab.place(knobN, P[n_], x0 + i * step, y, 72, 112, name="k_%s" % n_)
            if conds: cond(tab, *conds)
            for p_ in pvs(pv):
                p_.alpha_composite(knob_frames[frame], (x0 + i * step, y + 20))
                ImageDraw.Draw(p_).text((x0 + i * step + 36, y + 9), n_, font=font(F_TIT, 13), fill=(216, 218, 222), anchor="mm")

    # ---------------- the 4 x 4 pad map (same as the MPC pads) ----------------
    padimg_cache = {}

    def padmap(tab, pv, x0, y0, pw, ph, cx, cy, conds, big=False, names_prev=None):
        """top row 13-16: DECK A, DECK B, REVERSE, SLIP; row 9-12: CUT, HOLD, CUE, START; rows: slots 5-8, 1-4"""
        def imgs(tag, num, label, col, sub=None):
            k_ = (tag, pw, ph)
            if k_ not in padimg_cache:
                on = func_pad(pw, ph, num, label, True, col, sub, big); off = func_pad(pw, ph, num, label, False, col, sub, big)
                padimg_cache[k_] = (save(on, "sk_pad_%s_%dx%d_on.png" % (tag, pw, ph)), save(off, "sk_pad_%s_%dx%d_off.png" % (tag, pw, ph)), on, off)
            return padimg_cache[k_]
        X = lambda c: x0 + c * cx
        Y = lambda r: y0 + r * cy
        sub = None
        # row 0
        for c, (tag, num, lab, col, pname, kind, bid) in enumerate([
                ("decka", 13, "DECK A", AMBER, "Deck", "seg", 0), ("deckb", 14, "DECK B", AMBER, "Deck", "seg", 1),
                ("rev", 15, "REVERSE", AMBER, "Reverse", "tog", 1), ("slip", 16, "SLIP", CYAN, "Slip", "tog", 1)]):
            on, off, on_i, off_i = imgs(tag, num, lab, col)
            if kind == "seg":
                tab.place(def_segment("skPad_%s_%dx%d" % (tag, pw, ph), on, off, pw, ph, bid, 2), P[pname], X(c), Y(0), pw, ph, name=tag)
            else:
                tab.place(def_toggle("skPad_%s_%dx%d" % (tag, pw, ph), on, off, pw, ph), P[pname], X(c), Y(0), pw, ph, name=tag)
            cond(tab, *conds)
            for p_ in pvs(pv): p_.alpha_composite(on_i if tag == "decka" else off_i, (X(c), Y(0)))
        # row 1: CUT, HOLD (lit while the pad is held), CUE (tap = jump, lit flash), START
        for c, (tag, num, lab, col, sb) in enumerate([("cut", 9, "CUT", RED, "PAD HALTEN"), ("hold", 10, "HOLD", RED, "HAND DRAUF"),
                                                      ("cue", 11, "CUE", WHITE, "HOLD+CUE = SETZEN")]):
            on, off, on_i, off_i = imgs(tag, num, lab, col, sb)
            if tag == "cue":
                tab.place(def_toggle("skPad_cue_%dx%d" % (pw, ph), off, off, pw, ph), P["Cue Tap"], X(c), Y(1), pw, ph, name="cue")
                cond(tab, *conds)
                gl = glow_only(pw, ph, WHITE)
                disp(tab, "skPadCueLit_%dx%d" % (pw, ph), save(strip_of(gl), "sk_padglow_white_%dx%d_f2.png" % (pw, ph)), 2, "Pad Cue", X(c), Y(1), pw, ph, conds)
            else:
                stp = strip_of([off_i, on_i])
                disp(tab, "skPad_%s_%dx%d" % (tag, pw, ph), save(stp, "sk_pad_%s_%dx%d_f2.png" % (tag, pw, ph)), 2, "Pad Cut" if tag == "cut" else "Pad Hold",
                     X(c), Y(1), pw, ph, conds)
            for p_ in pvs(pv): p_.alpha_composite(off_i, (X(c), Y(1)))
        on, off, on_i, off_i = imgs("start", 12, "START", GREEN, "STOP")
        tab.place(def_toggle("skPad_start_%dx%d" % (pw, ph), on, off, pw, ph), P["Start/Stop"], X(3), Y(1), pw, ph, name="start")
        cond(tab, *conds)
        for p_ in pvs(pv): p_.alpha_composite(on_i, (X(3), Y(1)))
        # rows 2 + 3: samples
        names = names_prev or ["AHH", "OOH WAH", "STAB", "TONE 1K", "BREAK 92", "BASS DROP", "FRESH", "HORN"]
        for s in range(8):
            c, r = s % 4, (2 if s >= 4 else 3)
            on, off, on_i, off_i = imgs("slot%d" % (s + 1), s + 1, "", AMBER)
            tab.place(def_segment("skPad_slot%d_%dx%d" % (s, pw, ph), on, off, pw, ph, s, 8), P["Slot"], X(c), Y(r), pw, ph, name="slot%d" % s)
            cond(tab, *conds)
            fs = 22 if big else 13
            tab.place(def_text("skSlotName_%dx%d" % (pw, ph), pw - 8, 26, fs, "ffe6e7ea", "horizontallyCentred verticallyCentred"),
                      P["A Slot %d Name" % (s + 1)], X(c) + 4, Y(r) + ph // 2 - (10 if not big else 6), pw - 8, 26, name="sn%d" % s)
            cond(tab, *conds)
            for p_ in pvs(pv):
                p_.alpha_composite(on_i if s == 0 else off_i, (X(c), Y(r)))
                ImageDraw.Draw(p_).text((X(c) + pw / 2, Y(r) + ph / 2 + (3 if not big else 7)), names[s], font=font(F_TIT, fs), fill=(230, 231, 234), anchor="mm")

    # ================= DECK =================
    print("rendering decks ...")
    decks = {}
    for st in STYLES:
        img, maps, hits, rgb = U.draw_deck(st["plinth"])
        decks[st["plinth"]] = (img, maps, hits, rgb)
        print("  ", st["name"])
    img0, maps0, hits0, rgb0 = decks["silver"]
    M._DECK.update(maps=maps0, hx=hits0[0], hy=hits0[1], hz=hits0[2], rgb=rgb0)
    strobe_strip, strobe_frames = M.draw_strobe_frames()
    srx, sry, srw, srh = M._DECK["strobe_rect"]
    lab_strip, lab_frames, (lrx, lry, lrw, lrh) = U.draw_label_frames(maps0, hits0)
    arm, (ax, ay, aw, ah) = M.draw_tonearm()

    deck = Tab("DECK", save(Image.new("RGB", (W, H), (14, 14, 15)), "sk_bg_black.png"))
    L0, L1, L2 = lay_is(0), lay_is(1), lay_is(2)
    # ---------------- STUDIO ----------------
    bg_fns = [save(decks[st["plinth"]][0], "sk_bg_deck_%d.png" % i) for i, st in enumerate(STYLES)]
    for si in range(3):
        deck.image("bg%d" % si, bg_fns[si], 0, 0, W, H); cond(deck, L0, cstyle_is(si))
    prevS = decks["silver"][0].copy()
    disp(deck, "skStrobe", save(strobe_strip, "sk_strobe_f8.png"), 8, "Strobe", srx, sry, srw, srh, (L0,))
    prevS.alpha_composite(strobe_frames[0], (srx, sry))
    disp(deck, "skLabel", save(lab_strip, "sk_label_f48.png"), 48, "Angle", lrx, lry, lrw, lrh, (L0,))
    prevS.alpha_composite(lab_frames[3], (lrx, lry))
    deck.image("Tonearm", save(arm, "sk_tonearm.png"), ax, ay, aw, ah); cond(deck, L0)
    prevS.alpha_composite(arm, (ax, ay))
    badge = [save(U.deck_badge(Lt, None), "sk_badge_%s.png" % Lt.lower()) for Lt in "AB"]
    for d in range(2):
        deck.image("badge%d" % d, badge[d], 116, 20, 96, 44); cond(deck, L0, deck_is(d))
    prevS.alpha_composite(Image.open(os.path.join(OUT, badge[0])), (116, 20))
    jrx, jry, jrw, jrh = _region_rect(CX, CY, R_REC, Z_MAT)
    jdef = define("skJog", [act("Mouse Down", "Q-Link")], [comp("Jog", "Knob", filmstrip(CLEAR, 2, "AbsoluteRotaryKnob"), bounds(0, 0, jrw, jrh))])
    deck.place(jdef, P["Platter"], jrx, jry, jrw, jrh, name="jog"); cond(deck, L0)
    toggle(deck, prevS, "Start/Stop", "start", "START·STOP", 16, 548, 132, 58, "silver", (L0,))
    segments(deck, prevS, "Speed", ["33", "45"], 520, 556, 66, 52, gap=6, style="silver", conds=(L0,))
    pf_strip, pf_frames = M.draw_pitch_fader(PITCH_W, PITCH_H, 41)
    deck.place(def_slider("skPitch", save(pf_strip, "sk_pitch_f41.png"), 41, PITCH_W, PITCH_H, "Vertical"), P["Pitch"], PITCH_X, PITCH_Y, PITCH_W, PITCH_H, name="pitch")
    cond(deck, L0)
    prevS.alpha_composite(pf_frames[20], (PITCH_X, PITCH_Y))
    deck.place(clear_btn, P["Layout Tap"], 20, 18, 72, 72, name="laytap0"); cond(deck, L0)
    deck.place(def_text("skRecName", 300, 44, 22, "ffffb52e"), P["Record"], 832, 14, 300, 44, name="rec"); cond(deck, L0)
    deck.place(def_text("skPitchRo", 128, 44, 20, "ffffb52e", "right verticallyCentred"), P["Pitch"], 1132, 14, 128, 44, name="pro"); cond(deck, L0)
    padmap(deck, prevS, 822, 68, 106, 62, 112, 69, (L0,))
    knobs(deck, prevS, ["Strip Range", "Fader Curve", "Deck Volume", "Level"], 830, 356, 112, (L0, mode_is(0)))
    knobs(deck, None, ["Smooth", "Catch", "Cut Lag", "Crackle"], 830, 356, 112, (L0, mode_is(1)))
    deck.image("advframe", save(adv_frame(456, 128), "sk_advframe.png"), 816, 342, 456, 128); cond(deck, L0, mode_is(1))
    cf_strip, cf_frames = U.crossfader_strip(340, 72, 61)
    cf_fn = save(cf_strip, "sk_xfader_f61.png")
    deck.place(def_slider("skXFader", cf_fn, 61, 340, 72, "Horizontal"), P["Crossfader"], 860, 476, 340, 72, name="xfader"); cond(deck, L0)
    prevS.alpha_composite(cf_frames[8], (860, 476))
    cl_strip, cl_frames = U.led_strip(34, 34, (255, 60, 30))
    cl_fn = save(cl_strip, "sk_cutled_f2.png")
    disp(deck, "skCutLed", cl_fn, 2, "A Cut LED", 813, 494, 34, 34, (L0,))
    disp(deck, "skCutLed", cl_fn, 2, "B Cut LED", 1235, 494, 34, 34, (L0,))
    prevS.alpha_composite(cl_frames[1], (813, 494)); prevS.alpha_composite(cl_frames[0], (1235, 494))
    segments(deck, prevS, "Cut Mode", ["CUT ZU", "CUT AUF"], 822, 554, 86, 36, gap=4, conds=(L0,))
    cv_strip, cv_frames = U.curve_strip(112, 36, 21)
    cv_fn = save(cv_strip, "sk_curve_f21.png")
    disp(deck, "skCurve", cv_fn, 21, "Fader Curve", 1004, 554, 112, 36, (L0,))
    prevS.alpha_composite(cv_frames[17], (1004, 554))
    toggle(deck, prevS, "Mode", "advanced", "ADVANCED", 1124, 554, 144, 36, "dark", (L0,))
    disp(deck, "skStripLed", led_fn, 33, "Strip LED", 822, 596, 170, 28, (L0,))
    deck.place(def_text("skTip", 262, 26, 13, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 1002, 596, 262, 26, name="tip"); cond(deck, L0)
    # ADVANCED plate on the plinth: everything extra in reach
    deck.image("advplate", save(adv_plate(356, 104), "sk_advplate.png"), 156, 518, 356, 104); cond(deck, L0, mode_is(1))
    for i, (pn, nm, lab) in enumerate([("Hamster", "hamster", "HAMSTER"), ("After Scratch", "runon", "WEITERLAUF"), ("Set Cue Tap", "setcue", "CUE SETZEN"),
                                       ("Fire", "fireplay", "FIRE = PLAY"), ("Loop", "loop", "LOOP"), ("Deck On", "deckon", "DECK ON")]):
        x_, y_ = 166 + (i % 3) * 114, 538 + (i // 3) * 42
        if pn == "Set Cue Tap":
            on, off, _, _ = key(nm, 106, 36, lab, True)
            deck.place(def_toggle("skTg_setcue", off, off, 106, 36), P[pn], x_, y_, 106, 36, name=nm)
        else:
            on, off, _, _ = key(nm, 106, 36, lab, True)
            deck.place(def_toggle("skTg_%s_106x36" % nm, on, off, 106, 36), P[pn], x_, y_, 106, 36, name=nm)
        cond(deck, L0, mode_is(1))
    d_ = ImageDraw.Draw(prevS)
    d_.text((842, 37), "A 1  AHH", font=font(F_TIT, 22), fill=AMBER, anchor="lm")
    d_.text((1258, 37), "+0.00%", font=font(F_TIT, 20), fill=AMBER, anchor="rm")
    for i, v in enumerate(["180 deg", "SHARP 85", "0.0 dB", "-3.0 dB"]):
        d_.text((830 + i * 112 + 36, 458), v, font=font(F_TIT, 14), fill=(244, 241, 234), anchor="mm")
    d_.text((1133, 609), "LEKTION WAEHLEN, DANN START", font=font(F_TIT, 13), fill=AMBER, anchor="mm")
    prevS.convert("RGB").save(os.path.join(PREV, "preview_studio.png"))
    # the same with ADVANCED on (preview only)
    prevA = prevS.copy()
    prevA.alpha_composite(Image.open(os.path.join(OUT, "sk_advframe.png")), (816, 342))
    prevA.alpha_composite(Image.open(os.path.join(OUT, "sk_advplate.png")), (156, 518))
    for i, lab in enumerate(["HAMSTER", "WEITERLAUF", "CUE SETZEN", "FIRE = PLAY", "LOOP", "DECK ON"]):
        k_ = [k for k in keys if k.endswith("106x36") and keys[k][2] is not None]
        prevA.alpha_composite(M.draw_key(106, 36, lab, lab in ("WEITERLAUF", "FIRE = PLAY", "DECK ON"), True, None, "dark"), (166 + (i % 3) * 114, 538 + (i // 3) * 42))
    prevA.alpha_composite(keys["advanced_144x36"][2], (1124, 554))
    prevA.convert("RGB").save(os.path.join(PREV, "preview_studio_advanced.png"))

    # ---------------- BATTLE: both decks side by side ----------------
    sc = BATTLE_SCALE
    dw, dh = int(808 * sc), int(628 * sc)
    def battle_bg_items(S):
        f12 = font(F_SEMI, 12 * S)
        return [(640 * S, 26 * S, "SKRATCHA BATTLE", font(F_BOLD, 22 * S), "mm", 3 * S),
                (640 * S, 254 * S, "CROSSFADER", f12, "mm", 2 * S), (500 * S, 312 * S, "A", font(F_BOLD, 20 * S), "mm", 0),
                (780 * S, 312 * S, "B", font(F_BOLD, 20 * S), "mm", 0)]
    bbg = flat_bg([((489, 6, 791, 376), ""), ((6, 382, 1274, 622), "")], [(498, 48, 782, 86), (498, 92, 782, 130)], battle_bg_items)
    bd = ImageDraw.Draw(bbg)
    bd.rounded_rectangle([506, 282, 786, 290], 4, fill=(4, 4, 4))
    for k in range(11):
        bd.line([(506 + k * 28, 266), (506 + k * 28, 272)], fill=(220, 222, 226), width=1)
    deck.image("bbg", save(bbg, "sk_bg_battle.png"), 0, 0, W, H); cond(deck, L1)
    prevB = bbg.copy()
    small_decks = []
    for i, st in enumerate(STYLES):
        im = decks[st["plinth"]][0].crop((0, 0, 808, 628)).copy()
        im.alpha_composite(arm, (ax, ay))
        im = im.resize((dw, dh), Image.LANCZOS)
        small_decks.append(save(im, "sk_deck_small_%d.png" % i))
        if i < 2: prevB.alpha_composite(im, (BDX[i], 0))
    for d in range(2):
        for si in range(3):
            deck.image("sd%d%d" % (d, si), small_decks[si], BDX[d], 0, dw, dh); cond(deck, L1, dstyle_is(d, si))
    lab_s = [f.resize((int(lrw * sc), int(lrh * sc)), Image.LANCZOS) for f in lab_frames]
    str_s = [f.resize((int(srw * sc), int(srh * sc)), Image.LANCZOS) for f in strobe_frames]
    lab_fn, str_fn = save(strip_of(lab_s), "sk_label_small_f48.png"), save(strip_of(str_s), "sk_strobe_small_f8.png")
    glow = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
    gl2 = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
    ImageDraw.Draw(gl2).rounded_rectangle([3, 3, dw - 4, dh - 4], 12, outline=AMBER + (255,), width=4)
    glow.alpha_composite(gl2.filter(ImageFilter.GaussianBlur(5))); glow.alpha_composite(gl2)
    glow_fn = save(glow, "sk_deck_glow.png")
    jr = _region_rect(CX, CY, R_REC, Z_MAT)
    for d in range(2):
        Ln = "AB"[d]
        ox = BDX[d]
        disp(deck, "skStrobeS", str_fn, 8, "%s Strobe" % Ln, ox + int(srx * sc), int(sry * sc), str_s[0].width, str_s[0].height, (L1,))
        disp(deck, "skLabelS", lab_fn, 48, "%s Angle" % Ln, ox + int(lrx * sc), int(lry * sc), lab_s[0].width, lab_s[0].height, (L1,))
        prevB.alpha_composite(str_s[0], (ox + int(srx * sc), int(sry * sc))); prevB.alpha_composite(lab_s[3 + 20 * d], (ox + int(lrx * sc), int(lry * sc)))
        deck.image("glow%d" % d, glow_fn, ox, 0, dw, dh); cond(deck, L1, deck_is(d))
        if d == 0: prevB.alpha_composite(glow, (ox, 0))
        jw, jh = int(jr[2] * sc), int(jr[3] * sc)
        jd2 = define("skJogS", [act("Mouse Down", "Q-Link")], [comp("Jog", "Knob", filmstrip(CLEAR, 2, "AbsoluteRotaryKnob"), bounds(0, 0, jw, jh))])
        deck.place(jd2, P["Platter"], ox + int(jr[0] * sc), int(jr[1] * sc), jw, jh, name="jogS%d" % d); cond(deck, L1, deck_is(d))
        toggle(deck, prevB, "%s Start/Stop" % Ln, "startS", "START", ox + 10, 329, 80, 35, "silver", (L1,))
        segments(deck, prevB, "%s Speed" % Ln, ["33", "45"], ox + 312, 333, 40, 31, gap=4, style="silver", conds=(L1,))
        pfs = [f.resize((int(PITCH_W * sc), int(PITCH_H * sc)), Image.LANCZOS) for f in pf_frames]
        deck.place(def_slider("skPitchS", save(strip_of(pfs), "sk_pitch_small_f41.png"), 41, pfs[0].width, pfs[0].height, "Vertical"),
                   P["%s Pitch" % Ln], ox + int(PITCH_X * sc), int(PITCH_Y * sc), pfs[0].width, pfs[0].height, name="pitchS%d" % d)
        cond(deck, L1)
        prevB.alpha_composite(pfs[20], (ox + int(PITCH_X * sc), int(PITCH_Y * sc)))
        deck.place(def_text("skRecNameS", 276, 38, 16, "ffffb52e"), P["%s Record" % Ln], 502, 48 + 44 * d, 276, 38, name="recS%d" % d); cond(deck, L1)
        disp(deck, "skCutLed", cl_fn, 2, "%s Cut LED" % Ln, 488 + d * 270, 296 - 17 + 40, 34, 34, (L1,))
        deck.place(clear_btn, P["Layout Tap"], ox + 8, 8, 52, 52, name="laytap1%d" % d); cond(deck, L1)
    deck.place(def_slider("skXFader", cf_fn, 61, 340, 72, "Horizontal"), P["Crossfader"], 470, 250, 340, 72, name="xfaderB"); cond(deck, L1)
    prevB.alpha_composite(cf_frames[30], (470, 250))
    knobs(deck, prevB, ["Fader Curve", "Level"], 540, 138, 140, (L1,))
    segments(deck, prevB, "Cut Mode", ["CUT ZU", "CUT AUF"], 498, 334, 138, 34, gap=6, conds=(L1,))
    padmap(deck, prevB, 402, 386, 112, 56, 120, 60, (L1,))
    disp(deck, "skStripLed", led_fn, 33, "Strip LED", 24, 398, 170, 28, (L1,))
    deck.place(def_text("skTipB", 360, 30, 13, "ffffb52e"), P["Tip"], 24, 432, 360, 30, name="tipB"); cond(deck, L1)
    knobs(deck, prevB, ["Strip Range", "Smooth"], 40, 476, 140, (L1,))
    knobs(deck, prevB, ["A Volume", "B Volume"], 950, 476, 140, (L1,))
    toggle(deck, prevB, "Hamster", "hamster", "HAMSTER", 906, 398, 170, 44, "dark", (L1,))
    toggle(deck, prevB, "After Scratch", "runon", "WEITERLAUF", 1086, 398, 170, 44, "dark", (L1,), on_prev=True)
    pb_ = ImageDraw.Draw(prevB)
    pb_.text((506, 67), "A 1  AHH", font=font(F_TIT, 16), fill=AMBER, anchor="lm"); pb_.text((506, 111), "B 1  BREAK 92", font=font(F_TIT, 16), fill=AMBER, anchor="lm")
    prevB.convert("RGB").save(os.path.join(PREV, "preview_battle.png"))

    # ---------------- PADS: big pads for performing ----------------
    def pads_items(S):
        return [(46 * S, 112 * S, "", font(F_BOLD, 14 * S), "la", 0), (1016 * S, 156 * S, "CROSSFADER", font(F_SEMI, 12 * S), "mm", 2 * S),
                (796 * S, 196 * S, "A", font(F_BOLD, 22 * S), "mm", 0), (1238 * S, 196 * S, "B", font(F_BOLD, 22 * S), "mm", 0),
                (110 * S, 52 * S, "SKRATCHA  PADS", font(F_BOLD, 22 * S), "la", 3 * S)]
    pbg = flat_bg([((10, 10, 760, 618), ""), ((772, 10, 1270, 618), "")], [(782, 22, 1260, 112), (782, 566, 1260, 606)], pads_items)
    pd2 = ImageDraw.Draw(pbg)
    pd2.ellipse([28, 24, 84, 80], fill=(190, 192, 196), outline=(90, 92, 96), width=2)
    pd2.ellipse([48, 44, 64, 60], fill=(150, 152, 156))
    pd2.rounded_rectangle([876, 206, 1156, 214], 4, fill=(4, 4, 4))
    deck.image("pbg", save(pbg, "sk_bg_pads.png"), 0, 0, W, H); cond(deck, L2)
    prevP = pbg.copy()
    deck.place(clear_btn, P["Layout Tap"], 20, 16, 72, 72, name="laytap2"); cond(deck, L2)
    padmap(deck, prevP, 26, 96, 174, 122, 182, 130, (L2,), big=True)
    deck.place(def_text("skRecNameP", 330, 46, 26, "ffffb52e"), P["Record"], 794, 26, 330, 46, name="recP"); cond(deck, L2)
    deck.place(def_text("skPitchP", 120, 40, 20, "ffffb52e", "right verticallyCentred"), P["Pitch"], 1130, 28, 120, 40, name="proP"); cond(deck, L2)
    deck.place(def_text("skPhaseP", 450, 30, 15, "ffd8dade"), P["Tip"], 794, 74, 450, 34, name="tipP"); cond(deck, L2)
    deck.place(def_slider("skXFader", cf_fn, 61, 340, 72, "Horizontal"), P["Crossfader"], 840, 174, 340, 72, name="xfaderP"); cond(deck, L2)
    prevP.alpha_composite(cf_frames[8], (840, 174))
    disp(deck, "skCutLed", cl_fn, 2, "A Cut LED", 779, 213, 34, 34, (L2,))
    disp(deck, "skCutLed", cl_fn, 2, "B Cut LED", 1221, 213, 34, 34, (L2,))
    knobs(deck, prevP, ["Strip Range", "Fader Curve", "Deck Volume", "Level"], 790, 262, 120, (L2, mode_is(0)))
    knobs(deck, None, ["Smooth", "Catch", "Cut Lag", "Crackle"], 790, 262, 120, (L2, mode_is(1)))
    deck.image("advframeP", save(adv_frame(476, 120), "sk_advframe_p.png"), 782, 256, 476, 120); cond(deck, L2, mode_is(1))
    segments(deck, prevP, "Cut Mode", ["CUT ZU", "CUT AUF"], 790, 392, 112, 44, gap=6, conds=(L2,))
    toggle(deck, prevP, "Mode", "advanced", "ADVANCED", 1030, 392, 220, 44, "dark", (L2,))
    segments(deck, prevP, "Speed", ["33", "45"], 790, 448, 112, 44, gap=6, conds=(L2,))
    toggle(deck, prevP, "Hamster", "hamster", "HAMSTER", 1030, 448, 220, 44, "dark", (L2,))
    disp(deck, "skStripLed", led_fn, 33, "Strip LED", 790, 512, 170, 28, (L2,))
    disp(deck, "skCurveP", cv_fn, 21, "Fader Curve", 1000, 508, 112, 36, (L2,))
    deck.place(def_text("skTipP", 470, 36, 15, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 786, 568, 470, 36, name="tip2"); cond(deck, L2)
    pp_ = ImageDraw.Draw(prevP)
    pp_.text((806, 49), "A 1  AHH", font=font(F_TIT, 26), fill=AMBER, anchor="lm"); pp_.text((1248, 48), "+0.00%", font=font(F_TIT, 20), fill=AMBER, anchor="rm")
    pp_.text((1021, 586), "LEKTION WAEHLEN, DANN START", font=font(F_TIT, 15), fill=AMBER, anchor="mm")
    prevP.convert("RGB").save(os.path.join(PREV, "preview_pads.png"))

    # ================= BROWSER =================
    def br_items(S):
        f13 = font(F_SEMI, 13 * S)
        return [(1088 * S, 46 * S, "ZIEL-DECK", f13, "mm", S), (1088 * S, 238 * S, "LADEN IN SLOT  (TIPPEN = LADEN)", f13, "mm", S),
                (930 * S, 588 * S, "EIGENE WAVS: LAUFWERKE ODER PLUGIN-ORDNER/My Samples", font(F_MED, 12 * S), "la", 0)]
    br_bg = flat_bg([((14, 14, 446, 614), "ORDNER"), ((458, 14, 900, 614), "DATEI  (TIPPEN = AUSWAEHLEN)"), ((912, 14, 1266, 614), "")],
                    [(28, 52, 432, 512), (472, 52, 886, 512), (926, 540, 1252, 574)], br_items)
    brow = Tab("BROWSER", save(br_bg, "sk_bg_browser.png"))
    bpv = br_bg.copy()
    row_on, row_off = save(row_img(396, 60, True), "sk_row_on.png"), save(row_img(396, 60, False), "sk_row_off.png")
    bar_s, bar_f = sel_bar_strip(400, 60, 64)
    bar_fn = save(bar_s, "sk_selbar_f8.png")
    for li, (x0, pick, rows_p, sel_p, step_p, w_) in enumerate([(32, "Folder Pick", "Folder Row %d", "Folder Sel Row", "Folder Step", 396),
                                                                 (476, "File Pick", "File Row %d", "File Sel Row", "File Step", 406)]):
        disp(brow, "skSelBar%d" % li, bar_fn, 8, sel_p, x0 - 2, 56, 400, 6 * 64 + 60)
        for r in range(7):
            y = 56 + r * 64
            brow.place(def_segment("skRow%d_%d" % (li, r), row_on, row_off, 396, 60, r + 1, 8), P[pick], x0, y, 396, 60, name="row%d%d" % (li, r))
            brow.place(def_text("skRowTxt", 380, 60, 19, "ffe8e9ec"), P[rows_p % (r + 1)], x0 + 10, y, 380, 60, name="rt%d%d" % (li, r))
        for k, kind in enumerate(["up", "down", "pgup", "pgdn"]):
            on = save(arrow_key(92, 56, kind, True), "sk_arrow_%s_on.png" % kind); off = save(arrow_key(92, 56, kind, False), "sk_arrow_%s_off.png" % kind)
            brow.place(def_segment("skArrow%d_%s" % (li, kind), on, off, 92, 56, k + 1, 5), P[step_p], x0 + k * 101, 530, 92, 56, name="ar%d%s" % (li, kind))
            bpv.alpha_composite(arrow_key(92, 56, kind, False), (x0 + k * 101, 530))
    bpv.alpha_composite(bar_f[3], (30, 56)); bpv.alpha_composite(bar_f[1], (474, 56))
    bd_ = ImageDraw.Draw(bpv)
    for r, t in enumerate(["SKRATCHA SAMPLES", "MY SAMPLES", "> MPC-SSD", "  BREAKS", "  VOCALS", "  SCRATCH TOOLS", ""]):
        bd_.text((44, 56 + r * 64 + 30), t, font=font(F_TIT, 19), fill=(232, 233, 236), anchor="lm")
    for r, t in enumerate(["> AHH", "OOH WAH", "STAB", "TONE 1K", "BREAK 92", "BASS DROP", "FRESH"]):
        bd_.text((488, 56 + r * 64 + 30), t, font=font(F_TIT, 19), fill=(232, 233, 236), anchor="lm")
    padmap_dummy = None
    segments(brow, bpv, "Deck", ["DECK A", "DECK B"], 932, 60, 154, 52, gap=8)
    toggle(brow, bpv, "Preview", "preview", "VORHOEREN", 932, 128, 154, 52)
    toggle(brow, bpv, "Auto Preview", "autoprev", "AUTO-HOEREN", 1094, 128, 154, 52, on_prev=True)
    toggle(brow, bpv, "Rescan", "rescan", "NEU SUCHEN", 932, 186, 316, 40)
    for s in range(8):
        c, r = s % 4, (0 if s >= 4 else 1)
        x, y = 928 + c * 82, 252 + r * 84
        on = func_pad(78, 78, s + 1, "", True); off = func_pad(78, 78, s + 1, "", False)
        brow.place(def_segment("skLoad%d" % s, save(on, "sk_load%d_on.png" % s), save(off, "sk_load%d_off.png" % s), 78, 78, s + 1, 9), P["Load To Slot"], x, y, 78, 78, name="ld%d" % s)
        brow.place(def_text("skLoadName", 74, 30, 11, "ffe6e7ea", "horizontallyCentred verticallyCentred"), P["A Slot %d Name" % (s + 1)], x + 2, y + 34, 74, 30, name="ldn%d" % s)
        bpv.alpha_composite(off, (x, y))
    brow.place(def_text("skBrInfo", 316, 34, 14, "ffd8dade", "horizontallyCentred verticallyCentred"), P["Browser Info"], 930, 540, 316, 34, name="info")
    bd_.text((1088, 557), "DATEI 1/8  ORDNER 1/6", font=font(F_TIT, 14), fill=(216, 218, 222), anchor="mm")
    bpv.convert("RGB").save(os.path.join(PREV, "preview_browser.png"))

    # ================= LERNEN =================
    def le_items(S):
        f13 = font(F_SEMI, 13 * S)
        return [(52 * S, 30 * S, "LEKTION", f13, "la", S),
                (380 * S, 316 * S, "LEHRER", font(F_SEMI, 11 * S), "la", S), (380 * S, 360 * S, "DU", font(F_SEMI, 11 * S), "la", S),
                (480 * S, 516 * S, "TON SOLL", font(F_SEMI, 10 * S), "mm", S), (548 * S, 516 * S, "TON IST", font(F_SEMI, 10 * S), "mm", S),
                (418 * S, 516 * S, "SCHRITT", font(F_SEMI, 10 * S), "mm", S),
                (40 * S, 540 * S, "1. DEMO: ZUHOEREN", font(F_MED, 13 * S), "la", 0), (40 * S, 562 * S, "2. UEBEN: 1 TAKT ZAEHLEN, DANN DU", font(F_MED, 13 * S), "la", 0),
                (40 * S, 584 * S, "3. FOLGE DER GRUENEN LINIE", font(F_MED, 13 * S), "la", 0)]
    le_bg = flat_bg([((14, 14, 356, 614), ""), ((366, 14, 1266, 614), "")], [(376, 22, 1256, 76), (376, 82, 1256, 176), (376, 522, 1256, 562)], le_items)
    lern = Tab("LERNEN", save(le_bg, "sk_bg_lernen.png"))
    lpv = le_bg.copy()
    for i, nm in enumerate(LESSONS):
        on, off, on_i, off_i = key("lesson%d" % i, 300, 64, nm, True, "dark")
        lern.place(def_segment("skLesson%d" % i, on, off, 300, 64, i, len(LESSONS)), P["Lesson"], 34, 50 + i * 78, 300, 64, name="les%d" % i)
        lpv.alpha_composite(on_i if i == 0 else off_i, (34, 50 + i * 78))
    lern.place(def_text("skPhase", 860, 54, 28, "ffffffff", "horizontallyCentred verticallyCentred"), P["Phase"], 386, 22, 860, 54, name="phase")
    lern.place(def_text("skLT1", 850, 44, 22, "ffffb52e"), P["Lesson Text 1"], 392, 86, 850, 44, name="t1")
    lern.place(def_text("skLT2", 850, 44, 22, "ffffb52e"), P["Lesson Text 2"], 392, 130, 850, 44, name="t2")
    for i, les in enumerate(lessons):
        ls, lf = lane_strip(les, 860, 120)
        disp(lern, "skLane%d" % i, save(ls, "sk_lane%d_f32.png" % i), 32, "Lane", 386, 186, 860, 120, (lesson_is(i),))
        if i == 0: lpv.alpha_composite(lf[6], (386, 186))
    gs, gf = U.teach_strip(810, 40, GREEN, "")
    ys, yf = U.teach_strip(810, 40, AMBER, "")
    disp(lern, "skGhost", save(gs, "sk_ghost_f33.png"), 33, "Ghost", 436, 312, 810, 40)
    disp(lern, "skYou", save(ys, "sk_you_f33.png"), 33, "Strip LED", 436, 356, 810, 40)
    bs, bf = U.beat_strip(860, 30)
    disp(lern, "skBeat", save(bs, "sk_beat_f9.png"), 9, "Beat", 386, 404, 860, 30)
    hs, hf = hit_strip(64)
    disp(lern, "skHit", save(hs, "sk_hit_f3.png"), 3, "Step Hit", 386, 442, 64, 64)
    fl, flf = U.led_strip(48, 48, GREEN)
    al, alf = U.led_strip(48, 48, AMBER)
    disp(lern, "skFadeT", save(fl, "sk_led_green_f2.png"), 2, "Fader Target", 456, 450, 48, 48)
    disp(lern, "skFadeA", save(al, "sk_led_amber_f2.png"), 2, "Cut LED", 524, 450, 48, 48)
    ss_, sf = U.stars_strip(210, 54)
    disp(lern, "skStars", save(ss_, "sk_stars_f4.png"), 4, "Stars", 600, 448, 210, 54)
    lern.place(def_text("skScore", 420, 40, 17, "ffd8dade", "right verticallyCentred"), P["Score"], 826, 454, 420, 40, name="score")
    lern.place(def_text("skMsg", 860, 40, 22, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 386, 522, 860, 40, name="msg")
    toggle(lern, lpv, "Lesson Demo", "demo", "DEMO", 386, 568, 170, 44, "silver")
    toggle(lern, lpv, "Lesson Start", "lstart", "UEBEN", 566, 568, 170, 44, "silver")
    toggle(lern, lpv, "Click", "click", "KLICK", 746, 568, 120, 44, "dark", on_prev=True)
    lern.place(U.def_drag_text("skBpm", 170, 44, 20, "ffffb52e", "Vertical", "horizontallyCentred verticallyCentred"), P["Lesson BPM"], 876, 568, 170, 44, name="bpm")
    segments(lern, lpv, "Deck", ["A", "B"], 1056, 568, 92, 44, gap=6)
    for img_, pos in [(gf[9], (436, 312)), (yf[12], (436, 356)), (bf[3], (386, 404)), (hf[1], (386, 442)), (flf[1], (456, 450)), (alf[1], (524, 450)), (sf[2], (600, 448))]:
        lpv.alpha_composite(img_, pos)
    ld_ = ImageDraw.Draw(lpv)
    ld_.text((816, 49), "JETZT DU!", font=font(F_TIT, 28), fill=(255, 255, 255), anchor="mm")
    ld_.text((400, 108), "VOR UND ZURUECK IM TAKT", font=font(F_TIT, 22), fill=AMBER, anchor="lm")
    ld_.text((400, 152), "FOLGE DEM GRUENEN PUNKT", font=font(F_TIT, 22), fill=AMBER, anchor="lm")
    ld_.text((1244, 474), "TREFFER 88%   BESTE **-", font=font(F_TIT, 17), fill=(216, 218, 222), anchor="rm")
    ld_.text((816, 542), "SUPER! GENAU IM TAKT", font=font(F_TIT, 22), fill=AMBER, anchor="mm")
    ld_.text((961, 590), "80 BPM", font=font(F_TIT, 20), fill=AMBER, anchor="mm")
    lpv.convert("RGB").save(os.path.join(PREV, "preview_lernen.png"))

    # ================= SETUP =================
    def su_items(S):
        f13 = font(F_SEMI, 13 * S)
        return [(40 * S, 58 * S, "TURNTABLE-STIL DES AKTIVEN DECKS", f13, "la", S), (40 * S, 154 * S, "LAYOUT (ODER KREIS OBEN LINKS TIPPEN)", f13, "la", S),
                (40 * S, 238 * S, "PAD 1-8 =", f13, "la", S), (300 * S, 238 * S, "PAD 1 =", f13, "la", S),
                (672 * S, 58 * S, "STRIP RICHTUNG", f13, "la", S), (672 * S, 154 * S, "LOSLASSEN WENN", f13, "la", S),
                (40 * S, 362 * S, "CUT SPEED (PAD 9)", f13, "la", S), (40 * S, 456 * S, "NACH DEM SCRATCH", f13, "la", S),
                (672 * S, 362 * S, "PITCH RANGE", f13, "la", S), (672 * S, 456 * S, "PLATTE", f13, "la", S)]
    su_bg = flat_bg([((20, 16, 640, 310), "DECK  ·  LAYOUT"), ((652, 16, 1260, 310), "TOUCH STRIP"),
                     ((20, 320, 640, 612), "FADER  ·  SOUND"), ((652, 320, 1260, 612), "MOTOR (AKTIVES DECK)")], [], su_items)
    setup = Tab("SETUP", save(su_bg, "sk_bg_setup.png"))
    spv = su_bg.copy()
    segments(setup, spv, "Style", [s_["name"] for s_ in STYLES], 40, 74, 186, 54, gap=8)
    segments(setup, spv, "Layout", ["STUDIO", "BATTLE", "PADS"], 40, 170, 186, 54, gap=8)
    segments(setup, spv, "Fire", ["CUE", "PLAY"], 40, 254, 110, 46, first_on=1)
    segments(setup, spv, "Pad Base", ["C1 36", "C#1 37"], 300, 254, 120, 46)
    toggle(setup, spv, "Slip", "slipS", "SLIP", 480, 254, 140, 46)
    segments(setup, spv, "Strip Dir", ["NORMAL", "INVERT"], 672, 74, 140, 50)
    segments(setup, spv, "Release", ["CENTER", "TIMEOUT"], 672, 170, 140, 50)
    knobs(setup, spv, ["Strip Range", "Smooth", "Catch"], 980, 100, 96)
    segments(setup, spv, "Cut Speed", ["SHARP", "MEDIUM", "SOFT"], 40, 378, 120, 50)
    segments(setup, spv, "After Scratch", ["STOP", "WEITERLAUF"], 40, 472, 140, 50, first_on=1)
    toggle(setup, spv, "Hamster", "hamster", "HAMSTER", 440, 378, 150, 50)
    knobs(setup, spv, ["Crackle", "Cut Lag", "Fader Curve"], 340, 470, 100)
    segments(setup, spv, "Pitch Range", ["8%", "16%", "50%"], 672, 378, 92, 50)
    segments(setup, spv, "Loop", ["1X", "LOOP"], 672, 472, 92, 50)
    toggle(setup, spv, "Reverse", "rev", "REVERSE", 868, 472, 116, 50)
    toggle(setup, spv, "Deck On", "deckon", "DECK ON", 868, 548, 116, 50, on_prev=True)
    knobs(setup, spv, ["Start Time", "Brake Time"], 1010, 400, 120)
    spv.convert("RGB").save(os.path.join(PREV, "preview_setup.png"))

    # ================= INFO =================
    info_bg = U.draw_info_bg()
    info = Tab("INFO", save(info_bg, "sk_bg_info.png"))
    info_bg.convert("RGB").save(os.path.join(PREV, "preview_info.png"))
    icons(info_bg)

    tabs = [deck, brow, lern, setup, info]
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

    def qmap(rows):
        m = {}
        order = [[13, 14, 15, 16], [9, 10, 11, 12], [5, 6, 7, 8], [1, 2, 3, 4]]
        for r, row in enumerate(order):
            for c, q in enumerate(row):
                name = rows[r][c] if r < len(rows) and c < len(rows[r]) else None
                m["Q-Link %d" % q] = P[name] if name else -1
        return m
    deck_rows = [["Crossfader", "Fader Curve", "Strip Range", "Level"], ["Pitch", "Deck Volume", "A Volume", "B Volume"],
                 ["Smooth", "Catch", "Cut Lag", "Crackle"], ["Scratch", "Lesson BPM", "A Pitch", "B Pitch"]]
    br_rows = [["Folder", "File", "Crossfader", "Level"]]
    le_rows = [["Crossfader", "Lesson BPM", "Strip Range", "Level"], ["Smooth", "Fader Curve", None, None]]
    su_rows = [["Strip Range", "Smooth", "Catch", "Crackle"], ["Start Time", "Brake Time", "Cut Lag", "Fader Curve"], ["Scratch", "Level", None, None]]
    info_rows = [["Crossfader", "Level", "A Pitch", "B Pitch"]]
    ql = {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
          "Screen Mode Q-Links": {"version": 4, "map": [
              {"Tab": i + 1, "SubTab": 1, "Bank Direction": "Row", "Q-Links": qmap(rows)} for i, rows in enumerate([deck_rows, br_rows, le_rows, su_rows, info_rows])]},
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


if __name__ == "__main__":
    main()
