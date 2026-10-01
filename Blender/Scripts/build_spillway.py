"""Build mission 1, "Spillway": a night-time hydroelectric dam in the mountains of Valdoria.

Run:  blender -b --factory-startup --python Blender/Scripts/build_spillway.py
Output: Game/assets/levels/spillway/spillway.glb and Blender/Source/spillway.blend

Layout (Blender +Y is north, +X east, Z up, metres):
  1. Checkpoint   y -12..46, z 0     road, guard booth, barrier arm, containers
  2. Mountain road y 46..105, climbs to z 10 and bends west into a rock tunnel
  3. Tunnel        x -22..-52, y 101.5..108.5, side alcove on the south wall
  4. Dam crest     x -52..-142, y 100..110, z 10; reservoir to the north (water z 6)
  5. Control bldg  on a 20x14 m platform at the crest midpoint (x -107..-87)
  6. Relay yard    fenced 25x25 m on a rock shelf at the west end, gravel exit road
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import level_kit as lk  # noqa: E402
import retro_kit as rk  # noqa: E402

UP = np.array((0.0, 0.0, 1.0))
CREST_Z = 10.0
WATER_Z = 6.0

MATERIALS = (
    "asphalt", "gravel", "rock", "concrete", "concrete_dark", "tunnel", "paint",
    "container_red", "container_blue", "bldg_ext", "bldg_int", "floor_tile", "ceiling",
    "light", "lamp", "red_light", "window_lit", "window_dark", "console", "screen",
    "hazard", "sandbag", "crate", "metal", "generator", "fence", "lattice", "dish",
    "water", "roof", "barrier", "rock_far",
)
M = {name: i for i, name in enumerate(MATERIALS)}

UV_SCALES = {
    M["asphalt"]: 3.0, M["gravel"]: 2.5, M["rock"]: 4.0, M["concrete"]: 3.0,
    M["concrete_dark"]: 2.0, M["tunnel"]: 2.0, M["paint"]: 0.5,
    M["container_red"]: (2.0, 2.6, 0.0), M["container_blue"]: (2.0, 2.6, 0.0),
    M["hazard"]: 1.0, M["sandbag"]: 1.0, M["metal"]: 1.0, M["generator"]: 2.0,
    M["fence"]: (2.0, 2.8, CREST_Z), M["lattice"]: 1.0, M["dish"]: 1.5, M["water"]: 8.0,
    M["barrier"]: 2.0, M["rock_far"]: 7.0,
}
FACE_MAPPED = {M[n] for n in ("light", "lamp", "red_light", "window_lit", "window_dark",
                              "console", "screen", "crate")}
FULLBRIGHT = {M[n]: (1.0, 1.0, 1.0) for n in ("light", "lamp", "red_light", "window_lit", "screen")}

SODIUM = (1.0, 0.75, 0.4)
TUNNEL_LAMP = (0.9, 0.9, 0.8)
FLUORESCENT = (0.95, 1.0, 1.05)
RED = (0.95, 0.15, 0.08)


# --------------------------------------------------------------------------
# Textures (32-64 px, 8-16 level palettes)
# --------------------------------------------------------------------------

def _walk_cracks(size, rng, count, length):
    mask = np.zeros((size, size), dtype=bool)
    for _ in range(count):
        x, y = rng.integers(0, size, 2)
        for _ in range(length):
            mask[y % size, x % size] = True
            x += rng.integers(-1, 2)
            y += rng.integers(0, 2)
    return mask


def build_textures(rng):
    t = {}
    n = 64

    v = rk.fbm(n, rng) * 0.45 + rng.random((n, n)) * 0.55
    v[_walk_cracks(n, rng, 3, 50)] *= 0.35
    t["asphalt"] = rk.ramp(rk.quantize(v, 8), (0.16, 0.16, 0.17), (0.46, 0.45, 0.44))

    v = rk.value_noise(n, 32, rng) * 0.6 + rng.random((n, n)) * 0.4
    t["gravel"] = rk.ramp(rk.quantize(v, 10), (0.24, 0.22, 0.19), (0.62, 0.57, 0.49))

    base = rk.fbm(n, rng)
    y = np.arange(n)[:, None] / n
    strata = 0.5 + 0.5 * np.sin(2 * np.pi * (y * 3 + base * 0.9))
    v = base * 0.55 + strata * 0.3 + rng.random((n, n)) * 0.15
    v[_walk_cracks(n, rng, 5, 40)] *= 0.45
    rgb = rk.ramp(rk.quantize(np.clip(v, 0, 1), 12), (0.18, 0.17, 0.16), (0.60, 0.57, 0.52))
    lichen = rk.fbm(n, rng) > 0.64
    rgb[lichen] = rgb[lichen] * (0.85, 1.0, 0.8)
    t["rock"] = rgb

    # Distant mountainsides: broad, low-contrast blotches (reads as rock under fog).
    v = rk.fbm(n, rng, octaves=((2, 0.5), (4, 0.3), (8, 0.2))) * 0.7 + rk.fbm(n, rng) * 0.2
    v += rng.random((n, n)) * 0.1
    v[_walk_cracks(n, rng, 3, 30)] *= 0.6
    t["rock_far"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 10), (0.20, 0.20, 0.20), (0.52, 0.50, 0.46))

    def concrete(dark, light, seams=True):
        v = 0.3 + rk.fbm(n, rng) * 0.5 + rng.random((n, n)) * 0.2
        streak = rk.value_noise(n, 16, rng)[0]
        v *= 0.82 + 0.18 * streak[None, :]
        if seams:
            v[[0, 32], :] *= 0.6
            v[:, 0] *= 0.62
            for sy in (8, 24, 40, 56):
                for sx in (8, 40):
                    v[sy, sx] *= 0.35
        return rk.ramp(rk.quantize(np.clip(v, 0, 1), 10), dark, light)

    t["concrete"] = concrete((0.36, 0.36, 0.34), (0.76, 0.75, 0.70))
    t["concrete_dark"] = concrete((0.20, 0.20, 0.20), (0.50, 0.49, 0.47))
    t["barrier"] = concrete((0.40, 0.40, 0.38), (0.80, 0.79, 0.74), seams=False)
    band = (np.arange(n) // 16) % 2 == 0
    t["barrier"][38:45, band] = (0.75, 0.12, 0.08)
    t["barrier"][38:45, ~band] = (0.85, 0.84, 0.80)

    v = 0.45 + rk.fbm(n, rng) * 0.35 + rng.random((n, n)) * 0.15
    for e in (0, 32):
        v[e, :] = v[:, e] = 0.15
        v[e + 1, :] = np.minimum(1, v[e + 1, :] + 0.3)
    for sy in (4, 28, 36, 60):
        for sx in (4, 28, 36, 60):
            v[sy, sx] = 0.1
    t["tunnel"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.30, 0.30, 0.28), (0.68, 0.66, 0.58))

    v = 0.8 + rng.random((16, 16)) * 0.2
    v[rk.fbm(16, rng) > 0.66] = 0.45
    t["paint"] = rk.ramp(v, (0.35, 0.30, 0.15), (0.92, 0.78, 0.22))

    def container(dark, light):
        v = 0.55 + rk.fbm(n, rng) * 0.25 + rng.random((n, n)) * 0.1
        cols = np.arange(n) % 8
        v[:, cols < 2] *= 0.6
        v[:, cols == 2] = np.minimum(1, v[:, cols == 2] + 0.25)
        v[:3, :] = 0.3
        v[-3:, :] = 0.3
        rgb = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), dark, light)
        rust = rk.fbm(n, rng) > 0.66
        rgb[rust] = rgb[rust] * 0.4 + np.array((0.30, 0.16, 0.08))
        return rgb

    t["container_red"] = container((0.28, 0.07, 0.05), (0.70, 0.24, 0.15))
    t["container_blue"] = container((0.07, 0.13, 0.24), (0.24, 0.40, 0.60))

    v = 0.65 + rk.fbm(n, rng) * 0.25 + rng.random((n, n)) * 0.1
    v[[0, 32], :] *= 0.75
    t["bldg_ext"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.40, 0.42, 0.40), (0.80, 0.80, 0.74))

    v = 0.7 + rk.fbm(n, rng) * 0.2 + rng.random((n, n)) * 0.1
    rows = np.arange(n)
    v[rows % 8 == 0, :] *= 0.7
    for r in range(0, n, 8):
        off = 0 if (r // 8) % 2 == 0 else 8
        v[r:r + 8, (np.arange(n) + off) % 16 == 0] *= 0.7
    v[48:, :] *= 0.8  # darker wainscot band in the lower quarter
    t["bldg_int"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.33, 0.40, 0.36), (0.72, 0.80, 0.74))

    v = 0.5 + rk.fbm(n, rng) * 0.2 + rng.random((n, n)) * 0.1
    ty, tx = np.mgrid[0:n, 0:n] // 16
    v += np.where((tx + ty) % 2 == 0, 0.15, -0.05)
    v[::16, :] = v[:, ::16] = 0.1
    t["floor_tile"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.26, 0.26, 0.25), (0.66, 0.64, 0.58))

    v = 0.6 + rk.fbm(32, rng) * 0.25
    v[0, :] = v[:, 0] = 0.95
    v[31, :] = v[:, 31] = 0.25
    t["ceiling"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.32, 0.32, 0.32), (0.74, 0.74, 0.72))

    v = np.full((32, 32), 0.95)
    v[::8, :] = v[:, ::8] = 0.65
    v[:2, :] = v[-2:, :] = v[:, :2] = v[:, -2:] = 0.35
    t["light"] = rk.ramp(v, (0.40, 0.40, 0.36), (1.0, 0.98, 0.90))

    v = np.full((16, 16), 1.0)
    v[::4, :] = 0.8
    v[:1, :] = v[-1:, :] = v[:, :1] = v[:, -1:] = 0.3
    t["lamp"] = rk.ramp(v, (0.35, 0.20, 0.05), (1.0, 0.86, 0.55))

    yy, xx = np.mgrid[0:16, 0:16]
    d = np.hypot(yy - 7.5, xx - 7.5) / 8
    t["red_light"] = rk.ramp(np.clip(1.1 - d, 0.3, 1), (0.35, 0.02, 0.02), (1.0, 0.35, 0.25))

    v = 0.75 + rng.random((32, 32)) * 0.15
    v[::5, :] *= 0.85  # blinds
    v[:2, :] = v[-2:, :] = v[:, :2] = v[:, -2:] = 0.1
    v[:, 15:17] = 0.1
    t["window_lit"] = rk.ramp(np.clip(v, 0, 1), (0.10, 0.08, 0.05), (1.0, 0.86, 0.52))

    v = 0.3 + rng.random((32, 32)) * 0.1
    gy, gx = np.mgrid[0:32, 0:32]
    streak = np.abs(gx - gy - 4) < 3
    v[streak] += 0.35
    v[:2, :] = v[-2:, :] = v[:, :2] = v[:, -2:] = 0.05
    v[:, 15:17] = 0.05
    t["window_dark"] = rk.ramp(np.clip(v, 0, 1), (0.03, 0.04, 0.06), (0.30, 0.40, 0.55))

    v = 0.6 + rk.fbm(32, rng) * 0.2
    rgb = rk.ramp(rk.quantize(v, 6), (0.30, 0.31, 0.30), (0.62, 0.62, 0.58))
    palette = np.array(((0.9, 0.2, 0.1), (0.2, 0.8, 0.2), (0.95, 0.8, 0.1), (0.2, 0.5, 0.95), (0.1, 0.1, 0.1)))
    for by in range(6, 28, 6):
        for bx in range(3, 30, 4):
            rgb[by:by + 2, bx:bx + 2] = palette[rng.integers(0, len(palette))]
    rgb[:2, :] = rgb[-2:, :] = 0.2
    t["console"] = rgb

    v = np.full((32, 32), 0.1)
    for row in range(5, 28, 3):
        start = rng.integers(4, 8)
        length = rng.integers(6, 22)
        v[row, start:start + length] = rng.uniform(0.6, 1.0)
    v[:3, :] = v[-3:, :] = v[:, :3] = v[:, -3:] = 0.0
    rgb = rk.ramp(v, (0.02, 0.06, 0.04), (0.45, 1.0, 0.55))
    rgb[:3, :] = rgb[-3:, :] = rgb[:, :3] = rgb[:, -3:] = (0.18, 0.18, 0.18)
    t["screen"] = rgb

    yy, xx = np.mgrid[0:32, 0:32]
    stripes = ((xx + yy) // 8) % 2 == 0
    rgb = np.where(stripes[..., None], (0.88, 0.68, 0.10), (0.08, 0.08, 0.08)).astype(float)
    wear = rk.fbm(32, rng) > 0.62
    rgb[wear] = rgb[wear] * 0.5 + 0.18
    t["hazard"] = rgb

    v = np.zeros((32, 32))
    for r in range(4):
        off = 0 if r % 2 == 0 else 8
        for c in range(-1, 3):
            cy, cx = r * 8 + 4, c * 16 + 8 + off
            d = ((yy - cy) / 4.2) ** 2 + ((xx - cx) / 8.5) ** 2
            v = np.maximum(v, np.clip(1 - d, 0, 1) ** 0.5)
    v = v * 0.8 + rng.random((32, 32)) * 0.2
    t["sandbag"] = rk.ramp(rk.quantize(v, 8), (0.20, 0.18, 0.11), (0.66, 0.60, 0.42))

    v = 0.55 + rk.fbm(32, rng) * 0.3 + rng.random((32, 32)) * 0.1
    v[::8, :] *= 0.55
    v[:3, :] = v[-3:, :] = v[:, :3] = v[:, -3:] = 0.85
    diag = np.abs(xx - yy) <= 1
    v[diag] = 0.8
    v[0, :] = v[-1, :] = v[:, 0] = v[:, -1] = 0.2
    t["crate"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.24, 0.15, 0.07), (0.66, 0.47, 0.25))

    v = 0.55 + rk.fbm(32, rng) * 0.3 + rng.random((32, 32)) * 0.15
    v[_walk_cracks(32, rng, 4, 8)] = 0.9
    t["metal"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.15, 0.17, 0.17), (0.44, 0.47, 0.46))

    v = 0.7 + rk.fbm(32, rng) * 0.25
    v[6:26:3, 4:14] = 0.15  # vent slots
    v[8:24, 18:28] *= 0.55  # access panel
    v[:2, :] = v[-2:, :] = v[:, :2] = v[:, -2:] = 0.3
    t["generator"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.30, 0.22, 0.04), (0.90, 0.72, 0.18))

    v = 0.6 + rk.fbm(32, rng) * 0.3
    v[:, xx[0] % 4 == 3] = 0.05
    v[(yy < 4) & (np.abs((xx % 4) - 1.5) > (4 - yy) * 0.45)] = 0.05  # pointed pale tips
    v[[9, 10, 26, 27], :] = np.maximum(v[[9, 10, 26, 27], :], 0.85)
    t["fence"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.07, 0.10, 0.09), (0.40, 0.48, 0.42))

    v = np.full((32, 32), 0.08)
    bars = (xx < 3) | (xx > 28) | (yy < 2) | (np.abs(xx - yy) <= 1) | (np.abs(xx - (31 - yy)) <= 1)
    v[bars] = 0.7 + rk.fbm(32, rng)[bars] * 0.3
    t["lattice"] = rk.ramp(v, (0.04, 0.05, 0.07), (0.72, 0.72, 0.70))

    v = 0.8 + rk.fbm(32, rng) * 0.15
    v[::8, :] *= 0.8
    v[:, ::16] *= 0.8
    t["dish"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.40, 0.42, 0.44), (0.90, 0.91, 0.90))

    wy, wx = np.mgrid[0:n, 0:n] / n
    v = 0.5 + 0.25 * np.sin(2 * np.pi * (wy * 4 + rk.fbm(n, rng) * 1.5)) + rk.fbm(n, rng) * 0.25
    t["water"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.04, 0.08, 0.13), (0.26, 0.38, 0.50))

    v = 0.5 + rng.random((32, 32)) * 0.35 + rk.fbm(32, rng) * 0.15
    t["roof"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 6), (0.13, 0.13, 0.13), (0.40, 0.39, 0.36))

    return {name: rk.save_texture("tex_sp_" + name, rgb) for name, rgb in t.items()}


# --------------------------------------------------------------------------
# Road path (checkpoint -> tunnel mouth)
# --------------------------------------------------------------------------

def sample_line(a, b, step=2.0):
    a, b = np.array(a, float), np.array(b, float)
    k = max(1, math.ceil(np.linalg.norm(b - a) / step))
    return [a + (b - a) * i / k for i in range(1, k + 1)]


def sample_arc(centre, radius, a0, a1, step=2.0):
    k = max(1, math.ceil(abs(a1 - a0) * radius / step))
    return [np.array(centre) + radius * np.array((math.cos(a), math.sin(a)))
            for a in np.linspace(a0, a1, k + 1)[1:]]


RAMP_LENGTH = 44.0 + 15.0 * math.pi / 2  # straight climb + bend


def road_z(s_from_ramp_start):
    return float(np.clip(s_from_ramp_start / RAMP_LENGTH, 0, 1)) * CREST_Z


def road_stations():
    pts = [np.array((22.0, -24.0))]
    pts += sample_line((22, -24), (12, -24))
    pts += sample_arc((12, -12), 12, -math.pi / 2, -math.pi)
    pts += sample_line((0, -12), (0, 46))
    ramp_start = len(pts) - 1
    pts += sample_line((0, 46), (0, 90))
    pts += sample_arc((-15, 90), 15, 0, math.pi / 2)
    pts += sample_line((-15, 105), (-22, 105))
    pts = np.array(pts)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    z = np.array([road_z(s - seg[ramp_start]) for s in seg])
    wl = np.full(len(pts), 7.0)
    wr = np.full(len(pts), 7.0)
    for i, (x, y) in enumerate(pts):
        if abs(x) < 1e-6 and -12 <= y <= 46:
            wl[i] = np.interp(y, (-12, -6, 38, 46), (7, 16, 16, 7))
            wr[i] = np.interp(y, (-12, -6, 38, 46), (7, 14, 14, 7))
    return pts, z, wl, wr


def corridor(bm, pts, z, wl, wr, strips, rng, mats, dashes=False, ridge_kw=None):
    """Floor ribbon + rock ridges on both sides along a centre line.

    strips: [(lo, hi, material, cells)] with lo/hi either "L", "R" or an offset.
    Returns (tangents, right_perps).
    """
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True)
    right = np.stack((tang[:, 1], -tang[:, 0]), axis=1)

    def at(i, off):
        return np.array((*(pts[i] + right[i] * off), z[i]))

    def resolve(i, key):
        return -wl[i] if key == "L" else wr[i] if key == "R" else key

    for i in range(len(pts) - 1):
        for lo, hi, mat, cells in strips:
            a0, b0 = resolve(i, lo), resolve(i, hi)
            a1, b1 = resolve(i + 1, lo), resolve(i + 1, hi)
            for k in range(cells):
                f0, f1 = k / cells, (k + 1) / cells
                quad = [at(i, a0 + (b0 - a0) * f0), at(i + 1, a1 + (b1 - a1) * f0),
                        at(i + 1, a1 + (b1 - a1) * f1), at(i, a0 + (b0 - a0) * f1)]
                lk.face(bm, quad, mat, UP)
        if dashes and i % 2 == 0:
            p0, p1 = at(i, 0), at(i + 1, 0)
            q0, q1 = p0 + (p1 - p0) * 0.2, p0 + (p1 - p0) * 0.8
            side = np.array((*right[i], 0)) * 0.08
            lk.face(bm, [q0 - side + UP * 0.02, q1 - side + UP * 0.02,
                         q1 + side + UP * 0.02, q0 + side + UP * 0.02], mats["paint"], UP)

    left_base = np.array([at(i, -wl[i]) for i in range(len(pts))])
    right_base = np.array([at(i, wr[i]) for i in range(len(pts))])
    kw = ridge_kw or {}
    lk.ridge(bm, left_base, right, rng, mats["rock"], **kw)
    lk.ridge(bm, right_base, -right, rng, mats["rock"], **kw)
    return tang, right


# --------------------------------------------------------------------------
# Props
# --------------------------------------------------------------------------

def lamp_post(bm, base, arm_dir, height=5.5, arm=1.5):
    """Street lamp: post, arm and a head with a fullbright underside. Returns light pos."""
    x, y, z = base
    d = np.array((*arm_dir, 0.0))
    lk.box(bm, (x - 0.12, y - 0.12, z), (x + 0.12, y + 0.12, z + height), M["metal"])
    tip = np.array((x, y, 0.0)) + d * arm
    lk.slab(bm, (x, y), tip[:2], z + height - 0.15, z + height, 0.12, M["metal"], cell=2.0)
    hx, hy = tip[:2]
    lk.box(bm, (hx - 0.3, hy - 0.3, z + height - 0.3), (hx + 0.3, hy + 0.3, z + height + 0.05),
           M["metal"], faces=("+x", "-x", "+y", "-y", "+z", "-z"), mats={"-z": M["lamp"]})
    return (hx, hy, z + height - 0.6)


def floodlight(bm, base, inward, height=7.0):
    x, y, z = base
    w = np.array((*inward, 0.0))
    side = np.array((-inward[1], inward[0], 0.0))
    lk.box(bm, (x - 0.15, y - 0.15, z), (x + 0.15, y + 0.15, z + height), M["metal"])
    c = np.array((x, y, z + height - 0.4)) + w * 0.35
    for s in (-0.55, 0.55):
        hc = c + side * s
        lo, hi = hc - np.array((0.3, 0.3, 0.3)), hc + np.array((0.3, 0.3, 0.3))
        key = ("+" if abs(inward[0]) > abs(inward[1]) and inward[0] > 0 else
               "-" if abs(inward[0]) > abs(inward[1]) else
               "+" if inward[1] > 0 else "-") + ("x" if abs(inward[0]) > abs(inward[1]) else "y")
        lk.box(bm, lo, hi, M["metal"], faces=("+x", "-x", "+y", "-y", "+z", "-z"), mats={key: M["lamp"]})
    return tuple(np.array((x, y, z + height - 0.6)) + w * 2.0)


def crate(bm, x, y, z, size):
    h = size / 2
    lk.box(bm, (x - h, y - h, z), (x + h, y + h, z + size), M["crate"], cell=size)


def jersey(bm, p0, p1, mat):
    prof = [(-0.3, 0.0), (0.3, 0.0), (0.26, 0.25), (0.12, 0.85), (-0.12, 0.85), (-0.26, 0.25)]
    lk.prism(bm, prof, p0, p1, mat, cell=2.0)


def container(bm, lo, hi, mat):
    lk.box(bm, lo, hi, mat, cell=1.3)


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

def build_road(G, rng):
    bm = G["level"]
    pts, z, wl, wr = road_stations()
    strips = [("L", -4.0, M["gravel"], 6), (-4.0, 4.0, M["asphalt"], 4), (4.0, "R", M["gravel"], 5)]
    tang, right = corridor(bm, pts, z, wl, wr, strips, rng, M, dashes=True)
    # Rock face closing the south end of the road (hidden round the bend).
    us = lk.coords(0, 26, 2.0)
    vs = lk.coords(0, 18, 2.0)
    lk.rock_face(lambda c: bm, (22.0, -37.0, 0.0), (0, 1, 0), (0, 0, 1), us, vs, (-1, 0, 0), rng,
                 amp=1.5, mat=M["rock"], pin_edges=("v0",))
    G["road"] = (pts, z)


def build_checkpoint(G, rng):
    bm = G["level"]
    lights = G["lights"]

    # Guard booth: 3x3 m hut on a concrete pad, door to the south, window to the road.
    lk.box(bm, (4.95, 12.85, 0), (8.45, 16.15, 0.15), M["concrete_dark"],
           faces=("+x", "-x", "+y", "-y", "+z"))
    z0, z1, th = 0.15, 2.8, 0.15
    lk.wall(bm, (5.125, 13.075), (8.275, 13.075), z0, z1, th, M["bldg_int"], M["bldg_ext"], M["metal"],
            openings=[(0.875, 2.575, 0.0, 2.4)], cell=1.0)
    lk.wall(bm, (5.125, 15.925), (8.275, 15.925), z0, z1, th, M["bldg_ext"], M["bldg_int"], M["metal"],
            openings=[(1.2, 2.2, 1.1, 1.9)], cell=1.0)
    lk.wall(bm, (5.2, 13.15), (5.2, 15.85), z0, z1, th, M["bldg_ext"], M["bldg_int"], M["metal"],
            openings=[(0.35, 2.35, 0.95, 1.95)], cell=1.0)
    lk.wall(bm, (8.2, 13.15), (8.2, 15.85), z0, z1, th, M["bldg_int"], M["bldg_ext"], M["metal"], cell=1.0)
    lk.box(bm, (4.95, 12.85, 2.8), (8.45, 16.15, 3.0), M["roof"],
           faces=("+x", "-x", "+y", "-y", "+z", "-z"), mats={"-z": M["ceiling"]})
    lk.grid(bm, (6.2, 14.0, 2.78), (1.0, 0, 0), (0, 1.0, 0), -UP, cell=2.0, mat=M["light"])
    lk.box(bm, (5.3, 13.4, 0.15), (5.9, 15.6, 0.95), M["metal"])  # desk under the window
    lk.box(bm, (6.6, 12.72, 2.55), (7.1, 12.85, 2.7), M["metal"],
           faces=("+x", "-x", "-y", "+z", "-z"), mats={"-z": M["lamp"]})
    lights.append(lk.Light((6.7, 14.5, 2.45), (1.0, 0.95, 0.8), 4.5, zones=("booth",)))
    lights.append(lk.Light((6.85, 12.3, 2.5), SODIUM, 8.0))

    # Barrier arm across the east lane.
    lk.box(bm, (4.45, 15.35, 0), (4.75, 15.65, 1.15), M["metal"])
    lk.slab(bm, (4.45, 15.5), (0.2, 15.5), 0.95, 1.08, 0.1, M["hazard"], cell=1.0)

    # Road-closed line at the south end and a chicane of concrete barriers.
    for x in np.arange(-8.3, 8.0, 2.05):
        jersey(bm, (x, -11.0), (x + 1.85, -11.0), M["barrier"])
    jersey(bm, (1.5, 6.0), (3.5, 6.0), M["barrier"])
    jersey(bm, (-3.5, 10.0), (-1.5, 10.0), M["barrier"])
    jersey(bm, (-3.5, 26.0), (-1.5, 26.0), M["barrier"])

    # Sandbag nest on the east shoulder and a wall behind the booth.
    for p0, p1 in (((9.0, 22.0), (9.0, 25.5)), ((9.3, 22.0), (12.0, 22.0)), ((9.3, 25.5), (12.0, 25.5)),
                   ((5.0, 17.2), (8.4, 17.2)), ((-15.4, 2.0), (-11.5, 2.0))):
        lk.slab(bm, p0, p1, 0.0, 1.0, 0.6, M["sandbag"], cell=1.0)

    # Supply containers and crates.
    container(bm, (-12.5, 18.0, 0), (-10.1, 24.0, 2.6), M["container_red"])
    container(bm, (-13.0, 29.0, 0), (-7.0, 31.4, 2.6), M["container_blue"])
    crate(bm, -9.3, 20.0, 0, 1.2)
    crate(bm, -9.3, 21.3, 0, 1.0)
    crate(bm, -9.3, 20.0, 1.2, 1.0)

    # Floodlights.
    lights.append(lk.Light(floodlight(bm, (-14.8, 9.0, 0), (1, 0)), SODIUM, 18.0))
    lights.append(lk.Light(floodlight(bm, (13.0, 31.0, 0), (-1, 0)), SODIUM, 18.0))

    # Street lamps up the climb and round the bend.
    for (x, y, zz), d in (((5.8, 58.0, road_z(12)), (-1, 0)), ((-5.8, 74.0, road_z(28)), (1, 0)),
                          ((5.8, 88.0, road_z(42)), (-1, 0)),
                          ((-15 + 20.8 * math.cos(math.radians(50)), 90 + 20.8 * math.sin(math.radians(50)),
                            road_z(44 + 15 * math.radians(50))),
                           (-math.cos(math.radians(50)), -math.sin(math.radians(50)))),
                          ((-19.0, 98.8, CREST_Z), (0, 1))):
        lights.append(lk.Light(lamp_post(bm, (x, y, zz), d), SODIUM, 16.0, zones=("out", "tunnel")))

    # Invisible wall behind the road-closed barriers.
    lk.box(G["bounds"], (-12.0, -12.4, 0), (12.0, -11.8, 6.0), 0,
           faces=("+x", "-x", "+y", "-y", "+z", "-z"))


def build_tunnel(G, rng):
    bm = G["level"]
    lights = G["lights"]
    x0, x1, y0, y1, z0 = -52.0, -22.0, 101.5, 108.5, CREST_Z
    L = x1 - x0
    lk.grid(bm, (x0, y0, z0), (L, 0, 0), (0, y1 - y0, 0), UP, cell=1.5, mat=M["asphalt"])
    for x in np.arange(x0 + 1, x1, 4.0):
        lk.grid(bm, (x, 104.92, z0 + 0.02), (2.0, 0, 0), (0, 0.16, 0), UP, cell=2.0, mat=M["paint"])
    # North wall, chamfers and ceiling.
    lk.grid(bm, (x0, y1, z0), (L, 0, 0), (0, 0, 1.0), -np.array((0, 1, 0)), cell=1.5, mat=M["concrete_dark"])
    lk.grid(bm, (x0, y1, z0 + 1), (L, 0, 0), (0, 0, 2.8), -np.array((0, 1, 0)), cell=1.5, mat=M["tunnel"])
    lk.grid(bm, (x0, y1, z0 + 3.8), (L, 0, 0), (0, -1.2, 1.2), (0, -1, -1), cell=1.5, mat=M["tunnel"])
    lk.grid(bm, (x0, y0 + 1.2, z0 + 5), (L, 0, 0), (0, 4.6, 0), -UP, cell=1.5, mat=M["concrete_dark"])
    lk.grid(bm, (x0, y0, z0 + 3.8), (L, 0, 0), (0, 1.2, 1.2), (0, 1, -1), cell=1.5, mat=M["tunnel"])
    # South wall with the alcove opening (x -40..-34).
    for a, b in ((x0, -40.0), (-34.0, x1)):
        lk.grid(bm, (a, y0, z0), (b - a, 0, 0), (0, 0, 1.0), (0, 1, 0), cell=1.5, mat=M["concrete_dark"])
        lk.grid(bm, (a, y0, z0 + 1), (b - a, 0, 0), (0, 0, 2.8), (0, 1, 0), cell=1.5, mat=M["tunnel"])
    lk.grid(bm, (-40.0, y0, z0 + 3.2), (6, 0, 0), (0, 0, 0.6), (0, 1, 0), cell=1.5, mat=M["tunnel"])
    # Alcove (6 x 4 x 3.2 m).
    ay0 = 97.5
    lk.grid(bm, (-40, ay0, z0), (6, 0, 0), (0, 4, 0), UP, cell=1.0, mat=M["concrete_dark"])
    lk.grid(bm, (-40, ay0, z0 + 3.2), (6, 0, 0), (0, 4, 0), -UP, cell=1.0, mat=M["concrete_dark"])
    lk.grid(bm, (-40, ay0, z0), (6, 0, 0), (0, 0, 1.0), (0, 1, 0), cell=1.0, mat=M["concrete_dark"])
    lk.grid(bm, (-40, ay0, z0 + 1), (6, 0, 0), (0, 0, 2.2), (0, 1, 0), cell=1.0, mat=M["tunnel"])
    for x, n in ((-40.0, 1), (-34.0, -1)):
        lk.grid(bm, (x, ay0, z0), (0, 4, 0), (0, 0, 1.0), (n, 0, 0), cell=1.0, mat=M["concrete_dark"])
        lk.grid(bm, (x, ay0, z0 + 1), (0, 4, 0), (0, 0, 2.2), (n, 0, 0), cell=1.0, mat=M["tunnel"])
    lk.grid(bm, (-37.5, 99.0, z0 + 3.18), (1.0, 0, 0), (0, 1.0, 0), -UP, cell=2.0, mat=M["light"])
    lk.box(bm, (-39.8, 97.5, z0), (-39.0, 98.1, z0 + 2.0), M["metal"])  # cabinet
    crate(bm, -34.8, 98.2, z0, 1.0)
    lights.append(lk.Light((-37.0, 99.5, z0 + 2.6), TUNNEL_LAMP, 5.5, zones=("tunnel",)))
    # Wall lamps.
    for x, wy, n in ((-25, y1, -1), (-37, y1, -1), (-49, y1, -1), (-29, y0, 1), (-46.5, y0, 1)):
        lo = (x - 0.3, min(wy, wy + n * 0.2), z0 + 3.0)
        hi = (x + 0.3, max(wy, wy + n * 0.2), z0 + 3.35)
        key = "-y" if n < 0 else "+y"
        lk.box(bm, lo, hi, M["metal"], faces=("+x", "-x", key, "+z", "-z"), mats={key: M["light"]})
        lights.append(lk.Light((x, wy + n * 0.8, z0 + 3.0), TUNNEL_LAMP, 8.0, zones=("tunnel",)))

    # East portal face (road side) with a flat concrete headwall.
    us = lk.coords(0, 42, 2.0, extra=(16, 17.5, 24.5, 26))
    vs = lk.coords(0, 20, 2.0, extra=(5, 6.5))
    lk.rock_face(lambda c: bm, (-22.0, 84.0, z0), (0, 1, 0), (0, 0, 1), us, vs, (1, 0, 0), rng,
                 amp=1.6, mat=M["rock"], holes=[(17.5, 24.5, 0, 5)], flats=[(16, 26, 0, 6.5)],
                 flat_mat=M["concrete"], pin_edges=("v0",))
    for x, nx in ((-22.0, 1), (-52.0, -1)):
        for ya, yb in ((y0, y0 + 1.2), (y1, y1 - 1.2)):
            lk.face(bm, [(x, ya, z0 + 3.8), (x, yb, z0 + 5), (x, ya, z0 + 5)], M["concrete"], (nx, 0, 0))


def _mountain_lean(u, v, keep=(42.0, 62.0), phase=0.0):
    """Valley walls narrow towards the river and lean back above the crest.
    v is height above the valley floor (z + 38); the band `keep` stays vertical
    around the crest so the tunnel portal and abutments line up."""
    shape = -0.35 * max(0.0, keep[0] - v) + 0.7 * max(0.0, v - keep[1] + 2.0)
    w = min(1.0, max(0.0, (keep[0] - v) / 8.0) + max(0.0, (v - keep[1]) / 8.0))
    wave = 4.0 * math.sin(u / 17.0 + phase) + 2.5 * math.sin(u / 7.3 + 2 * phase)
    return shape + w * wave


def build_valley_walls(G, rng):
    """Big rock faces: east (mountain, tunnel exit), west abutment, far shores."""
    level, vista = G["level"], G["vista"]
    far = M["rock_far"]
    # Fine cells (2 m) around the tunnel exit where the crest lamps light the rock.
    us = sorted({c for c in lk.coords(0, 255, 7.0) if c < 100 or c > 138}
                | {float(u) for u in np.arange(100.0, 138.1, 2.0)} | {109.5, 111.5, 118.5, 120.5})
    vs = sorted({c for c in lk.coords(0, 82, 6.0) if c < 42 or c > 64}
                | {42.0, 44.0, 46.0, 48.0, 50.0, 52.0, 53.0, 54.5, 56.0, 58.0, 60.0, 62.0, 64.0})

    def east_route(c):
        return level if 92 <= c[1] <= 118 and 8 <= c[2] <= 24 else vista

    lk.rock_face(east_route, (-52.0, -10.0, -38.0), (0, 1, 0), (0, 0, 1), us, vs, (-1, 0, 0), rng,
                 amp=2.0, mat=far, holes=[(111.5, 118.5, 48, 53)], flats=[(109.5, 120.5, 46, 54.5)],
                 flat_mat=M["concrete"], lean=lambda u, v: _mountain_lean(u, v), jag_top=6.0)
    us_w = sorted(set(lk.coords(0, 255, 7.0)) | {99.0, 131.0})
    vs_w = sorted(set(lk.coords(0, 82, 6.0)) | {48.0})
    lk.rock_face(lambda c: vista, (-142.0, -10.0, -38.0), (0, 1, 0), (0, 0, 1), us_w, vs_w, (1, 0, 0), rng,
                 amp=2.5, mat=far, holes=[(99.0, 131.0, 48.0, 82.0)],
                 lean=lambda u, v: _mountain_lean(u, v, phase=1.7), jag_top=6.0)
    # Valley floor, south end and far reservoir shore (all fogged vista).
    lk.grid(vista, (-142, -10, -38), (90, 0, 0), (0, 78, 0), UP, cell=9.0, mat=M["gravel"])
    lk.rock_face(lambda c: vista, (-160.0, -10.0, -38.0), (1, 0, 0), (0, 0, 1), lk.coords(0, 126, 9.0),
                 lk.coords(0, 70, 8.0), (0, 1, 0), rng, amp=6.0, mat=far, pin_edges=("v0",),
                 lean=lambda u, v: 0.4 * v + 5.0 * math.sin(u / 13.0), jag_top=7.0)
    lk.rock_face(lambda c: vista, (-160.0, 245.0, 0.0), (1, 0, 0), (0, 0, 1), lk.coords(0, 126, 9.0),
                 lk.coords(0, 45, 7.0), (0, -1, 0), rng, amp=6.0, mat=far,
                 lean=lambda u, v: 0.5 * v + 6.0 * math.sin(u / 11.0), jag_top=8.0)


def build_dam(G, rng):
    level, vista, bounds = G["level"], G["vista"], G["bounds"]
    lights = G["lights"]
    z = CREST_Z
    # Crest floor: asphalt lane between concrete walkways; platform in the middle.
    for a, b in ((-142.0, -107.0), (-87.0, -52.0)):
        lk.grid(level, (a, 100, z), (b - a, 0, 0), (0, 1.5, 0), UP, cell=2.0, mat=M["concrete"])
        lk.grid(level, (a, 101.5, z), (b - a, 0, 0), (0, 7.0, 0), UP, cell=2.0, mat=M["asphalt"])
        lk.grid(level, (a, 108.5, z), (b - a, 0, 0), (0, 1.5, 0), UP, cell=2.0, mat=M["concrete"])
        for x in np.arange(a + 1, b - 1, 4.0):
            lk.grid(level, (x, 104.92, z + 0.02), (2.0, 0, 0), (0, 0.16, 0), UP, cell=2.0, mat=M["paint"])
    lk.grid(level, (-107, 98, z), (20, 0, 0), (0, 6, 0), UP, cell=2.0, mat=M["concrete"])
    lk.grid(level, (-107, 104, z), (4, 0, 0), (0, 8, 0), UP, cell=2.0, mat=M["concrete"])
    lk.grid(level, (-91, 104, z), (4, 0, 0), (0, 8, 0), UP, cell=2.0, mat=M["concrete"])

    # Parapets (with invisible walls on top so nobody climbs over).
    parapets = [((-142, 100.2), (-107, 100.2)), ((-87, 100.2), (-52, 100.2)),
                ((-142, 109.8), (-107, 109.8)), ((-87, 109.8), (-52, 109.8)),
                ((-107, 98.2), (-87, 98.2)),
                ((-106.8, 98.0), (-106.8, 100.4)), ((-87.2, 98.0), (-87.2, 100.4)),
                ((-106.8, 109.6), (-106.8, 112.0)), ((-87.2, 109.6), (-87.2, 112.0)),
                ((-107, 111.8), (-103, 111.8)), ((-91, 111.8), (-87, 111.8))]
    for p0, p1 in parapets:
        lk.slab(level, p0, p1, z, z + 1.1, 0.4, M["concrete"], cell=1.5, top_mat=M["concrete_dark"])
        lk.slab(bounds, p0, p1, z + 1.1, z + 4.1, 0.4, 0, cell=10.0, bottom=True)

    # Downstream face: short vertical band, then a steep batter down into the fog.
    lk.grid(vista, (-142, 100, z - 2), (90, 0, 0), (0, 0, 2), (0, -1, 0), cell=3.0, mat=M["concrete"])
    drop, run = 46.0, 33.1
    spill = (-128.0, -116.0)
    for a, b in ((-142.0, spill[0]), (spill[1], -52.0)):
        lk.grid(vista, (a, 100, z - 2), (b - a, 0, 0), (0, -run, -drop), (0, -1, 0.7), cell=3.5,
                mat=M["concrete"])
    for x in (-136.0, -97.0, -79.0, -64.0):  # buttress ribs
        top, bot = np.array((0, 100.0, z - 2)), np.array((0, 100 - run, z - 2 - drop))
        n_face = np.array((0, -drop, run)) / np.hypot(drop, run)
        for sx, nx in ((x - 0.6, -1), (x + 0.6, 1)):
            p = [top + (sx, 0, 0), bot + (sx, 0, 0), bot + (sx, 0, 0) + n_face * 0.8, top + (sx, 0, 0) + n_face * 0.8]
            lk.face(vista, p, M["concrete"], (nx, 0, 0))
        p = [top + (x - 0.6, 0, 0) + n_face * 0.8, top + (x + 0.6, 0, 0) + n_face * 0.8,
             bot + (x + 0.6, 0, 0) + n_face * 0.8, bot + (x - 0.6, 0, 0) + n_face * 0.8]
        lk.face(vista, p, M["concrete"], n_face)
    # Stepped spillway chute with training walls.
    steps = 23
    rise, tread = drop / steps, run / steps
    w = spill[1] - spill[0]
    for k in range(steps):
        yk, zk = 100 - tread * k, z - 2 - rise * k
        lk.grid(vista, (spill[0], yk, zk - rise), (w, 0, 0), (0, 0, rise), (0, -1, 0), cell=3.0,
                mat=M["concrete_dark"])
        lk.grid(vista, (spill[0], yk - tread, zk - rise), (w, 0, 0), (0, tread, 0), UP, cell=3.0,
                mat=M["concrete"])
    n_face = np.array((0, -drop, run)) / np.hypot(drop, run)
    top, bot = np.array((0, 100.0, z - 2)), np.array((0, 100 - run, z - 2 - drop))
    for x, nx in ((spill[0], 1), (spill[1], -1)):
        inner = [top + (x, 0, 0) - n_face * 1.3, bot + (x, 0, 0) - n_face * 1.3,
                 bot + (x, 0, 0) + n_face * 1.8, top + (x, 0, 0) + n_face * 1.8]
        lk.face(vista, inner, M["concrete"], (nx, 0, 0))
        xo = x - nx * 0.5
        outer = [top + (xo, 0, 0), bot + (xo, 0, 0), bot + (xo, 0, 0) + n_face * 1.8, top + (xo, 0, 0) + n_face * 1.8]
        lk.face(vista, outer, M["concrete"], (-nx, 0, 0))
        cap = [top + (x, 0, 0) + n_face * 1.8, bot + (x, 0, 0) + n_face * 1.8,
               bot + (xo, 0, 0) + n_face * 1.8, top + (xo, 0, 0) + n_face * 1.8]
        lk.face(vista, cap, M["concrete_dark"], n_face)

    # Platform overhang on the downstream side.
    lk.grid(vista, (-107, 98, z - 1.5), (20, 0, 0), (0, 0, 1.5), (0, -1, 0), cell=2.0, mat=M["concrete"])
    lk.grid(vista, (-107, 98, z - 1.5), (20, 0, 0), (0, 2, 0), -UP, cell=2.0, mat=M["concrete_dark"])
    for x, nx in ((-107, -1), (-87, 1)):
        lk.grid(vista, (x, 98, z - 1.5), (0, 2, 0), (0, 0, 1.5), (nx, 0, 0), cell=2.0, mat=M["concrete"])

    # Upstream face down into the water, and spillway gate piers.
    for a, b in ((-142.0, -107.0), (-87.0, -52.0)):
        lk.grid(vista, (a, 110, 3.0), (b - a, 0, 0), (0, 0, z - 3.0), (0, 1, 0), cell=3.0, mat=M["concrete"])
    lk.grid(vista, (-107, 112, 3.0), (20, 0, 0), (0, 0, z - 3.0), (0, 1, 0), cell=2.0, mat=M["concrete"])
    for x, nx in ((-107, -1), (-87, 1)):
        lk.grid(vista, (x, 110, 3.0), (0, 2, 0), (0, 0, z - 3.0), (nx, 0, 0), cell=2.0, mat=M["concrete"])
    for px in (-128.5, -122.5, -116.5):
        lk.box(vista, (px, 110, 3.0), (px + 1.0, 114.0, z), M["concrete"], cell=2.0,
               faces=("+x", "-x", "+y", "+z"))
    for ga, gb in ((-127.5, -122.5), (-121.5, -116.5)):
        lk.slab(vista, (ga, 112.5), (gb, 112.5), 4.5, z - 0.4, 0.3, M["metal"], cell=2.0)

    # Crest lamps every ~15 m, alternating sides.
    for x, y, d in ((-58.0, 100.8, (0, 1)), (-73.0, 109.2, (0, -1)), (-88.2, 98.9, (0, 1)),
                    (-105.8, 98.9, (0, 1)), (-121.0, 109.2, (0, -1)), (-136.0, 100.8, (0, 1))):
        lights.append(lk.Light(lamp_post(level, (x, y, z), d), SODIUM, 16.0, zones=("out", "tunnel")))

    # Supply crates by the tunnel exit.
    crate(level, -56.4, 101.2, z, 1.2)
    crate(level, -57.8, 101.2, z, 1.2)
    crate(level, -57.1, 101.2, z + 1.2, 1.0)


def build_control_building(G, rng):
    bm, lights = G["level"], G["lights"]
    z0, z1 = CREST_Z, CREST_Z + 4.0
    ext, inn, edge = M["bldg_ext"], M["bldg_int"], M["concrete_dark"]
    lk.grid(bm, (-103, 104, z0), (12, 0, 0), (0, 8, 0), UP, cell=1.0, mat=M["floor_tile"])
    # South wall: west doorway, lit window, vestibule doorway.
    lk.wall(bm, (-103, 104.15), (-91, 104.15), z0, z1, 0.3, inn, ext, edge,
            openings=[(1.0, 3.0, 0.0, 2.6), (4.0, 7.0, 1.2, 2.8), (9.0, 11.0, 0.0, 2.6)])
    # North wall: barred window over the consoles, facing the reservoir.
    lk.wall(bm, (-103, 111.85), (-91, 111.85), z0, z1, 0.3, ext, inn, edge,
            openings=[(1.0, 7.0, 1.8, 3.2)])
    lk.wall(bm, (-102.85, 104.3), (-102.85, 111.7), z0, z1, 0.3, ext, inn, edge)
    lk.wall(bm, (-91.15, 104.3), (-91.15, 111.7), z0, z1, 0.3, inn, ext, edge)
    lk.wall(bm, (-95.0, 104.3), (-95.0, 111.7), z0, z1, 0.2, inn, inn, edge,
            openings=[(2.7, 4.7, 0.0, 2.6)])
    # Lit window glass in the south wall (warm outside, dark night glass inside).
    lk.grid(bm, (-99, 104.14, z0 + 1.2), (3, 0, 0), (0, 0, 1.6), (0, -1, 0), cell=4.0, mat=M["window_lit"])
    lk.grid(bm, (-99, 104.16, z0 + 1.2), (3, 0, 0), (0, 0, 1.6), (0, 1, 0), cell=4.0, mat=M["window_dark"])
    # Bars in the reservoir window.
    for x in np.arange(-101.85, -96.0, 0.3):
        lk.box(bm, (x - 0.03, 111.8, z0 + 1.8), (x + 0.03, 111.9, z0 + 3.2), M["metal"], cell=2.0,
               faces=("+x", "-x", "+y", "-y"))
    lk.box(bm, (-102.0, 111.8, z0 + 2.45), (-96.0, 111.9, z0 + 2.55), M["metal"], cell=6.0,
           faces=("+y", "-y", "+z", "-z"))
    # Ceiling, roof slab and lights.
    lk.grid(bm, (-102.7, 104.3, z1 - 0.02), (11.4, 0, 0), (0, 7.4, 0), -UP, cell=1.5, mat=M["ceiling"])
    lk.box(bm, (-103.3, 103.7, z1), (-90.7, 112.3, z1 + 0.4), M["roof"], cell=2.0,
           faces=("+x", "-x", "+y", "-y", "+z"), mats={k: M["concrete_dark"] for k in ("+x", "-x", "+y", "-y")})
    for a, b in (((-103.3, 103.7), (12.6, 0.6)), ((-103.3, 111.7), (12.6, 0.6)),
                 ((-103.3, 104.3), (0.6, 7.4)), ((-91.3, 104.3), (0.6, 7.4))):
        lk.grid(bm, (*a, z1), (b[0], 0, 0), (0, b[1], 0), -UP, cell=2.0, mat=M["concrete_dark"])
    for x in (-100.9, -97.2, -93.1):
        lk.grid(bm, (x - 0.9, 107.7, z1 - 0.04), (1.8, 0, 0), (0, 0.6, 0), -UP, cell=2.0, mat=M["light"])
        lights.append(lk.Light((x, 108.0, z1 - 0.9), FLUORESCENT, 7.5, zones=("bldg",)))
    lk.box(bm, (-93.3, 103.72, z0 + 2.85), (-92.7, 104.0, z0 + 3.0), M["metal"],
           faces=("+x", "-x", "-y", "+z", "-z"), mats={"-z": M["lamp"]})
    lights.append(lk.Light((-93.0, 103.2, z0 + 2.7), SODIUM, 9.0))
    lights.append(lk.Light((-97.5, 103.0, z0 + 2.0), (0.45, 0.4, 0.25), 5.0))
    # Console bank along the north wall.
    for a, b in ((-102.55, -100.25), (-100.05, -97.75), (-97.55, -95.25)):
        lk.box(bm, (a, 110.6, z0), (b, 111.7, z0 + 0.9), M["metal"], cell=2.5,
               faces=("+x", "-x", "-y"), mats={"-y": M["console"]})
        desk = [(a, 110.6, z0 + 0.9), (b, 110.6, z0 + 0.9), (b, 111.1, z0 + 1.1), (a, 111.1, z0 + 1.1)]
        lk.face(bm, desk, M["console"], (0, -0.4, 1))
        for x in (a, b):
            lk.face(bm, [(x, 110.6, z0 + 0.9), (x, 111.1, z0 + 1.1), (x, 111.1, z0 + 0.9)], M["metal"],
                    (1 if x == b else -1, 0, 0))
        lk.box(bm, (a, 111.1, z0 + 0.9), (b, 111.7, z0 + 1.65), M["metal"], cell=2.5,
               faces=("+x", "-x", "-y", "+z"), mats={"-y": M["screen"]})
    # Equipment cabinets on the west wall and a desk in the vestibule.
    lk.box(bm, (-102.7, 105.0, z0), (-102.1, 108.4, z0 + 2.1), M["metal"], cell=1.2,
           mats={"+x": M["console"]})
    lk.box(bm, (-94.9, 104.9, z0), (-94.1, 106.4, z0 + 0.8), M["metal"], cell=1.5)


def build_relay(G, rng):
    bm, lights, bounds = G["level"], G["lights"], G["bounds"]
    z = CREST_Z
    # Rock shelf floor and enclosing ridges.
    lk.grid(bm, (-176, 89, z), (34, 0, 0), (0, 32, 0), UP, cell=2.0, mat=M["gravel"])
    for pts in (((-142, 110), (-142, 121), (-176, 121), (-176, 107.5)),
                ((-176, 100.5), (-176, 89), (-142, 89), (-142, 100))):
        base = lk.polyline_samples([(x, y, z) for x, y in pts], step=2.0)
        lk.ridge(bm, base, lk.polyline_inward(base, "left"), rng, M["rock"])

    # Gravel service road west into the fog.
    pts = [np.array((-176.0, 104.0))] + sample_line((-176, 104), (-190, 104))
    pts += sample_arc((-190, 124), 20, -math.pi / 2, -math.pi * 0.75)
    pts = np.array(pts)
    zs = np.full(len(pts), z)
    ws = np.full(len(pts), 3.5)
    tang, right = corridor(bm, pts, zs, ws, ws, [("L", "R", M["gravel"], 3)], rng, M)
    end, t_end, r_end = pts[-1], tang[-1], right[-1]
    side = np.array((*r_end, 0.0))
    origin = np.array((*end, z)) - side * 12.0
    lk.rock_face(lambda c: bm, origin, side, (0, 0, 1), lk.coords(0, 24, 2.0), lk.coords(0, 18, 2.0),
                 (-t_end[0], -t_end[1], 0), rng, amp=1.5, mat=M["rock"], pin_edges=("v0",))
    lk.box(bounds, (-188.6, 97.0, z), (-188.0, 111.0, z + 6), 0, faces=("+x", "-x", "+y", "-y", "+z", "-z"))
    lights.append(lk.Light(lamp_post(bm, (-178.0, 100.9, z), (0, 1)), SODIUM, 14.0))

    # Fence (opaque palisade) with posts, an open east entrance and a service gate west.
    fz0, fz1 = z, z + 2.8
    runs = [((-170, 92.5), (-145, 92.5)), ((-170, 117.5), (-145, 117.5)),
            ((-145, 92.5), (-145, 101)), ((-145, 109), (-145, 117.5)),
            ((-170, 92.5), (-170, 100.5)), ((-170, 107.5), (-170, 117.5))]
    for p0, p1 in runs:
        lk.slab(bm, p0, p1, fz0, fz1, 0.1, M["fence"], cell=2.0, top_mat=M["metal"])
        p0, p1 = np.array(p0, float), np.array(p1, float)
        n_posts = max(1, round(np.linalg.norm(p1 - p0) / 4.0))
        for k in range(n_posts + 1):
            px, py = p0 + (p1 - p0) * k / n_posts
            lk.box(bm, (px - 0.1, py - 0.1, z), (px + 0.1, py + 0.1, fz1 + 0.2), M["metal"], cell=2.0)
    for hy, sgn in ((100.5, 1), (107.5, -1)):  # gate leaves swung outwards
        a = math.radians(70)
        tip = (-170 - 3.5 * math.sin(a), hy + sgn * 3.5 * math.cos(a))
        lk.slab(bm, (-170.15, hy), tip, z + 0.05, z + 2.6, 0.08, M["fence"], cell=2.0, top_mat=M["metal"])
        lk.box(bm, (-170.2, hy - 0.15, z), (-169.8, hy + 0.15, z + 3.2), M["metal"], cell=2.0)
        lk.box(bm, (-170.1, hy - 0.1 - sgn * 0.3, z + 2.95), (-169.9, hy + 0.1 - sgn * 0.3, z + 3.15),
               M["red_light"], cell=2.0)
        lights.append(lk.Light((-169.6, hy - sgn * 0.3, z + 2.9), RED, 6.0))
    for gy in (101.0, 109.0):
        lk.box(bm, (-145.2, gy - 0.2, z), (-144.8, gy + 0.2, z + 3.2), M["metal"], cell=2.0)

    # Equipment hut (5 x 5 m) in the north-west corner.
    lk.box(bm, (-167.2, 110.8, z), (-161.8, 116.2, z + 0.12), M["concrete_dark"], cell=2.0)
    hz0, hz1 = z + 0.12, z + 3.2
    lk.wall(bm, (-167, 111.1), (-162, 111.1), hz0, hz1, 0.2, M["bldg_int"], M["bldg_ext"], M["metal"],
            openings=[(1.6, 3.4, 0.0, 2.5)])
    lk.wall(bm, (-167, 115.9), (-162, 115.9), hz0, hz1, 0.2, M["bldg_ext"], M["bldg_int"], M["metal"])
    lk.wall(bm, (-166.9, 111.2), (-166.9, 115.8), hz0, hz1, 0.2, M["bldg_ext"], M["bldg_int"], M["metal"])
    lk.wall(bm, (-162.1, 111.2), (-162.1, 115.8), hz0, hz1, 0.2, M["bldg_int"], M["bldg_ext"], M["metal"])
    lk.box(bm, (-167.2, 110.8, hz1), (-161.8, 116.2, hz1 + 0.2), M["roof"], cell=2.0,
           faces=("+x", "-x", "+y", "-y", "+z", "-z"), mats={"-z": M["ceiling"]})
    lk.grid(bm, (-165.0, 113.0, hz1 - 0.02), (1.0, 0, 0), (0, 1.0, 0), -UP, cell=2.0, mat=M["light"])
    lights.append(lk.Light((-164.5, 113.5, hz1 - 0.6), FLUORESCENT, 5.5, zones=("hut",)))
    lk.box(bm, (-166.7, 115.2, hz0), (-165.1, 115.8, hz0 + 1.9), M["metal"], cell=1.0)
    lk.box(bm, (-163.6, 115.1, hz0), (-162.3, 115.8, hz0 + 0.85), M["metal"], cell=1.5,
           mats={"-y": M["console"], "+z": M["console"]})
    lk.box(bm, (-164.8, 110.82, z + 2.9), (-164.2, 111.0, z + 3.1), M["red_light"], cell=2.0,
           faces=("+x", "-x", "-y", "+z", "-z"))
    lights.append(lk.Light((-164.5, 110.3, z + 2.7), RED, 7.0))

    # Generators, crates and the mast footing.
    for a in (-164.0, -160.5):
        lk.box(bm, (a, 93.2, z), (a + 2.5, 94.6, z + 1.6), M["generator"], cell=1.5, mats={"+z": M["metal"]})
        lk.box(bm, (a + 0.3, 93.6, z + 1.6), (a + 0.6, 93.9, z + 2.4), M["metal"], cell=2.0)
    crate(bm, -160.5, 103.0, z, 1.2)
    crate(bm, -159.3, 103.0, z, 1.2)
    crate(bm, -151.0, 111.5, z, 1.0)
    lk.box(bm, (-156.2, 105.8, z), (-153.8, 108.2, z + 0.25), M["concrete"], cell=1.2)
    lk.box(bm, (-155.55, 106.45, z + 0.25), (-154.45, 107.55, z + 0.55), M["concrete_dark"], cell=1.2)

    # Floodlights (sodium) and red warning lights.
    lights.append(lk.Light(floodlight(bm, (-146.2, 93.6, z), (-0.7071, 0.7071)), SODIUM, 18.0))
    lights.append(lk.Light(floodlight(bm, (-168.8, 116.4, z), (0.7071, -0.7071)), SODIUM, 18.0))
    lights.append(lk.Light((-155.0, 107.0, z + 11.3), RED, 12.0))
    lights.append(lk.Light((-155.0, 107.0, z + 5.5), (0.5, 0.08, 0.05), 7.0))


MAST_BASE = (-155.0, 107.0, CREST_Z + 0.55)


def build_uplink_dish(bm):
    """Upper lattice mast + dish in local space; origin is the mast base."""
    rings = [(k, 0.45 - 0.02 * k) for k in range(11)]
    for (za, ha), (zb, hb) in zip(rings, rings[1:]):
        for sx, sy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            n = np.array((sx, sy, 0.0))
            t = np.array((-sy, sx, 0.0))
            quad = [n * ha - t * ha + UP * za, n * ha + t * ha + UP * za,
                    n * hb + t * hb + UP * zb, n * hb - t * hb + UP * zb]
            lk.face(bm, quad, M["lattice"], n)
    for pz, ph in ((5.0, 0.8), (9.0, 0.7)):
        lk.box(bm, (-ph, -ph, pz), (ph, ph, pz + 0.1), M["metal"], cell=2.0,
               faces=("+x", "-x", "+y", "-y", "+z", "-z"))
    lk.box(bm, (-0.3, -0.3, 10.0), (0.3, 0.3, 10.2), M["metal"], cell=2.0,
           faces=("+x", "-x", "+y", "-y", "+z", "-z"))
    lk.box(bm, (-0.1, -0.1, 10.2), (0.1, 0.1, 10.5), M["red_light"], cell=2.0)
    # Dish aimed south-west and tilted 30 degrees up.
    yaw = math.radians(225)
    axis = np.array((math.cos(yaw) * math.cos(math.radians(30)),
                     math.sin(yaw) * math.cos(math.radians(30)), math.sin(math.radians(30))))
    side = np.cross(UP, axis)
    side /= np.linalg.norm(side)
    up2 = np.cross(axis, side)
    centre = np.array((0, 0, 9.4)) + axis * 0.9
    lk.slab(bm, (0, 0), centre[:2], 9.3, 9.5, 0.2, M["metal"], cell=2.0)
    rim_r, depth, segs = 1.3, 0.45, 10
    rim = [centre + (side * math.cos(a) + up2 * math.sin(a)) * rim_r
           for a in np.linspace(0, 2 * math.pi, segs, endpoint=False)]
    mid = [centre + (side * math.cos(a) + up2 * math.sin(a)) * rim_r * 0.55 - axis * depth * 0.7
           for a in np.linspace(0, 2 * math.pi, segs, endpoint=False)]
    apex = centre - axis * depth
    back = centre - axis * (depth + 0.25)
    for i in range(segs):
        j = (i + 1) % segs
        lk.face(bm, [rim[i], rim[j], mid[j], mid[i]], M["dish"], axis)
        lk.face(bm, [mid[i], mid[j], apex], M["dish"], axis)
        lk.face(bm, [rim[i], rim[j], back], M["metal"], -axis)
    feed = centre + axis * 0.9
    lk.slab(bm, apex[:2], feed[:2], apex[2] - 0.04 + 0.0, apex[2] + 0.04, 0.08, M["metal"], cell=2.0)
    lk.box(bm, feed - 0.12, feed + 0.12, M["metal"], cell=2.0, faces=("+x", "-x", "+y", "-y", "+z", "-z"))


# --------------------------------------------------------------------------
# Lighting, markers, assembly
# --------------------------------------------------------------------------

ZONES = {
    "booth": ((5.265, 13.14, 0.1), (8.135, 15.86, 2.82)),
    "tunnel": ((-51.95, 97.45, 9.9), (-22.05, 108.55, 15.1)),
    "bldg": ((-102.72, 104.28, 9.9), (-91.28, 111.72, 14.05)),
    "hut": ((-166.82, 111.18, 10.0), (-162.18, 115.82, 13.25)),
}
INTERIOR_AMBIENT = {"booth": (0.17, 0.17, 0.19), "tunnel": (0.15, 0.15, 0.17),
                    "bldg": (0.18, 0.19, 0.20), "hut": (0.16, 0.16, 0.18)}
MOON_DIR = np.array((-0.35, 0.45, 0.82)) / np.linalg.norm((-0.35, 0.45, 0.82))


def night_ambient(zone_id, names, pos, nrm):
    base = np.array((0.34, 0.37, 0.46))
    moon = np.array((0.15, 0.17, 0.24))
    sky = np.array((0.04, 0.05, 0.08))
    col = (base[None, :] + moon[None, :] * np.clip(nrm @ MOON_DIR, 0, None)[:, None]
           + sky[None, :] * np.clip(nrm[:, 2], 0, None)[:, None])
    # Fade the deep valley and dam toe so the drop reads as depth.
    col *= np.clip(1.0 + pos[:, 2:3] / 70.0, 0.45, 1.0)
    for zi, name in enumerate(names):
        if name in INTERIOR_AMBIENT:
            col[zone_id == zi] = INTERIOR_AMBIENT[name]
    return col


def place_markers():
    mk = lk.marker
    yaw = lk.yaw_towards
    N, S, E, W = yaw(0, 1), yaw(0, -1), yaw(1, 0), yaw(-1, 0)
    z = CREST_Z
    mk("PlayerSpawn", (0.0, -8.0, 0.0), N)

    patrols = {
        "A": [(-7.5, 15.0, 0), (-7.5, 27.5, 0), (-5.5, 34.0, 0), (-14.3, 34.5, 0), (-14.3, 26.5, 0),
              (-14.3, 15.0, 0)],
        "B": [(-17.0, 105.0, z), (-30.0, 107.0, z), (-49.0, 105.0, z), (-30.0, 103.0, z)],
        "C": [(-56.0, 105.0, z), (-70.0, 108.0, z), (-84.0, 105.0, z), (-70.0, 102.0, z)],
        "D": [(-110.0, 105.0, z), (-125.0, 108.0, z), (-139.0, 105.0, z), (-125.0, 102.0, z)],
        "E": [(-148.5, 96.0, z), (-148.5, 114.5, z), (-158.5, 113.0, z), (-167.8, 104.0, z),
              (-157.0, 97.5, z)],
    }
    for route, pts in patrols.items():
        for i, p in enumerate(pts):
            nxt = pts[(i + 1) % len(pts)]
            mk(f"Patrol_{route}_{i + 1:02d}", p, yaw(nxt[0] - p[0], nxt[1] - p[1]))

    def on_route(route, idx):
        pts = patrols[route]
        p, nxt = pts[idx], pts[(idx + 1) % len(pts)]
        return p, yaw(nxt[0] - p[0], nxt[1] - p[1])

    guards = [
        ("Guard_01_idle", (4.9, 11.8, 0.0), S),
        ("Guard_02_patrol_A", *on_route("A", 0)),
        ("Guard_03_patrol_A", *on_route("A", 3)),
        ("Guard_04_patrol_B", *on_route("B", 0)),
        ("Guard_05_idle", (-37.5, 100.0, z), N),
        ("Guard_06_patrol_C", *on_route("C", 2)),
        ("Guard_07_patrol_D", *on_route("D", 1)),
        ("Guard_08_idle", (-61.0, 107.5, z), E),
        ("Guard_09_idle", (-89.0, 100.3, z), E),
        ("Guard_10_idle", (-92.0, 109.8, z), S),
        ("Guard_11_idle", (-96.0, 105.0, z), W),
        ("Guard_12_idle", (-101.8, 109.0, z), S),
        ("Guard_13_patrol_E", *on_route("E", 0)),
        ("Guard_14_idle", (-165.5, 109.3, z), E),
        ("Guard_15_idle", (-149.5, 108.0, z), E),
    ]
    for name, pos, rot in guards:
        mk(name, pos, rot)

    mk("Alarm_01", (8.125, 14.5, 0.15 + 1.3), W)
    mk("Alarm_02", (-36.5, 97.5, z + 1.3), N)
    mk("Alarm_03", (-162.0, 113.5, z + 0.12 + 1.3), E)
    mk("Obj_AlarmGrid", (-91.3, 107.0, z + 1.3), W)
    mk("Obj_DataTap", (-98.9, 109.9, z), N)
    mk("Obj_Uplink", (-155.0, 105.4, z), N)
    mk("Exit", (-180.0, 104.0, z + 1.5), W, display="CUBE", scale=(2.5, 3.5, 2.0))

    pickups = [
        ("Pickup_Armor_01", (7.3, 15.1, 0.15)),
        ("Pickup_Armor_02", (-101.5, 104.9, z)),
        ("Pickup_AmmoP9_01", (10.8, 23.7, 0.0)),
        ("Pickup_AmmoP9_02", (-36.2, 98.4, z)),
        ("Pickup_AmmoP9_03", (-164.5, 113.8, z + 0.12)),
        ("Pickup_AmmoVK12_01", (-55.0, 101.2, z)),
        ("Pickup_AmmoVK12_02", (-98.5, 104.9, z)),
        ("Pickup_AmmoVK12_03", (-152.0, 95.0, z)),
        ("Pickup_AmmoTalon12_01", (-131.0, 101.5, z)),
        ("Pickup_AmmoTalon12_02", (-163.4, 113.0, z + 0.12)),
        ("Pickup_WeaponVK12_01", (-59.2, 101.2, z)),
        ("Pickup_WeaponTalon12_01", (-94.0, 111.0, z)),
    ]
    for name, pos in pickups:
        mk(name, pos, 0.0)


def finish(bm, name, materials, lights):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)
    bm.normal_update()
    lk.project_uvs(bm, UV_SCALES, FACE_MAPPED)
    obj = rk.mesh_object(name, bm, materials)
    return obj


def main():
    rk.reset_scene()
    images = build_textures(np.random.default_rng(69))
    materials = [rk.make_material("M_sp_" + name, images[name]) for name in MATERIALS]
    rng = np.random.default_rng(1969)

    G = {k: bmesh.new() for k in ("level", "vista", "water", "dish", "bounds")}
    G["lights"] = []
    build_road(G, rng)
    build_checkpoint(G, rng)
    build_tunnel(G, rng)
    build_valley_walls(G, rng)
    build_dam(G, rng)
    build_control_building(G, rng)
    build_relay(G, rng)
    build_uplink_dish(G["dish"])
    lk.grid(G["water"], (-142, 110, WATER_Z), (90, 0, 0), (0, 135, 0), UP, cell=6.0, mat=M["water"])

    lights = G["lights"]
    objs = [
        finish(G["level"], "Spillway_Level-col", materials, lights),
        finish(G["vista"], "Spillway_Vista", materials, lights),
        finish(G["water"], "Water", materials, lights),
    ]
    dish = finish(G["dish"], "Uplink_Dish-convcol", materials, lights)
    dish.location = MAST_BASE
    bounds = finish(G["bounds"], "Spillway_Bounds-colonly", [], lights)
    bpy.context.view_layer.update()
    for obj in objs + [dish]:
        lk.bake_vertex_lighting(obj, lights, night_ambient, ZONES, FULLBRIGHT)
    lk.bake_vertex_lighting(bounds, [], lambda zi, n, p, nr: np.ones((len(p), 3)))

    place_markers()
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs + [dish])
    print("SPILLWAY triangles (visible):", tris, "lights:", len(lights))
    rk.export_glb(os.path.join("levels", "spillway", "spillway.glb"), "spillway.blend")


main()
