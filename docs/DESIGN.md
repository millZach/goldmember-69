# Goldmember 69 — Design

## Pillars

1. **Feels like 1997.** Everything is tuned to read like a 64-bit console shooter, not a modern game with a filter.
2. **Missions, not corridors.** Each level has multiple objectives, and higher difficulties add objectives and tougher guards.
3. **Guards that react.** Where you shoot matters: guards clutch wounds, stagger, drop weapons, and run for alarms.
4. **Couch multiplayer.** 2–4 player split-screen deathmatch is a first-class mode.

## The retro look (rendering rules)

| Rule | Implementation |
|------|----------------|
| Low-poly | Characters ~400–600 tris, props ~20–200 tris, faceted normals |
| Low-res textures | 32×32 to 64×64, 16-color palettes, authored in Blender scripts |
| Blurry texture filtering | Custom material function emulating 3-point bilinear filtering |
| Vertex-colored lighting | Baked vertex color lighting, no dynamic shadows, no Lumen/Nanite |
| Distance fog | Short-range linear fog per level to hide the draw distance |
| Low resolution output | Render at 320×240 (4:3) and upscale, with an optional "sharp" mode |
| Frame pacing | Optional 20–30 fps cap for authenticity |
| Sprite effects | Muzzle flashes, explosions and bullet holes as billboards / decals |
| HUD | Minimal: ammo counter bottom-right, health/armor arcs shown only on damage |

## Core gameplay

- **Aiming:** auto-aim with a small cone while moving; hold aim to enter a manual aim mode with a movable crosshair and zoom.
- **Hit zones:** head / torso / arms / legs / groin, each with damage multipliers and unique reaction animations.
- **Health and armor:** separate bars, no regeneration, armor pickups.
- **Pause menu:** diegetic in-universe gadget (a wrist device) with mission objectives, inventory and options.
- **Difficulty tiers:** Agent / Special Agent / Elite Agent, plus an unlockable custom mode with sliders for enemy health, accuracy and reaction time.
- **Mission rating:** completion time and accuracy, with unlockable cheats for beating target times.

## Controls

- **Mouse and keyboard:** standard WASD + mouse look.
- **Controller:** modern twin-stick by default, plus an optional "classic" single-stick preset (stick = move/turn, face buttons = look/strafe) for the authentic feel.

## Weapons (original)

| Weapon | Role |
|--------|------|
| Kessler P9 | Silenced sidearm, starting weapon |
| Brandt .44 | Heavy revolver, slow and powerful |
| VK-12 | Compact SMG, high fire rate |
| Rook AR | Assault rifle with scope |
| Talon 12 | Pump shotgun |
| Mole charges | Remote-detonated mines |
| Throwing knives | Silent, retrievable |

## Mission 1 — "Spillway"

A hydroelectric dam at night in fictional mountainous country Valdoria. The player infiltrates via a checkpoint road, crosses the dam wall, and disables a relay station.

- **Objectives (Agent):** disable the alarm grid, reach the dam crest, destroy the relay uplink.
- **Special Agent adds:** plant a data tap in the control room.
- **Elite Agent adds:** no guard may raise the alarm.

## Audio

Original score written in a late-90s sequenced style (sample-based instruments, spy-jazz brass, surf guitar, ambient pads). Every track is composed for this project.

## Roadmap

1. **Milestone 0 — Foundation:** engine install, Unreal MCP, UE5 project, retro render pipeline, Blender → UE import pipeline.
2. **Milestone 1 — Vertical slice:** "Spillway" level, 3–4 weapons, guard AI with hit reactions, objectives, pause-menu gadget, HUD, one music track.
3. **Milestone 2 — Split-screen:** 2–4 player local deathmatch in 2 arenas.
4. **Milestone 3+:** additional missions, remaining weapons, difficulty modes, cheats.
