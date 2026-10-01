class_name WeaponManager
extends Node
## The player's arsenal: inventory and ammo, switching, reloading, hitscan firing with
## auto-aim, and the first-person viewmodel (rendered in its own viewport so it never
## clips into walls).

signal changed

const AUTO_AIM_ANGLE := 7.0 ## Degrees from the aim direction within which shots snap to a guard.
const SWITCH_TIME := 0.25
const VIEW_FOV := 60.0

var owned: Dictionary = {} ## weapon id -> {"mag": int, "reserve": int}
var current := ""

var _player: Player
var _cooldown := 0.0
var _reload_left := 0.0
var _switch_left := 0.0
var _pending_switch := ""
var _trigger_was_down := false
var _pump_left := 0.0

var _view_models := {}
var _flashes := {}
var _flash_left := 0.0
var _pivot: Node3D
var _view_camera: Camera3D
var _recoil := 0.0


func _ready() -> void:
	_player = get_parent() as Player
	_build_viewmodel_viewport()


## Give a weapon, or ammo for it if already owned. Returns true if anything was taken.
func give_weapon(id: String, ammo: int = -1) -> bool:
	if ammo < 0:
		ammo = Weapons.PICKUP_AMMO[id]
	if owned.has(id):
		return add_ammo(id, ammo)
	var data: Dictionary = Weapons.DATA[id]
	var in_mag := mini(ammo, data.mag)
	owned[id] = {"mag": in_mag, "reserve": mini(ammo - in_mag, data.max_reserve)}
	_add_view_model(id)
	switch_to(id)
	return true


func add_ammo(id: String, amount: int) -> bool:
	if not owned.has(id):
		return false
	var slot: Dictionary = owned[id]
	var max_reserve: int = Weapons.DATA[id].max_reserve
	if slot.reserve >= max_reserve:
		return false
	slot.reserve = mini(slot.reserve + amount, max_reserve)
	changed.emit()
	return true


func switch_to(id: String) -> void:
	if id == current or not owned.has(id):
		return
	if current == "":
		_equip(id)
		return
	_pending_switch = id
	_switch_left = SWITCH_TIME * 2.0
	_reload_left = 0.0
	Sound.play("weapon_switch")


func cycle(step: int) -> void:
	if owned.size() < 2:
		return
	var index := Weapons.ORDER.find(_pending_switch if _pending_switch != "" else current)
	for i in Weapons.ORDER.size():
		index = wrapi(index + step, 0, Weapons.ORDER.size())
		if owned.has(Weapons.ORDER[index]):
			switch_to(Weapons.ORDER[index])
			return


func current_data() -> Dictionary:
	return Weapons.DATA.get(current, {})


func current_slot() -> Dictionary:
	return owned.get(current, {})


func is_reloading() -> bool:
	return _reload_left > 0.0


func _physics_process(delta: float) -> void:
	_cooldown -= delta
	_update_switch(delta)
	_update_reload(delta)
	_update_pump(delta)

	if not _player.controls_enabled or current == "":
		_trigger_was_down = false
		return
	if Input.is_action_just_pressed("next_weapon"):
		cycle(1)
	elif Input.is_action_just_pressed("prev_weapon"):
		cycle(-1)
	elif Input.is_action_just_pressed("reload"):
		_start_reload()

	var trigger := Input.is_action_pressed("fire")
	var data := current_data()
	if trigger and (data.automatic or not _trigger_was_down):
		if is_reloading() and data.get("reload_per_round", false) and current_slot().mag > 0:
			_reload_left = 0.0 # Shotgun reloads can be interrupted to fire.
		if _cooldown <= 0.0 and _switch_left <= 0.0 and not is_reloading():
			_fire()
	_trigger_was_down = trigger


func _process(delta: float) -> void:
	_update_viewmodel(delta)


