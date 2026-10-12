#!/usr/bin/env python3
"""The frame around the screen in the Windows remake's grey metal, instead of the PC-98's gold.

    winhud.py [OUT]        default: winhud/, the shape tools/mkwinpatch.py takes as a source folder

The frame is FC0000 entry 0: ten pieces that ring the whole 640x400 screen, drawn in five colour
slots - 0 black for the panels text is written over, 4 white for the hairlines, and red, green and
yellow that together read as gold. Only 0 and 4 can be given another colour and kept: every picture
in the game writes black into 0 and white into 4 (563 of 564 demon portraits do, and 540 of them),
while 5, 6 and 7 are the red, green and yellow of the bars and the status line, which hundreds of
pictures put back the moment they load. So the metal is made of black and white alone.

Two things decide what it looks like:

  flatten   the art shades a surface by checkering black into its colour, and those dots survive any
            recolouring as speckle - the trough under the compass is the worst of it. A black pixel
            with no black above, below, left or right is such a shading dot and is folded back into
            the colour around it; an outline or a panel keeps its black, since those do have black
            beside them.
  PATTERN   each remaining colour is then drawn as a regular pattern of white on black, laid out on
            the screen's own grid so neighbouring pieces line up: the field a quarter white, the
            trough and the mouldings a checkerboard, the panels black, the hairlines white. Same grey
            as a dithering of it, without the scattered dots - black is the continuous ground.

The compass plate in the middle of the lower bar is the same gold and goes with it: FC0000 entry 2
frame 111 is the plate on its own, FC0110 entry 9 frames 0-3 the plate with the needle's N, S, E and
W. Its plate takes the same patterns, so the seam with the bar stays invisible; the dial keeps what
it holds, since the white face and the red letter on it are the reading, not the chrome; and its
outer ring is the circle the art draws, with nothing added beside it, because the circle is symmetric
and a pattern is not.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fcencode  # noqa: E402
import fcfit  # noqa: E402
import fcimage  # noqa: E402
import gfx  # noqa: E402

SLOTS = (0, 4)                 # black and white: the two the whole game agrees on
PATTERN = {0: "black",         # the panels behind the text
           4: "white",         # the hairlines
           5: "quarter",       # the thin outlines between panel and field
           6: "quarter",       # the metal field
           7: "half"}          # the trough under the view, and the mouldings
# (file, entry, the frames to convert or None for all, whether it is the compass plate)
PARTS = (("FC0000", 0, None, False),
         ("FC0000", 2, [111], True),
         ("FC0110", 9, [0, 1, 2, 3], True))


def entry_of(stem, k):
    path = os.path.join(WORK, "files", "DDS98", stem + ".BIN")
    return fcimage.entries(open(path, "rb").read())[k]


def indices(img, f):
    w, h, pix = img.indices(f)
    return np.array([fcfit.TRANSPARENT if c is None else c for c in pix], np.uint8).reshape(h, w)


def pattern(name, x0, y0, shape):
    """Where the pattern is white, over a piece whose top left corner is at (x0, y0) on screen."""
    yy, xx = np.mgrid[y0:y0 + shape[0], x0:x0 + shape[1]]
    if name == "white":
        return np.ones(shape, bool)
    if name == "black":
        return np.zeros(shape, bool)
    if name == "half":                       # a checkerboard: half white
        return (xx + yy) % 2 == 0
    if name == "quarter":                    # one white in each 2x2
        return (xx % 2 == 0) & (yy % 2 == 0)
    if name == "eighth":
        return (xx % 4 == 0) & (yy % 2 == 0)
    raise ValueError(name)


def grown(mask):
    """The mask and everything touching it, corners included."""
    out = mask.copy()
    out[1:] |= mask[:-1]
    out[:-1] |= mask[1:]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    out[1:, 1:] |= mask[:-1, :-1]
    out[:-1, :-1] |= mask[1:, 1:]
    out[1:, :-1] |= mask[:-1, 1:]
    out[:-1, 1:] |= mask[1:, :-1]
    return out


def beside(mask):
    """The mask grown by one pixel up, down, left and right - corners left out."""
    out = np.zeros_like(mask)
    out[1:] |= mask[:-1]
    out[:-1] |= mask[1:]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def flatten(was):
    """The art's own shading dots folded into the surface they shade."""
    black = was == 0
    lone = black & ~beside(black)
    if not lone.any():
        return was
    best = np.zeros(was.shape, np.uint8)
    top = np.zeros(was.shape, np.int8)
    for slot in (4, 5, 6, 7):
        count = np.zeros(was.shape, np.int8)
        is_it = (was == slot).astype(np.int8)
        count[1:] += is_it[:-1]
        count[:-1] += is_it[1:]
        count[:, 1:] += is_it[:, :-1]
        count[:, :-1] += is_it[:, 1:]
        take = count > top
        best[take] = slot
        top[take] = count[take]
    out = was.copy()
    keep = lone & (top > 0)
    out[keep] = best[keep]
    return out


