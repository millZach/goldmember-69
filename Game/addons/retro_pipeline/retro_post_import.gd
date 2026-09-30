@tool
extends EditorScenePostImportPlugin
## Replaces imported StandardMaterial3Ds with retro ShaderMaterials.
##
## Surfaces with vertex colors are treated as prelit level geometry (unshaded,
## lighting baked in Blender). Surfaces without them get per-vertex lighting.

const PRELIT_SHADER := preload("res://shaders/retro_prelit.gdshader")
const LIT_SHADER := preload("res://shaders/retro_lit.gdshader")


func _post_process(scene: Node) -> void:
	var cache := {}
	for node in scene.find_children("*", "MeshInstance3D", true, false):
		var mesh := (node as MeshInstance3D).mesh as ArrayMesh
		if mesh == null:
			continue
		for surface in mesh.get_surface_count():
			var prelit := (mesh.surface_get_format(surface) & Mesh.ARRAY_FORMAT_COLOR) != 0
			var source := mesh.surface_get_material(surface)
			var key := [source, prelit]
			if not cache.has(key):
				cache[key] = _convert(source, prelit)
			mesh.surface_set_material(surface, cache[key])


func _convert(source: Material, prelit: bool) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = PRELIT_SHADER if prelit else LIT_SHADER
	if source is BaseMaterial3D:
		var base := source as BaseMaterial3D
		material.resource_name = base.resource_name
		material.set_shader_parameter("albedo_texture", base.albedo_texture)
		material.set_shader_parameter("albedo_color", base.albedo_color)
		material.set_shader_parameter("uv_scale", Vector2(base.uv1_scale.x, base.uv1_scale.y))
		material.set_shader_parameter("alpha_cutout", base.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED)
	return material
