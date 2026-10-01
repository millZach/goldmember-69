class_name Mission
extends Node3D
## Runs a mission: spawns gameplay from named markers in the level, tracks objectives,
## alarms and stats, and drives the HUD, pause PDA and debrief.
##
## Marker names (Node3D/empties anywhere under the mission; they face -Z):
##   PlayerSpawn, Guard_<NN>_idle, Guard_<NN>_patrol_<Route>, Patrol_<Route>_<NN>,
##   Alarm_<NN>, Obj_AlarmGrid, Obj_DataTap, Obj_Uplink, Exit (scale = half extents),
##   Pickup_<Kind>_<NN> (see Pickup.KINDS).

signal objectives_changed
signal message(text: String)

const GUARD_SCENE := preload("res://guards/guard.tscn")
const ALARM_DURATION := 45.0

## Objectives per mission. "min" is the lowest difficulty that includes it. "keep"
## objectives start complete and fail if their condition is broken.
const OBJECTIVES := {
	"spillway": [
		{"id": "alarm_grid", "text": "Disable the alarm grid", "min": 0},
		{"id": "uplink", "text": "Destroy the relay uplink", "min": 0},
		{"id": "data_tap", "text": "Plant a data tap in the control room", "min": 1},
		{"id": "no_alarm", "text": "Do not allow the alarm to be raised", "min": 2, "keep": true},
	],
}

@export var mission_id := "spillway"
@export var music := "spillway"

var objectives: Array[Dictionary] = []
var elapsed := 0.0
var shots := 0
var hits := 0
var kills := 0
var headshots := 0
var ended := false
var alarm_grid_disabled := false
var alarm_active := false

var player: Player
var hud: Hud
var _alarm_runner: Guard
var _alarm_left := 0.0
var _siren: AudioStreamPlayer
var _last_sting := -100.0
var _markers := {}


static func find(node: Node) -> Mission:
	if node == null or not node.is_inside_tree():
		return null
	return node.get_tree().current_scene as Mission


func _ready() -> void:
	if Game.current_mission.is_empty():
		Game.current_mission = Game.mission_by_id(mission_id)
	_setup_objectives()
	_bake_navigation()
	_collect_markers()
	player = get_tree().get_first_node_in_group("player") as Player
	if player == null:
		player = $Player
	player.died.connect(func(): fail("Agent down"))
	_place_player()
	_spawn_guards()
	_spawn_alarms()
	_spawn_objectives()
	_spawn_pickups()
	_spawn_exit()
	player.weapons.give_weapon("p9", 27)

	hud = Hud.new()
	add_child(hud)
	hud.bind(self)
	add_child(Pda.new())
	Sound.play_music(music)
	Game.in_gameplay = true
	Game.set_mouse_captured(true)


func _process(delta: float) -> void:
	if ended:
		return
	elapsed += delta
	if alarm_active:
		_alarm_left -= delta
		if _alarm_left <= 0.0:
			_stop_siren()


# --- Objectives --------------------------------------------------------------

func _setup_objectives() -> void:
	for definition in OBJECTIVES.get(mission_id, []):
		if Game.difficulty >= definition.min:
			var objective: Dictionary = definition.duplicate()
			objective.state = "complete" if objective.get("keep", false) else "pending"
			objectives.append(objective)


func has_objective(id: String) -> bool:
	return objectives.any(func(o): return o.id == id)


func complete_objective(id: String) -> void:
	for objective in objectives:
		if objective.id == id and objective.state == "pending":
			objective.state = "complete"
			Sound.play("objective_complete")
			show_message("Objective complete: " + objective.text)
			objectives_changed.emit()


func fail_objective(id: String) -> void:
	for objective in objectives:
		if objective.id == id and objective.state != "failed":
			objective.state = "failed"
			show_message("Objective failed: " + objective.text)
			objectives_changed.emit()
			fail("Objective failed")


func all_objectives_complete() -> bool:
	return objectives.all(func(o): return o.state == "complete")


# --- Alarm -------------------------------------------------------------------

func alarms_enabled() -> bool:
	return not alarm_grid_disabled and not alarm_active and not ended


