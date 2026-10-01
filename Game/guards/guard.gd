class_name Guard
extends CharacterBody3D
## Enemy guard: idles or patrols, notices the player by sight or sound, fights,
## runs for the nearest alarm, and reacts to where it is hit.

signal died(guard: Guard)

enum State { IDLE, PATROL, INVESTIGATE, COMBAT, RUN_TO_ALARM, DEAD }

const MODEL_PATH := "res://assets/characters/guard.glb"
const WALK_SPEED := 1.6
const RUN_SPEED := 4.2
const SIGHT_RANGE := 26.0
const SIGHT_HALF_ANGLE := 55.0
const HEAD_HEIGHT := 1.6
const CHEST_HEIGHT := 1.25
const ALERT_RADIUS := 14.0
const ZONE_MULTIPLIER := {"head": 4.0, "torso": 1.0, "arm": 0.6, "leg": 0.7}
const STAGGER_TIME := {"head": 0.5, "torso": 0.35, "arm": 0.3, "leg": 0.7}
const WEAPON_TIMING := {
	"vk12": {"interval": 0.11, "burst": Vector2i(3, 6), "pause": Vector2(0.7, 1.3)},
	"p9": {"interval": 0.45, "burst": Vector2i(1, 3), "pause": Vector2(0.6, 1.1)},
}

@export var weapon_id := "vk12"
@export var patrol_points := PackedVector3Array()

var state := State.IDLE
var health := 100.0
var awareness := 0.0

var _player: Player
var _tuning: Dictionary
var _home_position: Vector3
var _home_facing: Vector3
var _last_seen := Vector3.ZERO
var _has_los := false
var _time_without_los := 0.0
var _patrol_index := 0
var _wait := 0.0
var _reaction := 0.0
var _burst_left := 0
var _fire_cooldown := 0.0
var _stagger := 0.0
var _think := 0.0
var _strafe_timer := 2.0
var _strafe_target := Vector3.INF
var _investigate_target := Vector3.ZERO
var _look_around := 0.0
var _alarm: AlarmPanel
var _alarm_time := 0.0

@onready var _nav: NavigationAgent3D = $Nav
@onready var _animator: GuardAnimator = $Animator


func _ready() -> void:
	add_to_group("guards")
	collision_layer = Layers.GUARDS
	collision_mask = Layers.WORLD | Layers.PLAYER
	_tuning = Game.tuning()
	health = 100.0 * _tuning.guard_health
	_home_position = global_position
	_home_facing = -global_basis.z
	_think = randf() * 0.1
	var model: Node3D
	if ResourceLoader.exists(MODEL_PATH):
		model = load(MODEL_PATH).instantiate()
	else:
		model = _placeholder_model()
	model.name = "Model"
	add_child(model)
	_animator.setup(model, weapon_id)
	state = State.PATROL if patrol_points.size() >= 2 else State.IDLE


func is_alive() -> bool:
	return state != State.DEAD


func _physics_process(delta: float) -> void:
	if state == State.DEAD:
		_animator.update(delta, 0.0, false)
		return
	if _player == null or not is_instance_valid(_player):
		_player = get_tree().get_first_node_in_group("player") as Player

	_think -= delta
	if _think <= 0.0:
		_think = 0.1
		_perceive(0.1)

	_stagger = maxf(_stagger - delta, 0.0)
	_fire_cooldown -= delta
	var desired := Vector3.ZERO
	match state:
		State.IDLE:
			desired = _do_idle(delta)
		State.PATROL:
			desired = _do_patrol(delta)
		State.INVESTIGATE:
			desired = _do_investigate(delta)
		State.COMBAT:
			desired = _do_combat(delta)
		State.RUN_TO_ALARM:
			desired = _do_run_to_alarm(delta)
	if _stagger > 0.0:
		desired *= 0.2

	velocity.x = desired.x
	velocity.z = desired.z
	velocity.y = 0.0 if is_on_floor() else velocity.y - 20.0 * delta
	move_and_slide()
	var aiming := state == State.COMBAT and _has_los
	_animator.update(delta, Vector2(velocity.x, velocity.z).length(), aiming)


# --- Perception --------------------------------------------------------------

func _perceive(step: float) -> void:
	_has_los = _player != null and _player.health > 0.0 and _can_see_player()
	if state == State.COMBAT or state == State.RUN_TO_ALARM:
		if _has_los:
			_last_seen = _player.global_position
		return
	if _has_los:
		var distance := global_position.distance_to(_player.global_position)
		awareness += step / maxf(0.12, distance * 0.05)
		if awareness >= 1.0:
			_last_seen = _player.global_position
			enter_combat()
	else:
		awareness = maxf(awareness - step * 0.3, 0.0)


func _can_see_player() -> bool:
	var eye := global_position + Vector3.UP * HEAD_HEIGHT
	var target := _player.get_camera().global_position
	var to_target := target - eye
	var sight_range := SIGHT_RANGE * (0.75 if _player.crouched else 1.0)
	if to_target.length() > sight_range:
		return false
	if state != State.COMBAT:
		var flat := Vector3(to_target.x, 0, to_target.z).normalized()
		if (-global_basis.z).angle_to(flat) > deg_to_rad(SIGHT_HALF_ANGLE):
			return false
	var query := PhysicsRayQueryParameters3D.create(eye, target, Layers.WORLD)
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()


