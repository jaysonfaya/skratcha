
# ======================================================================================================
# 3D DECK (oblique view, height-field ray marching) – overrides the flat versions above
# ======================================================================================================
import ortho3d as O3

Z_PLATTER = 26        # layout px: platter top (lip)
Z_MAT = 21            # felt top
Z_KNOB = 18
Z_KEY = 9
Z_ARM = 40
SIDE_ROWS = [5.5, 10.5, 15.5, 20.5]    # z of the strobe dot rows on the platter side
_DECK = {}


def _wgrid(S):
    Ww, Hw = W * S, int(math.ceil(H / O3.COS * S)) + 2
    x, y = PB.grid(Ww, Hw)
    return Ww, Hw, x, y


def _deck_maps():
    S = SS
    Ww, Hw, x, y = _wgrid(S)
    A, Hm, Rm, Mm = _maps(Ww, Hw, SILVER, 0.0, 0.28, 1.0)
    Hm += PB.brushed(Ww, Hw, 1, length=400, strength=0.14) + PB.white(Ww, Hw, 2) * 0.012 + PB.fbm(Ww, Hw, 2, 4, 160.0) * 0.25
    Rm += PB.fbm(Ww, Hw, 3, 3, 60.0) * 0.03
    EM = _np.zeros((Hw, Ww, 3), _np.float32)            # emission (added after shading)
    Yw = lambda ly: O3.Y(ly) * S                          # layout y -> world px

    # ---------------- platter (cylinder): lip, sloped strobe band (plain), step, felt slipmat
    pcx, pcy = CX * S, Yw(CY)
    px, py = x - pcx, y - pcy
    r = _np.sqrt(px * px + py * py)
    plat = PB.disc(r, R_PLATTER * S, 0.7)
    lip = PB.ring(r, R_STROBE_OUT * S, R_PLATTER * S)
    band = PB.ring(r, R_STROBE_IN * S, R_STROBE_OUT * S)
    step = PB.ring(r, R_MAT * S, R_STROBE_IN * S)
    mat = PB.disc(r, R_REC * S)
    gapm = PB.ring(r, R_REC * S, R_MAT * S)
    lathe = PB.radial_value(r, 5, scale=0.7, amp=0.05 * S, smooth=2)
    top = Z_PLATTER * S
    _put(A, Hm, Rm, Mm, lip, SILVER_BRIGHT, None, 0.08, 1.0)
    _put(A, Hm, Rm, Mm, band, PB.srgb_to_lin([0.60, 0.61, 0.63]), None, 0.22, 1.0)
    _put(A, Hm, Rm, Mm, step, SILVER_BRIGHT, None, 0.10, 1.0)
    _put(A, Hm, Rm, Mm, gapm, PB.srgb_to_lin([0.02, 0.02, 0.022]), None, 0.8, 0.0)
    felt = _felt_height(Ww, Hw, 7, S)
    _put(A, Hm, Rm, Mm, mat, FELT_COL, None, 0.95, 0.0)
    A[:] = A * (1 + (mat * PB.blur(PB.white(Ww, Hw, 9), 0.7 * S) * 0.10)[..., None])
    pr = PB.ring(r, (R_REC - 26) * S, (R_REC - 24) * S, 0.8)
    _put(A, Hm, Rm, Mm, pr, PRINT_COL * 0.8, None, 0.9, 0.0)
    hp = _np.zeros_like(r)
    hp += lip * (top + lathe + PB.dome(r - R_PLATTER * S, 0, 1) * 0 - 2.5 * S * (1 - PB.smoothstep(-5 * S, 0, r - R_PLATTER * S)) * 0)
    # rounded outer edge of the lip
    edge = PB.smoothstep(R_PLATTER * S - 4 * S, R_PLATTER * S, r)
    hp = lip * (top - 3 * S * edge ** 2 + lathe)
    hp += band * (top - 4 * S + (r - R_STROBE_IN * S) / ((R_STROBE_OUT - R_STROBE_IN) * S) * 4 * S + lathe * 0.5)
    hp += step * (top - 4.5 * S + lathe)
    hp += gapm * (Z_MAT * S - 2 * S)
    hp += mat * (Z_MAT * S + felt)
    Hm[:] = Hm * (1 - plat) + hp * plat + (1 - plat) * Hm * 0
    Hm[:] = _np.where(plat > 0.5, hp, Hm)

    # ---------------- target light (top left)
    tx, ty = 56 * S, Yw(54)
    tr = _np.sqrt((x - tx) ** 2 + (y - ty) ** 2)
    tl = PB.disc(tr, 34 * S)
    _put(A, Hm, Rm, Mm, tl, SILVER_BRIGHT, None, 0.05, 1.0)
    Hm[:] = Hm * (1 - tl) + tl * (PB.dome(tr - 34 * S, 10 * S, 6 * S) + PB.radial_value(tr, 41, 1.2, 0.05 * S))
    tc = PB.disc(tr, 6 * S)
    Hm[:] = Hm - tc * 2 * S

    # ---------------- black knurled dial bottom left, strobe glow
    kx, ky = 50 * S, Yw(470)
    kr = _np.sqrt((x - kx) ** 2 + (y - ky) ** 2)
    kth = _np.arctan2(y - ky, x - kx)
    kd = PB.disc(kr, 22 * S)
    _put(A, Hm, Rm, Mm, kd, PB.srgb_to_lin([0.04, 0.04, 0.045]), None, 0.4, 0.2)
    Hm[:] = Hm * (1 - kd) + kd * (PB.dome(kr - 22 * S, 12 * S, 4 * S) + _np.cos(kth * 70) * 0.5 * S * PB.ring(kr, 16 * S, 22 * S))
    km = (_np.abs(x - kx) < 1.2 * S) & (y < ky - 6 * S) & (y > ky - 18 * S)
    _put(A, Hm, Rm, Mm, km.astype(_np.float32), PAINT_WHITE, None, 0.5, 0.0)
    dial_txt = _text_mask(Ww, Hw, [((20 + i * 15) * S, Yw(508), s, font(F_SEMI, 9 * S), "la", 0) for i, s in enumerate(["-3", "0", "+3", "%"])])
    _put(A, Hm, Rm, Mm, dial_txt, INK_DARK, None, 0.6, 0.0)

    # ---------------- tone-arm base ring + well + anti-skate dial + lift lever + rest
    bx, by = 708 * S, Yw(124)
    br = _np.sqrt((x - bx) ** 2 + (y - by) ** 2)
    ringo = PB.disc(br, 94 * S)
    _put(A, Hm, Rm, Mm, ringo, SILVER_BRIGHT, None, 0.12, 1.0)
    Hm[:] = Hm * (1 - ringo) + ringo * (PB.dome(br - 94 * S, 12 * S, 6 * S) + PB.radial_value(br, 23, 1.0, 0.05 * S))
    well = PB.disc(br, 80 * S)
    _put(A, Hm, Rm, Mm, well, PB.srgb_to_lin([0.16, 0.16, 0.17]), None, 0.30, 0.8)
    Hm[:] = Hm * (1 - well) + well * (4 * S)
    ax_, ay_ = 768 * S, Yw(92)
    ar_ = _np.sqrt((x - ax_) ** 2 + (y - ay_) ** 2)
    ath = _np.arctan2(y - ay_, x - ax_)
    ad = PB.disc(ar_, 20 * S)
    _put(A, Hm, Rm, Mm, ad, PB.srgb_to_lin([0.035, 0.035, 0.04]), None, 0.35, 0.2)
    Hm[:] = Hm * (1 - ad) + ad * (16 * S + PB.dome(ar_ - 20 * S, 4 * S, 3 * S) + _np.cos(ath * 64) * 0.4 * S * PB.ring(ar_, 16 * S, 20 * S))
    for k in range(7):
        a = math.radians(-210 + k * 40)
        tick = (_np.abs((x - ax_) * math.sin(a) - (y - ay_) * math.cos(a)) < 0.8 * S) & PB.ring(ar_, 9 * S, 14 * S).astype(bool) & (((x - ax_) * math.cos(a) + (y - ay_) * math.sin(a)) > 0)
        _put(A, Hm, Rm, Mm, tick.astype(_np.float32), PAINT_WHITE, None, 0.5, 0.0)
    lev = _np.zeros((Hw, Ww), _np.uint8)
    _cv2.line(lev, (int(770 * S), int(Yw(176))), (int(792 * S), int(Yw(214))), 255, int(7 * S))
    levm = PB.blur(lev.astype(_np.float32) / 255, 0.8)
    _put(A, Hm, Rm, Mm, levm, PB.srgb_to_lin([0.03, 0.03, 0.035]), None, 0.35, 0.1)
    Hm[:] = _np.maximum(Hm, levm * 16 * S)
    ar2 = PB.rrect(x, y, 744 * S, Yw(300), 764 * S, Yw(340), 7 * S)
    arest = 1 - PB.smoothstep(-1, 1, ar2)
    _put(A, Hm, Rm, Mm, arest, PB.srgb_to_lin([0.03, 0.03, 0.032]), None, 0.6, 0.0)
    Hm[:] = Hm * (1 - arest) + arest * PB.dome(ar2, 22 * S, 5 * S)

    # ---------------- control area (engraved print, LCD glass), pitch slot
    sep = ((_np.abs(x - 800 * S) < 0.8 * S) & (y > Yw(24)) & (y < Yw(604))).astype(_np.float32)
    Hm[:] = Hm - sep * 0.8 * S
    for (a0, b0, a1, b1) in [(830, 124, 1154, 188), (830, 196, 1154, 246), (948, 438, 1098, 478), (984, 494, 1154, 522)]:
        ld = PB.rrect(x, y, a0 * S, Yw(b0), a1 * S, Yw(b1), 8 * S)
        lcd = 1 - PB.smoothstep(-1, 1, ld)
        bez = (1 - PB.smoothstep(-1, 1, ld - 3 * S)) - lcd
        _put(A, Hm, Rm, Mm, bez, PB.srgb_to_lin([0.05, 0.05, 0.055]), None, 0.4, 0.3)
        Hm[:] = Hm + bez * 1.0 * S
        _put(A, Hm, Rm, Mm, lcd, PB.srgb_to_lin([0.012, 0.011, 0.008]), -1 * S, 0.04, 0.0)
    for yl in (110, 404, 532):
        lm = ((_np.abs(y - Yw(yl)) < 0.8 * S) & (x > (808 + 22) * S) & (x < (1176 - 22) * S)).astype(_np.float32)
        Hm[:] = Hm - lm * 0.6 * S
    ink_items = [
        ((808 + 24) * S, Yw(26), "SKRATCHA", font(F_BOLD, 52 * S), "la", 3 * S),
        ((808 + 26) * S, Yw(84), "DIRECT DRIVE SCRATCH TURNTABLE", font(F_SEMI, 14 * S), "la", S),
        ((808 + 22) * S, Yw(412), "FADER", font(F_SEMI, 13 * S), "la", S),
        ((808 + 176) * S, Yw(478), "TOUCH STRIP", font(F_SEMI, 12 * S), "la", S),
        ((808 + 22) * S, Yw(540), "PADS  1 START/STOP · 2 CUT · 3 HOLD · 4 CUE", font(F_MED, 15 * S), "la", 0),
        ((808 + 22) * S, Yw(562), "5 SET CUE · 6 REV · 7 33/45 · 8 FADER", font(F_MED, 15 * S), "la", 0),
        ((808 + 22) * S, Yw(584), "9–16 HOT CUES  (SET CUE + PAD = STORE)", font(F_MED, 15 * S), "la", 0)]
    for i, lab in enumerate(["SMOOTH", "RANGE", "CATCH", "LEVEL"]):
        ink_items.append(((838 + i * 84 + 40) * S, Yw(262), lab, font(F_SEMI, 13 * S), "mm", S))
    tm = _text_mask(Ww, Hw, ink_items)
    # print in world space, but stretched in y so it reads the same after the tilt squeezes it
    tm = _cv2.resize(_cv2.resize(tm, (Ww, int(Hw * O3.COS))), (Ww, Hw))
    _put(A, Hm, Rm, Mm, tm, INK_DARK, None, 0.6, 0.0)
    Hm[:] = Hm - tm * 0.4 * S
    fx0, fy0, fx1, fy1 = 1188 * S, Yw(106), 1264 * S, Yw(536)
    slot = ((x > fx0 + 31 * S) & (x < fx0 + 41 * S) & (y > fy0 + 26 * S) & (y < fy1 - 26 * S)).astype(_np.float32)
    slot = PB.blur(slot, 0.7 * S)
    _put(A, Hm, Rm, Mm, slot, PB.srgb_to_lin([0.01, 0.01, 0.01]), -6 * S, 0.9, 0.0)
    scale = []
    for k, lab in [(8, "+8"), (6, "6"), (4, "4"), (2, "2"), (0, "0"), (-2, "2"), (-4, "4"), (-6, "6"), (-8, "-8")]:
        yk = 122 + 20 + (8 - k) / 16 * (520 - 120 - 40)
        scale.append(((1188 + 4) * S, Yw(yk + 4), lab, font(F_SEMI, 10 * S), "ls", 0))
        tick = ((_np.abs(y - Yw(yk)) < 0.7 * S) & (x > (1188 + 18) * S) & (x < (1188 + 26) * S)).astype(_np.float32)
        _put(A, Hm, Rm, Mm, tick, INK_DARK, None, 0.6, 0.0)
    scale += [((1188 + 1264) / 2 * S, Yw(554), "PITCH ADJ.", font(F_SEMI, 12 * S), "mm", 0)]
    sc = _text_mask(Ww, Hw, scale)
    _put(A, Hm, Rm, Mm, sc, INK_DARK, None, 0.6, 0.0)

    an = (lip + step) * 0.8 + band * 0.4 + ringo * (1 - well) * 0.7
    maps = {"albedo": A, "H": Hm, "rough": Rm, "metal": Mm, "aniso": an, "center": (pcx, pcy)}
    return O3.prepare(maps, shadow_steps=40, ao_radius=14 * S, ao_strength=0.05)


