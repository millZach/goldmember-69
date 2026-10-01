"""Build the three fictional weapons as first-person viewmodels and world models.

Run:  blender -b --factory-startup --python Blender/Scripts/build_weapons.py
Output: Game/assets/weapons/{p9,vk12,talon12}_{view,world}.glb and
        Blender/Source/weapons.blend

Each weapon is modelled in "grip space": origin at the centre of the hand grip,
barrel along +Y, Z up.
- <id>_world.glb: World (empty at grip) > Weapon [> Pump], Muzzle (empty)
- <id>_view.glb:  View (empty = camera, looking +Y) > Weapon, Arm_R [, Pump > Arm_L], Muzzle
  The viewmodel bakes a translation to VIEW_GRIP and a slight inward yaw into
  the vertices (object rotations stay zero).
"""

import math
import os
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
import model_kit as mk  # noqa: E402
import retro_kit as rk  # noqa: E402

VIEW_GRIP = Vector((0.16, 0.32, -0.16))
VIEW_YAW = 3.0  # degrees, barrel angled slightly toward the screen centre

# --------------------------------------------------------------------------
# Atlas layout (64x64, shared by every weapon; each weapon paints its own)
# --------------------------------------------------------------------------
METAL = (0, 0, 16, 16)
SIDE = (16, 0, 48, 16)
DARK = (0, 16, 16, 16)
BARREL = (16, 16, 32, 16)
TOP = (48, 16, 16, 16)
WOOD = (0, 32, 32, 16)
WOOD_PUMP = (32, 32, 32, 16)
GLOVE = (0, 48, 16, 16)
SLEEVE = (16, 48, 16, 16)
KNUCKLE = (32, 48, 16, 16)
ACCENT = (48, 48, 8, 8)
RUBBER = (56, 48, 8, 8)
MUZZLE_FACE = (48, 56, 8, 8)
MAG = (56, 56, 8, 8)

GUNMETAL = (0.29, 0.30, 0.33)
BLACK_METAL = (0.16, 0.16, 0.18)
POLYMER = (0.12, 0.12, 0.12)
LEATHER = (0.11, 0.09, 0.08)
SUIT = (0.13, 0.14, 0.19)
WOOD_C = (0.46, 0.27, 0.13)


def paint_common(at, metal, side_metal=None):
    at.fill(METAL, metal, var=0.12)
    at.fill(SIDE, side_metal or metal, var=0.1)
    at.fill(TOP, metal, var=0.1)
    at.fill(DARK, POLYMER, var=0.15)
    d = at.region(DARK)
    d[::2, ::2] = mk.scaled(POLYMER, 1.5)      # checkering
    d[1::2, 1::2] = mk.scaled(POLYMER, 1.5)
    d[:, 0] = d[:, -1] = mk.scaled(POLYMER, 0.7)
    at.fill(BARREL, BLACK_METAL, var=0.12)
    at.fill(MAG, BLACK_METAL, var=0.1)
    at.region(MAG)[::2, :] = mk.scaled(BLACK_METAL, 1.5)
    at.fill(ACCENT, (0.85, 0.83, 0.70), var=0.05)
    at.fill(RUBBER, (0.07, 0.07, 0.07), var=0.2)
    at.region(RUBBER)[::2, :] = (0.12, 0.12, 0.12)
    at.fill(MUZZLE_FACE, metal, var=0.1)
    mf = at.region(MUZZLE_FACE)
    mf[2:6, 2:6] = (0.03, 0.03, 0.03)
    mf[1, 3:5] = mf[6, 3:5] = mf[3:5, 1] = mf[3:5, 6] = mk.scaled(metal, 0.6)
    # wood grain: noise stretched along the length (u)
    for r in (WOOD, WOOD_PUMP):
        x, y, w, h = r
        at.fill(r, WOOD_C, var=0.12, grain=0.25)
        streak = at.rng.random((h, 1)) * 0.3 + at.rng.random((h, w)) * 0.1
        at.region(r)[:] *= (0.85 + streak)[..., None]
        at.region(r)[at.rng.random((h, w)) > 0.93] = mk.scaled(WOOD_C, 0.6)  # pores
    pump = at.region(WOOD_PUMP)
    pump[:, 2::4] = mk.scaled(WOOD_C, 0.45)   # grip grooves
    pump[:, 0] = pump[:, -1] = mk.scaled(WOOD_C, 0.6)
    # glove + sleeve
    at.fill(GLOVE, LEATHER, var=0.18, grain=0.2)
    g = at.region(GLOVE)
    g[4, :] = g[10, :] = mk.scaled(LEATHER, 0.6)
    g[7, 3:13] = mk.scaled(LEATHER, 1.6)       # sheen
    at.fill(KNUCKLE, LEATHER, var=0.18, grain=0.2)
    k = at.region(KNUCKLE)
    k[:, 3::4] = mk.scaled(LEATHER, 0.55)       # finger seams
    k[5:7, :] = mk.scaled(LEATHER, 1.5)         # knuckle highlight
    at.fill(SLEEVE, SUIT, var=0.12)
    s = at.region(SLEEVE)
    s[:, 7] = mk.scaled(SUIT, 0.7)              # seam
    s[0:2, :] = mk.scaled(SUIT, 0.75)           # cuff edge


