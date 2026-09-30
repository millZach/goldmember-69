// Props, characters and weapons: Gouraud (per-vertex) lighting from scene
// lights, no specular highlights.
shader_type spatial;
render_mode vertex_lighting, specular_disabled, cull_back, depth_draw_opaque;

#include "res://shaders/retro_common.gdshaderinc"

void fragment() {
	vec4 texel = sample_albedo(UV);
	if (alpha_cutout && texel.a < 0.5) {
		discard;
	}
	ALBEDO = texel.rgb * COLOR.rgb;
	ROUGHNESS = 1.0;
	METALLIC = 0.0;
}