def _side_fn(maps, phase=None, S=2):
    """platter side wall: polished aluminium with 4 rows of strobe dots (phase None -> plain, else dots)"""
    pcx, pcy = maps["center"]
    def fn(A, R, M, gx, gy, hx, hy, hz):
        dx, dy = hx - pcx, hy - pcy
        r = _np.sqrt(dx * dx + dy * dy)
        th = _np.arctan2(dy, dx)
        side = (r > (R_PLATTER - 4) * S) & (r < (R_PLATTER + 3) * S) & (hz < (Z_PLATTER - 2.5) * S) & (dy > -R_PLATTER * S * 0.2)
        cth, sth = _np.cos(th), _np.sin(th)
        K = 30.0
        bump_x = _np.zeros_like(r); bump_y = _np.zeros_like(r)
        alb = _np.ones(A.shape, _np.float32) * SILVER_BRIGHT
        rough = _np.full(R.shape, 0.12, _np.float32)
        if phase is not None:
            dots = _np.zeros_like(r)
            for i, zr in enumerate(SIDE_ROWS):
                a = (th + _np.pi / 2) * STROBE_DOTS / (2 * _np.pi) - phase - (0.5 if i % 2 else 0.0)
                fr_ = a - _np.round(a)
                du = fr_ * 2 * _np.pi * R_PLATTER * S / STROBE_DOTS
                dz = hz - zr * S
                ds = _np.sqrt(du * du + dz * dz)
                d1 = PB.disc(ds, 1.6 * S, 0.6)
                dots = _np.maximum(dots, d1)
            lamp = _np.clip(_np.cos(th - math.atan2(O3.Y(470) * S - pcy, 50 * S - pcx)), 0, 1) ** 3
            dcol = _np.dstack([0.9 + 3.0 * lamp, 0.85 + 0.1 * lamp, 0.85 + 0.05 * lamp])
            alb = alb * (1 - dots[..., None]) + dcol * dots[..., None]
            rough = rough * (1 - dots) + 0.05 * dots
        ngx = -cth * K; ngy = -sth * K
        A = _np.where(side[..., None], alb, A)
        R = _np.where(side, rough, R)
        M = _np.where(side, 1.0, M)
        gx = _np.where(side, ngx, gx)
        gy = _np.where(side, ngy, gy)
        return A, R, M, gx, gy
    return fn


