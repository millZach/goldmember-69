"""Modeling helpers for Goldmember 69 characters, weapons, props and sprites.

Builds on retro_kit. Everything here is low-poly, flat shaded and textured from
small procedurally painted atlases; no vertex colours are ever created (Godot's
import plugin then gives the surfaces the per-vertex-lit retro shader).

Conventions
- Blender units are metres, Z up, +Y is "forward" (Godot -Z).
- Atlas rects are (x, y, w, h) in pixels, y measured from the TOP of the image,
  matching the numpy arrays the textures are painted in.
- Each primitive is box-projected into its atlas rects: every face picks the rect
  for its dominant normal axis ("+x", "-x", "+y", "-y", "+z", "-z") and maps the
  primitive's bounding box onto it.  Rects are painted "as seen from outside":
    +y (front)  : image left = +X side (seen from the front)
    -y (back)   : image left = -X side (seen from behind)
    +x / -x     : image left = -Y (back), right = +Y (front); -x is a mirror of +x
    +z (top)    : image top = +Y
  and image up = +Z for all side faces.
"""

import math
import os
import struct
import sys
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import retro_kit as rk  # noqa: E402

GAME_ASSET_DIR = rk.GAME_ASSET_DIR
SOURCE_DIR = rk.SOURCE_DIR

SIDES = ("+x", "-x", "+y", "-y", "+z", "-z")


# --------------------------------------------------------------------------
# Texture atlases
# --------------------------------------------------------------------------

class Atlas:
    """A small square texture painted region by region with numpy."""

    def __init__(self, size, seed):
        self.size = size
        self.rng = np.random.default_rng(seed)
        self.rgb = np.zeros((size, size, 3))
        smooth = rk.fbm(size, self.rng, octaves=((8, 0.5), (16, 0.3), (32, 0.2)))
        self.smooth = (smooth - smooth.min()) / (smooth.max() - smooth.min())
        self.grain = self.rng.random((size, size))

    def region(self, rect):
        x, y, w, h = rect
        return self.rgb[y:y + h, x:x + w]

    def shade(self, rect, levels=3, grain=0.5):
        """Quantized noise in [-1, 1] for a rect."""
        x, y, w, h = rect
        v = self.smooth[y:y + h, x:x + w] * (1 - grain) + self.grain[y:y + h, x:x + w] * grain
        v = (v - 0.5) * 1.6 + 0.5
        return rk.quantize(np.clip(v, 0, 1), levels) * 2 - 1

    def fill(self, rect, color, var=0.1, levels=3, grain=0.5):
        s = self.shade(rect, levels, grain)
        self.region(rect)[:] = np.array(color, dtype=float) * (1 + var * s)[..., None]

    def px(self, rect, x, y, color):
        """Set pixel(s) relative to a rect. x/y may be ints or slices."""
        self.region(rect)[y, x] = color

    def uv(self, rect, u, v, inset=0.06):
        x, y, w, h = rect
        u = min(max(u, 0.0), 1.0)
        v = min(max(v, 0.0), 1.0)
        px = x + inset + u * (w - 2 * inset)
        py = y + h - inset - v * (h - 2 * inset)  # v=0 is the bottom of the rect
        return px / self.size, 1.0 - py / self.size

    def reduce_palette(self, n, iters=10):
        """Snap the atlas to an n-colour palette (farthest-point seeded k-means),
        so small accent colours (eyes, LEDs, badges) keep their own entries."""
        px = np.round(np.clip(self.rgb, 0, 1).reshape(-1, 3), 4)
        uniq, inverse, counts = np.unique(px, axis=0, return_inverse=True, return_counts=True)
        inverse = inverse.ravel()
        if len(uniq) > n:
            centers = [uniq[np.argmax(counts)]]
            dist = np.linalg.norm(uniq - centers[0], axis=1)
            for _ in range(n - 1):
                centers.append(uniq[np.argmax(dist)])
                dist = np.minimum(dist, np.linalg.norm(uniq - centers[-1], axis=1))
            centers = np.array(centers)
            for _ in range(iters):
                label = np.argmin(np.linalg.norm(uniq[:, None] - centers[None], axis=2), axis=1)
                for k in range(n):
                    sel = label == k
                    if sel.any():
                        centers[k] = np.average(uniq[sel], axis=0, weights=counts[sel])
            label = np.argmin(np.linalg.norm(uniq[:, None] - centers[None], axis=2), axis=1)
            uniq = centers[label]
        self.rgb = uniq[inverse].reshape(self.rgb.shape)

    def palette_size(self):
        q = np.round(np.clip(self.rgb, 0, 1) * 255).astype(np.uint8).reshape(-1, 3)
        return len(np.unique(q, axis=0))

    def save(self, name):
        return rk.save_texture(name, self.rgb)


def scaled(color, k):
    return tuple(min(1.0, c * k) for c in color)


