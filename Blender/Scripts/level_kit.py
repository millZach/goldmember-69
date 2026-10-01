"""Extra helpers for large outdoor levels, built on top of retro_kit.

Everything here is deterministic given the rng passed in. Geometry helpers take
a `hint` vector: faces are wound so their normal agrees with it, which keeps
back-face culling and one-sided trimesh collision correct without bookkeeping.
"""

import math

import bmesh
import bpy
import numpy as np

import retro_kit as rk

UP = np.array((0.0, 0.0, 1.0))


def v3(p):
    return np.array(p, dtype=float)


# --------------------------------------------------------------------------
# Primitive geometry
# --------------------------------------------------------------------------

def face(bm, pts, mat, hint):
    """Add a single polygon, flipped if its normal disagrees with `hint`."""
    pts = [v3(p) for p in pts]
    n = np.zeros(3)
    for a, b in zip(pts, pts[1:] + pts[:1]):  # Newell normal
        n += np.cross(a, b)
    if np.dot(n, hint) < 0:
        pts = pts[::-1]
    f = bm.faces.new([bm.verts.new(p) for p in pts])
    f.material_index = mat
    return f


def grid(bm, origin, u, v, hint, cell=1.0, mat=0):
    """Subdivided quad (see retro_kit.add_grid_quad) oriented to face `hint`."""
    u, v = v3(u), v3(v)
    if np.dot(np.cross(u, v), hint) < 0:
        u, v = v, u
    rk.add_grid_quad(bm, origin, u, v, cell=cell, mat=mat)


def box(bm, lo, hi, mat, cell=1.0, faces=("+x", "-x", "+y", "-y", "+z"), mats=None):
    """Outward-facing axis-aligned box. `mats` optionally maps face key -> material."""
    for key in faces:
        rk.add_box(bm, lo, hi, cell=cell, mat=(mats or {}).get(key, mat), faces=(key,))


def slab(bm, p0, p1, z0, z1, thick, mat, cell=1.0, top=True, caps=True, bottom=False,
         side_mats=None, top_mat=None):
    """Box extruded along the XY segment p0->p1 (walls, rails, fences)."""
    p0, p1 = v3((*p0[:2], 0)), v3((*p1[:2], 0))
    d = p1 - p0
    length = np.linalg.norm(d)
    d /= length
    n = np.array((-d[1], d[0], 0.0))
    h = UP * (z1 - z0)
    a = p0 - n * thick / 2 + UP * z0
    b = p1 - n * thick / 2 + UP * z0
    c = p1 + n * thick / 2 + UP * z0
    e = p0 + n * thick / 2 + UP * z0
    sm = side_mats or (mat, mat)
    grid(bm, a, b - a, h, -n, cell, sm[0])
    grid(bm, e, c - e, h, n, cell, sm[1])
    if top:
        grid(bm, a + h, b - a, e - a, UP, cell, mat if top_mat is None else top_mat)
    if bottom:
        grid(bm, a, b - a, e - a, -UP, cell, mat)
    if caps:
        grid(bm, a, e - a, h, -d, cell, mat)
        grid(bm, b, c - b, h, d, cell, mat)


def wall(bm, p0, p1, z0, z1, thick, mat_pos, mat_neg, mat_edge, openings=(), cell=1.0,
         caps=True, top=True):
    """Thick wall along p0->p1 with rectangular openings.

    openings: (s0, s1, zb, zt) in metres along the wall from p0 and above z0.
    mat_pos is used on the side the left-perpendicular of p0->p1 points to.
    """
    p0, p1 = v3((*p0[:2], 0)), v3((*p1[:2], 0))
    d = p1 - p0
    length = np.linalg.norm(d)
    d /= length
    n = np.array((-d[1], d[0], 0.0))
    t2 = thick / 2
    cuts = sorted({0.0, length, *[o[0] for o in openings], *[o[1] for o in openings]})

    def piece(sa, sb, za, zb):
        for side, mat in ((1, mat_pos), (-1, mat_neg)):
            origin = p0 + d * sa + n * side * t2 + UP * (z0 + za)
            grid(bm, origin, d * (sb - sa), UP * (zb - za), n * side, cell, mat)

    for sa, sb in zip(cuts, cuts[1:]):
        mid = (sa + sb) / 2
        hole = next((o for o in openings if o[0] <= mid <= o[1]), None)
        if hole is None:
            piece(sa, sb, 0.0, z1 - z0)
        else:
            if hole[2] > 0:
                piece(sa, sb, 0.0, hole[2])
            if hole[3] < z1 - z0:
                piece(sa, sb, hole[3], z1 - z0)
    for s0, s1, zb, zt in openings:
        width = UP * (zt - zb)
        for s, sign in ((s0, 1), (s1, -1)):  # jambs face into the opening
            grid(bm, p0 + d * s - n * t2 + UP * (z0 + zb), n * thick, width, d * sign, cell, mat_edge)
        span = d * (s1 - s0)
        if zb > 0:
            grid(bm, p0 + d * s0 - n * t2 + UP * (z0 + zb), span, n * thick, UP, cell, mat_edge)
        grid(bm, p0 + d * s0 - n * t2 + UP * (z0 + zt), span, n * thick, -UP, cell, mat_edge)
    if top:
        grid(bm, p0 - n * t2 + UP * z1, d * length, n * thick, UP, cell, mat_edge)
    if caps:
        grid(bm, p0 - n * t2 + UP * z0, n * thick, UP * (z1 - z0), -d, cell, mat_edge)
        grid(bm, p1 - n * t2 + UP * z0, n * thick, UP * (z1 - z0), d, cell, mat_edge)


