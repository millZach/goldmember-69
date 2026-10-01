#!/usr/bin/env bash
# Regenerate all generated assets (Blender models/levels, audio) and reimport into Godot.
set -euo pipefail
cd "$(dirname "$0")/.."

for script in Blender/Scripts/build_*.py; do
	echo "==> $script"
	blender -b --factory-startup --python "$script" 2>&1 | grep -E 'EXPORTED|Error|Traceback' || true
done

if [ -f Audio/Scripts/build_audio.py ]; then
	echo "==> Audio"
	python3 Audio/Scripts/build_audio.py
fi

echo "==> Godot import"
godot --headless --path Game --import >/dev/null 2>&1
echo "Done."
