class_name Player
extends CharacterBody3D
## First-person agent controller tuned for a late-90s console feel: brisk movement,
## no jumping, head bob, auto-levelling pitch on controller, and an aim mode where
## look input moves a crosshair around the screen (turning only at the edges).

signal health_changed
signal died

@export_group("Movement")
@export var run_speed := 5.5
@export var strafe_speed := 4.5
@export var crouch_speed_scale := 0.5
@export var aim_speed_scale := 0.5
@export var acceleration := 30.0
@export var gravity := 20.0
@export var footstep_distance := 2.2

@export_group("Look")
@export var stick_yaw_speed := 170.0 ## Degrees per second at full deflection.
@export var stick_pitch_speed := 110.0
@export var stick_curve := 2.0 ## Response exponent; higher gives finer control near center.
@export var max_pitch := 70.0
@export var auto_level_speed := 50.0 ## Degrees per second; 0 disables.

@export_group("Aim mode")
@export var crosshair_limit := 0.8 ## Fraction of the half-screen the crosshair may travel.
@export var crosshair_mouse_speed := 0.004 ## Screen fraction per screen pixel of mouse motion.
@export var crosshair_stick_speed := 1.6 ## Screen fraction per second at full deflection.
@export var edge_turn_speed := 60.0 ## Degrees per second of turning when the crosshair is at the edge.

@export_group("Camera")
@export var stand_height := 1.6
@export var crouch_height := 1.0
@export var base_fov := 60.0
@export var aim_fov := 38.0
@export var bob_amount := 0.035
@export var bob_cycles_per_meter := 0.35

const MAX_HEALTH := 100.0
const MAX_ARMOR := 100.0
const INTERACT_RANGE := 2.2
const STAND_CAPSULE_HEIGHT := 1.75
const CROUCH_CAPSULE_HEIGHT := 1.15

var health := MAX_HEALTH
var armor := 0.0
var pitch := 0.0
var crouched := false
var aiming := false
var controls_enabled := true
## Crosshair position in aim mode, in half-screen units (-1..1).
var aim_offset := Vector2.ZERO
## The interactable currently under the crosshair, if any.
var focused_interactable: Interactable

var _bob_phase := 0.0
var _bob_weight := 0.0
var _using_stick := false
var _step_distance := 0.0
var _recoil_pitch := 0.0

@onready var weapons: WeaponManager = $Weapons
@onready var _head: Node3D = $Head
@onready var _camera: Camera3D = $Head/Camera
@onready var _collision: CollisionShape3D = $Collision


func _ready() -> void:
	add_to_group("player")
	collision_layer = Layers.PLAYER
	collision_mask = Layers.WORLD | Layers.GUARDS
	_head.position.y = stand_height
	_camera.fov = base_fov
	_collision.shape = _collision.shape.duplicate()


func _unhandled_input(event: InputEvent) -> void:
	if not controls_enabled:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_using_stick = false
		var motion: Vector2 = event.screen_relative
		if Game.settings.invert_y:
			motion.y = -motion.y
		if aiming:
			_move_crosshair(motion * crosshair_mouse_speed)
		else:
			var sensitivity: float = Game.settings.mouse_sensitivity
			_turn(-motion.x * sensitivity, -motion.y * sensitivity)
	elif event.is_action_pressed("crouch"):
		_set_crouched(not crouched)
	elif event.is_action_pressed("interact") and focused_interactable:
		focused_interactable.interact(self)


func _physics_process(delta: float) -> void:
	aiming = controls_enabled and Input.is_action_pressed("aim")
	var move := Vector2.ZERO
	if controls_enabled:
		move = Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	_stick_look(delta, move != Vector2.ZERO)
	_edge_turn(delta)

	var speed_scale := (crouch_speed_scale if crouched else 1.0) * (aim_speed_scale if aiming else 1.0)
	var target := global_basis * Vector3(move.x * strafe_speed, 0.0, move.y * run_speed) * speed_scale
	velocity.x = move_toward(velocity.x, target.x, acceleration * delta)
	velocity.z = move_toward(velocity.z, target.z, acceleration * delta)
	if not is_on_floor():
		velocity.y -= gravity * delta
	var before := global_position
	move_and_slide()
	_footsteps(before.distance_to(global_position))

	_update_camera(delta)
	_update_focus()


## Returns [origin, direction] of a shot through the crosshair.
func get_aim_ray() -> Array:
	var size := get_viewport().get_visible_rect().size
	var screen := size * 0.5 + aim_offset * size * 0.5
	return [_camera.project_ray_origin(screen), _camera.project_ray_normal(screen)]


func get_camera() -> Camera3D:
	return _camera


func get_bob_offset() -> Vector2:
	return Vector2(_camera.position.x, _camera.position.y)


func add_recoil(degrees: float) -> void:
	_recoil_pitch += degrees


