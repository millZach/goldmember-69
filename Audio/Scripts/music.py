"""Original compositions for Goldmember 69, written as readable pattern data.

Pattern notation (one token per grid step, '|' is a visual bar line only):
    C5   note onset          C5!  accented        C5'  soft/ghost
    -    hold previous note  .    rest
Bass lines use chord-relative degree tokens instead of note names:
    r root  f fifth  o octave  t third  s seventh  T third-up-an-octave  u fifth-up-an-octave
Drum lines: X accent, x normal, g ghost, o open hat, . rest.

All melodies, bass lines and progressions in this file are original.
"""
import math

import numpy as np

import instruments as ins
from synth import (chain, convolve, fade_edges, fft_filter, hp_resp, limiter, lp_resp, lufs_integrated,
                   make_ir, note_to_midi, peak_resp, shelf_resp, undb)

SR = 32000


# ================================================================= sequencing helpers
def parse_line(s):
    """Return (events, n_steps); events = [start_step, length_steps, token, vel]."""
    toks = s.replace("|", " ").split()
    events = []
    cur = None
    for i, tok in enumerate(toks):
        if tok == "-":
            if cur is not None:
                cur[1] += 1
        elif tok == ".":
            cur = None
        else:
            vel = 1.0
            if tok.endswith("!"):
                vel, tok = 1.2, tok[:-1]
            elif tok.endswith("'"):
                vel, tok = 0.6, tok[:-1]
            cur = [i, 1, tok, vel]
            events.append(cur)
    return events, len(toks)


def parse_drums(s):
    toks = s.replace("|", " ").split()
    vel = {"X": 1.15, "x": 0.9, "g": 0.4, "o": 0.9}
    return [(i, vel[c], c) for i, c in enumerate(toks) if c in vel]


class Mixer:
    def __init__(self, sr, length, tail):
        self.sr = sr
        self.n = int(round(length * sr))
        self.N = self.n + int(tail * sr)
        self.tracks = {}

    def track(self, name, gain_db=0.0, send=0.15, eq=None):
        self.tracks[name] = dict(buf=np.zeros((self.N, 2)), gain=undb(gain_db), send=send, eq=eq)

    def add(self, name, sig, t, pan=0.0, gain=1.0):
        i = int(round(t * self.sr))
        if i >= self.N or i < 0:
            return
        sig = sig[: self.N - i]
        buf = self.tracks[name]["buf"]
        if sig.ndim == 1:
            a = (pan + 1.0) * math.pi / 4.0
            buf[i:i + len(sig), 0] += sig * math.cos(a) * math.sqrt(2) * gain
            buf[i:i + len(sig), 1] += sig * math.sin(a) * math.sqrt(2) * gain
        else:
            buf[i:i + len(sig)] += sig * gain

    def render(self, ir, loop=True, stats=False):
        dry = np.zeros((self.N, 2))
        send = np.zeros((self.N, 2))
        for name, tr in self.tracks.items():
            b = tr["buf"]
            if tr["eq"] is not None:
                b = fft_filter(b, self.sr, tr["eq"])
            b = b * tr["gain"]
            if stats:
                rms = math.sqrt(float(np.mean(b[: self.n] ** 2)) + 1e-20)
                print(f"      track {name:10s} rms {20 * math.log10(rms):6.1f} dB")
            dry += b
            send += b * tr["send"]
        wet = convolve(send, ir)
        full = np.zeros((len(wet), 2))
        full[: self.N] += dry
        full += wet
        if not loop:
            return full
        out = np.zeros((self.n, 2))
        for k in range(0, len(full), self.n):
            seg = full[k:k + self.n]
            out[: len(seg)] += seg
        return out


def master(x, sr, loop, target_lufs=-16.0, ceiling_db=-3.0, eq=None):
    if eq is not None:
        x = fft_filter(x, sr, eq, circular=loop)
    x = x - x.mean(axis=0)
    gain = target_lufs - lufs_integrated(x, sr)
    y = x
    for _ in range(4):
        y = limiter(x * undb(gain), sr, ceiling_db - 0.35, circular=loop)
        err = target_lufs - lufs_integrated(y, sr)
        gain += err
        if abs(err) < 0.05:
            break
    return np.clip(y, -undb(ceiling_db - 0.3), undb(ceiling_db - 0.3))


def trim_tail(x, sr, thresh_db=-60.0, fade=0.3):
    env = np.max(np.abs(x), axis=1)
    idx = np.nonzero(env > undb(thresh_db) * env.max())[0]
    end = min(len(x), (idx[-1] if len(idx) else len(x)) + int(0.05 * sr))
    y = x[:end].copy()
    f = min(end, int(fade * sr))
    y[end - f:] *= np.linspace(1, 0, f)[:, None] ** 2
    return y


