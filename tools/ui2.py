#!/usr/bin/env python3
"""SKRATCHA 2.0 skin: two decks (one view, switched by the DECK parameter), three turntable styles, a real LP with
the JF label, a battle mixer panel, BROWSER, LERNEN (teacher), SETUP and INFO tabs.

    ui2.py <params.json> <out skins dir> <preview dir> <jf_logo.png> <fonts dir>

Re-uses the renderers of make_ui.py (PBR height maps, oblique 3D ray marching) and its TUI.json builders.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_ui as M                     # reads sys.argv[1:6]
from make_ui import (PB, O3, RD, _np, _cv2, Image, ImageDraw, ImageFilter, ImageFont, font, text, save, down,
                     F_BOLD, F_SEMI, F_MED, F_TIT, W, H, SS, OUT, PREV, LOGO, FONTS, P,
                     _maps, _put, _text_mask, _glow, _faceplate_maps, _side_fn, _region_rect, _wgrid,
                     define, act, comp, bounds, focus_comp, label_data, filmstrip, def_display, def_toggle, def_segment,
                     def_readout, def_slider, Tab, DEFS)

CX, CY = M.CX, M.CY
R_PLATTER, R_STROBE_OUT, R_STROBE_IN, R_MAT, R_REC = M.R_PLATTER, M.R_STROBE_OUT, M.R_STROBE_IN, M.R_MAT, M.R_REC
Z_PLATTER, Z_MAT = M.Z_PLATTER, M.Z_MAT
R_LP = R_REC - 3          # the record (12") on the slipmat
Z_LP = Z_MAT + 2.0
R_LAB = 86                # label
Z_LAB = Z_LP + 0.4
LABEL_FRAMES = 48
SILVER, SILVER_BRIGHT, PAINT_WHITE, INK_DARK, ANOD = M.SILVER, M.SILVER_BRIGHT, M.PAINT_WHITE, M.INK_DARK, M.ANOD
AMBER = (255, 181, 46)
GREEN = (60, 235, 110)
LAB_RED = PB.srgb_to_lin([0.42, 0.045, 0.05])
FOIL = PB.srgb_to_lin([1.0, 0.80, 0.42])

STYLES = [
    {"name": "DD SILBER", "sub": "DIRECT DRIVE  ·  QUARTZ LOCK", "plinth": "silver"},
    {"name": "BATTLE", "sub": "BATTLE EDITION  ·  HIGH TORQUE", "plinth": "black"},
    {"name": "RIEMEN 70ER", "sub": "BELT DRIVE  ·  WALNUT 1974", "plinth": "walnut"},
]

PITCH_X, PITCH_Y, PITCH_W, PITCH_H = 716, 344, 72, 268
PANEL = (812, 6, 1274, 622)


# ======================================================================================================
# the deck in 3D
# ======================================================================================================
def _plinth(style, Ww, Hw):
    if style == "silver":
        A, Hm, Rm, Mm = _maps(Ww, Hw, SILVER, 0.0, 0.28, 1.0)
        Hm += PB.brushed(Ww, Hw, 1, length=400, strength=0.14) + PB.white(Ww, Hw, 2) * 0.012 + PB.fbm(Ww, Hw, 2, 4, 220.0) * 0.08
        Rm += PB.fbm(Ww, Hw, 3, 3, 60.0) * 0.015
        ink = (34, 35, 38, 235)
    elif style == "black":
        A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.045, 0.045, 0.05]), 0.0, 0.55, 0.15)
        Hm += PB.fbm(Ww, Hw, 4, 5, 6.0) * 0.18 + PB.fbm(Ww, Hw, 5, 3, 200.0) * 0.06     # fine textured powder coat
        Rm += PB.fbm(Ww, Hw, 6, 3, 40.0) * 0.05
        ink = (226, 228, 232, 235)
    elif style in ("oak", "mahogany"):   # dark oak / glossy mahogany with lacquer
        x, y = PB.grid(Ww, Hw)
        warp = PB.fbm(Ww, Hw, 18, 3, 600.0) * 26.0 + PB.fbm(Ww, Hw, 19, 2, 100.0) * 3.0
        fine = _np.sin((y + warp) * 2 * _np.pi / 6.0)
        broad = _np.sin((y + warp * 1.4) * 2 * _np.pi / 55.0)
        g = PB.brushed(Ww, Hw, 17, length=900, strength=1.0); g = (g - g.min()) / (g.max() - g.min() + 1e-6)
        t = _np.clip(0.45 + 0.08 * fine + 0.14 * broad + 0.5 * (g - 0.5), 0, 1)
        if style == "oak":
            dark = PB.srgb_to_lin([0.10, 0.065, 0.035]); light = PB.srgb_to_lin([0.30, 0.20, 0.10]); rough = 0.38
        else:
            dark = PB.srgb_to_lin([0.16, 0.035, 0.025]); light = PB.srgb_to_lin([0.42, 0.12, 0.07]); rough = 0.14
        A = (dark[None, None, :] * (1 - t[..., None]) + light[None, None, :] * t[..., None]).astype(_np.float32)
        Hm = (fine * 0.04 + PB.white(Ww, Hw, 10) * 0.008).astype(_np.float32)
        Rm = _np.full((Hw, Ww), rough, _np.float32)
        Mm = _np.zeros((Hw, Ww), _np.float32)
        ink = (240, 214, 150, 235)
    elif style == "bakelite":
        A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.07, 0.045, 0.03]), 0.0, 0.12, 0.0)
        Hm += PB.fbm(Ww, Hw, 21, 3, 300.0) * 0.25
        A[:] = A * (1 + PB.fbm(Ww, Hw, 22, 4, 80.0)[..., None] * 0.25)
        ink = (230, 200, 140, 235)
    elif style == "leather":   # 1960s suitcase: teal leatherette
        A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.10, 0.36, 0.38]), 0.0, 0.6, 0.0)
        Hm += PB.fbm(Ww, Hw, 23, 5, 5.0) * 0.5
        A[:] = A * (1 + PB.fbm(Ww, Hw, 24, 3, 200.0)[..., None] * 0.08)
        ink = (245, 238, 220, 240)
    elif style == "gunmetal":
        A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.20, 0.205, 0.215]), 0.0, 0.32, 1.0)
        Hm += PB.brushed(Ww, Hw, 25, length=500, strength=0.16) + PB.white(Ww, Hw, 26) * 0.01
        ink = (232, 190, 90, 240)
    elif style == "white":
        A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.86, 0.87, 0.88]), 0.0, 0.18, 0.0)
        Hm += PB.fbm(Ww, Hw, 27, 3, 400.0) * 0.05
        ink = (40, 90, 170, 240)
    elif style == "glass":
        A, Hm, Rm, Mm = _maps(Ww, Hw, PB.srgb_to_lin([0.015, 0.016, 0.02]), 0.0, 0.05, 0.0)
        Hm += PB.fbm(Ww, Hw, 28, 2, 900.0) * 0.03
        ink = (90, 240, 255, 245)
    else:   # walnut veneer, satin lacquer
        x, y = PB.grid(Ww, Hw)
        warp = PB.fbm(Ww, Hw, 8, 3, 700.0) * 22.0 + PB.fbm(Ww, Hw, 12, 2, 120.0) * 3.0
        fine = _np.sin((y + warp) * 2 * _np.pi / 7.0)
        broad = _np.sin((y + warp * 1.3) * 2 * _np.pi / 70.0)
        g = PB.brushed(Ww, Hw, 7, length=900, strength=1.0)
        g = (g - g.min()) / (g.max() - g.min() + 1e-6)
        t = _np.clip(0.45 + 0.07 * fine + 0.14 * broad + 0.55 * (g - 0.5), 0, 1)
        dark = PB.srgb_to_lin([0.13, 0.065, 0.035]); light = PB.srgb_to_lin([0.36, 0.20, 0.10])
        A = (dark[None, None, :] * (1 - t[..., None]) + light[None, None, :] * t[..., None]).astype(_np.float32)
        Hm = (fine * 0.04 + PB.white(Ww, Hw, 10) * 0.008).astype(_np.float32)
        Rm = (0.24 + 0.06 * (1 - t)).astype(_np.float32)
        Mm = _np.zeros((Hw, Ww), _np.float32)
        ink = (236, 222, 196, 235)
    return A, Hm, Rm, Mm, ink


def deck_maps(style, design=None):
    S = SS
    Ww, Hw, x, y = _wgrid(S)
    design = design or {}
    A, Hm, Rm, Mm, ink = _plinth(style, Ww, Hw)
    vin = design.get("vinyl", {"col": [0.014, 0.014, 0.016], "rough": 0.14, "kind": "plain"})
    lab_col = PB.srgb_to_lin(design.get("label", [0.42, 0.045, 0.05]))
    Yw = lambda ly: O3.Y(ly) * S

    # ---------------- platter, slipmat, the LP
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
    felt = M._felt_height(Ww, Hw, 7, S)
    _put(A, Hm, Rm, Mm, mat, M.FELT_COL, None, 0.95, 0.0)
    edge = PB.smoothstep(R_PLATTER * S - 4 * S, R_PLATTER * S, r)
    hp = lip * (top - 3 * S * edge ** 2 + lathe)
    hp += band * (top - 4 * S + (r - R_STROBE_IN * S) / ((R_STROBE_OUT - R_STROBE_IN) * S) * 4 * S + lathe * 0.5)
    hp += step * (top - 4.5 * S + lathe)
    hp += gapm * (Z_MAT * S - 2 * S)
    hp += mat * (Z_MAT * S + felt)

    # the record: glossy black vinyl, grooves (fine radial ridges), track gaps, a lead-in and a shiny run-out
    lp = PB.disc(r, R_LP * S, 0.8)
    rr = r / S
    gaps = [122, 151, 176, 199, 221, 238]
    gap = _np.zeros_like(r)
    for g in gaps:
        gap = _np.maximum(gap, _np.exp(-((rr - g) / 1.1) ** 2))
    leadin = PB.ring(r, (R_LP - 5) * S, R_LP * S, 0.8)
    runout = PB.ring(r, (R_LAB + 4) * S, 104 * S, 1.2)
    grooves = PB.radial_value(r, 35, scale=1.8, amp=1.0, smooth=1) * (1 - gap) * (1 - runout) * (1 - leadin) * 0.05 * S
    vcol = PB.srgb_to_lin(vin["col"])
    _put(A, Hm, Rm, Mm, lp, vcol, None, vin["rough"], 0.0)
    if vin["kind"] == "marble":
        mb = PB.fbm(Ww, Hw, 61, 5, 40.0); mb = (mb - mb.min()) / (mb.max() - mb.min() + 1e-6)
        swirl = _np.sin((mb * 9.0 + _np.arctan2(py, px) * 2.0)) * 0.5 + 0.5
        c2 = PB.srgb_to_lin(vin["col2"])
        mix = (swirl ** 3 * lp)[..., None]
        A[:] = A * (1 - mix) + c2[None, None, :] * mix
    elif vin["kind"] == "timecode":
        band_ = (_np.sin(r / S * 2 * _np.pi / 1.6) > 0.3).astype(_np.float32)
        tc = PB.ring(r, 110 * S, (R_LP - 8) * S, 1.0) * band_ * 0.55
        c2 = PB.srgb_to_lin(vin["col2"])
        A[:] = A * (1 - tc[..., None]) + c2[None, None, :] * tc[..., None]
    elif vin["kind"] == "splatter":
        sp = (PB.blur(PB.white(Ww, Hw, 63), 1.6 * S) > 0.085).astype(_np.float32) * lp
        c2 = PB.srgb_to_lin(vin["col2"])
        A[:] = A * (1 - sp[..., None]) + c2[None, None, :] * sp[..., None]
    Rm[:] = Rm * (1 - lp) + lp * (vin["rough"] - 0.01 + 0.10 * (1 - gap) * (1 - runout) * (1 - leadin) - 0.06 * runout)
    rim = PB.smoothstep((R_LP - 2.5) * S, R_LP * S, r)
    hlp = Z_LP * S - rim ** 2 * 1.6 * S + grooves - leadin * 0.25 * S
    # label (raised a little), red paper; the turning print is the label film strip
    lab = PB.disc(r, R_LAB * S, 0.8)
    _put(A, Hm, Rm, Mm, lab, lab_col, None, 0.65, 0.0)
    hlab = Z_LAB * S + PB.fbm(Ww, Hw, 37, 5, 24.0) * 0.10 * S
    spindle = PB.disc(r, 4.2 * S, 0.6)
    _put(A, Hm, Rm, Mm, spindle, SILVER_BRIGHT, None, 0.08, 1.0)
    hsp = Z_LAB * S + PB.dome(r - 4.2 * S, 7 * S, 2.5 * S)
    hrec = hlp * (1 - lab) + hlab * lab
    hrec = hrec * (1 - spindle) + hsp * spindle
    hp = hp * (1 - lp) + hrec * lp
    Hm[:] = _np.where(plat > 0.5, hp, Hm)

    # ---------------- target light, strobe-lamp dial
    tx, ty = 56 * S, Yw(54)
    tr = _np.sqrt((x - tx) ** 2 + (y - ty) ** 2)
    tl = PB.disc(tr, 34 * S)
    _put(A, Hm, Rm, Mm, tl, SILVER_BRIGHT, None, 0.05, 1.0)
    Hm[:] = Hm * (1 - tl) + tl * (PB.dome(tr - 34 * S, 10 * S, 6 * S) + PB.radial_value(tr, 41, 1.2, 0.05 * S))
    Hm[:] = Hm - PB.disc(tr, 6 * S) * 2 * S
    kx, ky = 50 * S, Yw(470)
    kr = _np.sqrt((x - kx) ** 2 + (y - ky) ** 2)
    kth = _np.arctan2(y - ky, x - kx)
    kd = PB.disc(kr, 22 * S)
    _put(A, Hm, Rm, Mm, kd, PB.srgb_to_lin([0.04, 0.04, 0.045]), None, 0.4, 0.2)
    Hm[:] = Hm * (1 - kd) + kd * (PB.dome(kr - 22 * S, 12 * S, 4 * S) + _np.cos(kth * 70) * 0.5 * S * PB.ring(kr, 16 * S, 22 * S))

    # ---------------- tone-arm base, anti-skate, lift lever, arm rest
    bx, by = 708 * S, Yw(124)
    br = _np.sqrt((x - bx) ** 2 + (y - by) ** 2)
    ringo = PB.disc(br, 94 * S)
    ring_col = {"black": [0.08, 0.08, 0.085], "glass": [0.05, 0.05, 0.06], "oak": [0.75, 0.55, 0.25], "bakelite": [0.72, 0.52, 0.24],
                "gunmetal": [0.70, 0.55, 0.22]}.get(style)
    _put(A, Hm, Rm, Mm, ringo, PB.srgb_to_lin(ring_col) if ring_col else SILVER_BRIGHT, None, 0.12, 1.0)
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
    lev = _np.zeros((Hw, Ww), _np.uint8)
    _cv2.line(lev, (int(770 * S), int(Yw(176))), (int(792 * S), int(Yw(214))), 255, int(7 * S))
    levm = PB.blur(lev.astype(_np.float32) / 255, 0.8)
    _put(A, Hm, Rm, Mm, levm, PB.srgb_to_lin([0.03, 0.03, 0.035]), None, 0.35, 0.1)
    Hm[:] = _np.maximum(Hm, levm * 16 * S)
    ar2 = PB.rrect(x, y, 744 * S, Yw(286), 764 * S, Yw(326), 7 * S)
    arest = 1 - PB.smoothstep(-1, 1, ar2)
    _put(A, Hm, Rm, Mm, arest, PB.srgb_to_lin([0.03, 0.03, 0.032]), None, 0.6, 0.0)
    Hm[:] = Hm * (1 - arest) + arest * PB.dome(ar2, 22 * S, 5 * S)

    # ---------------- pitch slot (bottom right of the deck, like the real thing)
    fx0, fy0, fx1, fy1 = PITCH_X * S, Yw(PITCH_Y), (PITCH_X + PITCH_W) * S, Yw(PITCH_Y + PITCH_H)
    slot = ((x > fx0 + 31 * S) & (x < fx0 + 41 * S) & (y > fy0 + 18 * S) & (y < fy1 - 18 * S)).astype(_np.float32)
    slot = PB.blur(slot, 0.7 * S)
    _put(A, Hm, Rm, Mm, slot, PB.srgb_to_lin([0.01, 0.01, 0.01]), -6 * S, 0.9, 0.0)
    ink2 = []
    for k, lab_ in [(8, "+8"), (4, "4"), (0, "0"), (-4, "4"), (-8, "-8")]:
        yk = PITCH_Y + 20 + (8 - k) / 16 * (PITCH_H - 40)
        ink2.append(((PITCH_X - 4) * S, (yk + 4) * S, lab_, font(F_SEMI, 10 * S), "rs", 0))
        tick = ((_np.abs(y - Yw(yk)) < 0.7 * S) & (x > (PITCH_X + 16) * S) & (x < (PITCH_X + 26) * S)).astype(_np.float32)
        _put(A, Hm, Rm, Mm, tick, INK_DARK if style in ("silver", "white") else PAINT_WHITE, None, 0.6, 0.0)
    ink2.append(((PITCH_X + PITCH_W / 2) * S, (PITCH_Y - 8) * S, "PITCH", font(F_SEMI, 11 * S), "mm", S))

    # ---------------- the battle mixer: black anodised plate, LCD glass, crossfader slot, slot-pad well
    x0, y0, x1, y1 = PANEL
    pd = PB.rrect(x, y, x0 * S, Yw(y0), x1 * S, Yw(y1), 14 * S)
    face = 1 - PB.smoothstep(-1, 1, pd)
    _put(A, Hm, Rm, Mm, face, ANOD, None, 0.32, 0.55)
    Hm[:] = Hm * (1 - face) + face * (PB.dome(pd, 5 * S, 4 * S) + PB.brushed(Ww, Hw, 77, 160, 0.5) * 0.5)
    for sx, sy in [(x0 + 12, y0 + 12), (x1 - 12, y0 + 12), (x0 + 12, y1 - 12), (x1 - 12, y1 - 12)]:
        sr_ = _np.sqrt((x - sx * S) ** 2 + (y - Yw(sy)) ** 2)
        sm = PB.disc(sr_, 4.5 * S)
        _put(A, Hm, Rm, Mm, sm, SILVER, None, 0.25, 1.0)
        Hm[:] = Hm * (1 - sm) + sm * (6 * S + PB.dome(sr_ - 4.5 * S, 2 * S, 3 * S))
    lcds = [(820, 12, 1268, 60), (998, 594, 1268, 622)]
    for (a0, b0, a1, b1) in lcds:
        ld = PB.rrect(x, y, a0 * S, Yw(b0), a1 * S, Yw(b1), 7 * S)
        lcd = 1 - PB.smoothstep(-1, 1, ld)
        bez = (1 - PB.smoothstep(-1, 1, ld - 3 * S)) - lcd
        _put(A, Hm, Rm, Mm, bez, PB.srgb_to_lin([0.02, 0.02, 0.022]), None, 0.4, 0.3)
        Hm[:] = Hm + bez * 1.0 * S
        _put(A, Hm, Rm, Mm, lcd, PB.srgb_to_lin([0.010, 0.009, 0.007]), 4 * S, 0.04, 0.0)
    # recessed well for the 4 x 4 pad map (exactly like the MPC pads)
    wd = PB.rrect(x, y, 816 * S, Yw(64), 1272 * S, Yw(344), 8 * S)
    wl = 1 - PB.smoothstep(-1, 1, wd)
    _put(A, Hm, Rm, Mm, wl, PB.srgb_to_lin([0.02, 0.02, 0.022]), None, 0.6, 0.2)
    Hm[:] = Hm - wl * PB.dome(wd, 2.5 * S, 3 * S)
    # crossfader slot
    cfs = PB.rrect(x, y, 896 * S, Yw(510), 1176 * S, Yw(518), 4 * S)
    cfm = 1 - PB.smoothstep(-1, 1, cfs)
    _put(A, Hm, Rm, Mm, cfm, PB.srgb_to_lin([0.004, 0.004, 0.004]), -5 * S, 0.9, 0.0)
    for k in range(11):
        xx = 896 + k * 28
        tk = ((_np.abs(x - xx * S) < 0.7 * S) & (y > Yw(486)) & (y < Yw(494))).astype(_np.float32)
        _put(A, Hm, Rm, Mm, tk, PAINT_WHITE, None, 0.6, 0.0)

    f12, f11 = font(F_SEMI, 12 * S), font(F_SEMI, 11 * S)
    panel_ink = [
        (830 * S, 498 * S, "A", font(F_BOLD, 22 * S), "mm", 0), (1252 * S, 498 * S, "B", font(F_BOLD, 22 * S), "mm", 0),
        (1036 * S, 476 * S, "CROSSFADER", f12, "mm", 2 * S),
    ]
    deck_ink = []
    an = (lip + step) * 0.8 + band * 0.4 + ringo * (1 - well) * 0.7 + lp * (1 - lab) * (1 - gap * 0.85) * (1 - runout) * 0.9
    maps = {"albedo": A, "H": Hm, "rough": Rm, "metal": Mm, "aniso": an, "center": (pcx, pcy)}
    maps = O3.prepare(maps, shadow_steps=40, ao_radius=14 * S, ao_strength=0.05)
    return maps, ink, deck_ink + ink2, panel_ink


def draw_deck(style, design=None):
    S = SS
    maps, ink, deck_ink, panel_ink = deck_maps(style, design)
    pcx, pcy = maps["center"]
    rgb, _, (hx, hy, hz) = O3.render(maps, W * S, H * S, 0, 0, aniso=(maps["aniso"], pcx, pcy, 1.0), side=_side_fn(maps, None, S))
    img = PB.to_image(rgb)
    _glow(img, 96 * S, int(O3.screen_v(O3.Y(452) * S, 0)), 70 * S, (255, 40, 20), 85)
    if design and design.get("neon"):
        # LED ring around the platter and a glowing record edge
        g = Image.new("RGBA", img.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        cxs, cys = CX * S, O3.screen_v(O3.Y(CY) * S, Z_PLATTER * S)
        for rad, col, wdt in [((R_PLATTER + 6) * S, (40, 230, 255, 255), 5 * S), ((R_LP + 1) * S, (255, 60, 220, 200), 3 * S)]:
            gd.ellipse([cxs - rad, cys - rad * O3.COS, cxs + rad, cys + rad * O3.COS], outline=col, width=int(wdt))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(6 * S))); img.alpha_composite(g)
    d = ImageDraw.Draw(img)
    for (xx, yy, t_, f_, anc, sp_) in deck_ink:
        text(d, (xx, yy), t_, f_, ink, anc, sp_)
    for (xx, yy, t_, f_, anc, sp_) in panel_ink:
        text(d, (xx, yy), t_, f_, (218, 220, 224, 230), anc, sp_)
    return down(img), maps, (hx, hy, hz), rgb


def draw_label_frames(maps, hits, design=None):
    design = design or {}
    """the LP label: red paper with the gold JF logo and a foil ring, turning; shaded on the deck's 3D hits"""
    S = SS
    hx, hy, hz = hits
    pcx, pcy = maps["center"]
    rx, ry, rw, rh = _region_rect(CX, CY, R_LAB + 1, Z_LAB)
    ry -= 6; rh += 8                                     # spindle tip
    sl = (slice(ry * S, (ry + rh) * S), slice(rx * S, (rx + rw) * S))
    shx, shy, shz = hx[sl], hy[sl], hz[sl]
    dx, dy = shx - pcx, shy - pcy
    rr = _np.sqrt(dx * dx + dy * dy)
    on_lab = (rr < (R_LAB + 0.5) * S) & (shz > (Z_LP - 1) * S)
    # label artwork in label coordinates (tile 2R x 2R, centre = spindle)
    T = int(2 * R_LAB * S) + 8
    art = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    ad = ImageDraw.Draw(art)
    c = T / 2
    lg = Image.open(LOGO).convert("RGBA"); lg = lg.crop(lg.getbbox())
    lh = int(98 * S); lw = int(lg.width * lh / lg.height)
    art.paste(Image.new("RGBA", (lw, lh), (255, 255, 255, 255)), (int(c - lw / 2 - 2 * S), int(c - lh / 2 - 8 * S)), lg.resize((lw, lh), Image.LANCZOS))
    ad.ellipse([c - 80 * S, c - 80 * S, c + 80 * S, c + 80 * S], outline=(255, 255, 255, 255), width=int(1.6 * S))
    ad.ellipse([c - 74 * S, c - 74 * S, c + 74 * S, c + 74 * S], outline=(255, 255, 255, 255), width=int(0.8 * S))
    fs = font(F_BOLD, 9 * S)
    # small curved print along the bottom: SKRATCHA · 33 1/3 RPM · SIDE A
    msg = design.get("label_text", "SKRATCHA RECORDS  ·  33 1/3 RPM  ·  STEREO  ·  JJ DA PLUG")
    ang0 = math.radians(200)
    span = math.radians(140)
    for i, ch in enumerate(msg):
        a = ang0 - span * i / (len(msg) - 1)
        gx_ = c + 66 * S * math.cos(a); gy_ = c - 66 * S * math.sin(a)
        g = Image.new("RGBA", (int(16 * S), int(16 * S)), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((8 * S, 8 * S), ch, font=fs, fill=(255, 255, 255, 255), anchor="mm")
        g = g.rotate(math.degrees(a) - 90, resample=Image.BICUBIC)
        art.alpha_composite(g, (int(gx_ - 8 * S), int(gy_ - 8 * S)))
    for i, s_ in enumerate(["SIDE A", "45 / 33"]):
        ad.text((c + (-44 if i == 0 else 44) * S, c + 46 * S), s_, font=font(F_BOLD, 8 * S), fill=(255, 255, 255, 255), anchor="mm")
    foil = _np.asarray(art.split()[3]).astype(_np.float32) / 255
    speck = PB.blur(PB.white(T, T, 91), 0.7 * S)
    frames = []
    base_maps = {"albedo": maps["albedo"], "rough": maps["rough"], "metal": maps["metal"], "gx": maps["gx"], "gy": maps["gy"]}
    design = design or {}
    def shade_flat(col, rough, metal):
        return O3.shade_hits({"albedo": _np.zeros_like(maps["albedo"]) + col, "rough": _np.full_like(maps["rough"], rough),
                              "metal": (_np.ones_like if metal else _np.zeros_like)(maps["metal"]), "gx": maps["gx"], "gy": maps["gy"]},
                             shx, shy, shz, shadows=maps["shadow"], ao=maps["ao"])
    paper1 = shade_flat(PB.srgb_to_lin(design.get("label", [0.42, 0.045, 0.05])), 0.62, False)
    paper2 = shade_flat(PB.srgb_to_lin(design["label2"]), 0.5, False) if design.get("label2") else None
    lmetal = design.get("logo_metal", True)
    gold = shade_flat(PB.srgb_to_lin(design.get("logo", [1.0, 0.80, 0.42])), 0.22 if lmetal else 0.55, lmetal)
    if design.get("logo_glow"):
        gold = gold * 0.4 + PB.srgb_to_lin(design.get("logo", [1, 1, 1]))[None, None, :] * 1.6
    gx_t, gy_t = _np.meshgrid(_np.arange(T, dtype=_np.float32), _np.arange(T, dtype=_np.float32))
    grad = _np.clip((gx_t + gy_t) / (2.0 * T), 0, 1)       # diagonal gradient across the label (turns with it)
    for k in range(LABEL_FRAMES):
        ang = math.radians(k * 360.0 / LABEL_FRAMES)       # clockwise as seen from above
        ca, sa = math.cos(-ang), math.sin(-ang)
        ux = dx * ca - dy * sa + c
        uy = dx * sa + dy * ca + c
        fm = O3.remap(foil, ux, uy, _cv2.BORDER_CONSTANT)
        sp = O3.remap(speck, ux, uy, _cv2.BORDER_CONSTANT)
        paper = paper1
        if paper2 is not None:
            gt = O3.remap(grad, ux, uy, _cv2.BORDER_REPLICATE)[..., None]
            paper = paper1 * (1 - gt) + paper2 * gt
        paper = paper * (1 + 0.05 * sp)[..., None]
        rgb = paper * (1 - fm[..., None]) + gold * fm[..., None]
        # spindle stays chrome (rotationally symmetric)
        spin = (rr < 4.6 * S)
        if k == 0:
            spin_rgb = O3.shade_hits(base_maps, shx, shy, shz, shadows=maps["shadow"], ao=maps["ao"])
        rgb = _np.where(spin[..., None], spin_rgb, rgb)
        alpha = (on_lab | spin).astype(_np.float32)
        frames.append(down(PB.to_image(rgb, alpha), (rw, rh)))
    strip = Image.new("RGBA", (rw, rh * LABEL_FRAMES), (0, 0, 0, 0))
    for k, fr in enumerate(frames):
        strip.paste(fr, (0, k * rh))
    return strip, frames, (rx, ry, rw, rh)


# ======================================================================================================
# small parts (2D with light shading)
# ======================================================================================================
def slot_pad(w, h, num, on):
    S = 3
    img = M._key_pbr(w, h, "", on, led=False, style="dark").resize((w * S, h * S), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    if on:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).rounded_rectangle([5 * S, 5 * S, (w - 5) * S, (h - 8) * S], 8 * S, outline=AMBER + (255,), width=int(3 * S))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(3 * S)))
        img.alpha_composite(g)
    d = ImageDraw.Draw(img)
    d.text((12 * S, 10 * S), str(num), font=font(F_BOLD, 17 * S), fill=(AMBER + (255,)) if on else (150, 152, 156, 255), anchor="la")
    return img.resize((w, h), Image.LANCZOS)


