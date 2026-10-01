"""Verification report for the generated OGGs (uses ffprobe/ffmpeg for decoding and EBU R128)."""
import math
import re
import subprocess

import numpy as np

from synth import lufs_momentary_max, read_audio


def _ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=channels,sample_rate,codec_name:format=duration",
                          "-of", "default=nw=1", str(path)], capture_output=True, text=True, check=True).stdout
    d = dict(line.split("=", 1) for line in out.strip().splitlines())
    return float(d["duration"]), int(d["channels"]), int(d["sample_rate"]), d["codec_name"]


def _ebur128(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=sample",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    summ = err[err.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summ).group(1))
    pk = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summ)
    return i, float(pk.group(1)) if pk else float("nan")


def _db(x):
    return 20 * math.log10(max(float(x), 1e-12))


def loop_seam(a, sr):
    """Measure the wrap discontinuity against the signal's typical sample-to-sample step."""
    w = int(0.01 * sr)
    jump = np.abs(a[0] - a[-1]).max()
    steps = np.abs(np.diff(a, axis=0)).max(axis=1)
    p999 = np.percentile(steps, 99.9)
    rms_end = np.sqrt(np.mean(a[-w:] ** 2))
    rms_start = np.sqrt(np.mean(a[:w] ** 2))
    # second-difference "click energy" at seam vs. median over the file
    wrap = np.concatenate([a[-3:], a[:3]])
    d2_seam = np.abs(np.diff(wrap, 2, axis=0)).max()
    d2_all = np.percentile(np.abs(np.diff(a, 2, axis=0)).max(axis=1), 99.0)
    return jump, p999, rms_end, rms_start, d2_seam, d2_all


def report(music_dir, sfx_dir, loops):
    ok = True
    print("\n=== verification ===")
    print(f"{'file':28s} {'dur s':>7s} {'ch':>3s} {'rate':>6s} {'peak dB':>8s} {'LUFS-I':>7s} {'LUFS-Mmax':>9s}")
    for kind, d in (("music", music_dir), ("sfx", sfx_dir)):
        for p in sorted(d.glob("*.ogg")):
            dur, ch, sr, codec = _ffprobe(p)
            lufs, _ = _ebur128(p)
            a, _ = read_audio(p)
            pk = _db(np.abs(a).max())
            mmax = lufs_momentary_max(a.astype(float), sr)
            ist = "  n/a" if lufs <= -69.9 else f"{lufs:5.1f}"  # < 400 ms: no gated block
            flag = ""
            if pk >= -0.1:
                flag, ok = " CLIP!", False
            if kind == "music" and pk > -2.5:
                flag += " (music peak high)"
            if kind == "sfx" and pk > -0.9:
                flag += " (sfx peak > -1)"
            print(f"{kind + '/' + p.stem:28s} {dur:7.2f} {ch:3d} {sr:6d} {pk:8.2f} {ist:>7s} {mmax:9.1f}{flag}")

    print("\n=== loop seams (decoded OGG) ===")
    for kind, d in (("music", music_dir), ("sfx", sfx_dir)):
        for name in sorted(loops[kind]):
            p = d / f"{name}.ogg"
            if not p.exists():
                continue
            a, sr = read_audio(p)
            jump, p999, re_, rs, d2s, d2a = loop_seam(a, sr)
            good = jump <= max(p999, 1e-3) and d2s <= 4 * d2a + 1e-3
            ok &= bool(good)
            print(f"{name:14s} samples {len(a)}  |last-first| {jump:.4f} (99.9th pct step {p999:.4f})  "
                  f"rms10ms end/start {_db(re_):6.1f}/{_db(rs):6.1f} dB  "
                  f"seam d2 {d2s:.4f} vs p99 {d2a:.4f}  -> {'OK' if good else 'CLICK?'}")

    print("\n=== music RMS per 2 s (dBFS) ===")
    for p in sorted(music_dir.glob("*.ogg")):
        a, sr = read_audio(p)
        m = a.mean(axis=1)
        w = 2 * sr
        vals = [_db(np.sqrt(np.mean(m[i:i + w] ** 2))) for i in range(0, len(m), w)]
        print(f"{p.stem}:")
        for i in range(0, len(vals), 10):
            print("   " + " ".join(f"{v:6.1f}" for v in vals[i:i + 10]))
        # spectral balance summary
        spec = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
        f = np.fft.rfftfreq(len(m), 1 / sr)
        tot = spec.sum()
        bands = [(20, 120), (120, 500), (500, 2000), (2000, 6000), (6000, 16000)]
        print("   band energy %: " + "  ".join(f"{lo}-{hi}:{100 * spec[(f >= lo) & (f < hi)].sum() / tot:4.1f}"
                                              for lo, hi in bands))
        silent = [i * 2 for i, v in enumerate(vals) if v < -45]
        if silent and p.stem in loops["music"]:
            print(f"   WARNING near-silent windows at {silent}")
            ok = False
    print("\nverification", "PASSED" if ok else "FAILED")
    return ok