# ================================================================= SPILLWAY
# F minor, 118 BPM, 52 bars (~105.8 s). Intro(4) A(16) B(16) A'(8) Breakdown(8).
SP_BPM = 118
SP_CHORDS = {
    # root pc name, third, fifth, seventh, pad voicing, brass voicing, guitar arpeggio voicing
    "Fm":     ("F", 3, 7, 10, ["F3", "Ab3", "C4", "Eb4"], ["C4", "F4", "Ab4"], ["F4", "C5", "Ab4", "F5"]),
    "Dbmaj7": ("Db", 4, 7, 11, ["Db3", "F3", "Ab3", "C4"], ["Db4", "F4", "Ab4", "C5"], ["Db4", "Ab4", "F4", "C5"]),
    "Gbmaj7": ("Gb", 4, 7, 11, ["Gb3", "Bb3", "Db4", "F4"], ["Db4", "F4", "Gb4", "Bb4"], ["Gb4", "Db5", "Bb4", "F5"]),
    "Bbm7":   ("Bb", 3, 7, 10, ["F3", "Ab3", "Bb3", "Db4"], ["Db4", "F4", "Bb4"], ["Bb4", "F5", "Db5", "Ab4"]),
    "C7":     ("C", 4, 7, 10, ["E3", "Bb3", "Db4", "G4"], ["E4", "G4", "Bb4", "Db5"], ["C4", "G4", "E4", "Bb4"]),
    "Db":     ("Db", 4, 7, 12, ["Db3", "F3", "Ab3", "Db4"], ["Db4", "F4", "Ab4"], ["Db4", "Ab4", "F4", "Db5"]),
    "Eb":     ("Eb", 4, 7, 12, ["Eb3", "G3", "Bb3", "Eb4"], ["Eb4", "G4", "Bb4"], ["Eb4", "Bb4", "G4", "Eb5"]),
    "Eb7":    ("Eb", 4, 7, 10, ["Eb3", "G3", "Bb3", "Db4"], ["Db4", "G4", "Bb4"], ["Eb4", "Bb4", "G4", "Db5"]),
    "Cm7":    ("C", 3, 7, 10, ["C3", "Eb3", "G3", "Bb3"], ["Eb4", "G4", "Bb4"], ["C4", "G4", "Eb4", "Bb4"]),
    "Abmaj7": ("Ab", 4, 7, 11, ["C3", "Eb3", "G3", "Ab3"], ["C4", "Eb4", "G4"], ["Ab4", "Eb5", "C5", "G5"]),
    "Gb":     ("Gb", 4, 7, 12, ["Gb3", "Bb3", "Db4", "Gb4"], ["Db4", "Gb4", "Bb4"], ["Gb4", "Db5", "Bb4", "Gb5"]),
}
# lowest bass root for each pitch class (keeps the line between Bb1 and A2)
_BASS_ROOT = {"C": "C2", "Db": "Db2", "D": "D2", "Eb": "Eb2", "E": "E2", "F": "F2", "Gb": "Gb2", "G": "G2",
              "Ab": "Ab2", "A": "A1", "Bb": "Bb1", "B": "B1"}

SP_SECTIONS = [
    ("intro", ["Fm", "Fm", "Fm", "Fm"]),
    ("A", ["Fm", "Fm", "Dbmaj7", "Dbmaj7", "Bbm7", "Bbm7", "C7", "C7",
           "Fm", "Fm", "Dbmaj7", "Gbmaj7", "Bbm7", "Bbm7", "C7", "C7"]),
    ("B", ["Db", "Db", "Eb", "Eb", "Cm7", "Cm7", "Fm", "Fm",
           "Bbm7", "Bbm7", "Eb7", "Eb7", "Abmaj7", "Abmaj7", "C7", "C7"]),
    ("A2", ["Fm", "Fm", "Dbmaj7", "Gbmaj7", "Bbm7", "Bbm7", "C7", "C7"]),
    ("brk", ["Fm", "Fm", "Dbmaj7", "Dbmaj7", "Gb", "Gb", "C7", "C7"]),
]

# Bass: 16th-note grid, chord-relative degrees.
SP_BASS = {
    "intro": "r . . r . . r . r . . r . . f .",
    "A":     "r r o r . r f r r s o r . r f t",
    "A_b":   "r r o r . r f r r . o r f . o f",
    "B":     "r . r r o . r r r . r r o . f f",
    "B_b":   "r r o r r r o r f f u f f f o f",
    "brk":   "r . . o . . r . r . . o . . f .",
}

# Guitar lead (A section melody), 8th-note grid.
SP_LEAD_A = """
C5 - - Ab4 - - F4 G4   | Ab4 - - - - - . .      | F5 - - Eb5 - - C5 Db5 | C5 - - - Ab4 - - -
Db5 - - C5 - - Bb4 Ab4 | Bb4 - - F4 - - - -     | G4 - Ab4 - Bb4 - C5 - | E5 - - - - - . .
C5 - - Ab4 - - F4 G4   | Ab4 - - C5 - - F5 -    | Ab5 - - G5 - - F5 Eb5 | F5 - - - Db5 - Bb4 -
Db5 - C5 - Bb4 - Ab4 - | F4 - - - - - Db5 -     | E4 - G4 - Bb4 - Db5 - | C5 - - - - - - -
"""

# Brass melody for B section, 8th-note grid.
SP_BRASS_B = """
F4 - - - - - Ab4 -  | C5 - - - Bb4 - Ab4 - | G4 - - - - - Bb4 -  | Eb5 - - - Db5 - C5 -
Bb4 - - - G4 - - -  | C5 - - - Eb5 - - -   | F5 - - - - - - -    | - - - - Eb5 - F5 -
Db5 - - - - - F5 -  | Bb4 - - - C5 - Db5 - | Eb5 - - - Db5 - Bb4 - | G4 - - - - - - -
C5 - - - Eb5 - - Ab5 | - - - - G5 - F5 -   | E5 - - - G5 - - -   | - - - - - - . .
"""

# Brass stab rhythm over 2 bars (16th grid).
SP_STABS = "X - - . . . x - . . . . . . . . | . . . . . . . . . . x - . x - -"