def prism(bm, profile, p0, p1, mat, cell=1.0, caps=True):
    """Extrude a closed 2D profile [(across, z), ...] (counter-clockwise when viewed
    looking along p0->p1) along the XY segment p0->p1. Used for jersey barriers."""
    p0, p1 = v3((*p0[:2], 0)), v3((*p1[:2], 0))
    d = p1 - p0
    d /= np.linalg.norm(d)
    n = np.array((-d[1], d[0], 0.0))
    pts0 = [p0 + n * a + UP * z for a, z in profile]
    pts1 = [p1 + n * a + UP * z for a, z in profile]
    centre0 = sum(pts0) / len(pts0)
    for i in range(len(profile)):
        j = (i + 1) % len(profile)
        mid = (pts0[i] + pts0[j]) / 2
        out = mid - centre0
        out -= d * np.dot(out, d)
        grid(bm, pts0[i], pts1[i] - pts0[i], pts0[j] - pts0[i], out, cell, mat)
    if caps:
        face(bm, pts0, mat, -d)
        face(bm, pts1, mat, d)


# --------------------------------------------------------------------------
# Terrain
# --------------------------------------------------------------------------

def coords(a, b, cell, extra=()):
    """Evenly spaced coordinates from a to b (~cell apart) plus forced break lines."""
    n = max(1, round(abs(b - a) / cell))
    vals = set(np.round(np.linspace(a, b, n + 1), 4))
    vals |= {round(float(e), 4) for e in extra if min(a, b) < e < max(a, b)}
    vals = sorted(vals)
    # Drop break lines that would create slivers.
    out = [vals[0]]
    for x in vals[1:]:
        if x - out[-1] < 0.25 * cell and x not in extra and x != vals[-1]:
            continue
        out.append(x)
    return out


def _in_rect(u, v, rect, eps=1e-4):
    return rect[0] - eps <= u <= rect[1] + eps and rect[2] - eps <= v <= rect[3] + eps


def rock_face(route, origin, u_axis, v_axis, us, vs, facing, rng, amp=1.5, mat=0,
              holes=(), flats=(), flat_mat=0, pin_edges=(), lean=None, jag_top=0.0):
    """Noise-displaced cliff/wall grid.

    route(centre_xyz) -> bmesh chooses which object each cell goes into.
    us/vs are coordinate lists along u_axis/v_axis; holes/flats are (u0,u1,v0,v1)
    rectangles: holes are skipped, flats use flat_mat and get no displacement.
    Displacement pushes vertices away from `facing` (into the rock).
    pin_edges: any of "u0", "u1", "v0", "v1" to keep that border flat.
    lean(u, v) -> extra displacement into the rock (large-scale shape, e.g. a
    mountainside sloping back); jag_top randomises the top row's height.
    """
    origin, u_axis, v_axis, facing = v3(origin), v3(u_axis), v3(v_axis), v3(facing)
    facing /= np.linalg.norm(facing)
    noise = rng.random((len(us), len(vs)))
    pos = np.zeros((len(us), len(vs), 3))
    for i, u in enumerate(us):
        for j, v in enumerate(vs):
            pinned = any(_in_rect(u, v, r) for r in (*holes, *flats))
            pinned |= ("u0" in pin_edges and i == 0) or ("u1" in pin_edges and i == len(us) - 1)
            pinned |= ("v0" in pin_edges and j == 0) or ("v1" in pin_edges and j == len(vs) - 1)
            disp = 0.0 if pinned else amp * noise[i, j]
            if lean is not None:
                disp += lean(u, v)
            pos[i, j] = origin + u_axis * u + v_axis * v - facing * disp
            if jag_top and j == len(vs) - 1:
                pos[i, j] += UP * jag_top * (noise[i, j - 1] * 2 - 1)
    for i in range(len(us) - 1):
        for j in range(len(vs) - 1):
            cu, cv = (us[i] + us[i + 1]) / 2, (vs[j] + vs[j + 1]) / 2
            if any(_in_rect(cu, cv, r, 0) for r in holes):
                continue
            m = flat_mat if any(_in_rect(cu, cv, r, 0) for r in flats) else mat
            quad = [pos[i, j], pos[i + 1, j], pos[i + 1, j + 1], pos[i, j + 1]]
            centre = sum(quad) / 4
            face(route(centre), quad, m, facing)


