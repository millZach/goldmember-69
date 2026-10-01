"""Synthesised 'sample-like' instruments for the Goldmember 69 soundtrack.

Each function returns a mono float64 note. Notes are cached where they are
deterministic so the sequencer can reuse them cheaply.
"""
import math

import numpy as np

from synth import (adsr, exp_decay, fade_edges, fm_op, karplus, mtof, noise, pulse,
                   saw, sine, svf, drive, onepole_lp, TWO_PI)

_cache = {}


def _cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def _t(n, sr):
    return np.arange(n) / sr


# ---------------------------------------------------------------- basses
def synth_bass(m, dur, vel, sr):
    """Driving filtered saw bass with resonant pluck envelope."""
    def make():
        f = float(mtof(m))
        n = int((dur + 0.06) * sr)
        t = _t(n, sr)
        x = 0.7 * saw(f, n, sr) + 0.45 * saw(f * 1.005, n, sr, 0.3) + 0.25 * pulse(f, n, sr, 0.3)
        x -= np.mean(x)
        fc = 160 + (900 + 2600 * vel) * np.exp(-t / 0.075)
        y = svf(x, fc, sr, q=1.8)
        y = drive(y * 1.2, 1.6) + 0.4 * np.sin(TWO_PI * f * t)
        env = adsr(n, sr, 0.002, 0.25, 0.75, 0.035, dur)
        return fade_edges(y * env * vel, sr, 0.0015, 0.004)
    return _cached(("sbass", m, round(dur, 3), round(vel, 2), sr), make)


def upright_bass(m, dur, vel, sr, rng):
    """Karplus-Strong upright: dark pluck + body thump."""
    def make():
        f = float(mtof(m))
        ring = min(dur + 0.12, 1.4)
        n = int(ring * sr)
        r = np.random.default_rng(int(m * 131 + vel * 100))
        x = karplus(f, ring, sr, r, decay=0.9965, bright=0.18, pick_pos=0.13)
        x /= np.max(np.abs(x)) + 1e-9
        t = _t(n, sr)
        thump = np.sin(TWO_PI * f * t) * np.exp(-t / 0.35) * 0.6
        finger = svf(noise(n, r), 900, sr, q=0.8, mode="bp") * np.exp(-t / 0.012) * 0.5
        y = x + thump[:len(x)] + finger[:len(x)]
        env = adsr(len(y), sr, 0.004, 0.6, 0.55, 0.08, dur)
        return fade_edges(y * env * vel, sr, 0.001, 0.01)
    return _cached(("ubass", m, round(dur, 3), round(vel, 2), sr), make)


# ---------------------------------------------------------------- brass
def synth_brass(m, dur, vel, sr, bright=1.0, attack=0.025, release=0.18, muted=False):
    """Detuned saw section through an envelope-swept filter plus an FM 'blat' layer."""
    def make():
        f = float(mtof(m))
        n = int((dur + release + 0.1) * sr)
        t = _t(n, sr)
        vib_amt = np.clip((t - 0.25) / 0.4, 0, 1) * (0.0045 if not muted else 0.003)
        scoop = 1.0 - 0.012 * np.exp(-t / 0.035)
        fr = f * scoop * (1.0 + vib_amt * np.sin(TWO_PI * 5.3 * t))
        x = saw(fr, n, sr) + 0.8 * saw(fr * 1.0065, n, sr, 0.37) + 0.8 * saw(fr * 0.9942, n, sr, 0.71)
        swell = 1.0 - np.exp(-t / (attack * 1.2))
        fc = f * (1.3 + (5.5 if not muted else 2.6) * vel * bright * swell * (0.62 + 0.38 * np.exp(-t / 0.22)))
        fc = np.minimum(fc, 9000 if not muted else 3500)
        y = svf(x, fc, sr, q=0.85) * 0.5
        idx = 2.6 * vel * bright * swell * (0.55 + 0.45 * np.exp(-t / 0.15))
        mod = idx * np.sin(TWO_PI * np.cumsum(fr) / sr)
        fmv = np.sin(TWO_PI * np.cumsum(fr) / sr + mod) * 0.45
        y = y + fmv
        env = adsr(n, sr, attack, 0.35, 0.78, release, dur)
        return fade_edges(drive(y * env, 1.2) * vel, sr, 0.001, 0.01)
    return _cached(("brass", m, round(dur, 3), round(vel, 2), bright, attack, release, muted, sr), make)


