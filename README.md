# Goldmember 69

An original late-90s console-style spy FPS built in Unreal Engine 5, with assets modeled in Blender through MCP.

This is a love letter to the 64-bit era of shooters — low-poly models, blurry low-res textures, heavy distance fog, auto-aim, location-based hit reactions, objective-driven missions and split-screen deathmatch. All characters, levels, weapons, art and music are original to this project; it contains no assets, names or audio from any commercial game or film franchise.

## Status

Pre-production. See [docs/DESIGN.md](docs/DESIGN.md) for the design and roadmap.

## Layout

| Path | Contents |
|------|----------|
| `Unreal/` | UE5 project (created once the engine is installed) |
| `Blender/Source/` | `.blend` source files |
| `Blender/Scripts/` | Python generators for props, characters, texture palettes |
| `Audio/Source/` | Original music and SFX sources |
| `Tools/` | Pipeline scripts (export, import, build) |
| `docs/` | Design docs |

## Toolchain

- Unreal Engine 5.x (C++ core systems, Blueprints for content)
- Blender 4.5 LTS + [blender-mcp](https://github.com/ahujasid/blender-mcp)
- Git LFS for binary assets
