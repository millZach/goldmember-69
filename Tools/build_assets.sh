#!/usr/bin/env bash
# Regenerate all Blender-built assets and reimport them into Godot.
set -euo pipefail
cd "$(dirname "$0")/.."

for script in Blender/Scripts/build_*.py; do
	echo "==> $script"
	blender -b --factory-startup --python "$script" 2>&1 | grep -E 'EXPORTED|Error|Traceback' || true
done

echo "==> Godot import"
godot --headless --path Game --import >/dev/null 2>&1
echo "Done."
