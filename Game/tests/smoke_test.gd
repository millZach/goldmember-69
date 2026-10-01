extends Node
## Headless gameplay smoke test. Run:
##   godot --headless --path Game res://tests/smoke_test.tscn -- --mission-scene=<path>
## Exits with code 0 on success, 1 on failure.

var _failures: Array[String] = []


func _ready() -> void:
	_run.call_deferred()


func _run() -> void:
	var scene_path := "res://levels/test_room/test_room.tscn"
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--mission-scene="):
			scene_path = arg.trim_prefix("--mission-scene=")
		elif arg.begins_with("--difficulty="):
			Game.difficulty = arg.trim_prefix("--difficulty=").to_int() as Game.Difficulty
	# Add the mission beside this node (changing scenes would free the test itself).
	var instance: Node = load(scene_path).instantiate()
	get_tree().root.add_child(instance)
	get_tree().current_scene = instance
	await _frames(10)
	var mission := get_tree().current_scene as Mission
	_check(mission != null, "scene root is a Mission")
	if mission == null:
		return _finish()

	var guards := get_tree().get_nodes_in_group("guards")
	print("guards: %d, alarms: %d, objectives: %d" % [guards.size(), get_tree().get_nodes_in_group("alarms").size(), mission.objectives.size()])
	_check(guards.size() > 0, "guards spawned")
	var player := mission.player
	_check(player.weapons.current == "p9", "player starts with the P9")

	# Navigation: a path from the first guard to the player should exist.
	await _physics(5)
	var map := player.get_world_3d().navigation_map
	var guard: Guard = guards[0]
	var path := NavigationServer3D.map_get_path(map, guard.global_position, player.global_position, true)
	print("nav path points guard->player: %d" % path.size())
	_check(path.size() > 1, "navmesh path exists")

	# Put the player 6 m in front of a guard, facing it, and let the guard react.
	var forward := -guard.global_basis.z
	player.global_position = guard.global_position + forward * 6.0
	player.look_at(guard.global_position, Vector3.UP)
	player.rotation.x = 0.0
	player.rotation.z = 0.0
	player.pitch = 0.0
	await _physics(180)
	print("guard state after 3s: %s, player health %.0f" % [Guard.State.keys()[guard.state], player.health])
	_check(guard.state == Guard.State.COMBAT or guard.state == Guard.State.RUN_TO_ALARM, "guard noticed the player")

	# Aim at the guard's chest and fire until it drops.
	var shots := 0
	while guard.is_alive() and shots < 20:
		if not guard.is_alive():
			break
		var chest := guard.global_position + Vector3.UP * Guard.CHEST_HEIGHT
		var cam := player.get_camera()
		player.look_at(Vector3(chest.x, player.global_position.y, chest.z), Vector3.UP)
		player.rotation.x = 0.0
		var to := chest - cam.global_position
		player.pitch = rad_to_deg(atan2(to.y, Vector2(to.x, to.z).length()))
		await _physics(2)
		player.weapons.call("_fire")
		shots += 1
		await _physics(20)
	print("shots fired: %d, guard alive: %s, kills: %d" % [shots, guard.is_alive(), mission.kills])
	_check(not guard.is_alive(), "player killed the guard")
	await _physics(10)
	var drops := get_tree().current_scene.find_children("*", "Pickup", true, false).size()
	print("pickups in scene: %d" % drops)
	if not mission.objectives.is_empty():
		await _play_objectives(mission)
	_finish()


## Use every interactable, wait for the charge to blow, then walk into the exit.
func _play_objectives(mission: Mission) -> void:
	var player := mission.player
	player.health = 10000.0 # Keep the remaining guards from ending the run.
	for area in mission.find_children("*", "Interactable", true, false):
		print("using: %s" % area.prompt)
		area.interact(player)
	await _physics(420)
	for objective in mission.objectives:
		print("objective %s: %s" % [objective.id, objective.state])
	_check(mission.all_objectives_complete(), "all objectives complete")
	var exit := mission.find_child("Exit", true, false) as Node3D
	_check(exit != null, "exit marker found")
	if exit:
		player.global_position = exit.global_position
		await _physics(10)
	_check(mission.ended, "mission ended at the exit")


func _check(condition: bool, label: String) -> void:
	print(("PASS " if condition else "FAIL ") + label)
	if not condition:
		_failures.append(label)


func _finish() -> void:
	print("RESULT: %s" % ("OK" if _failures.is_empty() else "FAILED: " + ", ".join(_failures)))
	get_tree().quit(0 if _failures.is_empty() else 1)


func _frames(count: int) -> void:
	for i in count:
		await get_tree().process_frame


func _physics(count: int) -> void:
	for i in count:
		await get_tree().physics_frame
