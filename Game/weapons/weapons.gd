class_name Weapons
## Stats for every weapon. Damage is per pellet against a 100 HP guard (before hit-zone multipliers).

const DATA := {
	"p9": {
		"name": "Kessler P9",
		"damage": 34.0,
		"pellets": 1,
		"spread": 0.5,
		"fire_interval": 0.28,
		"automatic": false,
		"mag": 9,
		"max_reserve": 90,
		"reload_time": 1.2,
		"noise_radius": 6.0,
		"sound": "p9_fire",
		"recoil": 1.2,
		"range": 60.0,
	},
	"vk12": {
		"name": "VK-12",
		"damage": 22.0,
		"pellets": 1,
		"spread": 2.0,
		"fire_interval": 0.085,
		"automatic": true,
		"mag": 30,
		"max_reserve": 240,
		"reload_time": 1.6,
		"noise_radius": 30.0,
		"sound": "vk12_fire",
		"recoil": 0.6,
		"range": 60.0,
	},
	"talon12": {
		"name": "Talon 12",
		"damage": 14.0,
		"pellets": 8,
		"spread": 5.0,
		"fire_interval": 0.85,
		"automatic": false,
		"mag": 6,
		"max_reserve": 36,
		"reload_time": 0.45,
		"reload_per_round": true,
		"noise_radius": 35.0,
		"sound": "talon12_fire",
		"pump_sound": "talon12_pump",
		"recoil": 4.0,
		"range": 35.0,
	},
}

## Cycle order when switching.
const ORDER: Array[String] = ["p9", "vk12", "talon12"]

## Ammo granted by pickups and dropped weapons.
const PICKUP_AMMO := {"p9": 18, "vk12": 60, "talon12": 12}


static func view_scene(id: String) -> PackedScene:
	return _load("res://assets/weapons/%s_view.glb" % id)


static func world_scene(id: String) -> PackedScene:
	return _load("res://assets/weapons/%s_world.glb" % id)


static func _load(path: String) -> PackedScene:
	return load(path) if ResourceLoader.exists(path) else null
