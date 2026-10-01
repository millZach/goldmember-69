class_name Interactable
extends Area3D
## Something the player can use with the interact button while looking at it.

signal used(player: Player)

@export var prompt := "Use"
var enabled := true


static func create(parent: Node3D, text: String, size: Vector3, offset := Vector3.ZERO) -> Interactable:
	var area := Interactable.new()
	area.prompt = text
	var shape := CollisionShape3D.new()
	shape.shape = BoxShape3D.new()
	(shape.shape as BoxShape3D).size = size
	area.add_child(shape)
	area.position = offset
	parent.add_child(area)
	return area


func _ready() -> void:
	collision_layer = Layers.INTERACT
	collision_mask = 0
	monitoring = false


func interact(player: Player) -> void:
	if enabled:
		used.emit(player)
