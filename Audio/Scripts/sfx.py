"""Synthesised sound effects for Goldmember 69 (mono, 32 kHz).

Every effect is built from noise, sines, modal resonators and filters.
Each builder returns a mono float array; build_all() levels them by
category (momentary loudness target + -1 dBFS peak ceiling).
"""
import math
import zlib

import numpy as np

from synth import (TWO_PI, convolve_mono, drive, fade_edges, fft_filter, hp_resp, limiter, lp_resp,
                   bp_resp, lufs_momentary_max, make_ir, mtof, noise, peak_db, svf, undb)

SR = 32000


def _rng(name):
    return np.random.default_rng(zlib.crc32(name.encode()))


def _t(n):
    return np.arange(n) / SR


def _n(sec):
    return int(sec * SR)


def place(out, sig, t, gain=1.0):
    i = int(t * SR)
    j = min(len(out), i + len(sig))
    if i < len(out):
        out[i:j] += sig[: j - i] * gain
    return out


def env_exp(n, tau, attack=0.0005):
    t = _t(n)
    return (1.0 - np.exp(-t / max(attack, 1e-5))) * np.exp(-t / tau)


def nburst(rng, dur, tau, lo=None, hi=None, q=0.7, attack=0.0003):
    n = _n(dur)
    x = noise(n, rng)
    if lo and hi:
        x = svf(svf(x, lo, SR, q, "hp"), hi, SR, q, "lp")
    elif lo:
        x = svf(x, lo, SR, q, "hp")
    elif hi:
        x = svf(x, hi, SR, q, "lp")
    return x * env_exp(n, tau, attack)


def bpburst(rng, dur, tau, fc, q=2.0, attack=0.0003):
    n = _n(dur)
    return svf(noise(n, rng), fc, SR, q, "bp") * env_exp(n, tau, attack)


def sweep_sine(f0, f1, dur, tau_f, tau_a, attack=0.0005):
    n = _n(dur)
    t = _t(n)
    f = f1 + (f0 - f1) * np.exp(-t / tau_f)
    return np.sin(TWO_PI * np.cumsum(f) / SR) * env_exp(n, tau_a, attack)


def modal(freqs, amps, taus, dur, rng=None, detune=0.0):
    n = _n(dur)
    t = _t(n)
    x = np.zeros(n)
    for f, a, tau in zip(freqs, amps, taus):
        ph = rng.uniform(0, TWO_PI) if rng is not None else 0.0
        x += a * np.sin(TWO_PI * f * t + ph) * np.exp(-t / tau)
        if detune:
            x += a * 0.5 * np.sin(TWO_PI * f * (1 + detune) * t + ph) * np.exp(-t / tau)
    return x


def click(rng, base=3000.0, tau=0.006, dur=0.05, bright=1.0):
    ratios = (1.0, 1.47, 2.09, 2.83)
    x = modal([base * r for r in ratios], [1.0, 0.7, 0.5, 0.3], [tau, tau * 0.8, tau * 0.6, tau * 0.5], dur, rng)
    x += bright * nburst(rng, dur, 0.0015, lo=2500)
    return x


def room(x, rt=0.35, mix=0.15, seed=3, length=None):
    ir = make_ir(SR, length=length or rt * 1.4, rt_low=rt, rt_high=rt * 0.5, predelay=0.004, seed=seed)[:, 0]
    wet = convolve_mono(x, ir)
    out = np.zeros(len(wet))
    out[: len(x)] += x
    return out + wet * mix


def trim(x, lead_db=-55.0, tail_db=-65.0, fade_out=0.01):
    a = np.abs(x)
    pk = a.max()
    on = np.nonzero(a > pk * undb(lead_db))[0]
    off = np.nonzero(a > pk * undb(tail_db))[0]
    y = x[on[0]: off[-1] + 1]
    return fade_edges(y, SR, 0.0003, fade_out)