# ---------------------------------------------------------------- guitar
def guitar(m, dur, vel, sr, rng, trem_picking=True, pick_rate=None):
    """Karplus-Strong guitar, tremolo-picked on longer notes, lightly overdriven."""
    f = float(mtof(m))
    ring = dur + 0.25
    n = int(ring * sr)
    out = np.zeros(n)
    if trem_picking and pick_rate:
        step = 1.0 / pick_rate
        k = 0
        tpos = 0.0
        while tpos < dur - 0.01:
            seg = min(step + 0.02, dur - tpos + 0.02) + (0.2 if tpos + step >= dur else 0.0)
            v = vel * (0.95 if k % 2 == 0 else 0.78) * (1.0 + rng.uniform(-0.05, 0.05))
            p = karplus(f, seg, sr, rng, decay=0.9975, bright=0.75, pick_pos=0.18)
            p = fade_edges(p, sr, 0.0008, 0.012) * v
            i = int(tpos * sr)
            j = min(n, i + len(p))
            out[i:j] += p[:j - i]
            tpos += step
            k += 1
    else:
        p = karplus(f, ring, sr, rng, decay=0.9985, bright=0.8, pick_pos=0.2) * vel
        env = adsr(len(p), sr, 0.001, 1.0, 0.9, 0.12, dur)
        out[:len(p)] += p * env
    out = drive(out * 1.5, 1.4)
    return fade_edges(out, sr, 0.0005, 0.02)


# ---------------------------------------------------------------- strings
def strings(m, dur, vel, sr, attack=0.35, release=0.7, tremolo=0.0):
    def make():
        f = float(mtof(m))
        n = int((dur + release + 0.1) * sr)
        t = _t(n, sr)
        r = np.random.default_rng(int(m * 17 + 3))
        x = np.zeros(n)
        for c in (-11.0, -4.0, 0.0, 5.0, 12.0):
            rate = r.uniform(4.5, 6.0)
            fr = f * 2 ** (c / 1200.0) * (1.0 + 0.0035 * np.sin(TWO_PI * rate * t + r.uniform(0, 6.28)))
            x += saw(fr, n, sr, r.uniform())
        x *= 0.3
        env = adsr(n, sr, attack, 0.6, 0.9, release, dur)
        if tremolo > 0:
            env = env * (1.0 - 0.55 * (0.5 + 0.5 * np.sin(TWO_PI * tremolo * t)))
        return x * env * vel
    return _cached(("str", m, round(dur, 3), round(vel, 2), attack, release, tremolo, sr), make)


# ---------------------------------------------------------------- keys / mallets
def vibes(m, dur, vel, sr):
    """Vibraphone: 1:4:10 bar partials, soft mallet, motor tremolo, damper after note."""
    def make():
        f = float(mtof(m))
        ring = dur + 1.6
        n = int(ring * sr)
        t = _t(n, sr)
        x = (np.sin(TWO_PI * f * t) * np.exp(-t / 1.5)
             + 0.32 * vel * np.sin(TWO_PI * f * 3.98 * t) * np.exp(-t / 0.45)
             + 0.10 * vel * np.sin(TWO_PI * f * 9.94 * t) * np.exp(-t / 0.09))
        r = np.random.default_rng(int(m))
        click = onepole_lp(noise(n, r), 3000, sr) * np.exp(-t / 0.004) * 0.6
        x = x + click
        motor = 1.0 - 0.32 * (0.5 + 0.5 * np.sin(TWO_PI * 5.4 * t - 1.2))
        damp = np.where(t < dur + 0.25, 1.0, np.exp(-(t - dur - 0.25) / 0.25))
        return fade_edges(x * motor * damp * vel, sr, 0.0005, 0.02)
    return _cached(("vib", m, round(dur, 3), round(vel, 2), sr), make)


