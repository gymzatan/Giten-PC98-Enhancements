#!/usr/bin/env python3
"""ctxfree_test.py - tools/ctxfree.py on an emulated CPU (unicorn): the original DDS98.EXE and the one with the fix,
with the game's m_calloc (0871:79F0) and m_free (0871:7ABA) replaced by stubs that count their calls and keep their
arguments; everything else runs the game's own code.

  * 1603:73D6 makes the context node the script runner uses: one m_calloc of 12 bytes, the node zeroed but for
    its tag and data words (both 0 when the runner calls it);
  * the tail of the script runner 1603:58EE (from 1603:5923, the node being the current context at [618A]:08E2,
    as 1603:7372 leaves it): the original tidies the node and never frees it, the fixed one frees exactly that
    node, once; both return the same value with the same stack;
  * the fixed file differs from the original in the call's displacement alone, which no relocation touches;
    apply_to is idempotent and apply_to(..., revert=True) gives the original back.

    ctxfree_test.py [--image HDI]

With an image, its DDS98.EXE is the fixed program (with every other fix of the build in it) and the same file
with this fix taken out the original.
"""
import argparse
import os
import struct
import sys

from unicorn import UC_ARCH_X86, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ctxfree  # noqa: E402
from asm86 import assemble  # noqa: E402
from mz import MZ  # noqa: E402

LOAD = 0x1000
DS = LOAD + 0x48FC                      # DGROUP
SCRIPT = LOAD + ctxfree.SEG             # 1603
RT = LOAD + 0x0871                      # m_calloc / m_free live here
SENT = 0xD000                           # a hlt the far returns come back to
NODE = 0xFF00                           # where the m_calloc stub hands out its block (DGROUP)
CALLOCS, SIZE, FREES, FREED = 0xFFE0, 0xFFE2, 0xFFE4, 0xFFE6     # the stubs' counters and arguments
CTXSEG = DS                             # the segment [618A] names; the current context is at CTXSEG:08E2
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def load(blob):
    path = os.path.join(WORK, "build", "_ctxfree_test.exe")
    with open(path, "wb") as f:
        f.write(blob)
    try:
        return bytes(MZ(path, base=LOAD).image), MZ(path).reloc_set
    finally:
        os.remove(path)