# --------------------------------------------------------------------------
# Hands
# --------------------------------------------------------------------------

def right_hand(b, grip_bottom, grip_top, half_w, half_d, elbow, wrist, knuckle_front=0.022):
    """Gloved fist wrapped around a grip axis, forearm + suit sleeve toward `elbow`."""
    gb, gt = Vector(grip_bottom), Vector(grip_top)
    axis = (gt - gb).normalized()
    top = gt - axis * 0.012
    bottom = top - axis * 0.085
    b.tube([bottom, top], [mk.rect(-half_w - 0.011, half_w + 0.011, -half_d - 0.014, half_d + knuckle_front)] * 2,
           {"default": GLOVE, "+y": KNUCKLE}, up=(0, 1, 0))
    # thumb along the left side of the weapon
    t0 = top + Vector((-half_w - 0.012, -0.012, -0.004))
    b.tube([t0, t0 + Vector((0, 0.05, 0.004))], [mk.rect(-0.009, 0.009, -0.008, 0.008)] * 2, GLOVE)
    # glove cuff, then sleeve
    wrist = Vector(wrist)
    d = (Vector(elbow) - wrist).normalized()
    cuff = wrist + d * 0.075
    b.tube([wrist - d * 0.02, cuff], [mk.rect(-0.029, 0.029, -0.026, 0.026), mk.rect(-0.032, 0.032, -0.029, 0.029)],
           GLOVE)
    b.tube([cuff - d * 0.01, Vector(elbow)], [mk.rect(-0.04, 0.04, -0.037, 0.037), mk.rect(-0.047, 0.047, -0.043, 0.043)],
           SLEEVE)


# --------------------------------------------------------------------------
# Kessler P9 - compact pistol, long integral suppressor
# --------------------------------------------------------------------------

def paint_p9():
    at = mk.Atlas(64, seed=909)
    paint_common(at, GUNMETAL)
    s = at.region(SIDE)                         # slide side, rear at left
    s[1:14, 2:12:2] = mk.scaled(GUNMETAL, 0.55)  # rear serrations
    s[3:9, 26:36] = mk.scaled(GUNMETAL, 0.5)     # ejection port
    s[3, 26:36] = mk.scaled(GUNMETAL, 1.4)
    s[11, 16:24] = mk.scaled(GUNMETAL, 1.35)     # engraved marking
    s[11, 17:23:2] = mk.scaled(GUNMETAL, 0.8)
    s[13:16, :] = mk.scaled(GUNMETAL, 0.7)       # slide/frame line
    b = at.region(BARREL)                        # suppressor, rings at the ends
    b[:, [2, 3, 28, 29]] = mk.scaled(BLACK_METAL, 1.6)
    b[:, 15] = mk.scaled(BLACK_METAL, 0.6)
    b[7:9, 6:13] = mk.scaled(BLACK_METAL, 1.4)   # etched maker band
    t = at.region(TOP)
    t[:, 7:9] = mk.scaled(GUNMETAL, 0.6)         # sight channel
    at.region(ACCENT)[2:6, 2:6] = (0.95, 0.95, 0.9)
    return at


