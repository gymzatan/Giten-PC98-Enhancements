#!/usr/bin/env python3
"""The line the palette allocator prints when a colour finds no slot, kept off the screen.

A picture loaded with kind 0 (0871:8F16) asks 0871:8A9A (the game's s:\\iodrv\\pal_io.c) for a hardware
palette slot for each colour it owns: a claimed slot 0-13 that already holds the colour, else the first slot
nobody claims, else a claimed 14 or 15 that holds it. When all sixteen are claimed by other colours it
prints 「no space(col=%.3x)」 with the C run-time's printf (0000:0708) and returns slot 2. The caller maps the
picture's index to slot 2 and 0871:8B6C writes the colour there and claims it, so the colour that did not fit
is drawn right, and whatever else draws with slot 2 at that moment - a room's middle tone - takes that colour
until slot 2 is written again. The print goes to the text screen, which the game never clears: the line stays
over the picture, one more each time the scene is entered.

The fix is a short jump over the print: 0871:8AF8 `push word [bp+6]` (ff 76) becomes `jmp 8B04` (eb 0a),
landing on the `mov al,2` the print is followed by. The slot the colour gets and what the caller does with it
stay as they were. The bytes jumped over stay in place, the relocated segment word of the printf call
(0871:8B02) among them, so the file keeps every relocation. It goes into every build, with no switch: it mends
nothing but a debugging line.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NAME = "调色板报错屏蔽"
FILE = "DDS98.EXE"
HDR = 0x3800                            # DDS98.EXE's header: file offset = HDR + segment * 16 + offset
SEG, OFF = 0x0871, 0x8AF8
AT = HDR + SEG * 16 + OFF
# the window checked is the whole print, up to the `mov al,2` it jumps to; only its first two bytes change
ORIG = bytes.fromhex("ff 76 06 1e 68 48 0f 9a 08 07 00 00 b0 02")
FIXED = bytes.fromhex("eb 0a") + ORIG[2:]


class NoSpaceError(ValueError):
    pass


def state(blob):
    """'orig' or 'fixed'."""
    now = bytes(blob[AT:AT + len(ORIG)])
    if now == ORIG:
        return "orig"
    if now == FIXED:
        return "fixed"
    raise NoSpaceError(f"{FILE} 第 {AT:#x} 字节起既不是原版也不是修复后的内容")


def apply_to(blob, revert=False):
    """DDS98.EXE with the print skipped (or back in)."""
    state(blob)
    out = bytearray(blob)
    out[AT:AT + len(ORIG)] = ORIG if revert else FIXED
    return bytes(out)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    data = open(a.exe, "rb").read()
    print(f"{a.exe}: {state(data)}")
    out = apply_to(data, revert=a.revert)
    if out != data:
        open(a.exe, "wb").write(out)
        print(f"{a.exe}: {state(out)}")


if __name__ == "__main__":
    main()
