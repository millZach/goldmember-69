class_name GuardAnimator
extends Node
## Procedural animation for the segmented (rigid-part) guard model: walk cycle,
## aiming pose, hit flinches and death falls. Parts rotate about their joint origins.

const PARTS: Array[String] = [
	"Pelvis", "Torso", "Head",
	"UpperArm_R", "LowerArm_R", "UpperArm_L", "LowerArm_L",
	"Thigh_R", "Shin_R", "Thigh_L", "Shin_L",
]

var model: Node3D
var muzzle: Node3D
var weapon: Node3D

var _parts := {}
var _rest_position := {}
var _flinch := {} ## part -> Vector3 euler offset, decays over time
var _walk_phase := 0.0
var _aim := 0.0
var _flash: Sprite3D
var _flash_left := 0.0

var _dead := false
var _death_time := 0.0
var _death_style := 0 ## 0 fall back, 1 crumple forward, 2 spin
var _death_side := 1.0


func setup(guard_model: Node3D, weapon_id: String) -> void:
	model = guard_model
	for part_name in PARTS:
		var part := model.find_child(part_name, true, false) as Node3D
		if part:
			_parts[part_name] = part
			_rest_position[part_name] = part.position
	var socket := model.find_child("WeaponSocket", true, false) as Node3D
	var scene := Weapons.world_scene(weapon_id)
	if socket and scene:
		weapon = scene.instantiate()
		# The world model's barrel points along -Z; with the arm hanging down, point it down.
		weapon.rotation.x = -PI * 0.5
		socket.add_child(weapon)
		muzzle = weapon.find_child("Muzzle", true, false)
		if muzzle:
			_flash = Effects.make_flash_sprite(0.012)
			muzzle.add_child(_flash)


func muzzle_position() -> Vector3:
	if muzzle:
		return muzzle.global_position
	return model.global_position + Vector3.UP * 1.4


func flash() -> void:
	_flash_left = 0.06


## zone: "head", "torso", "arm", "leg"
func flinch(zone: String) -> void:
	match zone:
		"head":
			_add_flinch("Head", Vector3(0.7, randf_range(-0.3, 0.3), 0))
			_add_flinch("Torso", Vector3(0.25, 0, 0))
		"torso":
			_add_flinch("Torso", Vector3(0.45, randf_range(-0.25, 0.25), 0))
			_add_flinch("Head", Vector3(0.2, 0, 0))
		"arm":
			var side := "R" if randf() < 0.5 else "L"
			_add_flinch("UpperArm_" + side, Vector3(-0.9, 0, 0.4 if side == "R" else -0.4))
			_add_flinch("Torso", Vector3(0, 0.35 if side == "R" else -0.35, 0))
		"leg":
			var side := "R" if randf() < 0.5 else "L"
			_add_flinch("Thigh_" + side, Vector3(0.5, 0, 0))
			_add_flinch("Shin_" + side, Vector3(-1.1, 0, 0))
			_add_flinch("Torso", Vector3(-0.35, 0, 0))


func die(zone: String) -> void:
	_dead = true
	_death_time = 0.0
	_death_side = 1.0 if randf() < 0.5 else -1.0
	match zone:
		"leg":
			_death_style = 1
		"head":
			_death_style = 2 if randf() < 0.5 else 0
		_:
			_death_style = 0 if randf() < 0.7 else 2
	if _flash:
		_flash.visible = false


func is_dead() -> bool:
	return _dead