def build_p9(at):
    b = mk.Builder(at)
    b.tube([(0, -0.022, -0.05), (0, 0.004, 0.038)], [mk.rect(-0.0155, 0.0155, -0.021, 0.021)] * 2, DARK,
           up=(0, 1, 0))
    b.box((-0.017, -0.047, -0.061), (0.017, 0.0, -0.05), METAL)                      # magazine base
    b.box((-0.0135, -0.03, 0.03), (0.0135, 0.104, 0.057), {"default": DARK, "+z": METAL})  # frame
    b.loft([(-0.049, mk.chamfer_rect(-0.0145, 0.0145, 0.054, 0.088, 0.005, top_only=True)),
            (0.112, mk.chamfer_rect(-0.0145, 0.0145, 0.054, 0.088, 0.005, top_only=True))],
           {"+x": SIDE, "-x": SIDE, "+z": TOP, "default": METAL}, axis="y", long_y=True)   # slide
    b.box((-0.009, -0.046, 0.087), (0.009, -0.035, 0.096), METAL)                    # rear sight
    b.box((-0.003, 0.097, 0.087), (0.003, 0.106, 0.097), ACCENT)                     # front sight
    b.box((-0.004, -0.055, 0.058), (0.004, -0.046, 0.074), METAL)                    # hammer
    b.box((-0.0055, 0.052, 0.004), (0.0055, 0.06, 0.032), METAL)                     # trigger guard
    b.box((-0.0055, 0.010, -0.002), (0.0055, 0.06, 0.005), METAL)
    b.box((-0.003, 0.025, 0.010), (0.003, 0.032, 0.032), METAL)                      # trigger
    z = 0.071
    b.loft([(0.104, mk.ngon(8, 0.012, cb=z)), (0.118, mk.ngon(8, 0.0185, cb=z)),
            (0.29, mk.ngon(8, 0.0185, cb=z)), (0.30, mk.ngon(8, 0.0145, cb=z))],
           {"default": BARREL, "+y": MUZZLE_FACE, "-y": METAL}, axis="y", long_y=True)  # suppressor
    return b, Vector((0, 0.30, z))


def arm_p9(at):
    b = mk.Builder(at)
    right_hand(b, (0, -0.022, -0.05), (0, 0.004, 0.038), 0.0155, 0.021,
               elbow=(0.15, -0.34, -0.27), wrist=(0.004, -0.035, -0.03))
    return b


# --------------------------------------------------------------------------
# VK-12 - compact SMG, stubby receiver, vertical magazine, folded wire stock
# --------------------------------------------------------------------------

def paint_vk12():
    at = mk.Atlas(64, seed=1212)
    paint_common(at, BLACK_METAL, side_metal=(0.23, 0.24, 0.26))
    c = (0.23, 0.24, 0.26)
    s = at.region(SIDE)                          # receiver side, rear at left
    s[:, 0:2] = mk.scaled(c, 0.6)
    s[4:8, 30:40] = mk.scaled(c, 0.45)          # ejection port
    s[3, 30:40] = mk.scaled(c, 1.4)
    s[10:12, 6:28] = mk.scaled(c, 0.7)          # cocking slot
    s[1:3, 8:14] = (0.75, 0.70, 0.45)           # selector markings
    s[1:3, 16] = (0.70, 0.15, 0.10)
    s[13:16, :] = mk.scaled(c, 0.75)
    b = at.region(BARREL)                        # perforated shroud
    b[2:14:3, 2:30:3] = (0.03, 0.03, 0.03)
    b[:, [0, 31]] = mk.scaled(BLACK_METAL, 1.5)
    t = at.region(TOP)
    t[:, 6:10] = mk.scaled(BLACK_METAL, 0.6)
    t[::3, 6:10] = mk.scaled(BLACK_METAL, 1.6)  # rib
    return at