SP_DRUMS = {
    "intro_a": dict(k=". . . . . . . . . . . . . . . .", s=". . . . . . . . . . . . . . . .", h="x . g . x . g . x . g . x . g ."),
    "intro_b": dict(k="X . . . . . . . X . . x . . . .", s=". . . . . . . . . . . . . . . .", h="x . x . x . x . x . x . x . x ."),
    "A":  dict(k="X . . x . . x . x . . . . . x .", s=". . . . X . . . . . . . X . . g", h="x . x x x . x . x . x x x . o ."),
    "B":  dict(k="X . . . . . . . x . x . . . . .", s=". . . . . . . . X . . . . . . .", h="x . x . x . x . x . x . x . x .",
               t=". . . x . . x . . . . . . x . ."),
    "brk": dict(k="X . . . . . . . . . X . . . . .", s=". . . . g . . . . . . . g . . .", h="x g x g x g x g x g x g x g x g"),
}
SP_FILL = [(8, "t1", 0.9), (9, "t1", 0.7), (10, "t2", 0.9), (11, "t2", 0.7),
           (12, "t3", 1.0), (13, "t3", 0.8), (14, "s", 1.1), (15, "s", 1.15)]


def _chord_bass_note(ch, deg):
    root, third, fifth, sev = SP_CHORDS[ch][0], SP_CHORDS[ch][1], SP_CHORDS[ch][2], SP_CHORDS[ch][3]
    r = note_to_midi(_BASS_ROOT[root])
    return r + {"r": 0, "f": fifth, "o": 12, "t": third, "s": sev, "T": third + 12, "u": fifth + 12}[deg]


def _harmony_below(mel, chord_notes, min_gap=3):
    pcs = {n % 12 for n in chord_notes}
    for d in range(min_gap, 10):
        if (mel - d) % 12 in pcs:
            return mel - d
    return mel - 5


