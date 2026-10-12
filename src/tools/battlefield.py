#!/usr/bin/env python3
"""The world map's battle field without a ceiling or floor, so a world-map battle ends in black.

    battlefield.py check [IMAGE.hdi ...]      default: the dist image

Battles on the world map are fought on M00FF 「２Ｄ戦闘フィールド」, a 7x7 map without walls that the
world map loads as its 3D map (ov42 state 0: 358E:597C(FF, 0)); the battle's backdrop is that map's
room picture. When the battle ends (mode 22h, state 6 at ov16:285A) the game frees the backdrop,
puts the world map's palette table back and asks for one more redraw of the 3D view (358E:8692; the
handler's tail 869A -> 86C8 -> 8406). With no backdrop left, the view shows M00FF's ceiling and floor
- wall set 0, FC1000 entries 4 and 5 - in the world map's greens for a few frames before the fade: a
green gradient in the original, a green corridor with the Windows art.

This gives M00FF a wall set of its own, 8. FC1080.BIN is the game's FC1000.BIN with every visible
pixel of entries 4 and 5 turned to colour 0, frames and boxes unchanged; every other entry is kept
as it is. M00FF's one section names set 8 at +22h. 358E:5514 loads wall set s as 1000h+s*10h
(entry 0 with kind 1, entries 4 and 5 with kind 2), and no other map names set 8, so all that
changes is what those last frames show: black. M00FF has no walls, so entry 0's pieces are never
drawn; its palette goes into slots 0-3 when the world map loads M00FF, and the world map's tiles
write their own colours over 1-3 before anything is drawn with them. The Windows art patch does not
carry FC1080 (the file is the same in both builds); it sets M00FF's door byte to 8 with every other
section's, and its FC1400 has an entry 8.

    apply_to(files, added)   M00FF.BIN in files (the build's copy, or the game's own) with set 8,
                             and FC1080.BIN in added
    check(fs)                what is wrong with an image's FC1080.BIN and M00FF.BIN ([] = nothing)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fcencode  # noqa: E402
import fcimage  # noqa: E402
from ddscrypt import decrypt, encrypt  # noqa: E402

SRC = os.path.join(WORK, "files", "DDS98")
MAP = "M00FF.BIN"
BASE = "FC1000.BIN"                     # wall set 0, which M00FF names in the game
FILE = "FC1080.BIN"                     # wall set 8, which no map of the game names
SET, WAS = 8, 0
WALL_AT = 0x22
BLANK = (4, 5)                          # ceiling and floor


class BattlefieldError(ValueError):
    pass


def blacked(entry):
    """An FC entry with every visible pixel of every frame turned to colour 0."""
    img = fcimage.Image(entry)
    edits = {}
    for off, f in fcencode.unique_frames(img).items():
        _w, _h, pix = img.indices(f)
        edits[off] = [None if p is None else 0 for p in pix]
    return fcencode.encode_entry(entry, edits)


def wall_set(base=None):
    """FC1080.BIN made from the game's FC1000.BIN."""
    base = base if base is not None else open(os.path.join(SRC, BASE), "rb").read()
    ents = list(fcimage.entries(base))
    for k in BLANK:
        ents[k] = blacked(ents[k])
    return b"".join(struct.pack("<I", len(e)) + e for e in ents)


def section(plain):
    """The offset of M00FF's one section."""
    _zero, _name, count = struct.unpack_from("<3H", plain, 0)
    if count != 1:
        raise BattlefieldError(f"{MAP} has {count} sections, the game's has one")
    return struct.unpack_from("<H", plain, 6)[0]


def with_set(data):
    """M00FF.BIN naming wall set 8. The build's copy differs from the game's in its name only."""
    word, plain = decrypt(data)
    plain = bytearray(plain)
    at = section(plain) + WALL_AT
    if plain[at] not in (WAS, SET):
        raise BattlefieldError(f"{MAP} names wall set {plain[at]}, not the game's {WAS}")
    plain[at] = SET
    return encrypt(bytes(plain), header_word=word)


def apply_to(files, added, src=SRC):
    data = files.get(MAP) or open(os.path.join(src, MAP), "rb").read()
    files[MAP] = with_set(data)
    added[FILE] = wall_set(open(os.path.join(src, BASE), "rb").read())


def check(fs):
    """Problems with FC1080.BIN and M00FF.BIN in an opened image (a fat12 filesystem)."""
    out = []
    e = fs.find(f"DDS98/{FILE}")
    if e is None:
        return [f"{FILE} missing"]
    got = list(fcimage.entries(bytes(fs.read_chain(e["cluster"], e["size"]))))
    base = list(fcimage.entries(open(os.path.join(SRC, BASE), "rb").read()))
    if len(got) != len(base):
        out.append(f"{FILE} has {len(got)} entries, {BASE} {len(base)}")
    for k, (mine, theirs) in enumerate(zip(got, base)):
        if k not in BLANK:
            if mine != theirs:
                out.append(f"{FILE} entry {k} differs from {BASE}'s")
            continue
        a, b = fcimage.Image(mine), fcimage.Image(theirs)
        if len(a.frames) != len(b.frames):
            out.append(f"{FILE} entry {k}: {len(a.frames)} frames, {BASE} {len(b.frames)}")
            continue
        for f in range(len(a.frames)):
            wa, ha, pa = a.indices(f)
            wb, hb, pb = b.indices(f)
            if (wa, ha) != (wb, hb) or a.frames[f][:4] != b.frames[f][:4]:
                out.append(f"{FILE} entry {k} frame {f}: box differs from {BASE}'s")
            elif [p is None for p in pa] != [p is None for p in pb]:
                out.append(f"{FILE} entry {k} frame {f}: visible pixels differ from {BASE}'s")
            elif any(p not in (None, 0) for p in pa):
                out.append(f"{FILE} entry {k} frame {f}: draws colours other than 0")
    e = fs.find(f"DDS98/{MAP}")
    _word, plain = decrypt(bytes(fs.read_chain(e["cluster"], e["size"])))
    got_set = plain[section(plain) + WALL_AT]
    if got_set != SET:
        out.append(f"{MAP} names wall set {got_set}, not {SET}")
    return out


def main(argv):
    from fat12 import Fat12, open_hdi
    if argv[:1] != ["check"]:
        print(__doc__)
        return 2
    images = argv[1:] or [os.path.join(WORK, "dist", "Redux", "Game.hdi")]
    bad = 0
    for image in images:
        _raw, _hdr, disk, part = open_hdi(image)
        problems = check(Fat12(disk, part))
        print(f"{image}: " + ("ok" if not problems else "; ".join(problems)))
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
