"""Small from-scratch DSP toolkit for Goldmember 69 audio (numpy only).

Everything here is synthesised: oscillators, envelopes, filters, Karplus-Strong,
FM, noise, reverb, limiter, loudness metering and OGG export via ffmpeg.
"""
import math
import subprocess

import numpy as np

TWO_PI = 2.0 * math.pi

# ---------------------------------------------------------------- pitch utils
_NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_to_midi(name):
    """'C4' -> 60, 'F#3', 'Bb2', 'Eb5'."""
    letter = name[0].upper()
    rest = name[1:]
    acc = 0
    while rest and rest[0] in "#b":
        acc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    octave = int(rest)
    return 12 * (octave + 1) + _NOTE_BASE[letter] + acc


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def db(x):
    return 20.0 * math.log10(max(x, 1e-12))


def undb(d):
    return 10.0 ** (d / 20.0)


# ---------------------------------------------------------------- envelopes
def adsr(n, sr, a, d, s, r, hold):
    """ADSR envelope of n samples. `hold` = seconds the gate is held."""
    t = np.arange(n) / sr
    env = np.empty(n)
    a = max(a, 1e-4)
    d = max(d, 1e-4)
    r = max(r, 1e-4)
    att = t < a
    env[att] = t[att] / a
    dec = ~att
    env[dec] = s + (1.0 - s) * np.exp(-(t[dec] - a) / (d / 4.0))
    # level at gate-off
    if hold < a:
        lvl = hold / a
    else:
        lvl = s + (1.0 - s) * math.exp(-(hold - a) / (d / 4.0))
    rel = t >= hold
    env[rel] = lvl * np.exp(-(t[rel] - hold) / (r / 5.0))
    return env


def exp_decay(n, sr, tau):
    return np.exp(-np.arange(n) / (sr * tau))


def fade_edges(x, sr, fin=0.001, fout=0.005):
    n = len(x)
    a = min(n, max(1, int(fin * sr)))
    b = min(n, max(1, int(fout * sr)))
    x = x.copy()
    x[:a] *= np.linspace(0, 1, a)
    x[n - b:] *= np.linspace(1, 0, b)
    return x


# ---------------------------------------------------------------- oscillators
def phase(freq, n, sr, ph0=0.0):
    if np.isscalar(freq):
        return (ph0 + np.arange(n) * (freq / sr)) % 1.0
    inc = np.asarray(freq, dtype=float) / sr
    ph = np.concatenate(([0.0], np.cumsum(inc[:-1])))
    return (ph0 + ph) % 1.0


def _polyblep(ph, dt):
    out = np.zeros_like(ph)
    dt = np.broadcast_to(dt, ph.shape)
    m = ph < dt
    t = ph[m] / dt[m]
    out[m] = t + t - t * t - 1.0
    m = ph > 1.0 - dt
    t = (ph[m] - 1.0) / dt[m]
    out[m] = t * t + t + t + 1.0
    return out


def saw(freq, n, sr, ph0=0.0):
    ph = phase(freq, n, sr, ph0)
    dt = np.broadcast_to(np.asarray(freq, dtype=float) / sr, ph.shape)
    return 2.0 * ph - 1.0 - _polyblep(ph, dt)


def pulse(freq, n, sr, width=0.5, ph0=0.0):
    ph = phase(freq, n, sr, ph0)
    dt = np.broadcast_to(np.asarray(freq, dtype=float) / sr, ph.shape)
    s1 = 2.0 * ph - 1.0 - _polyblep(ph, dt)
    ph2 = (ph + width) % 1.0
    s2 = 2.0 * ph2 - 1.0 - _polyblep(ph2, dt)
    return s1 - s2 - (1.0 - 2.0 * width) * 0  # DC left in; removed by callers' HP


def sine(freq, n, sr, ph0=0.0):
    return np.sin(TWO_PI * phase(freq, n, sr, ph0))


def tri(freq, n, sr, ph0=0.0):
    ph = phase(freq, n, sr, ph0)
    return 1.0 - 4.0 * np.abs(ph - 0.5)


def fm_op(freq, n, sr, mod=None, ph0=0.0):
    """Sine operator with phase-modulation input `mod` (radians)."""
    ph = TWO_PI * phase(freq, n, sr, ph0)
    if mod is not None:
        ph = ph + mod
    return np.sin(ph)


