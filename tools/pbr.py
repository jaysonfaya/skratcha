"""Tiny physically based 2.5D renderer for SKRATCHA's skin (numpy + OpenCV).

Every surface is described by maps: albedo (linear RGB), height (pixels), roughness, metalness.
The camera looks straight down. Lighting = a studio: one large key softbox top-left, a strip light right, a dim
ceiling, plus image-based reflections of those lights (GGX-like lobes whose width grows with roughness),
Schlick Fresnel, height-field shadows and ambient occlusion. Output is tone-mapped sRGB.

Micro-structure (brushing, lathe rings, grooves, paper, rubber, knurling) lives in the height maps, so the
softboxes break up on it exactly like on a photo.
"""
import math

import cv2
import numpy as np
from PIL import Image

KEY = np.array([-0.72, -0.38, 0.58]); KEY /= np.linalg.norm(KEY)
STRIP = np.array([0.74, -0.30, 0.60]); STRIP /= np.linalg.norm(STRIP)
LIGHT_DIR = np.array([-0.55, -0.62, 0.56]); LIGHT_DIR /= np.linalg.norm(LIGHT_DIR)   # sun-like key for shadows
FILL_DIR = np.array([0.6, -0.2, 0.77]); FILL_DIR /= np.linalg.norm(FILL_DIR)


