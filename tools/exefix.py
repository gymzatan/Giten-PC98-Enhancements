#!/usr/bin/env python3
"""The blank-row defect in DDS98.EXE, and the two places that have to change to close it.

The data files write "no equipment" as 0; the running game writes it as 0x7FF, the word reading
0xFFFF with the top five bits - a fitted gem's number - all set. A character's record is built from
its template with the data's own convention (ov32:0EB1) and is put right immediately afterwards by
ov14:0592, which rewrites every slot that does not hold a real item as 0xFFFF. A weapon knocked off
in battle, though, goes through character field 49 (main:20550), which sets the slot's eleven-bit
item number on its own and leaves the rest of the word alone - so the slot ends up holding 0 again.

Two places then hand such a slot back to the inventory without recognising it as empty:

    ov14:03BE   the give-back when a new weapon is equipped over it
    ov12:05FD   the give-back when the equipment menu takes something off

Both ask `(word & 0x7FF) == 0x7FF`, which 0 does not satisfy, so the inventory is handed item number
0 with a count of 1. Item 0 is a stub: its record has no numeric block and no name, so the list draws
a blank row that still takes up one of the sixty-four slots. DLSPACE.EXE was shipped to scrub exactly
that entry out of saved games; fixing these two places means no save ever gets one.

The fix gives both places the test the rest of the game already uses for the same question -
`(word << 5) < 0x20` as a signed compare, which rejects 0 and 0x7FF alike - so each replacement is
the same length as what it replaces and keeps every branch target. The menu site also loses its
`count = max(count, 1)` clamp for a plain `count = 1`: ov14:0592 gives every equipped item a count of
1, and the one kind that carries a real count, ammunition, is handled by the other branch.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FILE = "DDS98.EXE"
APPLY = "apply"
REVERT = "revert"

# `lead` is the code just ahead of the replaced window: it is untouched by the patch and identical in
# the Japanese original and the Chinese build, so lead+window names the site in a whole disk image.
# The menu site needs its window in the search as well - the code right next to it opens with the
# same twenty bytes - which is why the search is always for the complete form, either one.
SITES = (
    {"name": "装备归还", "where": "ov14:03BE", "at": 0x609BE,
     "lead": "8a460a8bf70376f08e46fc268844248b46f4",
     "orig": "80e4073dff077424",
     "fixed": "c1e0053d20007c24",
     "was": "and ah,7 / cmp ax,7FF / je",
     "now": "shl ax,5 / cmp ax,20 / jl"},
    {"name": "菜单卸下", "where": "ov12:05FD", "at": 0x5E7FD,
     "lead": "9a64a78e358bd8368b07368b57028946f68956f8",
     "orig": "83fa017d05c746f80100c1e005c1f805",
     "fixed": "c1e0053d20007c18c1f805c746f80100",
     "was": "cmp dx,1 / jge / mov [bp-8],1 / shl ax,5 / sar ax,5",
     "now": "shl ax,5 / cmp ax,20 / jl / sar ax,5 / mov [bp-8],1"},
)


class FixError(ValueError):
    pass


def forms(site):
    """(original form, fixed form) of a site, each the lead followed by its window."""
    lead = bytes.fromhex(site["lead"])
    return lead + bytes.fromhex(site["orig"]), lead + bytes.fromhex(site["fixed"])


def state(blob):
    """[(site, 'orig' | 'fixed')] read off the executable by offset."""
    out = []
    for s in SITES:
        a, b = bytes.fromhex(s["orig"]), bytes.fromhex(s["fixed"])
        here = bytes(blob[s["at"]:s["at"] + len(a)])
        if here == a:
            out.append((s, "orig"))
        elif here == b:
            out.append((s, "fixed"))
        else:
            raise FixError(f"{s['name']}（{s['where']}）：DDS98.EXE 的 0x{s['at']:X} 处是 "
                           f"{here.hex(' ')}，既不是原版也不是修复后的字节")
    return out


def apply_to(blob, action=APPLY):
    """The executable with both sites in the wanted state."""
    out = bytearray(blob)
    for s, _now in state(blob):
        want = bytes.fromhex(s["fixed"] if action == APPLY else s["orig"])
        out[s["at"]:s["at"] + len(want)] = want
    return bytes(out)


def occurrences(data, form):
    at, hits = 0, []
    while True:
        i = data.find(form, at)
        if i < 0:
            return hits
        hits.append(i)
        at = i + 1


def patch_bytes(data, action=APPLY):
    """(image, changed site names) with both sites moved to the wanted state, each found by its own
    bytes rather than by where a file happens to sit - the same way the .bat patches work."""
    out = bytearray(data)
    changed = []
    for s in SITES:
        a, b = forms(s)
        src, dst = (a, b) if action == APPLY else (b, a)
        here, there = occurrences(out, src), occurrences(out, dst)
        if not here and len(there) == 1:
            continue
        if len(here) != 1 or there:
            raise FixError(f"{s['name']}（{s['where']}）：这个镜像里原样 {len(here)} 处、"
                           f"改后 {len(there)} 处，无法确定要改哪里")
        at = here[0]
        out[at:at + len(dst)] = dst
        changed.append(s["name"])
    return bytes(out), changed


def main(argv):
    """exefix.py [DDS98.EXE] - what state each site is in."""
    path = argv[0] if argv else os.path.join("files", "DDS98", FILE)
    blob = open(path, "rb").read()
    print(f"{path}  {len(blob)} 字节")
    for s, now in state(blob):
        print(f"  {s['name']}（{s['where']}，文件 0x{s['at']:X}）："
              f"{'原版' if now == 'orig' else '已修复'}")
        print(f"      原版 {s['was']}")
        print(f"      修复 {s['now']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