def build_spillway(seed=118):
    rng = np.random.default_rng(seed)
    sr = SR
    beat = 60.0 / SP_BPM
    s16 = beat / 4
    s8 = beat / 2
    bar_len = beat * 4
    bars = []
    for sec, chords in SP_SECTIONS:
        for i, c in enumerate(chords):
            bars.append((sec, i, c))
    nbars = len(bars)
    length = nbars * bar_len
    mx = Mixer(sr, length, tail=5.0)
    mx.track("bass", -1.0, 0.04, eq=chain(hp_resp(35, 2), lp_resp(4500, 2)))
    mx.track("drums", -6.0, 0.10, eq=chain(hp_resp(35, 2), shelf_resp(3000, 2.0)))
    mx.track("hats", 1.0, 0.12, eq=hp_resp(5000, 1))
    mx.track("brass", -3.0, 0.30, eq=chain(hp_resp(160, 2), lp_resp(6000, 2)))
    mx.track("guitar", -6.5, 0.35, eq=chain(hp_resp(180, 2), lp_resp(4500, 2), peak_resp(2200, 1.5, 1.2), peak_resp(900, -2, 1.0)))
    mx.track("strings", -11.0, 0.45, eq=chain(hp_resp(180, 2), lp_resp(3200, 2)))

    kit = {
        "k": [ins.kick(sr, rng) for _ in range(3)],
        "s": [ins.snare(sr, rng) for _ in range(3)],
        "h": [ins.hat(sr, rng) for _ in range(4)],
        "o": [ins.hat(sr, rng, open_=True) for _ in range(2)],
        "t1": [ins.tom(sr, rng, 196)], "t2": [ins.tom(sr, rng, 147)], "t3": [ins.tom(sr, rng, 110)],
        "c": [ins.crash(sr, rng)],
    }
    tom_pan = {"t1": -0.35, "t2": 0.0, "t3": 0.35}

    def hit(name, t, vel, pan=0.0):
        smp = kit[name][rng.integers(len(kit[name]))]
        trk = "hats" if name in ("h", "o", "c") else "drums"
        if name == "h":
            pan = 0.3
        if name == "c":
            pan = -0.25
        mx.add(trk, smp, t + rng.uniform(-0.002, 0.002), pan, vel * rng.uniform(0.93, 1.03))

    lead_ev, _ = parse_line(SP_LEAD_A)
    bassb_ev, _ = parse_line(SP_BRASS_B)
    stabs_ev, _ = parse_line(SP_STABS)

    fill_bars = {3, 11, 19, 27, 35, 43}
    crash_bars = {4, 12, 20, 28, 36}

    for bi, (sec, si, ch) in enumerate(bars):
        t0 = bi * bar_len
        cd = SP_CHORDS[ch]
        loud = {"intro": 0.8, "A": 1.0, "B": 1.05, "A2": 1.05, "brk": 0.85}[sec]

        # ---------------- bass
        if sec == "intro":
            bp = SP_BASS["intro"]
        elif sec in ("A", "A2"):
            bp = SP_BASS["A"] if si % 2 == 0 else SP_BASS["A_b"]
        elif sec == "B":
            bp = SP_BASS["B"] if si < 8 else SP_BASS["B_b"]
        else:
            bp = SP_BASS["brk"]
        ev, _ = parse_line(bp)
        for st, ln, tok, v in ev:
            m = _chord_bass_note(ch, tok)
            acc = 1.0 if st % 4 == 0 else 0.85
            dur = min(ln * s16 * 0.9, s16 * 3)
            mx.add("bass", ins.synth_bass(m, round(dur, 3), round(0.8 * acc * v * loud, 2), sr), t0 + st * s16, 0.0)

        # ---------------- drums
        if sec == "intro":
            pat = SP_DRUMS["intro_a"] if si < 2 else SP_DRUMS["intro_b"]
        elif sec in ("A", "A2"):
            pat = SP_DRUMS["A"]
        elif sec == "B":
            pat = SP_DRUMS["B"]
        else:
            pat = SP_DRUMS["brk"]
        fill = bi in fill_bars
        for key, line in pat.items():
            for st, v, c in parse_drums(line):
                if fill and st >= 8 and key in ("s", "t", "k") and not (key == "k" and st == 8):
                    continue
                if key == "h":
                    hit("o" if c == "o" else "h", t0 + st * s16, v * loud)
                elif key == "t":
                    hit("t3" if st % 2 else "t2", t0 + st * s16, v * 0.8 * loud, 0.2)
                else:
                    hit(key, t0 + st * s16, v * loud)
        if fill:
            for st, name, v in SP_FILL:
                hit(name, t0 + st * s16, v * loud, tom_pan.get(name, 0.0))
        if bi in crash_bars:
            hit("c", t0, 1.0)
        if sec == "brk" and si == 7:
            # soft tom pickup back into the intro
            for st, name, v in ((12, "t2", 0.45), (13, "t2", 0.4), (14, "t3", 0.55), (15, "t3", 0.6)):
                hit(name, t0 + st * s16, v, tom_pan[name])

        # ---------------- strings pad (one chord per bar, re-voiced on chord change)
        if True:
            prev = bars[bi - 1][2] if bi > 0 else None
            nxt = bars[bi + 1][2] if bi + 1 < nbars else bars[0][2]
            if ch != prev or si == 0:
                nb = 1
                while bi + nb < nbars and bars[bi + nb][2] == ch and bars[bi + nb][0] == sec and nb < 4:
                    nb += 1
                dur = nb * bar_len - 0.05
                pv = 0.55 if sec == "intro" else 0.8
                for k, nm in enumerate(cd[4]):
                    mx.add("strings", ins.strings(note_to_midi(nm), round(dur, 3), pv, sr),
                           t0, pan=-0.6 + 1.2 * k / 3.0)

        # ---------------- brass
        bpan = [-0.3, 0.3, -0.1, 0.1]
        if sec in ("A", "A2") or (sec == "intro" and si == 3):
            if sec == "intro":
                stab_list = [(8, 2, "X", 1.0), (12, 2, "X", 1.0)]
                off = 0
            else:
                stab_list = [(st, ln, tok, v) for st, ln, tok, v in stabs_ev]
                off = 16 * (si % 2)
            for st, ln, tok, v in stab_list:
                if sec != "intro" and not (off <= st < off + 16):
                    continue
                stt = st - off
                for k, nm in enumerate(cd[5]):
                    mx.add("brass", ins.synth_brass(note_to_midi(nm), round(ln * s16 * 0.85, 3), round(0.8 * v, 2), sr,
                                                    attack=0.012, release=0.12),
                           t0 + stt * s16, bpan[k % 4], 0.55)
        if sec == "B":
            for st, ln, tok, v in bassb_ev:
                if not (si * 8 <= st < si * 8 + 8):
                    continue
                m = note_to_midi(tok)
                dur = ln * s8 - 0.03
                chord_notes = [note_to_midi(x) for x in SP_CHORDS[ch][4]]
                hm = _harmony_below(m, chord_notes)
                tt = t0 + (st - si * 8) * s8
                mx.add("brass", ins.synth_brass(m, round(dur, 3), 0.95, sr, attack=0.03), tt, -0.15, 0.9)
                mx.add("brass", ins.synth_brass(hm, round(dur, 3), 0.8, sr, attack=0.03), tt + 0.006, 0.2, 0.7)
                mx.add("brass", ins.synth_brass(m - 12, round(dur, 3), 0.75, sr, attack=0.03), tt + 0.004, 0.0, 0.55)
            if si in (0, 4, 8, 12):
                pass
        if sec == "brk" or (sec == "intro" and si < 2):
            if si % 2 == 0:
                for k, nm in enumerate(cd[5]):
                    mx.add("brass", ins.synth_brass(note_to_midi(nm) - 12, round(bar_len * 2 - 0.2, 3), 0.55, sr,
                                                    attack=0.6, release=0.5, bright=0.6),
                           t0, bpan[k % 4], 0.5)

        # ---------------- guitar
        if sec == "A" or sec == "A2":
            idx0 = si if sec == "A" else si + 8
            for st, ln, tok, v in lead_ev:
                if not (idx0 * 8 <= st < idx0 * 8 + 8):
                    continue
                dur = ln * s8 - 0.02
                tt = t0 + (st - idx0 * 8) * s8
                m = note_to_midi(tok)
                g = ins.guitar(m, dur, 0.9 * v, sr, rng, trem_picking=ln >= 3, pick_rate=4.0 / beat * 2)
                mx.add("guitar", g, tt, 0.12)
                mx.add("guitar", g * 0.28, tt + 3 * s16, -0.55)  # dotted-8th echo
                if sec == "A2":
                    mx.add("brass", ins.synth_brass(m - 12, round(dur, 3), 0.7, sr, attack=0.03), tt, 0.25, 0.5)
        elif sec == "B" or sec == "brk" or (sec == "intro" and si >= 2):
            arp = [note_to_midi(x) for x in cd[6]]
            order = [0, 1, 2, 1, 3, 1, 2, 1]
            if sec == "B":
                for st in range(16):
                    m = arp[order[st % 8]]
                    g = ins.guitar(m, s16 * 0.95, 0.42 if st % 4 else 0.55, sr, rng, trem_picking=False)
                    mx.add("guitar", g, t0 + st * s16, -0.35, 0.8)
            else:
                for st in range(8):
                    m = arp[order[st]]
                    g = ins.guitar(m, s8 * 0.95, 0.55, sr, rng, trem_picking=False)
                    mx.add("guitar", g, t0 + st * s8, -0.2)
                    mx.add("guitar", g * 0.3, t0 + st * s8 + 3 * s16, 0.5)

    ir = make_ir(sr, length=2.6, rt_low=2.0, rt_high=0.8, predelay=0.018, seed=11)
    print("    rendering spillway mix")
    mix = mx.render(ir, loop=True, stats=True)
    eq = chain(lp_resp(11500, 2), peak_resp(1400, -2.0, 1.5), shelf_resp(5000, 2.0))
    return master(mix, sr, loop=True, target_lufs=-16.0, ceiling_db=-3.0, eq=eq), sr


