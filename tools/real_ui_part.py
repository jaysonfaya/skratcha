
# ======================================================================================================
# PHOTO-REAL VERSIONS (override the flat drawings above)
# ======================================================================================================
import numpy as _np
import real_draw as RD


def _engrave(d, xy, s, f, anchor="la", light=(255, 255, 255, 150), ink=(38, 39, 42, 255), spacing=0):
    x, y = xy
    text(d, (x, y + 1.3 * SS), s, f, light, anchor, spacing)
    text(d, (x, y), s, f, ink, anchor, spacing)


def _print(d, xy, s, f, anchor="la", col=(232, 233, 236, 235), spacing=0):
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
    sd.line([(x + 14 * S, y + 16 * S) for x, y in pts], fill=(0, 0, 0, 150), width=11 * S, joint="curve")
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
    RD.draw_tube(img, pts, 5.2 * S, S)
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
    img.alpha_composite(RD.metal_disc(18 * S, base=0.75, power=16, rim_dark=0.35), ((cx - 9) * S, (cy - 9) * S))
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