def crossfader_strip(w=340, h=72, frames=61):
    """cap only (the slot is in the panel): a battle-mixer fader knob, ribbed rubber over chrome"""
    S = 3
    cw_, ch_ = 34 * S, 54 * S
    gx, gy = PB.grid(cw_, ch_)
    dist = PB.rrect(gx, gy, 0, 0, cw_, ch_, 6 * S)
    capm = 1 - PB.smoothstep(-1, 1, dist)
    ridges = _np.cos(gx / S * 2 * _np.pi / 3.2) * 0.5 * S
    A, Hm, Rm, Mm = _maps(cw_, ch_, PB.srgb_to_lin([0.035, 0.035, 0.04]), 0.0, 0.5, 0.0)
    Hm = capm * (PB.dome(dist, 12 * S, 6 * S) + ridges * PB.smoothstep(-28 * S, -8 * S, dist))
    line = (_np.abs(gx - cw_ / 2) < 1.3 * S) & (dist < -4 * S)
    A[line] = PB.srgb_to_lin([1.0, 0.70, 0.18]); Rm[line] = 0.3; Hm[line] += 0.6 * S
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=8, ao_radius=2 * S)
    cap = PB.to_image(rgb, capm)
    capsh = PB.to_image(_np.zeros((ch_, cw_, 3), _np.float32), PB.blur(capm, 4 * S) * 0.8)
    out = []
    x_l, x_r = 896 - 860 + 0, 1176 - 860       # slot ends relative to the component (x 860)
    for k in range(frames):
        v = k / (frames - 1)
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        xc = x_l + v * (x_r - x_l)
        img.alpha_composite(capsh, (int((xc - 17 + 3) * S), int((h / 2 - 27 + 6) * S)))
        img.alpha_composite(cap, (int((xc - 17) * S), int((h / 2 - 27) * S)))
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def curve_strip(w=112, h=50, frames=21):
    """little graph of the crossfader curve: A and B gain over the travel"""
    out = []
    S = 3
    for k in range(frames):
        c = k / (frames - 1)
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], 6 * S, fill=(6, 6, 5, 255), outline=(30, 30, 32, 255), width=S)
        def g(xo):
            lag = 0.01
            if xo <= lag: return 0.0
            u = (xo - lag) / (1 - lag)
            wdt = 1.0 - 0.985 * (c ** 0.6)
            return math.sin(1.5707963 * min(1.0, u / max(0.01, wdt)))
        for col, side in ((AMBER, 0), ((90, 200, 255), 1)):
            pts = []
            for i in range(101):
                p = i / 100
                o = 1 - p if side == 0 else p
                pts.append(((6 + p * (w - 12)) * S, (h - 7 - g(o) * (h - 14)) * S))
            d.line(pts, fill=col + (255,), width=int(2 * S), joint="curve")
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def led_strip(w, h, colour, frames=2):
    out = []
    for k in range(frames):
        img = Image.new("RGBA", (w * 3, h * 3), (0, 0, 0, 0))
        RD.led_lens(ImageDraw.Draw(img), w * 1.5, h * 1.5, min(w, h) * 0.42, colour, k == 1, img)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def teach_strip(w, h, colour, label, frames=33):
    """a touch-strip picture with a glowing dot (frame 0 = no dot)"""
    out = []
    S = 2
    for k in range(frames):
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], 10 * S, fill=(10, 10, 11, 255), outline=(44, 45, 48, 255), width=2 * S)
        for i in range(33):
            xx = (16 + i * (w - 32) / 32) * S
            d.line([(xx, (h - 12) * S), (xx, (h - (18 if i % 8 == 0 else 14)) * S)], fill=(70, 72, 76, 255), width=S)
        d.text((14 * S, 8 * S), label, font=font(F_SEMI, 12 * S), fill=(140, 142, 146, 255), anchor="la")
        if k > 0:
            p = (k - 1) / (frames - 2)
            xx = (16 + p * (w - 32)) * S
            g = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse([xx - 22 * S, h / 2 * S - 22 * S, xx + 22 * S, h / 2 * S + 22 * S], fill=colour + (150,))
            img.alpha_composite(g.filter(ImageFilter.GaussianBlur(8 * S)))
            d = ImageDraw.Draw(img)
            d.ellipse([xx - 12 * S, h / 2 * S - 12 * S, xx + 12 * S, h / 2 * S + 12 * S], fill=colour + (255,), outline=(255, 255, 255, 200), width=S)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def beat_strip(w, h, frames=9):
    out = []
    for k in range(frames):
        img = Image.new("RGBA", (w * 3, h * 3), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i in range(8):
            cx = (w / 16 + i * w / 8) * 3
            col = (255, 70, 40) if i in (0, 4) else GREEN
            d = RD.led_lens(d, cx, h * 1.5, h * 0.95, col, k == i + 1, img)
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def stars_strip(w, h, frames=4):
    out = []
    for k in range(frames):
        img = Image.new("RGBA", (w * 3, h * 3), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i in range(3):
            cx, cy, R = (w / 6 + i * w / 3) * 3, h * 1.5, h * 1.35
            pts = []
            for j in range(10):
                a = -math.pi / 2 + j * math.pi / 5
                rad = R if j % 2 == 0 else R * 0.45
                pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
            if i < k:
                g = Image.new("RGBA", img.size, (0, 0, 0, 0))
                ImageDraw.Draw(g).polygon(pts, fill=(255, 200, 60, 200))
                img.alpha_composite(g.filter(ImageFilter.GaussianBlur(6)))
                d = ImageDraw.Draw(img)
                d.polygon(pts, fill=(255, 196, 50, 255), outline=(255, 240, 180, 255))
            else:
                d.polygon(pts, fill=(30, 30, 32, 255), outline=(90, 90, 96, 255))
        out.append(img.resize((w, h), Image.LANCZOS))
    strip = Image.new("RGBA", (w, h * frames), (0, 0, 0, 0))
    for k, fr in enumerate(out):
        strip.paste(fr, (0, k * h))
    return strip, out


def deck_badge(letter, style):
    S = 3
    w, h = 96, 44
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * S, 2 * S, (w - 2) * S, (h - 2) * S], 8 * S, fill=(12, 12, 13, 235), outline=(70, 70, 74, 255), width=S)
    d.text((14 * S, h / 2 * S), "DECK", font=font(F_SEMI, 14 * S), fill=(170, 172, 176, 255), anchor="lm")
    d.text(((w - 22) * S, h / 2 * S), letter, font=font(F_BOLD, 30 * S), fill=AMBER + (255,), anchor="mm")
    return img.resize((w, h), Image.LANCZOS)