func take_damage(amount: float, from: Vector3 = Vector3.ZERO) -> void:
	if health <= 0.0:
		return
	var absorbed := minf(armor, amount)
	armor -= absorbed
	health = maxf(health - (amount - absorbed), 0.0)
	Sound.play("player_hurt", null, -2.0)
	health_changed.emit()
	if health <= 0.0:
		controls_enabled = false
		_set_crouched(true)
		died.emit()


func heal_armor(amount: float) -> bool:
	if armor >= MAX_ARMOR:
		return false
	armor = minf(armor + amount, MAX_ARMOR)
	health_changed.emit()
	return true


func _move_crosshair(delta_screen: Vector2) -> void:
	aim_offset += delta_screen
	aim_offset = aim_offset.clamp(Vector2.ONE * -crosshair_limit, Vector2.ONE * crosshair_limit)


func _edge_turn(delta: float) -> void:
	if not aiming:
		aim_offset = aim_offset.move_toward(Vector2.ZERO, 6.0 * delta)
		return
	# Pushing the crosshair against the edge of its box turns the view.
	var edge := crosshair_limit * 0.98
	var turn := Vector2(
		signf(aim_offset.x) if absf(aim_offset.x) >= edge else 0.0,
		signf(aim_offset.y) if absf(aim_offset.y) >= edge else 0.0)
	if turn != Vector2.ZERO:
		_turn(-turn.x * edge_turn_speed * delta, -turn.y * edge_turn_speed * delta)


func _stick_look(delta: float, moving: bool) -> void:
	if not controls_enabled:
		return
	var look := Input.get_vector("look_left", "look_right", "look_up", "look_down")
	if Game.settings.invert_y:
		look.y = -look.y
	if look != Vector2.ZERO:
		_using_stick = true
		var curved := look.normalized() * pow(minf(look.length(), 1.0), stick_curve)
		if aiming:
			_move_crosshair(curved * crosshair_stick_speed * delta)
		else:
			var scale: float = Game.settings.stick_sensitivity
			_turn(-curved.x * stick_yaw_speed * scale * delta, -curved.y * stick_pitch_speed * scale * delta)
	elif _using_stick and moving and not aiming and auto_level_speed > 0.0:
		pitch = move_toward(pitch, 0.0, auto_level_speed * delta)


func _turn(yaw_degrees: float, pitch_degrees: float) -> void:
	rotate_y(deg_to_rad(yaw_degrees))
	pitch = clampf(pitch + pitch_degrees, -max_pitch, max_pitch)


func _set_crouched(value: bool) -> void:
	if not value and not _can_stand():
		return
	crouched = value
	var capsule := _collision.shape as CapsuleShape3D
	capsule.height = CROUCH_CAPSULE_HEIGHT if crouched else STAND_CAPSULE_HEIGHT
	_collision.position.y = capsule.height * 0.5


func _can_stand() -> bool:
	var shape := CapsuleShape3D.new()
	shape.radius = (_collision.shape as CapsuleShape3D).radius * 0.9
	shape.height = STAND_CAPSULE_HEIGHT
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = shape
	query.transform = Transform3D(Basis.IDENTITY, global_position + Vector3.UP * (STAND_CAPSULE_HEIGHT * 0.5 + 0.05))
	query.collision_mask = Layers.WORLD
	return get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty()


func _footsteps(distance: float) -> void:
	if not is_on_floor() or crouched:
		return
	_step_distance += distance
	if _step_distance >= footstep_distance:
		_step_distance = 0.0
		Sound.play("footstep_%d" % randi_range(1, 3), null, -14.0, 0.1)


func _update_camera(delta: float) -> void:
	var target_height := crouch_height if crouched else stand_height
	_head.position.y = move_toward(_head.position.y, target_height, 4.0 * delta)
	_recoil_pitch = move_toward(_recoil_pitch, 0.0, 20.0 * delta)
	_head.rotation.x = deg_to_rad(clampf(pitch + _recoil_pitch, -max_pitch, max_pitch))

	var ground_speed := Vector2(velocity.x, velocity.z).length()
	var bobbing := is_on_floor() and ground_speed > 0.5
	_bob_weight = move_toward(_bob_weight, 1.0 if bobbing else 0.0, 4.0 * delta)
	if bobbing:
		_bob_phase = fmod(_bob_phase + ground_speed * bob_cycles_per_meter * TAU * delta, TAU)
	_camera.position = Vector3(sin(_bob_phase) * 0.5, sin(_bob_phase * 2.0), 0.0) * bob_amount * _bob_weight

	var target_fov := aim_fov if aiming else base_fov
	_camera.fov = lerpf(_camera.fov, target_fov, 1.0 - exp(-12.0 * delta))


func _update_focus() -> void:
	focused_interactable = null
	if not controls_enabled:
		return
	var origin := _camera.global_position
	var query := PhysicsRayQueryParameters3D.create(origin, origin - _camera.global_basis.z * INTERACT_RANGE,
			Layers.WORLD | Layers.INTERACT, [get_rid()])
	query.collide_with_areas = true
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if not hit.is_empty() and hit.collider is Interactable and hit.collider.enabled:
		focused_interactable = hit.collider