# ================================================================= weapons
def p9_fire():
    r = _rng("p9")
    out = np.zeros(_n(0.4))
    place(out, sweep_sine(190, 65, 0.12, 0.018, 0.045), 0, 0.9)
    place(out, nburst(r, 0.12, 0.03, lo=150, hi=1300), 0, 0.9)
    place(out, bpburst(r, 0.05, 0.006, 2600, q=1.5), 0, 0.35)
    place(out, bpburst(r, 0.08, 0.018, 650, q=2.5), 0.002, 0.5)
    # slide travel + return clicks
    place(out, click(r, 3400, 0.007, 0.06, 0.6), 0.048, 0.28)
    place(out, click(r, 2700, 0.009, 0.06, 0.5), 0.082, 0.33)
    y = room(drive(out, 1.5), rt=0.3, mix=0.12, seed=4)
    return y


def vk12_fire():
    r = _rng("vk12")
    out = np.zeros(_n(0.55))
    place(out, nburst(r, 0.06, 0.009, lo=1500, attack=0.0001), 0, 1.3)
    place(out, sweep_sine(170, 55, 0.2, 0.02, 0.07), 0, 1.0)
    place(out, bpburst(r, 0.15, 0.04, 950, q=1.2), 0, 0.9)
    place(out, nburst(r, 0.4, 0.12, hi=2200), 0.01, 0.35)
    place(out, click(r, 3100, 0.006, 0.05, 0.4), 0.06, 0.12)
    y = drive(out, 2.6)
    return room(y, rt=0.45, mix=0.18, seed=5)


def talon12_fire():
    r = _rng("talon12")
    out = np.zeros(_n(1.3))
    place(out, nburst(r, 0.08, 0.014, lo=900, attack=0.0001), 0, 1.3)
    place(out, sweep_sine(95, 36, 0.8, 0.05, 0.25), 0, 1.4)
    n = _n(0.9)
    t = _t(n)
    blast = svf(noise(n, r), 300 + 4200 * np.exp(-t / 0.08), SR, 0.7) * env_exp(n, 0.2, 0.0008)
    place(out, blast, 0, 1.5)
    place(out, nburst(r, 1.2, 0.4, hi=220), 0.01, 0.9)
    y = drive(out, 2.2)
    return room(y, rt=0.9, mix=0.2, seed=6)


def _clack(r, base, heavy=1.0):
    out = np.zeros(_n(0.12))
    place(out, bpburst(r, 0.03, 0.004, 2600, q=1.2), 0, 0.8)
    place(out, modal([base, base * 2.37, base * 3.91], [1.0, 0.6, 0.35], [0.03, 0.02, 0.012], 0.12, r), 0, 0.5)
    place(out, sweep_sine(220, 150, 0.05, 0.01, 0.015), 0, 0.6 * heavy)
    return out


def _scrape(r, dur, fc=4000, level=0.25):
    n = _n(dur)
    t = _t(n)
    x = svf(noise(n, r), fc, SR, 1.2, "bp")
    grit = (r.random(n) < 0.02) * r.uniform(-1, 1, n)
    x = x + svf(grit, 3000, SR, 1.0, "hp") * 2
    return x * np.sin(np.pi * t / dur) * level


def talon12_pump():
    r = _rng("pump")
    out = np.zeros(_n(0.45))
    place(out, _scrape(r, 0.1, 3500, 0.2), 0.0)
    place(out, _clack(r, 1150, 1.0), 0.09)
    place(out, _scrape(r, 0.09, 3000, 0.2), 0.17)
    place(out, _clack(r, 1300, 1.3), 0.25, 1.1)
    return room(out, rt=0.25, mix=0.1, seed=7)


def reload():
    r = _rng("reload")
    out = np.zeros(_n(1.05))
    place(out, click(r, 3600, 0.005, 0.04, 0.5), 0.0, 0.5)          # mag release
    place(out, _scrape(r, 0.14, 2600, 0.22), 0.04)                    # mag out
    place(out, _clack(r, 900, 0.5), 0.17, 0.5)
    place(out, _scrape(r, 0.1, 3000, 0.25), 0.42)                     # mag in
    place(out, _clack(r, 1050, 1.2), 0.52, 0.9)
    place(out, _scrape(r, 0.08, 4200, 0.2), 0.74)                     # slide back
    place(out, click(r, 2900, 0.01, 0.06, 0.6), 0.8, 0.6)
    place(out, _clack(r, 1400, 0.7), 0.9, 0.75)                       # slide forward
    return room(out, rt=0.25, mix=0.1, seed=8)


