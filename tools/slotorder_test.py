#!/usr/bin/env python3
"""slotorder_test.py - tools/slotorder.py on an emulated CPU (unicorn): the palette allocator 0871:8A9A of the
original DDS98.EXE and of the one with the fix, run on the same slot tables with the mode word [78C6] and the
battle's saved-claims pointer [2F04]:[2F06] set.

  * outside a battle - the pointer null with any mode 00-27h, or a battle mode (0Bh, 22h) with the pointer null,
    or the pointer set with any other mode: the same slot from both programs for every table;
  * in a battle (0Bh or 22h with the pointer set, its offset or segment or both not zero): the original gives
    the first free slot counting up, the fixed one the first counting down; a claimed 0-13 holding the colour,
    a claimed 14/15 holding it when nothing is free, and slot 2 when nothing fits come out of both alike - each
    checked against a model of the allocator;
  * the fixed file differs from the original in the two windows alone (the hook at 8ABB and the routine at
    69C2), neither of which holds a relocated word; apply_to is idempotent and revert gives the original back.

    slotorder_test.py [--image HDI]

With an image, its DDS98.EXE is the fixed program (with every other fix of the build) and the same file with
this fix taken out the original. Both programs have nospace's jump over the print, so slot 2 comes back quietly.
"""
import argparse
import os
import random
import struct
import sys

from unicorn import UC_ARCH_X86, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import nospace  # noqa: E402
import slotorder  # noqa: E402
from mz import MZ  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
SP = 0xAB00
SENT = 0xD000
REFS, COLS = 0x6CB6, 0x6CD6
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def load(blob):
    path = os.path.join(WORK, "build", "_slotorder_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    try:
        return bytes(MZ(path, base=LOAD).image), MZ(path).reloc_set
    finally:
        os.remove(path)


class Pal:
    def __init__(self, blob):
        img, _ = load(blob)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x110000)
        self.mu.mem_write(LOAD * 16, img)
        self.mu.mem_write(SENT * 16, b"\xf4")

    def alloc(self, refs, cols, colour, mode, saved=(0x0004, 0x5A3C)):
        self.mu.mem_write(DS * 16 + REFS, struct.pack("<16H", *refs))
        self.mu.mem_write(DS * 16 + COLS, struct.pack("<16H", *cols))
        self.mu.mem_write(DS * 16 + slotorder.MODE, struct.pack("<H", mode))
        self.mu.mem_write(DS * 16 + slotorder.SAVED, struct.pack("<2H", *saved))
        words = [0, SENT, colour]
        sp = SP - 2 * len(words)
        self.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(words)}H", *words))
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, LOAD + slotorder.SEG), (X.UC_X86_REG_IP, 0x8A9A),
                       (X.UC_X86_REG_SP, sp), (X.UC_X86_REG_BP, 0x1234), (X.UC_X86_REG_SI, 0x5A5A),
                       (X.UC_X86_REG_DI, 0xA5A5)):
            self.mu.reg_write(reg, v)
        self.mu.emu_start((LOAD + slotorder.SEG) * 16 + 0x8A9A, SENT * 16, count=100_000)
        if self.mu.reg_read(X.UC_X86_REG_CS) != SENT:
            raise RuntimeError("8A9A did not come back")
        kept = (self.mu.reg_read(X.UC_X86_REG_SI), self.mu.reg_read(X.UC_X86_REG_DI),
                self.mu.reg_read(X.UC_X86_REG_BP), self.mu.reg_read(X.UC_X86_REG_SP))
        return self.mu.reg_read(X.UC_X86_REG_AX) & 0xFF, kept