def epiano(m, dur, vel, sr):
    """Two-operator FM electric piano with a bell-ish tine transient."""
    def make():
        f = float(mtof(m))
        n = int((dur + 0.5) * sr)
        t = _t(n, sr)
        idx = (0.9 + 1.4 * vel) * np.exp(-t / 0.35) + 0.25
        mod = idx * np.sin(TWO_PI * f * t)
        body = np.sin(TWO_PI * f * t + mod)
        tine = 0.22 * vel * np.sin(TWO_PI * f * 14.0 * t) * np.exp(-t / 0.03) if f * 14 < sr * 0.45 else 0
        x = body + tine
        env = np.exp(-t / 1.6) * adsr(n, sr, 0.002, 0.1, 1.0, 0.18, dur)
        return fade_edges(x * env * vel, sr, 0.0005, 0.01)
    return _cached(("ep", m, round(dur, 3), round(vel, 2), sr), make)


def bell(m, dur, vel, sr):
    """FM bell / chime (inharmonic ratio)."""
    f = float(mtof(m))
    n = int((dur + 0.8) * sr)
    t = _t(n, sr)
    mod = 2.2 * vel * np.exp(-t / 0.4) * np.sin(TWO_PI * f * 3.5 * t)
    x = np.sin(TWO_PI * f * t + mod) * np.exp(-t / 0.7)
    x += 0.3 * np.sin(TWO_PI * f * 2.0 * t) * np.exp(-t / 0.25)
    return fade_edges(x * vel, sr, 0.0005, 0.02)


# ---------------------------------------------------------------- drums
def kick(sr, rng, vel=1.0, tone=1.0):
    n = int(0.42 * sr)
    t = _t(n, sr)
    f = 48 * tone + 115 * tone * np.exp(-t / 0.035)
    body = np.sin(TWO_PI * np.cumsum(f) / sr) * np.exp(-t / 0.2)
    click = svf(noise(n, rng), 2500, sr, q=0.7) * np.exp(-t / 0.004) * 0.6
    x = drive(body * 1.2 + click, 1.5)
    return fade_edges(x * vel, sr, 0.0003, 0.02)


def snare(sr, rng, vel=1.0, tone=1.0, decay=0.16):
    n = int((decay * 3 + 0.05) * sr)
    t = _t(n, sr)
    f = 185 * tone * (1 + 0.25 * np.exp(-t / 0.01))
    shell = (np.sin(TWO_PI * np.cumsum(f) / sr) + 0.5 * np.sin(TWO_PI * np.cumsum(f * 1.62) / sr)) * np.exp(-t / 0.05)
    nz = noise(n, rng)
    wires = svf(nz, 5200, sr, q=0.6, mode="bp") + 0.5 * svf(nz, 2000, sr, q=0.7, mode="hp")
    wires *= np.exp(-t / decay)
    x = 0.8 * shell + 1.1 * wires
    return fade_edges(drive(x, 1.4) * vel, sr, 0.0003, 0.02)


def hat(sr, rng, vel=1.0, open_=False):
    dur = 0.45 if open_ else 0.07
    n = int(dur * sr)
    t = _t(n, sr)
    metal = np.zeros(n)
    for fr in (317, 431, 557, 678, 803, 1011):
        metal += np.sign(np.sin(TWO_PI * fr * 3.1 * t + rng.uniform(0, 6)))
    x = 0.35 * metal / 6 + noise(n, rng)
    x = svf(x, 7500, sr, q=0.8, mode="hp")
    x *= np.exp(-t / (0.12 if open_ else 0.018))
    return fade_edges(x * vel * 0.6, sr, 0.0002, 0.01)


def tom(sr, rng, freq, vel=1.0):
    n = int(0.55 * sr)
    t = _t(n, sr)
    f = freq * (1 + 0.5 * np.exp(-t / 0.03))
    x = np.sin(TWO_PI * np.cumsum(f) / sr) * np.exp(-t / 0.22)
    x += 0.3 * svf(noise(n, rng), freq * 4, sr, q=1.0, mode="bp") * np.exp(-t / 0.03)
    return fade_edges(drive(x, 1.3) * vel, sr, 0.0003, 0.02)