def build_vk12(at):
    b = mk.Builder(at)
    b.tube([(0, -0.030, -0.058), (0, 0.0, 0.035)], [mk.rect(-0.016, 0.016, -0.02, 0.02)] * 2, DARK,
           up=(0, 1, 0))                                                              # pistol grip
    b.loft([(-0.11, mk.chamfer_rect(-0.022, 0.022, 0.035, 0.098, 0.008, top_only=True)),
            (0.13, mk.chamfer_rect(-0.022, 0.022, 0.035, 0.098, 0.008, top_only=True))],
           {"+x": SIDE, "-x": SIDE, "+z": TOP, "default": METAL}, axis="y", long_y=True)  # receiver
    b.box((-0.018, -0.02, 0.018), (0.018, 0.10, 0.038), DARK)                        # trigger housing
    b.box((-0.016, 0.044, -0.002), (0.016, 0.092, 0.02), METAL)                      # magazine well
    b.box((-0.011, 0.052, -0.135), (0.011, 0.084, 0.0), MAG, long_y=True)            # magazine
    b.box((-0.006, 0.010, -0.009), (0.006, 0.046, -0.003), METAL)                    # trigger guard
    b.box((-0.003, 0.021, -0.004), (0.003, 0.028, 0.019), METAL)                     # trigger
    z = 0.07
    b.loft([(0.125, mk.ngon(8, 0.018, cb=z)), (0.205, mk.ngon(8, 0.018, cb=z))],
           {"default": BARREL, "+y": METAL, "-y": METAL}, axis="y", long_y=True)      # barrel shroud
    b.loft([(0.20, mk.ngon(6, 0.0085, cb=z)), (0.25, mk.ngon(6, 0.0085, cb=z))],
           {"default": METAL, "+y": MUZZLE_FACE}, axis="y")                           # barrel
    b.box((-0.003, 0.185, 0.086), (0.003, 0.197, 0.106), METAL)                      # front sight post
    b.box((-0.012, -0.098, 0.097), (0.012, -0.076, 0.112), METAL)                    # rear sight
    b.box((-0.036, 0.062, 0.072), (-0.022, 0.078, 0.086), METAL)                     # charging knob
    # folded wire stock: hinge at the rear, rods along the lower sides, butt bar forward
    b.box((-0.025, -0.126, 0.03), (0.025, -0.104, 0.062), METAL)
    for side in (1, -1):
        x0, x1 = mk.xr(side, 0.023, 0.030)
        b.box((x0, -0.122, 0.032), (x1, 0.123, 0.039), METAL, long_y=True)
    b.box((-0.031, 0.115, 0.004), (0.031, 0.124, 0.04), RUBBER)
    return b, Vector((0, 0.25, z))


def arm_vk12(at):
    b = mk.Builder(at)
    right_hand(b, (0, -0.030, -0.058), (0, 0.0, 0.035), 0.016, 0.02,
               elbow=(0.15, -0.34, -0.27), wrist=(0.004, -0.04, -0.035))
    return b


# --------------------------------------------------------------------------
# Talon 12 - pump shotgun, dark metal, brown wood pump and stock
# --------------------------------------------------------------------------