def model(refs, cols, colour, down):
    for s in range(14):
        if refs[s] > 0 and cols[s] == colour:
            return s
    for s in (range(15, -1, -1) if down else range(16)):
        if refs[s] == 0:
            return s
    for s in (14, 15):
        if refs[s] > 0 and cols[s] == colour:
            return s
    return 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    a = ap.parse_args()
    if a.image:
        from fat12 import Fat12, open_hdi
        _raw, _hdr, disk, part = open_hdi(a.image)
        fs = Fat12(disk, part)
        e = fs.find("DDS98/" + slotorder.FILE)
        fixed = bytes(fs.read_chain(e["cluster"], e["size"]))
        check(slotorder.state(fixed) == "fixed", f"{a.image}: the fix is in")
        orig = slotorder.apply_to(fixed, revert=True)
    else:
        orig = nospace.apply_to(open(os.path.join(WORK, "files", "DDS98", slotorder.FILE), "rb").read())
        check(slotorder.state(orig) == "orig", "files/DDS98: the original (with nospace)")
        fixed = slotorder.apply_to(orig)

    print("the file")
    check(slotorder.assembled() == slotorder.CAVE_CODE,
          f"CAVE_CODE is CAVE_SRC assembled ({len(slotorder.CAVE_CODE)} of the routine's "
          f"{slotorder.CAVE_END - slotorder.CAVE} bytes)")
    diff = [i for i in range(len(orig)) if orig[i] != fixed[i]]
    windows = [(slotorder.at(off), slotorder.at(off) + len(o)) for off, o, _f in slotorder.SITES]
    check(len(orig) == len(fixed) and all(any(lo <= i < hi for lo, hi in windows) for i in diff),
          f"{len(diff)} bytes differ, all inside the two windows")
    _img, relocs = load(fixed)
    inside = [p for off, o, _f in slotorder.SITES for p in range(slotorder.SEG * 16 + off - 1,
                                                                   slotorder.SEG * 16 + off + len(o)) if p in relocs]
    check(not inside, "no relocated word inside or straddling either window")
    check(slotorder.apply_to(fixed) == fixed, "apply_to is idempotent")
    check(slotorder.apply_to(fixed, revert=True) == orig, "revert gives the original back")

    po, pf = Pal(orig), Pal(fixed)
    rng = random.Random(1990)
    palette = [0x000, 0xFFF, 0x5F4, 0xC35, 0xAD1, 0x223, 0x344, 0x652, 0xBAC, 0x84C, 0x7C4, 0x2B1]
    others = [m for m in range(0x28) if m not in slotorder.BATTLE_MODES]

    def pointer():
        return rng.choice(((rng.randrange(1, 0x10000), rng.randrange(1, 0x10000)), (rng.randrange(1, 0x10000), 0),
                           (0, rng.randrange(1, 0x10000))))

    for battle in (False, True):
        print("in a battle" if battle else "outside a battle")
        bad = n = 0
        kinds = {}
        for trial in range(6000):
            if battle:
                mode, saved = rng.choice(slotorder.BATTLE_MODES), pointer()
            else:
                kind = trial % 3
                kinds[kind] = kinds.get(kind, 0) + 1
                mode = rng.choice(slotorder.BATTLE_MODES) if kind == 1 else rng.choice(others)
                saved = pointer() if kind == 2 else (0, 0)
            refs = [rng.choice((0, 0, 1, 2)) for _ in range(16)]
            if trial % 7 == 0:
                refs = [1] * 16
                refs[rng.randrange(16)] = rng.choice((0, 1))
            cols = [rng.choice(palette) for _ in range(16)]
            colour = rng.choice(palette)
            so, ko = po.alloc(refs, cols, colour, mode, saved)
            sf, kf = pf.alloc(refs, cols, colour, mode, saved)
            n += 1
            want_o, want_f = model(refs, cols, colour, False), model(refs, cols, colour, battle)
            if so != want_o or sf != want_f or (not battle and so != sf) or ko != kf:
                bad += 1
                if bad <= 5:
                    print(f"    mode {mode:02X} saved {saved[1]:04X}:{saved[0]:04X} refs {refs} colour {colour:03X}: "
                          f"original {so} (model {want_o}), fixed {sf} (model {want_f})")
        what = ("counts down" if battle else
                f"gives the same slot ({kinds[0]} no battle, {kinds[1]} battle mode with the pointer null, "
                f"{kinds[2]} pointer set with another mode)")
        check(bad == 0, f"{n} random tables: the original counts up, the fixed one {what}; si, di, bp, sp kept")
    print("cases in a battle")
    full = [1] * 16
    other = [0x100 + i for i in range(16)]
    refs = full[:]
    refs[9] = refs[12] = 0
    check(pf.alloc(refs, other, 0x223, 0x0B)[0] == 12 and po.alloc(refs, other, 0x223, 0x0B)[0] == 9,
          "free 9 and 12: the original takes 9, the fixed one 12")
    cols = other[:]
    cols[5] = 0x223
    refs = full[:]
    refs[10] = 0
    check(pf.alloc(refs, cols, 0x223, 0x22)[0] == 5, "a claimed 5 holding the colour still comes first")
    cols = other[:]
    cols[15] = 0x223
    check(pf.alloc(full, cols, 0x223, 0x0B)[0] == 15, "nothing free: a claimed 15 holding the colour")
    check(pf.alloc(full, other, 0x223, 0x22)[0] == 2, "nothing fits: slot 2")
    print("cases after a battle")
    refs = full[:]
    refs[9] = refs[12] = 0
    check(pf.alloc(refs, other, 0x223, 0x0B, (0, 0))[0] == 9,
          "mode 0Bh with the claims put back (the corridor redrawn after a random battle): 9, as the game")
    check(pf.alloc(refs, other, 0x223, 0x01, (0x0004, 0x5A3C))[0] == 9,
          "the map's mode with the claims still saved (the world map redrawn before they go back): 9, as the game")
    print(f"\n{fails} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
