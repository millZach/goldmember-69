class_name RetroTheme
## Shared UI theme: small crisp text on flat panels. The PDA uses the green LCD palette.

const FONT_SIZE := 8
const LCD_BACK := Color(0.09, 0.16, 0.09)
const LCD_TEXT := Color(0.62, 0.95, 0.55)
const LCD_DIM := Color(0.35, 0.6, 0.32)
const MENU_BACK := Color(0.05, 0.06, 0.1, 0.92)
const MENU_TEXT := Color(0.92, 0.9, 0.82)
const MENU_ACCENT := Color(0.95, 0.75, 0.25)


static func make(text: Color = MENU_TEXT, accent: Color = MENU_ACCENT, back: Color = MENU_BACK) -> Theme:
	var theme := Theme.new()
	theme.default_font_size = FONT_SIZE
	for type in ["Label", "Button", "CheckButton", "OptionButton"]:
		theme.set_color("font_color", type, text)
	for type in ["Button", "CheckButton", "OptionButton"]:
		theme.set_color("font_hover_color", type, accent)
		theme.set_color("font_focus_color", type, accent)
		theme.set_color("font_pressed_color", type, accent)
		theme.set_stylebox("normal", type, _box(Color(0, 0, 0, 0)))
		theme.set_stylebox("hover", type, _box(Color(accent, 0.15)))
		theme.set_stylebox("pressed", type, _box(Color(accent, 0.3)))
		theme.set_stylebox("focus", type, _box(Color(accent, 0.2), accent))
	theme.set_stylebox("panel", "PanelContainer", _box(back, text.darkened(0.5)))
	theme.set_stylebox("slider", "HSlider", _box(text.darkened(0.6)))
	theme.set_stylebox("grabber_area", "HSlider", _box(text.darkened(0.2)))
	theme.set_stylebox("grabber_area_highlight", "HSlider", _box(accent))
	theme.set_constant("separation", "VBoxContainer", 2)
	theme.set_constant("separation", "HBoxContainer", 4)
	return theme


static func lcd() -> Theme:
	return make(LCD_TEXT, Color(0.9, 1.0, 0.7), LCD_BACK)


static func _box(color: Color, border := Color(0, 0, 0, 0)) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = color
	box.content_margin_left = 3
	box.content_margin_right = 3
	box.content_margin_top = 1
	box.content_margin_bottom = 1
	if border.a > 0.0:
		box.border_color = border
		box.set_border_width_all(1)
	return box


## A label with a drop shadow, for HUD text over the 3D view.
static func hud_label(size := FONT_SIZE) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", MENU_TEXT)
	label.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return label
