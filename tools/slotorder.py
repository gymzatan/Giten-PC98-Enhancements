#!/usr/bin/env python3
"""In battle the palette allocator hands out free slots from the top, so the enemies leave the background alone.

A picture loaded with kind 0 (0871:8F16) takes a hardware slot for each colour it owns from 0871:8A9A: a
claimed slot 0-13 that already holds the colour, else the first slot nobody claims (counting up from 0), else
a claimed 14 or 15 that holds it, else slot 2. A room scene leaves the room's own colours in 1-3 and, when it
has more than three, in 8, 9, ... in the order it owns them; a 266 background does the same. When a battle
starts (ov16:2101 in a dungeon, 25D5 on the world map) 0871:89D2 with mode 3 saves the sixteen claims and
colours into a buffer, kept at [2F04]:[2F06], and drops the claims on 8-15 (0871:89C2); the battle then
writes 0000 into 14 and 15 and claims them (8B6C, the two colours ov19's animations cycle) and loads the
enemies' pictures. The room or background stays on screen behind the enemies, and those pictures take free
slots counting up - 8 first: whatever of the background is drawn through 8, 9, ... takes the enemies' colours
for the whole battle. At its end the battle puts the saved claims and colours back and frees the buffer
(0871:8A42, which leaves [2F04]:[2F06] null).

The fix: while the battle holds the saved claims ([2F04]:[2F06] not null) and its own mode is the current one
([78C6] 0Bh in a dungeon, 22h on the world map), the free-slot search counts down from 15 instead of up from 0.
14 and 15 are claimed then, so the enemies fill 13, 12, ... and meet the background's slots only when the
background and the enemies together need more than the six slots 8-13. Both tests are needed: a dungeon battle
won against random enemies redraws the corridor (358E:5C00) after putting the claims back, still in mode 0Bh,
and a world-map battle redraws the map after going back to the map's mode, before putting the claims back.
Everything else - and every picture loaded while the battle has a menu, a message or an action of its own
mode up - takes its slots as in the game. The share search before the free-slot search and the 14/15 search
and the fallback after it are the game's own.

The new search lives where 0871:69C2 was: a routine that copies the hardware palette into a 16-word buffer,
which nothing in the program calls, jumps to, or points at (no near or far call or jump, no immediate, no far
pointer, no word of DGROUP with its offset), with no relocation inside. 0871:8ABB, the start of the free-slot
loop, calls it and goes to the game's own exits: 8AF4 (return the slot) when it found one, 8ACF (the 14/15
search) when not. It goes into every build and both translation patches, and the Windows art patch writes it
too, with no switch.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

NAME = "战斗色槽顺序"
FILE = "DDS98.EXE"
HDR = 0x3800                            # DDS98.EXE's header: file offset = HDR + segment * 16 + offset
SEG = 0x0871
CAVE, CAVE_END = 0x69C2, 0x6A2B        # the unused palette read-back routine, up to and with its retf 4
HOOK = 0x8ABB                           # the free-slot loop of 8A9A, up to its last jb at 8ACD
MODE = 0x78C6                           # the current mode ([78C6], 25CA:8012)
BATTLE_MODES = (0x0B, 0x22)
SAVED = 0x2F04                          # the battle's saved claims and colours: far pointer, null outside it
REFS = 0x6CB6                           # the allocator's sixteen claim counts

ORIG_HOOK = bytes.fromhex("33 d2 bb b6 6c 83 3f 00 74 2f 42 83 c3 02 81 fb d6 6c 72 f1")
ORIG_CAVE = bytes.fromhex(
    "c8 0a 00 00 57 56 8b 0e 7e 46 a1 80 46 0b c1 74 52 a1 80 46 8b f9 89 46 fa 8b 46 06 8b 56 08 8b f0"
    " c7 46 f6 10 00 8b 4e f6 8e c2 8e 5e fa 8a 25 26 32 64 01 25 00 0f 26 31 04 8a 45 01 c0 e0 04 26 32"
    " 04 25 f0 00 26 31 04 8a 45 02 26 32 04 25 0f 00 26 31 04 26 80 64 01 0f 83 c7 03 46 46 e2 cd 16 1f"
    " 5e 5f c9 ca 04 00")

# ax is free here: the 14/15 search reloads it from the colour argument and the exit at 8AF4 sets it from dx
CAVE_SRC = f"""
free_slot:
    mov ax, word ptr [{SAVED:#x}]
    or ax, word ptr [{SAVED + 2:#x}]
    jz up_from_0
    cmp word ptr [{MODE:#x}], {BATTLE_MODES[0]:#x}
    je down
    cmp word ptr [{MODE:#x}], {BATTLE_MODES[1]:#x}
    je down
up_from_0:
    xor dx, dx
    mov bx, {REFS:#x}
up:
    cmp word ptr [bx], 0
    je found
    inc dx
    add bx, 2
    cmp bx, {REFS + 32:#x}
    jb up
    clc
    ret
down:
    mov dx, 0xf
    mov bx, {REFS + 30:#x}
dn:
    cmp word ptr [bx], 0
    je found
    dec dx
    sub bx, 2
    cmp bx, {REFS:#x}
    jae dn
    clc
    ret
found:
    stc
    ret
"""
# CAVE_SRC assembled at CAVE. Kept as bytes so tools/winpatch.py, which carries this module into the
# Windows-art patch's .exe, needs no assembler (asm86 needs capstone); tools/slotorder_test.py checks that
# assembling CAVE_SRC still gives exactly these.
CAVE_CODE = bytes.fromhex(
    "a1 04 2f 0b 06 06 2f 74 0e 83 3e c6 78 0b 74 1d 83 3e c6 78 22 74 16 31 d2 bb b6 6c 83 3f 00 74"
    " 23 42 83 c3 02 81 fb d6 6c 72 f1 f8 c3 ba 0f 00 bb d4 6c 83 3f 00 74 0c 4a 83 eb 02 81 fb b6 6c 73 f1"
    " f8 c3 f9 c3")


class SlotOrderError(ValueError):
    pass


def assembled():
    """CAVE_SRC run through tools/asm86.py (needs capstone)."""
    from asm86 import assemble
    code, _labels = assemble(CAVE_SRC, org=CAVE)
    return code


def cave_code():
    if len(CAVE_CODE) > CAVE_END - CAVE:
        raise SlotOrderError(f"the search is {len(CAVE_CODE)} bytes, the routine it replaces {CAVE_END - CAVE}")
    return CAVE_CODE


def hook_code():
    """call free_slot / jc 8AF4 (return dx) / jmp 8ACF (the 14-15 search), the rest of the old loop as nops."""
    rel = (CAVE - (HOOK + 3)) & 0xFFFF
    code = bytes([0xE8, rel & 0xFF, rel >> 8, 0x72, 0x8AF4 - (HOOK + 5), 0xEB, 0x8ACF - (HOOK + 7)])
    return code + b"\x90" * (len(ORIG_HOOK) - len(code))


def fixed_cave():
    code = cave_code()
    return code + ORIG_CAVE[len(code):]


SITES = ((CAVE, ORIG_CAVE, fixed_cave), (HOOK, ORIG_HOOK, hook_code))


def at(off):
    return HDR + SEG * 16 + off


def state(blob):
    """'orig' or 'fixed'."""
    forms = set()
    for off, orig, fixed in SITES:
        now = bytes(blob[at(off):at(off) + len(orig)])
        if now == orig:
            forms.add("orig")
        elif now == fixed():
            forms.add("fixed")
        else:
            raise SlotOrderError(f"{FILE} 第 {at(off):#x} 字节起既不是原版也不是修复后的内容")
    if len(forms) != 1:
        raise SlotOrderError(f"{FILE} 的两处只改了一处")
    return forms.pop()


def apply_to(blob, revert=False):
    """DDS98.EXE with the search counting down in battle (or the game's own back)."""
    state(blob)
    out = bytearray(blob)
    for off, orig, fixed in SITES:
        new = orig if revert else fixed()
        out[at(off):at(off) + len(new)] = new
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