def draw_deck_bg():
    S = SS
    maps = _deck_maps()
    pcx, pcy = maps["center"]
    rgb, _, (hx, hy, hz) = O3.render(maps, W * S, H * S, 0, 0, aniso=(maps["aniso"], pcx, pcy, 1.0), side=_side_fn(maps, None, S))
    _DECK.update(maps=maps, hx=hx, hy=hy, hz=hz, rgb=rgb)
    img = PB.to_image(rgb)
    _glow(img, 96 * S, int(O3.screen_v(O3.Y(452) * S, 0)), 70 * S, (255, 40, 20), 85)
    return down(img)


def _region_rect(cx_l, cy_l, rad, z):
    """screen rectangle (layout px) of a horizontal disc of radius rad at layout centre (cx, cy) and height z"""
    vc = cy_l - z * O3.SIN
    return int(cx_l - rad), int(math.floor(vc - rad * O3.COS)), int(2 * rad), int(math.ceil(2 * rad * O3.COS)) + 1


def draw_label_frames():
    """the big JF print on the felt (turns with the platter), re-shaded on the fixed 3D hits of the deck"""
    S = SS
    maps = _DECK["maps"]
    hx, hy, hz = _DECK["hx"], _DECK["hy"], _DECK["hz"]
    pcx, pcy = maps["center"]
    rx, ry, rw, rh = _region_rect(CX, CY, R_LABEL, Z_MAT)
    sl = (slice(ry * S, (ry + rh) * S), slice(rx * S, (rx + rw) * S))
    shx, shy, shz = hx[sl], hy[sl], hz[sl]
    lg = Image.open(LOGO).convert("RGBA"); lg = lg.crop(lg.getbbox())
    lh = int(276 * S); lw = int(lg.width * lh / lg.height)
    lgm = _np.asarray(lg.resize((lw, lh), Image.LANCZOS).split()[3]).astype(_np.float32) / 255
    speck = PB.blur(PB.white(lw, lh, 91), 0.7 * S)
    dx, dy = shx - pcx, shy - pcy
    on_mat = (_np.sqrt(dx * dx + dy * dy) < R_LABEL * S) & (shz > (Z_MAT - 3) * S)
    base_rgb = _DECK["rgb"][sl]
    frames = []
    for k in range(LABEL_FRAMES):
        ang = math.radians(k * 360.0 / (LABEL_FRAMES - 1))
        ca, sa = math.cos(-ang), math.sin(-ang)
        # mat coordinates of each hit, rotated back into the logo's frame
        ux = dx * ca - dy * sa + lw / 2 + 6 * S
        uy = dx * sa + dy * ca + lh / 2
        lm = O3.remap(lgm, ux, uy, _cv2.BORDER_CONSTANT) * on_mat
        sp = O3.remap(speck, ux, uy, _cv2.BORDER_CONSTANT)
        cover = _np.clip(lm * (0.82 + 0.25 * sp), 0, 1)
        A = _np.ones(shx.shape + (3,), _np.float32) * PRINT_COL * (1 + 0.12 * sp)[..., None]
        sub = {"albedo": A, "rough": _np.full(shx.shape, 0.92, _np.float32), "metal": _np.zeros(shx.shape, _np.float32),
               "gx": maps["gx"], "gy": maps["gy"]}
        # shade the ink with the deck's normals/shadows at the same hits
        Aw = maps["albedo"].copy()
        rgb_ink = O3.shade_hits({"albedo": _np.zeros_like(maps["albedo"]) + PRINT_COL, "rough": _np.full_like(maps["rough"], 0.92),
                                 "metal": _np.zeros_like(maps["metal"]), "gx": maps["gx"], "gy": maps["gy"]},
                                shx, shy, shz, shadows=maps["shadow"], ao=maps["ao"]) * (1 + 0.12 * sp)[..., None]
        img = PB.to_image(rgb_ink, cover)
        frames.append(down(img, (rw, rh)))
    strip = Image.new("RGBA", (rw, rh * LABEL_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * rh))
    _DECK["label_rect"] = (rx, ry, rw, rh)
    return strip, frames