def outside(free):
    """The pixels of `free` a walk in from the border reaches - so what it misses is enclosed."""
    seen = np.zeros_like(free)
    seen[0], seen[-1], seen[:, 0], seen[:, -1] = free[0], free[-1], free[:, 0], free[:, -1]
    while True:
        more = seen.copy()
        more[1:] |= seen[:-1] & free[1:]
        more[:-1] |= seen[1:] & free[:-1]
        more[:, 1:] |= seen[:, :-1] & free[:, 1:]
        more[:, :-1] |= seen[:, 1:] & free[:, :-1]
        if np.array_equal(more, seen):
            return seen
        seen = more


def compass(a):
    """The dial: its black ring and everything the ring encloses."""
    ring = a == 0
    return ring | ~outside(~ring)


def connected(seed, allowed):
    """The part of `allowed` a walk from `seed` reaches, corners included."""
    got = seed & allowed
    while True:
        more = grown(got) & allowed
        if np.array_equal(more, got):
            return got
        got = more


def inner_ring(was):
    """The black ring against the face - or the dark middle, on the frame with the needle off."""
    black = compass(was) & (was == 0)
    face = disc(was)
    if face.any():
        return connected(grown(face) & black, black)
    middle = np.zeros(was.shape, bool)
    middle[was.shape[0] // 2 - 1:was.shape[0] // 2 + 1,
           was.shape[1] // 2 - 1:was.shape[1] // 2 + 1] = True
    return connected(middle & black, black)


def disc(a):
    """The compass face: its white, and the red inside it - the letter."""
    white = a == 4
    if not white.any():
        return white
    cy, cx = (a.shape[0] - 1) / 2, (a.shape[1] - 1) / 2
    ys, xs = np.nonzero(white)
    far = ((ys - cy) ** 2 + (xs - cx) ** 2).max()
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    return white | ((a == 5) & ((yy - cy) ** 2 + (xx - cx) ** 2 <= far))


def even_outer(was, now):
    """The dial's outer ring: the circle the art draws in black, and nothing beside it.

    The art's circle is already the same in all four quadrants; a pattern laid over the chrome is
    not, so black that lands against the circle would thicken it in some quadrants only."""
    zone = compass(was) & ~disc(was) & ~grown(inner_ring(was))
    ring = zone & (was == 0)
    ring |= ring[:, ::-1] | ring[::-1] | ring[::-1, ::-1]
    out = now.copy()
    out[zone] = np.where(ring[zone], 0, now[zone])
    out[zone & ~ring & grown(ring) & (out == 0)] = 4
    return out


def painted(img, f, is_plate):
    """One frame: shading flattened, each colour drawn as its pattern, the dial kept."""
    was = indices(img, f)
    flat = flatten(was)
    x0, y0 = fcfit.frame_origin(img, f)
    out = np.full(was.shape, fcfit.TRANSPARENT, np.uint8)
    for slot in sorted({int(v) for v in np.unique(flat)} - {fcfit.TRANSPARENT}):
        where = flat == slot
        white = pattern(PATTERN.get(slot, "black"), x0, y0, was.shape)
        out[where] = np.where(white[where], 4, 0)
    if is_plate:
        out = even_outer(was, np.where(disc(was), was, out))
    return out


def frames_of(stem, k, frames, is_plate):
    """{frame: index array} for the frames of one entry that carry their own picture."""
    img = fcimage.Image(entry_of(stem, k))
    want = range(len(img.frames)) if frames is None else frames
    first = fcencode.unique_frames(img)
    offs = fcencode.frame_offsets(img.layout)
    return {f: painted(img, f, is_plate) for f in want if first[offs[f]] == f}, img


def build(out=None):
    """Write the converted frames where the patch takes its pictures from."""
    out = out or os.path.join(WORK, "winhud")
    for stem, k, frames, is_plate in PARTS:
        index, img = frames_of(stem, k, frames, is_plate)
        allowed = set(SLOTS) | ({5} if is_plate else set())
        drew = {int(v) for a in index.values() for v in np.unique(a)} - {fcfit.TRANSPARENT}
        if not drew <= allowed:
            raise SystemExit(f"{stem} 条目 {k} 画到了 {sorted(drew - allowed)}，"
                             "这些槽同屏别的画面会重填")
        folder = os.path.join(out, stem)
        os.makedirs(folder, exist_ok=True)
        for f, a in sorted(index.items()):
            im = Image.new("P", (a.shape[1], a.shape[0]))
            im.putpalette(gfx.palette_rgb(gfx.entry_palette(img)))
            im.putdata(a.reshape(-1).tolist())
            im.save(os.path.join(folder, f"{k:02d}_{f:03d}.png"), transparency=fcfit.TRANSPARENT)
        counts, size = fcencode.cell_cost(entry_of(stem, k), fcfit.edits_of(img, index))
        white = sum(int((a == 4).sum()) for a in index.values())
        drawn = sum(int((a != fcfit.TRANSPARENT).sum()) for a in index.values())
        print(f"{folder}：条目 {k} 的 {len(index)} 帧，cell {sum(counts.values())}"
              f"（上限 {fcfit.CELL_LIMIT}），解码 {size} 字节（上限 {fcfit.MEMORY_CAP}）；"
              f"白占 {white / drawn:.0%}，调色板没动")
    return out


if __name__ == "__main__":
    build(*sys.argv[1:])
