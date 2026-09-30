extends Node
## Global game state: input bindings, retro display options, mouse capture and pause.
##
## Debug keys:
##   F1  cycle internal resolution (320x240 / 640x480 / 1280x960)
##   F2  toggle 3-point texture filtering
##   F3  cycle frame cap (uncapped / 30 / 20)
##   F4  toggle debug overlay
##   F11 toggle fullscreen
##
## Pass `-- --screenshot=<path>` on the command line to render a few frames,
## save a PNG and quit (used for automated visual checks).

const RESOLUTIONS: Array[Vector2i] = [Vector2i(320, 240), Vector2i(640, 480), Vector2i(1280, 960)]
const FRAME_CAPS: Array[int] = [0, 30, 20]
const UI_FONT_SIZE := 8

var resolution_index := 0
var frame_cap_index := 0
var three_point_filtering := true

var _pause_layer: CanvasLayer
var _resume_button: Button
var _debug_label: Label
var _screenshot_path := ""
var _screenshot_frames := 0


func _enter_tree() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	InputBindings.register()


func _ready() -> void:
	_build_pause_menu()
	_build_debug_overlay()
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--screenshot="):
			_screenshot_path = arg.trim_prefix("--screenshot=")
	_capture_mouse(true)


func _process(_delta: float) -> void:
	if _debug_label.visible:
		_debug_label.text = "%d FPS  %dx%d  3PT:%s  CAP:%s" % [
			Engine.get_frames_per_second(),
			RESOLUTIONS[resolution_index].x, RESOLUTIONS[resolution_index].y,
			"ON" if three_point_filtering else "OFF",
			str(FRAME_CAPS[frame_cap_index]) if FRAME_CAPS[frame_cap_index] > 0 else "OFF",
		]
	if _screenshot_path != "":
		_screenshot_frames += 1
		if _screenshot_frames == 30:
			get_viewport().get_texture().get_image().save_png(_screenshot_path)
			get_tree().quit()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause"):
		set_paused(not get_tree().paused)
	elif event is InputEventMouseButton and event.pressed and not get_tree().paused:
		_capture_mouse(true)
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_F1:
				resolution_index = (resolution_index + 1) % RESOLUTIONS.size()
				get_window().content_scale_size = RESOLUTIONS[resolution_index]
			KEY_F2:
				three_point_filtering = not three_point_filtering
				RenderingServer.global_shader_parameter_set("retro_three_point", three_point_filtering)
			KEY_F3:
				frame_cap_index = (frame_cap_index + 1) % FRAME_CAPS.size()
				Engine.max_fps = FRAME_CAPS[frame_cap_index]
			KEY_F4:
				_debug_label.visible = not _debug_label.visible
			KEY_F11:
				var fullscreen := get_window().mode == Window.MODE_FULLSCREEN
				get_window().mode = Window.MODE_WINDOWED if fullscreen else Window.MODE_FULLSCREEN


func set_paused(paused: bool) -> void:
	get_tree().paused = paused
	_pause_layer.visible = paused
	_capture_mouse(not paused)
	if paused:
		_resume_button.grab_focus()


func _capture_mouse(capture: bool) -> void:
	if _screenshot_path != "":
		return
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if capture else Input.MOUSE_MODE_VISIBLE


func _build_pause_menu() -> void:
	_pause_layer = CanvasLayer.new()
	_pause_layer.layer = 10
	_pause_layer.visible = false
	add_child(_pause_layer)

	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	_pause_layer.add_child(dim)

	var box := VBoxContainer.new()
	box.set_anchors_preset(Control.PRESET_CENTER)
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.grow_horizontal = Control.GROW_DIRECTION_BOTH
	box.grow_vertical = Control.GROW_DIRECTION_BOTH
	_pause_layer.add_child(box)

	var title := Label.new()
	title.text = "PAUSED"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", UI_FONT_SIZE * 2)
	box.add_child(title)

	_resume_button = _menu_button(box, "Resume", set_paused.bind(false))
	_menu_button(box, "Quit", get_tree().quit)


func _menu_button(parent: Control, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.add_theme_font_size_override("font_size", UI_FONT_SIZE)
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func _build_debug_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 20
	add_child(layer)
	_debug_label = Label.new()
	_debug_label.position = Vector2(2, 0)
	_debug_label.add_theme_font_size_override("font_size", UI_FONT_SIZE)
	_debug_label.visible = false
	layer.add_child(_debug_label)