def noise(n, rng):
    return rng.uniform(-1.0, 1.0, n)


# ---------------------------------------------------------------- filters
def svf(x, fc, sr, q=0.707, mode="lp"):
    """TPT state-variable filter (Simper). fc may be scalar or per-sample."""
    n = len(x)
    fc = np.clip(np.broadcast_to(np.asarray(fc, dtype=float), (n,)), 10.0, sr * 0.45)
    g = np.tan(math.pi * fc / sr)
    k = 1.0 / q
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    ic1 = ic2 = 0.0
    lp = [0.0] * n
    bp = [0.0] * n
    for i, (v0, c1, c2, c3) in enumerate(zip(x.tolist(), a1.tolist(), a2.tolist(), a3.tolist())):
        v3 = v0 - ic2
        v1 = c1 * ic1 + c2 * v3
        v2 = ic2 + c2 * ic1 + c3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        lp[i] = v2
        bp[i] = v1
    lp = np.array(lp)
    bp = np.array(bp)
    if mode == "lp":
        return lp
    if mode == "bp":
        return bp
    if mode == "hp":
        return x - k * bp - lp
    if mode == "notch":
        return x - k * bp
    raise ValueError(mode)


def onepole_lp(x, fc, sr):
    a = 1.0 - math.exp(-TWO_PI * fc / sr)
    y = 0.0
    out = [0.0] * len(x)
    for i, v in enumerate(x.tolist()):
        y += a * (v - y)
        out[i] = y
    return np.array(out)


def onepole_hp(x, fc, sr):
    return x - onepole_lp(x, fc, sr)