func _fire() -> void:
	var data := current_data()
	var slot := current_slot()
	if slot.mag <= 0:
		Sound.play("dry_fire")
		_cooldown = 0.3
		if slot.reserve > 0:
			_start_reload()
		return
	slot.mag -= 1
	_cooldown = data.fire_interval
	_recoil = 1.0
	_flash_left = 0.05
	_player.add_recoil(data.recoil)
	Sound.play(data.sound, null, 0.0, 0.04)
	var mission := Mission.find(self)
	if mission:
		mission.emit_noise(_player.global_position, data.noise_radius, _player)
	if data.has("pump_sound"):
		_pump_left = 0.3

	var ray := _player.get_aim_ray()
	var origin: Vector3 = ray[0]
	var direction: Vector3 = ray[1]
	if not _player.aiming:
		direction = _auto_aim(origin, direction, data.range)

	var hit_guard := false
	var impact_sound_played := false
	for pellet in data.pellets:
		var spread_dir := _apply_spread(direction, data.spread)
		var result := _raycast(origin, origin + spread_dir * data.range)
		if result.is_empty():
			continue
		var collider: Object = result.collider
		if collider is Guard:
			(collider as Guard).take_hit(data.damage, result.position, spread_dir, _player)
			hit_guard = true
			continue
		var handler := _find_shot_handler(collider)
		if handler:
			handler.on_shot(data.damage, result.position)
		Effects.bullet_hole(result.position, result.normal)
		Effects.puff(result.position + result.normal * 0.05)
		if not impact_sound_played:
			Sound.play("impact_metal" if handler else "impact_concrete", result.position, -6.0, 0.15)
			impact_sound_played = true
	if mission:
		mission.record_shot(hit_guard)
	changed.emit()
	if slot.mag == 0 and slot.reserve > 0:
		_start_reload.call_deferred()


func _auto_aim(origin: Vector3, direction: Vector3, max_range: float) -> Vector3:
	# If the shot already lands on a guard, respect the player's aim (headshots).
	var direct := _raycast(origin, origin + direction * max_range)
	if not direct.is_empty() and direct.collider is Guard:
		return direction
	var best_angle := deg_to_rad(AUTO_AIM_ANGLE)
	var best := direction
	for node in get_tree().get_nodes_in_group("guards"):
		var guard := node as Guard
		if not guard.is_alive():
			continue
		var target := guard.global_position + Vector3.UP * Guard.CHEST_HEIGHT
		var to_target := target - origin
		if to_target.length() > max_range:
			continue
		var angle := direction.angle_to(to_target.normalized())
		if angle >= best_angle:
			continue
		var los := _raycast(origin, target)
		if not los.is_empty() and los.collider == guard:
			best_angle = angle
			best = to_target.normalized()
	return best


func _apply_spread(direction: Vector3, degrees: float) -> Vector3:
	if degrees <= 0.0:
		return direction
	var side := direction.cross(Vector3.UP).normalized()
	if side.is_zero_approx():
		side = Vector3.RIGHT
	var up := side.cross(direction).normalized()
	var radius := tan(deg_to_rad(degrees)) * sqrt(randf())
	var angle := randf() * TAU
	return (direction + (side * cos(angle) + up * sin(angle)) * radius).normalized()


func _raycast(from: Vector3, to: Vector3) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(from, to, Layers.SHOT_MASK, [_player.get_rid()])
	return _player.get_world_3d().direct_space_state.intersect_ray(query)


func _find_shot_handler(collider: Object) -> Node:
	var node := collider as Node
	for i in 3:
		if node == null:
			return null
		if node.has_method("on_shot"):
			return node
		node = node.get_parent()
	return null


func _start_reload() -> void:
	var slot := current_slot()
	var data := current_data()
	if slot.is_empty() or is_reloading() or slot.mag >= data.mag or slot.reserve <= 0:
		return
	_reload_left = data.reload_time
	Sound.play("reload")


