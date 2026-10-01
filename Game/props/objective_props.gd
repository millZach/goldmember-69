class_name ObjectiveProps
## Builders for objective props: the alarm-grid breaker, data tap and uplink charge.


static func breaker(parent: Node3D, at: Transform3D) -> Interactable:
	var root := Node3D.new()
	parent.add_child(root)
	root.global_transform = at
	var model := _model("res://assets/props/breaker_panel.glb")
	if model:
		root.add_child(model)
	var area := Interactable.create(root, "Disable alarm grid", Vector3(0.8, 1.0, 0.6), Vector3(0, 0, -0.3))
	area.used.connect(func(_p):
		Sound.play("impact_metal", root.global_position, -4.0)
		var levers := model.find_child("Levers", true, false) as Node3D if model else null
		if levers:
			levers.create_tween().tween_property(levers, "rotation:x", levers.rotation.x + deg_to_rad(70), 0.3))
	return area


static func data_tap_spot(parent: Node3D, at: Transform3D) -> Interactable:
	var root := Node3D.new()
	parent.add_child(root)
	root.global_transform = at
	return Interactable.create(root, "Plant data tap", Vector3(1.2, 1.2, 1.0), Vector3(0, 0.9, -0.5))


static func place_data_tap(parent: Node3D, at: Transform3D) -> void:
	var model := _model("res://assets/props/data_tap.glb")
	if model == null:
		return
	parent.add_child(model)
	# On the console top, just in front of the marker.
	model.global_transform = at.translated_local(Vector3(0, 1.0, -0.55))
	Sound.play("charge_beep", model.global_position)


static func uplink_spot(parent: Node3D, at: Transform3D) -> Interactable:
	var root := Node3D.new()
	parent.add_child(root)
	root.global_transform = at
	return Interactable.create(root, "Plant charge", Vector3(1.4, 1.6, 1.4), Vector3(0, 0.8, -0.4))


## Plants a charge that beeps, then explodes after a few seconds and calls on_detonate(position).
static func plant_charge(parent: Node3D, at: Transform3D, on_detonate: Callable) -> void:
	var charge := _model("res://assets/props/explosive_charge.glb")
	if charge == null:
		charge = Node3D.new()
	parent.add_child(charge)
	charge.global_transform = at.translated_local(Vector3(0, 0, -0.4))
	Sound.play("charge_plant", charge.global_position)
	var tween := charge.create_tween()
	for i in 4:
		tween.tween_interval(1.0)
		tween.tween_callback(func(): Sound.play("charge_beep", charge.global_position, 0.0, 0.0))
	tween.tween_interval(0.6)
	tween.tween_callback(func():
		var position := charge.global_position
		Effects.explosion(position)
		charge.queue_free()
		on_detonate.call(position))


static func _model(path: String) -> Node3D:
	if not ResourceLoader.exists(path):
		return null
	return load(path).instantiate()
