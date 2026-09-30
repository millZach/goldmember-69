"""Build the Milestone 0 test room: prelit hall, platform with ramp, pillars and crates.

Run:  blender -b --factory-startup --python Blender/Scripts/build_test_room.py
Output: Game/assets/levels/test_room/test_room.glb and Blender/Source/test_room.blend
"""

import os
import sys

import bmesh
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import retro_kit as rk  # noqa: E402

# Room extents in Blender units (meters). Blender is Z-up; +Y becomes Godot -Z.
X0, X1 = -10.0, 10.0
Y0, Y1 = -14.0, 14.0
HEIGHT = 5.0
BAND = 1.0  # height of the dark lower wall band

WALL, WALL_BAND, FLOOR, CEILING, LIGHT_PANEL, HAZARD = range(6)


def build_textures(rng):
    textures = {}

    # Concrete wall panels with horizontal and vertical seams.
    v = rk.fbm(64, rng) * 0.8 + rng.random((64, 64)) * 0.2
    v[[0, 32], :] *= 0.55
    v[:, 0] *= 0.6
    v[[1, 33], :] = np.minimum(1.0, v[[1, 33], :] * 1.25)
    textures["wall"] = rk.ramp(rk.quantize(v, 8), (0.20, 0.22, 0.21), (0.58, 0.60, 0.55))

    # Ribbed dark metal for the lower band.
    v = rk.fbm(64, rng) * 0.7 + rng.random((64, 64)) * 0.3
    cols = np.arange(64) % 8
    v[:, cols == 0] *= 0.5
    v[:, cols == 1] = np.minimum(1.0, v[:, cols == 1] * 1.4)
    textures["wall_band"] = rk.ramp(rk.quantize(v, 8), (0.12, 0.14, 0.16), (0.38, 0.42, 0.45))

    # Floor tiles with grout and per-tile tint.
    v = rk.fbm(64, rng) * 0.6 + rng.random((64, 64)) * 0.25
    for ty in range(2):
        for tx in range(2):
            v[ty * 32:(ty + 1) * 32, tx * 32:(tx + 1) * 32] += rng.uniform(-0.08, 0.12)
    v[[0, 32], :] = 0.05
    v[:, [0, 32]] = 0.05
    textures["floor"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.22, 0.20, 0.17), (0.55, 0.50, 0.42))

    # Beveled ceiling panels with corner screws.
    v = 0.55 + rk.fbm(64, rng) * 0.25
    for edge in (0, 32):
        v[edge, :] = v[:, edge] = 0.95
        v[edge + 31, :] = v[:, edge + 31] = 0.2
    for sy in (3, 28, 35, 60):
        for sx in (3, 28, 35, 60):
            v[sy, sx] = 0.1
    textures["ceiling"] = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.30, 0.30, 0.30), (0.70, 0.70, 0.68))

    # Fluorescent light panel with a diffuser grid.
    v = np.full((32, 32), 0.95)
    v[::8, :] = v[:, ::8] = 0.6
    v[:2, :] = v[-2:, :] = v[:, :2] = v[:, -2:] = 0.35
    textures["light_panel"] = rk.ramp(v, (0.40, 0.38, 0.30), (1.0, 0.97, 0.85))

    # Worn hazard stripes.
    y, x = np.mgrid[0:32, 0:32]
    stripes = ((x + y) // 8) % 2 == 0
    rgb = np.where(stripes[..., None], (0.85, 0.65, 0.10), (0.08, 0.08, 0.08))
    wear = rk.fbm(32, rng) > 0.62
    rgb[wear] = rgb[wear] * 0.5 + 0.18
    textures["hazard"] = rgb

    # Olive supply crate with a beveled frame and a stencil plate.
    v = rk.fbm(32, rng) * 0.7 + rng.random((32, 32)) * 0.3
    v[:3, :] = np.minimum(1.0, v[:3, :] + 0.35)
    v[:, :3] = np.minimum(1.0, v[:, :3] + 0.35)
    v[-3:, :] *= 0.45
    v[:, -3:] *= 0.45
    rgb = rk.ramp(rk.quantize(np.clip(v, 0, 1), 8), (0.18, 0.22, 0.12), (0.42, 0.47, 0.28))
    plate = np.zeros((32, 32), dtype=bool)
    plate[13:19, 9:23] = True
    plate &= rk.fbm(32, rng) < 0.7
    rgb[plate] = (0.70, 0.68, 0.50)
    textures["crate"] = rgb

    return {name: rk.save_texture("tex_" + name, rgb) for name, rgb in textures.items()}


def build_room(materials):
    bm = bmesh.new()
    width, depth = X1 - X0, Y1 - Y0

    # Floor and ceiling.
    rk.add_grid_quad(bm, (X0, Y0, 0), (width, 0, 0), (0, depth, 0), mat=FLOOR)
    rk.add_grid_quad(bm, (X0, Y1, HEIGHT), (width, 0, 0), (0, -depth, 0), mat=CEILING)

    # Inward-facing walls, split into a dark lower band and upper panels.
    walls = (
        ((X1, Y0), (-width, 0, 0)),  # south, faces +Y
        ((X0, Y1), (width, 0, 0)),  # north, faces -Y
        ((X0, Y0), (0, depth, 0)),  # west, faces +X
        ((X1, Y1), (0, -depth, 0)),  # east, faces -X
    )
    for (x, y), u_vec in walls:
        rk.add_grid_quad(bm, (x, y, 0), u_vec, (0, 0, BAND), mat=WALL_BAND)
        rk.add_grid_quad(bm, (x, y, BAND), u_vec, (0, 0, HEIGHT - BAND), mat=WALL)

    # Pillars.
    for px in (-5.0, 5.0):
        for py in (-6.0, 2.0):
            lo, hi = (px - 0.6, py - 0.6), (px + 0.6, py + 0.6)
            sides = ("+x", "-x", "+y", "-y")
            rk.add_box(bm, (*lo, 0), (*hi, BAND), mat=WALL_BAND, faces=sides)
            rk.add_box(bm, (*lo, BAND), (*hi, HEIGHT), mat=WALL, faces=sides)

    # Raised platform at the north end, hazard-striped front edge.
    plat_y, plat_h = 9.0, 1.5
    rk.add_box(bm, (-5, plat_y, 0), (5, Y1, plat_h), mat=FLOOR, faces=("+z",))
    rk.add_box(bm, (-5, plat_y, 0), (5, Y1, plat_h), mat=HAZARD, faces=("-y",))
    rk.add_box(bm, (-5, plat_y, 0), (5, Y1, plat_h), mat=WALL_BAND, faces=("+x", "-x"))

    # Ramp up to the platform.
    ramp_y = 5.0
    rk.add_grid_quad(bm, (-1.5, ramp_y, 0), (3, 0, 0), (0, plat_y - ramp_y, plat_h), mat=FLOOR)
    for x, order in ((1.5, (0, 1, 2)), (-1.5, (2, 1, 0))):
        corners = [(x, ramp_y, 0), (x, plat_y, 0), (x, plat_y, plat_h)]
        face = bm.faces.new([bm.verts.new(corners[i]) for i in order])
        face.material_index = WALL_BAND

    # Ceiling light fixtures, slightly below the ceiling.
    fixtures = [(x, y) for x in (-5.0, 5.0) for y in (-10.0, -2.0, 6.0)] + [(0.0, 11.5)]
    for cx, cy in fixtures:
        rk.add_grid_quad(bm, (cx - 1, cy + 0.5, HEIGHT - 0.05), (2, 0, 0), (0, -1, 0), cell=2.0, mat=LIGHT_PANEL)

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    rk.box_project_uvs(bm)
    room = rk.mesh_object("TestRoom-col", bm, materials)

    lights = [((cx, cy, HEIGHT - 0.8), (1.05, 0.97, 0.80), 11.0) for cx, cy in fixtures]
    lights.append(((0.0, 12.5, 2.5), (0.70, 0.12, 0.05), 7.0))  # red alarm glow on the platform
    rk.bake_vertex_lighting(room.data, lights, ambient=(0.24, 0.25, 0.29))

    # Light panels are fullbright.
    colors = room.data.color_attributes["Col"]
    for poly in room.data.polygons:
        if poly.material_index == LIGHT_PANEL:
            for li in poly.loop_indices:
                colors.data[li].color = (1.0, 1.0, 1.0, 1.0)
    return room


def build_crates(crate_material):
    placements = [
        ((-7.0, -9.0, 0.0), 1.0),
        ((-7.0, -9.0, 1.0), 1.0),
        ((-5.9, -9.2, 0.0), 1.0),
        ((7.0, 3.5, 0.0), 1.2),
        ((6.4, -2.5, 0.0), 0.9),
        ((-3.5, 12.0, 1.5), 1.0),
    ]
    for index, ((x, y, z), size) in enumerate(placements, start=1):
        bm = bmesh.new()
        half = size / 2
        rk.add_box(bm, (-half, -half, 0), (half, half, size), cell=size)
        rk.face_uvs(bm)
        crate = rk.mesh_object(f"Crate_{index:02d}-convcol", bm, [crate_material])
        crate.location = (x, y, z)


def main():
    rk.reset_scene()
    rng = np.random.default_rng(1997)
    images = build_textures(rng)
    order = ("wall", "wall_band", "floor", "ceiling", "light_panel", "hazard")
    room_materials = [rk.make_material("M_" + name, images[name]) for name in order]
    build_room(room_materials)
    build_crates(rk.make_material("M_crate", images["crate"]))
    rk.export_glb(os.path.join("levels", "test_room", "test_room.glb"), "test_room.blend")


main()
