class_name Player
extends CharacterBody3D
## First-person agent controller tuned for a late-90s console feel:
## brisk movement, no jumping, gentle head bob, and a pitch that drifts back to
## level while moving on a controller.

@export_group("Movement")
@export var run_speed := 5.5
@export var strafe_speed := 4.5
@export var crouch_speed_scale := 0.5
@export var aim_speed_scale := 0.5
@export var acceleration := 30.0
@export var gravity := 20.0

@export_group("Look")
@export var mouse_sensitivity := 0.12 ## Degrees per screen pixel.
@export var stick_yaw_speed := 170.0 ## Degrees per second at full deflection.
@export var stick_pitch_speed := 110.0
@export var stick_curve := 2.0 ## Response exponent; higher gives finer control near center.
@export var max_pitch := 70.0
@export var aim_look_scale := 0.4
@export var auto_level_speed := 50.0 ## Degrees per second; 0 disables.

@export_group("Camera")
@export var stand_height := 1.6
@export var crouch_height := 1.0
@export var base_fov := 60.0
@export var aim_fov := 38.0
@export var bob_amount := 0.035
@export var bob_cycles_per_meter := 0.35

var pitch := 0.0
var crouched := false
var aiming := false

var _bob_phase := 0.0
var _bob_weight := 0.0
var _using_stick := false

@onready var _head: Node3D = $Head
@onready var _camera: Camera3D = $Head/Camera


func _ready() -> void:
	_head.position.y = stand_height
	_camera.fov = base_fov


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		_using_stick = false
		var scale := mouse_sensitivity * (aim_look_scale if aiming else 1.0)
		_turn(-event.screen_relative.x * scale, -event.screen_relative.y * scale)
	elif event.is_action_pressed("crouch"):
		crouched = not crouched


func _physics_process(delta: float) -> void:
	aiming = Input.is_action_pressed("aim")
	var move := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	_stick_look(delta, move != Vector2.ZERO)

	var speed_scale := (crouch_speed_scale if crouched else 1.0) * (aim_speed_scale if aiming else 1.0)
	var target := global_basis * Vector3(move.x * strafe_speed, 0.0, move.y * run_speed) * speed_scale
	velocity.x = move_toward(velocity.x, target.x, acceleration * delta)
	velocity.z = move_toward(velocity.z, target.z, acceleration * delta)
	if not is_on_floor():
		velocity.y -= gravity * delta
	move_and_slide()

	_update_camera(delta)


func _stick_look(delta: float, moving: bool) -> void:
	var look := Input.get_vector("look_left", "look_right", "look_up", "look_down")
	if look != Vector2.ZERO:
		_using_stick = true
		var curved := look.normalized() * pow(minf(look.length(), 1.0), stick_curve)
		var scale := aim_look_scale if aiming else 1.0
		_turn(-curved.x * stick_yaw_speed * scale * delta, -curved.y * stick_pitch_speed * scale * delta)
	elif _using_stick and moving and not aiming and auto_level_speed > 0.0:
		pitch = move_toward(pitch, 0.0, auto_level_speed * delta)


func _turn(yaw_degrees: float, pitch_degrees: float) -> void:
	rotate_y(deg_to_rad(yaw_degrees))
	pitch = clampf(pitch + pitch_degrees, -max_pitch, max_pitch)


func _update_camera(delta: float) -> void:
	var target_height := crouch_height if crouched else stand_height
	_head.position.y = move_toward(_head.position.y, target_height, 4.0 * delta)
	_head.rotation.x = deg_to_rad(pitch)

	var ground_speed := Vector2(velocity.x, velocity.z).length()
	var bobbing := is_on_floor() and ground_speed > 0.5
	_bob_weight = move_toward(_bob_weight, 1.0 if bobbing else 0.0, 4.0 * delta)
	if bobbing:
		_bob_phase = fmod(_bob_phase + ground_speed * bob_cycles_per_meter * TAU * delta, TAU)
	_camera.position = Vector3(sin(_bob_phase) * 0.5, sin(_bob_phase * 2.0), 0.0) * bob_amount * _bob_weight

	var target_fov := aim_fov if aiming else base_fov
	_camera.fov = lerpf(_camera.fov, target_fov, 1.0 - exp(-12.0 * delta))
