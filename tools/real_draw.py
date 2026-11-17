"""Photo-real drawing helpers for SKRATCHA (numpy + Pillow).

Light comes from the top left (and a weaker fill from the top right), so every surface is shaded the same way:
circularly brushed aluminium and vinyl grooves get anisotropic highlights (the bright "light cross" you see on real
records), chrome is shaded as a reflecting cylinder, rubber and anodised parts are matte with soft speculars.
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

LIGHT = math.atan2(-1.0, -1.0)      # key light direction (screen angle, top left)
FILL = math.atan2(-1.0, 0.6)        # fill light (top right), weaker


# ------------------------------------------------------------------------------------------------- basics
def grid(w, h, cx=0.0, cy=0.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return xx - cx, yy - cy


def to_rgba(rgb, alpha=None):
    rgb = np.clip(rgb, 0.0, 1.0)
    a = np.ones(rgb.shape[:2], np.float32) if alpha is None else np.clip(alpha, 0.0, 1.0)
    arr = np.dstack([rgb, a[..., None]]) * 255.0
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def from_img(img):
    a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255.0
    return a[..., :3], a[..., 3]


def blur_np(a, r):
    if r <= 0:
        return a
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im).astype(np.float32) / 255.0


def noise(w, h, seed, blur=0.0):
    rng = np.random.default_rng(seed)
    n = rng.random((h, w)).astype(np.float32)
    return blur_np(n, blur) if blur else n


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ring_mask(r, r_in, r_out, aa=1.0):
    return smoothstep(r_in - aa, r_in + aa, r) * (1.0 - smoothstep(r_out - aa, r_out + aa, r))


def disc_mask(r, rad, aa=1.0):
    return 1.0 - smoothstep(rad - aa, rad + aa, r)


def radial_streaks(r, seed, scale=1.0, amount=0.05):
    """random value per radius (circular brushing / grooves)"""
    rng = np.random.default_rng(seed)
    n = int(r.max() * scale) + 4
    table = rng.standard_normal(n).astype(np.float32)
    table = np.convolve(table, np.ones(2) / 2, mode="same")
    idx = np.clip((r * scale).astype(np.int32), 0, n - 1)
    return table[idx] * amount


def aniso(theta, power, light=LIGHT):
    """highlight of circular grooves: brightest where the radius points along the light axis"""
    return np.abs(np.cos(theta - light)) ** power


def comp(dst_rgb, dst_a, src_rgb, src_a):
    """alpha-composite src over dst (numpy arrays)"""
    a = src_a[..., None]
    out_rgb = src_rgb * a + dst_rgb * (1 - a)
    out_a = src_a + dst_a * (1 - src_a)
    return out_rgb, out_a


def shadow_layer(mask, blur, opacity, dx, dy):
    m = np.roll(np.roll(mask, int(dy), axis=0), int(dx), axis=1)
    return blur_np(m, blur) * opacity


# ------------------------------------------------------------------------------------------------- materials
def brushed_plate(w, h, base, seed=1, grain=0.035, light=True):
    rng = np.random.default_rng(seed)
    rows = rng.standard_normal((h, 1)).astype(np.float32)
    fine = rng.standard_normal((h, w)).astype(np.float32)
    # horizontal brushing: strong per-row variation + fine noise smeared along x
    fine = np.asarray(Image.fromarray(np.clip((fine * 0.2 + 0.5) * 255, 0, 255).astype(np.uint8), "L")
                      .filter(ImageFilter.BoxBlur(0)).resize((w // 8 + 1, h), Image.BILINEAR).resize((w, h), Image.BILINEAR)).astype(np.float32) / 255.0 - 0.5
    v = rows * grain * 0.6 + fine * grain
    rgb = np.ones((h, w, 3), np.float32) * np.array(base, np.float32)
    rgb += v[..., None]
    if light:
        x, y = grid(w, h)
        g = 1.0 + 0.06 * (1 - (x / w + y / h))            # brighter toward the light
        rgb *= g[..., None]
    return rgb


def anodised(w, h, base=(0.085, 0.087, 0.092), seed=3):
    rgb = brushed_plate(w, h, base, seed=seed, grain=0.012, light=False)
    x, y = grid(w, h)
    rgb *= (1.0 + 0.10 * (1 - (x / w + y / h) * 0.7))[..., None]
    return rgb


# ------------------------------------------------------------------------------------------------- record
def vinyl(size, r_rec, r_runout, seed=11, label_r=None):
    """top view of a black record (size x size, centred). Returns rgb, alpha."""
    c = size / 2.0
    x, y = grid(size, size, c, c)
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    S = size / (2 * r_rec)          # pixels per "unit radius" scale
    base = 0.028
    rgb = np.full((size, size, 3), base, np.float32)
    # groove bands: tracks with narrow glossy gaps between them
    rr = r / S
    rng = np.random.default_rng(seed)
    gaps = np.sort(rng.uniform(r_runout + 12, r_rec - 6, 6))
    band = np.ones_like(r)
    for gpos in gaps:
        band -= np.exp(-((rr - gpos) / 1.4) ** 2) * 0.85
    band = np.clip(band, 0.0, 1.0)
    grooves = radial_streaks(r, seed, scale=1.0 / max(S, 1e-6) * 1.6, amount=0.010)
    # highlights: key light cross + fill, grooved bands scatter (wide, soft), gaps reflect (narrow, bright)
    key_wide = aniso(th, 3) * 0.16 + aniso(th, 14) * 0.30 + aniso(th, 60) * 0.22
    key_gap = aniso(th, 120) * 0.65
    fill = aniso(th, 6, FILL) * 0.07 + aniso(th, 30, FILL) * 0.12
    radial_fall = 0.55 + 0.45 * smoothstep(r_runout * S, r_rec * S, r)   # outer grooves catch more light
    spec = (key_wide * band + key_gap * (1 - band)) * radial_fall + fill * band
    spec += grooves * (0.6 + 2.0 * aniso(th, 8))
    tint = np.array([0.92, 0.95, 1.0], np.float32)
    rgb += spec[..., None] * tint
    # run-out area: smooth and glossy with a lead-out spiral
    ro = (r < (r_runout + 9) * S) & (r > (r_runout) * S)
    rgb[ro] = base + 0.0
    gloss = aniso(th, 200) * 0.75 + aniso(th, 200, FILL) * 0.25
    rgb += (ring_mask(r, r_runout * S, (r_runout + 9) * S) * gloss)[..., None] * 0.85
    spiral = np.abs(((r / S - (r_runout + 4.5)) - (th / (2 * np.pi)) * 2.5) % 2.5 - 1.25) < 0.12
    rgb[spiral & ro] += 0.05
    # edge bevel: thin bright rim, dark just inside
    rgb += (ring_mask(r, (r_rec - 1.6) * S, (r_rec - 0.2) * S) * (0.18 + 0.5 * aniso(th, 4)))[..., None]
    rgb -= (ring_mask(r, (r_rec - 3.5) * S, (r_rec - 1.6) * S) * 0.015)[..., None]
    alpha = disc_mask(r, r_rec * S, 1.0)
    if label_r:
        alpha *= 1.0  # label is drawn on top by the rotating film strip
    return rgb, alpha


def platter(size, R_platter, R_strobe_out, R_strobe_in, R_mat, seed=21):
    c = size / 2.0
    x, y = grid(size, size, c, c)
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    rgb = np.zeros((size, size, 3), np.float32)
    alpha = disc_mask(r, R_platter, 1.2)
    # polished outer lip: circular brushed aluminium
    lip = ring_mask(r, R_strobe_out, R_platter)
    al = 0.56 + radial_streaks(r, seed, 2.0, 0.035) + 0.38 * aniso(th, 10) + 0.18 * aniso(th, 60) + 0.10 * aniso(th, 16, FILL)
    # bevels: bright outer edge facing the light, darker step to the strobe band
    edge = ring_mask(r, R_platter - 2.0, R_platter) * (0.25 + 0.55 * np.clip(-np.cos(th - LIGHT + np.pi), 0, 1))
    rgb += (lip * (al + edge))[..., None] * np.array([1.0, 1.0, 1.02])
    # strobe band: a sloped, darker satin surface (dots are drawn by the live strip)
    band = ring_mask(r, R_strobe_in, R_strobe_out)
    sb = 0.30 + radial_streaks(r, seed + 1, 2.0, 0.02) + 0.16 * aniso(th, 8)
    rgb += (band * sb)[..., None]
    # inner step (aluminium) and the rubber mat
    step = ring_mask(r, R_mat, R_strobe_in)
    rgb += (step * (0.48 + 0.30 * aniso(th, 12) + radial_streaks(r, seed + 2, 2.0, 0.03)))[..., None]
    mat = disc_mask(r, R_mat)
    ridges = 0.5 + 0.5 * np.sin(r * 2 * np.pi / 3.2)
    m = 0.040 + 0.012 * ridges * (0.4 + aniso(th, 4)) + 0.02 * aniso(th, 30) * ridges
    rgb = rgb * (1 - mat[..., None]) + (mat * m)[..., None] * np.ones(3)
    # ambient occlusion where mat meets the step
    rgb *= (1 - 0.35 * ring_mask(r, R_mat - 3, R_mat + 1.5))[..., None]
    return rgb, alpha


def strobe_dots(size, R_in, R_out, phase, n_dots, lamp_angle, scale):
    """dots on the strobe band, lit red by the strobe lamp (a domed highlight each)"""
    c = size / 2.0
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rmid = (R_in + R_out) / 2.0
    for i in range(n_dots):
        a = 2 * math.pi * (i + phase) / n_dots - math.pi / 2
        px = c + rmid * math.cos(a)
        py = c + rmid * math.sin(a)
        lamp = max(0.0, math.cos(a - lamp_angle))
        lit = 0.25 + 0.75 * lamp ** 1.5
        rad = 3.3 * scale
        base = (int(70 + 185 * lit), int(36 + 40 * lit), int(32 + 30 * lit))
        d.ellipse([px - rad, py - rad, px + rad, py + rad], fill=base + (255,))
        hl = rad * 0.45
        d.ellipse([px - rad * 0.55 - hl / 2, py - rad * 0.55 - hl / 2, px - rad * 0.55 + hl / 2, py - rad * 0.55 + hl / 2],
                  fill=(255, int(200 + 55 * lit), int(190 + 50 * lit), int(120 + 120 * lit)))
    glow = img.filter(ImageFilter.GaussianBlur(2.2 * scale))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(img)
    return out


# ------------------------------------------------------------------------------------------------- chrome tube
def chrome_profile(u):
    """colour across a chrome cylinder, u in -1..1 (left to right across the tube, light from the top left)"""
    env = 0.50 + 0.25 * np.cos((u + 0.2) * 3.0)
    hi = np.exp(-((u + 0.45) / 0.10) ** 2) * 0.75 + np.exp(-((u - 0.55) / 0.18) ** 2) * 0.22
    dark = np.exp(-((u - 0.15) / 0.22) ** 2) * 0.30
    edge = np.abs(u) ** 6 * 0.35
    v = np.clip(env + hi - dark - edge, 0.03, 1.0)
    return v


def draw_tube(img, pts, radius, scale, colour=(1.0, 1.0, 1.02)):
    """draw a shaded cylinder along a polyline onto a PIL RGBA image (coordinates already scaled)"""
    d = ImageDraw.Draw(img)
    pts = np.asarray(pts, np.float64)
    # normals
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9
    nor = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
    # orient normals so that u=-1 faces the light (top left)
    if np.mean(nor[:, 0] * -1 + nor[:, 1] * -1) < 0:
        nor = -nor
    steps = int(radius * 2 * 1.5) + 2
    for k in range(steps + 1):
        u = 1 - 2 * k / steps            # from the far side (u=+1) to the lit side (u=-1)
        off = -u * radius
        v = float(chrome_profile(np.array([u]))[0])
        col = tuple(int(255 * min(1, v * c)) for c in colour) + (255,)
        line = [tuple(p + nor[i] * off) for i, p in enumerate(pts)]
        d.line(line, fill=col, width=max(1, int(scale * 1.6)), joint="curve")


def bezier(p0, p1, p2, p3, n=80):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.array(p, np.float64) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def metal_disc(size, base=0.62, power=10, seed=5, rim_dark=0.25):
    c = size / 2.0
    x, y = grid(size, size, c, c)
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    v = base + radial_streaks(r, seed, 2.5, 0.03) + 0.30 * aniso(th, power) + 0.08 * aniso(th, power, FILL)
    v -= rim_dark * smoothstep(c * 0.85, c, r)
    alpha = disc_mask(r, c - 0.8, 1.0)
    return to_rgba(np.dstack([v, v, v * 1.02]), alpha)


# ------------------------------------------------------------------------------------------------- controls
def rubber_knob(size, value, ss=3, led_n=15, accent=(1.0, 0.42, 0.10)):
    """DJ-mixer knob: knurled rubber skirt, matte cap, white pointer, LED ring around"""
    S = size * ss
    c = S / 2.0
    x, y = grid(S, S, c, c)
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    rgb = np.zeros((S, S, 3), np.float32)
    alpha = np.zeros((S, S), np.float32)
    # LED ring (dots)
    ledimg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(ledimg)
    a0, a1 = math.radians(135), math.radians(405)
    lit_upto = value * (led_n - 1)
    r_led = c - 4.5 * ss
    for i in range(led_n):
        a = a0 + (a1 - a0) * i / (led_n - 1)
        px, py = c + r_led * math.cos(a), c + r_led * math.sin(a)
        on = i <= lit_upto + 1e-6 and value > 0.004
        col = tuple(int(255 * v) for v in accent) if on else (52, 30, 22)
        rr = 2.2 * ss
        ld.ellipse([px - rr, py - rr, px + rr, py + rr], fill=col + (255,))
    if value > 0.004:
        glow = ledimg.filter(ImageFilter.GaussianBlur(2.5 * ss))
        ledimg = Image.alpha_composite(glow, ledimg)
    # drop shadow
    rk = c - 11 * ss
    sh = blur_np(np.roll(np.roll(disc_mask(r, rk), int(3 * ss), 0), int(2 * ss), 1), 4 * ss) * 0.75
    rgb, alpha = comp(rgb, alpha, np.zeros_like(rgb), sh)
    # knurled skirt
    skirt = disc_mask(r, rk)
    ridges = 0.5 + 0.5 * np.cos(th * 36)
    sv = 0.07 + 0.05 * ridges + 0.10 * aniso(th, 3) * ridges
    sv *= 1.0 - 0.4 * smoothstep(rk * 0.9, rk, r)
    rgb, alpha = comp(rgb, alpha, np.dstack([sv, sv, sv]), skirt)
    # cap: slightly domed matte black with a soft highlight
    rc = rk * 0.72
    cap = disc_mask(r, rc)
    hx, hy = -rc * 0.35, -rc * 0.35
    dh = np.sqrt((x - hx) ** 2 + (y - hy) ** 2) / rc
    cv = 0.10 + 0.10 * np.exp(-dh * dh * 2.5) - 0.04 * smoothstep(rc * 0.8, rc, r)
    rgb, alpha = comp(rgb, alpha, np.dstack([cv, cv, cv * 1.03]), cap)
    # edge highlight of the cap
    rgb += (ring_mask(r, rc - 1.2 * ss, rc) * 0.08 * (0.5 + aniso(th, 2)))[..., None]
    img = to_rgba(rgb, alpha)
    img = Image.alpha_composite(ledimg, img)
    d = ImageDraw.Draw(img)
    ang = a0 + (a1 - a0) * value
    d.line([(c + rc * 0.22 * math.cos(ang), c + rc * 0.22 * math.sin(ang)), (c + rk * 0.96 * math.cos(ang), c + rk * 0.96 * math.sin(ang))],
           fill=(246, 246, 240, 255), width=int(2.6 * ss))
    return img.resize((size, size), Image.LANCZOS)


def key_cap(w, h, label, on, font_path, led=True, style="silver", ss=3, led_col=(1.0, 0.18, 0.10)):
    """a real push key: drop shadow, bevelled face, engraved legend, domed LED lens"""
    W, H = w * ss, h * ss
    x, y = grid(W, H)
    press = 1.2 * ss if on else 0.0
    rad = 7 * ss
    # rounded-rect signed distance
    def rrect_mask(x0, y0, x1, y1, r):
        cx = np.clip(x, x0 + r, x1 - r); cy = np.clip(y, y0 + r, y1 - r)
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r
        return 1.0 - smoothstep(-1.0, 1.0, dist), dist
    body, dist = rrect_mask(2 * ss, 2 * ss + press, W - 2 * ss, H - 5 * ss + press, rad)
    shadow = blur_np(rrect_mask(3 * ss, 5 * ss, W - 1 * ss, H - 1 * ss, rad)[0], 3 * ss) * (0.45 if on else 0.65)
    rgb = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)
    rgb, alpha = comp(rgb, alpha, np.zeros_like(rgb), shadow)
    t = (y - 2 * ss) / (H - 7 * ss)
    if style == "silver":
        face = 0.82 - 0.22 * t + 0.03 * (np.random.default_rng(4).random((H, W)) - 0.5)
        face -= 0.06 if on else 0.0
        col = np.dstack([face, face, face * 1.01])
        ink = (40, 40, 44)
    else:
        face = 0.20 - 0.10 * t
        face -= 0.03 if on else 0.0
        col = np.dstack([face, face, face * 1.04])
        ink = (226, 228, 232)
    # bevel: light top-left edge, dark bottom-right edge
    bevel = smoothstep(-3.5 * ss, 0, dist)
    hl = bevel * np.clip(1 - t * 2, 0, 1) * 0.25
    lo = bevel * np.clip(t * 2 - 1, 0, 1) * 0.25
    col = col + hl[..., None] - lo[..., None]
    rgb, alpha = comp(rgb, alpha, col, body)
    img = to_rgba(rgb, alpha)
    d = ImageDraw.Draw(img)
    fs = (18 if len(label) <= 6 else 15) * ss
    f = ImageFont.truetype(font_path, fs)
    ty = (h / 2 + (5 if led else 0)) * ss + press - 2 * ss
    # engraved text: light lower edge + ink
    if style == "silver":
        d.text((W / 2, ty + 1.2 * ss), label, font=f, fill=(250, 250, 250, 170), anchor="mm")
    else:
        d.text((W / 2, ty + 1.2 * ss), label, font=f, fill=(0, 0, 0, 200), anchor="mm")
    d.text((W / 2, ty), label, font=f, fill=ink + (255,), anchor="mm")
    if led:
        lx, ly, lr = W / 2, 11 * ss + press, 3.2 * ss
        if on:
            glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse([lx - lr * 3, ly - lr * 3, lx + lr * 3, ly + lr * 3], fill=tuple(int(255 * c) for c in led_col) + (150,))
            img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3 * ss)))
            d = ImageDraw.Draw(img)
            base = tuple(int(255 * c) for c in led_col)
        else:
            base = tuple(int(70 * c) + 18 for c in led_col)
        d.ellipse([lx - lr, ly - lr, lx + lr, ly + lr], fill=base + (255,), outline=(20, 20, 20, 255), width=max(1, ss // 2))
        d.ellipse([lx - lr * 0.6, ly - lr * 0.7, lx - lr * 0.05, ly - lr * 0.2], fill=(255, 255, 255, 170 if on else 70))
    return img.resize((w, h), Image.LANCZOS)


def led_lens(d, cx, cy, r, colour, on, img=None):
    if on and img is not None:
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([cx - r * 2.6, cy - r * 2.6, cx + r * 2.6, cy + r * 2.6], fill=colour + (140,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(r)))
        d = ImageDraw.Draw(img)
    base = colour if on else tuple(int(c * 0.22) + 12 for c in colour)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=base + (255,), outline=(14, 14, 14, 255), width=max(1, int(r / 4)))
    d.ellipse([cx - r * 0.6, cy - r * 0.7, cx - r * 0.05, cy - r * 0.2], fill=(255, 255, 255, 170 if on else 60))
    return d


def screw(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(150, 152, 156, 255), outline=(40, 40, 42, 255), width=max(1, int(r / 5)))
    d.ellipse([cx - r * 0.75, cy - r * 0.75, cx + r * 0.2, cy + r * 0.2], fill=(205, 208, 212, 255))
    a = math.radians(30)
    for s in (0, math.pi / 2):
        d.line([(cx - r * 0.7 * math.cos(a + s), cy - r * 0.7 * math.sin(a + s)), (cx + r * 0.7 * math.cos(a + s), cy + r * 0.7 * math.sin(a + s))],
               fill=(50, 50, 54, 255), width=max(1, int(r / 3)))