def draw_strobe_frames():
    S = SS
    maps = _DECK["maps"]
    hx, hy, hz = _DECK["hx"], _DECK["hy"], _DECK["hz"]
    pcx, pcy = maps["center"]
    # the visible side wall: front half of the platter between its top and the plinth
    rx = CX - R_PLATTER
    ry = int(math.floor(CY - R_PLATTER * O3.COS * 0.25 - Z_PLATTER * O3.SIN))
    rw = 2 * R_PLATTER
    rh = int(math.ceil(CY + R_PLATTER * O3.COS + 2)) - ry
    sl = (slice(ry * S, (ry + rh) * S), slice(rx * S, (rx + rw) * S))
    shx, shy, shz = hx[sl], hy[sl], hz[sl]
    dx, dy = shx - pcx, shy - pcy
    r = _np.sqrt(dx * dx + dy * dy)
    side = (r > (R_PLATTER - 4) * S) & (r < (R_PLATTER + 3) * S) & (shz < (Z_PLATTER - 2.5) * S) & (dy > -R_PLATTER * S * 0.2)
    frames = []
    for k in range(STROBE_FRAMES):
        phase = k / (STROBE_FRAMES - 1)
        rgb = O3.shade_hits(maps, shx, shy, shz, shadows=maps["shadow"], ao=maps["ao"], side=_side_fn(maps, phase, S))
        img = PB.to_image(rgb, side.astype(_np.float32))
        frames.append(down(img, (rw, rh)))
    strip = Image.new("RGBA", (rw, rh * STROBE_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * rh))
    _DECK["strobe_rect"] = (rx, ry, rw, rh)
    return strip, frames