## Picks this guard to run for the alarm if nobody else is and an alarm is near.
func request_alarm_runner(guard: Guard) -> AlarmPanel:
	if not alarms_enabled():
		return null
	if is_instance_valid(_alarm_runner) and _alarm_runner.is_alive():
		return null
	var best: AlarmPanel
	var best_distance := 45.0
	for alarm in get_tree().get_nodes_in_group("alarms"):
		var distance: float = guard.global_position.distance_to(alarm.global_position)
		if alarm.usable() and distance < best_distance:
			best = alarm
			best_distance = distance
	if best:
		_alarm_runner = guard
	return best


func raise_alarm(panel: AlarmPanel) -> void:
	if not alarms_enabled():
		return
	alarm_active = true
	_alarm_left = ALARM_DURATION
	panel.sounding = true
	_siren = Sound.make_loop("alarm_siren", self, -6.0)
	if _siren:
		_siren.play()
	show_message("ALARM RAISED")
	for guard in get_tree().get_nodes_in_group("guards"):
		guard.alert(player.global_position)
	if has_objective("no_alarm"):
		fail_objective("no_alarm")


func _stop_siren() -> void:
	if _siren:
		_siren.queue_free()
		_siren = null
	for alarm in get_tree().get_nodes_in_group("alarms"):
		alarm.sounding = false


# --- Noise, stats, messages --------------------------------------------------

func emit_noise(at: Vector3, radius: float, source: Node) -> void:
	for guard in get_tree().get_nodes_in_group("guards"):
		guard.hear_noise(at, radius, source)


func on_guard_spotted_player(_guard: Guard) -> void:
	if elapsed - _last_sting > 20.0:
		_last_sting = elapsed
		Sound.play("alert_sting", null, -4.0, 0.0)


func record_shot(hit: bool) -> void:
	shots += 1
	if hit:
		hits += 1


func record_kill(headshot: bool) -> void:
	kills += 1
	if headshot:
		headshots += 1


func show_message(text: String) -> void:
	message.emit(text)


# --- Ending ------------------------------------------------------------------

func complete() -> void:
	if ended:
		return
	ended = true
	_stop_siren()
	Sound.stop_music()
	Sound.play_music("mission_complete", false)
	_show_debrief(true, "")


func fail(reason: String) -> void:
	if ended:
		return
	ended = true
	_stop_siren()
	Sound.stop_music()
	Sound.play_music("mission_failed", false)
	_show_debrief(false, reason)


func _show_debrief(success: bool, reason: String) -> void:
	player.controls_enabled = false
	await get_tree().create_timer(1.5).timeout
	get_tree().paused = true
	Game.in_gameplay = false
	Game.set_mouse_captured(false)
	var debrief := Debrief.new()
	add_child(debrief)
	debrief.show_result(self, success, reason)


# --- Spawning ----------------------------------------------------------------

func _bake_navigation() -> void:
	var region := get_node_or_null("NavRegion") as NavigationRegion3D
	if region:
		region.bake_navigation_mesh(false)


func _collect_markers() -> void:
	for node in find_children("*", "Node3D", true, false):
		var marker_name := String(node.name)
		for prefix in ["PlayerSpawn", "Guard_", "Patrol_", "Alarm_", "Obj_", "Exit", "Pickup_"]:
			if marker_name.begins_with(prefix):
				_markers[marker_name] = node
				break


func _markers_with_prefix(prefix: String) -> Array:
	var names := _markers.keys().filter(func(n): return n.begins_with(prefix))
	names.sort()
	return names.map(func(n): return _markers[n])


func _place_player() -> void:
	var spawn: Node3D = _markers.get("PlayerSpawn")
	if spawn:
		player.global_position = spawn.global_position
		var forward := -spawn.global_basis.z
		player.rotation.y = atan2(-forward.x, -forward.z)
	var pose := Game.debug_pose
	if pose.size() >= 4:
		player.global_position = Vector3(pose[0], pose[1], pose[2])
		player.rotation.y = deg_to_rad(pose[3])
		if pose.size() >= 5:
			player.pitch = pose[4]
		Game.debug_pose = PackedFloat32Array()


