extends Node
## Global game state: settings, difficulty, scene flow, retro display options and mouse capture.
##
## Debug keys:
##   F1  cycle internal resolution (320x240 / 640x480 / 1280x960)
##   F2  toggle 3-point texture filtering
##   F3  cycle frame cap (uncapped / 30 / 20)
##   F4  toggle debug overlay
##   F11 toggle fullscreen
##
## Command-line options (after `--`), used for automated checks:
##   --mission=<id>          start a mission directly
##   --difficulty=<0-2>
##   --pose=x,y,z,yaw,pitch  place the player (degrees)
##   --screenshot=<path>     render ~1 second, save a PNG and quit

enum Difficulty { AGENT, SPECIAL_AGENT, ELITE_AGENT }

const DIFFICULTY_NAMES: Array[String] = ["Agent", "Special Agent", "Elite Agent"]
const DIFFICULTY_TUNING: Array[Dictionary] = [
	{"guard_health": 1.0, "guard_accuracy": 0.35, "guard_damage": 7.0, "reaction_time": 0.8},
	{"guard_health": 1.3, "guard_accuracy": 0.5, "guard_damage": 10.0, "reaction_time": 0.6},
	{"guard_health": 1.7, "guard_accuracy": 0.65, "guard_damage": 14.0, "reaction_time": 0.45},
]
const MISSIONS: Array[Dictionary] = [
	{"id": "spillway", "title": "Spillway", "location": "Valdoria", "scene": "res://missions/spillway/spillway.tscn"},
	{"id": "test_room", "title": "Test Room", "location": "Training", "scene": "res://levels/test_room/test_room.tscn"},
]
const MENU_SCENE := "res://ui/main_menu.tscn"
const SETTINGS_PATH := "user://settings.cfg"
const RESOLUTIONS: Array[Vector2i] = [Vector2i(320, 240), Vector2i(640, 480), Vector2i(1280, 960)]
const RESOLUTION_NAMES: Array[String] = ["320x240", "640x480", "1280x960"]
const FRAME_CAPS: Array[int] = [0, 30, 20]
const UI_FONT_SIZE := 8

var difficulty := Difficulty.AGENT
var current_mission: Dictionary = {}
var in_gameplay := false
var settings := {
	"mouse_sensitivity": 0.12,
	"stick_sensitivity": 1.0,
	"invert_y": false,
	"three_point_filtering": true,
	"resolution_index": 0,
	"frame_cap_index": 0,
	"music_volume": 0.7,
	"sfx_volume": 1.0,
}

## Set from --pose; consumed by the next mission that loads.
var debug_pose := PackedFloat32Array()

var _debug_label: Label
var _screenshot_path := ""
var _screenshot_frames := 0


func _enter_tree() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	InputBindings.register()


func _ready() -> void:
	_load_settings()
	apply_settings()
	_build_debug_overlay()
	_parse_command_line()


func tuning() -> Dictionary:
	return DIFFICULTY_TUNING[difficulty]


func mission_by_id(id: String) -> Dictionary:
	for mission in MISSIONS:
		if mission.id == id:
			return mission
	return {}


func start_mission(id: String, level: int = difficulty) -> void:
	current_mission = mission_by_id(id)
	difficulty = level as Difficulty
	get_tree().paused = false
	get_tree().change_scene_to_file(current_mission.scene)


func restart_mission() -> void:
	start_mission(current_mission.id)


func goto_menu() -> void:
	in_gameplay = false
	get_tree().paused = false
	set_mouse_captured(false)
	get_tree().change_scene_to_file(MENU_SCENE)


func set_mouse_captured(capture: bool) -> void:
	if _screenshot_path != "":
		return
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if capture else Input.MOUSE_MODE_VISIBLE


func is_screenshot_run() -> bool:
	return _screenshot_path != ""


func apply_settings() -> void:
	RenderingServer.global_shader_parameter_set("retro_three_point", settings.three_point_filtering)
	get_window().content_scale_size = RESOLUTIONS[settings.resolution_index]
	Engine.max_fps = FRAME_CAPS[settings.frame_cap_index]
	Sound.set_volumes(settings.music_volume, settings.sfx_volume)


func save_settings() -> void:
	var file := ConfigFile.new()
	for key in settings:
		file.set_value("settings", key, settings[key])
	file.save(SETTINGS_PATH)


func _load_settings() -> void:
	var file := ConfigFile.new()
	if file.load(SETTINGS_PATH) != OK:
		return
	for key in settings:
		settings[key] = file.get_value("settings", key, settings[key])


func _parse_command_line() -> void:
	var mission_id := ""
	for arg in OS.get_cmdline_user_args():
		var parts := arg.trim_prefix("--").split("=", true, 1)
		if parts.size() != 2:
			continue
		match parts[0]:
			"screenshot":
				_screenshot_path = parts[1]
			"mission":
				mission_id = parts[1]
			"difficulty":
				difficulty = clampi(parts[1].to_int(), 0, 2) as Difficulty
			"pose":
				debug_pose = PackedFloat32Array(Array(parts[1].split(",")).map(func(v): return v.to_float()))
	if mission_id != "":
		start_mission.call_deferred(mission_id)


func _process(_delta: float) -> void:
	if _debug_label.visible:
		_debug_label.text = "%d FPS  %s  3PT:%s  CAP:%s" % [
			Engine.get_frames_per_second(),
			RESOLUTION_NAMES[settings.resolution_index],
			"ON" if settings.three_point_filtering else "OFF",
			str(FRAME_CAPS[settings.frame_cap_index]) if FRAME_CAPS[settings.frame_cap_index] > 0 else "OFF",
		]
	if _screenshot_path != "":
		_screenshot_frames += 1
		if _screenshot_frames == 60:
			get_viewport().get_texture().get_image().save_png(_screenshot_path)
			get_tree().quit()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and in_gameplay and not get_tree().paused:
		set_mouse_captured(true)
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_F1:
				settings.resolution_index = (settings.resolution_index + 1) % RESOLUTIONS.size()
				apply_settings()
			KEY_F2:
				settings.three_point_filtering = not settings.three_point_filtering
				apply_settings()
			KEY_F3:
				settings.frame_cap_index = (settings.frame_cap_index + 1) % FRAME_CAPS.size()
				apply_settings()
			KEY_F4:
				_debug_label.visible = not _debug_label.visible
			KEY_F11:
				var fullscreen := get_window().mode == Window.MODE_FULLSCREEN
				get_window().mode = Window.MODE_WINDOWED if fullscreen else Window.MODE_FULLSCREEN


func _build_debug_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 100
	add_child(layer)
	_debug_label = Label.new()
	_debug_label.position = Vector2(2, 0)
	_debug_label.add_theme_font_size_override("font_size", UI_FONT_SIZE)
	_debug_label.visible = false
	layer.add_child(_debug_label)
