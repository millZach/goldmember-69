"""Shared helpers for generating late-90s console-style assets in Blender.

Import from a build script run with:  blender -b --factory-startup --python <script>
"""

import math
import os

import bmesh
import bpy
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEXTURE_DIR = os.path.join(REPO_ROOT, "Blender", "Textures")
SOURCE_DIR = os.path.join(REPO_ROOT, "Blender", "Source")
GAME_ASSET_DIR = os.path.join(REPO_ROOT, "Game", "assets")

# World-space size (meters) covered by one repeat of a level texture.
TEXTURE_WORLD_SIZE = 2.0


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


# --------------------------------------------------------------------------
# Textures
# --------------------------------------------------------------------------

def value_noise(size, cells, rng):
    """Tileable smooth value noise in [0, 1], shape (size, size)."""
    grid = rng.random((cells, cells))
    coords = np.arange(size) * cells / size
    i0 = np.floor(coords).astype(int)
    i1 = (i0 + 1) % cells
    f = coords - i0
    f = f * f * (3.0 - 2.0 * f)
    g00 = grid[np.ix_(i0, i0)]
    g10 = grid[np.ix_(i0, i1)]
    g01 = grid[np.ix_(i1, i0)]
    g11 = grid[np.ix_(i1, i1)]
    fx = f[np.newaxis, :]
    fy = f[:, np.newaxis]
    top = g00 + (g10 - g00) * fx
    bottom = g01 + (g11 - g01) * fx
    return top + (bottom - top) * fy


def fbm(size, rng, octaves=((4, 0.5), (8, 0.25), (16, 0.15), (32, 0.1))):
    total = sum(amp for _, amp in octaves)
    out = sum(value_noise(size, cells, rng) * amp for cells, amp in octaves)
    return out / total


def quantize(values, levels):
    """Snap [0, 1] values to a small number of steps, like a 16-color palette."""
    return np.clip(np.floor(values * levels), 0, levels - 1) / (levels - 1)


def ramp(values, dark, light):
    """Map [0, 1] values onto a two-color ramp. Returns (h, w, 3)."""
    dark = np.array(dark)
    light = np.array(light)
    return dark + (light - dark) * values[..., np.newaxis]


def save_texture(name, rgb):
    """Save an (h, w, 3) top-down float array as a PNG and return the Blender image."""
    os.makedirs(TEXTURE_DIR, exist_ok=True)
    h, w, _ = rgb.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(rgb, 0.0, 1.0)
    image = bpy.data.images.new(name, w, h, alpha=False)
    # Blender stores rows bottom-up.
    image.pixels.foreach_set(np.flipud(rgba).ravel())
    image.filepath_raw = os.path.join(TEXTURE_DIR, name + ".png")
    image.file_format = "PNG"
    image.save()
    return image


def make_material(name, image):
    mat = bpy.data.materials.new(name)
    if not mat.use_nodes:
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    return mat


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def add_grid_quad(bm, origin, u_vec, v_vec, cell=1.0, mat=0):
    """Add a quad subdivided into ~cell-sized squares. Normal = u_vec x v_vec.

    Subdividing matters: lighting is baked per vertex, so big faces need
    interior vertices to show gradients.
    """
    origin = np.array(origin, dtype=float)
    u_vec = np.array(u_vec, dtype=float)
    v_vec = np.array(v_vec, dtype=float)
    nu = max(1, round(np.linalg.norm(u_vec) / cell))
    nv = max(1, round(np.linalg.norm(v_vec) / cell))
    verts = [
        [bm.verts.new(origin + u_vec * (i / nu) + v_vec * (j / nv)) for j in range(nv + 1)]
        for i in range(nu + 1)
    ]
    for i in range(nu):
        for j in range(nv):
            face = bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))
            face.material_index = mat


def add_box(bm, lo, hi, cell=1.0, mat=0, faces=("+x", "-x", "+y", "-y", "+z", "-z")):
    """Add an outward-facing box from corner lo to corner hi."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    specs = {
        "+x": ((x1, y0, z0), (0, dy, 0), (0, 0, dz)),
        "-x": ((x0, y1, z0), (0, -dy, 0), (0, 0, dz)),
        "+y": ((x1, y1, z0), (-dx, 0, 0), (0, 0, dz)),
        "-y": ((x0, y0, z0), (dx, 0, 0), (0, 0, dz)),
        "+z": ((x0, y0, z1), (dx, 0, 0), (0, dy, 0)),
        "-z": ((x0, y1, z0), (dx, 0, 0), (0, -dy, 0)),
    }
    for key in faces:
        origin, u_vec, v_vec = specs[key]
        add_grid_quad(bm, origin, u_vec, v_vec, cell, mat)


def box_project_uvs(bm, world_size=TEXTURE_WORLD_SIZE):
    """World-space box-mapped UVs so texel density is constant across the level."""
    uv_layer = bm.loops.layers.uv.verify()
    for face in bm.faces:
        n = face.normal
        axis = max(range(3), key=lambda a: abs(n[a]))
        for loop in face.loops:
            p = loop.vert.co
            if axis == 0:
                u, v = p.y * (1 if n.x > 0 else -1), p.z
            elif axis == 1:
                u, v = p.x * (-1 if n.y > 0 else 1), p.z
            else:
                u, v = p.x, p.y * (1 if n.z > 0 else -1)
            loop[uv_layer].uv = (u / world_size, v / world_size)


def face_uvs(bm):
    """Map the full texture onto every face (for props like crates)."""
    uv_layer = bm.loops.layers.uv.verify()
    corners = ((0, 0), (1, 0), (1, 1), (0, 1))
    for face in bm.faces:
        for loop, uv in zip(face.loops, corners):
            loop[uv_layer].uv = uv


def bake_vertex_lighting(mesh, lights, ambient, floor_occlusion=0.25, occlusion_height=1.2):
    """Bake simple prelit vertex colors: ambient + lambert point lights, no shadows.

    lights: list of (position, color, radius).
    floor_occlusion darkens vertices near the floor, a cheap stand-in for AO.
    """
    attr = mesh.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    mesh.color_attributes.active_color = attr
    ambient = np.array(ambient)
    for poly in mesh.polygons:
        normal = np.array(poly.normal)
        for loop_index in poly.loop_indices:
            pos = np.array(mesh.vertices[mesh.loops[loop_index].vertex_index].co)
            color = ambient.copy()
            for light_pos, light_color, radius in lights:
                to_light = np.array(light_pos) - pos
                dist = np.linalg.norm(to_light)
                if dist >= radius:
                    continue
                lambert = max(0.0, float(np.dot(normal, to_light / max(dist, 1e-4))))
                falloff = (1.0 - dist / radius) ** 1.5
                color += np.array(light_color) * lambert * falloff
            if pos[2] < occlusion_height:
                color *= 1.0 - floor_occlusion * (1.0 - pos[2] / occlusion_height)
            attr.data[loop_index].color = (*np.clip(color, 0.0, 1.0), 1.0)


def mesh_object(name, bm, materials):
    mesh = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    for mat in materials:
        mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = False
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def export_glb(relative_path, blend_name):
    """Export the scene to Game/assets/<relative_path> and save the .blend source."""
    out_path = os.path.join(GAME_ASSET_DIR, relative_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_yup=True,
        export_apply=True,
        export_materials="EXPORT",
        export_vertex_color="ACTIVE",
        export_image_format="AUTO",
    )
    os.makedirs(SOURCE_DIR, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SOURCE_DIR, blend_name))
    print("EXPORTED", out_path)


def deg(value):
    return math.radians(value)
