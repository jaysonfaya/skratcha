"""Oblique 3D view for SKRATCHA: height-field ray marching with PBR shading (see pbr.py).

World: x to the right, y toward the viewer, z up, all in pixels of the supersampled world grid.
Camera: parallel projection tilted by TILT from straight down, looking from the front. A world point shows on
screen at  u = x,  v = y*cos(TILT) - z*sin(TILT).  Fronts of objects (faces toward +y) become visible, tops are
seen slightly flattened, like a product photo from the front.

Layout helper: a "layout" coordinate (lx, ly) is where a point on the ground appears on screen. The world y of
that ground point is ly / cos(TILT); an object of height z at that place appears z*sin(TILT) higher.
"""
import math

import cv2
import numpy as np

import pbr as PB

TILT = math.radians(30.0)
COS, SIN = math.cos(TILT), math.sin(TILT)
VIEW = np.array([0.0, SIN, COS], np.float32)        # direction from the surface toward the camera


def Y(ly):
    """world y of a ground point that appears at layout/screen y = ly"""
    return ly / COS


def screen_v(y_world, z):
    return y_world * COS - z * SIN


def remap(img, mx, my, border=cv2.BORDER_REPLICATE):
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=border)


def march(H, out_w, out_h, u0=0.0, v0=0.0, zmax=None, step=0.5, floating=None):
    """For every screen pixel of the rectangle (u0, v0, out_w, out_h) find where its view ray meets the height field.
    Returns world (x, y) of the hit, the hit height and a mask of rays that hit (all hit for a closed ground).
    floating: (Hbottom) -> a hit only counts where the ray is above the object's underside (for objects that float)."""
    if zmax is None:
        zmax = float(H.max()) + 1.0
    uu, vv = np.meshgrid(np.arange(out_w, dtype=np.float32) + u0, np.arange(out_h, dtype=np.float32) + v0)
    # ray: z(y) = (y*COS - v) / SIN ; marching from high z (large y) down toward z = 0
    y_top = (vv + zmax * SIN) / COS
    y_bot = vv / COS
    n = int(math.ceil((zmax * SIN / COS) / step)) + 2
    hit_y = y_bot.copy()
    hit = np.zeros(vv.shape, bool)
    prev_y = y_top
    prev_d = None
    for k in range(n + 1):
        t = k / n
        yk = y_top + (y_bot - y_top) * t
        zr = (yk * COS - vv) / SIN
        hk = remap(H, uu, yk)
        d = zr - hk                         # > 0: ray above the surface
        if floating is not None:
            hb = remap(floating, uu, yk)
            inside = (d <= 0) & (zr >= hb)
        else:
            inside = d <= 0
        new = inside & ~hit
        if prev_d is not None:
            # refine between the previous step (above) and this one (below)
            frac = np.clip(prev_d / np.maximum(prev_d - d, 1e-6), 0, 1)
            yh = prev_y + (yk - prev_y) * frac
        else:
            yh = yk
        hit_y = np.where(new, yh, hit_y)
        hit |= new
        prev_y, prev_d = yk, d
    hit_z = np.where(hit, (hit_y * COS - vv) / SIN, 0.0)
    return uu, hit_y, hit_z, hit