def ridge(bm, base, inward, rng, mat, rows=(0.0, 1.6, 4.0, 7.0, 10.5, 14.0), lean=0.12,
          amp=1.3, jag=2.0, cap=4.0, back_out=8.0, back_drop=22.0):
    """Jagged rock ridge along a base polyline, front face looking along `inward`.

    The profile runs up the front face, over a cap and down a coarse back face so
    the ridge reads as solid rock from both sides. The base row sits exactly on
    the base points (floor edge) so there is no crack between floor and cliff.
    """
    base = np.asarray(base, dtype=float)
    inward = np.asarray(inward, dtype=float)
    cols = []
    for i, (b, w) in enumerate(zip(base, inward)):
        out = -np.array((w[0], w[1], 0.0))
        tang = np.array((-out[1], out[0], 0.0))
        prof = []
        d = 0.0
        for k, h in enumerate(rows):
            if k == 0:
                prof.append(b.copy())
                continue
            d = lean * h + amp * rng.uniform(-0.2, 1.0)
            dz = rng.uniform(-jag, jag) if k == len(rows) - 1 else rng.uniform(-0.3, 0.3)
            jit = rng.uniform(-0.4, 0.4) if 0 < i < len(base) - 1 else 0.0
            prof.append(b + out * d + tang * jit + UP * (h + dz))
        top = prof[-1][2]
        cap_pt = b + out * (d + cap + rng.uniform(0, 2.5))
        cap_pt[2] = top + rng.uniform(-1.0, 1.5)
        prof.append(cap_pt)
        prof.append(b + out * (d + cap + back_out) - UP * back_drop)
        cols.append(prof)
    # Consistent winding across the whole ridge; decide once from the first segment.
    t = base[min(1, len(base) - 1)] - base[0]
    flip = np.dot(np.cross(t, UP), np.array((*inward[0], 0.0))) < 0
    for i in range(len(cols) - 1):
        for k in range(len(cols[i]) - 1):
            quad = [cols[i][k], cols[i + 1][k], cols[i + 1][k + 1], cols[i][k + 1]]
            if flip:
                quad = quad[::-1]
            f = bm.faces.new([bm.verts.new(p) for p in quad])
            f.material_index = mat


def polyline_samples(points, step=2.0):
    """Resample a polyline so no segment is longer than step (keeps corners)."""
    pts = [v3(p) for p in points]
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, math.ceil(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * (k / n) for k in range(1, n + 1)]
    return np.array(out)


def polyline_inward(samples, side="left"):
    """Unit horizontal normals (mitred at corners) on the given side of travel."""
    n = len(samples)
    res = []
    for i in range(n):
        normals = []
        for a, b in ((i - 1, i), (i, i + 1)):
            if 0 <= a and b < n:
                t = samples[b][:2] - samples[a][:2]
                t /= np.linalg.norm(t)
                left = np.array((-t[1], t[0]))
                normals.append(left if side == "left" else -left)
        m = sum(normals)
        m /= np.linalg.norm(m)
        # Mitre so offset edges stay parallel to the segments.
        res.append(m / max(0.5, float(np.dot(m, normals[0]))))
    return np.array(res)


# --------------------------------------------------------------------------
# UVs
# --------------------------------------------------------------------------

def project_uvs(bm, scales, face_mapped=(), default=rk.TEXTURE_WORLD_SIZE):
    """World-space box-projected UVs with per-material scale.

    scales: material index -> size, or (size_u, size_v, v_offset).
    face_mapped: material indices that get the whole texture per face (screens,
    crates); orientation keeps world-up as texture-up.
    """
    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        if f.material_index in face_mapped:
            nn = np.array(n)
            up = UP - nn * np.dot(UP, nn)
            if np.linalg.norm(up) < 1e-3:
                up = np.array((0.0, 1.0, 0.0))
            up /= np.linalg.norm(up)
            right = np.cross(up, nn)
            pts = np.array([lp.vert.co for lp in f.loops])
            us, vs = pts @ right, pts @ up
            du, dv = max(us.max() - us.min(), 1e-6), max(vs.max() - vs.min(), 1e-6)
            for lp, u, v in zip(f.loops, us, vs):
                lp[uv_layer].uv = ((u - us.min()) / du, (v - vs.min()) / dv)
            continue
        s = scales.get(f.material_index, default)
        su, sv, voff = (s, s, 0.0) if np.isscalar(s) else s
        axis = max(range(3), key=lambda a: abs(n[a]))
        for lp in f.loops:
            p = lp.vert.co
            if axis == 0:
                u, v = p.y * (1 if n.x > 0 else -1), p.z - voff
            elif axis == 1:
                u, v = p.x * (-1 if n.y > 0 else 1), p.z - voff
            else:
                u, v, sv_ = p.x, p.y * (1 if n.z > 0 else -1), su
                lp[uv_layer].uv = (u / su, v / sv_)
                continue
            lp[uv_layer].uv = (u / su, v / sv)


