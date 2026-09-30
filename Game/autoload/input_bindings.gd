class_name InputBindings
## Registers every gameplay action for keyboard/mouse and controller.
##
## Kept in code rather than project.godot so bindings stay readable and diffable.

const STICK_DEADZONE := 0.2
const LOOK_DEADZONE := 0.15
const TRIGGER_DEADZONE := 0.3


static func register() -> void:
	_action("move_forward", STICK_DEADZONE, [KEY_W], [], [], [[JOY_AXIS_LEFT_Y, -1.0]])
	_action("move_back", STICK_DEADZONE, [KEY_S], [], [], [[JOY_AXIS_LEFT_Y, 1.0]])
	_action("move_left", STICK_DEADZONE, [KEY_A], [], [], [[JOY_AXIS_LEFT_X, -1.0]])
	_action("move_right", STICK_DEADZONE, [KEY_D], [], [], [[JOY_AXIS_LEFT_X, 1.0]])

	_action("look_left", LOOK_DEADZONE, [KEY_LEFT], [], [], [[JOY_AXIS_RIGHT_X, -1.0]])
	_action("look_right", LOOK_DEADZONE, [KEY_RIGHT], [], [], [[JOY_AXIS_RIGHT_X, 1.0]])
	_action("look_up", LOOK_DEADZONE, [KEY_UP], [], [], [[JOY_AXIS_RIGHT_Y, -1.0]])
	_action("look_down", LOOK_DEADZONE, [KEY_DOWN], [], [], [[JOY_AXIS_RIGHT_Y, 1.0]])

	_action("fire", TRIGGER_DEADZONE, [], [MOUSE_BUTTON_LEFT], [], [[JOY_AXIS_TRIGGER_RIGHT, 1.0]])
	_action("aim", TRIGGER_DEADZONE, [], [MOUSE_BUTTON_RIGHT], [], [[JOY_AXIS_TRIGGER_LEFT, 1.0]])
	_action("interact", 0.5, [KEY_E, KEY_SPACE], [], [JOY_BUTTON_A], [])
	_action("crouch", 0.5, [KEY_C, KEY_CTRL], [], [JOY_BUTTON_B], [])
	_action("reload", 0.5, [KEY_R], [], [JOY_BUTTON_X], [])
	_action("next_weapon", 0.5, [KEY_Q], [MOUSE_BUTTON_WHEEL_DOWN], [JOY_BUTTON_Y], [])
	_action("prev_weapon", 0.5, [], [MOUSE_BUTTON_WHEEL_UP], [JOY_BUTTON_LEFT_SHOULDER], [])
	_action("pause", 0.5, [KEY_ESCAPE], [], [JOY_BUTTON_START], [])


static func _action(name: StringName, deadzone: float, keys: Array, mouse_buttons: Array, joy_buttons: Array, joy_axes: Array) -> void:
	if InputMap.has_action(name):
		InputMap.erase_action(name)
	InputMap.add_action(name, deadzone)
	for keycode in keys:
		var key := InputEventKey.new()
		key.physical_keycode = keycode
		InputMap.action_add_event(name, key)
	for button in mouse_buttons:
		var mouse := InputEventMouseButton.new()
		mouse.button_index = button
		InputMap.action_add_event(name, mouse)
	for button in joy_buttons:
		var joy := InputEventJoypadButton.new()
		joy.device = -1
		joy.button_index = button
		InputMap.action_add_event(name, joy)
	for axis_spec in joy_axes:
		var motion := InputEventJoypadMotion.new()
		motion.device = -1
		motion.axis = axis_spec[0]
		motion.axis_value = axis_spec[1]
		InputMap.action_add_event(name, motion)
