class_name Pda
extends CanvasLayer
## Pause menu styled as a rugged field PDA with a green LCD: mission objectives,
## gear, options, resume and abort.

const DEVICE_SIZE := Vector2(236, 196)

var _mission: Mission
var _device: Control
var _screen: VBoxContainer
var _tabs: HBoxContainer
var _page: Control
var _resume: Button
var _open := false


func _ready() -> void:
	layer = 10
	process_mode = Node.PROCESS_MODE_ALWAYS
	visible = false
	_mission = get_parent() as Mission
	_build()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and not _mission.ended:
		get_viewport().set_input_as_handled()
		set_open(not _open)
	elif _open and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
		set_open(false)


func set_open(open: bool) -> void:
	_open = open
	visible = open
	get_tree().paused = open
	Game.set_mouse_captured(not open)
	Sound.play("pda_open" if open else "pda_close", null, -4.0, 0.0)
	if open:
		_show_mission()
		_device.position.y = get_viewport().get_visible_rect().size.y
		var tween := create_tween()
		tween.tween_property(_device, "position:y", _device_rest().y, 0.18).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		_resume.grab_focus.call_deferred()


func _device_rest() -> Vector2:
	return ((get_viewport().get_visible_rect().size - DEVICE_SIZE) * 0.5).round()


func _build() -> void:
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.5)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)

	# Device casing.
	_device = Panel.new()
	var casing := StyleBoxFlat.new()
	casing.bg_color = Color(0.2, 0.21, 0.2)
	casing.border_color = Color(0.08, 0.08, 0.08)
	casing.set_border_width_all(2)
	casing.set_corner_radius_all(6)
	_device.add_theme_stylebox_override("panel", casing)
	_device.size = DEVICE_SIZE
	_device.position = _device_rest()
	add_child(_device)

	var brand := Label.new()
	brand.text = "FIELD PDA  MK-II"
	brand.add_theme_font_size_override("font_size", 8)
	brand.add_theme_color_override("font_color", Color(0.6, 0.6, 0.55))
	brand.position = Vector2(10, 4)
	_device.add_child(brand)

	var led := ColorRect.new()
	led.color = Color(0.3, 0.9, 0.3)
	led.size = Vector2(4, 4)
	led.position = Vector2(DEVICE_SIZE.x - 14, 8)
	_device.add_child(led)

	var bezel := PanelContainer.new()
	bezel.theme = RetroTheme.lcd()
	bezel.position = Vector2(8, 18)
	bezel.size = DEVICE_SIZE - Vector2(16, 26)
	_device.add_child(bezel)

	_screen = VBoxContainer.new()
	bezel.add_child(_screen)

	_tabs = HBoxContainer.new()
	_screen.add_child(_tabs)
	_tab_button("MISSION", _show_mission)
	_tab_button("GEAR", _show_gear)
	_tab_button("OPTIONS", _show_options)

	_page = VBoxContainer.new()
	_page.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_screen.add_child(_page)

	var actions := HBoxContainer.new()
	_screen.add_child(actions)
	_resume = _action_button(actions, "RESUME", func(): set_open(false))
	_action_button(actions, "ABORT", func():
		get_tree().paused = false
		Game.goto_menu())


func _tab_button(text: String, action: Callable) -> void:
	var button := Button.new()
	button.text = text
	button.pressed.connect(func():
		Sound.play("menu_move", null, -6.0, 0.0)
		action.call())
	_tabs.add_child(button)


func _action_button(parent: Control, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(func():
		Sound.play("menu_select", null, -4.0, 0.0)
		action.call())
	parent.add_child(button)
	return button


func _clear_page() -> void:
	for child in _page.get_children():
		child.queue_free()


func _line(text: String, dim := false) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.custom_minimum_size.x = DEVICE_SIZE.x - 30
	if dim:
		label.add_theme_color_override("font_color", RetroTheme.LCD_DIM)
	_page.add_child(label)
	return label


func _show_mission() -> void:
	_clear_page()
	var info := Game.current_mission
	_line("%s - %s" % [info.get("title", "Mission").to_upper(), info.get("location", "")])
	_line("%s    %s" % [Game.DIFFICULTY_NAMES[Game.difficulty], _format_time(_mission.elapsed)], true)
	_line("")
	if _mission.objectives.is_empty():
		_line("No objectives. Free training.", true)
	var letter := 0
	for objective in _mission.objectives:
		var mark: String = {"pending": "[ ]", "complete": "[X]", "failed": "[!]"}[objective.state]
		_line("%s %s. %s" % [mark, char(65 + letter), objective.text])
		letter += 1


func _show_gear() -> void:
	_clear_page()
	var player := _mission.player
	_line("HEALTH %3d   ARMOR %3d" % [player.health, player.armor])
	_line("")
	for id in Weapons.ORDER:
		if player.weapons.owned.has(id):
			var slot: Dictionary = player.weapons.owned[id]
			var marker := ">" if id == player.weapons.current else " "
			_line("%s %-12s %3d / %3d" % [marker, Weapons.DATA[id].name, slot.mag, slot.reserve])


func _show_options() -> void:
	_clear_page()
	var options := OptionsPanel.new()
	_page.add_child(options)


static func _format_time(seconds: float) -> String:
	return "%d:%02d" % [int(seconds) / 60, int(seconds) % 60]
