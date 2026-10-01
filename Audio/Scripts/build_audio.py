#!/usr/bin/env python3
"""Regenerate every music track and sound effect for Goldmember 69.

Usage:
    python3 Audio/Scripts/build_audio.py             # build everything, then verify
    python3 Audio/Scripts/build_audio.py --only menu,p9_fire
    python3 Audio/Scripts/build_audio.py --verify    # only run the verification report

Output:
    Game/assets/audio/music/<name>.ogg   stereo 32 kHz Vorbis q5
    Game/assets/audio/sfx/<name>.ogg     mono   32 kHz Vorbis q5

Everything is synthesised from scratch and seeded, so builds are deterministic.
Requires python3 + numpy and ffmpeg/ffprobe on PATH.
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

import music  # noqa: E402
import sfx  # noqa: E402
from synth import peak_db, read_audio, undb, write_ogg  # noqa: E402

ROOT = HERE.parent.parent
MUSIC_DIR = ROOT / "Game" / "assets" / "audio" / "music"
SFX_DIR = ROOT / "Game" / "assets" / "audio" / "sfx"
LOOPS = {"music": {"spillway", "menu"}, "sfx": set(sfx.LOOPING_SFX)}


def encode_checked(path, x, sr, ceiling_db):
    """Encode to Vorbis, then decode and pull the gain down if lossy overshoot broke the ceiling."""
    for _ in range(4):
        write_ogg(path, x, sr, quality=5)
        dec, _ = read_audio(path)
        over = peak_db(dec) - ceiling_db
        if over <= 0:
            return
        x = x * undb(-over - 0.05)


def _build_music(name):
    t = time.time()
    x, sr = music.MUSIC[name]()
    encode_checked(MUSIC_DIR / f"{name}.ogg", x, sr, -2.9)
    return name, len(x) / sr, time.time() - t


def _build_sfx(name):
    x = sfx.build(name)
    encode_checked(SFX_DIR / f"{name}.ogg", x, sfx.SR, -1.0)
    return name, len(x) / sfx.SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma separated names to build")
    ap.add_argument("--verify", action="store_true", help="only run verification")
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1))
    args = ap.parse_args()

    if not args.verify:
        only = {s for s in args.only.split(",") if s}
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        SFX_DIR.mkdir(parents=True, exist_ok=True)
        m_names = [n for n in music.MUSIC if not only or n in only]
        s_names = [n for n in sfx.SFX if not only or n in only]
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            mf = [ex.submit(_build_music, n) for n in m_names]
            sf = [ex.submit(_build_sfx, n) for n in s_names]
            for f in sf:
                name, dur = f.result()
                print(f"  sfx   {name:20s} {dur:6.2f} s")
            for f in mf:
                name, dur, took = f.result()
                print(f"  music {name:20s} {dur:6.2f} s  (built in {took:.1f} s)")
        print(f"built in {time.time() - t0:.1f} s")

    import verify_audio
    ok = verify_audio.report(MUSIC_DIR, SFX_DIR, LOOPS)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
