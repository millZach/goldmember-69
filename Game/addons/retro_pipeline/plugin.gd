@tool
extends EditorPlugin

var _post_import: EditorScenePostImportPlugin


func _enter_tree() -> void:
	_post_import = preload("res://addons/retro_pipeline/retro_post_import.gd").new()
	add_scene_post_import_plugin(_post_import)


func _exit_tree() -> void:
	remove_scene_post_import_plugin(_post_import)
	_post_import = null