## speed: ground speed in m/s. aiming: blend toward the two-handed aim pose.
func update(delta: float, speed: float, aiming: bool) -> void:
	if model == null:
		return
	for part_name in _flinch:
		_flinch[part_name] = (_flinch[part_name] as Vector3).lerp(Vector3.ZERO, 1.0 - exp(-7.0 * delta))
	_flash_left -= delta
	if _flash:
		_flash.visible = _flash_left > 0.0
		_flash.rotation.z = randf() * TAU

	if _dead:
		_update_death(delta)
		return

	var amount := clampf(speed / 3.5, 0.0, 1.0)
	_walk_phase = fmod(_walk_phase + delta * speed * 4.2, TAU)
	_aim = move_toward(_aim, 1.0 if aiming else 0.0, delta * 5.0)
	var s := sin(_walk_phase)
	var pose := {}
	pose["Thigh_R"] = Vector3(s * 0.55 * amount, 0, 0)
	pose["Thigh_L"] = Vector3(-s * 0.55 * amount, 0, 0)
	pose["Shin_R"] = Vector3(-maxf(0.0, sin(_walk_phase + 1.2)) * 0.8 * amount, 0, 0)
	pose["Shin_L"] = Vector3(-maxf(0.0, sin(_walk_phase + PI + 1.2)) * 0.8 * amount, 0, 0)
	pose["Torso"] = Vector3(0.05 * amount, s * 0.08 * amount, 0)
	pose["Head"] = Vector3.ZERO
	pose["Pelvis"] = Vector3.ZERO

	var swing_r := Vector3(-s * 0.4 * amount, 0, 0.08)
	var swing_l := Vector3(s * 0.4 * amount, 0, -0.08)
	var aim_r := Vector3(1.45, 0.15, 0)
	var aim_l := Vector3(1.3, -0.55, 0)
	pose["UpperArm_R"] = swing_r.lerp(aim_r, _aim)
	pose["UpperArm_L"] = swing_l.lerp(aim_l, _aim)
	pose["LowerArm_R"] = Vector3(0.25, 0, 0).lerp(Vector3(0.1, 0, 0), _aim)
	pose["LowerArm_L"] = Vector3(0.25, 0, 0).lerp(Vector3(0.35, 0.3, 0), _aim)

	for part_name in _parts:
		(_parts[part_name] as Node3D).rotation = pose.get(part_name, Vector3.ZERO) + _flinch.get(part_name, Vector3.ZERO)
	if _parts.has("Pelvis"):
		_parts.Pelvis.position = _rest_position.Pelvis + Vector3.UP * absf(s) * 0.03 * amount


func _update_death(delta: float) -> void:
	_death_time += delta
	var t := clampf(_death_time / 0.75, 0.0, 1.0)
	var fall := t * t
	var knees := clampf(_death_time / 0.25, 0.0, 1.0)
	var limp := {}
	match _death_style:
		0: # Knocked backwards.
			model.rotation = Vector3(fall * PI * 0.5, 0, 0)
			limp = {"UpperArm_R": Vector3(-0.6, 0, 1.0), "UpperArm_L": Vector3(-0.6, 0, -1.0),
					"Thigh_R": Vector3(0.3 * knees, 0, 0), "Shin_R": Vector3(-0.4 * knees, 0, 0),
					"Head": Vector3(0.4, 0, 0)}
		1: # Legs give out, crumple forwards.
			model.rotation = Vector3(-fall * PI * 0.5, 0, 0)
			limp = {"Thigh_R": Vector3(1.0 * knees, 0, 0), "Thigh_L": Vector3(0.9 * knees, 0, 0),
					"Shin_R": Vector3(-1.6 * knees, 0, 0), "Shin_L": Vector3(-1.5 * knees, 0, 0),
					"UpperArm_R": Vector3(1.2, 0, 0.3), "UpperArm_L": Vector3(1.2, 0, -0.3),
					"Head": Vector3(-0.3, 0, 0)}
		2: # Spin and fall sideways.
			model.rotation = Vector3(0, _death_side * t * 1.8, _death_side * fall * PI * 0.5)
			limp = {"UpperArm_R": Vector3(0, 0, 1.3), "UpperArm_L": Vector3(0, 0, -1.3),
					"Thigh_L": Vector3(0.5 * knees, 0, 0), "Shin_L": Vector3(-0.8 * knees, 0, 0),
					"Head": Vector3(0, 0, _death_side * 0.5)}
	# Lift slightly as the body tips so it lies on the floor rather than in it.
	model.position.y = fall * 0.15
	for part_name in _parts:
		var target: Vector3 = limp.get(part_name, Vector3.ZERO)
		var part: Node3D = _parts[part_name]
		part.rotation = part.rotation.lerp(target, 1.0 - exp(-10.0 * delta))


func _add_flinch(part_name: String, offset: Vector3) -> void:
	_flinch[part_name] = _flinch.get(part_name, Vector3.ZERO) + offset