def dry_fire():
    r = _rng("dry")
    out = np.zeros(_n(0.12))
    place(out, click(r, 3300, 0.008, 0.08, 0.5), 0)
    place(out, sweep_sine(260, 180, 0.04, 0.01, 0.01), 0, 0.3)
    return out


def weapon_switch():
    r = _rng("switch")
    out = np.zeros(_n(0.45))
    n = _n(0.22)
    t = _t(n)
    cloth = svf(noise(n, r), 1200, SR, 0.6, "bp") * np.sin(np.pi * t / 0.22) ** 2
    place(out, cloth, 0, 0.35)
    for k, tt in enumerate((0.05, 0.09, 0.12)):
        place(out, click(r, 2400 + 500 * k, 0.004, 0.04, 0.3), tt, 0.15)
    place(out, _clack(r, 1250, 0.8), 0.2, 0.7)
    place(out, click(r, 3800, 0.006, 0.05, 0.5), 0.27, 0.3)
    return room(out, rt=0.2, mix=0.08, seed=9)


# ================================================================= impacts
def impact_concrete():
    r = _rng("concrete")
    out = np.zeros(_n(0.4))
    place(out, bpburst(r, 0.12, 0.03, 1800, q=0.9), 0, 1.0)
    place(out, nburst(r, 0.3, 0.07, lo=1500, hi=6000), 0.005, 0.12)   # dust hiss
    place(out, nburst(r, 0.04, 0.003, lo=3000), 0, 0.8)
    place(out, sweep_sine(160, 110, 0.06, 0.01, 0.02), 0, 0.5)
    for k in range(10):
        tt = 0.03 + r.exponential(0.07)
        if tt < 0.35:
            place(out, nburst(r, 0.012, 0.0025, lo=2500) * r.uniform(0.1, 0.35) * math.exp(-tt / 0.15), tt)
    return drive(out, 1.4)


def impact_metal():
    r = _rng("metal")
    out = np.zeros(_n(0.7))
    base = 1450.0
    place(out, nburst(r, 0.02, 0.002, lo=2000), 0, 0.9)
    place(out, modal([base, base * 2.32, base * 3.87, base * 5.21, base * 0.61],
                     [1.0, 0.7, 0.45, 0.3, 0.4], [0.28, 0.18, 0.1, 0.06, 0.12], 0.7, r, detune=0.004), 0, 0.55)
    place(out, bpburst(r, 0.05, 0.01, 3000, 1.0), 0, 0.5)
    return out


def impact_flesh():
    r = _rng("flesh")
    out = np.zeros(_n(0.25))
    place(out, nburst(r, 0.15, 0.035, hi=450), 0, 1.4)
    place(out, sweep_sine(120, 80, 0.15, 0.02, 0.05), 0, 0.8)
    place(out, bpburst(r, 0.03, 0.006, 1100, 1.5), 0, 0.25)
    return drive(out, 1.3)


def guard_death():
    r = _rng("death")
    out = np.zeros(_n(1.0))
    n = _n(0.35)
    t = _t(n)
    place(out, svf(noise(n, r), 1500, SR, 0.5, "bp") * np.sin(np.pi * t / 0.35) ** 2, 0.0, 0.18)   # cloth
    place(out, nburst(r, 0.2, 0.04, hi=350), 0.05, 0.8)                                             # knees
    place(out, sweep_sine(90, 60, 0.2, 0.02, 0.05), 0.05, 0.5)
    place(out, nburst(r, 0.4, 0.07, hi=300), 0.33, 1.3)                                             # torso
    place(out, sweep_sine(75, 45, 0.35, 0.03, 0.09), 0.33, 1.0)
    place(out, nburst(r, 0.15, 0.03, hi=500), 0.47, 0.45)                                           # arm
    for k in range(4):                                                                              # gear rattle
        place(out, click(r, 2100 + 400 * k, 0.006, 0.04, 0.3), 0.34 + 0.025 * k + r.uniform(0, 0.01), 0.1)
    return room(drive(out, 1.3), rt=0.3, mix=0.1, seed=10)


