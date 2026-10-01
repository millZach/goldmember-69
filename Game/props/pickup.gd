class_name Pickup
extends Area3D
## A spinning item the player collects by walking over it.

const KINDS := {
	"Armor": {"model": "res://assets/props/armor_vest.glb", "label": "Body armor"},
	"AmmoP9": {"model": "res://assets/props/ammo_box.glb", "label": "P9 ammo", "ammo": "p9"},
	"AmmoVK12": {"model": "res://assets/props/ammo_box.glb", "label": "VK-12 ammo", "ammo": "vk12"},
	"AmmoTalon12": {"model": "res://assets/props/ammo_box.glb", "label": "Talon 12 shells", "ammo": "talon12"},
	"WeaponP9": {"weapon": "p9"},
	"WeaponVK12": {"weapon": "vk12"},
	"WeaponTalon12": {"weapon": "talon12"},
}

var kind := ""
var amount := -1 ## Ammo amount override; -1 uses the weapon's default.
var _model: Node3D
var _time := randf() * TAU


static func create(parent: Node, pickup_kind: String, at: Vector3, ammo := -1) -> Pickup:
	if not KINDS.has(pickup_kind):
		push_warning("Unknown pickup kind: " + pickup_kind)
		return null
	var pickup := Pickup.new()
	pickup.kind = pickup_kind
	pickup.amount = ammo
	parent.add_child(pickup)
	pickup.global_position = at
	return pickup


func _ready() -> void:
	collision_layer = Layers.PICKUPS
	collision_mask = Layers.PLAYER
	var shape := CollisionShape3D.new()
	shape.shape = SphereShape3D.new()
	(shape.shape as SphereShape3D).radius = 0.7
	shape.position.y = 0.5
	add_child(shape)
	body_entered.connect(_on_body_entered)

	var info: Dictionary = KINDS[kind]
	var scene: PackedScene
	if info.has("weapon"):
		scene = Weapons.world_scene(info.weapon)
	elif ResourceLoader.exists(info.model):
		scene = load(info.model)
	_model = scene.instantiate() if scene else _placeholder()
	add_child(_model)
	if info.has("weapon"):
		_model.rotation.z = PI * 0.5 # Lie the gun on its side.


func _process(delta: float) -> void:
	_time += delta
	_model.rotation.y = _time * 1.5
	_model.position.y = 0.15 + sin(_time * 2.0) * 0.05


func _on_body_entered(body: Node3D) -> void:
	var player := body as Player
	if player == null or player.health <= 0.0:
		return
	var info: Dictionary = KINDS[kind]
	var taken := false
	var label := ""
	if kind == "Armor":
		taken = player.heal_armor(Player.MAX_ARMOR)
		label = info.label
	elif info.has("ammo"):
		taken = player.weapons.add_ammo(info.ammo, Weapons.PICKUP_AMMO[info.ammo] if amount < 0 else amount)
		label = info.label
	else:
		var had := player.weapons.owned.has(info.weapon)
		taken = player.weapons.give_weapon(info.weapon, amount)
		label = Weapons.DATA[info.weapon].name + (" ammo" if had else "")
	if not taken:
		return
	Sound.play("pickup_armor" if kind == "Armor" else "pickup_ammo")
	var mission := Mission.find(self)
	if mission:
		mission.show_message("Picked up " + label)
	queue_free()


func _placeholder() -> Node3D:
	var mesh := MeshInstance3D.new()
	mesh.mesh = BoxMesh.new()
	(mesh.mesh as BoxMesh).size = Vector3(0.3, 0.2, 0.2)
	return mesh
