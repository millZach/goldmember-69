class_name Debrief
extends CanvasLayer
## End-of-mission screen with stats and retry/menu options.


func _ready() -> void:
	layer = 12
	process_mode = Node.PROCESS_MODE_ALWAYS


func show_result(mission: Mission, success: bool, reason: String) -> void:
	var back := ColorRect.new()
	back.color = Color(0.02, 0.03, 0.06, 0.85)
	back.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(back)

	var panel := PanelContainer.new()
	panel.theme = RetroTheme.make()
	add_child(panel)
	var box := VBoxContainer.new()
	panel.add_child(box)

	var title := Label.new()
	title.text = "MISSION COMPLETE" if success else "MISSION FAILED"
	title.add_theme_font_size_override("font_size", 16)
	title.add_theme_color_override("font_color", RetroTheme.MENU_ACCENT if success else Color(0.95, 0.3, 0.25))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)
	if reason != "":
		_row(box, reason, "")
	_row(box, Game.current_mission.get("title", ""), Game.DIFFICULTY_NAMES[Game.difficulty])
	_row(box, "", "")
	_row(box, "Time", Pda._format_time(mission.elapsed))
	var accuracy := 0.0 if mission.shots == 0 else 100.0 * mission.hits / mission.shots
	_row(box, "Accuracy", "%d%%" % roundi(accuracy))
	_row(box, "Shots fired", str(mission.shots))
	_row(box, "Kills", str(mission.kills))
	_row(box, "Headshots", str(mission.headshots))
	_row(box, "", "")

	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_child(buttons)
	var retry := _button(buttons, "Retry", Game.restart_mission)
	_button(buttons, "Main menu", Game.goto_menu)
	retry.grab_focus.call_deferred()

	await get_tree().process_frame
	panel.position = ((panel.get_viewport_rect().size - panel.size) * 0.5).round()


func _row(box: VBoxContainer, left: String, right: String) -> void:
	var row := HBoxContainer.new()
	var a := Label.new()
	a.text = left
	a.custom_minimum_size.x = 90
	row.add_child(a)
	var b := Label.new()
	b.text = right
	b.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	b.custom_minimum_size.x = 70
	row.add_child(b)
	box.add_child(row)


func _button(parent: Control, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(func():
		Sound.play("menu_select", null, -4.0, 0.0)
		action.call())
	parent.add_child(button)
	return button