# ======================================================================================================
# flat panel pages (BROWSER, LERNEN, SETUP)
# ======================================================================================================
def panel_page(boxes, lcds, items_fn, wells=()):
    S = SS
    w, h = W * S, H * S
    A, Hm, Rm, Mm = _maps(w, h, SILVER, 0.0, 0.30, 1.0)
    x, y = PB.grid(w, h)
    Hm += PB.brushed(w, h, 61, length=400, strength=0.16) + PB.white(w, h, 62) * 0.015 + PB.fbm(w, h, 62, 4, 120.0) * 0.3
    items = []
    for i, (box, t) in enumerate(boxes):
        _faceplate_maps(A, Hm, Rm, Mm, x, y, box, S, 70 + i)
        if t:
            items.append(((box[0] + 30) * S, (box[1] + 12) * S, t, font(F_BOLD, 18 * S), "la", 2 * S))
    for (a0, b0, a1, b1) in lcds:
        ld = PB.rrect(x, y, a0 * S, b0 * S, a1 * S, b1 * S, 8 * S)
        lcd = 1 - PB.smoothstep(-1, 1, ld)
        bez = (1 - PB.smoothstep(-1, 1, ld - 3 * S)) - lcd
        _put(A, Hm, Rm, Mm, bez, PB.srgb_to_lin([0.03, 0.03, 0.033]), None, 0.4, 0.3)
        Hm[:] = Hm + bez * 1.0 * S
        _put(A, Hm, Rm, Mm, lcd, PB.srgb_to_lin([0.010, 0.009, 0.007]), -1 * S, 0.04, 0.0)
    for (a0, b0, a1, b1) in wells:
        wd = PB.rrect(x, y, a0 * S, b0 * S, a1 * S, b1 * S, 8 * S)
        wl = 1 - PB.smoothstep(-1, 1, wd)
        _put(A, Hm, Rm, Mm, wl, PB.srgb_to_lin([0.02, 0.02, 0.022]), None, 0.6, 0.2)
        Hm[:] = Hm - wl * PB.dome(wd, 2.5 * S, 3 * S)
    items += items_fn(S)
    pm = _text_mask(w, h, items)
    _put(A, Hm, Rm, Mm, pm, PAINT_WHITE, None, 0.55, 0.0)
    Hm[:] = Hm + pm * 0.15 * S
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=20, ao_radius=12 * S, ao_strength=0.05)
    return down(PB.to_image(rgb))


