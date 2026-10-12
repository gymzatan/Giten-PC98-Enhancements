#!/usr/bin/env python3
"""nospace_test.py - tools/nospace.py on an emulated CPU (unicorn): the palette allocator 0871:8A9A of the
original DDS98.EXE and of the one with the fix, run on the same slot tables, with the C run-time's printf
(0000:0708) replaced by a stub that counts its calls and keeps the colour it was handed.

  * every slot claimed by another colour: both return slot 2, the original prints once with the colour, the
    fixed one does not print;
  * the other outcomes, in both programs alike and with no print: a claimed slot 0-13 that holds the colour
    (the first of two), the first unclaimed slot, a claimed 14 or 15 that holds the colour, and the order of
    those three when more than one applies;
  * a sweep of random tables, the same answer from both programs every time, a print only in the original and
    only when the answer is the fallback;
  * the fixed file differs from the original in the two bytes alone, which no relocation touches; apply_to is
    idempotent and apply_to(..., revert=True) gives the original back.

    nospace_test.py [--image HDI]

With an image, its DDS98.EXE is the fixed program (with every other fix of the build in it) and the same
file with this fix taken out the original.
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
from asm86 import assemble  # noqa: E402
from mz import MZ  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
SP = 0xAB00                             # inside the startup stack
SENT = 0xD000                           # a hlt the far returns come back to
REFS, COLS = 0x6CB6, 0x6CD6             # the allocator's claim counts and colours, 16 words each
CALLS, ARG = 0xFFF0, 0xFFF2             # where the printf stub counts its calls and keeps its colour
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def load(blob):
    path = os.path.join(WORK, "build", "_nospace_test.exe")
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
        # printf(fmt far, colour): count the call, keep the colour (the word after the far format pointer)
        stub = assemble(f"push bp\nmov bp, sp\ninc word ptr [{CALLS:#x}]\nmov ax, word ptr [bp + 0xa]\n"
                        f"mov word ptr [{ARG:#x}], ax\nmov ax, 0x13\npop bp\nretf", org=0x0708)[0]
        self.mu.mem_write(LOAD * 16 + 0x0708, stub)
        self.mu.mem_write(SENT * 16, b"\xf4")

    def alloc(self, refs, cols, colour):
        """8A9A(colour) with the given claim counts and colours -> (slot, prints, printed colour)."""
        self.mu.mem_write(DS * 16 + REFS, struct.pack("<16H", *refs))
        self.mu.mem_write(DS * 16 + COLS, struct.pack("<16H", *cols))
        self.mu.mem_write(DS * 16 + CALLS, b"\0\0\0\0")
        words = [0, SENT, colour]
        sp = SP - 2 * len(words)
        self.mu.mem_write(DS * 16 + sp, struct.pack(f"<{len(words)}H", *words))
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, LOAD + nospace.SEG), (X.UC_X86_REG_IP, 0x8A9A),
                       (X.UC_X86_REG_SP, sp), (X.UC_X86_REG_BP, 0)):
            self.mu.reg_write(reg, v)
        self.mu.emu_start((LOAD + nospace.SEG) * 16 + 0x8A9A, SENT * 16, count=100_000)
        if self.mu.reg_read(X.UC_X86_REG_CS) != SENT:
            raise RuntimeError("8A9A did not come back")
        calls, arg = struct.unpack("<2H", self.mu.mem_read(DS * 16 + CALLS, 4))
        return self.mu.reg_read(X.UC_X86_REG_AX) & 0xFF, calls, arg


def model(refs, cols, colour):
    for s in range(14):
        if refs[s] > 0 and cols[s] == colour:
            return s
    for s in range(16):
        if refs[s] == 0:
            return s
    for s in (14, 15):
        if refs[s] > 0 and cols[s] == colour:
            return s
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    a = ap.parse_args()
    if a.image:
        from fat12 import Fat12, open_hdi
        _raw, _hdr, disk, part = open_hdi(a.image)
        fs = Fat12(disk, part)
        e = fs.find("DDS98/" + nospace.FILE)
        fixed = bytes(fs.read_chain(e["cluster"], e["size"]))
        check(nospace.state(fixed) == "fixed", f"{a.image}: the fix is in")
        orig = nospace.apply_to(fixed, revert=True)
    else:
        orig = open(os.path.join(WORK, "files", "DDS98", nospace.FILE), "rb").read()
        check(nospace.state(orig) == "orig", "files/DDS98: the original")
        fixed = nospace.apply_to(orig)

    print("the file")
    diff = [i for i in range(len(orig)) if orig[i] != fixed[i]]
    check(len(orig) == len(fixed) and diff == [nospace.AT, nospace.AT + 1], f"differs at {[hex(i) for i in diff]}")
    _img, relocs = load(fixed)
    img_at = nospace.SEG * 16 + nospace.OFF
    check(not any(p in relocs for p in range(img_at - 1, img_at + 2)), "no relocation in the two bytes")
    check(img_at + 10 in relocs, "the printf call's segment word (0871:8B02) is still relocated")
    check(nospace.apply_to(fixed) == fixed, "apply_to is idempotent")
    check(nospace.apply_to(fixed, revert=True) == orig, "revert gives the original back")

    po, pf = Pal(orig), Pal(fixed)
    other = [0x100 + i for i in range(16)]
    full = [1] * 16
    print("every slot claimed by another colour")
    so, no, co = po.alloc(full, other, 0x223)
    sf, nf, _ = pf.alloc(full, other, 0x223)
    check(so == 2 and no == 1 and co == 0x223, f"original: slot {so}, {no} print(s) of {co:03X}")
    check(sf == 2 and nf == 0, f"fixed: slot {sf}, {nf} print(s)")

    print("the other outcomes")
    cases = []
    cols = other[:]
    cols[5] = cols[9] = 0x223
    cases.append(("claimed 5 and 9 hold it", full, cols, 5))
    refs = full[:]
    refs[7] = 0
    cases.append(("7 unclaimed", refs, other, 7))
    cols = other[:]
    cols[15] = 0x223
    cases.append(("claimed 15 holds it", full, cols, 15))
    refs = full[:]
    refs[3] = 0
    cols = other[:]
    cols[14] = 0x223
    cases.append(("3 unclaimed before a claimed 14 that holds it", refs, cols, 3))
    refs = full[:]
    refs[1] = 0
    cols = other[:]
    cols[12] = 0x223
    cases.append(("a claimed 12 that holds it before an unclaimed 1", refs, cols, 12))
    refs = full[:]
    refs[4] = 0
    cols = other[:]
    cols[4] = 0x223
    cases.append(("an unclaimed slot holding it is only a free slot", refs, cols, 4))
    for what, refs, cols, want in cases:
        ro, pro = po.alloc(refs, cols, 0x223)[:2]
        rf, prf = pf.alloc(refs, cols, 0x223)[:2]
        check(ro == rf == want and pro == prf == 0, f"{what}: slot {ro} / {rf}, prints {pro} / {prf}")

    print("random tables")
    rng = random.Random(98)
    bad = fallbacks = 0
    for _ in range(3000):
        refs = [rng.choice((0, 1, 1, 1, 2, 5)) for _ in range(16)]
        cols = [rng.choice((0x000, 0xFFF, 0x223, 0x445, 0x667, 0x5F4)) for _ in range(16)]
        colour = rng.choice((0x223, 0x445, 0x889, 0x000))
        want = model(refs, cols, colour)
        ro, pro, co = po.alloc(refs, cols, colour)
        rf, prf, _ = pf.alloc(refs, cols, colour)
        fallbacks += want is None
        ok = ro == rf == (2 if want is None else want) and prf == 0 and pro == (want is None)
        ok = ok and (want is not None or co == colour)
        bad += not ok
    check(bad == 0, f"3000 tables ({fallbacks} with no slot): the same slot, the print only in the original")

    print("FAILED" if fails else "all passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