# ================================================================= MENU
# G minor lounge groove, 96 BPM swung 8ths, 24 bars (60.0 s). A(8) A'(8) B(8).
MN_BPM = 96
MN_CHORDS = {
    # root, third, fifth, seventh, comping voicing
    "Gm9":    ("G", 3, 7, 10, ["Bb3", "D4", "F4", "A4"]),
    "Cm9":    ("C", 3, 7, 10, ["Bb3", "D4", "Eb4", "G4"]),
    "F13":    ("F", 4, 7, 10, ["A3", "D4", "Eb4", "G4"]),
    "Bbmaj7": ("Bb", 4, 7, 11, ["A3", "C4", "D4", "F4"]),
    "Ebmaj7": ("Eb", 4, 7, 11, ["G3", "Bb3", "D4", "F4"]),
    "Am7b5":  ("A", 3, 6, 10, ["G3", "C4", "Eb4", "A4"]),
    "D7b9":   ("D", 4, 7, 10, ["F#3", "C4", "Eb4", "A4"]),
    "D7#9":   ("D", 4, 7, 10, ["F#3", "C4", "F4", "A4"]),
    "Dm7":    ("D", 3, 7, 10, ["C4", "E4", "F4", "A4"]),
    "Gm7":    ("G", 3, 7, 10, ["F3", "Bb3", "D4", "F4"]),
}
MN_ROOT = {"G": 43, "C": 36, "F": 41, "Bb": 34, "Eb": 39, "A": 33, "D": 38}
MN_PROG = (["Gm9", "Gm9", "Cm9", "F13", "Bbmaj7", "Ebmaj7", "Am7b5", "D7b9"] +
           ["Gm9", "Gm9", "Cm9", "F13", "Bbmaj7", "Ebmaj7", "Am7b5", "D7#9"] +
           ["Ebmaj7", "Ebmaj7", "Dm7", "Gm7", "Cm9", "F13", "Am7b5", "D7b9"])

MN_VIBES = """
. . D5 - F5 - A5 -      | G5 - - - - - F5 D5    | Eb5 - - - D5 - Bb4 -  | C5 - - - - - . .
. D5 F5 A5 - - G5 -     | G5 - - - Bb4 - D5 -   | C5 - - Eb5 - - D5 C5  | F#4 - - - Eb5 - - -
. . D5 - F5 - A5 -      | Bb5 - - A5 - - G5 -   | F5 - - Eb5 - - D5 -   | A4 - - - D5 - - -
A5 - - - F5 - D5 -      | G5 - - - - - Bb5 -    | A5 - G5 - Eb5 - C5 -  | D5 - - - - - . .
"""
MN_BRASS_B = """
G4 - - - - - Bb4 -      | D5 - - - - - . .      | C5 - - - A4 - F4 -    | Bb4 - - - - - . .
. . Eb5 - D5 - Bb4 -    | C5 - - - A4 - D5 -    | Eb5 - - - C5 - - -    | F#4 - - - A4 - C5 -
"""
MN_COMP = ["X - - x . . . .", ". . x - . . . x"]
MN_RIDE = "x . x x x . x x"


def _walking_bass(prog, rng):
    """Generate a walking line: root on 1, chord tones on 2-3, chromatic/step approach on 4."""
    notes = []
    for i, ch in enumerate(prog):
        root, third, fifth, sev = MN_CHORDS[ch][:4]
        r = MN_ROOT[root]
        nxt = MN_ROOT[MN_CHORDS[prog[(i + 1) % len(prog)]][0]]
        tones = [r + third, r + fifth, r + sev, r + 12, r - 12 + sev, r - 12 + fifth]
        tones = [t for t in tones if 28 <= t <= 50]
        near = [t for t in tones if abs(t - r) <= 7]
        b2 = near[rng.integers(len(near))]
        cand = sorted(tones, key=lambda t: abs(t - nxt))
        b3 = cand[0] if cand[0] != b2 else cand[1]
        b4 = nxt + (1 if (b3 > nxt or rng.random() < 0.35) else -1)
        if b4 == b3:
            b4 = nxt - 1 if b4 > nxt else nxt + 1
        notes.append([r, b2, b3, b4])
    return notes