class Game:
    def __init__(self, blob):
        img, _ = load(blob)
        self.mu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.mu.mem_map(0, 0x110000)
        self.mu.mem_write(LOAD * 16, img)
        # m_calloc(size, count) with DS = DGROUP: count the call, keep size * count, hand out DS:NODE zeroed
        calloc = assemble(f"push bp\nmov bp, sp\ninc word ptr [{CALLOCS:#x}]\nmov ax, word ptr [bp + 6]\n"
                          f"mul word ptr [bp + 8]\nmov word ptr [{SIZE:#x}], ax\nmov ax, {NODE:#x}\nmov dx, ds\n"
                          f"pop bp\nretf 4", org=0x79F0)[0]
        self.mu.mem_write(RT * 16 + 0x79F0, calloc)
        # m_free(far pointer): count the call, keep the offset it was handed
        free = assemble(f"push bp\nmov bp, sp\ninc word ptr [{FREES:#x}]\nmov ax, word ptr [bp + 6]\n"
                        f"mov word ptr [{FREED:#x}], ax\npop bp\nretf 4", org=0x7ABA)[0]
        self.mu.mem_write(RT * 16 + 0x7ABA, free)
        self.mu.mem_write(SENT * 16, b"\xf4")

    def word(self, off, seg=DS):
        return struct.unpack("<H", self.mu.mem_read(seg * 16 + off, 2))[0]

    def run(self, ip, sp, bp, si=0):
        for reg, v in ((X.UC_X86_REG_SS, DS), (X.UC_X86_REG_DS, DS), (X.UC_X86_REG_ES, DS),
                       (X.UC_X86_REG_CS, SCRIPT), (X.UC_X86_REG_IP, ip), (X.UC_X86_REG_SP, sp),
                       (X.UC_X86_REG_BP, bp), (X.UC_X86_REG_SI, si)):
            self.mu.reg_write(reg, v)
        self.mu.emu_start(SCRIPT * 16 + ip, SENT * 16, count=200_000)
        if self.mu.reg_read(X.UC_X86_REG_CS) != SENT:
            raise RuntimeError(f"1603:{ip:04X} did not come back")

    def new_node(self):
        """1603:73D6(data 0:0, tag 0), as 1603:5900 calls it -> (node offset, segment)."""
        self.mu.mem_write(DS * 16 + CALLOCS, bytes(8))
        self.mu.mem_write(DS * 16 + NODE, b"\xaa" * 12)
        sp = 0xA000 - 10
        self.mu.mem_write(DS * 16 + sp, struct.pack("<5H", 0, SENT, 0, 0, 0))
        self.run(0x73D6, sp, 0)
        return self.mu.reg_read(X.UC_X86_REG_AX), self.mu.reg_read(X.UC_X86_REG_DX)

    def tail(self, node):
        """The runner from 1603:5923 with node the current context -> (frees, freed offset, ax, sp)."""
        self.mu.mem_write(DS * 16 + FREES, bytes(4))
        self.mu.mem_write(DS * 16 + 0x618A, struct.pack("<H", CTXSEG))
        self.mu.mem_write(CTXSEG * 16 + 0x08E2, struct.pack("<2H", node, DS))
        self.mu.mem_write(DS * 16 + 0x1CEC, bytes(4))           # C324: no pending entries
        bp = 0xA000
        # 58EE's frame: saved si below bp, old bp, the far return, its 6 bytes of arguments
        self.mu.mem_write(DS * 16 + bp - 2, struct.pack("<H", 0x1234))
        self.mu.mem_write(DS * 16 + bp, struct.pack("<6H", 0, 0, SENT, 1, 2, 3))
        self.run(0x5923, bp - 2, bp, si=0x5678)
        return (self.word(FREES), self.word(FREED), self.mu.reg_read(X.UC_X86_REG_AX),
                self.mu.reg_read(X.UC_X86_REG_SP))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    a = ap.parse_args()
    if a.image:
        from fat12 import Fat12, open_hdi
        _raw, _hdr, disk, part = open_hdi(a.image)
        fs = Fat12(disk, part)
        e = fs.find("DDS98/" + ctxfree.FILE)
        fixed = bytes(fs.read_chain(e["cluster"], e["size"]))
        check(ctxfree.state(fixed) == "fixed", f"{a.image}: the fix is in")
        orig = ctxfree.apply_to(fixed, revert=True)
    else:
        orig = open(os.path.join(WORK, "files", "DDS98", ctxfree.FILE), "rb").read()
        check(ctxfree.state(orig) == "orig", "files/DDS98: the original")
        fixed = ctxfree.apply_to(orig)

    print("the file")
    diff = [i for i in range(len(orig)) if orig[i] != fixed[i]]
    call = ctxfree.AT + 9                                   # the call 73BE / 7416 in the window
    check(len(orig) == len(fixed) and diff == [call + 1], f"differs at {[hex(i) for i in diff]}")
    _img, relocs = load(fixed)
    img_at = ctxfree.SEG * 16 + ctxfree.OFF
    check(not any(p in relocs for p in range(img_at - 1, img_at + len(ctxfree.ORIG))),
          "no relocation in the window")
    check(ctxfree.apply_to(fixed) == fixed, "apply_to is idempotent")
    check(ctxfree.apply_to(fixed, revert=True) == orig, "revert gives the original back")

    go, gf = Game(orig), Game(fixed)
    print("the context node (1603:73D6)")
    for name, g in (("original", go), ("fixed", gf)):
        off, seg = g.new_node()
        node = bytes(g.mu.mem_read(seg * 16 + off, 12))
        check(g.word(CALLOCS) == 1 and g.word(SIZE) == 12 and (off, seg) == (NODE, DS) and node == bytes(12),
              f"{name}: {g.word(CALLOCS)} m_calloc of {g.word(SIZE)} bytes, node {node.hex(' ')}")

    print("the runner's tail (1603:5923)")
    fo, oo, ao, so = go.tail(NODE)
    ff, of, af, sf = gf.tail(NODE)
    check(fo == 0, f"original: the node is not freed ({fo} m_free)")
    check(ff == 1 and of == NODE, f"fixed: the node is freed once ({ff} m_free of {of:04X})")
    check(ao == af == 0x5678 and so == sf, f"same return value ({ao:04X} / {af:04X}) and stack ({so:04X} / {sf:04X})")

    print("FAILED" if fails else "all passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
