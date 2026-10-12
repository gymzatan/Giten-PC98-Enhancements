#!/usr/bin/env python3
"""Make an HDI boot straight into partition 1, skipping NEC's fixed-disk boot menu.

NEC's menu IPL ("IPL1" at sector 0 + 4, menu version 2.30) keeps its auto-boot
setting in sector 0 at offset 0x1FA: 0x80 boots the first partition without
waiting. That byte was found by letting the menu itself set auto-boot (Space)
and diffing the image - a single byte changed, 00 -> 80. Giten's image carries
the same IPL, so the same byte applies.

    autoboot.py image.hdi        set the flag in place (idempotent)
"""
import struct
import sys

# Six bytes from the end of sector 0, whatever that sector's size is: dumps of this game come both
# with 512-byte sectors and with 256-byte ones, and the byte sits just before 55 AA either way.
FLAG_BACK = 6
FLAG_AUTOBOOT = 0x80


def set_autoboot(path):
    with open(path, "r+b") as f:
        head = f.read(32)
        hdr = struct.unpack_from("<I", head, 8)[0]
        sector = struct.unpack_from("<I", head, 16)[0]
        f.seek(hdr)
        sector0 = f.read(sector)
        if sector0[4:8] != b"IPL1" or sector0[-2:] != b"\x55\xaa":
            raise SystemExit(f"{path}: not NEC's menu IPL (sig {sector0[4:8]!r}), not touching it")
        at = sector - FLAG_BACK
        before = sector0[at]
        if before not in (0x00, FLAG_AUTOBOOT):
            raise SystemExit(f"{path}: unexpected auto-boot byte {before:#04x}")
        f.seek(hdr + at)
        f.write(bytes([FLAG_AUTOBOOT]))
    return before


if __name__ == "__main__":
    for p in sys.argv[1:]:
        was = set_autoboot(p)
        print(f"{p}: auto-boot byte {was:#04x} -> {FLAG_AUTOBOOT:#04x}")
