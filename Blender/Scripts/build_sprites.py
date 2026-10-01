"""Paint the 2D effect/HUD sprites as crisp RGBA pixel art.

Run:  blender -b --factory-startup --python Blender/Scripts/build_sprites.py
Output: Game/assets/sprites/*.png and Blender/Source/sprites.blend (images packed)

Alpha is stepped (a few discrete levels, mostly 0 or 1) to keep edges crisp.
"""

import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import model_kit as mk  # noqa: E402
import retro_kit as rk  # noqa: E402

SPRITE_DIR = os.path.join(mk.GAME_ASSET_DIR, "sprites")
RNG = np.random.default_rng(6969)


def canvas(w, h):
    return np.zeros((h, w, 4))


def polar(size, cx=None, cy=None):
    c = (size - 1) / 2
    cx = c if cx is None else cx
    cy = c if cy is None else cy
    y, x = np.mgrid[0:size, 0:size]
    dx, dy = x - cx, y - cy
    return np.hypot(dx, dy), np.arctan2(dy, dx)


def paint_levels(img, d, levels):
    """levels: [(threshold, (r, g, b, a)), ...] ascending; d < threshold gets the colour."""
    for threshold, color in reversed(levels):
        img[d < threshold] = color
    return img


def muzzle_flash():
    size = 32
    dist, ang = polar(size)
    spikes = 5.0 + 10.5 * np.abs(np.cos(2 * ang)) ** 10 + 5.5 * np.abs(np.sin(2 * ang)) ** 12
    spikes += 2.0 * np.abs(np.cos(4 * ang + 0.4)) ** 6         # small secondary points
    d = dist / spikes
    img = canvas(size, size)
    return paint_levels(img, d, [
        (0.30, (1.00, 1.00, 0.96, 1.0)),
        (0.52, (1.00, 0.97, 0.62, 1.0)),
        (0.76, (1.00, 0.84, 0.25, 1.0)),
        (1.00, (0.95, 0.52, 0.10, 0.85)),
    ])


def bullet_hole():
    k, d, r, c = (0.04, 0.04, 0.04, 1.0), (0.16, 0.15, 0.14, 1.0), (0.58, 0.56, 0.52, 1.0), (0.40, 0.38, 0.36, 0.75)
    o = (0, 0, 0, 0)
    rows = [
        "..c.cc..",
        ".crrrcc.",
        "crdddr..",
        ".rdkkdrc",
        "crdkkdr.",
        ".crddrc.",
        "..crrc..",
        "...c.c..",
    ]
    lut = {".": o, "k": k, "d": d, "r": r, "c": c}
    return np.array([[lut[ch] for ch in row] for row in rows], dtype=float)


def blob_mask(size, blobs):
    y, x = np.mgrid[0:size, 0:size]
    field = np.zeros((size, size))
    for bx, by, br in blobs:
        field = np.maximum(field, 1.0 - np.hypot(x - bx, y - by) / br)
    return field


def puff(size, blobs, dark, mid, light, alpha_edge=0.6):
    """Cauliflower cloud: each lump gets its own top-left highlight."""
    y, x = np.mgrid[0:size, 0:size]
    field = blob_mask(size, blobs)
    shade = np.full((size, size), -1.0)
    for bx, by, br in blobs:  # later (front) lumps overwrite earlier ones
        inside = np.hypot(x - bx, y - by) < br * 0.92
        lit = 1.0 - np.hypot(x - (bx - br * 0.35), y - (by - br * 0.4)) / (br * 1.25)
        shade = np.where(inside, lit, shade)
    img = canvas(size, size)
    inside = field > 0.0
    solid = field > 0.1
    img[inside] = (*dark, alpha_edge)
    img[solid] = (*dark, 1.0)
    img[solid & (shade > 0.25)] = (*mid, 1.0)
    img[solid & (shade > 0.62)] = (*light, 1.0)
    edge = inside & ~solid
    img[edge & ((x + y) % 2 == 0)] = 0.0
    return img


def impact_puff():
    return puff(16, [(11, 10.5, 3.6), (4.5, 10.5, 3.6), (7.5, 11, 4.0), (10.5, 6, 4.0), (5, 6, 4.2), (7.8, 7.8, 4.2)],
                dark=(0.36, 0.35, 0.33), mid=(0.56, 0.55, 0.52), light=(0.76, 0.75, 0.72))


