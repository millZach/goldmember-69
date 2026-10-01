class_name AlarmPanel
extends Node3D
## Wall-mounted alarm box. Guards run to it to raise the alarm; the player can shoot it out.

const MODEL := "res://assets/props/alarm_panel.glb"

var destroyed := false
var sounding := false
var _lamp: Node3D
var _blink := 0.0


func _ready() -> void:
	add_to_group("alarms")
	if ResourceLoader.exists(MODEL):
		var model: Node3D = load(MODEL).instantiate()
		add_child(model)
		_lamp = model.find_child("Lamp", true, false)
	# Solid body so bullets can hit it.
	var body: StaticBody3D = preload("res://props/shot_relay.gd").new()
	body.collision_layer = Layers.WORLD
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	(shape.shape as BoxShape3D).size = Vector3(0.4, 0.55, 0.14)
	shape.position = Vector3(0, 0.05, -0.07)
	body.add_child(shape)
	add_child(body)


func _process(delta: float) -> void:
	if _lamp and sounding and not destroyed:
		_blink += delta
		_lamp.visible = fmod(_blink, 0.5) < 0.25


## Where a guard should stand to use the panel (floor level, in front of it).
func approach_point() -> Vector3:
	var forward := -global_basis.z
	var point := global_position + forward * 0.9
	point.y -= 1.3
	return point


func usable() -> bool:
	return not destroyed


func on_shot(_damage: float, at: Vector3) -> void:
	if destroyed:
		return
	destroyed = true
	sounding = false
	if _lamp:
		_lamp.visible = false
	Effects.puff(at, "impact_puff", 0.03)
	Sound.play("impact_metal", at)