# --------------------------------------------------------------------------
# Cross-section profiles (2D points in a loft frame's (a, b) plane)
# --------------------------------------------------------------------------

def rect(a0, a1, b0, b1):
    a0, a1 = min(a0, a1), max(a0, a1)
    b0, b1 = min(b0, b1), max(b0, b1)
    return [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]


def chamfer_rect(a0, a1, b0, b1, c, top_only=False):
    """Rectangle with 45-degree corner chamfers (octagon, or hexagon if top_only)."""
    a0, a1 = min(a0, a1), max(a0, a1)
    b0, b1 = min(b0, b1), max(b0, b1)
    if top_only:
        return [(a0, b0), (a1, b0), (a1, b1 - c), (a1 - c, b1), (a0 + c, b1), (a0, b1 - c)]
    return [(a0 + c, b0), (a1 - c, b0), (a1, b0 + c), (a1, b1 - c),
            (a1 - c, b1), (a0 + c, b1), (a0, b1 - c), (a0, b0 + c)]


def ngon(n, ra, rb=None, ca=0.0, cb=0.0):
    """Regular n-gon (or ellipse-ish) with a flat side on top (+b)."""
    rb = ra if rb is None else rb
    step = 2 * math.pi / n
    phase = (math.pi / 2 - math.pi / n) % step
    return [(ca + ra * math.cos(phase + k * step), cb + rb * math.sin(phase + k * step)) for k in range(n)]


def xr(side, a, b):
    """Mirror an x interval (a, b) defined for the right (+X) side onto side +1/-1."""
    return tuple(sorted((side * a, side * b)))


AXIS_FRAMES = {
    # axis: (direction, a-axis, b-axis)
    "x": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    "y": ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
    "z": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
}


def frame_along(direction, up=(0, 0, 1)):
    """Orthonormal (d, a, b) frame with b as close to `up` as possible."""
    d = Vector(direction).normalized()
    up = Vector(up)
    if abs(d.dot(up.normalized())) > 0.98:
        up = Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0))
    b = (up - d * up.dot(d)).normalized()
    a = b.cross(d).normalized()
    return tuple(d), tuple(a), tuple(b)


def _signed_area(points):
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(points, points[1:] + points[:1]))


# --------------------------------------------------------------------------
# Mesh builder
# --------------------------------------------------------------------------

class Builder:
    """Accumulates textured primitives into one bmesh."""

    def __init__(self, atlas, material_index=0):
        self.bm = bmesh.new()
        self.uv_layer = self.bm.loops.layers.uv.verify()
        self.atlas = atlas
        self.mat = material_index

    # -- primitives ---------------------------------------------------------

    def loft(self, rings, regions, axis="z", frame=None, origin=(0, 0, 0), caps=(True, True), mat=None,
             long_y=False):
        """Loft closed cross-sections along an axis.

        rings: [(t, [(a, b), ...]), ...] with the same point count in every ring.
        Points are positioned at origin + d*t + a_axis*a + b_axis*b.
        long_y: on +-z faces run the rect's u along Y (for barrels/parts whose
        texture detail follows their length).
        """
        d, ea, eb = (Vector(v) for v in (frame or AXIS_FRAMES[axis]))
        origin = Vector(origin)
        handed = 1 if ea.cross(eb).dot(d) > 0 else -1
        ccw = 1 if _signed_area(list(rings[0][1])) > 0 else -1
        ascending = 1 if rings[-1][0] > rings[0][0] else -1
        flip = handed * ccw * ascending < 0
        vrings = []
        for t, pts in rings:
            pts = list(pts)
            if flip:
                pts.reverse()
            vrings.append([self.bm.verts.new(origin + d * t + ea * a + eb * b) for a, b in pts])
        faces = []
        n = len(vrings[0])
        for r0, r1 in zip(vrings, vrings[1:]):
            for i in range(n):
                j = (i + 1) % n
                faces.append(self.bm.faces.new((r0[i], r0[j], r1[j], r1[i])))
        if caps[0]:
            faces.append(self.bm.faces.new(list(reversed(vrings[0]))))
        if caps[1]:
            faces.append(self.bm.faces.new(vrings[-1]))
        self._finish(faces, regions, mat, long_y)
        return faces

    def box(self, lo, hi, regions, mat=None, long_y=False):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        return self.loft([(z0, rect(x0, x1, y0, y1)), (z1, rect(x0, x1, y0, y1))], regions, "z", mat=mat,
                         long_y=long_y)

    def prism(self, p0, p1, radius, sides, regions, up=(0, 0, 1), rb=None, mat=None, long_y=False):
        """n-sided prism between two points (flat side toward `up`)."""
        p0, p1 = Vector(p0), Vector(p1)
        frame = frame_along(p1 - p0, up)
        length = (p1 - p0).length
        prof = ngon(sides, radius, rb)
        return self.loft([(0.0, prof), (length, prof)], regions, frame=frame, origin=p0, mat=mat, long_y=long_y)

    def tube(self, points, profiles, regions, up=(0, 0, 1), mat=None):
        """Loft along a straight line given ring centre points and matching 2D profiles."""
        p0 = Vector(points[0])
        d, ea, eb = frame_along(Vector(points[-1]) - p0, up)
        dv = Vector(d)
        rings = [((Vector(p) - p0).dot(dv), prof) for p, prof in zip(points, profiles)]
        return self.loft(rings, regions, frame=(d, ea, eb), origin=p0, mat=mat)

    # -- helpers -------------------------------------------------------------

    def _finish(self, faces, regions, mat, long_y=False):
        mat = self.mat if mat is None else mat
        for f in faces:
            f.material_index = mat
            f.normal_update()
        verts = {v for f in faces for v in f.verts}
        lo = Vector([min(v.co[i] for v in verts) for i in range(3)])
        hi = Vector([max(v.co[i] for v in verts) for i in range(3)])
        size = [max(hi[i] - lo[i], 1e-6) for i in range(3)]
        for f in faces:
            n = f.normal
            axis = max(range(3), key=lambda i: abs(n[i]))
            key = ("+" if n[axis] > 0 else "-") + "xyz"[axis]
            if isinstance(regions, dict):
                region = regions.get(key, regions.get("default"))
            else:
                region = regions
            for loop in f.loops:
                p = loop.vert.co
                fx = (p.x - lo.x) / size[0]
                fy = (p.y - lo.y) / size[1]
                fz = (p.z - lo.z) / size[2]
                if axis == 0:
                    u, v = fy, fz
                elif axis == 1:
                    u, v = (1 - fx if key == "+y" else fx), fz
                elif long_y:
                    u, v = fy, (fx if key == "+z" else 1 - fx)
                else:
                    u, v = fx, (fy if key == "+z" else 1 - fy)
                loop[self.uv_layer].uv = self.atlas.uv(region, u, v)

    def transform(self, matrix):
        bmesh.ops.transform(self.bm, matrix=matrix, verts=self.bm.verts)

    def triangles(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)