def hit_puff():
    return puff(16, [(9.5, 10.5, 2.8), (5.5, 10, 2.8), (10, 6.5, 3.0), (5.4, 6.2, 3.0), (7.6, 8.2, 3.4)],
                dark=(0.30, 0.03, 0.04), mid=(0.50, 0.07, 0.07), light=(0.68, 0.16, 0.12), alpha_edge=0.5)


def explosion_sheet():
    frames = 8
    sheet = canvas(32 * frames, 32)
    # (radius, core fraction, fire amount 0..1, alpha, noise)
    specs = [(4.5, 0.55, 1.0, 1.0, 0.6), (8.0, 0.45, 1.0, 1.0, 1.2), (11.0, 0.35, 1.0, 1.0, 1.6),
             (13.5, 0.22, 0.8, 1.0, 2.0), (14.5, 0.08, 0.45, 1.0, 2.2), (15.0, 0.0, 0.15, 0.9, 2.4),
             (15.5, 0.0, 0.0, 0.6, 2.6), (15.5, 0.0, 0.0, 0.3, 2.8)]
    y, x = np.mgrid[0:32, 0:32]
    for i, (radius, core, fire, alpha, wobble) in enumerate(specs):
        dist, ang = polar(32, 15.5, 16.5 - i * 0.4)
        phase = RNG.random(3) * 6.28
        edge = radius + wobble * (np.sin(5 * ang + phase[0]) + 0.6 * np.sin(9 * ang + phase[1])
                                  + 0.4 * np.sin(13 * ang + phase[2]))
        d = dist / np.maximum(edge, 1.0)
        noise = RNG.random((32, 32)) * 0.18
        img = canvas(32, 32)
        # smoke body, darker toward the bottom-right
        smoke_shade = 0.18 + 0.22 * (1 - (x + y) / 62.0) + noise * 0.5
        smoke = d < 1.0
        grey = np.clip(np.round(smoke_shade * 6) / 6, 0.1, 0.5)
        img[smoke, 0] = grey[smoke]
        img[smoke, 1] = grey[smoke] * 0.97
        img[smoke, 2] = grey[smoke] * 0.94
        img[smoke, 3] = 1.0
        # fire layers take over the inside while the fireball is hot
        if fire > 0:
            f = d + noise - 0.1
            img[f < fire * 1.0] = (0.78, 0.18, 0.05, 1.0)
            img[f < fire * 0.8] = (0.96, 0.45, 0.08, 1.0)
            img[f < fire * 0.6] = (1.0, 0.75, 0.2, 1.0)
            img[f < core] = (1.0, 0.97, 0.75, 1.0)
        # fade out by dithering alpha (crisp pixels, no smooth ramps)
        if alpha < 1.0:
            thresh = np.array([[0.0, 0.5, 0.125, 0.625], [0.75, 0.25, 0.875, 0.375],
                               [0.1875, 0.6875, 0.0625, 0.5625], [0.9375, 0.4375, 0.8125, 0.3125]])
            dither = np.tile(thresh, (8, 8))
            img[(dither >= alpha) & smoke] = 0.0
        img[~smoke] = 0.0
        sheet[:, i * 32:(i + 1) * 32] = img
    return sheet


def crosshair():
    size = 16
    white = np.zeros((size, size), dtype=bool)
    c = 7
    white[1:5, c] = white[10:14, c] = True
    white[c, 1:5] = white[c, 10:14] = True
    outline = np.zeros_like(white)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            outline |= np.roll(np.roll(white, dy, 0), dx, 1)
    outline &= ~white
    img = canvas(size, size)
    img[outline] = (0.05, 0.05, 0.05, 0.85)
    img[white] = (1.0, 1.0, 1.0, 1.0)
    return img


SPRITES = {
    "muzzle_flash": muzzle_flash,
    "bullet_hole": bullet_hole,
    "impact_puff": impact_puff,
    "hit_puff": hit_puff,
    "explosion_sheet": explosion_sheet,
    "crosshair": crosshair,
}


def main():
    rk.reset_scene()
    for name, fn in SPRITES.items():
        img = fn()
        path = os.path.join(SPRITE_DIR, name + ".png")
        mk.save_png_rgba(path, img)
        image = bpy.data.images.load(path)
        image.pack()
        print(f"SPRITE {name} {img.shape[1]}x{img.shape[0]}")
    mk.save_blend("sprites.blend")


main()
