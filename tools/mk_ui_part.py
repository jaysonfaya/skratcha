
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

PRINT_COL = PB.srgb_to_lin([0.36, 0.42, 0.52])      # grey-blue print on the felt
FELT_COL = PB.srgb_to_lin([0.075, 0.085, 0.115])


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
    dial_txt = _text_mask(w, h, [(84 * S, (492 + i * 9) * S, s, font(F_SEMI, 9 * S), "la", 0) for i, s in enumerate(["+6.4", "+3.3", "0  %", "-3.3"])])
    _put(A, Hm, Rm, Mm, dial_txt, INK_DARK, None, 0.6, 0.0)

    # ---------------- tone-arm base: large ring housing, recessed well, anti-skate dial, lift lever, arm rest
    bx, by = 708 * S, 124 * S
    br = _np.sqrt((x - bx) ** 2 + (y - by) ** 2)
    ringo = PB.disc(br, 94 * S)
    _put(A, Hm, Rm, Mm, ringo, SILVER_BRIGHT, None, 0.12, 1.0)
    Hm[:] = Hm * (1 - ringo) + ringo * (PB.dome(br - 94 * S, 9 * S, 6 * S) + PB.radial_value(br, 23, 1.0, 0.05 * S))
    well = PB.disc(br, 80 * S)
    _put(A, Hm, Rm, Mm, well, SILVER, 3 * S, 0.22, 1.0)
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
        tint = _np.dstack([0.75 + 3.2 * lamp, 0.75 + 0.1 * lamp, 0.78 + 0.05 * lamp])
        rgb = rgb * tint
        frames.append(down(PB.to_image(rgb, dots), (2 * R_STROBE_OUT, 2 * R_STROBE_OUT)))
    strip = Image.new("RGBA", (2 * R_STROBE_OUT, 2 * R_STROBE_OUT * STROBE_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * 2 * R_STROBE_OUT))
    return strip, frames