# --------------------------------------------------------------------------
# Objects, hierarchy, export
# --------------------------------------------------------------------------

def new_collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def mesh_object(name, builder, materials, collection, pivot=(0, 0, 0)):
    """Create a flat-shaded mesh object whose origin is `pivot` (world space)."""
    bm = builder.bm
    bmesh.ops.translate(bm, vec=-Vector(pivot), verts=bm.verts)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for mat in materials:
        mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = False
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def empty_object(name, collection, size=0.05, display="PLAIN_AXES"):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display
    obj.empty_display_size = size
    collection.objects.link(obj)
    return obj


class Rig:
    """Parents objects while tracking world-space pivots (all rotations stay zero)."""

    def __init__(self):
        self.pivots = {}

    def add(self, obj, pivot, parent=None):
        pivot = Vector(pivot)
        self.pivots[obj.name] = pivot
        if parent is not None:
            obj.parent = parent
            obj.location = pivot - self.pivots[parent.name]
        else:
            obj.location = pivot
        return obj


def export_collection(collection, relative_path):
    """Export one collection to Game/assets/<relative_path> as GLB (no vertex colours)."""
    out_path = os.path.join(GAME_ASSET_DIR, relative_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    view_layer = bpy.context.view_layer
    view_layer.active_layer_collection = view_layer.layer_collection.children[collection.name]
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_yup=True,
        export_apply=True,
        export_materials="EXPORT",
        export_vertex_color="NONE",
        use_active_collection=True,
    )
    print("EXPORTED", out_path)
    return out_path


def retire_names(collection, prefix):
    """After export, prefix object/mesh names so the next asset can reuse exact names."""
    for obj in collection.objects:
        obj.name = f"{prefix}.{obj.name}"
        if obj.data is not None:
            obj.data.name = obj.name


def save_blend(name):
    os.makedirs(SOURCE_DIR, exist_ok=True)
    path = os.path.join(SOURCE_DIR, name)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print("SAVED", path)


def count_triangles(collection):
    total = 0
    for obj in collection.objects:
        if obj.type == "MESH":
            total += sum(len(p.vertices) - 2 for p in obj.data.polygons)
    return total


# --------------------------------------------------------------------------
# RGBA sprites
# --------------------------------------------------------------------------

def save_png_rgba(path, rgba):
    """Write an (h, w, 4) float [0, 1] top-down array as an 8-bit RGBA PNG."""
    data = np.round(np.clip(rgba, 0.0, 1.0) * 255).astype(np.uint8)
    h, w, _ = data.shape
    raw = b"".join(b"\x00" + data[row].tobytes() for row in range(h))

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)
    print("WROTE", path)