def footstep(k):
    r = _rng(f"step{k}")
    out = np.zeros(_n(0.28))
    pitch = [1.0, 0.92, 1.08][k - 1]
    place(out, nburst(r, 0.1, 0.022, hi=420 * pitch), 0, 1.0)
    place(out, sweep_sine(110 * pitch, 80 * pitch, 0.08, 0.01, 0.02), 0, 0.5)
    toe = 0.05 + 0.012 * (k - 2)
    place(out, bpburst(r, 0.06, 0.018, 2300 * pitch, 1.0), toe, 0.22)
    place(out, nburst(r, 0.08, 0.02, lo=3500), toe, 0.08)
    for g in range(3):
        place(out, nburst(r, 0.01, 0.002, lo=4000) * 0.1, toe + r.uniform(0, 0.05))
    return out


# ================================================================= world / feedback
def alarm_siren():
    """Seamless 2.0 s hi-lo siren loop (two 0.5 s tones, twice)."""
    n = _n(2.0)
    t = _t(n)
    hi, lo = 988.0, 740.0
    seg = (t // 0.5).astype(int) % 2
    target = np.where(seg == 0, hi, lo)
    # smooth tone changes (circular one-pole via FFT low-pass on the control signal)
    f = fft_filter(target, SR, lp_resp(40.0, 1), circular=True)
    # force an integer number of cycles over the loop so the phase wraps exactly
    cyc = f.sum() / SR
    f *= round(cyc) / cyc
    ph = np.concatenate(([0.0], np.cumsum(f[:-1]) / SR))
    x = np.zeros(n)
    for k, a in ((1, 1.0), (3, 0.45), (5, 0.25), (7, 0.12), (9, 0.06)):
        mask = (f * k < SR * 0.45).astype(float)
        x += a * mask * np.sin(TWO_PI * k * ph)
    # second horn a few cents up, also integer cycles
    f2 = f * 1.006
    cyc2 = f2.sum() / SR
    f2 *= round(cyc2) / cyc2
    ph2 = np.concatenate(([0.0], np.cumsum(f2[:-1]) / SR))
    for k, a in ((1, 0.6), (3, 0.25), (5, 0.12)):
        x += a * np.sin(TWO_PI * k * ph2)
    x = np.tanh(x * 1.2)
    # horn/speaker colouration, circular so the loop stays seamless
    x = fft_filter(x, SR, bp_resp(400, 3500, 2), circular=True)
    return x


def pickup_ammo():
    r = _rng("ammo")
    out = np.zeros(_n(0.4))
    place(out, _clack(r, 1500, 0.6), 0.0, 0.8)
    place(out, click(r, 3200, 0.008, 0.05, 0.5), 0.06, 0.6)
    n = _n(0.3)
    t = _t(n)
    place(out, np.sign(np.sin(TWO_PI * 1760 * t)) * 0.2 * np.exp(-t / 0.05), 0.05, 0.35)
    return room(out, rt=0.2, mix=0.1, seed=12)


def pickup_armor():
    r = _rng("armor")
    out = np.zeros(_n(0.7))
    n = _n(0.2)
    t = _t(n)
    whoosh = svf(noise(n, r), 600 + 3000 * t / 0.2, SR, 1.5, "bp") * np.sin(np.pi * t / 0.2) ** 2
    place(out, whoosh, 0, 0.6)
    for k, (m, tt) in enumerate(((76, 0.08), (83, 0.17))):
        f = float(mtof(m))
        nn = _n(0.5)
        tn = _t(nn)
        mod = 1.8 * np.exp(-tn / 0.1) * np.sin(TWO_PI * f * 2.0 * tn)
        place(out, np.sin(TWO_PI * f * tn + mod) * env_exp(nn, 0.14, 0.002), tt, 0.45)
    return room(out, rt=0.4, mix=0.15, seed=13)


def player_hurt():
    r = _rng("hurt")
    out = np.zeros(_n(0.45))
    place(out, nburst(r, 0.2, 0.05, hi=600), 0, 1.2)
    place(out, sweep_sine(140, 60, 0.35, 0.08, 0.1, attack=0.002), 0, 1.0)
    n = _n(0.3)
    t = _t(n)
    grit = svf(noise(n, r), 900, SR, 3.0, "bp") * np.exp(-t / 0.06)
    place(out, grit, 0.005, 0.3)
    return drive(out, 2.0)


def _beep(freq, dur, square=0.3):
    n = _n(dur)
    t = _t(n)
    x = np.sin(TWO_PI * freq * t) + square * np.sin(TWO_PI * 3 * freq * t) / 3 + square * np.sin(TWO_PI * 5 * freq * t) / 5
    return fade_edges(x, SR, 0.002, 0.006)


def charge_plant():
    r = _rng("plant")
    out = np.zeros(_n(1.35))
    place(out, _clack(r, 900, 1.2), 0, 0.9)                 # magnetic clamp
    place(out, click(r, 3000, 0.006, 0.05, 0.3), 0.05, 0.4)
    for k, tt in enumerate((0.3, 0.48, 0.66)):
        place(out, _beep(1800 + 200 * k, 0.07), tt, 0.35)
    place(out, _beep(2600, 0.35), 0.86, 0.4)                # armed
    return room(out, rt=0.25, mix=0.08, seed=14)


def charge_beep():
    return _beep(2400, 0.075) * 0.5


def explosion():
    r = _rng("explosion")
    out = np.zeros(_n(2.6))
    place(out, nburst(r, 0.1, 0.02, lo=700, attack=0.0001), 0, 1.4)
    place(out, sweep_sine(75, 26, 1.6, 0.12, 0.5), 0, 1.6)
    n = _n(2.2)
    t = _t(n)
    blast = svf(noise(n, r), 150 + 5000 * np.exp(-t / 0.18), SR, 0.7) * env_exp(n, 0.45, 0.004)
    place(out, blast, 0, 1.6)
    rumble = svf(svf(noise(_n(2.5), r), 110, SR, 0.7), 110, SR, 0.7)
    place(out, rumble * env_exp(len(rumble), 0.8, 0.05), 0, 4.0)
    for k in range(28):
        tt = 0.12 + r.exponential(0.45)
        if tt < 2.2:
            place(out, bpburst(r, 0.03, r.uniform(0.003, 0.008), r.uniform(1500, 5000), 1.5)
                  * r.uniform(0.05, 0.3) * math.exp(-tt / 0.8), tt)
    y = drive(out, 2.0)
    y = room(y, rt=1.2, mix=0.2, seed=15, length=1.6)[: _n(2.5)]
    n = len(y)
    fo = _n(0.6)
    y[n - fo:] *= np.linspace(1, 0, fo) ** 2
    return y


def objective_complete():
    out = np.zeros(_n(1.1))
    for m, tt in ((79, 0.0), (84, 0.09), (88, 0.18)):
        f = float(mtof(m))
        nn = _n(0.9)
        tn = _t(nn)
        mod = 1.6 * np.exp(-tn / 0.25) * np.sin(TWO_PI * f * 3.5 * tn)
        x = np.sin(TWO_PI * f * tn + mod) * np.exp(-tn / 0.35)
        x += 0.25 * np.sin(TWO_PI * f * 2 * tn) * np.exp(-tn / 0.15)
        place(out, fade_edges(x, SR, 0.001, 0.02), tt, 0.4)
    return room(out, rt=0.6, mix=0.2, seed=16)


def menu_move():
    n = _n(0.05)
    t = _t(n)
    x = np.sign(np.sin(TWO_PI * 1320 * t)) * np.exp(-t / 0.015)
    return fade_edges(svf(x, 5000, SR, 0.7), SR, 0.0005, 0.005)


def menu_select():
    out = np.zeros(_n(0.2))
    for f, tt in ((990, 0.0), (1480, 0.055)):
        n = _n(0.07)
        t = _t(n)
        x = np.sign(np.sin(TWO_PI * f * t)) * np.exp(-t / 0.03)
        place(out, fade_edges(svf(x, 5500, SR, 0.7), SR, 0.0005, 0.006), tt)
    return room(out, rt=0.2, mix=0.1, seed=17)


def _chirp(f0, f1, dur):
    n = _n(dur)
    t = _t(n)
    f = f0 * (f1 / f0) ** (t / dur)
    ph = np.cumsum(f) / SR
    x = np.sin(TWO_PI * ph) + 0.3 * np.sign(np.sin(TWO_PI * ph))
    return fade_edges(x * (0.6 + 0.4 * np.exp(-t / 0.05)), SR, 0.002, 0.01)


def pda_open():
    r = _rng("pdaopen")
    out = np.zeros(_n(0.3))
    place(out, click(r, 3500, 0.004, 0.03, 0.3), 0, 0.5)
    place(out, _chirp(600, 1800, 0.12), 0.01, 0.4)
    place(out, _beep(2100, 0.05, 0.6), 0.14, 0.3)
    place(out, _beep(2800, 0.05, 0.6), 0.2, 0.25)
    return svf(out, 6000, SR, 0.7)


def pda_close():
    r = _rng("pdaclose")
    out = np.zeros(_n(0.25))
    place(out, _beep(2400, 0.04, 0.6), 0, 0.25)
    place(out, _chirp(1700, 500, 0.12), 0.04, 0.4)
    place(out, click(r, 3000, 0.005, 0.03, 0.3), 0.17, 0.5)
    return svf(out, 6000, SR, 0.7)


# ================================================================= registry + levelling
# name -> (builder, target max momentary loudness LUFS, trim leading silence?)
SFX = {
    "p9_fire":            (p9_fire, -17.0, True),
    "vk12_fire":          (vk12_fire, -11.5, True),
    "talon12_fire":       (talon12_fire, -9.5, True),
    "talon12_pump":       (talon12_pump, -18.0, True),
    "reload":             (reload, -19.0, True),
    "dry_fire":           (dry_fire, -22.0, True),
    "weapon_switch":      (weapon_switch, -20.0, True),
    "impact_concrete":    (impact_concrete, -17.0, True),
    "impact_metal":       (impact_metal, -17.0, True),
    "impact_flesh":       (impact_flesh, -17.0, True),
    "guard_death":        (guard_death, -16.0, True),
    "footstep_1":         (lambda: footstep(1), -23.0, True),
    "footstep_2":         (lambda: footstep(2), -23.0, True),
    "footstep_3":         (lambda: footstep(3), -23.0, True),
    "alarm_siren":        (alarm_siren, -16.0, False),
    "pickup_ammo":        (pickup_ammo, -18.0, True),
    "pickup_armor":       (pickup_armor, -18.0, True),
    "player_hurt":        (player_hurt, -15.0, True),
    "charge_plant":       (charge_plant, -18.0, True),
    "charge_beep":        (charge_beep, -21.0, True),
    "explosion":          (explosion, -9.0, True),
    "objective_complete": (objective_complete, -17.0, True),
    "menu_move":          (menu_move, -25.0, True),
    "menu_select":        (menu_select, -22.0, True),
    "pda_open":           (pda_open, -22.0, True),
    "pda_close":          (pda_close, -22.0, True),
}
LOOPING_SFX = {"alarm_siren"}
MAX_GR = {"p9_fire": 8.0, "vk12_fire": 10.0, "talon12_fire": 10.0, "explosion": 10.0,
          "impact_concrete": 8.0, "impact_metal": 8.0, "impact_flesh": 8.0}
CEILING_DB = -1.3


def build(name):
    fn, target, do_trim = SFX[name]
    x = np.asarray(fn(), dtype=float)
    loop = name in LOOPING_SFX
    if not loop:
        x = fft_filter(x, SR, hp_resp(25, 2))
    if do_trim:
        x = trim(x)
    x = x / (np.max(np.abs(x)) + 1e-12) * 0.5
    gain = target - lufs_momentary_max(x, SR)
    # allow a bounded amount of peak limiting to reach the target (more for punchy one-shots)
    max_gr = MAX_GR.get(name, 6.0)
    headroom = CEILING_DB - peak_db(x * undb(gain))
    if headroom < -max_gr:
        gain += headroom + max_gr
    y = x * undb(gain)
    if peak_db(y) > CEILING_DB:
        y = limiter(y, SR, CEILING_DB - 0.1, lookahead=0.0015, release=0.05, circular=loop)
    y = np.clip(y, -undb(CEILING_DB - 0.05), undb(CEILING_DB - 0.05))
    if not loop:
        y = fade_edges(y, SR, 0.0002, 0.004)
    return y
