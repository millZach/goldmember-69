# Goldmember 69

An original late-90s console-style spy FPS built in Godot 4, with assets generated in Blender.

This is a love letter to the 64-bit era of shooters: low-poly models, blurry low-res textures, heavy distance fog, auto-aim, location-based hit reactions, objective-driven missions and split-screen deathmatch. All characters, levels, weapons, art and music are original to this project; it contains no assets, names or audio from any commercial game or film franchise.

| | |
|---|---|
| ![Checkpoint](docs/screenshots/m1_checkpoint.png) | ![Dam crest](docs/screenshots/m1_crest.png) |
| ![Control room](docs/screenshots/m1_control_room.png) | ![Test room](docs/screenshots/m1_test_room_guard.png) |

## Status

Milestone 1 (vertical slice) is done: the "Spillway" mission with 15 guards, three weapons, alarms, difficulty-based objectives, a field-PDA pause menu, main menu, debrief and an original score. See [docs/DESIGN.md](docs/DESIGN.md) for the design and roadmap.

## Running

```sh
godot --path Game            # play
godot -e --path Game         # open the editor
./Tools/build_assets.sh      # regenerate Blender assets + audio and reimport
./Tools/smoke_test.sh        # headless gameplay tests (combat, objectives, exit)
./Tools/export_web.sh        # web build into Build/web
```

## Controls

| Action | Keyboard / mouse | Controller |
|--------|------------------|------------|
| Move | WASD | Left stick |
| Look | Mouse / arrow keys | Right stick |
| Fire | Left click | Right trigger |
| Aim mode (zoom + movable crosshair) | Right click | Left trigger |
| Interact | E / Space | A |
| Crouch | C / Ctrl | B |
| Reload | R | X |
| Next / previous weapon | Q, mouse wheel | Y / LB |
| Pause | Esc | Start |

Debug keys: **F1** internal resolution, **F2** 3-point texture filtering, **F3** frame cap, **F4** debug overlay, **F11** fullscreen.

## Layout

| Path | Contents |
|------|----------|
| `Game/` | Godot 4 project |
| `Game/shaders/` | Retro shaders (3-point filtering, prelit and vertex-lit variants) |
| `Game/addons/retro_pipeline/` | Import plugin that converts glTF materials to the retro shaders |
| `Game/missions/`, `Game/guards/`, `Game/player/`, `Game/ui/` | Gameplay code |
| `Game/tests/` | Headless smoke test |
| `Blender/Scripts/` | Python generators for levels, characters, weapons, props, sprites |
| `Audio/Scripts/` | Synthesizer and compositions for the original score and SFX |
| `Blender/Source/` | Generated `.blend` sources |
| `Blender/Textures/` | Generated texture PNGs |
| `Tools/` | Pipeline scripts |
| `docs/` | Design docs and screenshots |

## Asset pipeline

1. A script in `Blender/Scripts/` builds geometry and 32–64 px palette textures, then bakes lighting into vertex colors.
2. It exports a `.glb` into `Game/assets/`. Object name suffixes such as `-col` and `-convcol` make Godot generate collision.
3. On import, `retro_pipeline` swaps every material for a retro shader. Surfaces with vertex colors get the unshaded prelit shader; others get per-vertex lighting.

## Toolchain

- Godot 4.7 (Compatibility renderer)
- Blender 5.2 + [blender-mcp](https://github.com/ahujasid/blender-mcp)
- Git LFS for binary assets