func _spawn_guards() -> void:
	var index := 0
	for marker in _markers_with_prefix("Guard_"):
		var parts := String(marker.name).split("_")
		var guard: Guard = GUARD_SCENE.instantiate()
		guard.weapon_id = "p9" if index % 3 == 2 else "vk12"
		if parts.size() >= 4 and parts[2] == "patrol":
			var points := PackedVector3Array()
			for point in _markers_with_prefix("Patrol_%s_" % parts[3]):
				points.append(point.global_position)
			guard.patrol_points = points
		add_child(guard)
		guard.global_position = marker.global_position
		var forward: Vector3 = -marker.global_basis.z
		guard.rotation.y = atan2(-forward.x, -forward.z)
		index += 1


func _spawn_alarms() -> void:
	for marker in _markers_with_prefix("Alarm_"):
		var panel := AlarmPanel.new()
		add_child(panel)
		panel.global_transform = _upright(marker)


func _spawn_objectives() -> void:
	var grid: Node3D = _markers.get("Obj_AlarmGrid")
	if grid:
		var breaker := ObjectiveProps.breaker(self, _upright(grid))
		breaker.used.connect(func(_p):
			breaker.enabled = false
			alarm_grid_disabled = true
			_stop_siren()
			show_message("Alarm grid disabled")
			complete_objective("alarm_grid"))

	var tap: Node3D = _markers.get("Obj_DataTap")
	if tap and has_objective("data_tap"):
		var terminal := ObjectiveProps.data_tap_spot(self, _upright(tap))
		terminal.used.connect(func(_p):
			terminal.enabled = false
			ObjectiveProps.place_data_tap(self, _upright(tap))
			complete_objective("data_tap"))

	var uplink: Node3D = _markers.get("Obj_Uplink")
	if uplink:
		var mast := ObjectiveProps.uplink_spot(self, _upright(uplink))
		mast.used.connect(func(_p):
			mast.enabled = false
			show_message("Charge planted")
			ObjectiveProps.plant_charge(self, _upright(uplink), _on_uplink_destroyed))


func _on_uplink_destroyed(at: Vector3) -> void:
	emit_noise(at, 60.0, player)
	_blast_damage(at, 6.0, 90.0)
	var dish := find_child("Uplink_Dish", true, false) as Node3D
	if dish:
		var tween := create_tween()
		tween.tween_property(dish, "rotation:x", dish.rotation.x + deg_to_rad(80), 1.4) \
				.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	complete_objective("uplink")


func _blast_damage(at: Vector3, radius: float, damage: float) -> void:
	var to_player := player.global_position.distance_to(at)
	if to_player < radius:
		player.take_damage(damage * (1.0 - to_player / radius), at)
	for guard in get_tree().get_nodes_in_group("guards"):
		var distance: float = guard.global_position.distance_to(at)
		if distance < radius:
			guard.take_hit(damage * 2.0 * (1.0 - distance / radius), guard.global_position + Vector3.UP, Vector3.ZERO, null)


func _spawn_pickups() -> void:
	for marker in _markers_with_prefix("Pickup_"):
		var kind := String(marker.name).split("_")[1]
		Pickup.create(self, kind, marker.global_position)


func _spawn_exit() -> void:
	var marker: Node3D = _markers.get("Exit")
	if marker == null:
		return
	var area := Area3D.new()
	area.collision_layer = 0
	area.collision_mask = Layers.PLAYER
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	(shape.shape as BoxShape3D).size = marker.global_basis.get_scale().abs() * 2.0
	area.add_child(shape)
	add_child(area)
	area.global_position = marker.global_position
	area.body_entered.connect(func(body):
		if body != player or ended:
			return
		if all_objectives_complete():
			complete()
		else:
			show_message("Objectives incomplete"))


## Marker transform without scale, kept upright.
func _upright(marker: Node3D) -> Transform3D:
	var forward := -marker.global_basis.z
	forward.y = 0.0
	if forward.length_squared() < 0.001:
		forward = Vector3.FORWARD
	return Transform3D(Basis.looking_at(forward.normalized(), Vector3.UP), marker.global_position)
