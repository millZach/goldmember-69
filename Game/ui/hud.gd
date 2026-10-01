class_name Hud
extends CanvasLayer
## In-mission HUD: ammo counter, health/armor bars that appear on change, the aim-mode
## crosshair, damage flash, interaction prompt and a message line.

const BAR_SHOW_TIME := 3.0
const MESSAGE_TIME := 2.5

var _mission: Mission
var _player: Player
var _ammo: Label
var _weapon_name: Label
var _prompt: Label
var _message: Label
var _crosshair: TextureRect
var _flash: ColorRect
var _bars: Control
var _health_bar: ColorRect
var _armor_bar: ColorRect
var _bars_left := 0.0
var _messages: Array[String] = []
var _message_left := 0.0
var _last_health := 0.0


func _ready() -> void:
	layer = 5
	_flash = ColorRect.new()
	_flash.color = Color(0.8, 0.0, 0.0, 0.0)
	_flash.set_anchors_preset(Control.PRESET_FULL_RECT)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_flash)

	_crosshair = TextureRect.new()
	_crosshair.texture = Effects.texture("crosshair")
	_crosshair.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_crosshair.visible = false
	add_child(_crosshair)

	_ammo = RetroTheme.hud_label(16)
	_ammo.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_ammo.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_ammo.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_ammo.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_ammo.offset_right = -6
	_ammo.offset_bottom = -4
	add_child(_ammo)

	_weapon_name = RetroTheme.hud_label()
	_weapon_name.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_weapon_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_weapon_name.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_weapon_name.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_weapon_name.offset_right = -6
	_weapon_name.offset_bottom = -24
	add_child(_weapon_name)

	_prompt = RetroTheme.hud_label()
	_prompt.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_prompt.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_prompt.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_prompt.offset_bottom = -44
	add_child(_prompt)

	_message = RetroTheme.hud_label()
	_message.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	_message.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_message.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_message.offset_top = 8
	add_child(_message)

	_bars = Control.new()
	_bars.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bars.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	_bars.position += Vector2(8, -18)
	add_child(_bars)
	_health_bar = _make_bar(Vector2(0, 0), Color(0.85, 0.15, 0.1))
	_armor_bar = _make_bar(Vector2(0, 6), Color(0.25, 0.5, 0.95))
	_bars.modulate.a = 0.0


func bind(mission: Mission) -> void:
	_mission = mission
	_player = mission.player
	_last_health = _player.health
	mission.message.connect(_queue_message)
	_player.health_changed.connect(_on_health_changed)


func _process(delta: float) -> void:
	if _player == null:
		return
	var weapons := _player.weapons
	var slot := weapons.current_slot()
	if slot.is_empty():
		_ammo.text = ""
		_weapon_name.text = ""
	else:
		_ammo.text = "%d  %d" % [slot.mag, slot.reserve]
		_weapon_name.text = weapons.current_data().name + (" (reloading)" if weapons.is_reloading() else "")

	var focused := _player.focused_interactable
	_prompt.text = focused.prompt if focused else ""

	_crosshair.visible = _player.aiming and _crosshair.texture != null
	if _crosshair.visible:
		var size := get_viewport().get_visible_rect().size
		var center := size * 0.5 + _player.aim_offset * size * 0.5
		_crosshair.position = (center - _crosshair.texture.get_size() * 0.5).round()

	_flash.color.a = move_toward(_flash.color.a, 0.0, delta * 1.5)
	_bars_left -= delta
	_bars.modulate.a = clampf(_bars_left, 0.0, 1.0)
	_health_bar.size.x = 80.0 * _player.health / Player.MAX_HEALTH
	_armor_bar.size.x = 80.0 * _player.armor / Player.MAX_ARMOR

	_message_left -= delta
	if _message_left <= 0.0:
		if _messages.is_empty():
			_message.text = ""
		else:
			_message.text = _messages.pop_front()
			_message_left = MESSAGE_TIME


func _on_health_changed() -> void:
	if _player.health < _last_health:
		_flash.color.a = 0.45
	_last_health = _player.health
	_bars_left = BAR_SHOW_TIME


func _queue_message(text: String) -> void:
	if _messages.size() < 4:
		_messages.append(text)


func _make_bar(at: Vector2, color: Color) -> ColorRect:
	var back := ColorRect.new()
	back.color = Color(0, 0, 0, 0.6)
	back.position = at - Vector2.ONE
	back.size = Vector2(82, 6)
	_bars.add_child(back)
	var bar := ColorRect.new()
	bar.color = color
	bar.position = at
	bar.size = Vector2(80, 4)
	_bars.add_child(bar)
	return bar
