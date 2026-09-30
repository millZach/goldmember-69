// Level geometry: lighting is baked into vertex colors in Blender, so no
// runtime lights are evaluated. Fog still applies.
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

#include "res://shaders/retro_common.gdshaderinc"

void fragment() {
	vec4 texel = sample_albedo(UV);
	if (alpha_cutout && texel.a < 0.5) {
		discard;
	}
	ALBEDO = texel.rgb * COLOR.rgb;
}
