"""Build the Valdorian border guard: segmented rigid parts, one 64x64 atlas.

Run:  blender -b --factory-startup --python Blender/Scripts/build_characters.py
Output: Game/assets/characters/guard.glb and Blender/Source/characters.blend

Hierarchy (every origin sits on its joint pivot, rotations zero, facing +Y,
guard's right side is +X):

Guard (empty, feet)
  Pelvis
    Torso
      Head
      UpperArm_R > LowerArm_R > WeaponSocket (empty, palm of right hand)
      UpperArm_L > LowerArm_L
    Thigh_R > Shin_R
    Thigh_L > Shin_L

Knees, elbows and shoulders carry a hexagonal "joint cap" prism along X centred
on the pivot, sized to the limb depth, so limbs can rotate +-60 deg (and more)
about X without opening gaps.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import model_kit as mk  # noqa: E402
import retro_kit as rk  # noqa: E402

# --------------------------------------------------------------------------
# Atlas layout (x, y, w, h), y from the top of the 64x64 image
# --------------------------------------------------------------------------
FACE = (0, 0, 16, 16)
HEAD_SIDE = (16, 0, 16, 16)
HEAD_BACK = (32, 0, 8, 16)
HAIR = (32, 0, 8, 5)
POUCH = (40, 0, 8, 8)
RADIO = (40, 8, 8, 8)
BERET_FRONT = (48, 0, 8, 8)
BERET_SIDE = (56, 0, 8, 8)
BERET_TOP = (48, 8, 16, 8)
TORSO_FRONT = (0, 16, 24, 32)
TORSO_BACK = (24, 16, 24, 32)
TORSO_SIDE = (48, 16, 8, 32)
PELVIS_SIDE = (56, 16, 8, 16)
WEB = (56, 32, 8, 8)
SKIN = (56, 40, 8, 8)
PELVIS_FRONT = (0, 48, 16, 16)
PELVIS_BACK = (16, 48, 16, 16)
SLEEVE = (32, 48, 8, 16)
TROUSER = (40, 48, 8, 16)
BOOT = (48, 48, 8, 16)
HAND = (56, 48, 8, 8)
SOLE = (56, 56, 8, 8)
SOLE_BOTTOM = (56, 61, 8, 3)

# Palette
UNI = (0.38, 0.41, 0.44)        # slate-grey field uniform
UNI_DARK = (0.28, 0.30, 0.33)   # trousers / seams
WEBBING = (0.13, 0.14, 0.12)
BUCKLE = (0.62, 0.56, 0.36)
BOOT_C = (0.09, 0.09, 0.10)
SOLE_C = (0.20, 0.17, 0.14)
BERET_C = (0.13, 0.27, 0.13)
SKIN_C = (0.80, 0.60, 0.46)
SKIN_SH = (0.62, 0.44, 0.33)
HAIR_C = (0.17, 0.12, 0.08)
EYE = (0.06, 0.05, 0.05)
LIP = (0.50, 0.28, 0.24)
RED = (0.70, 0.12, 0.10)


def paint_atlas():
    at = mk.Atlas(64, seed=6901)

    # --- face (col 0 = guard's right, seen from the front) ---
    at.fill(FACE, SKIN_C, var=0.05, grain=0.3)
    f = at.region(FACE)
    f[0:2, :] = HAIR_C
    f[2, [0, 1, 14, 15]] = HAIR_C
    f[3:7, [0, 15]] = SKIN_SH
    f[4, 3:7] = HAIR_C            # brows
    f[4, 9:13] = HAIR_C
    f[5, 4:6] = EYE               # eyes
    f[5, 10:12] = EYE
    f[5, 3] = f[5, 12] = SKIN_SH
    f[6, 4:6] = SKIN_SH
    f[6, 10:12] = SKIN_SH
    f[6:9, 7:9] = mk.scaled(SKIN_C, 0.9)   # nose ridge
    f[8, 6] = f[8, 9] = SKIN_SH
    f[9, 5:11] = HAIR_C           # moustache
    f[9, 4] = f[9, 11] = SKIN_SH
    f[11, 6:10] = LIP
    f[10, 7:9] = SKIN_SH
    f[12:14, [1, 14]] = SKIN_SH   # jaw line
    f[13, 5:11] = mk.scaled(SKIN_C, 0.92)
    f[14:16, :] = SKIN_SH         # under the chin

    # --- head sides (seen from +X: back on the left) ---
    at.fill(HEAD_SIDE, SKIN_C, var=0.05, grain=0.3)
    s = at.region(HEAD_SIDE)
    s[0:3, :] = HAIR_C
    s[3:11, 0:5] = HAIR_C
    s[3:8, 5] = HAIR_C
    s[3:7, 11:13] = HAIR_C        # sideburn
    s[6:11, 7:10] = SKIN_SH       # ear
    s[7:10, 8] = mk.scaled(SKIN_SH, 0.8)
    s[11:13, 0:4] = SKIN_SH       # nape
    s[13:16, 3:14] = SKIN_SH      # jaw shadow

    # --- back of head ---
    at.fill(HEAD_BACK, HAIR_C, var=0.15, grain=0.6)
    b = at.region(HEAD_BACK)
    b[11:16, :] = SKIN_SH
    b[11, 1:7] = HAIR_C

    # --- beret ---
    for r in (BERET_FRONT, BERET_SIDE, BERET_TOP):
        at.fill(r, BERET_C, var=0.12)
    for r in (BERET_FRONT, BERET_SIDE):
        at.region(r)[6:8, :] = (0.08, 0.07, 0.06)   # leather headband
    bf = at.region(BERET_FRONT)
    bf[2:5, 5:7] = BUCKLE                            # cap badge: gold shield, red bar
    bf[3, 5:7] = RED
    at.region(BERET_TOP)[3:5, 7:9] = mk.scaled(BERET_C, 0.7)  # stalk nub

    # --- torso front (col 0 = guard's right) ---
    at.fill(TORSO_FRONT, UNI, var=0.07)
    t = at.region(TORSO_FRONT)
    t[:, 11:13] = mk.scaled(UNI, 0.88)      # button placket
    t[4:30:5, 12] = (0.20, 0.21, 0.22)      # buttons
    t[0:4, 8:16] = UNI_DARK                  # collar
    t[0:3, 10:14] = mk.scaled(UNI_DARK, 0.7)
    t[0, 11:13] = SKIN_SH
    for c0 in (4, 17):                       # webbing straps
        at.fill((c0, 16, 3, 32), WEBBING, var=0.15)
        t[1:32:4, c0 + 1] = mk.scaled(WEBBING, 1.6)  # stitching
    t[13:15, 4:20] = WEBBING                 # chest strap
    t[13:15, 11:13] = BUCKLE
    t[7:9, 19:21] = RED                      # arm-of-service patch (guard's left chest)
    t[7, 21] = BUCKLE
    t[30:32, :] = UNI_DARK                   # shirt tucked into belt
    t[:, 0] = mk.scaled(UNI, 0.85)
    t[:, 23] = mk.scaled(UNI, 0.85)

    # --- torso back (col 0 = guard's left) ---
    at.fill(TORSO_BACK, UNI, var=0.07)
    t = at.region(TORSO_BACK)
    for c0 in (5, 16):
        at.fill((24 + c0, 16, 3, 32), WEBBING, var=0.15)
    t[14:16, 5:19] = WEBBING
    t[4, 1:23] = mk.scaled(UNI, 0.85)        # yoke seam
    t[30:32, :] = UNI_DARK

    # --- torso sides ---
    at.fill(TORSO_SIDE, UNI, var=0.07)
    t = at.region(TORSO_SIDE)
    t[:, 3] = mk.scaled(UNI, 0.82)           # side seam
    t[0:6, :] = mk.scaled(UNI, 0.9)          # armpit shade
    t[30:32, :] = UNI_DARK

    # --- pelvis ---
    for r in (PELVIS_FRONT, PELVIS_BACK, PELVIS_SIDE):
        at.fill(r, UNI_DARK, var=0.08)
        x, y, w, h = r
        at.fill((x, y, w, 5), WEBBING, var=0.15)
        at.region(r)[5, :] = mk.scaled(UNI_DARK, 0.75)
    p = at.region(PELVIS_FRONT)
    p[0:5, 6:10] = BUCKLE
    p[1:4, 7:9] = mk.scaled(BUCKLE, 0.6)
    p[6:13, 7] = mk.scaled(UNI_DARK, 0.7)    # fly
    p[6:9, 1] = p[9, 2] = mk.scaled(UNI_DARK, 0.7)  # pockets
    p[6:9, 14] = p[9, 13] = mk.scaled(UNI_DARK, 0.7)
    p = at.region(PELVIS_BACK)
    p[7:11, 2:6] = mk.scaled(UNI_DARK, 0.85)  # back pockets
    p[7:11, 10:14] = mk.scaled(UNI_DARK, 0.85)
    p[7, 2:6] = p[7, 10:14] = mk.scaled(UNI_DARK, 0.7)

    # --- limbs ---
    at.fill(SLEEVE, UNI, var=0.08)
    sl = at.region(SLEEVE)
    sl[5, :] = mk.scaled(UNI, 0.85)
    sl[11, 1:7] = mk.scaled(UNI, 0.85)
    sl[14:16, :] = UNI_DARK                  # cuff / elbow seam
    at.fill(TROUSER, UNI_DARK, var=0.08)
    tr = at.region(TROUSER)
    tr[:, 3] = mk.scaled(UNI_DARK, 0.85)     # crease
    tr[6:11, 0] = tr[6:11, 7] = mk.scaled(UNI_DARK, 0.75)
    tr[14:16, :] = mk.scaled(UNI_DARK, 0.7)
    at.fill(BOOT, BOOT_C, var=0.25)
    bo = at.region(BOOT)
    bo[0, :] = (0.18, 0.18, 0.19)
    for row in range(2, 14, 2):              # laces
        bo[row, 2:6] = (0.26, 0.25, 0.23)
    bo[14:16, :] = SOLE_C
    at.fill(SOLE, BOOT_C, var=0.25)
    so = at.region(SOLE)
    so[4, :] = (0.22, 0.22, 0.23)            # welt
    so[5:8, :] = SOLE_C

    # --- skin / hands / gear ---
    at.fill(SKIN, SKIN_C, var=0.04, grain=0.3)
    at.fill(HAND, SKIN_C, var=0.05, grain=0.3)
    h = at.region(HAND)
    h[4, :] = SKIN_SH                        # knuckles / finger line
    h[6, 1:7] = SKIN_SH
    at.fill(WEB, WEBBING, var=0.18)
    at.region(WEB)[1::3, 1::3] = mk.scaled(WEBBING, 1.5)
    at.fill(POUCH, WEBBING, var=0.15)
    po = at.region(POUCH)
    po[0:3, :] = mk.scaled(WEBBING, 1.35)    # flap
    po[3, :] = (0.06, 0.06, 0.06)
    po[1:3, 3:5] = BUCKLE
    at.fill(RADIO, (0.16, 0.18, 0.15), var=0.1)
    ra = at.region(RADIO)
    ra[1:4, 1:7] = (0.08, 0.09, 0.08)        # speaker grille
    ra[2, 1:7:2] = (0.22, 0.24, 0.2)
    ra[5, 2] = (0.9, 0.2, 0.1)               # LED
    ra[5:7, 4:7] = (0.3, 0.3, 0.28)

    return at


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def joint_cap(bld, side, center_x, z, x_half, radius, regions):
    x0, x1 = mk.xr(side, center_x - x_half, center_x + x_half)
    bld.prism((x0, 0, z), (x1, 0, z), radius, 6, regions, up=(0, 0, 1))


def build_pelvis(at):
    b = mk.Builder(at)
    b.loft([
        (0.80, mk.rect(-0.10, 0.10, -0.08, 0.09)),
        (0.88, mk.rect(-0.165, 0.165, -0.105, 0.115)),
        (1.03, mk.rect(-0.16, 0.16, -0.10, 0.11)),
    ], {"+y": PELVIS_FRONT, "-y": PELVIS_BACK, "+x": PELVIS_SIDE, "-x": PELVIS_SIDE,
        "+z": WEB, "-z": TROUSER})
    # waist joint cap (octagon along X on the Torso pivot) so the torso can lean
    b.prism((-0.148, 0, 1.00), (0.148, 0, 1.00), 0.112, 8, TORSO_SIDE)
    for side in (1, -1):  # pouches on the back of the belt
        x0, x1 = mk.xr(side, 0.035, 0.125)
        b.box((x0, -0.145, 0.885), (x1, -0.095, 1.005), {"default": WEB, "-y": POUCH})
    return b


def build_torso(at):
    b = mk.Builder(at)
    b.loft([
        (0.98, mk.rect(-0.15, 0.15, -0.095, 0.10)),
        (1.12, mk.rect(-0.155, 0.155, -0.10, 0.11)),
        (1.30, mk.rect(-0.185, 0.185, -0.11, 0.13)),
        (1.44, mk.rect(-0.19, 0.19, -0.10, 0.11)),
        (1.49, mk.rect(-0.12, 0.12, -0.07, 0.07)),
    ], {"+y": TORSO_FRONT, "-y": TORSO_BACK, "+x": TORSO_SIDE, "-x": TORSO_SIDE,
        "+z": SLEEVE, "-z": WEB})
    for side in (1, -1):  # magazine pouches on the chest rig
        x0, x1 = mk.xr(side, 0.03, 0.12)
        b.box((x0, 0.10, 1.09), (x1, 0.155, 1.21), {"default": WEB, "+y": POUCH})
    # radio on the left shoulder strap, with a stub antenna
    b.box((-0.135, 0.095, 1.32), (-0.07, 0.145, 1.41), {"default": WEB, "+y": RADIO})
    b.box((-0.125, 0.11, 1.41), (-0.113, 0.122, 1.52), WEB)
    return b


def build_head(at):
    b = mk.Builder(at)
    b.box((-0.05, -0.055, 1.44), (0.05, 0.045, 1.57), SKIN)  # neck
    b.loft([
        (1.545, mk.rect(-0.07, 0.07, -0.07, 0.085)),
        (1.60, mk.rect(-0.095, 0.095, -0.10, 0.11)),
        (1.77, mk.rect(-0.095, 0.095, -0.115, 0.10)),
    ], {"+y": FACE, "-y": HEAD_BACK, "+x": HEAD_SIDE, "-x": HEAD_SIDE, "+z": HAIR, "-z": SKIN})
    b.loft([  # nose wedge
        (1.648, mk.rect(-0.015, 0.015, 0.095, 0.126)),
        (1.695, mk.rect(-0.009, 0.009, 0.095, 0.105)),
    ], SKIN)
    for side in (1, -1):  # ears
        x0, x1 = mk.xr(side, 0.09, 0.112)
        b.box((x0, -0.025, 1.625), (x1, 0.015, 1.69), SKIN)
    # beret, slouched toward the guard's right, badge over the left eye
    b.loft([
        (1.735, mk.rect(-0.104, 0.104, -0.123, 0.108)),
        (1.775, mk.rect(-0.112, 0.128, -0.132, 0.118)),
        (1.808, mk.rect(-0.07, 0.135, -0.105, 0.09)),
    ], {"+y": BERET_FRONT, "default": BERET_SIDE, "+z": BERET_TOP})
    return b


def build_upper_arm(at, side):
    b = mk.Builder(at)
    b.loft([
        (1.47, mk.rect(*mk.xr(side, 0.168, 0.272), -0.06, 0.06)),
        (1.30, mk.rect(*mk.xr(side, 0.165, 0.275), -0.06, 0.06)),
        (1.12, mk.rect(*mk.xr(side, 0.175, 0.265), -0.05, 0.05)),
    ], SLEEVE)
    joint_cap(b, side, 0.22, 1.42, 0.062, 0.07, SLEEVE)   # shoulder
    return b


def build_lower_arm(at, side):
    b = mk.Builder(at)
    joint_cap(b, side, 0.22, 1.14, 0.044, 0.058, SLEEVE)  # elbow
    b.loft([
        (1.17, mk.rect(*mk.xr(side, 0.176, 0.264), -0.05, 0.05)),
        (1.06, mk.rect(*mk.xr(side, 0.173, 0.267), -0.052, 0.052)),
        (0.88, mk.rect(*mk.xr(side, 0.186, 0.254), -0.04, 0.04)),
    ], SLEEVE)
    b.loft([  # hand, palm facing the body
        (0.895, mk.rect(*mk.xr(side, 0.192, 0.248), -0.045, 0.045)),
        (0.82, mk.rect(*mk.xr(side, 0.19, 0.252), -0.05, 0.05)),
        (0.745, mk.rect(*mk.xr(side, 0.197, 0.245), -0.04, 0.035)),
    ], HAND)
    tx = mk.xr(side, 0.188, 0.214)
    b.box((tx[0], 0.035, 0.81), (tx[1], 0.066, 0.875), HAND)  # thumb
    return b


def build_thigh(at, side):
    b = mk.Builder(at)
    b.loft([
        (0.985, mk.rect(*mk.xr(side, 0.02, 0.18), -0.095, 0.10)),
        (0.75, mk.rect(*mk.xr(side, 0.03, 0.175), -0.085, 0.09)),
        (0.47, mk.rect(*mk.xr(side, 0.045, 0.155), -0.065, 0.07)),
    ], TROUSER)
    return b


def build_shin(at, side):
    b = mk.Builder(at)
    joint_cap(b, side, 0.10, 0.50, 0.057, 0.081, TROUSER)  # knee
    b.loft([
        (0.53, mk.rect(*mk.xr(side, 0.045, 0.155), -0.065, 0.07)),
        (0.35, mk.rect(*mk.xr(side, 0.048, 0.152), -0.062, 0.065)),
        (0.24, mk.rect(*mk.xr(side, 0.052, 0.148), -0.055, 0.058)),
    ], TROUSER)
    b.loft([  # boot shaft
        (0.27, mk.rect(*mk.xr(side, 0.045, 0.155), -0.068, 0.068)),
        (0.08, mk.rect(*mk.xr(side, 0.043, 0.157), -0.075, 0.075)),
    ], BOOT)
    b.loft([  # foot, lofted forward along +Y
        (-0.085, mk.rect(*mk.xr(side, 0.042, 0.158), 0.0, 0.10)),
        (0.07, mk.rect(*mk.xr(side, 0.040, 0.160), 0.0, 0.10)),
        (0.175, mk.rect(*mk.xr(side, 0.050, 0.150), 0.0, 0.055)),
    ], {"default": SOLE, "+z": BOOT, "-z": SOLE_BOTTOM}, axis="y")
    return b


def main():
    rk.reset_scene()
    at = paint_atlas()
    at.reduce_palette(20)
    image = at.save("tex_ch_guard")
    mat = rk.make_material("M_ch_guard", image)
    mats = [mat]
    coll = mk.new_collection("guard")
    rig = mk.Rig()

    root = rig.add(mk.empty_object("Guard", coll, 0.3), (0, 0, 0))
    pelvis = rig.add(mk.mesh_object("Pelvis", build_pelvis(at), mats, coll, (0, 0, 0.95)), (0, 0, 0.95), root)
    torso = rig.add(mk.mesh_object("Torso", build_torso(at), mats, coll, (0, 0, 1.00)), (0, 0, 1.00), pelvis)
    rig.add(mk.mesh_object("Head", build_head(at), mats, coll, (0, 0, 1.52)), (0, 0, 1.52), torso)
    for side, tag in ((1, "R"), (-1, "L")):
        shoulder = (0.22 * side, 0, 1.42)
        elbow = (0.22 * side, 0, 1.14)
        upper = rig.add(mk.mesh_object(f"UpperArm_{tag}", build_upper_arm(at, side), mats, coll, shoulder),
                        shoulder, torso)
        lower = rig.add(mk.mesh_object(f"LowerArm_{tag}", build_lower_arm(at, side), mats, coll, elbow),
                        elbow, upper)
        if side == 1:
            rig.add(mk.empty_object("WeaponSocket", coll, 0.08, "ARROWS"), (0.22, 0.0, 0.82), lower)
        hip = (0.10 * side, 0, 0.92)
        knee = (0.10 * side, 0, 0.50)
        thigh = rig.add(mk.mesh_object(f"Thigh_{tag}", build_thigh(at, side), mats, coll, hip), hip, pelvis)
        rig.add(mk.mesh_object(f"Shin_{tag}", build_shin(at, side), mats, coll, knee), knee, thigh)

    print("GUARD TRIANGLES", mk.count_triangles(coll), "PALETTE", at.palette_size())
    mk.export_collection(coll, os.path.join("characters", "guard.glb"))
    mk.save_blend("characters.blend")


main()