# --------------------------------------------------------------------------
# Lighting
# --------------------------------------------------------------------------

class Light:
    def __init__(self, pos, color, radius, zones=("out",)):
        self.pos = v3(pos)
        self.color = v3(color)
        self.radius = float(radius)
        self.zones = tuple(zones)


def bake_vertex_lighting(obj, lights, ambient, zones=None, fullbright=None):
    """Vectorised equivalent of retro_kit.bake_vertex_lighting with light zones.

    Same model (ambient + lambert point lights with (1 - d/r)^1.5 falloff, no
    shadows), plus:
      zones: name -> (lo, hi) world boxes. A vertex inside a box belongs to that
             zone, else "out". Lights only affect vertices in their zones, which
             stops interior lamps bleeding through walls and vice versa.
      ambient(zone_ids, zone_names, pos, nrm) -> (N, 3) ambient colour.
      fullbright: material index -> rgb forced onto those faces (light panels).
    """
    mesh = obj.data
    mw = np.array(obj.matrix_world)
    rot = mw[:3, :3]
    attr = mesh.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    mesh.color_attributes.active_color = attr
    n_loops = len(mesh.loops)
    if n_loops == 0:
        return
    vidx = np.zeros(n_loops, dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", vidx)
    co = np.zeros(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) @ rot.T + mw[:3, 3]
    pos = co[vidx]
    pnorm = np.zeros(len(mesh.polygons) * 3)
    mesh.polygons.foreach_get("normal", pnorm)
    pnorm = pnorm.reshape(-1, 3) @ rot.T
    pnorm /= np.maximum(np.linalg.norm(pnorm, axis=1, keepdims=True), 1e-9)
    loop_start = np.zeros(len(mesh.polygons), dtype=np.int64)
    loop_total = np.zeros(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get("loop_start", loop_start)
    mesh.polygons.foreach_get("loop_total", loop_total)
    poly_of_loop = np.repeat(np.arange(len(mesh.polygons)), loop_total)
    order = np.argsort(np.repeat(loop_start, loop_total) + np.concatenate(
        [np.arange(t) for t in loop_total]))
    poly_of_loop = poly_of_loop[order]
    nrm = pnorm[poly_of_loop]

    zone_names = ["out"] + list((zones or {}).keys())
    zone_id = np.zeros(n_loops, dtype=np.int64)
    for zi, name in enumerate(zone_names[1:], start=1):
        lo, hi = (v3(b) for b in zones[name])
        inside = np.all((pos >= lo) & (pos <= hi), axis=1)
        zone_id[inside & (zone_id == 0)] = zi

    color = ambient(zone_id, zone_names, pos, nrm).astype(float)
    for light in lights:
        allowed = np.isin(zone_id, [zone_names.index(z) for z in light.zones if z in zone_names])
        to_light = light.pos - pos
        dist = np.linalg.norm(to_light, axis=1)
        mask = allowed & (dist < light.radius)
        if not mask.any():
            continue
        lam = np.clip(np.sum(nrm[mask] * to_light[mask], axis=1) / np.maximum(dist[mask], 1e-4), 0, None)
        fall = (1.0 - dist[mask] / light.radius) ** 1.5
        color[mask] += light.color[None, :] * (lam * fall)[:, None]

    if fullbright:
        mats = np.zeros(len(mesh.polygons), dtype=np.int64)
        mesh.polygons.foreach_get("material_index", mats)
        loop_mat = mats[poly_of_loop]
        for mi, rgb in fullbright.items():
            color[loop_mat == mi] = rgb
    rgba = np.ones((n_loops, 4))
    rgba[:, :3] = np.clip(color, 0.0, 1.0)
    attr.data.foreach_set("color", rgba.ravel())
    return rgba[:, :3]


# --------------------------------------------------------------------------
# Markers
# --------------------------------------------------------------------------

def yaw_towards(dx, dy):
    """Z rotation that turns an empty's local +Y towards (dx, dy)."""
    return math.atan2(-dx, dy)


def marker(name, pos, yaw=0.0, display="ARROWS", scale=(1.0, 1.0, 1.0), size=0.5):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display
    obj.empty_display_size = size if display != "CUBE" else 1.0
    obj.location = pos
    obj.rotation_euler = (0.0, 0.0, yaw)
    obj.scale = scale
    bpy.context.scene.collection.objects.link(obj)
    return obj