def paint_talon12():
    at = mk.Atlas(64, seed=1200)
    paint_common(at, BLACK_METAL, side_metal=(0.22, 0.22, 0.24))
    c = (0.22, 0.22, 0.24)
    s = at.region(SIDE)                          # receiver side
    s[3:9, 22:38] = mk.scaled(c, 0.45)          # loading/ejection port
    s[3, 22:38] = mk.scaled(c, 1.5)
    s[11, 6:14] = (0.62, 0.55, 0.35)            # brass-filled engraving
    s[11, 7:13:2] = mk.scaled(c, 0.8)
    s[1, :] = mk.scaled(c, 1.35)
    s[14:16, :] = mk.scaled(c, 0.7)
    b = at.region(BARREL)
    b[:, 0] = b[:, 31] = mk.scaled(BLACK_METAL, 1.5)
    b[7, :] = mk.scaled(BLACK_METAL, 1.25)      # light seam along the tube
    at.region(ACCENT)[2:6, 2:6] = (0.95, 0.90, 0.55)  # brass bead
    return at


PUMP_CENTER = Vector((0, 0.44, 0.025))


def build_talon12(at):
    b = mk.Builder(at)
    b.loft([(0.04, mk.chamfer_rect(-0.022, 0.022, 0.0, 0.072, 0.007, top_only=True)),
            (0.25, mk.chamfer_rect(-0.022, 0.022, 0.0, 0.072, 0.007, top_only=True))],
           {"+x": SIDE, "-x": SIDE, "+z": TOP, "default": METAL}, axis="y", long_y=True)  # receiver
    b.box((-0.012, 0.075, -0.012), (0.012, 0.165, 0.002), METAL)                      # trigger group
    b.box((-0.005, 0.07, -0.052), (0.005, 0.163, -0.044), METAL)                      # trigger guard
    b.box((-0.005, 0.155, -0.052), (0.005, 0.163, -0.01), METAL)
    b.box((-0.003, 0.108, -0.036), (0.003, 0.116, -0.01), METAL)                      # trigger
    z = 0.052
    b.loft([(0.25, mk.ngon(8, 0.0125, cb=z)), (0.78, mk.ngon(8, 0.0125, cb=z))],
           {"default": BARREL, "+y": MUZZLE_FACE, "-y": METAL}, axis="y", long_y=True)  # barrel
    b.loft([(0.25, mk.ngon(6, 0.0115, cb=0.022)), (0.715, mk.ngon(6, 0.0115, cb=0.022))],
           {"default": BARREL, "+y": METAL}, axis="y", long_y=True)                    # magazine tube
    b.box((-0.0135, 0.655, 0.012), (0.0135, 0.672, 0.062), METAL)                     # barrel clamp
    b.box((-0.003, 0.764, 0.063), (0.003, 0.774, 0.071), ACCENT)                      # bead sight
    b.loft([(0.06, mk.rect(-0.019, 0.019, -0.004, 0.066)),                            # wood stock
            (-0.035, mk.rect(-0.017, 0.017, -0.026, 0.03)),
            (-0.11, mk.rect(-0.019, 0.019, -0.05, 0.037)),
            (-0.30, mk.rect(-0.022, 0.022, -0.105, 0.045))],
           WOOD, axis="y", long_y=True)
    b.loft([(-0.298, mk.rect(-0.023, 0.023, -0.108, 0.048)), (-0.316, mk.rect(-0.023, 0.023, -0.108, 0.048))],
           RUBBER, axis="y")                                                           # butt pad
    return b, Vector((0, 0.78, z))


def pump_talon12(at):
    b = mk.Builder(at)
    b.loft([(0.36, mk.chamfer_rect(-0.024, 0.024, 0.002, 0.048, 0.009)),
            (0.37, mk.chamfer_rect(-0.026, 0.026, 0.0, 0.05, 0.01)),
            (0.51, mk.chamfer_rect(-0.026, 0.026, 0.0, 0.05, 0.01)),
            (0.52, mk.chamfer_rect(-0.024, 0.024, 0.002, 0.048, 0.009))],
           {"default": WOOD_PUMP, "+y": WOOD, "-y": WOOD}, axis="y", long_y=True)
    return b


def arm_talon12(at):
    b = mk.Builder(at)
    right_hand(b, (0, -0.02, -0.05), (0, 0.004, 0.045), 0.018, 0.026,
               elbow=(0.15, -0.34, -0.27), wrist=(0.004, -0.05, -0.03), knuckle_front=0.02)
    return b


