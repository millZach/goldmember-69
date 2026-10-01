extends StaticBody3D
## Forwards bullet hits on this body to its parent's on_shot().


func on_shot(damage: float, at: Vector3) -> void:
	get_parent().on_shot(damage, at)
