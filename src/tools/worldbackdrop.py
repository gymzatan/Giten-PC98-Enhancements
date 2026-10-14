#!/usr/bin/env python3
"""World-map areas without a battle backdrop take their neighbours' backdrop.

    worldbackdrop.py show                 the world map's backdrops, as the game has them and as built
    worldbackdrop.py check [IMAGE.hdi ...]   default: the dist image

The world map is 54 regions of 288x200 pixels (ET1000h + region: 6 columns 1-6 by 9 rows 1-9 of an 8-wide
grid), each split into 9x5 areas of 32x40 pixels, plus a 46th row the encounter code uses for the whole region
when [38B4] bit 0 is set (358E:AB5E). A region file is read raw (no cipher, 07B1:02B2): a length word, then one
13-byte row per area, byte 0 the battle backdrop. 358E:ABF5 copies it to [3966], and the only reader,
358E:AF2C, loads entry [3966] of ET10FF (3 bytes: picture 5000h | b0, variant b1, frame b2) as the battle's
room picture with 358E:559E. Entry 0 is picture 5000h, an empty 8x8 frame that sets no colour, and 358E:55EA
draws nothing but the backdrop while one is loaded, so in 665 of the 2484 areas a battle is fought on black.

Here every area with backdrop 0 takes one from the areas next to it on the whole map, region borders
included: the areas that have one are spread outward one step at a time, and an area reached in a step takes
the backdrop most of its already-filled neighbours (north, east, south, west) have; a tie goes to the one most
common in its own region, then to the lower number. A region's 46th row takes the backdrop most common among
its 45 areas once they are filled. Nothing else in the rows changes. ET10FF is not touched.

    plan(src_dir)        {file name: new bytes} for every region file that changes
    apply_to(files)      the changed region files into the build's files
    check(fs)            what is wrong with an image's region files ([] = nothing)
"""
import collections
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
SRC = os.path.join(WORK, "files", "DDS98")
ROW = 13
COLS, ROWS = 9, 5          # areas in a region
EXTRA = COLS * ROWS        # the region-wide row


class BackdropError(ValueError):
    pass


def regions(src_dir=SRC):
    """{region: (file name, raw bytes)} of the world map's region files."""
    out = {}
    for path in sorted(glob.glob(os.path.join(src_dir, "ET10[0-9A-F][0-9A-F].BIN"))):
        name = os.path.basename(path)
        r = int(name[4:6], 16)
        if r != 0xFF:
            out[r] = (name, open(path, "rb").read())
    return out


def rows_of(raw):
    """The 46 rows of a region file. ET1011 has two bytes more after its last row (its row 45 is 15 bytes long
    in the data; the game reads 13 bytes a row by number, so they are never read); they stay as they are."""
    n = struct.unpack_from("<H", raw, 0)[0]
    if n + 2 != len(raw) or not 0 <= n - ROW * (EXTRA + 1) < ROW:
        raise BackdropError(f"a region file of {len(raw)} bytes is not {EXTRA + 1} rows of {ROW}")
    return [bytearray(raw[2 + ROW * k:2 + ROW * (k + 1)]) for k in range(EXTRA + 1)]


def filled(src_dir=SRC):
    """{region: [backdrop of each of the 46 rows]} as the game has them, and as filled here."""
    game = {r: [row[0] for row in rows_of(raw)] for r, (_n, raw) in regions(src_dir).items()}
    cell = {}
    for r, bds in game.items():
        for a in range(EXTRA):
            cell[((r % 8) * COLS + a % COLS, (r // 8) * ROWS + a // COLS)] = (r, a)
    value = {xy: game[r][a] for xy, (r, a) in cell.items() if game[r][a]}
    region_common = {r: collections.Counter(b for b in bds[:EXTRA] if b) for r, bds in game.items()}
    frontier = [xy for xy in cell if xy not in value]
    while frontier:
        step = {}
        for (x, y) in frontier:
            near = [value[n] for n in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)) if n in value]
            if near:
                count = collections.Counter(near)
                r = cell[(x, y)][0]
                step[(x, y)] = min(count, key=lambda b: (-count[b], -region_common[r][b], b))
        if not step:
            raise BackdropError(f"{len(frontier)} areas have no area with a backdrop anywhere near them")
        value.update(step)
        frontier = [xy for xy in frontier if xy not in value]
    out = {}
    for r, bds in game.items():
        new = list(bds)
        for a in range(EXTRA):
            new[a] = value[((r % 8) * COLS + a % COLS, (r // 8) * ROWS + a // COLS)]
        if not new[EXTRA]:
            count = collections.Counter(new[:EXTRA])
            new[EXTRA] = min(count, key=lambda b: (-count[b], b))
        out[r] = (bds, new)
    return out


def plan(src_dir=SRC):
    files = regions(src_dir)
    out = {}
    for r, (old, new) in filled(src_dir).items():
        if old == new:
            continue
        name, raw = files[r]
        rows = rows_of(raw)
        for k, b in enumerate(new):
            rows[k][0] = b
        out[name] = raw[:2] + b"".join(bytes(row) for row in rows) + raw[2 + ROW * (EXTRA + 1):]
    return out


def apply_to(files, src_dir=SRC):
    for name, data in plan(src_dir).items():
        if name in files:
            raise BackdropError(f"{name} is already changed by another step of the build")
        files[name] = data


def check(fs):
    """Problems with an opened image's region files (a fat12 filesystem)."""
    out = []
    want = plan()
    for r, (name, raw) in regions().items():
        e = fs.find(f"DDS98/{name}")
        if e is None:
            out.append(f"{name} missing")
            continue
        got = bytes(fs.read_chain(e["cluster"], e["size"]))
        if got != want.get(name, raw):
            out.append(f"{name} differs from the filled backdrops")
    return out


def show():
    res = filled()
    width, height = 8 * COLS, 10 * ROWS
    maps = {"game": [[" "] * width for _ in range(height)], "built": [[" "] * width for _ in range(height)]}
    for r, (old, new) in res.items():
        for a in range(EXTRA):
            x, y = (r % 8) * COLS + a % COLS, (r // 8) * ROWS + a // COLS
            maps["game"][y][x] = "0123456789A"[old[a]] if old[a] else "."
            maps["built"][y][x] = "0123456789A"[new[a]]
    print("the world map's battle backdrops (ET10FF entry; . = none), as the game has them | as built:")
    for g, b in zip(maps["game"], maps["built"]):
        if g.count(" ") < width:
            print("".join(g) + "   " + "".join(b))
    changed = sum(1 for old, new in res.values() for a in range(EXTRA + 1) if old[a] != new[a])
    zeros = sum(1 for old, _new in res.values() for b in old[:EXTRA] if not b)
    print(f"{zeros} areas without a backdrop in the game; {changed} rows changed (with the region-wide rows)")
    by = collections.Counter(new[a] for old, new in res.values() for a in range(EXTRA) if not old[a])
    print("filled with:", dict(sorted(by.items())))


def main(argv):
    if argv[:1] == ["show"]:
        show()
        return 0
    if argv[:1] != ["check"]:
        print(__doc__)
        return 2
    from fat12 import Fat12, open_hdi
    images = argv[1:] or [os.path.join(WORK, "dist", "Giten CN", "Giten_CN.hdi")]
    bad = 0
    for image in images:
        _raw, _hdr, disk, part = open_hdi(image)
        problems = check(Fat12(disk, part))
        print(f"{image}: " + ("ok" if not problems else "; ".join(problems)))
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