def _object_render(build, w_l, h_l, zmax_l, S=3, emission=None):
    """render a small object on a transparent ground. build(Ww, Hw, x, y, S) -> maps(albedo,H,rough,metal,obj[,em]).
    w_l, h_l: footprint in layout px. Returns an RGBA image whose screen height is h_l + zmax*sin (layout px)."""
    Ww, Hw = int(w_l * S), int(math.ceil(h_l / O3.COS * S))
    x, y = PB.grid(Ww, Hw)
    maps = build(Ww, Hw, x, y, S)
    maps = O3.prepare(maps, shadow_steps=16, ao_radius=3 * S, ao_strength=0.05)
    out_h = int(math.ceil((h_l + zmax_l * O3.SIN) * S))
    v0 = -zmax_l * O3.SIN * S
    rgb, alpha, (hx, hy, hz) = O3.render(maps, Ww, out_h, 0, v0, transparent_ground=True)
    if "em" in maps:
        em = _np.dstack([O3.remap(maps["em"][..., c], hx, hy) for c in range(3)])
        ema = O3.remap(maps["em_a"], hx, hy)
        rgb = rgb + em
        alpha = _np.maximum(alpha, ema)
    return PB.to_image(rgb, alpha), out_h / S


def draw_knob_strip(size=80, frames=64, accent=RED):
    out = []
    a0, a1 = math.radians(135), math.radians(405)
    for k in range(frames):
        v = k / (frames - 1)
        ang = a0 + (a1 - a0) * v
        def build(Ww, Hw, x, y, S, v=v, ang=ang):
            c = Ww / 2.0
            cy = Hw / 2.0
            px, py = x - c, y - cy
            r = _np.sqrt(px * px + py * py)
            th = _np.arctan2(py, px)
            rk = (size / 2 - 11) * S
            rc = rk * 0.74
            A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.03, 0.03, 0.032]), 0.0, 0.6, 0.0)
            skirt = PB.disc(r, rk)
            knurl = _np.cos((th - ang) * 40) * 0.6 * S * PB.ring(r, rc + 2 * S, rk)
            Hm = skirt * ((Z_KNOB - 3) * S * PB.smoothstep(rk, rk - 2.5 * S, r) + knurl)
            cap = PB.disc(r, rc)
            Hm = Hm * (1 - cap) + cap * (Z_KNOB * S - 2 * S * (r / rc) ** 2 + PB.fbm(Ww, Hw, 9, 3, 6.0) * 0.08 * S)
            Rm = Rm * (1 - cap) + cap * 0.42
            pxr = px * math.cos(-ang) - py * math.sin(-ang)
            pyr = px * math.sin(-ang) + py * math.cos(-ang)
            ptr = PB.blur(((pxr > rc * 0.25) & (pxr < rk * 0.97) & (_np.abs(pyr) < 1.5 * S)).astype(_np.float32), 0.6)
            A = A * (1 - ptr[..., None]) + PB.srgb_to_lin([0.92, 0.92, 0.88]) * ptr[..., None]
            Hm = Hm + ptr * 0.3 * S
            # LED ring on the panel (emissive dots)
            em = _np.zeros((Hw, Ww, 3), _np.float32)
            ema = _np.zeros((Hw, Ww), _np.float32)
            r_led = (size / 2 - 4.5) * S
            for i in range(15):
                aa = a0 + (a1 - a0) * i / 14
                lx, ly = c + r_led * math.cos(aa), cy + r_led * math.sin(aa)
                dl = _np.sqrt((x - lx) ** 2 + (y - ly) ** 2)
                dot = PB.disc(dl, 2.2 * S)
                on = v > 0.004 and i <= v * 14 + 1e-6
                col = _np.array([3.0, 0.9, 0.18]) if on else _np.array([0.10, 0.04, 0.02])
                em += dot[..., None] * col
                ema = _np.maximum(ema, dot)
                if on:
                    gl = _np.exp(-(dl / (3.8 * S)) ** 2) * 0.55
                    em += gl[..., None] * _np.array([1.2, 0.35, 0.05])
                    ema = _np.maximum(ema, gl * 0.9)
            return {"albedo": A, "H": Hm, "rough": Rm, "metal": Mm, "obj": skirt, "em": em, "em_a": ema}
        img, hs = _object_render(build, size, size, Z_KNOB, S=3)
        out.append(img.resize((size, size), Image.LANCZOS))
    strip = Image.new("RGBA", (size, size * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * size))
    return strip, out


