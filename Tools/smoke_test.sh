#!/usr/bin/env bash
# Headless gameplay smoke tests for each mission scene.
set -uo pipefail
cd "$(dirname "$0")/.."
status=0
for scene in res://levels/test_room/test_room.tscn res://missions/spillway/spillway.tscn; do
	echo "==> $scene"
	timeout 180 godot --headless --path Game res://tests/smoke_test.tscn -- --mission-scene="$scene" 2>&1 \
		| grep -E '^(PASS|FAIL|RESULT|guards|nav|guard|shots|pickups|SCRIPT ERROR|ERROR)' || status=1
	[ "${PIPESTATUS[0]}" -eq 0 ] || status=1
done
exit $status