func _update_reload(delta: float) -> void:
	if not is_reloading():
		return
	_reload_left -= delta
	if _reload_left > 0.0:
		return
	var data := current_data()
	var slot := current_slot()
	if data.get("reload_per_round", false):
		slot.mag += 1
		slot.reserve -= 1
		if slot.mag < data.mag and slot.reserve > 0:
			_reload_left = data.reload_time
			Sound.play("reload", null, -4.0)
		else:
			_reload_left = 0.0
			Sound.play(data.get("pump_sound", "reload"))
	else:
		var loaded := mini(data.mag - slot.mag, slot.reserve)
		slot.mag += loaded
		slot.reserve -= loaded
		_reload_left = 0.0
	changed.emit()


func _update_pump(delta: float) -> void:
	if _pump_left > 0.0:
		_pump_left -= delta
		if _pump_left <= 0.0:
			Sound.play(current_data().get("pump_sound", ""))


func _update_switch(delta: float) -> void:
	if _switch_left <= 0.0:
		return
	var before := _switch_left
	_switch_left -= delta
	# Swap models at the bottom of the lower/raise motion.
	if before > SWITCH_TIME and _switch_left <= SWITCH_TIME and _pending_switch != "":
		_equip(_pending_switch)
		_pending_switch = ""


func _equip(id: String) -> void:
	current = id
	for weapon_id in _view_models:
		_view_models[weapon_id].visible = weapon_id == id
	changed.emit()


# --- Viewmodel -------------------------------------------------------------

func _build_viewmodel_viewport() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 1
	add_child(layer)
	var container := SubViewportContainer.new()
	container.stretch = true
	container.set_anchors_preset(Control.PRESET_FULL_RECT)
	container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(container)
	var viewport := SubViewport.new()
	viewport.transparent_bg = true
	viewport.own_world_3d = true
	viewport.msaa_3d = Viewport.MSAA_DISABLED
	container.add_child(viewport)

	var environment := Environment.new()
	environment.background_mode = Environment.BG_CLEAR_COLOR
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.45, 0.45, 0.5)
	environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	_view_camera = Camera3D.new()
	_view_camera.fov = VIEW_FOV
	_view_camera.near = 0.01
	_view_camera.far = 10.0
	_view_camera.environment = environment
	viewport.add_child(_view_camera)

	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-40, 30, 0)
	light.light_energy = 0.9
	viewport.add_child(light)

	_pivot = Node3D.new()
	viewport.add_child(_pivot)


func _add_view_model(id: String) -> void:
	var scene := Weapons.view_scene(id)
	var model: Node3D = scene.instantiate() if scene else Node3D.new()
	model.visible = false
	_pivot.add_child(model)
	_view_models[id] = model
	var muzzle := model.find_child("Muzzle", true, false) as Node3D
	if muzzle:
		var flash := Effects.make_flash_sprite(0.004)
		muzzle.add_child(flash)
		_flashes[id] = flash


func _update_viewmodel(delta: float) -> void:
	if _pivot == null:
		return
	_recoil = move_toward(_recoil, 0.0, delta * 8.0)
	_flash_left -= delta
	for id in _flashes:
		var flash: Sprite3D = _flashes[id]
		flash.visible = id == current and _flash_left > 0.0
		if flash.visible:
			flash.rotation.z = randf() * TAU

	var bob := _player.get_bob_offset()
	var lowered := 0.0
	if _switch_left > 0.0:
		lowered = 1.0 - absf(_switch_left - SWITCH_TIME) / SWITCH_TIME
	var reload_tilt := 0.0
	if is_reloading():
		reload_tilt = 1.0
	var target := Vector3(bob.x * 0.6, bob.y * 0.6 - lowered * 0.35, _recoil * 0.05)
	_pivot.position = _pivot.position.lerp(target, 1.0 - exp(-20.0 * delta))
	var target_rotation := Vector3(_recoil * 0.12 - reload_tilt * 0.6, 0.0, reload_tilt * 0.3)
	_pivot.rotation = _pivot.rotation.lerp(target_rotation, 1.0 - exp(-12.0 * delta))
