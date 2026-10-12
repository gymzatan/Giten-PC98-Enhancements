#!/usr/bin/env python3
"""Self-test of fcencode.py. Run from work/.

    fcencode_test.py          cell codes against the decoder, an edited entry, frames given new
                              boxes, refusals
    fcencode_test.py corpus   also every entry of files/DDS98/FC*.BIN encoded unedited:
                              the same layout, palettes, flags, dictionaries and frame
                              words as the game data (a few minutes)
"""
import glob
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fcimage  # noqa: E402
from fcencode import CellEncoder, EncodeError, encode_entry, frame_box, frame_offsets, unique_frames  # noqa: E402

SRC = "files/DDS98"
FAILS = []
# what a picture decoded before may leave in the cell decoder's buffer (the game never clears it)
LEFTOVER = bytes((i * 37 + 11) & 0xFF for i in range(32))


def expect(ok, what):
    if not ok:
        FAILS.append(what)
        print("FAIL", what)


def fc_entry(stem, k):
    return fcimage.entries(open(os.path.join(SRC, stem + ".BIN"), "rb").read())[k]


def test_cell_codes():
    rng = random.Random(1997)
    enc = CellEncoder()
    targets, stream, starts = [], bytearray(), []
    for _ in range(30000):
        t = []
        cols = enc.cols or [(0x00,) * 8] * 4
        for p in range(4):
            r = rng.random()
            if r < 0.08:
                col = None
            elif r < 0.25:
                col = (rng.choice([0x00, 0xFF]),) * 8
            elif r < 0.40:
                col = cols[rng.randrange(4)]
            elif r < 0.50 and p:
                col = t[rng.randrange(p)] or (0x00,) * 8
            elif r < 0.65:
                base = cols[rng.randrange(3)]
                col = tuple(rng.randrange(256) if rng.random() < 0.2 else v for v in base)
            elif r < 0.80:
                fill = rng.choice([0x00, 0xFF])
                col = tuple(rng.randrange(256) if rng.random() < 0.25 else fill for _ in range(8))
            elif r < 0.90:
                v = rng.randrange(256)
                col = []
                for _r in range(8):
                    if rng.random() < 0.3:
                        v = rng.randrange(256)
                    col.append(v)
                col = tuple(col)
            else:
                col = tuple(rng.randrange(256) for _ in range(8))
            t.append(col)
        if rng.random() < 0.05:
            t = list(cols)
        starts.append(len(stream))
        stream += enc.encode(t)
        targets.append(t)
    dec = fcimage.CellDecoder(bytes(stream), 0, LEFTOVER)
    bad = 0
    modes = set()
    for start, t in zip(starts, targets):
        if dec.p != start:
            bad += 1
            break
        modes.add(stream[start] & 0x0F)
        buf = dec.cell()
        for p in range(4):
            if t[p] is not None and tuple(buf[4 * r + p] for r in range(8)) != t[p]:
                bad += 1
    expect(bad == 0 and dec.p == len(stream), f"cell codes decode to their targets ({bad} wrong)")
    expect(modes == set(range(15)), f"cell modes 0-14 all used (used {sorted(modes)})")
    print(f"cell codes: {len(targets)} cells, {len(stream)} bytes, modes {sorted(modes)}")


def expect_whatever_came_before(entry, what):
    """The stream opens with a cell coded in full, and every cell decodes the same whatever the
    picture decoded before left in the buffer - the blank cell 0 included, which the battle's 2x
    drawer draws for every empty word."""
    img = fcimage.Image(entry)
    expect(entry[img.data_start + 14] & 0x0F not in (14, 15), f"{what}: the first cell is coded in full")
    expect(fcimage.Image(entry, LEFTOVER).cells == img.cells,
           f"{what}: cells decode the same whatever the decoder's buffer held before")