def build_menu(seed=96):
    rng = np.random.default_rng(seed)
    sr = SR
    beat = 60.0 / MN_BPM
    bar_len = beat * 4
    swing = 0.62  # long 8th fraction of a beat

    def t8(bar, step):
        b, half = divmod(step, 2)
        return bar * bar_len + b * beat + (swing * beat if half else 0.0)

    nb = len(MN_PROG)
    mx = Mixer(sr, nb * bar_len, tail=5.0)
    mx.track("bass", 2.0, 0.06, eq=chain(hp_resp(38, 2), lp_resp(2500, 2)))
    mx.track("drums", 1.0, 0.18, eq=hp_resp(45, 2))
    mx.track("ride", -1.0, 0.2, eq=hp_resp(1500, 1))
    mx.track("vibes", -6.5, 0.35, eq=chain(hp_resp(200, 1), lp_resp(7000, 1)))
    mx.track("ep", -6.5, 0.25, eq=chain(hp_resp(150, 2), lp_resp(5000, 2)))
    mx.track("brass", -4.0, 0.3, eq=chain(hp_resp(350, 2), peak_resp(1300, 6, 1.2), lp_resp(3800, 2)))

    walk = _walking_bass(MN_PROG, rng)
    vib_ev, _ = parse_line(MN_VIBES)
    brass_ev, _ = parse_line(MN_BRASS_B)
    ride_smp = [ins.ride(sr, rng) for _ in range(3)]
    brush = [ins.brush_hit(sr, rng) for _ in range(4)]
    kicks = [ins.soft_kick(sr, rng) for _ in range(2)]

    for bi, ch in enumerate(MN_PROG):
        t0 = bi * bar_len
        cd = MN_CHORDS[ch]
        # walking bass
        for k, m in enumerate(walk[bi]):
            v = 0.95 if k in (0, 2) else 0.8
            mx.add("bass", ins.upright_bass(m, round(beat * 0.92, 3), v, sr, rng),
                   t0 + k * beat + rng.uniform(-0.004, 0.004), 0.0)
        # brushes: swish each beat, taps on 2 and 4, soft kick on 1 and 3
        for k in range(4):
            mx.add("drums", ins.brush_swish(sr, rng, beat, 0.9), t0 + k * beat, -0.2 if k % 2 else 0.2)
            if k in (1, 3):
                mx.add("drums", brush[rng.integers(4)], t0 + k * beat, 0.1, 0.9)
            else:
                mx.add("drums", kicks[rng.integers(2)], t0 + k * beat, 0.0, 0.7)
        for st, v, c in parse_drums(MN_RIDE.replace(" ", " ")):
            mx.add("ride", ride_smp[rng.integers(3)], t8(bi, st), 0.35, v * (1.0 if st % 2 == 0 else 0.7))
        if bi % 8 == 7:
            for st in (6, 7):
                mx.add("drums", brush[rng.integers(4)], t8(bi, st), -0.1, 0.7 + 0.2 * (st - 6))
        # electric piano comping
        comp = MN_COMP[bi % 2]
        cev, _ = parse_line(comp.replace("X", "C4!").replace("x", "C4"))
        for st, ln, tok, v in cev:
            dur = ln * beat / 2 * 0.95
            for k, nm in enumerate(cd[4]):
                mx.add("ep", ins.epiano(note_to_midi(nm), round(dur, 3), 0.55 * v, sr),
                       t8(bi, st) + k * 0.004, -0.35 + 0.7 * k / 3)
        # vibes melody in A / A', comp chords in B
        if bi < 16:
            for st, ln, tok, v in vib_ev:
                if bi * 8 <= st < bi * 8 + 8:
                    s = st - bi * 8
                    end = s + ln
                    tt = t8(bi, s)
                    te = t8(bi + end // 8, end % 8)
                    mx.add("vibes", ins.vibes(note_to_midi(tok), round(te - tt - 0.02, 3), 0.85 * v, sr), tt, 0.15)
        else:
            for s in (0, 3, 6):
                for k, nm in enumerate(cd[4]):
                    mx.add("vibes", ins.vibes(note_to_midi(nm) + 12, round(beat * 0.7, 3), 0.28, sr),
                           t8(bi, s) + k * 0.012, -0.3 + 0.6 * k / 3)
            for st, ln, tok, v in brass_ev:
                rel = bi - 16
                if rel * 8 <= st < rel * 8 + 8:
                    s = st - rel * 8
                    end = s + ln
                    tt = t8(bi, s)
                    te = t8(bi + end // 8, end % 8)
                    m = note_to_midi(tok)
                    hm = _harmony_below(m, [note_to_midi(x) for x in cd[4]])
                    mx.add("brass", ins.synth_brass(m, round(te - tt - 0.03, 3), 0.75, sr, attack=0.04, muted=True), tt, 0.2)
                    mx.add("brass", ins.synth_brass(hm, round(te - tt - 0.03, 3), 0.6, sr, attack=0.04, muted=True), tt + 0.008, -0.2, 0.8)
        # A': muted brass pads behind the vibes in the second half
        if 12 <= bi < 16:
            for k, nm in enumerate(cd[4][1:]):
                mx.add("brass", ins.synth_brass(note_to_midi(nm), round(bar_len - 0.1, 3), 0.45, sr, attack=0.25,
                                                release=0.4, muted=True), t0, -0.4 + 0.4 * k, 0.55)

    ir = make_ir(sr, length=2.2, rt_low=1.5, rt_high=0.6, predelay=0.02, seed=21)
    print("    rendering menu mix")
    mix = mx.render(ir, loop=True, stats=True)
    eq = chain(lp_resp(10500, 2), shelf_resp(3000, 2.0))
    return master(mix, sr, loop=True, target_lufs=-17.0, ceiling_db=-3.0, eq=eq), sr


# ================================================================= STINGERS
def _brass_chord(mx, names, t, dur, vel, **kw):
    pans = np.linspace(-0.4, 0.4, len(names))
    for nm, p in zip(names, pans):
        mx.add("brass", ins.synth_brass(note_to_midi(nm), round(dur, 3), vel, SR, **kw), t, float(p))


def build_mission_complete(seed=7):
    """Bb major fanfare, 132 BPM. Rising triplet pickup, ascending top line to a held Bb chord."""
    rng = np.random.default_rng(seed)
    sr = SR
    beat = 60.0 / 132
    mx = Mixer(sr, 7.2, tail=0.0)
    mx.track("brass", -1.0, 0.3, eq=chain(hp_resp(120, 2), peak_resp(1600, 2, 1.5)))
    mx.track("perc", -2.0, 0.25)
    mx.track("strings", -9.0, 0.4, eq=chain(hp_resp(150, 2), lp_resp(4500, 2)))
    trip = beat / 3
    # pickup triplet (unison + octave)
    for k, nm in enumerate(["D4", "Eb4", "F4"]):
        for o in (0, -12):
            mx.add("brass", ins.synth_brass(note_to_midi(nm) + o, round(trip * 0.8, 3), 0.95, sr, attack=0.01, release=0.08),
                   k * trip, 0.0, 0.8)
    T = beat
    seq = [  # (start beat, length beats, chord voicing, top)
        (1.0, 1.0, ["Bb2", "F3", "Bb3", "D4"], "F4"),
        (2.0, 0.5, ["Bb2", "F3", "Bb3", "F4"], "D4"),
        (2.5, 0.5, ["Bb2", "D3", "Bb3", "D4"], "F4"),
        (3.0, 1.0, ["G2", "Eb3", "Bb3", "Eb4"], "G4"),
        (4.0, 1.0, ["F2", "C3", "A3", "C4"], "A4"),
        (5.0, 1.0, ["Gb2", "Db3", "Gb3", "Db4"], "Bb4"),
        (6.0, 1.0, ["Ab2", "Eb3", "Ab3", "Eb4"], "C5"),
        (7.0, 6.0, ["Bb1", "Bb2", "F3", "Bb3", "F4"], "D5"),
    ]
    for sb, lb, chord, top in seq:
        dur = lb * T - 0.04
        _brass_chord(mx, chord, sb * T, dur, 0.85, attack=0.015, release=0.35 if lb > 2 else 0.12)
        for o in (0, 12):
            mx.add("brass", ins.synth_brass(note_to_midi(top) + o, round(dur, 3), 1.0, sr, attack=0.015,
                                            release=0.4 if lb > 2 else 0.12), sb * T, 0.1, 0.9 if o == 0 else 0.6)
    # percussion: timpani on Bb and F, snare roll into the final chord, crash
    mx.add("perc", ins.timpani(note_to_midi("Bb2"), 0.9, sr, rng), 1.0 * T, 0.0, 0.9)
    mx.add("perc", ins.timpani(note_to_midi("F2"), 0.8, sr, rng), 4.0 * T, 0.0, 0.8)
    mx.add("perc", ins.snare_roll(sr, rng, 2.0 * T, 0.15, 0.6), 5.0 * T, 0.1, 0.8)
    # timpani roll on F building into the last chord
    roll_t = 5.0 * T
    while roll_t < 7.0 * T - 0.05:
        v = 0.2 + 0.35 * (roll_t - 5.0 * T) / (2.0 * T)
        mx.add("perc", ins.timpani(note_to_midi("F2"), v, sr, rng, dur=0.6), roll_t, 0.0, 1.0)
        roll_t += 0.075
    mx.add("perc", ins.timpani(note_to_midi("Bb1") + 12, 1.0, sr, rng), 7.0 * T, 0.0, 1.0)
    mx.add("perc", ins.crash(sr, rng, 1.0, dur=3.5), 7.0 * T, -0.2, 0.9)
    mx.add("perc", ins.crash(sr, rng, 0.7, dur=3.5), 7.0 * T + 0.01, 0.3, 0.6)
    for k, nm in enumerate(["Bb3", "D4", "F4", "Bb4", "D5"]):
        mx.add("strings", ins.strings(note_to_midi(nm), round(5.6 * T, 3), 0.8, sr, attack=0.05, release=1.2, tremolo=12.0),
               7.0 * T, -0.5 + 0.25 * k)
    ir = make_ir(sr, length=2.5, rt_low=2.1, rt_high=0.9, seed=31)
    full = mx.render(ir, loop=False)
    full = full[: int(7.2 * sr)]
    n = len(full)
    fo = int(1.3 * sr)
    full[n - fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    return master(full, sr, loop=False, target_lufs=-15.0, ceiling_db=-3.0), sr


def build_mission_failed(seed=8):
    """D minor, slow and falling: Dm - Gm/Bb - A7 - Dm with timpani and a low final boom."""
    rng = np.random.default_rng(seed)
    sr = SR
    beat = 60.0 / 72
    mx = Mixer(sr, 6.0, tail=0.0)
    mx.track("brass", -1.0, 0.35, eq=chain(hp_resp(90, 2), lp_resp(3200, 2)))
    mx.track("strings", -6.0, 0.45, eq=chain(hp_resp(60, 2), lp_resp(3500, 2)))
    mx.track("perc", -6.0, 0.3, eq=hp_resp(45, 2))
    seq = [  # start, len (beats), chord, melody
        (0.0, 1.0, ["D2", "A2", "D3", "F3"], "A4"),
        (1.0, 1.0, ["Bb1", "G2", "D3", "G3"], "Bb4"),
        (2.0, 0.5, ["A1", "A2", "C#3", "G3"], "G4"),
        (2.5, 0.5, ["A1", "A2", "C#3", "G3"], "E4"),
        (3.0, 3.2, ["D2", "A2", "D3", "F3"], "D4"),
    ]
    for sb, lb, chord, mel in seq:
        dur = lb * beat - 0.05
        rel = 1.2 if lb > 2 else 0.2
        _brass_chord(mx, chord, sb * beat, dur, 0.6, attack=0.06, release=rel, bright=0.55)
        mx.add("brass", ins.synth_brass(note_to_midi(mel), round(dur, 3), 0.75, sr, attack=0.05, release=rel, bright=0.6),
               sb * beat, 0.15)
        for k, nm in enumerate(chord[1:]):
            mx.add("strings", ins.strings(note_to_midi(nm) + 12, round(dur, 3), 0.6, sr, attack=0.08, release=rel),
                   sb * beat, -0.5 + 0.5 * k)
    mx.add("perc", ins.timpani(note_to_midi("D2"), 1.0, sr, rng, dur=3.0), 0.0, 0.0)
    mx.add("perc", ins.timpani(note_to_midi("A1"), 0.7, sr, rng, dur=2.0), 2.0 * beat, 0.0)
    mx.add("perc", ins.timpani(note_to_midi("D2"), 1.0, sr, rng, dur=3.0), 3.0 * beat, 0.0)
    mx.add("perc", ins.kick(sr, rng, 0.8, tone=0.7), 3.0 * beat, 0.0)
    mx.add("perc", ins.crash(sr, rng, 0.35, dur=3.0), 3.0 * beat, 0.0, 0.5)
    ir = make_ir(sr, length=2.5, rt_low=2.4, rt_high=0.9, seed=41)
    full = mx.render(ir, loop=False)[: int(5.6 * sr)]
    n = len(full)
    fo = int(1.4 * sr)
    full[n - fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    return master(full, sr, loop=False, target_lufs=-17.0, ceiling_db=-3.0), sr


def build_alert_sting(seed=9):
    """Diminished brass/string stab with timpani and a rising string shriek (~1.5 s)."""
    rng = np.random.default_rng(seed)
    sr = SR
    mx = Mixer(sr, 1.6, tail=0.0)
    mx.track("brass", 0.0, 0.3, eq=chain(hp_resp(90, 2), peak_resp(1500, 3, 1.5)))
    mx.track("strings", -4.0, 0.35, eq=chain(hp_resp(150, 2), lp_resp(6000, 2)))
    mx.track("perc", -6.0, 0.3, eq=hp_resp(45, 2))
    stab = ["C#3", "G3", "Bb3", "E4", "G4", "C#5"]
    _brass_chord(mx, stab, 0.0, 0.32, 1.1, attack=0.006, release=0.25, bright=1.2)
    _brass_chord(mx, ["C#2", "C#3"], 0.0, 0.5, 0.9, attack=0.006, release=0.3)
    for k, nm in enumerate(["C#4", "E4", "G4", "Bb4", "C#5"]):
        s = ins.strings(note_to_midi(nm), 1.0, 0.8, sr, attack=0.01, release=0.35, tremolo=14.0)
        n = len(s)
        cres = np.clip(np.arange(n) / sr / 0.9, 0.35, 1.0) ** 1.5
        mx.add("strings", s * cres, 0.02, -0.5 + 0.25 * k)
    # rising shriek: glissando saw ensemble
    n = int(1.1 * sr)
    t = np.arange(n) / sr
    f = 800 * 2 ** (t * 1.2)
    from synth import saw as _saw
    sh = sum(_saw(f * 2 ** (c / 1200.0), n, sr, 0.3 * i) for i, c in enumerate((-9, 0, 8)))
    sh *= np.clip(t / 0.8, 0, 1) ** 2 * np.clip((1.1 - t) / 0.08, 0, 1) * 0.12
    mx.add("strings", sh, 0.2, 0.3)
    mx.add("perc", ins.timpani(note_to_midi("C#2"), 1.1, sr, rng, dur=1.5), 0.0, 0.0)
    mx.add("perc", ins.kick(sr, rng, 1.0, tone=0.8), 0.0, 0.0)
    mx.add("perc", ins.crash(sr, rng, 0.8, dur=1.5), 0.0, 0.2)
    ir = make_ir(sr, length=1.8, rt_low=1.6, rt_high=0.7, seed=51)
    full = mx.render(ir, loop=False)[: int(1.55 * sr)]
    n = len(full)
    fo = int(0.3 * sr)
    full[n - fo:] *= np.linspace(1, 0, fo)[:, None] ** 2
    return master(full, sr, loop=False, target_lufs=-14.0, ceiling_db=-3.0), sr


MUSIC = {
    "spillway": build_spillway,
    "menu": build_menu,
    "mission_complete": build_mission_complete,
    "mission_failed": build_mission_failed,
    "alert_sting": build_alert_sting,
}