# ----------------------------------------------------------------------------------------- textures
def grid(w, h, cx=0.0, cy=0.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return xx - cx, yy - cy


def rng(seed):
    return np.random.default_rng(seed)


def white(w, h, seed):
    return rng(seed).standard_normal((h, w)).astype(np.float32)


def fbm(w, h, seed, octaves=5, base=64.0, gain=0.5):
    out = np.zeros((h, w), np.float32)
    amp, scale = 1.0, base
    r = rng(seed)
    for _ in range(octaves):
        sw, sh = max(2, int(w / scale) + 2), max(2, int(h / scale) + 2)
        n = r.standard_normal((sh, sw)).astype(np.float32)
        out += amp * cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
        amp *= gain; scale /= 2.0
    return out / 2.0


def brushed(w, h, seed, length=60, strength=1.0, vertical=False):
    n = white(w, h, seed)
    k = (1, length) if vertical else (length, 1)
    b = cv2.blur(n, k) * math.sqrt(length)
    return b * strength * 0.25


def rings(r, seed, period=1.0, jitter=0.4, amp=1.0):
    """concentric micro ridges (lathe / grooves): height as a function of radius only"""
    n = int(r.max()) + 8
    jit = rng(seed).standard_normal(n * 4).astype(np.float32) * jitter
    # phase accumulates with jittered period
    rr = r / period
    idx = np.clip((rr * 4).astype(np.int32), 0, len(jit) - 1)
    return np.sin(2 * np.pi * rr + jit[idx]) * amp


def radial_value(r, seed, scale=1.0, amp=1.0, smooth=2):
    n = int(r.max() * scale) + 8
    t = rng(seed).standard_normal(n).astype(np.float32)
    if smooth > 1:
        t = np.convolve(t, np.ones(smooth) / smooth, mode="same")
    return t[np.clip((r * scale).astype(np.int32), 0, n - 1)] * amp


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def disc(r, rad, aa=1.0):
    return 1.0 - smoothstep(rad - aa, rad + aa, r)


def ring(r, a, b, aa=1.0):
    return smoothstep(a - aa, a + aa, r) * (1 - smoothstep(b - aa, b + aa, r))


def rrect(x, y, x0, y0, x1, y1, rad):
    cx = np.clip(x, x0 + rad, x1 - rad); cy = np.clip(y, y0 + rad, y1 - rad)
    return np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - rad      # signed distance (negative inside)


def dome(dist, height, width):
    """rounded profile rising from an edge (dist <= 0 inside): 0 at the edge -> height inside"""
    t = np.clip(-dist / width, 0, 1)
    return height * np.sqrt(1 - (1 - t) ** 2)


def blur(a, sigma):
    if sigma <= 0:
        return a
    return cv2.GaussianBlur(a, (0, 0), sigma)


# ----------------------------------------------------------------------------------------- shading
def normals(H, strength=1.0):
    gx = cv2.Sobel(H, cv2.CV_32F, 1, 0, ksize=3) / 8.0 * strength
    gy = cv2.Sobel(H, cv2.CV_32F, 0, 1, ksize=3) / 8.0 * strength
    n = np.dstack([-gx, -gy, np.ones_like(H)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n


def env_radiance(R, rough):
    """studio environment seen along reflection vectors R (H,W,3), blurred by roughness"""
    r2 = (rough ** 2)[..., None] if np.ndim(rough) else rough ** 2
    def lobe(C, size, inten):
        cosang = np.clip((R * C).sum(axis=2), -1, 1)
        ang2 = (1 - cosang) * 2.0                     # ~angle^2 for small angles
        w2 = size ** 2 + (r2[..., 0] if np.ndim(r2) else r2) * 1.6
        return inten * np.exp(-ang2 / w2) * (size ** 2 / w2) ** 0.6
    L = lobe(KEY, 0.30, 5.0) + lobe(STRIP, 0.12, 2.6)
    # ceiling and walls: brighter overhead, darker toward the horizon
    up = np.clip(R[..., 2], 0, 1)
    # ceiling bright overhead, a dark band (studio walls / black flags) toward the horizon, faint floor bounce:
    # flat surfaces see the ceiling, curved chrome sweeps through all three -> real contrast
    L += 0.05 + 0.42 * up ** 6 + 0.06 * np.clip(-R[..., 0] - R[..., 1], 0, 1)
    L -= 0.04 * np.exp(-((up - 0.55) / 0.12) ** 2)
    L += 0.05 * np.exp(-((up - 0.15) / 0.10) ** 2)
    # white sweep in front of the deck (product-photo cove): seen by sides and fronts that face the camera
    down = np.clip(-R[..., 2], 0, 1)
    L += 0.55 * np.sqrt(down) * np.clip(R[..., 1] + 0.3, 0, 1)
    L = np.clip(L, 0.0, None)
    return L


def shadow_map(H, steps=28, step_px=2.0, soft=3.0, light=LIGHT_DIR):
    """height-field shadows by ray marching toward the light"""
    dx, dy = light[0], light[1]
    l = math.hypot(dx, dy)
    dx, dy = dx / l, dy / l
    slope = light[2] / l                    # height gained per pixel travelled toward the light
    occ = np.zeros_like(H)
    h, w = H.shape
    for k in range(1, steps + 1):
        d = k * step_px
        M = np.float32([[1, 0, -dx * d], [0, 1, -dy * d]])
        Hs = cv2.warpAffine(H, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        occ = np.maximum(occ, (Hs - H - d * slope) / (soft * (1 + 0.15 * k)))
    return 1.0 - np.clip(occ, 0, 1)


def ao_map(H, radius=12.0, strength=0.06):
    b = blur(H, radius)
    return np.clip(1.0 - np.clip(b - H, 0, None) * strength, 0.25, 1.0)


def aniso_radial(shape, cx, cy, sharp=1.0):
    """reflection of the studio lights in circular grooves (vinyl, lathe-turned metal): the groove walls tilt only
    along the radius, so a light is reflected where the radius lines up with the light's half vector -> a soft
    wedge through the centre for every light (the 'light cross')."""
    h, w = shape
    x, y = grid(w, h, cx, cy)
    r = np.sqrt(x * x + y * y) + 1e-6
    tx, ty = -y / r, x / r                  # tangent of the groove
    V = np.array([0, 0, 1.0])
    out = np.zeros(shape, np.float32)
    for C, size, inten in ((KEY, 0.10, 5.0), (STRIP, 0.05, 2.6)):
        Hh = C + V; Hh = Hh / np.linalg.norm(Hh)
        hxy = math.hypot(Hh[0], Hh[1])
        across = (Hh[0] * tx + Hh[1] * ty)          # part of the half vector the groove cannot tilt toward
        s1 = (size * sharp) ** 2
        out += inten * (np.exp(-across ** 2 / s1) * 0.65 + np.exp(-across ** 2 / (s1 * 9)) * 0.35)
    return out


def shade(albedo, H, rough, metal, normal_strength=1.0, shadows=True, ao=True, exposure=1.0, extra_normal=None,
          shadow_steps=28, ao_radius=12.0, ao_strength=0.06, aniso=None):
    N = normals(H, normal_strength)
    if extra_normal is not None:
        N = N + extra_normal
        N /= np.linalg.norm(N, axis=2, keepdims=True)
    V = np.array([0, 0, 1.0], np.float32)
    ndv = np.clip(N[..., 2], 1e-3, 1)
    R = 2 * ndv[..., None] * N - V
    rough = np.clip(rough, 0.03, 1.0)
    metal = np.clip(metal, 0, 1)[..., None]
    f0 = 0.04 * (1 - metal) + albedo * metal
    fres = f0 + (1 - f0) * ((1 - ndv) ** 5)[..., None] * (1 - rough[..., None]) ** 2
    spec_env = env_radiance(R, rough)
    if aniso is not None:
        amap, acx, acy, asharp = aniso
        spec_env = spec_env * (1 - amap) + aniso_radial(H.shape, acx, acy, asharp) * amap
    spec_env = spec_env[..., None]
    # direct diffuse from key + fill
    nl_key = np.clip((N * LIGHT_DIR).sum(axis=2), 0, 1)
    nl_fill = np.clip((N * FILL_DIR).sum(axis=2), 0, 1)
    sh = shadow_map(H, steps=shadow_steps) if shadows else np.ones_like(H)
    occ = ao_map(H, ao_radius, ao_strength) if ao else np.ones_like(H)
    diffuse = albedo * (1 - metal) * ((nl_key * sh * 1.05 + nl_fill * 0.30 + 0.22) * occ)[..., None]
    spec = fres * spec_env * (0.35 + 0.65 * sh[..., None]) * occ[..., None]
    rgb = (diffuse + spec) * exposure
    return rgb, sh


def tonemap(rgb):
    # ACES-like filmic curve, then sRGB gamma
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    x = np.clip(rgb, 0, None)
    y = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)
    return np.where(y <= 0.0031308, y * 12.92, 1.055 * np.power(y, 1 / 2.4) - 0.055)


def to_image(rgb_linear, alpha=None):
    s = tonemap(rgb_linear)
    a = np.ones(s.shape[:2], np.float32) if alpha is None else np.clip(alpha, 0, 1)
    arr = np.dstack([s, a[..., None]]) * 255
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
