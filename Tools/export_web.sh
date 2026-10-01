#!/usr/bin/env bash
# Export the Web build to Build/web (served for playtesting by Tools/serve_web.py).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p Build/web
godot --headless --path Game --export-release "Web" ../Build/web/index.html 2>&1 | grep -iE 'error' || true
echo "Exported to Build/web"