def world_normals(H):
    gx = cv2.Sobel(H, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(H, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return gx, gy


def shade_hits(maps, hx, hy, hz, extra=None, shadows=None, ao=None, aniso=None, side=None):
    """maps: dict albedo (h,w,3), H, rough, metal, gx, gy (world). hx, hy: world hit coords per screen pixel."""
    A = np.dstack([remap(maps["albedo"][..., c], hx, hy) for c in range(3)])
    R = remap(maps["rough"], hx, hy)
    M = remap(maps["metal"], hx, hy)
    gx = remap(maps["gx"], hx, hy)
    gy = remap(maps["gy"], hx, hy)
    side_mask = None
    if side is not None:
        A, R, M, gx, gy = side(A, R, M, gx, gy, hx, hy, hz)
        side_mask = getattr(side, "side_mask", None)
    N = np.dstack([-gx, -gy, np.ones_like(gx)])
    N /= np.linalg.norm(N, axis=2, keepdims=True)
    ndv = np.clip((N * VIEW).sum(axis=2), 1e-3, 1)
    Rv = 2 * ndv[..., None] * N - VIEW
    rough = np.clip(R, 0.03, 1.0)
    metal = np.clip(M, 0, 1)[..., None]
    f0 = 0.04 * (1 - metal) + A * metal
    fres = f0 + (1 - f0) * ((1 - ndv) ** 5)[..., None] * (1 - rough[..., None]) ** 2
    spec_env = PB.env_radiance(Rv, rough)
    if aniso is not None:
        amap, acx, acy, asharp = aniso
        a = remap(amap, hx, hy)
        spec_env = spec_env * (1 - a) + aniso_at(hx, hy, acx, acy, asharp) * a
    nl_key = np.clip((N * PB.LIGHT_DIR).sum(axis=2), 0, 1)
    nl_fill = np.clip((N * PB.FILL_DIR).sum(axis=2), 0, 1)
    sh = remap(shadows, hx, hy) if shadows is not None else np.ones_like(R)
    oc = remap(ao, hx, hy) if ao is not None else np.ones_like(R)
    if side_mask is not None:
        sh = np.where(side_mask, 1.0, sh); oc = np.where(side_mask, 0.9, oc)
    nl_front = np.clip((N * np.array([0.0, 0.75, 0.66])).sum(axis=2), 0, 1)
    diffuse = A * (1 - metal) * ((nl_key * sh * 1.05 + nl_fill * 0.30 + nl_front * 0.25 + 0.20) * oc)[..., None]
    spec = fres * spec_env[..., None] * (0.35 + 0.65 * sh[..., None]) * oc[..., None]
    return diffuse + spec


def aniso_at(hx, hy, cx, cy, sharp):
    x = hx - cx; y = hy - cy
    r = np.sqrt(x * x + y * y) + 1e-6
    tx, ty = -y / r, x / r
    out = np.zeros(hx.shape, np.float32)
    for C, size, inten in ((PB.KEY, 0.10, 5.0), (PB.STRIP, 0.05, 2.6)):
        Hh = C + VIEW; Hh = Hh / np.linalg.norm(Hh)
        across = Hh[0] * tx + Hh[1] * ty
        s1 = (size * sharp) ** 2
        out += inten * (np.exp(-across ** 2 / s1) * 0.65 + np.exp(-across ** 2 / (s1 * 9)) * 0.35)
    return out


def prepare(maps, shadow_steps=34, ao_radius=24.0, ao_strength=0.05):
    H = maps["H"]
    gx, gy = world_normals(H)
    maps["gx"], maps["gy"] = gx, gy
    maps["shadow"] = PB.shadow_map(H, steps=shadow_steps)
    maps["ao"] = PB.ao_map(H, ao_radius, ao_strength)
    return maps


def render(maps, out_w, out_h, u0=0.0, v0=0.0, aniso=None, side=None, transparent_ground=False):
    hx, hy, hz, hit = march(maps["H"], out_w, out_h, u0, v0)
    rgb = shade_hits(maps, hx, hy, hz, shadows=maps.get("shadow"), ao=maps.get("ao"), aniso=aniso, side=side)
    alpha = None
    if transparent_ground:
        # object pixels are opaque; ground pixels keep only the darkening of shadow + occlusion
        obj = remap(maps["obj"], hx, hy)
        gsh = remap(maps["shadow"], hx, hy) * remap(maps["ao"], hx, hy)
        alpha = np.clip(obj + (1 - obj) * (1 - gsh) * 0.95, 0, 1)
        rgb = rgb * obj[..., None]          # ground colour -> black (shadow only)
    return rgb, alpha, (hx, hy, hz)