## Called by the mission for gunshots and other loud noises.
func hear_noise(at: Vector3, radius: float, source: Node) -> void:
	if state == State.DEAD or source == self:
		return
	if global_position.distance_to(at) > radius:
		return
	if state == State.COMBAT or state == State.RUN_TO_ALARM:
		return
	if source is Guard or source is Player:
		# Gunfire nearby: assume the worst and head for it.
		awareness = maxf(awareness, 0.6)
		_investigate(at if source is Player else (source as Node3D).global_position)


## Another guard (or the alarm) has told us where the player is.
func alert(player_position: Vector3) -> void:
	if state == State.DEAD or state == State.COMBAT or state == State.RUN_TO_ALARM:
		return
	_last_seen = player_position
	enter_combat(false)


func enter_combat(notify := true) -> void:
	if state == State.DEAD:
		return
	awareness = 1.0
	state = State.COMBAT
	_reaction = _tuning.reaction_time
	_time_without_los = 0.0
	var mission := Mission.find(self)
	if mission == null or not notify:
		return
	mission.on_guard_spotted_player(self)
	for node in get_tree().get_nodes_in_group("guards"):
		if node != self and global_position.distance_to(node.global_position) < ALERT_RADIUS:
			node.alert(_last_seen)
	_alarm = mission.request_alarm_runner(self)
	if _alarm:
		state = State.RUN_TO_ALARM
		_alarm_time = 0.0


# --- States ------------------------------------------------------------------

func _do_idle(delta: float) -> Vector3:
	if global_position.distance_to(_home_position) > 0.8:
		return _move_to(_home_position, WALK_SPEED)
	_face(global_position + _home_facing, delta, 3.0)
	return Vector3.ZERO


func _do_patrol(delta: float) -> Vector3:
	if _wait > 0.0:
		_wait -= delta
		return Vector3.ZERO
	var target := patrol_points[_patrol_index]
	if Vector2(target.x - global_position.x, target.z - global_position.z).length() < 0.7:
		_patrol_index = (_patrol_index + 1) % patrol_points.size()
		_wait = randf_range(0.8, 2.0)
		return Vector3.ZERO
	return _move_to(target, WALK_SPEED)


func _investigate(at: Vector3) -> void:
	state = State.INVESTIGATE
	_investigate_target = at
	_look_around = 0.0


func _do_investigate(delta: float) -> Vector3:
	if global_position.distance_to(_investigate_target) > 1.5 and _look_around == 0.0:
		return _move_to(_investigate_target, RUN_SPEED * 0.7)
	_look_around += delta
	rotate_y(delta * 1.2)
	if _look_around > 4.0:
		awareness = 0.3
		state = State.PATROL if patrol_points.size() >= 2 else State.IDLE
	return Vector3.ZERO


func _do_combat(delta: float) -> Vector3:
	if _player == null or _player.health <= 0.0:
		return Vector3.ZERO
	if not _has_los:
		_time_without_los += delta
		_reaction = maxf(_reaction, _tuning.reaction_time * 0.5)
		if _time_without_los > 8.0:
			_investigate(_last_seen)
			return Vector3.ZERO
		if global_position.distance_to(_last_seen) > 1.2:
			return _move_to(_last_seen, RUN_SPEED)
		rotate_y(delta * 1.5)
		return Vector3.ZERO

	_time_without_los = 0.0
	_face(_player.global_position, delta, 8.0)
	var distance := global_position.distance_to(_player.global_position)

	_reaction -= delta
	if _reaction <= 0.0 and _stagger <= 0.0:
		_update_firing()

	if distance > 16.0:
		return _move_to(_player.global_position, RUN_SPEED * 0.8)
	_strafe_timer -= delta
	if _strafe_timer <= 0.0:
		_strafe_timer = randf_range(2.5, 4.5)
		var side := global_basis.x * (1.0 if randf() < 0.5 else -1.0) * randf_range(1.5, 2.5)
		_strafe_target = NavigationServer3D.map_get_closest_point(get_world_3d().navigation_map, global_position + side)
	if _strafe_target != Vector3.INF:
		if global_position.distance_to(_strafe_target) < 0.4:
			_strafe_target = Vector3.INF
		else:
			var to := _strafe_target - global_position
			return Vector3(to.x, 0, to.z).normalized() * 2.6
	return Vector3.ZERO


func _do_run_to_alarm(delta: float) -> Vector3:
	var mission := Mission.find(self)
	if _alarm == null or not _alarm.usable() or mission == null or not mission.alarms_enabled():
		state = State.COMBAT
		return Vector3.ZERO
	var target := _alarm.approach_point()
	if Vector2(target.x - global_position.x, target.z - global_position.z).length() > 0.6:
		return _move_to(target, RUN_SPEED)
	_face(_alarm.global_position, delta, 8.0)
	_alarm_time += delta
	if _alarm_time > 1.2:
		mission.raise_alarm(_alarm)
		state = State.COMBAT
	return Vector3.ZERO