def fft_filter(x, sr, fn, circular=False):
    """Zero-phase filter by magnitude response fn(freq_hz_array)->gain.
    Works on 1-D or (n, ch). circular=True treats x as a loop."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    pad = 0 if circular else min(n, int(sr * 0.25))
    m = n + pad
    nfft = 1 << (m - 1).bit_length() if not circular else n
    X = np.fft.rfft(x, n=nfft, axis=0)
    f = np.fft.rfftfreq(nfft, 1.0 / sr)
    H = fn(f)
    if X.ndim == 2:
        H = H[:, None]
    y = np.fft.irfft(X * H, n=nfft, axis=0)
    return y[:n]


def lp_resp(fc, order=2):
    return lambda f: 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order))


def hp_resp(fc, order=2):
    return lambda f: 1.0 / np.sqrt(1.0 + (np.maximum(f, 1e-3) / fc) ** (-2 * order))


def bp_resp(lo, hi, order=2):
    l, h = hp_resp(lo, order), lp_resp(hi, order)
    return lambda f: l(f) * h(f)


def shelf_resp(fc, gain_db, high=True):
    g = undb(gain_db)

    def fn(f):
        r = (f / fc) ** 2
        w = r / (1.0 + r) if high else 1.0 / (1.0 + r)
        return 1.0 + (g - 1.0) * w
    return fn


def peak_resp(fc, gain_db, width_oct=1.0):
    g = undb(gain_db)

    def fn(f):
        o = np.log2(np.maximum(f, 1.0) / fc) / (width_oct / 2.0)
        return 1.0 + (g - 1.0) * np.exp(-0.5 * o * o * 2.0)
    return fn


def chain(*fns):
    def fn(f):
        out = np.ones_like(f)
        for g in fns:
            out = out * g(f)
        return out
    return fn


def drive(x, amount):
    """tanh saturation normalised to keep small-signal gain ~1."""
    return np.tanh(x * amount) / math.tanh(amount) if amount > 0 else x


# ---------------------------------------------------------------- Karplus-Strong
def karplus(freq, dur, sr, rng, decay=0.996, bright=0.5, excite=None, pick_pos=0.2):
    """Plucked string. Rendered at an integer period then resampled to exact pitch."""
    n_out = int(dur * sr)
    period = max(2, int(math.floor(sr / freq - 0.5)))
    actual = sr / (period + 0.5)
    ratio = freq / actual
    n = int(n_out * ratio) + period + 4
    if excite is None:
        ex = rng.uniform(-1, 1, period)
        # brightness: smooth the excitation
        if bright < 1.0:
            a = bright
            y = 0.0
            for i in range(period):
                y += a * (ex[i] - y)
                ex[i] = y
        # pick position comb (removes some harmonics like a real pluck point)
        d = max(1, int(period * pick_pos))
        ex = ex - np.roll(ex, d)
        ex -= ex.mean()
    else:
        ex = excite
    y = np.zeros(n + period + 1)
    y[1:period + 1] = ex[:period]
    # y[i] = decay * 0.5*(y[i-P] + y[i-P-1]) for i > P, block-vectorised
    base = period + 1
    i = base
    while i < n + 1:
        j = min(i + period, n + 1)
        y[i:j] = decay * 0.5 * (y[i - period:j - period] + y[i - period - 1:j - period - 1])
        i = j
    y = y[1:]
    # resample to exact pitch
    pos = np.arange(n_out) * ratio
    out = np.interp(pos, np.arange(len(y)), y)
    return out


# ---------------------------------------------------------------- reverb
def make_ir(sr, length=2.0, rt_low=1.8, rt_high=0.7, predelay=0.012, seed=7,
            early=True, width=1.0):
    """Stereo reverb impulse response built from band-split decaying noise."""
    rng = np.random.default_rng(seed)
    n = int(length * sr)
    t = np.arange(n) / sr
    out = np.zeros((n, 2))
    bands = [(0, 400, rt_low * 1.05), (400, 2500, (rt_low + rt_high) / 2), (2500, sr / 2, rt_high)]
    for ch in range(2):
        nz = rng.standard_normal(n)
        spec = np.fft.rfft(nz)
        f = np.fft.rfftfreq(n, 1.0 / sr)
        acc = np.zeros(n)
        for lo, hi, rt in bands:
            m = (f >= lo) & (f < hi)
            s = np.zeros_like(spec)
            s[m] = spec[m]
            band = np.fft.irfft(s, n=n)
            acc += band * np.exp(-6.9078 * t / rt)  # -60 dB at rt
        # soft onset
        acc *= 1.0 - np.exp(-t / 0.008)
        out[:, ch] = acc
    if width < 1.0:
        mid = out.mean(axis=1, keepdims=True)
        out = mid + (out - mid) * width
    if early:
        for ch in range(2):
            for k in range(10):
                d = int((predelay + rng.uniform(0.004, 0.06)) * sr)
                if d < n:
                    out[d, ch] += rng.uniform(-1, 1) * 2.5 * (1 - k / 12)
    pd = int(predelay * sr)
    out = np.concatenate([np.zeros((pd, 2)), out])[:n]
    out /= np.sqrt(np.sum(out ** 2) / 2)
    return out


def convolve(x, ir):
    """x: (n,) or (n,2); ir: (m,2). Returns (n+m-1, 2)."""
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    n = len(x) + len(ir) - 1
    nfft = 1 << (n - 1).bit_length()
    out = np.zeros((n, 2))
    for ch in range(2):
        X = np.fft.rfft(x[:, ch], nfft)
        H = np.fft.rfft(ir[:, ch], nfft)
        out[:, ch] = np.fft.irfft(X * H, nfft)[:n]
    return out


def convolve_mono(x, ir):
    n = len(x) + len(ir) - 1
    nfft = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:n]


# ---------------------------------------------------------------- loudness (BS.1770)
def _k_resp(sr):
    def biquad_mag(b, a, f):
        z = np.exp(-1j * TWO_PI * f / sr)
        return np.abs((b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z))

    # high shelf
    G, Q, fc = 3.99984385397, 0.7071752369554193, 1681.9744509555319
    A = 10 ** (G / 40.0)
    w0 = TWO_PI * fc / sr
    al = math.sin(w0) / (2 * Q)
    c = math.cos(w0)
    b1 = [A * ((A + 1) + (A - 1) * c + 2 * math.sqrt(A) * al),
          -2 * A * ((A - 1) + (A + 1) * c),
          A * ((A + 1) + (A - 1) * c - 2 * math.sqrt(A) * al)]
    a1 = [(A + 1) - (A - 1) * c + 2 * math.sqrt(A) * al,
          2 * ((A - 1) - (A + 1) * c),
          (A + 1) - (A - 1) * c - 2 * math.sqrt(A) * al]
    Q, fc = 0.5003270373253953, 38.13547087613982
    w0 = TWO_PI * fc / sr
    al = math.sin(w0) / (2 * Q)
    c = math.cos(w0)
    b2 = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    a2 = [1 + al, -2 * c, 1 - al]
    return lambda f: biquad_mag(b1, a1, f) * biquad_mag(b2, a2, f)


def k_weight(x, sr):
    return fft_filter(x, sr, _k_resp(sr))


def lufs_integrated(x, sr):
    if x.ndim == 1:
        x = x[:, None]
    y = k_weight(x, sr)
    blk = int(0.4 * sr)
    hop = int(0.1 * sr)
    if len(y) < blk:
        ms = np.mean(y ** 2, axis=0).sum()
        return -0.691 + 10 * math.log10(max(ms, 1e-20))
    cs = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y ** 2, axis=0)])
    starts = np.arange(0, len(y) - blk + 1, hop)
    ms = ((cs[starts + blk] - cs[starts]) / blk).sum(axis=1)
    lk = -0.691 + 10 * np.log10(np.maximum(ms, 1e-20))
    g = ms[lk > -70]
    if len(g) == 0:
        return -70.0
    rel = -0.691 + 10 * math.log10(g.mean()) - 10
    g2 = ms[(lk > -70) & (lk > rel)]
    return -0.691 + 10 * math.log10(g2.mean())


def lufs_momentary_max(x, sr):
    if x.ndim == 1:
        x = x[:, None]
    y = k_weight(x, sr)
    blk = int(0.4 * sr)
    if len(y) < blk:
        y = np.concatenate([y, np.zeros((blk - len(y), y.shape[1]))])
    cs = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y ** 2, axis=0)])
    hop = max(1, int(0.01 * sr))
    starts = np.arange(0, len(y) - blk + 1, hop)
    ms = ((cs[starts + blk] - cs[starts]) / blk).sum(axis=1)
    return -0.691 + 10 * math.log10(max(ms.max(), 1e-20))


# ---------------------------------------------------------------- limiter
def limiter(x, sr, ceiling_db=-3.0, lookahead=0.004, release=0.12, circular=False):
    """Look-ahead brickwall limiter. x: (n,) or (n,ch)."""
    mono = x.ndim == 1
    if mono:
        x = x[:, None]
    n = len(x)
    pad = int(2.0 * sr) if circular else 0
    if circular:
        xe = np.concatenate([x[-pad:], x, x[:pad]])
    else:
        xe = x
    thr = undb(ceiling_db)
    peak = np.max(np.abs(xe), axis=1)
    graw = np.minimum(1.0, thr / np.maximum(peak, 1e-12))
    W = max(1, int(lookahead * sr))
    gp = np.concatenate([graw, np.ones(W)])
    gmin = np.lib.stride_tricks.sliding_window_view(gp, W + 1).min(axis=1)[:len(graw)]
    # release smoothing (instant attack)
    rc = 1.0 - math.exp(-1.0 / (release * sr))
    g = 1.0
    out = [0.0] * len(gmin)
    for i, v in enumerate(gmin.tolist()):
        if v < g:
            g = v
        else:
            g += (v - g) * rc
        out[i] = g
    g2 = np.array(out)
    # trailing moving average over W+1 samples -> smooth attack, never overshoots
    cs = np.concatenate([[0.0], np.cumsum(np.concatenate([np.ones(W), g2]))])
    idx = np.arange(len(g2))
    g3 = (cs[idx + W + 1] - cs[idx]) / (W + 1)
    y = xe * g3[:, None]
    if circular:
        y = y[pad:pad + n]
    return y[:, 0] if mono else y


def peak_db(x):
    return db(float(np.max(np.abs(x))))


# ---------------------------------------------------------------- export
def write_ogg(path, x, sr, quality=5):
    x = np.asarray(x, dtype=np.float32)
    ch = 1 if x.ndim == 1 else x.shape[1]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "f32le", "-ar", str(sr), "-ac", str(ch), "-i", "-",
           "-c:a", "libvorbis", "-q:a", str(quality),
           "-fflags", "+bitexact", "-flags:a", "+bitexact", "-map_metadata", "-1", str(path)]
    subprocess.run(cmd, input=np.ascontiguousarray(x).tobytes(), check=True)


def read_audio(path, sr=None):
    """Decode any file with ffmpeg to float32 (n, ch)."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=channels,sample_rate", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    fsr, ch = int(probe[0]), int(probe[1])
    if sr is None:
        sr = fsr
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).reshape(-1, ch)
    return a, sr
