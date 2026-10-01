extends Control
## Title screen and menus: press start, main menu, mission select, difficulty, options.

var _panel: PanelContainer
var _content: VBoxContainer
var _press_start: Label
var _title_screen := true
var _blink := 0.0
var _selected_mission := ""


func _ready() -> void:
	theme = RetroTheme.make()
	set_anchors_preset(Control.PRESET_FULL_RECT)
	Game.in_gameplay = false
	Game.set_mouse_captured(false)
	Sound.play_music("menu")
	_build_backdrop()

	_panel = PanelContainer.new()
	_panel.visible = false
	add_child(_panel)
	_content = VBoxContainer.new()
	_panel.add_child(_content)

	_press_start = Label.new()
	_press_start.text = "PRESS START"
	_press_start.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_press_start.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_press_start.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_press_start.offset_bottom = -40
	add_child(_press_start)


func _process(delta: float) -> void:
	_blink += delta
	_press_start.visible = _title_screen and fmod(_blink, 1.0) < 0.6


func _unhandled_input(event: InputEvent) -> void:
	var pressed := (event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton) and event.is_pressed()
	if _title_screen and pressed:
		_title_screen = false
		Sound.play("menu_select", null, -4.0, 0.0)
		_show_main()
		get_viewport().set_input_as_handled()
	elif not _title_screen and event.is_action_pressed("ui_cancel"):
		Sound.play("menu_move", null, -6.0, 0.0)
		_show_main()
		get_viewport().set_input_as_handled()


func _build_backdrop() -> void:
	var back := ColorRect.new()
	back.color = Color(0.03, 0.04, 0.08)
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(back)
	# Horizontal scanline bands for a bit of texture.
	for i in 24:
		var band := ColorRect.new()
		band.color = Color(0.2, 0.25, 0.45, 0.03 + 0.02 * (i % 3))
		band.position = Vector2(0, i * 10)
		band.size = Vector2(320, 5)
		add_child(band)

	var title := Label.new()
	title.text = "GOLDMEMBER 69"
	title.add_theme_font_size_override("font_size", 24)
	title.add_theme_color_override("font_color", RetroTheme.MENU_ACCENT)
	title.add_theme_color_override("font_shadow_color", Color(0.4, 0.2, 0.0))
	title.add_theme_constant_override("shadow_offset_x", 2)
	title.add_theme_constant_override("shadow_offset_y", 2)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	title.grow_horizontal = Control.GROW_DIRECTION_BOTH
	title.offset_top = 24
	add_child(title)

	var tagline := Label.new()
	tagline.text = "A COVERT OPERATIONS THRILLER"
	tagline.add_theme_color_override("font_color", Color(0.6, 0.62, 0.7))
	tagline.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tagline.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	tagline.grow_horizontal = Control.GROW_DIRECTION_BOTH
	tagline.offset_top = 56
	add_child(tagline)


func _clear() -> void:
	for child in _content.get_children():
		child.queue_free()


func _heading(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.add_theme_color_override("font_color", RetroTheme.MENU_ACCENT)
	_content.add_child(label)


func _button(text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.custom_minimum_size.x = 140
	button.pressed.connect(func():
		Sound.play("menu_select", null, -4.0, 0.0)
		action.call())
	button.focus_entered.connect(func(): Sound.play("menu_move", null, -8.0, 0.0))
	_content.add_child(button)
	return button


func _present(first: Control) -> void:
	_panel.visible = true
	await get_tree().process_frame
	_panel.size = _panel.get_combined_minimum_size()
	_panel.position = ((size - _panel.size) * Vector2(0.5, 0.62)).round()
	if first:
		first.grab_focus()


func _show_main() -> void:
	_title_screen = false
	_clear()
	var first := _button("Mission select", _show_missions)
	_button("Options", _show_options)
	if OS.get_name() != "Web":
		_button("Quit", get_tree().quit)
	_present(first)


func _show_missions() -> void:
	_clear()
	_heading("SELECT MISSION")
	var first: Button
	for i in Game.MISSIONS.size():
		var mission: Dictionary = Game.MISSIONS[i]
		var number := "%02d" % (i + 1) if mission.id != "test_room" else "--"
		var button := _button("%s  %s" % [number, mission.title], func(): _show_difficulty(mission.id))
		if first == null:
			first = button
	_present(first)


func _show_difficulty(mission_id: String) -> void:
	_selected_mission = mission_id
	_clear()
	_heading("SELECT DIFFICULTY")
	var first: Button
	for level in Game.DIFFICULTY_NAMES.size():
		var count: int = Mission.OBJECTIVES.get(mission_id, []).filter(func(o): return o.min <= level).size()
		var label := "%s  (%d objectives)" % [Game.DIFFICULTY_NAMES[level], count]
		var button := _button(label, func(): Game.start_mission(_selected_mission, level))
		if first == null:
			first = button
	_present(first)


func _show_options() -> void:
	_clear()
	_heading("OPTIONS")
	var options := OptionsPanel.new()
	_content.add_child(options)
	var back := _button("Back", _show_main)
	await get_tree().process_frame
	var first := options.first_control()
	_present(first if first else back)
