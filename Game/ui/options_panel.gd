class_name OptionsPanel
extends VBoxContainer
## Settings controls bound to Game.settings; changes apply and save immediately.


func _ready() -> void:
	_slider("Mouse speed", "mouse_sensitivity", 0.03, 0.4, 0.01)
	_slider("Stick speed", "stick_sensitivity", 0.4, 2.0, 0.1)
	_toggle("Invert look", "invert_y")
	_toggle("3-point filter", "three_point_filtering")
	_choice("Resolution", "resolution_index", Game.RESOLUTION_NAMES)
	_choice("Frame cap", "frame_cap_index", ["Off", "30 fps", "20 fps"])
	_slider("Music", "music_volume", 0.0, 1.0, 0.05)
	_slider("Sound", "sfx_volume", 0.0, 1.0, 0.05)


func first_control() -> Control:
	for row in get_children():
		return row.get_child(1)
	return null


func _row(text: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	var label := Label.new()
	label.text = text
	label.custom_minimum_size.x = 70
	row.add_child(label)
	add_child(row)
	return row


func _slider(text: String, key: String, low: float, high: float, step: float) -> void:
	var slider := HSlider.new()
	slider.min_value = low
	slider.max_value = high
	slider.step = step
	slider.value = Game.settings[key]
	slider.custom_minimum_size = Vector2(80, 8)
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	slider.value_changed.connect(func(v): _apply(key, v))
	_row(text).add_child(slider)


func _toggle(text: String, key: String) -> void:
	var toggle := CheckButton.new()
	toggle.button_pressed = Game.settings[key]
	toggle.text = "On" if toggle.button_pressed else "Off"
	toggle.toggled.connect(func(on):
		toggle.text = "On" if on else "Off"
		_apply(key, on))
	_row(text).add_child(toggle)


func _choice(text: String, key: String, options: Array) -> void:
	var button := Button.new()
	button.text = options[Game.settings[key]]
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.pressed.connect(func():
		var value: int = (Game.settings[key] + 1) % options.size()
		button.text = options[value]
		_apply(key, value))
	_row(text).add_child(button)


func _apply(key: String, value: Variant) -> void:
	Game.settings[key] = value
	Game.apply_settings()
	Game.save_settings()
	Sound.play("menu_move", null, -6.0, 0.0)