def crash(sr, rng, vel=1.0, dur=2.2):
    n = int(dur * sr)
    t = _t(n, sr)
    metal = np.zeros(n)
    for _ in range(14):
        fr = rng.uniform(300, 1600) * 3.0
        metal += np.sign(np.sin(TWO_PI * fr * t + rng.uniform(0, 6)))
    x = 0.25 * metal / 14 + noise(n, rng)
    x = svf(x, 4200, sr, q=0.6, mode="hp")
    x *= np.exp(-t / 0.55) * (0.8 + 0.2 * np.exp(-t / 0.05))
    return fade_edges(x * vel * 0.55, sr, 0.0005, 0.05)


def ride(sr, rng, vel=1.0):
    n = int(1.0 * sr)
    t = _t(n, sr)
    x = np.zeros(n)
    for fr, a in ((2350, 1.0), (3190, 0.7), (4420, 0.5), (5610, 0.35), (7050, 0.25)):
        x += a * np.sin(TWO_PI * fr * t + rng.uniform(0, 6)) * np.exp(-t / rng.uniform(0.25, 0.5))
    x += 0.5 * svf(noise(n, rng), 6000, sr, q=0.7, mode="hp") * np.exp(-t / 0.06)
    x *= 1.0 + 1.5 * np.exp(-t / 0.004)
    return fade_edges(x * vel * 0.25, sr, 0.0003, 0.05)


def brush_hit(sr, rng, vel=1.0):
    n = int(0.3 * sr)
    t = _t(n, sr)
    x = svf(noise(n, rng), 3500, sr, q=0.5, mode="bp")
    env = (1 - np.exp(-t / 0.004)) * np.exp(-t / 0.09)
    body = np.sin(TWO_PI * 200 * t) * np.exp(-t / 0.03) * 0.25
    return fade_edges((x * env + body) * vel, sr, 0.0005, 0.02)


def brush_swish(sr, rng, dur, vel=1.0):
    n = int(dur * sr)
    t = _t(n, sr)
    x = svf(noise(n, rng), 3000, sr, q=0.4, mode="bp")
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return x * env * vel * 0.35


def soft_kick(sr, rng, vel=1.0):
    n = int(0.35 * sr)
    t = _t(n, sr)
    f = 55 + 40 * np.exp(-t / 0.03)
    x = np.sin(TWO_PI * np.cumsum(f) / sr) * np.exp(-t / 0.16)
    return fade_edges(x * vel, sr, 0.001, 0.02)


def timpani(m, vel, sr, rng, dur=2.5):
    f = float(mtof(m))
    n = int(dur * sr)
    t = _t(n, sr)
    fr = f * (1 + 0.03 * np.exp(-t / 0.06))
    x = np.zeros(n)
    for ratio, amp, tau in ((1.0, 1.0, 0.9), (1.504, 0.5, 0.6), (1.742, 0.3, 0.45), (2.0, 0.25, 0.4), (2.245, 0.15, 0.3)):
        x += amp * np.sin(TWO_PI * np.cumsum(fr * ratio) / sr) * np.exp(-t / tau)
    mallet = svf(noise(n, rng), 600, sr, q=0.7) * np.exp(-t / 0.02) * 1.2
    return fade_edges(drive((x + mallet) * vel, 1.2), sr, 0.0005, 0.05)


def snare_roll(sr, rng, dur, v0, v1, rate=24.0):
    n = int((dur + 0.3) * sr)
    out = np.zeros(n)
    k = 0
    tt = 0.0
    while tt < dur:
        v = v0 + (v1 - v0) * (tt / dur)
        h = snare(sr, rng, v * rng.uniform(0.85, 1.0), decay=0.1)
        i = int(tt * sr)
        j = min(n, i + len(h))
        out[i:j] += h[:j - i]
        tt += 1.0 / rate
        k += 1
    return out
