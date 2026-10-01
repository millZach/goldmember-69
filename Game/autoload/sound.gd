extends Node
## Pooled sound effect and music playback. Missing audio files are skipped silently
## so gameplay works before every sound exists.

const SFX_DIR := "res://assets/audio/sfx/"
const MUSIC_DIR := "res://assets/audio/music/"
const POOL_3D := 24
const POOL_2D := 8

var _cache := {}
var _players_3d: Array[AudioStreamPlayer3D] = []
var _players_2d: Array[AudioStreamPlayer] = []
var _next_3d := 0
var _next_2d := 0
var _music: AudioStreamPlayer
var _music_name := ""


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	for bus in ["Music", "SFX"]:
		if AudioServer.get_bus_index(bus) == -1:
			AudioServer.add_bus()
			AudioServer.set_bus_name(AudioServer.bus_count - 1, bus)
	for i in POOL_3D:
		var player := AudioStreamPlayer3D.new()
		player.bus = &"SFX"
		player.unit_size = 8.0
		player.max_distance = 80.0
		add_child(player)
		_players_3d.append(player)
	for i in POOL_2D:
		var player := AudioStreamPlayer.new()
		player.bus = &"SFX"
		add_child(player)
		_players_2d.append(player)
	_music = AudioStreamPlayer.new()
	_music.bus = &"Music"
	add_child(_music)


func set_volumes(music: float, sfx: float) -> void:
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("Music"), linear_to_db(maxf(music, 0.0001)))
	AudioServer.set_bus_volume_db(AudioServer.get_bus_index("SFX"), linear_to_db(maxf(sfx, 0.0001)))


func get_stream(sound_name: String, directory := SFX_DIR) -> AudioStream:
	var path := directory + sound_name + ".ogg"
	if not _cache.has(path):
		_cache[path] = load(path) if ResourceLoader.exists(path) else null
	return _cache[path]


## Play a sound. Pass a position for 3D sound, or leave it null for a flat UI/first-person sound.
func play(sound_name: String, at: Variant = null, volume_db := 0.0, pitch_jitter := 0.05) -> void:
	var stream := get_stream(sound_name)
	if stream == null:
		return
	var pitch := 1.0 + randf_range(-pitch_jitter, pitch_jitter)
	if at is Vector3:
		var player := _players_3d[_next_3d]
		_next_3d = (_next_3d + 1) % POOL_3D
		player.stream = stream
		player.global_position = at
		player.volume_db = volume_db
		player.pitch_scale = pitch
		player.play()
	else:
		var player := _players_2d[_next_2d]
		_next_2d = (_next_2d + 1) % POOL_2D
		player.stream = stream
		player.volume_db = volume_db
		player.pitch_scale = pitch
		player.play()


## Create a looping player owned by the caller (e.g. an alarm siren). Returns null if the sound is missing.
func make_loop(sound_name: String, parent: Node, volume_db := 0.0) -> AudioStreamPlayer:
	var stream := get_stream(sound_name)
	if stream == null:
		return null
	stream = stream.duplicate()
	if "loop" in stream:
		stream.loop = true
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = &"SFX"
	player.volume_db = volume_db
	parent.add_child(player)
	return player


func play_music(track: String, loop := true) -> void:
	if track == _music_name and _music.playing:
		return
	var stream := get_stream(track, MUSIC_DIR)
	_music_name = track
	if stream == null:
		_music.stop()
		return
	stream = stream.duplicate()
	if "loop" in stream:
		stream.loop = loop
	_music.stream = stream
	_music.play()


func stop_music() -> void:
	_music_name = ""
	_music.stop()