# --- Combat ------------------------------------------------------------------

func _update_firing() -> void:
	var timing: Dictionary = WEAPON_TIMING.get(weapon_id, WEAPON_TIMING.vk12)
	if _fire_cooldown > 0.0:
		return
	if _burst_left <= 0:
		_burst_left = randi_range(timing.burst.x, timing.burst.y)
		_fire_cooldown = randf_range(timing.pause.x, timing.pause.y)
		return
	_burst_left -= 1
	_fire_cooldown = timing.interval
	_shoot()


func _shoot() -> void:
	var muzzle := _animator.muzzle_position()
	_animator.flash()
	Sound.play(Weapons.DATA[weapon_id].sound, muzzle, -2.0)
	var mission := Mission.find(self)
	if mission:
		mission.emit_noise(global_position, 25.0, self)

	var distance := global_position.distance_to(_player.global_position)
	var chance: float = _tuning.guard_accuracy * clampf(1.4 - distance / 25.0, 0.25, 1.2)
	if Vector2(_player.velocity.x, _player.velocity.z).length() > 3.0:
		chance *= 0.65
	if _player.crouched:
		chance *= 0.8
	if randf() < chance:
		_player.take_damage(_tuning.guard_damage, global_position)
		return
	# Miss: kick up a puff near the player.
	var target := _player.get_camera().global_position + Vector3(randf_range(-1, 1), randf_range(-1.2, 0.3), randf_range(-1, 1))
	var dir := (target - muzzle).normalized()
	var query := PhysicsRayQueryParameters3D.create(muzzle, muzzle + dir * 60.0, Layers.WORLD)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if not hit.is_empty():
		Effects.bullet_hole(hit.position, hit.normal)
		Effects.puff(hit.position + hit.normal * 0.05)
		Sound.play("impact_concrete", hit.position, -8.0, 0.2)


## Returns true if the hit killed the guard.
func take_hit(damage: float, at: Vector3, _direction: Vector3, attacker: Node3D) -> bool:
	if state == State.DEAD:
		return false
	var zone := hit_zone(at)
	health -= damage * ZONE_MULTIPLIER[zone]
	Sound.play("impact_flesh", at, -2.0)
	Effects.puff(at, "hit_puff")
	var mission := Mission.find(self)
	if health <= 0.0:
		_die(zone)
		if mission:
			mission.record_kill(zone == "head")
		return true
	_stagger = STAGGER_TIME[zone]
	_animator.flinch(zone)
	if attacker:
		_last_seen = attacker.global_position
	if state != State.COMBAT and state != State.RUN_TO_ALARM:
		enter_combat()
	return false


## Which body part a world-space point on the guard corresponds to.
func hit_zone(at: Vector3) -> String:
	var local := to_local(at)
	if local.y > 1.5:
		return "head"
	if local.y > 0.95:
		return "arm" if absf(local.x) > 0.19 else "torso"
	return "leg"


func _die(zone: String) -> void:
	state = State.DEAD
	remove_from_group("guards")
	collision_layer = 0
	collision_mask = Layers.WORLD
	velocity = Vector3.ZERO
	_animator.die(zone)
	get_tree().create_timer(0.55).timeout.connect(func(): Sound.play("guard_death", global_position, -3.0))
	if _animator.weapon:
		_animator.weapon.visible = false
	var drop_kind: String = {"vk12": "WeaponVK12", "p9": "WeaponP9", "talon12": "WeaponTalon12"}.get(weapon_id, "")
	if drop_kind != "":
		var drop_at := global_position + global_basis.x * 0.6 + Vector3.UP * 0.05
		Pickup.create(get_parent(), drop_kind, drop_at, Weapons.PICKUP_AMMO[weapon_id] / 2)
	died.emit(self)


# --- Movement helpers --------------------------------------------------------

func _move_to(target: Vector3, speed: float) -> Vector3:
	_nav.target_position = target
	var next := _nav.get_next_path_position()
	if _nav.is_navigation_finished():
		next = target
	var to := next - global_position
	to.y = 0.0
	if to.length() < 0.05:
		return Vector3.ZERO
	var direction := to.normalized()
	if state != State.COMBAT or not _has_los:
		_face(global_position + direction, get_physics_process_delta_time(), 6.0)
	return direction * speed


func _face(point: Vector3, delta: float, turn_speed: float) -> void:
	var to := point - global_position
	to.y = 0.0
	if to.length_squared() < 0.0001:
		return
	var target_yaw := atan2(-to.x, -to.z)
	rotation.y = lerp_angle(rotation.y, target_yaw, 1.0 - exp(-turn_speed * delta))


func _placeholder_model() -> Node3D:
	var mesh := MeshInstance3D.new()
	mesh.mesh = CapsuleMesh.new()
	mesh.position.y = 0.9
	var root := Node3D.new()
	root.add_child(mesh)
	return root
