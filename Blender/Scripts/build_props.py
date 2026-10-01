"""Build interactive/pickup props.

Run:  blender -b --factory-startup --python Blender/Scripts/build_props.py
Output: Game/assets/props/*.glb and Blender/Source/props.blend

Roots (empties) and notable children:
- alarm_panel.glb      AlarmPanel > Body, Lamp (red dome, origin at its base)
- breaker_panel.glb    BreakerPanel > Body, Levers (origin on the hinge axis; rotate about X)
- data_tap.glb         DataTap > Body
- explosive_charge.glb Charge > Body
- ammo_box.glb         AmmoBox > Body
- armor_vest.glb       ArmorVest > Body
Wall-mounted panels have their origin at the back-centre and face +Y.
"""

import os
import sys

import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import model_kit as mk  # noqa: E402
import retro_kit as rk  # noqa: E402

STEEL = (0.52, 0.53, 0.52)
GREY = (0.46, 0.48, 0.47)
DARK = (0.10, 0.10, 0.11)
YELLOW = (0.88, 0.70, 0.12)
RED = (0.78, 0.10, 0.08)
OFFWHITE = (0.85, 0.83, 0.76)
OLIVE = (0.30, 0.34, 0.18)


def hazard(at, rect, width=3):
    x, y, w, h = rect
    yy, xx = np.mgrid[0:h, 0:w]
    stripes = ((xx + yy) // width) % 2 == 0
    at.region(rect)[:] = np.where(stripes[..., None], YELLOW, (0.08, 0.08, 0.08))


def screws(region, color, inset=1):
    h, w, _ = region.shape
    for yy in (inset, h - 1 - inset):
        for xx in (inset, w - 1 - inset):
            region[yy, xx] = color


def finish(name, file, at, parts, extra=None):
    """parts: list of (object name, builder, pivot, parent name or None)."""
    at.reduce_palette(16)
    image = at.save(f"tex_pr_{file}")
    mats = [rk.make_material(f"M_pr_{file}", image)]
    coll = mk.new_collection(file)
    rig = mk.Rig()
    objs = {name: rig.add(mk.empty_object(name, coll, 0.1), (0, 0, 0))}
    for obj_name, builder, pivot, parent in parts:
        obj = mk.mesh_object(obj_name, builder, mats, coll, pivot)
        objs[obj_name] = rig.add(obj, pivot, objs[parent or name])
    print(f"PROP {file} TRIANGLES {mk.count_triangles(coll)} PALETTE {at.palette_size()}")
    mk.export_collection(coll, os.path.join("props", f"{file}.glb"))
    mk.retire_names(coll, file)


# --------------------------------------------------------------------------
# Alarm panel
# --------------------------------------------------------------------------

def alarm_panel():
    FRONT, SIDE, TOP = (0, 0, 32, 40), (32, 0, 16, 40), (48, 0, 16, 16)
    BUTTON, COLLAR = (48, 16, 16, 16), (32, 40, 16, 8)
    LAMP, LAMP_BASE = (0, 40, 16, 16), (16, 40, 16, 8)
    at = mk.Atlas(64, seed=31)
    at.fill(FRONT, STEEL, var=0.07)
    hazard(at, FRONT, 3)
    at.fill((3, 3, 26, 34), STEEL, var=0.07)                 # inner plate
    f = at.region(FRONT)
    f[3, 3:29] = mk.scaled(STEEL, 1.25)
    f[36, 3:29] = mk.scaled(STEEL, 0.7)
    f[5:11, 6:26] = OFFWHITE                                 # label plate
    f[7:9, 8:24] = RED                                       # "ALARM" bar
    f[7:9, 11] = f[7:9, 16] = f[7:9, 21] = OFFWHITE
    for row in range(29, 35, 2):                             # speaker grille
        f[row, 8:24:2] = DARK
    screws(f[3:37, 3:29], mk.scaled(STEEL, 0.5), 1)
    at.fill(SIDE, STEEL, var=0.07)
    at.region(SIDE)[:, 0] = at.region(SIDE)[:, -1] = mk.scaled(STEEL, 0.75)
    at.fill(TOP, STEEL, var=0.07)
    at.fill(BUTTON, RED, var=0.1)
    bt = at.region(BUTTON)
    bt[3:7, 4:8] = (0.98, 0.45, 0.40)                        # highlight
    bt[12:16, :] = mk.scaled(RED, 0.65)
    at.fill(COLLAR, YELLOW, var=0.08)
    at.fill(LAMP, RED, var=0.08)
    la = at.region(LAMP)
    la[2:9, 3:6] = (1.0, 0.55, 0.45)
    la[3:6, 4] = (1.0, 0.85, 0.80)
    la[13:16, :] = mk.scaled(RED, 0.6)
    at.fill(LAMP_BASE, (0.18, 0.18, 0.19), var=0.1)

    body = mk.Builder(at)
    body.box((-0.2, 0.0, -0.25), (0.2, 0.12, 0.25), {"+y": FRONT, "+z": TOP, "default": SIDE})
    bz = -0.045
    body.prism((0, 0.118, bz), (0, 0.136, bz), 0.082, 8, COLLAR)          # yellow guard collar
    body.loft([(0.134, mk.ngon(8, 0.06, cb=bz)), (0.165, mk.ngon(8, 0.06, cb=bz)),
               (0.182, mk.ngon(8, 0.046, cb=bz))], BUTTON, axis="y")       # big mushroom button
    lamp = mk.Builder(at)
    lamp.loft([(0.248, mk.ngon(8, 0.056, ca=0, cb=0.06)), (0.272, mk.ngon(8, 0.056, cb=0.06))],
              LAMP_BASE)
    lamp.loft([(0.27, mk.ngon(8, 0.047, cb=0.06)), (0.305, mk.ngon(8, 0.046, cb=0.06)),
               (0.335, mk.ngon(8, 0.03, cb=0.06)), (0.345, mk.ngon(8, 0.012, cb=0.06))],
              {"default": LAMP, "+z": (4, 42, 6, 6)})
    finish("AlarmPanel", "alarm_panel", at, [
        ("Body", body, (0, 0, 0), None),
        ("Lamp", lamp, (0, 0.06, 0.25), None),
    ])


# --------------------------------------------------------------------------
# Breaker panel
# --------------------------------------------------------------------------

def breaker_panel():
    FRONT, SIDE, TOP = (0, 0, 32, 48), (32, 0, 8, 48), (40, 0, 24, 8)
    BLACK, GRIP, ROD = (40, 8, 8, 8), (48, 8, 8, 8), (56, 8, 8, 8)
    at = mk.Atlas(64, seed=32)
    at.fill(FRONT, GREY, var=0.06)
    f = at.region(FRONT)
    f[0, :] = f[:, 0] = mk.scaled(GREY, 1.25)                # door bevel
    f[47, :] = f[:, 31] = mk.scaled(GREY, 0.65)
    f[2, 2:30] = f[45, 2:30] = mk.scaled(GREY, 0.8)          # door seam
    f[2:46, 2] = f[2:46, 29] = mk.scaled(GREY, 0.8)
    for row in range(5, 12, 2):                              # vent slots
        f[row, 7:25] = DARK
    tri = [(14, 15, 16), (15, 14, 17), (16, 13, 18), (17, 13, 18), (18, 12, 19)]  # warning triangle
    for row, c0, c1 in tri:
        f[row, c0:c1 + 1] = YELLOW
    f[19, 12:20] = YELLOW
    f[15:18, 15:17] = DARK
    f[41:43, 9:23] = OFFWHITE                                # circuit label strip
    f[41:43, 10:22:3] = DARK
    f[22:26, 26:28] = DARK                                   # key lock
    screws(f, mk.scaled(GREY, 0.5), 3)
    at.fill(SIDE, GREY, var=0.06)
    at.region(SIDE)[:, 0] = mk.scaled(GREY, 0.7)
    at.fill(TOP, GREY, var=0.06)
    at.fill(BLACK, DARK, var=0.2)
    at.fill(GRIP, RED, var=0.12)
    at.region(GRIP)[:, ::3] = mk.scaled(RED, 0.6)
    at.fill(ROD, (0.62, 0.62, 0.60), var=0.1)

    body = mk.Builder(at)
    body.box((-0.3, 0.0, -0.45), (0.3, 0.15, 0.45), {"+y": FRONT, "+z": TOP, "-z": TOP, "default": SIDE})
    body.box((-0.12, 0.148, -0.30), (0.12, 0.165, -0.13), BLACK)              # lever base plate
    body.box((-0.11, 0.16, -0.19), (-0.086, 0.2, -0.13), BLACK)               # hinge brackets
    body.box((0.086, 0.16, -0.19), (0.11, 0.2, -0.13), BLACK)
    body.box((0.2, 0.148, -0.05), (0.225, 0.175, 0.07), BLACK)                # door handle
    hinge = Vector((0, 0.18, -0.16))
    levers = mk.Builder(at)
    levers.prism(hinge + Vector((-0.086, 0, 0)), hinge + Vector((0.086, 0, 0)), 0.016, 6, ROD)  # hinge pin
    for x in (-0.07, 0.07):                                                    # lever arms, "ON" = up
        p0 = hinge + Vector((x, 0, 0))
        levers.tube([p0, p0 + Vector((0, 0.05, 0.17))], [mk.rect(-0.01, 0.01, -0.009, 0.009)] * 2, ROD)
    top = hinge + Vector((0, 0.05, 0.17))
    levers.prism(top + Vector((-0.1, 0, 0)), top + Vector((0.1, 0, 0)), 0.017, 6, GRIP)  # handle bar
    finish("BreakerPanel", "breaker_panel", at, [
        ("Body", body, (0, 0, 0), None),
        ("Levers", levers, tuple(hinge), None),
    ])


# --------------------------------------------------------------------------
# Data tap
# --------------------------------------------------------------------------

def data_tap():
    FRONT, BODY, TOP = (0, 0, 16, 8), (16, 0, 16, 8), (0, 8, 16, 8)
    LED, BLACK = (16, 8, 4, 4), (20, 8, 4, 4)
    at = mk.Atlas(32, seed=33)
    CASE = (0.33, 0.33, 0.28)
    at.fill(FRONT, CASE, var=0.08)
    f = at.region(FRONT)
    f[1:5, 1:9] = (0.08, 0.16, 0.08)                         # LCD
    f[2, 2:7] = (0.35, 0.85, 0.35)
    f[3, 2:5] = (0.25, 0.65, 0.25)
    f[1:7:2, 10:15:2] = DARK                                 # keypad
    f[7, :] = mk.scaled(CASE, 0.65)
    at.fill(BODY, CASE, var=0.08)
    at.region(BODY)[7, :] = mk.scaled(CASE, 0.65)
    at.region(BODY)[2:5, 4:12:2] = mk.scaled(CASE, 0.6)     # vent ribs
    at.fill(TOP, CASE, var=0.08)
    t = at.region(TOP)
    t[0, :] = t[:, 0] = mk.scaled(CASE, 1.25)
    t[2:6, 4:11] = OFFWHITE                                  # sticker
    t[3, 5:10] = (0.2, 0.3, 0.6)
    at.region(LED)[:] = (0.25, 1.0, 0.35)
    at.region(LED)[1:3, 1:3] = (0.8, 1.0, 0.8)
    at.fill(BLACK, DARK, var=0.2)

    b = mk.Builder(at)
    b.loft([(0.0, mk.rect(-0.075, 0.075, -0.05, 0.05)), (0.045, mk.rect(-0.075, 0.075, -0.05, 0.05)),
            (0.058, mk.rect(-0.068, 0.068, -0.043, 0.043))], {"+y": FRONT, "+z": TOP, "default": BODY})
    b.box((0.035, 0.012, 0.055), (0.052, 0.029, 0.066), LED)                            # green LED
    b.prism((-0.048, -0.025, 0.05), (-0.048, -0.025, 0.125), 0.007, 6, BLACK)           # stubby antenna
    b.box((-0.056, -0.033, 0.122), (-0.040, -0.017, 0.138), BLACK)                      # antenna tip
    b.box((-0.02, -0.065, 0.012), (0.02, -0.048, 0.035), BLACK)                         # cable plug
    finish("DataTap", "data_tap", at, [("Body", b, (0, 0, 0), None)])


# --------------------------------------------------------------------------
# Explosive charge
# --------------------------------------------------------------------------

def explosive_charge():
    SIDE, TOP, STRAP = (0, 0, 16, 8), (0, 8, 16, 16), (16, 0, 8, 8)
    TIMER, TIMER_SIDE = (16, 8, 16, 8), (16, 16, 8, 8)
    WIRE_R, WIRE_B = (24, 16, 4, 4), (28, 16, 4, 4)
    at = mk.Atlas(32, seed=34)
    WRAP = (0.62, 0.58, 0.40)
    at.fill(SIDE, WRAP, var=0.07)
    at.region(SIDE)[3:5, 2:14:3] = mk.scaled(WRAP, 0.55)    # printed marks
    at.fill(TOP, WRAP, var=0.07)
    t = at.region(TOP)
    t[2:14, 2] = t[2:14, 13] = mk.scaled(WRAP, 0.6)
    t[10:13, 4:12] = mk.scaled(WRAP, 0.6)                    # printed block text
    t[11, 5:11:2] = WRAP
    at.fill(STRAP, DARK, var=0.25)
    at.region(STRAP)[:, [0, -1]] = (0.2, 0.2, 0.2)
    at.fill(TIMER, DARK, var=0.1)
    tm = at.region(TIMER)
    tm[2:6, 2:14] = (0.05, 0.02, 0.02)                       # LED readout
    tm[3, 3:6] = tm[3, 7:10] = tm[4, 11:13] = (1.0, 0.15, 0.08)
    tm[4, 3] = tm[4, 5] = tm[4, 9] = (1.0, 0.15, 0.08)
    tm[6, 2:5] = (0.7, 0.7, 0.65)                            # buttons
    at.fill(TIMER_SIDE, DARK, var=0.1)
    at.region(WIRE_R)[:] = (0.8, 0.12, 0.1)
    at.region(WIRE_B)[:] = (0.15, 0.3, 0.8)

    b = mk.Builder(at)
    b.box((-0.1, -0.05, 0.0), (0.1, 0.05, 0.055), {"+z": TOP, "default": SIDE})
    for x in (-0.06, 0.06):
        b.box((x - 0.011, -0.054, 0.0), (x + 0.011, 0.054, 0.059), STRAP)
    b.box((-0.042, -0.034, 0.057), (0.042, 0.034, 0.082), {"+z": TIMER, "default": TIMER_SIDE})
    b.box((0.04, -0.018, 0.058), (0.09, -0.01, 0.066), WIRE_R)                        # wires into the block
    b.box((0.04, 0.01, 0.058), (0.078, 0.018, 0.066), WIRE_B)
    b.box((0.082, -0.018, 0.04), (0.09, -0.01, 0.066), WIRE_R)
    b.box((0.07, 0.01, 0.04), (0.078, 0.018, 0.066), WIRE_B)
    finish("Charge", "explosive_charge", at, [("Body", b, (0, 0, 0), None)])


# --------------------------------------------------------------------------
# Ammo box
# --------------------------------------------------------------------------

def ammo_box():
    SIDE, END, TOP, METAL = (0, 0, 16, 16), (16, 0, 8, 16), (0, 16, 16, 8), (16, 16, 8, 8)
    LID = (24, 0, 8, 8)
    at = mk.Atlas(32, seed=35)
    at.fill(SIDE, OLIVE, var=0.1)
    s = at.region(SIDE)
    s[5:7, 3:13] = YELLOW                                    # stencil lines
    s[5:7, [5, 8, 11]] = OLIVE
    s[9, 4:12] = YELLOW
    s[9, 6] = s[9, 9] = OLIVE
    s[15, :] = mk.scaled(OLIVE, 0.6)
    at.fill(END, OLIVE, var=0.1)
    at.region(END)[15, :] = mk.scaled(OLIVE, 0.6)
    at.region(END)[3:7, 2:6] = mk.scaled(OLIVE, 0.7)
    at.fill(TOP, OLIVE, var=0.1)
    at.region(TOP)[[0, -1], :] = mk.scaled(OLIVE, 1.25)
    at.fill(LID, mk.scaled(OLIVE, 0.9), var=0.1)
    at.region(LID)[-1, :] = mk.scaled(OLIVE, 0.55)
    at.fill(METAL, (0.22, 0.23, 0.2), var=0.15)

    b = mk.Builder(at)
    b.box((-0.15, -0.072, 0.0), (0.15, 0.072, 0.15), {"+x": END, "-x": END, "default": SIDE})
    b.box((-0.153, -0.076, 0.148), (0.153, 0.076, 0.18), {"+z": TOP, "default": LID})
    for x in (-0.07, 0.07):
        b.box((x - 0.008, -0.008, 0.18), (x + 0.008, 0.008, 0.19), METAL)               # handle posts
    b.box((-0.08, -0.01, 0.19), (0.08, 0.01, 0.2), METAL)                                 # handle
    b.box((0.15, -0.025, 0.1), (0.162, 0.025, 0.172), METAL)                              # latch
    finish("AmmoBox", "ammo_box", at, [("Body", b, (0, 0, 0), None)])


# --------------------------------------------------------------------------
# Armor vest (lying flat, neck toward +Y)
# --------------------------------------------------------------------------

VEST_OUTLINE = [(-0.22, -0.30), (0.22, -0.30), (0.24, -0.10), (0.205, 0.04), (0.19, 0.17), (0.165, 0.30),
                (0.075, 0.30), (0.055, 0.21), (0.0, 0.175), (-0.055, 0.21), (-0.075, 0.30), (-0.165, 0.30),
                (-0.19, 0.17), (-0.205, 0.04), (-0.24, -0.10)]


def armor_vest():
    TOP, EDGE, POUCH, BOTTOM = (0, 0, 48, 56), (48, 0, 16, 8), (48, 8, 16, 16), (48, 24, 16, 16)
    at = mk.Atlas(64, seed=36)
    NAVY = (0.27, 0.31, 0.37)
    at.fill(TOP, NAVY, var=0.08)
    t = at.region(TOP)
    # top of the image = +Y (neck); 48 px across 0.48 m, 56 px along 0.60 m
    t[0:18, 8:16] = DARK                                     # shoulder straps
    t[0:18, 32:40] = DARK
    t[1:18:3, 11:13] = (0.25, 0.25, 0.25)
    t[1:18:3, 35:37] = (0.25, 0.25, 0.25)
    t[18:21, 4:44] = DARK                                    # chest strap
    t[18:21, 22:26] = (0.55, 0.55, 0.5)                      # buckle
    t[24:31, 15:33] = (0.68, 0.68, 0.64)                     # ID panel
    t[26:29, 17:31] = (0.30, 0.30, 0.34)
    t[26:29, 20:22] = t[26:29, 26:28] = (0.68, 0.68, 0.64)
    t[32:, 23:25] = mk.scaled(NAVY, 0.7)                     # front closure
    for c in (3, 44):
        t[20:56, c] = mk.scaled(NAVY, 0.75)                  # side seams
    at.fill(EDGE, DARK, var=0.2)
    at.fill(POUCH, (0.14, 0.15, 0.18), var=0.12)
    p = at.region(POUCH)
    p[0:6, :] = (0.19, 0.20, 0.24)
    p[6, :] = DARK
    p[2:5, 6:10] = DARK
    at.fill(BOTTOM, mk.scaled(NAVY, 0.7), var=0.1)

    b = mk.Builder(at)
    scaled = [(x * 0.95, y * 0.95) for x, y in VEST_OUTLINE]
    b.loft([(0.0, VEST_OUTLINE), (0.035, VEST_OUTLINE), (0.05, scaled)],
           {"+z": TOP, "-z": BOTTOM, "default": EDGE})
    for x0, x1 in ((-0.19, -0.075), (-0.058, 0.058), (0.075, 0.19)):
        b.box((x0, -0.275, 0.04), (x1, -0.14, 0.075), {"+z": POUCH, "default": (48, 14, 16, 10)})
    finish("ArmorVest", "armor_vest", at, [("Body", b, (0, 0, 0), None)])


def main():
    rk.reset_scene()
    alarm_panel()
    breaker_panel()
    data_tap()
    explosive_charge()
    ammo_box()
    armor_vest()
    mk.save_blend("props.blend")


main()