def _key_pbr(w, h, label, on, led=True, style="silver"):
    press = 1.6 if on else 0.0
    def build(Ww, Hw, x, y, S):
        dist = PB.rrect(x, y, 3 * S, 3 * S, Ww - 3 * S, Hw - 4 * S, 7 * S)
        body = 1 - PB.smoothstep(-1, 1, dist)
        zt = (Z_KEY - press) * S
        if style == "silver":
            A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.80, 0.81, 0.83]), 0.0, 0.26, 1.0)
            Hm = body * (zt * PB.smoothstep(0, -3.5 * S, dist) + PB.brushed(Ww, Hw, 51, 40, 0.4) * 0.4)
            ink = PB.srgb_to_lin([0.10, 0.10, 0.11])
        else:
            A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.05, 0.05, 0.055]), 0.0, 0.55, 0.0)
            Hm = body * (zt * PB.smoothstep(0, -3.5 * S, dist) + PB.fbm(Ww, Hw, 52, 4, 4.0) * 0.15 * S)
            ink = PB.srgb_to_lin([0.85, 0.86, 0.88])
        fs = (18 if len(label) <= 6 else 15) * S
        tm = _text_mask(Ww, Hw, [(Ww / 2, Hw / 2 + (5 * S if led else 0), label, ImageFont.truetype(os.path.join(FONTS, F_BOLD), fs), "mm", 0)])
        tm = _cv2.resize(_cv2.resize(tm, (Ww, int(Hw * O3.COS))), (Ww, Hw))
        A = A * (1 - tm[..., None]) + ink * tm[..., None]
        Hm = Hm - tm * 0.5 * S
        Rm = Rm * (1 - tm) + tm * 0.6
        Mm = Mm * (1 - tm)
        maps = {"albedo": A, "H": Hm, "rough": Rm, "metal": Mm, "obj": body}
        if led:
            lx, ly = Ww / 2, 11 * S / O3.COS
            dl = _np.sqrt((x - lx) ** 2 + (y - ly) ** 2)
            dot = PB.disc(dl, 3.2 * S)
            col = _np.array([3.2, 0.35, 0.18]) if on else _np.array([0.12, 0.02, 0.01])
            em = dot[..., None] * col
            ema = dot.copy()
            if on:
                gl = _np.exp(-(dl / (6 * S)) ** 2) * 0.6
                em = em + gl[..., None] * _np.array([1.4, 0.15, 0.06])
            maps["em"], maps["em_a"] = em, ema
        return maps
    img, hs = _object_render(build, w, h, Z_KEY, S=3)
    return img.resize((w, h), Image.LANCZOS)


