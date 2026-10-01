extends Node
## Spawns short-lived visual effects (bullet holes, puffs, explosions) into the current scene.

const SPRITE_DIR := "res://assets/sprites/"
const MAX_BULLET_HOLES := 48

var _textures := {}
var _holes: Array[MeshInstance3D] = []
var _hole_mesh: QuadMesh


func _ready() -> void:
	_hole_mesh = QuadMesh.new()
	_hole_mesh.size = Vector2(0.12, 0.12)
	var tex := texture("bullet_hole")
	if tex:
		_hole_mesh.material = _sprite_material(tex, false)


func texture(sprite_name: String) -> Texture2D:
	if not _textures.has(sprite_name):
		var path := SPRITE_DIR + sprite_name + ".png"
		_textures[sprite_name] = load(path) if ResourceLoader.exists(path) else null
	return _textures[sprite_name]


func bullet_hole(position: Vector3, normal: Vector3) -> void:
	if _hole_mesh.material == null:
		return
	# Holes are freed with their scene, so drop stale entries first.
	_holes.assign(_holes.filter(func(h): return is_instance_valid(h)))
	var hole: MeshInstance3D
	if _holes.size() < MAX_BULLET_HOLES:
		hole = MeshInstance3D.new()
		hole.mesh = _hole_mesh
		_attach(hole)
	else:
		hole = _holes.pop_front()
	_holes.append(hole)
	var up := Vector3.UP if absf(normal.dot(Vector3.UP)) < 0.95 else Vector3.FORWARD
	hole.global_transform = Transform3D(Basis.looking_at(-normal, up), position + normal * 0.01)
	hole.rotate_object_local(Vector3.FORWARD, randf() * TAU)


## A puff sprite that expands and fades. kind: "impact_puff" or "hit_puff".
func puff(position: Vector3, kind := "impact_puff", size := 0.02) -> void:
	var tex := texture(kind)
	if tex == null:
		return
	var sprite := _billboard(tex, size)
	_attach(sprite)
	sprite.global_position = position
	var tween := sprite.create_tween()
	tween.set_parallel()
	tween.tween_property(sprite, "scale", Vector3.ONE * 2.0, 0.3)
	tween.tween_property(sprite, "modulate:a", 0.0, 0.3)
	tween.chain().tween_callback(sprite.queue_free)


func explosion(position: Vector3) -> void:
	Sound.play("explosion", position, 4.0, 0.0)
	var tex := texture("explosion_sheet")
	if tex == null:
		return
	var sprite := _billboard(tex, 0.12)
	sprite.hframes = 8
	_attach(sprite)
	sprite.global_position = position + Vector3.UP * 1.2
	var tween := sprite.create_tween()
	tween.tween_property(sprite, "frame", 7, 0.8)
	tween.tween_callback(sprite.queue_free)


## A billboard sprite for things like muzzle flashes. Caller owns it.
func make_flash_sprite(size := 0.01) -> Sprite3D:
	var tex := texture("muzzle_flash")
	var sprite := _billboard(tex, size) if tex else Sprite3D.new()
	sprite.visible = false
	return sprite


func _billboard(tex: Texture2D, pixel_size: float) -> Sprite3D:
	var sprite := Sprite3D.new()
	sprite.texture = tex
	sprite.pixel_size = pixel_size
	sprite.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	sprite.shaded = false
	sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
	sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	return sprite


func _sprite_material(tex: Texture2D, billboard: bool) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_texture = tex
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	if billboard:
		material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	return material


func _attach(node: Node3D) -> void:
	var scene := get_tree().current_scene
	if node.get_parent() != scene:
		if node.get_parent():
			node.get_parent().remove_child(node)
		scene.add_child(node)