def test_edit():
    stem, k = "FC5030", 3                              # weapon shop, sign 火気厳禁
    entry = fc_entry(stem, k)
    img = fcimage.Image(entry)
    first = unique_frames(img)
    o, f = next(iter(first.items()))
    W, H, pix = img.indices(f)
    rng = random.Random(3)
    edited = list(pix)
    for y in range(20, 60):
        for x in range(260, 340):
            edited[y * W + x] = None if (x + y) % 7 == 0 else rng.randrange(16)
    new = encode_entry(entry, {o: edited})
    out = fcimage.Image(new)
    expect(out.indices(f)[2] == edited, "edited frame decodes to the edit")
    expect_whatever_came_before(new, "edited entry")
    expect(out.palettes == img.palettes and out.pal_head == img.pal_head
           and out.pal_tail == img.pal_tail and out.no_remap == img.no_remap,
           "palettes and flags kept")
    w, h = img.frames[f][2:4]
    kept = all(a & 0xF000 == b & 0xF000 for i, (a, b) in enumerate(zip(img.frames[f][4], out.frames[f][4]))
               if not (32 <= i % w <= 42 and 2 <= i // w <= 7))
    expect(kept, "cells outside the edit keep kind and flip bits")
    same = encode_entry(entry, {})
    expect(fcimage.Image(same).frames == img.frames, "unedited entry keeps its frame words")
    reuse = list(pix)
    for y in range(8):
        for x in range(8):
            reuse[(16 + y) * W + 8 + x] = pix[y * W + 7 - x]    # cell (1,2) := cell (0,0) mirrored
    got = fcimage.Image(encode_entry(entry, {o: reuse}))
    expect(got.frames[f][4][2 * w + 1] & 0x3FFF == img.frames[f][4][0] & 0x3FFF
           and got.frames[f][4][2 * w + 1] & 0xC000 == (img.frames[f][4][0] & 0xC000) ^ 0x8000,
           "a mirrored copy of a cell reuses it with the horizontal flip the entry already uses")
    print(f"edit: {stem} entry {k} {len(entry)} -> {len(new)} bytes (unedited {len(same)}), "
          f"counts {img.counts} -> {out.counts}")


def test_mixed_edit():
    stem, k = "FC0000", 0                              # main screen frame: kinds 1 and 3, no remap
    entry = fc_entry(stem, k)
    img = fcimage.Image(entry)
    o, f = next(iter(unique_frames(img).items()))
    W, _H, pix = img.indices(f)
    w = img.frames[f][2]
    colour = {16: 1, 17: 3, 18: 7, 19: 12}             # cell row -> colour, with transparent pixels
    edited = list(pix)
    for cy, c in colour.items():
        for y in range(cy * 8, cy * 8 + 8):
            for x in range(16, 120):
                edited[y * W + x] = c if (x + y) % 5 else None
    new = encode_entry(entry, {o: edited})
    out = fcimage.Image(new)
    expect(out.indices(f)[2] == edited, "kind 1/3 entry: edited frame decodes to the edit")
    expect_whatever_came_before(new, "kind 1/3 entry")
    was = {(img.frames[f][4][cy * w + cx] >> 12) & 3 for cy in colour for cx in range(2, 14)}
    got = {cy: {(out.frames[f][4][cy * w + cx] >> 12) & 3 for cx in range(2, 14)} for cy in colour}
    expect(was == {3} and got == {16: {3}, 17: {2}, 18: {1}, 19: {0}},
           f"kind 3 cells take the kind their colours need (was {was}, now {got})")
    print(f"mixed edit: {stem} entry {k} counts {img.counts} -> {out.counts}")


def contiguous(layout):
    """The layout is its offset table and then its records, back to back, nothing else."""
    _head, n = struct.unpack_from("<2H", layout, 0)
    at = 4 + 2 * n
    for o in sorted(set(frame_offsets(layout))):
        if o != at:
            return False
        w, h = struct.unpack_from("<2H", layout, o + 4)
        at = o + 8 + 2 * w * h
    return at == len(layout)


def test_boxes():
    stem, k = "FC2870", 2                              # 跺脚鬼: frames 0-2 share one record, 3 and 4 their own
    entry = fc_entry(stem, k)
    img = fcimage.Image(entry)
    offs = frame_offsets(img.layout)
    o0, o3, o4 = offs[0], offs[3], offs[4]
    expect(offs[1] == offs[2] == o0 and len({o0, o3, o4}) == 3, f"{stem} entry {k}: frames 0-2 share a record")
    grown = (-5, -18, 9, 20)
    W, H = grown[2] * 8, grown[3] * 8
    pix0 = [None if (x // 3 + y // 5) % 4 == 0 else (x * 7 + y * 3) % 16 for y in range(H) for x in range(W)]
    x3, y3, w3, h3 = frame_box(img, 3)
    moved = (x3 + 1, y3 + 2, w3 - 2, h3 - 3)            # a part of frame 3's own picture, placed where it was
    was3 = img.indices(3)
    pix3 = [was3[2][(y + 16) * was3[0] + x + 8] for y in range(moved[3] * 8) for x in range(moved[2] * 8)]
    new = encode_entry(entry, {o0: pix0, o3: pix3}, {o0: grown, o3: moved})
    out = fcimage.Image(new)
    expect(all(frame_box(out, f) == grown for f in (0, 1, 2)) and out.indices(0)[2] == pix0
           and out.indices(1)[2] == pix0 and len(set(frame_offsets(out.layout)[:3])) == 1,
           "a grown box: the frames sharing it take it together, and it decodes to the edit")
    expect(frame_box(out, 3) == moved and out.indices(3)[2] == pix3, "a moved, smaller box decodes to the edit")
    expect(frame_box(out, 4) == frame_box(img, 4) and out.indices(4)[2] == img.indices(4)[2],
           "a frame without a new box keeps its box and pixels")
    expect(contiguous(out.layout), "the rebuilt layout is its table and records back to back")
    expect_whatever_came_before(new, "entry with new boxes")
    expect(fcimage.Image(encode_entry(new, {})).layout == out.layout, "encoding it again keeps its layout")
    refused(lambda: encode_entry(entry, {}, {o0: grown}), "a box without pixels", "needs the frame's pixels")
    refused(lambda: encode_entry(entry, {o0: img.indices(0)[2]}, {o0: grown}), "pixels of the old size",
            "pixels given")
    refused(lambda: encode_entry(entry, {o0: pix0}, {o0: grown, o0 + 1: grown}), "a box for no frame",
            "no frame at layout offset")
    refused(lambda: encode_entry(entry, {o0: []}, {o0: (0, 0, 0, 4)}), "an empty box", "box at")
    print(f"boxes: {stem} entry {k} {len(entry)} -> {len(new)} bytes, layout {len(img.layout)} -> "
          f"{len(out.layout)}")


def synthetic_entry(w, h):
    layout = struct.pack("<3H4H", 0, 1, 6, 0, 0, w, h) + bytes(2 * w * h)
    enc = CellEncoder()
    stream = enc.encode([(0,) * 8] * 4) + bytes(8)
    return (struct.pack("<H", len(layout)) + layout + struct.pack("<3H", 0, 0, 0)
            + struct.pack("<IBB4H", 10 + len(stream), 0, 0, 1, 0, 0, 0) + stream)


def refused(fn, what, needle):
    try:
        fn()
    except EncodeError as e:
        expect(needle in str(e), f"{what}: message {str(e)!r}")
        return
    expect(False, f"{what}: not refused")


def test_refusals():
    refused(lambda: encode_entry(fc_entry("FC0000", 4), {}), "cells drawn by number", "no frame references")
    entry = fc_entry("FC5030", 3)
    o = next(iter(unique_frames(fcimage.Image(entry))))
    refused(lambda: encode_entry(entry, {o: [0] * 10}), "wrong pixel count", "pixels given")
    refused(lambda: encode_entry(entry, {o + 1: []}), "unknown frame", "no frame at layout offsets")
    derived = bytearray(entry)
    at = fcimage.Image(entry).data_start + 5
    derived[at] = 1
    refused(lambda: encode_entry(bytes(derived), {}), "derived planes", "derived_plane")
    remap = bytearray(fc_entry("FC0000", 0))
    remap[fcimage.Image(bytes(remap)).data_start + 4] = 0
    refused(lambda: encode_entry(bytes(remap), {}), "remapping entry with kind 1-3 cells", "remaps colours")
    w, h = 80, 52
    syn = synthetic_entry(w, h)
    W = w * 8
    pix = [8] * (W * h * 8)
    for i in range(w * h):
        cx, cy = i % w, i // w
        base = cy * 8 * W + cx * 8
        pix[base] = 15
        pix[base + 7 * W + 7] = 12
        for b in range(8):
            pix[base + W + b] = 8 | (i >> b & 1)
            pix[base + 2 * W + b] = 8 | (i >> (8 + b) & 1)
    refused(lambda: encode_entry(syn, {6: pix}), "too many cells", "the game takes 4095")
    small = synthetic_entry(4, 3)
    got = fcimage.Image(encode_entry(small, {6: [(i * 7) % 16 for i in range(32 * 24)]}))
    expect(got.counts[0] > 1 and not any(got.counts[1:]),
           f"opaque cells of an entry with kind-0 words only are kind 0 (counts {got.counts})")


def test_corpus():
    n = cells = old_size = new_size = frameless = 0
    for path in sorted(glob.glob(os.path.join(SRC, "FC*.BIN"))):
        stem = os.path.basename(path)[:-4].upper()
        for k, entry in enumerate(fcimage.entries(open(path, "rb").read())):
            if (stem, k) == ("FC0000", 4):
                continue
            img = fcimage.Image(entry)
            if not unique_frames(img):
                refused(lambda: encode_entry(entry, {}), f"{stem} entry {k} without frames", "no frames")
                frameless += 1
                continue
            new = encode_entry(entry, {})
            out = fcimage.Image(new)
            same = (out.layout == img.layout and out.counts == img.counts
                    and new[2 + len(img.layout):img.data_start] == entry[2 + len(img.layout):img.data_start]
                    and (out.no_remap, out.derived) == (img.no_remap, img.derived)
                    and out.cells == img.cells)
            expect(same, f"{stem} entry {k} unedited: same layout, palettes, flags and dictionaries")
            expect(contiguous(img.layout), f"{stem} entry {k}: the layout is its table and records back to back")
            expect_whatever_came_before(new, f"{stem} entry {k} unedited")
            n += 1
            cells += sum(img.counts)
            old_size += len(entry)
            new_size += len(new)
    print(f"corpus: {n} entries, {cells} cells, {old_size} -> {new_size} bytes; "
          f"{frameless} entries without frames refused")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_cell_codes()
    test_edit()
    test_mixed_edit()
    test_boxes()
    test_refusals()
    if sys.argv[1:] == ["corpus"]:
        test_corpus()
    print("OK" if not FAILS else f"{len(FAILS)} failures")
    sys.exit(1 if FAILS else 0)