def draw_key(w, h, label, on, led=True, sub=None, style="silver"):
    return _key_pbr(w, h, label, on, led, style)


def draw_pitch_fader(w=72, h=396, frames=41):
    out = []
    travel_top, travel_bot = 20, h - 20
    for k in range(frames):
        v = k / (frames - 1)
        yv = travel_bot - v * (travel_bot - travel_top)
        def build(Ww, Hw, x, y, S, yv=yv, v=v):
            cyw = yv * S / O3.COS
            dist = PB.rrect(x, y, 9 * S, cyw - 17 * S, 63 * S, cyw + 17 * S, 5 * S)
            cap = 1 - PB.smoothstep(-1, 1, dist)
            A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.03, 0.03, 0.033]), 0.0, 0.45, 0.0)
            ridges = _np.cos((y - cyw) / S * 2 * _np.pi / 3.4) * 0.5 * S
            Hm = cap * (14 * S * PB.smoothstep(0, -4 * S, dist) + ridges * PB.smoothstep(-24 * S, -6 * S, dist))
            line = (_np.abs(y - cyw) < 1.3 * S) & (dist < -3 * S)
            A[line] = PB.srgb_to_lin([0.92, 0.92, 0.93]); Mm[line] = 1.0; Rm[line] = 0.1; Hm[line] += 0.8 * S
            maps = {"albedo": A, "H": Hm, "rough": Rm, "metal": Mm, "obj": cap}
            # zero LED
            lx, ly = (w - 11) * S, (h / 2) * S / O3.COS
            dl = _np.sqrt((x - lx) ** 2 + (y - ly) ** 2)
            dot = PB.disc(dl, 4.2 * S)
            on = abs(v - 0.5) < 0.5 / (frames - 1)
            col = _np.array([0.25, 2.8, 0.6]) if on else _np.array([0.02, 0.10, 0.04])
            maps["em"] = dot[..., None] * col + ((_np.exp(-(dl / (8 * S)) ** 2) * 0.5)[..., None] * _np.array([0.1, 1.0, 0.3]) if on else 0)
            maps["em_a"] = _np.maximum(dot, _np.exp(-(dl / (8 * S)) ** 2) * 0.6 if on else 0)
            return maps
        img, hs = _object_render(build, w, h, 14, S=2)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def draw_tonearm():
    """floating S-arm: rendered on its own (with an underside so it does not reach the ground), its shadow is
    cast onto the deck's real heights"""
    S = SS
    maps_d = _DECK["maps"]
    Ww, Hw, x, y = _wgrid(S)
    Yw = lambda ly: O3.Y(ly) * S
    A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.95, 0.95, 0.96]), 0.0, 0.05, 1.0)
    Hb = _np.full((Hw, Ww), 1e6, _np.float32)          # underside (no object: never hit)
    obj = _np.zeros((Hw, Ww), _np.float32)
    def add_tube(pts, rad, z0, col=(0.96, 0.96, 0.97), rough=0.04, metal=1.0):
        th_, tm_ = _tube_height(Ww, Hw, pts, rad)
        top = z0 + th_
        sel = tm_ > 0.02
        better = sel & (top > _np.where(obj > 0.02, Hm, -1))
        A[better] = PB.srgb_to_lin(list(col)); Rm[better] = rough; Mm[better] = metal
        Hm[better] = top[better]
        Hb[better] = _np.minimum(Hb[better], (z0 - th_)[better])
        obj[:] = _np.maximum(obj, tm_)
    zc = Z_ARM * S
    # counterweight (as a fat short tube along y)
    add_tube([(708 * S, Yw(y_)) for y_ in _np.linspace(26, 70, 20)], 20 * S, zc, col=(0.06, 0.06, 0.065), rough=0.35, metal=0.4)
    add_tube([(708 * S, Yw(y_)) for y_ in _np.linspace(70, 118, 20)], 4.5 * S, zc)
    # gimbal (short wide disc approximated by a fat tube along x)
    add_tube([(x_ * S, Yw(124)) for x_ in _np.linspace(696, 720, 8)], 16 * S, zc - 4 * S, col=(0.9, 0.9, 0.92), rough=0.08)
    curve = RD.bezier((708, 132), (712, 300), (660, 380), (566, 482), 160)
    add_tube([(cx_ * S, Yw(cy_)) for cx_, cy_ in curve], 6.0 * S, zc)
    hx_, hy_ = 566, 482
    # headshell (flat black plate) + finger lift
    shell = _np.zeros((Hw, Ww), _np.uint8)
    _cv2.fillPoly(shell, [_np.array([(xx * S, Yw(yy)) for xx, yy in [(hx_ - 32, hy_ - 10), (hx_ + 7, hy_ - 21), (hx_ + 15, hy_ + 4), (hx_ - 23, hy_ + 23)]], _np.int32)], 255)
    shm = PB.blur(shell.astype(_np.float32) / 255, 0.8)
    sel = shm > 0.3
    A[sel] = PB.srgb_to_lin([0.04, 0.04, 0.045]); Rm[sel] = 0.3; Mm[sel] = 0.2
    Hm[sel] = zc - 2 * S; Hb[sel] = zc - 7 * S
    obj[:] = _np.maximum(obj, shm)
    add_tube([((hx_ - 28 - t * 26) * S, Yw(hy_ - 4 + t * 8)) for t in _np.linspace(0, 1, 20)], 2.3 * S, zc - 3 * S)
    Hm_eff = _np.where(obj > 0.02, Hm, 0.0).astype(_np.float32)
    maps = {"albedo": A, "H": Hm_eff, "rough": Rm, "metal": Mm, "obj": obj}
    gx, gy = O3.world_normals(Hm_eff)
    maps["gx"], maps["gy"] = gx, gy
    maps["shadow"] = _np.ones_like(Hm_eff)
    maps["ao"] = _np.ones_like(Hm_eff)
    # screen bounding box of the arm (layout px)
    bx0, by0, bw, bh = 470, 0, 340, 520
    hx2, hy2, hz2, hit = O3.march(Hm_eff, bw * S, bh * S, bx0 * S, by0 * S, zmax=zc + 24 * S, floating=Hb)
    rgb = O3.shade_hits(maps, hx2, hy2, hz2, shadows=None, ao=None)
    arm_a = hit & (O3.remap(obj, hx2, hy2) > 0.3)
    # shadow on the deck: where does the light ray from each deck hit meet the arm?
    L = PB.LIGHT_DIR
    dsl = (slice(by0 * S, (by0 + bh) * S), slice(bx0 * S, (bx0 + bw) * S))
    dhx, dhy, dhz = _DECK["hx"][dsl], _DECK["hy"][dsl], _DECK["hz"][dsl]
    t = (zc - dhz) / L[2]
    sx_, sy_ = dhx + L[0] * t, dhy + L[1] * t
    shad = PB.blur(O3.remap(obj, sx_, sy_, _cv2.BORDER_CONSTANT), 3.5 * S) * 0.62
    alpha = _np.where(arm_a, 1.0, shad).astype(_np.float32)
    rgb = _np.where(arm_a[..., None], rgb, 0.0)
    img = PB.to_image(rgb, alpha)
    return down(img, (bw, bh)), (bx0, by0, bw, bh)

