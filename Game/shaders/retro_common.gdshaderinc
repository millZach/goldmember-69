// Shared sampling for the retro look.
//
// 64-bit era consoles filtered textures with a 3-sample (triangle) bilinear
// approximation instead of true 4-sample bilinear. It produces the soft,
// slightly jagged smear that defines the look. Toggle globally with the
// `retro_three_point` shader global.

global uniform bool retro_three_point;

uniform sampler2D albedo_texture : source_color, hint_default_white, filter_nearest, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform vec2 uv_scale = vec2(1.0);
uniform bool alpha_cutout = false;

vec4 sample_three_point(sampler2D tex, vec2 uv) {
	vec2 size = vec2(textureSize(tex, 0));
	vec2 offset = fract(uv * size - vec2(0.5));
	offset -= step(1.0, offset.x + offset.y);
	vec4 c0 = texture(tex, uv - offset / size);
	vec4 c1 = texture(tex, uv - vec2(offset.x - sign(offset.x), offset.y) / size);
	vec4 c2 = texture(tex, uv - vec2(offset.x, offset.y - sign(offset.y)) / size);
	return c0 + abs(offset.x) * (c1 - c0) + abs(offset.y) * (c2 - c0);
}

vec4 sample_albedo(vec2 uv) {
	uv *= uv_scale;
	vec4 texel = retro_three_point ? sample_three_point(albedo_texture, uv) : texture(albedo_texture, uv);
	return texel * albedo_color;
}
