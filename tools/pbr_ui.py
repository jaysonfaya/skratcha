
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
    Hm += PB.brushed(w, h, 1, length=140, strength=1.1) + PB.fbm(w, h, 2, 3, 6.0) * 0.10
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
    lathe = PB.rings(r, 5, period=0.9 * S, jitter=0.5, amp=0.18 * S)
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
    grooves = PB.rings(r, 13, period=1.25 * S, jitter=0.9, amp=1.0) * groove_amp
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

    rgb, _ = PB.shade(A, Hm, Rm, Mm, normal_strength=1.0, shadows=True, ao=True, shadow_steps=34, ao_radius=14 * S, ao_strength=0.05)
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
    Hm += PB.brushed(w, h, 61, length=140, strength=1.1) + PB.fbm(w, h, 62, 3, 6.0) * 0.10
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
    grooves = PB.rings(r, 35, period=1.25 * S, jitter=0.9, amp=1.0) * (1 - gap) * (1 - runout) * 0.28 * S
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
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=20, ao_radius=12 * S, ao_strength=0.05)
    return down(PB.to_image(rgb))