def left_arm_talon12(at):
    """Left hand cupping the pump from below, forearm running off-screen bottom-left."""
    b = mk.Builder(at)
    b.box((-0.036, 0.40, -0.014), (0.018, 0.486, 0.034), {"default": GLOVE, "-x": KNUCKLE})   # palm/fist
    b.box((0.018, 0.405, 0.004), (0.032, 0.48, 0.036), KNUCKLE)                             # fingertips
    b.box((-0.04, 0.47, 0.03), (-0.024, 0.52, 0.046), GLOVE)                                  # thumb
    wrist = Vector((-0.02, 0.41, -0.005))
    elbow = Vector((-0.27, -0.30, -0.34))
    d = (elbow - wrist).normalized()
    cuff = wrist + d * 0.08
    b.tube([wrist, cuff], [mk.rect(-0.029, 0.029, -0.026, 0.026), mk.rect(-0.032, 0.032, -0.029, 0.029)], GLOVE)
    b.tube([cuff - d * 0.01, elbow], [mk.rect(-0.036, 0.036, -0.034, 0.034), mk.rect(-0.045, 0.045, -0.042, 0.042)],
           SLEEVE)
    return b


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

WEAPONS = {
    "p9": (paint_p9, build_p9, arm_p9, None, None),
    "vk12": (paint_vk12, build_vk12, arm_vk12, None, None),
    "talon12": (paint_talon12, build_talon12, arm_talon12, pump_talon12, left_arm_talon12),
}


def view_matrix():
    return Matrix.Translation(VIEW_GRIP) @ Matrix.Rotation(math.radians(VIEW_YAW), 4, "Z")


def assemble(wid, at, mats, view):
    _, build, arm, pump, left_arm = WEAPONS[wid]
    coll = mk.new_collection(f"{wid}_{'view' if view else 'world'}")
    rig = mk.Rig()
    root = rig.add(mk.empty_object("View" if view else "World", coll, 0.1), (0, 0, 0))
    m = view_matrix() if view else Matrix.Identity(4)
    grip = m @ Vector((0, 0, 0))

    weapon, muzzle = build(at)
    weapon.transform(m)
    rig.add(mk.mesh_object("Weapon", weapon, mats, coll, grip), grip, root)
    if view:
        hand = arm(at)
        hand.transform(m)
        rig.add(mk.mesh_object("Arm_R", hand, mats, coll, grip), grip, root)
    if pump:
        pump_b = pump(at)
        pump_b.transform(m)
        pc = m @ PUMP_CENTER
        pump_obj = rig.add(mk.mesh_object("Pump", pump_b, mats, coll, pc), pc, root)
        if view:
            la = left_arm(at)
            la.transform(m)
            rig.add(mk.mesh_object("Arm_L", la, mats, coll, pc), pc, pump_obj)
    rig.add(mk.empty_object("Muzzle", coll, 0.03, "ARROWS"), m @ muzzle, root)
    print(f"WEAPON {coll.name} TRIANGLES {mk.count_triangles(coll)} "
          f"weapon-only={sum(len(p.vertices) - 2 for o in coll.objects if o.name in ('Weapon', 'Pump') for p in o.data.polygons)} "
          f"muzzle={tuple(round(c, 4) for c in (m @ muzzle))}")
    return coll


def main():
    rk.reset_scene()
    for wid, (paint, *_rest) in WEAPONS.items():
        at = paint()
        at.reduce_palette(16)
        image = at.save(f"tex_wp_{wid}")
        mats = [rk.make_material(f"M_wp_{wid}", image)]
        for view in (False, True):
            coll = assemble(wid, at, mats, view)
            mk.export_collection(coll, os.path.join("weapons", f"{coll.name}.glb"))
            mk.retire_names(coll, coll.name)
    mk.save_blend("weapons.blend")


main()