def draw_info_bg():
    """INFO: the LP with the gold JF label, CREATOR: JJ DA PLUG, the pad map"""
    S = SS
    w, h = W * S, H * S
    A, Hm, Rm, Mm = _maps(w, h, PB.srgb_to_lin([0.05, 0.05, 0.055]), 0.0, 0.35, 0.5)
    x, y = PB.grid(w, h)
    Hm += PB.brushed(w, h, 81, length=160, strength=0.8)
    cx, cy, R = 640 * S, 286 * S, 236 * S
    r = _np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    rec = PB.disc(r, R)
    rr = r / S
    gap = _np.zeros_like(r)
    for g in _np.sort(PB.rng(33).uniform(118, 228, 6)):
        gap = _np.maximum(gap, _np.exp(-((rr - g) / 1.3) ** 2))
    runout = PB.ring(r, 92 * S, 106 * S, 1.5)
    grooves = PB.radial_value(r, 35, scale=0.9, amp=1.0, smooth=1) * (1 - gap) * (1 - runout) * 0.07 * S
    _put(A, Hm, Rm, Mm, rec, PB.srgb_to_lin([0.018, 0.018, 0.02]), None, 0.16, 0.0)
    Hm[:] = Hm * (1 - rec) + rec * (8 * S + PB.dome(r - R, 2 * S, 3 * S) + grooves + PB.fbm(w, h, 36, 3, 300.0) * 1.2 * S)
    Rm[:] = Rm * (1 - rec) + rec * (0.16 + 0.10 * (1 - gap) * (1 - runout) - 0.08 * runout)
    lab = PB.disc(r, 90 * S)
    _put(A, Hm, Rm, Mm, lab, LAB_RED, None, 0.65, 0.0)
    Hm[:] = Hm * (1 - lab) + lab * (8 * S + PB.fbm(w, h, 37, 5, 24.0) * 0.18 * S)
    lg = Image.open(LOGO).convert("RGBA"); lg = lg.crop(lg.getbbox())
    lh = 120 * S; lw = int(lg.width * lh / lg.height)
    lgm = Image.new("L", (w, h), 0)
    lgm.paste(lg.resize((lw, lh), Image.LANCZOS).split()[3], (int(cx - lw / 2 - 4 * S), int(cy - lh / 2)))
    ringm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(ringm).ellipse([cx - 84 * S, cy - 84 * S, cx + 84 * S, cy + 84 * S], outline=255, width=int(2.2 * S))
    foil = _np.maximum(_np.asarray(lgm), _np.asarray(ringm)).astype(_np.float32) / 255
    _put(A, Hm, Rm, Mm, foil, FOIL, None, 0.18, 1.0)
    Hm[:] = Hm + PB.blur(foil, 0.8 * S) * 0.9 * S
    items = [(640 * S, 560 * S, "SKRATCHA  ·  CREATOR: JJ DA PLUG", font(F_BOLD, 24 * S), "mm", 3 * S),
             (640 * S, 592 * S, "VERSION 2.7.1  ·  10 TURNTABLES  ·  MPC PLUGIN SDK", font(F_MED, 14 * S), "mm", S)]
    left = ["PADS = BILDSCHIRM (4 x 4)", "13 DECK A  14 DECK B  15 REV  16 SLIP", "9 CUT   10 HOLD   11 CUE   12 START",
            "1-8  SAMPLES (5-8 UEBER 1-4)", "BATTLE: LINKS A, RECHTS B (GESPIEGELT)", "HOLD + CUE = CUE SETZEN",
            "ANSICHT-TASTE = LAYOUT", "RUNDE LEUCHTE = TURNTABLE-AERA"]
    for i, s in enumerate(left):
        items.append((34 * S, (52 + i * 30) * S, s, font(F_BOLD if i == 0 else F_MED, 16 * S), "la", 0))
    right = ["SO GEHT'S", "TOUCH STRIP AUF PITCH BEND", "STRIP = HAND AUF DER PLATTE", "LOSLASSEN = TELLER LAEUFT WEITER",
             "SLIP: PLATTE LAEUFT IM HINTERGRUND", "Q-LINK 1 = CROSSFADER", "LERNEN: DEMO, DANN DU", "ALLES ALS MIDI AUFNEHMBAR"]
    for i, s in enumerate(right):
        items.append((1246 * S, (52 + i * 30) * S, s, font(F_BOLD if i == 0 else F_MED, 16 * S), "ra", 0))
    pm = _text_mask(w, h, items)
    _put(A, Hm, Rm, Mm, pm, PAINT_WHITE, None, 0.55, 0.0)
    an = rec * (1 - gap * 0.85) * (1 - runout) * (1 - lab) * 0.85
    rgb, _ = PB.shade(A, Hm, Rm, Mm, shadows=True, ao=True, shadow_steps=20, ao_radius=12 * S, ao_strength=0.05, aniso=(an, cx, cy, 1.0))
    return down(PB.to_image(rgb))


