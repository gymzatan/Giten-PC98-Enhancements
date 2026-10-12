#!/usr/bin/env python3
"""Every software interrupt the game raises through the C runtime.

MS C's int86/int86x (0000:0DCE here) builds `INT nn; RETF` on the stack and far
calls it, so a byte scan for `CD nn` misses these. The interrupt number is the
last immediate pushed before the call, and the register image is a REGS block
on the caller's stack; this lists each call site with the interrupt number and
any AH value stored into the block just before it.
"""
import collections
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mz import MZ, overlays  # noqa: E402

INT86 = (0x0000, 0x0DCE)


def scan_image(label, image, seg_of, far_target):
    img = bytes(image)
    pat = b"\x9a" + struct.pack("<HH", far_target[1], far_target[0])
    rows = []
    for mm in re.finditer(re.escape(pat), img):
        k = mm.start()
        back = img[max(0, k - 40):k]
        intno = None
        for q in range(len(back) - 2, -1, -1):
            if back[q] == 0x6A:                       # push imm8
                intno = back[q + 1]
                break
        ah = None
        for q in range(len(back) - 4, -1, -1):        # mov byte ptr [bp-xx], imm8
            if back[q] == 0xC6 and back[q + 1] == 0x46:
                ah = back[q + 3]
                break
        rows.append((seg_of(k), intno, ah))
    return rows


def main(exe="files/DDS98/DDS98.EXE"):
    m = MZ(exe)
    segs = sorted({0x0, 0x535, 0x871, 0x1603, 0x25CA, 0x358E, 0x439F, 0x4802, 0x4900, 0x4E39, 0x4F11})

    def seg_of(lin):
        s = max(x for x in segs if x * 16 <= lin)
        return f"{s:04X}:{lin - s * 16:04X}"

    rows = scan_image("main", m.image, seg_of, INT86)
    for num, ov in sorted(overlays(exe).items()):
        rows += scan_image(f"ov{num}", ov.image, lambda k, n=num: f"ov{n:02d}:{k:04X}", INT86)
    tally = collections.Counter((i, a) for _w, i, a in rows)
    print(f"{len(rows)} int86 call sites")
    for (i, a), n in sorted(tally.items(), key=lambda x: (x[0][0] or 0, x[0][1] or 0)):
        print(f"   INT {i if i is None else f'{i:02X}h'}  AH={a if a is None else f'{a:02X}h'}  x{n}")
    for where, i, a in rows:
        if i == 0x18:
            print(f"   INT 18h at {where}  AH={a if a is None else f'{a:02X}h'}")


if __name__ == "__main__":
    main(*sys.argv[1:])