# ======================================================================================================
# TUI helpers
# ======================================================================================================
def cond(tab, *handles):
    """make the last placed component visible only while all handles are valid"""
    tab.items[-1]["bounds"]["additionalInvalidatingHandles"] = list(handles)
    tab.items[-1]["bounds"]["showWhenDataModelInvalid"] = "Hide"


def deck_is(d):
    return "IndexedEnabling/%d/2/Parameter %d" % (d, P["Deck"])


def mode_is(m):
    return "IndexedEnabling/%d/2/Parameter %d" % (m, P["Mode"])


def style_is(d, s):
    return "IndexedEnabling/%d/3/Parameter %d" % (s, P["A Style" if d == 0 else "B Style"])


def def_knob_named(key, fn, frames, size=80, val_colour="fff4f1ea", name_colour="ffd8dade"):
    acts = [act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "", "knob overlay"), act("Enter Pressed", "Show Overlay", "", "knob overlay")]
    nm = label_data(13, name_colour, "SemiBold"); nm["type"] = "Name"
    comps = [focus_comp(size, size + 44),
             comp("Name", "Label", nm, bounds(-16, 0, size + 32, 18)),
             comp("Knob", "Knob", filmstrip(fn, frames), bounds(0, 20, size, size)),
             comp("Value", "Label", label_data(14, val_colour, "SemiBold"), bounds(-16, size + 22, size + 32, 20))]
    return define(key, acts, comps)


def def_text(key, w, h, size, colour, just="left verticallyCentred"):
    return def_readout(key, w, h, size, colour, just)


def def_drag_text(key, w, h, size, colour, drag, just="left verticallyCentred"):
    """invisible drag knob + value text: touch and drag to change (folder, file, lesson BPM)"""
    acts = [act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "", "knob overlay"), act("Enter Pressed", "Show Overlay", "", "knob overlay")]
    return define(key, acts, [focus_comp(w, h), comp("Drag", "Knob", filmstrip(CLEAR, 2, drag), bounds(0, 0, w, h)),
                              comp("Value", "Label", label_data(size, colour, "Bold", just), bounds(12, 0, w - 24, h))])


CLEAR = None


# ======================================================================================================
def main():
    global CLEAR
    CLEAR = save(Image.new("RGBA", (4, 8), (0, 0, 0, 0)), "sk_clear_f2.png")
    knob_strip, knob_frames = M.draw_knob_strip(80, 64)
    knob_fn = save(knob_strip, "sk_knob80_f64.png")
    knobN = def_knob_named("skKnobN", knob_fn, 64)
    led_s, led_frames = M.draw_led_strip(170, 28, 33)
    led_fn = save(led_s, "sk_stripled_f33.png")

    keys = {}
    def key(name, w, h, label, led=True, style="silver"):
        if name not in keys:
            on = M.draw_key(w, h, label, True, led, None, style); off = M.draw_key(w, h, label, False, led, None, style)
            keys[name] = (save(on, "sk_key_%s_on.png" % name), save(off, "sk_key_%s_off.png" % name), on, off)
        return keys[name]

    def _pvs(pv):
        return [] if pv is None else (pv if isinstance(pv, list) else [pv])

    def segments(tab, pv, pname, labels, x, y, w, h, gap=6, style="dark", conds=(), first_on=0):
        for i, lab in enumerate(labels):
            nm = ("%s_%d_%dx%d" % (pname, i, w, h)).replace(" ", "").replace("/", "").replace("#", "s").lower()
            on, off, on_i, off_i = key(nm, w, h, lab, True, style)
            tab.place(def_segment("skSeg_" + nm, on, off, w, h, i, len(labels)), P[pname], x + i * (w + gap), y, w, h, name=lab)
            if conds: cond(tab, *conds)
            for p_ in _pvs(pv): p_.alpha_composite(on_i if i == first_on else off_i, (x + i * (w + gap), y))

    def toggle(tab, pv, pname, name, label, x, y, w, h, style="dark", conds=(), on_prev=False):
        name = "%s_%dx%d" % (name, w, h)
        on, off, on_i, off_i = key(name, w, h, label, True, style)
        tab.place(def_toggle("skTg_" + name, on, off, w, h), P[pname], x, y, w, h, name=name)
        if conds: cond(tab, *conds)
        for p_ in _pvs(pv): p_.alpha_composite(on_i if on_prev else off_i, (x, y))

    # ================= DECK =================
    print("rendering decks ...")
    decks = {}
    for s in STYLES:
        img, maps, hits, rgb = draw_deck(s["plinth"])
        decks[s["plinth"]] = (img, maps, hits, rgb)
        print("  ", s["name"])
    img0, maps0, hits0, rgb0 = decks["silver"]
    M._DECK.update(maps=maps0, hx=hits0[0], hy=hits0[1], hz=hits0[2], rgb=rgb0)

    deck = Tab("DECK", save(img0, "sk_bg_deck_0.png"))
    bg_fns = [save(decks[s["plinth"]][0], "sk_bg_deck_%d.png" % i) for i, s in enumerate(STYLES)]
    for d in range(2):
        for si in range(3):
            deck.image("bg%d%d" % (d, si), bg_fns[si], 0, 0, W, H)
            cond(deck, deck_is(d), style_is(d, si))

    strobe_strip, strobe_frames = M.draw_strobe_frames()
    st_fn = save(strobe_strip, "sk_strobe_f%d.png" % M.STROBE_FRAMES)
    srx, sry, srw, srh = M._DECK["strobe_rect"]
    lab_strip, lab_frames, (lrx, lry, lrw, lrh) = draw_label_frames(maps0, hits0)
    lb_fn = save(lab_strip, "sk_label_f%d.png" % LABEL_FRAMES)
    arm, (ax, ay, aw, ah) = M.draw_tonearm()
    arm_fn = save(arm, "sk_tonearm.png")
    sdef = def_display("skStrobe", st_fn, M.STROBE_FRAMES, srw, srh)
    ldef = def_display("skLabel", lb_fn, LABEL_FRAMES, lrw, lrh)
    jrx, jry, jrw, jrh = _region_rect(CX, CY, R_REC, Z_MAT)
    jdef = define("skJog", [act("Mouse Down", "Q-Link")], [comp("Jog", "Knob", filmstrip(CLEAR, 2, "AbsoluteRotaryKnob"), bounds(0, 0, jrw, jrh))])
    pf_strip, pf_frames = M.draw_pitch_fader(PITCH_W, PITCH_H, 41)
    pf_fn = save(pf_strip, "sk_pitch_%dx%d_f41.png" % (PITCH_W, PITCH_H))
    pdef = def_slider("skPitch", pf_fn, 41, PITCH_W, PITCH_H, "Vertical")
    badge = [save(deck_badge(L, None), "sk_badge_%s.png" % L.lower()) for L in "AB"]
    cf_strip, cf_frames = crossfader_strip(340, 72, 61)
    cf_fn = save(cf_strip, "sk_xfader_f61.png")
    cv_strip, cv_frames = curve_strip(112, 50, 21)
    cv_fn = save(cv_strip, "sk_curve_f21.png")
    cl_strip, cl_frames = led_strip(34, 34, (255, 60, 30))
    cl_fn = save(cl_strip, "sk_cutled_f2.png")
    pads = [(save(slot_pad(106, 76, i + 1, True), "sk_slot%d_on.png" % (i + 1)), save(slot_pad(106, 76, i + 1, False), "sk_slot%d_off.png" % (i + 1))) for i in range(8)]
    pads_i = [(slot_pad(106, 76, i + 1, True), slot_pad(106, 76, i + 1, False)) for i in range(8)]

    previews = []
    for d in range(2):
        L = "AB"[d]
        dc = deck_is(d)
        pre = lambda p: P[("A " if d == 0 else "B ") + p]
        prev = decks[STYLES[d]["plinth"]][0].copy() if d == 0 else decks[STYLES[1]["plinth"]][0].copy()
        deck.place(sdef, P["A Strobe" if d == 0 else "B Strobe"], srx, sry, srw, srh, name="strobe%s" % L); cond(deck, dc)
        prev.alpha_composite(strobe_frames[0], (srx, sry))
        deck.place(ldef, P["A Angle" if d == 0 else "B Angle"], lrx, lry, lrw, lrh, name="label%s" % L); cond(deck, dc)
        prev.alpha_composite(lab_frames[3 + 9 * d], (lrx, lry))
        if d == 0:
            deck.image("Tonearm", arm_fn, ax, ay, aw, ah)
        prev.alpha_composite(arm, (ax, ay))
        deck.image("badge%s" % L, badge[d], 116, 20, 96, 44); cond(deck, dc)
        prev.alpha_composite(Image.open(os.path.join(OUT, badge[d])), (116, 20))
        if d == 0:
            deck.place(jdef, P["Platter"], jrx, jry, jrw, jrh, name="jog")
        # START/STOP, 33/45
        toggle(deck, prev, L + " Start/Stop", "start", "START·STOP", 16, 548, 132, 58, "silver", (dc,))
        segments(deck, prev, L + " Speed", ["33", "45"], 520, 556, 66, 52, gap=6, style="silver", conds=(dc,))
        deck.place(pdef, P[L + " Pitch"], PITCH_X, PITCH_Y, PITCH_W, PITCH_H, name="pitch" + L); cond(deck, dc)
        prev.alpha_composite(pf_frames[20], (PITCH_X, PITCH_Y))
        # panel: record LCD and pitch
        deck.place(def_text("skRecName", 300, 46, 24, "ffffb52e"), P[L + " Record"], 834, 80, 300, 46, name="rec" + L); cond(deck, dc)
        deck.place(def_text("skPitchRo", 130, 46, 20, "ffffb52e", "right verticallyCentred"), P[L + " Pitch"], 1126, 80, 130, 46, name="pro" + L); cond(deck, dc)
        # slots: top row 5..8, bottom row 1..4 (like the pads)
        for s in range(8):
            col, row = s % 4, (0 if s >= 4 else 1)
            x, y = 822 + col * 112, 142 + row * 80
            sdef_ = def_segment("skSlot%d" % s, pads[s][0], pads[s][1], 106, 76, s, 8)
            deck.place(sdef_, P[L + " Slot"], x, y, 106, 76, name="slot%s%d" % (L, s)); cond(deck, dc)
            prev.alpha_composite(pads_i[s][0] if s == 0 else pads_i[s][1], (x, y))
            deck.place(def_text("skSlotName", 98, 24, 13, "ffe6e7ea", "horizontallyCentred verticallyCentred"),
                       P["%s Slot %d Name" % (L, s + 1)], x + 4, y + 40, 98, 24, name="sn%s%d" % (L, s)); cond(deck, dc)
        # knobs: SIMPLE = range, curve, deck volume, level; ADVANCED = smooth, catch, cut lag, crackle
        simple = ["Strip Range", "Fader Curve", L + " Volume", "Level"]
        adv = ["Smooth", "Catch", "Cut Lag", "Crackle"]
        for i in range(4):
            x = 836 + i * 112
            deck.place(knobN, P[simple[i]], x, 304, 80, 124, name="ks%s%d" % (L, i)); cond(deck, dc, mode_is(0))
            deck.place(knobN, P[adv[i]], x, 304, 80, 124, name="ka%s%d" % (L, i)); cond(deck, dc, mode_is(1))
            prev.alpha_composite(knob_frames[40], (x, 324))
        # cut LEDs of both decks next to the crossfader
        deck.place(def_display("skCutLed", cl_fn, 2, 34, 34), P[L + " Cut LED"], 813 if d == 0 else 1235, 484, 34, 34, name="cut%s" % L)
        previews.append(prev)

    # shared panel parts (both decks)
    segments(deck, previews[0], "Deck", ["DECK A", "DECK B"], 822, 12, 140, 54, gap=6, style="dark", first_on=0)
    segments(deck, previews[1], "Deck", ["DECK A", "DECK B"], 822, 12, 140, 54, gap=6, style="dark", first_on=1)
    deck.items.pop(); deck.items.pop()          # (placed twice only for the two previews)
    toggle(deck, previews, "Mode", "mode", "ADVANCED", 1118, 12, 148, 54, "dark")
    deck.place(def_slider("skXFader", cf_fn, 61, 340, 72, "Horizontal"), P["Crossfader"], 860, 438, 340, 72, name="xfader")
    segments(deck, previews, "Cut Mode", ["CLOSE", "OPEN"], 822, 532, 100, 46, gap=6, style="dark")
    toggle(deck, previews, "Hamster", "hamster", "HAMSTER", 1040, 532, 110, 46, "dark")
    deck.place(def_display("skCurve", cv_fn, 21, 112, 50), P["Fader Curve"], 1156, 530, 112, 50, name="curve")
    deck.place(def_display("skStripLed", led_fn, 33, 170, 28), P["Strip LED"], 822, 590, 170, 28, name="stripled")
    deck.place(def_text("skTip", 256, 30, 13, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 1005, 589, 256, 30, name="tip")

    # previews (deck A silver, deck B battle)
    for d, prev in enumerate(previews):
        dd = ImageDraw.Draw(prev)
        prev.alpha_composite(cf_frames[8 if d == 0 else 52], (860, 438))
        prev.alpha_composite(cv_frames[17], (1156, 530))
        prev.alpha_composite(led_frames[0], (822, 590))
        prev.alpha_composite(cl_frames[1], (813, 484)); prev.alpha_composite(cl_frames[0], (1235, 484))
        dd.text((838, 103), "%s 1  %s" % ("AB"[d], "AHH" if d == 0 else "BREAK 92"), font=font(F_TIT, 24), fill=AMBER, anchor="lm")
        dd.text((1254, 103), "+0.00%", font=font(F_TIT, 20), fill=AMBER, anchor="rm")
        names = ["AHH", "OOH WAH", "STAB", "TONE 1K", "BREAK 92", "BASS DROP", "FRESH", "HORN"]
        if d == 1: names = names[4:] + names[:4]
        for s in range(8):
            col, row = s % 4, (0 if s >= 4 else 1)
            dd.text((822 + col * 112 + 53, 142 + row * 80 + 52), names[s], font=font(F_TIT, 13), fill=(230, 231, 234), anchor="mm")
        for i, (n_, v_) in enumerate(zip(["Strip Range", "Fader Curve", "%s Volume" % "AB"[d], "Level"], ["180 deg", "SHARP 85", "0.0 dB", "-3.0 dB"])):
            dd.text((876 + i * 112, 312), n_, font=font(F_TIT, 13), fill=(216, 218, 222), anchor="mm")
            dd.text((876 + i * 112, 416), v_, font=font(F_TIT, 14), fill=(244, 241, 234), anchor="mm")
        dd.text((1133, 604), "LEKTION WAEHLEN, DANN START", font=font(F_TIT, 13), fill=AMBER, anchor="mm")
        prev.convert("RGB").save(os.path.join(PREV, "preview_deck_%s.png" % "ab"[d]))

    # ================= BROWSER =================
    def br_items(S):
        f13 = font(F_SEMI, 13 * S)
        return [(60 * S, 52 * S, "ORDNER  (WISCHEN ODER Q-LINK 1)", f13, "la", S), (60 * S, 136 * S, "DATEI  (WISCHEN ODER Q-LINK 2)", f13, "la", S),
                (930 * S, 52 * S, "ZIEL-DECK", f13, "mm", S), (930 * S, 228 * S, "LADEN IN SLOT  (TIPPEN = LADEN + AUF DIE PLATTE)", f13, "mm", S),
                (60 * S, 560 * S, "EIGENE WAVS: USB / SD / SSD  -  ODER  PLUGIN-ORDNER/My Samples", font(F_MED, 14 * S), "la", 0),
                (60 * S, 584 * S, "MAX. 15 S PRO SLOT (MONO/STEREO WAV)", font(F_MED, 14 * S), "la", 0)]
    br_bg = panel_page([((20, 16, 680, 612), "BROWSER"), ((700, 16, 1260, 612), "")],
                       [(50, 64, 650, 116), (50, 148, 650, 444), (50, 452, 650, 488)], br_items, wells=[(712, 238, 1248, 418)])
    brow = Tab("BROWSER", save(br_bg, "sk_bg_browser.png"))
    bprev = br_bg.copy()
    brow.place(def_drag_text("skFolder", 600, 52, 22, "ffffb52e", "Horizontal"), P["Folder"], 50, 64, 600, 52, name="folder")
    brow.place(def_drag_text("skFileDrag", 600, 296, 1, "00000000", "Vertical"), P["File"], 50, 148, 600, 296, name="filedrag")
    # highlight bar for the selected row
    hl = Image.new("RGBA", (592, 54), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle([0, 0, 591, 53], 6, fill=(255, 181, 46, 46), outline=(255, 181, 46, 150), width=2)
    brow.image("hl", save(hl, "sk_rowhl.png"), 54, 269, 592, 54)
    bprev.alpha_composite(hl, (54, 269))
    rows_y = [158, 214, 270, 326, 382]
    for r_, yy in enumerate(rows_y):
        brow.place(def_text("skRow%d" % r_, 560, 52, 22 if r_ == 2 else 18, "ffffb52e" if r_ == 2 else "ff9a9ca0"), P["Row %d" % (r_ + 1)], 70, yy, 560, 52, name="row%d" % r_)
    brow.place(def_text("skBrInfo", 580, 36, 15, "ffd8dade"), P["Browser Info"], 62, 452, 580, 36, name="info")
    segments(brow, bprev, "Deck", ["DECK A", "DECK B"], 790, 70, 140, 54, gap=8, style="dark")
    toggle(brow, bprev, "Preview", "preview", "VORHOEREN", 740, 150, 180, 56, "dark")
    toggle(brow, bprev, "Rescan", "rescan", "NEU SUCHEN", 1040, 150, 180, 56, "dark")
    for d in range(2):
        L = "AB"[d]
        for s in range(8):
            col, row = s % 4, (0 if s >= 4 else 1)
            x, y = 718 + col * 132, 246 + row * 86
            brow.place(def_segment("skLoad%d" % s, pads[s][0], pads[s][1], 106, 76, s + 1, 9), P["Load To Slot"], x + 10, y, 106, 76, name="ld%s%d" % (L, s)); cond(brow, deck_is(d))
            brow.place(def_text("skSlotName", 98, 24, 13, "ffe6e7ea", "horizontallyCentred verticallyCentred"), P["%s Slot %d Name" % (L, s + 1)], x + 14, y + 40, 98, 24, name="lsn%s%d" % (L, s)); cond(brow, deck_is(d))
            if d == 0: bprev.alpha_composite(pads_i[s][1], (x + 10, y))
    brow.place(knobN, P["Folder"], 760, 450, 80, 124, name="kfolder")
    brow.place(knobN, P["File"], 880, 450, 80, 124, name="kfile")
    brow.place(knobN, P["Crossfader"], 1000, 450, 80, 124, name="kxf")
    brow.place(knobN, P["Level"], 1120, 450, 80, 124, name="klevel")
    for i in range(4): bprev.alpha_composite(knob_frames[30], (760 + i * 120, 470))
    bd = ImageDraw.Draw(bprev)
    bd.text((62, 90), "SKRATCHA SAMPLES", font=font(F_TIT, 22), fill=AMBER, anchor="lm")
    for r_, (yy, nm) in enumerate(zip(rows_y, ["", "", "> AHH", "OOH WAH", "STAB"])):
        bd.text((82, yy + 26), nm, font=font(F_TIT, 22 if r_ == 2 else 18), fill=AMBER if r_ == 2 else (154, 156, 160), anchor="lm")
    bd.text((74, 470), "DATEI 1/8  ORDNER 1/3", font=font(F_TIT, 15), fill=(216, 218, 222), anchor="lm")
    bprev.convert("RGB").save(os.path.join(PREV, "preview_browser.png"))

    # ================= LERNEN =================
    def le_items(S):
        f13 = font(F_SEMI, 13 * S)
        return [(52 * S, 48 * S, "LEKTION", f13, "la", S), (390 * S, 168 * S, "LEHRER (GRUEN)  -  SO SOLL DEINE HAND GEHEN", f13, "la", S),
                (390 * S, 246 * S, "DU  -  DEIN FINGER AUF DEM STRIP", f13, "la", S), (390 * S, 324 * S, "TAKT", f13, "la", S),
                (420 * S, 392 * S, "TON SOLL", font(F_SEMI, 11 * S), "mm", S), (500 * S, 392 * S, "TON IST", font(F_SEMI, 11 * S), "mm", S),
                (52 * S, 528 * S, "1. DEMO ANHOEREN   2. START = 1 TAKT ZAEHLEN", font(F_MED, 13 * S), "la", 0),
                (52 * S, 552 * S, "3. NACH 4 TAKTEN STERNE  ***  = WEITER", font(F_MED, 13 * S), "la", 0)]
    le_bg = panel_page([((20, 16, 360, 612), ""), ((372, 16, 1260, 612), "")],
                       [(390, 40, 1244, 156), (390, 466, 1244, 516)], le_items)
    lern = Tab("LERNEN", save(le_bg, "sk_bg_lernen.png"))
    lprev = le_bg.copy()
    LESSONS = [p_["choices"] for p_ in M.params if p_["name"] == "Lesson"][0]
    for i, nm in enumerate(LESSONS):
        on, off, on_i, off_i = key("lesson%d" % i, 300, 60, nm, True, "dark")
        lern.place(def_segment("skLesson%d" % i, on, off, 300, 60, i, len(LESSONS)), P["Lesson"], 40, 66 + i * 70, 300, 60, name="les%d" % i)
        lprev.alpha_composite(on_i if i == 0 else off_i, (40, 66 + i * 70))
    lern.place(def_text("skLT1", 830, 50, 24, "ffffb52e"), P["Lesson Text 1"], 404, 46, 830, 50, name="t1")
    lern.place(def_text("skLT2", 830, 50, 24, "ffffb52e"), P["Lesson Text 2"], 404, 100, 830, 50, name="t2")
    gs, gf = teach_strip(850, 56, GREEN, "")
    ys, yf = teach_strip(850, 56, AMBER, "")
    lern.place(def_display("skGhost", save(gs, "sk_ghost_f33.png"), 33, 850, 56), P["Ghost"], 390, 180, 850, 56, name="ghost")
    lern.place(def_display("skYou", save(ys, "sk_you_f33.png"), 33, 850, 56), P["Strip LED"], 390, 258, 850, 56, name="you")
    bs, bf = beat_strip(850, 36)
    lern.place(def_display("skBeat", save(bs, "sk_beat_f9.png"), 9, 850, 36), P["Beat"], 390, 336, 850, 36, name="beat")
    fl, flf = led_strip(40, 40, GREEN)
    al, alf = led_strip(40, 40, AMBER)
    lern.place(def_display("skFadeT", save(fl, "sk_led_green_f2.png"), 2, 40, 40), P["Fader Target"], 400, 400, 40, 40, name="fadet")
    for d in range(2):
        lern.place(def_display("skFadeA", save(al, "sk_led_amber_f2.png"), 2, 40, 40), P["%s Cut LED" % "AB"[d]], 480, 400, 40, 40, name="fadea%d" % d); cond(lern, deck_is(d))
    ss_, sf = stars_strip(210, 54)
    lern.place(def_display("skStars", save(ss_, "sk_stars_f4.png"), 4, 210, 54), P["Stars"], 560, 394, 210, 54, name="stars")
    lern.place(def_text("skScore", 450, 40, 17, "ffd8dade", "right verticallyCentred"), P["Score"], 790, 400, 450, 40, name="score")
    lern.place(def_text("skMsg", 830, 48, 24, "ffffb52e", "horizontallyCentred verticallyCentred"), P["Tip"], 404, 467, 830, 48, name="msg")
    toggle(lern, lprev, "Lesson Demo", "demo", "DEMO", 400, 536, 170, 62, "silver")
    toggle(lern, lprev, "Lesson Start", "lstart", "START", 584, 536, 170, 62, "silver")
    toggle(lern, lprev, "Click", "click", "KLICK", 768, 536, 130, 62, "dark", on_prev=True)
    lern.place(def_drag_text("skBpm", 180, 62, 22, "ffffb52e", "Vertical", "horizontallyCentred verticallyCentred"), P["Lesson BPM"], 912, 536, 180, 62, name="bpm")
    segments(lern, lprev, "Deck", ["A", "B"], 1106, 536, 64, 62, gap=6, style="dark")
    for img_, pos in [(gf[9], (390, 180)), (yf[12], (390, 258)), (bf[3], (390, 336)), (flf[1], (400, 400)), (alf[1], (480, 400)), (sf[2], (560, 394))]:
        lprev.alpha_composite(img_, pos)
    ld_ = ImageDraw.Draw(lprev)
    ld_.text((414, 71), "VOR UND ZURUECK IM TAKT", font=font(F_TIT, 24), fill=AMBER, anchor="lm")
    ld_.text((414, 125), "FOLGE DEM GRUENEN PUNKT", font=font(F_TIT, 24), fill=AMBER, anchor="lm")
    ld_.text((1236, 420), "TREFFER 88%   BESTE **-", font=font(F_TIT, 17), fill=(216, 218, 222), anchor="rm")
    ld_.text((819, 491), "SUPER! GENAU IM TAKT", font=font(F_TIT, 24), fill=AMBER, anchor="mm")
    ld_.text((1002, 567), "80 BPM", font=font(F_TIT, 22), fill=AMBER, anchor="mm")
    lprev.convert("RGB").save(os.path.join(PREV, "preview_lernen.png"))

    # ================= SETUP =================
    def su_items(S):
        f13 = font(F_SEMI, 13 * S)
        it = [(40 * S, 66 * S, "TURNTABLE-STIL (KLANG, LOOK, GEFUEHL)", f13, "la", S), (40 * S, 176 * S, "PAD 1-8 =", f13, "la", S),
              (300 * S, 176 * S, "PAD BASE NOTE", f13, "la", S), (672 * S, 66 * S, "STRIP RICHTUNG", f13, "la", S),
              (672 * S, 176 * S, "LOSLASSEN WENN", f13, "la", S), (40 * S, 370 * S, "CUT SPEED (PAD 10)", f13, "la", S),
              (672 * S, 370 * S, "PITCH RANGE", f13, "la", S), (672 * S, 476 * S, "PLATTEN-ENDE", f13, "la", S)]
        it.append((40 * S, 586 * S, "SIMPLE: NUR DAS WICHTIGSTE.  ADVANCED (OBEN RECHTS AUF DECK): ALLES.", font(F_MED, 14 * S), "la", 0))
        return it
    su_bg = panel_page([((20, 16, 640, 300), "DECK"), ((652, 16, 1260, 300), "TOUCH STRIP"),
                        ((20, 320, 640, 612), "FADER  ·  SOUND"), ((652, 320, 1260, 612), "MOTOR (AKTIVES DECK)")], [], su_items)
    setup = Tab("SETUP", save(su_bg, "sk_bg_setup.png"))
    sprev = su_bg.copy()
    for d in range(2):
        L = "AB"[d]
        segments(setup, sprev if d == 0 else None, L + " Style", [s["name"] for s in STYLES], 40, 84, 186, 56, gap=8, style="dark", conds=(deck_is(d),))
        segments(setup, sprev if d == 0 else None, L + " Pitch Rng", ["8%", "16%", "50%"], 672, 388, 92, 52, conds=(deck_is(d), mode_is(1)))
        segments(setup, sprev if d == 0 else None, L + " Loop", ["1X", "LOOP"], 672, 494, 92, 52, conds=(deck_is(d), mode_is(1)))
        toggle(setup, sprev if d == 0 else None, L + " Reverse", "rev", "REVERSE", 872, 494, 120, 52, "dark", (deck_is(d), mode_is(1)))
        toggle(setup, sprev if d == 0 else None, L + " On", "on", "DECK ON", 1004, 494, 120, 52, "dark", (deck_is(d), mode_is(1)), on_prev=True)
        for i, pn in enumerate([L + " Start Time", L + " Brake Time"]):
            setup.place(knobN, P[pn], 1000 + i * 120, 360, 80, 124, name="m%s%d" % (L, i)); cond(setup, deck_is(d), mode_is(1))
    segments(setup, sprev, "Fire", ["CUE", "PLAY"], 90, 194, 90, 52)
    segments(setup, sprev, "Pad Base", ["C1 36", "C#1 37"], 300, 194, 120, 52)
    segments(setup, sprev, "Strip Dir", ["NORMAL", "INVERT"], 672, 84, 140, 52)
    segments(setup, sprev, "Release", ["CENTER", "TIMEOUT"], 672, 194, 140, 52)
    segments(setup, sprev, "Cut Speed", ["SHARP", "MEDIUM", "SOFT"], 40, 388, 120, 52)
    for i, pn in enumerate(["Strip Range", "Smooth", "Catch"]):
        setup.place(knobN, P[pn], 980 + i * 96, 120, 80, 124, name="st%d" % i)
        if pn != "Strip Range": cond(setup, mode_is(1))
        sprev.alpha_composite(knob_frames[30], (980 + i * 96, 140))
    for i, pn in enumerate(["Crackle", "Cut Lag", "Fader Curve"]):
        setup.place(knobN, P[pn], 60 + i * 120, 460, 80, 124, name="fs%d" % i)
        sprev.alpha_composite(knob_frames[20], (60 + i * 120, 480))
    toggle(setup, sprev, "Hamster", "hamster", "HAMSTER", 440, 388, 150, 52, "dark")
    sprev.convert("RGB").save(os.path.join(PREV, "preview_setup.png"))

    # ================= INFO =================
    info_bg = draw_info_bg()
    info = Tab("INFO", save(info_bg, "sk_bg_info.png"))
    info_bg.convert("RGB").save(os.path.join(PREV, "preview_info.png"))

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
    deck_rows = [["Crossfader", "Fader Curve", "Strip Range", "Level"], ["A Pitch", "B Pitch", "A Volume", "B Volume"],
                 ["Smooth", "Catch", "Cut Lag", "Crackle"], ["Scratch", "Lesson BPM", None, None]]
    br_rows = [["Folder", "File", "Crossfader", "Level"]]
    le_rows = [["Crossfader", "Lesson BPM", "Strip Range", "Level"], ["Smooth", "Fader Curve", None, None]]
    su_rows = [["Strip Range", "Smooth", "Catch", "Crackle"], ["A Start Time", "A Brake Time", "B Start Time", "B Brake Time"], ["Cut Lag", "Fader Curve", "Scratch", "Level"]]
    info_rows = [["Crossfader", "Level", "A Pitch", "B Pitch"]]
    ql = {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
          "Screen Mode Q-Links": {"version": 4, "map": [
              {"Tab": i + 1, "SubTab": 1, "Bank Direction": "Row", "Q-Links": qmap(rows)} for i, rows in enumerate([deck_rows, br_rows, le_rows, su_rows, info_rows])]},
          "Program Mode Q-Links": qmap(deck_rows)}
    json.dump(ql, open(os.path.join(OUT, "Q-Links.json"), "w"), indent=1)

    total = 0
    for fn in sorted(os.listdir(OUT)):
        if fn.endswith(".png"):
            im = Image.open(os.path.join(OUT, fn))
            total += os.path.getsize(os.path.join(OUT, fn))
            assert im.height <= 16384, fn
    print("skin written: %d definitions, %d tabs, %.1f MB PNG" % (len(DEFS), len(tabs), total / 1e6))


if __name__ == "__main__":
    main()
