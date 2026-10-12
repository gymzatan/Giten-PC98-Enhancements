#!/usr/bin/env python3
"""The Windows version's door textures, re-projected into the PC-98 door pieces. Run from work/.

    windoor.py [OUT]        default: windoors/

The doors live in FC1400; the Windows version keeps a door in the lower left quarter of each wall
set's 256x256 texture (wintex.py draws the other three quarters into the walls, ceiling and floor).
PC-98 originally shared five door entries across wall sets. Windows does not: the door is part of
the wall texture. This writes one FC1400 entry per wall set (entry number = set number) and
winpatch remaps every map section's door byte to that set, so each corridor shows its own door.

What the engine does, and this relies on:

  which door  a map section's header names its wall set at +22h and its variant at +23h, then its door
              at +24h and its stairs at +25h (358E:5BA6); 358E:87C2 loads 1400h + the door and 1300h +
              the stairs, both variant 0 with kind 2. Kind 2 writes no palette, so a door draws in
              whatever colours 1-3 the wall set has put on screen. After the remap, +24h equals +22h
              and FC1400 entry s holds wall set s's door. Set 10's texture has no door; its entry
              stays the original black doorway.
  pieces      frame 10 + lateral*10 + depth*2 + face, face 0 the door ahead, 1 the door on the left;
              the right half of the view is the same piece drawn mirrored, so a door ahead is stored
              whole (its handle is not symmetric) and is twice the width of the wall face behind it.
              Frames 0, 2, 4, 6, 8 are the nearest door ahead opening: its leaves slide apart into the
              jambs, and what they uncover is black. Every wall set uses the original entry 0's
              pieces, so the silhouette and the opening are the same.
  colours     black and the set's three, in the set's order of luminance. Each entry is fitted to its
              own set; on screen those are the colours the wall has already put there.

The stairs, FC1300, are one full view per entry of going up (frame 0) and going down (frame 1). They are
drawn from the Windows pictures FC3000 frames 7 and 8 are converted from: the same staircases as the
Windows w/up.bmp and w/dn.bmp, but rendered whole, with the stairwell's own walls and lamps. Their
contrast stretched (STAIR_RANGE), their cells are chosen as FC3000's are (wincells.shared_cells), in what
a dungeon screen holds - black, the set's three colours and the status frame's white, red, green and
yellow, which stay on screen throughout. They are chosen by brightness, the set's colours taken as greys,
the same pixels being shown in every set the entry serves; the lamps and signs are drawn in the status
frame's colours nearest their own, and nothing else is drawn in its red, green or yellow.

Output, one folder per FC file as text/gfx expects: <entry>_<frame>.png for every piece. The PNGs keep
their entries' stored palettes, which the game never shows; _preview/ has the pieces as the game would
draw them, original beside re-projected.
"""
import collections
import glob
import json
import os
import struct
import sys

import numpy as np
from PIL import Image as PILImage, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(WORK, "run"))
import fcimage  # noqa: E402
import wincells  # noqa: E402
import wintex  # noqa: E402
import win_to_pc98 as W2P  # noqa: E402
from ddscrypt import decrypt  # noqa: E402

DOORS = "FC1400"
STAIRS = "FC1300"
# one FC1400 entry per wall set (resource 1400h + set). 8 and 9 pad so set 10 is entry 10.
DOOR_ENTRIES = 11
DOOR_TEMPLATE = 0                       # original circuit door: opening animation and all pieces
DOOR_BLANK = 2                          # original black doorway
DOOR_WALLS = (0, 1, 2, 3, 4, 5, 6, 7)   # Windows textures that hold a door
DOOR_PAD = (8, 9, 10)                   # 10 = subway (wall10 is flat black); 8-9 unused
DITHER = 1.0                            # how far two colours are mixed in an ordered pattern
STAIR_SCENES = ("00_007.png", "00_008.png")  # the FC3000 frames whose pictures frame 0 (going up) and
                                        # frame 1 (going down) are drawn from
SCREEN = {4: 0x0FFF, 5: 0x05F4, 6: 0x0C35, 7: 0x0AD1}  # the status frame's colours, on every dungeon screen
STAIR_RANGE = (5, 95)                   # the percentiles of a staircase's luminance taken to black and to the
                                        # wall set's middle colour: drawn as they are, the steps sit below the
                                        # darkest colour of any set and were barely there
LAMP_CHROMA = 40                        # a staircase pixel whose channels spread this far apart is a lamp or
                                        # a sign; the stairwells are grey to within 15 everywhere else
LAMP_SIZE = 5                           # ... when it lies in a square this wide of such pixels: the few
                                        # tinted specks on the steps lie in none
FIRST = 10                              # frames below this are the opening of the nearest door
ANIMATION = (0, 2, 4, 6, 8)
CLOSED = 10                             # the same door, standing shut
WALLS = os.path.join(WORK, "wingfx_new")   # the converted walls whose colours the doors must share


class DoorError(ValueError):
    pass


def pairings(at=0x24):
    """{entry: {wall set: how many map sections pair them}}, read from the map section headers;
    at 24h the doors, at 25h the stairs."""
    out = collections.defaultdict(collections.Counter)
    for path in sorted(glob.glob(os.path.join(WORK, "files", "DDS98", "M0*.BIN"))):
        _w, p = decrypt(open(path, "rb").read())
        _zero, _na, cnt = struct.unpack_from("<3H", p, 0)
        for o in struct.unpack_from(f"<{cnt}H", p, 6):
            if o + 0x26 > len(p) or p[o + 0x22] == 0xFF:
                continue
            out[p[o + at]][p[o + 0x22]] += 1
    return out


def wall_colours(s):
    """The three colours wall set s puts on screen, brightest first, as the converted walls have them."""
    stem = f"FC{0x1000 | s << 4:04X}"
    path = os.path.join(WALLS, stem, "palettes.json")
    if os.path.exists(path):
        words = [int(w, 16) for w in json.load(open(path, encoding="utf-8"))["0"][0]]
    else:
        entries = fcimage.entries(open(os.path.join(wintex.SRC, stem + ".BIN"), "rb").read())
        words = list(fcimage.Image(entries[0]).palettes[0])
    cols = [np.array(fcimage.pc98_rgb(words[i]), float) for i in (1, 2, 3)]
    order = sorted(range(3), key=lambda i: -(cols[i] @ wintex.LUMA))
    if order != [0, 1, 2]:
        raise DoorError(f"{stem}: colours 1-3 are not in falling luminance")
    return cols


def has_door(bmp):
    """Whether a texture's door quarter holds a door at all: set 10's is flat black, the Windows game
    never showing a door in those corridors."""
    t = wintex.tile(bmp, "door")
    return float(np.percentile(t.reshape(-1, 3) @ wintex.LUMA, 90)) >= 8.0


def door_palette(colours, base):
    """The template door's stored palette with slots 1-3 set to this wall set's colours."""
    pal = list(base)
    pal[wintex.BLACK] = 0x0000
    for i, col in zip(wintex.OWN, colours):
        pal[i] = wintex.word(col)
    return pal


def cell(frame):
    """(lateral, depth, face) of a door piece, face 2 the door ahead and 3 the door on the left, as
    wintex's wall pieces number them."""
    lateral, rest = divmod(frame - FIRST, 10)
    depth, face = divmod(rest, 2)
    return lateral, depth, 2 if face == 0 else 3


def pieces_of(img, k):
    """The pieces of one door entry that draw anything, each carrying the cell it covers."""
    out = []
    for f in wintex.owners(img):
        p = wintex.Piece(img, k, f)
        if p.mask.sum() <= 64:
            continue
        if f in ANIMATION:
            p.lateral, p.depth, p.face = cell(CLOSED)
            p.opening = ANIMATION.index(f)
        else:
            p.lateral, p.depth, p.face = cell(f)
            p.opening = None
        out.append(p)
    return out


def leaf_shift(p, shut):
    """How far each leaf of an opening door has slid, in pixels, by matching what it still draws against
    the door standing shut. The leaves slide outwards into the jambs, so the left one is looked for to
    the right of where it ends up and the right one to the left."""
    dy, dx = p.y - shut.y, p.x - shut.x
    r0, r1 = max(0, -dy), min(p.H, shut.H - dy)
    a = p.index[r0:r1]
    b = shut.index[r0 + dy:r1 + dy]
    body = (a != wintex.TRANSPARENT) & (a != wintex.BLACK)
    mid = p.W // 2
    shifts = []
    for sign, lo, hi in ((1, 0, mid), (-1, mid, p.W)):
        want = body[:, lo:hi]
        if not want.any():
            shifts.append(0)
            continue
        best, score = 0, -1
        for d in range(200):
            sc = np.arange(lo, hi) + dx + sign * d
            ok = (sc >= 0) & (sc < shut.W)
            if not ok.any():
                break
            same = int(((a[:, lo:hi][:, ok] == b[:, sc[ok]]) & want[:, ok]).sum())
            if same > score:
                best, score = d, same
        shifts.append(best)
    return shifts


def door_uv(p, g, xs, ys, shut):
    """Texture coordinates for a door piece. A piece standing shut takes the wall face's own; a leaf of
    an opening door takes them from where that leaf came from, so its pattern slides with it."""
    if p.opening is None or p.opening == 0:
        return wintex.uv_wall(p, g, xs, ys)
    left, right = leaf_shift(p, shut)
    mid = p.x + p.W // 2
    back = np.where(xs < mid, left, -right)
    return wintex.uv_wall(p, g, xs + back, ys)


def quantise(rgb, mask, colours, origin, strength=DITHER):
    """The four colours a door may use - black and the set's three - laid down with an ordered dither on
    the cell grid: a pixel takes the lighter of the two nearest its own where it lies past the mid-point
    between them by more than the pattern's threshold there. Flat areas stay flat, and a gradient the
    four colours cannot hold becomes a mix of the two around it rather than a step."""
    keys = np.array([wintex.BLACK, 1, 2, 3])
    cols = np.array([np.zeros(3)] + list(colours))
    ys, xs = np.nonzero(mask)
    c = rgb[mask]
    d = ((c[:, None, :] - cols[None]) ** 2).sum(-1)
    order = np.argsort(d, axis=1)
    a, b = order[:, 0], order[:, 1]
    span = cols[b] - cols[a]
    u = np.clip(((c - cols[a]) * span).sum(1) / np.maximum((span ** 2).sum(1), 1e-9), 0, 1)
    thr = wintex.BAYER[(origin[1] + ys) % 4, (origin[0] + xs) % 4]
    pick = np.where(u > 0.5 + (thr - 0.5) * strength, b, a)
    out = np.full(mask.shape, wintex.TRANSPARENT, np.uint8)
    out[ys, xs] = keys[pick]
    return out


def stretched(rgba, top):
    """A dark picture's luminance stretched: its STAIR_RANGE low percentile to black and its high one to
    `top`, straight between, and what lies above - the lamps - pressed into top .. 255 so they keep their
    shape. The shadows stay black, where lifting the whole picture by a gamma had greyed them.

    The same amount of light is added to each channel, so a pixel keeps the colour it had rather than
    having its tint multiplied: scaled instead, the stairwell's faint green cast came out as green
    specks all over it, and the green sign as a white block."""
    c = rgba[..., :3].astype(float)
    y = c @ wintex.LUMA
    lo, hi = (float(v) for v in np.percentile(y, STAIR_RANGE))
    below = np.clip(y - lo, 0, None) * (top / max(hi - lo, 1e-6))
    above = top + (y - hi) * ((255.0 - top) / max(255.0 - hi, 1e-6))
    want = np.where(y <= hi, below, above)
    out = rgba.copy()
    out[..., :3] = np.clip(c + (want - y)[..., None], 0, 255).astype(np.uint8)
    return out


def squares(mask, k):
    """How many pixels of `mask` lie in the k x k square centred on each pixel (k odd)."""
    r = k // 2
    s = np.pad(mask.astype(int), r).cumsum(0).cumsum(1)
    s = np.pad(s, ((1, 0), (1, 0)))
    h, w = mask.shape
    return s[k:k + h, k:k + w] - s[:h, k:k + w] - s[k:k + h, :w] + s[:h, :w]


def lamps(rgba):
    """The lamps and signs of a staircase picture: its pixels of LAMP_CHROMA or more that lie in a
    LAMP_SIZE square of such pixels."""
    c = rgba[..., :3].astype(int)
    tinted = (c.max(-1) - c.min(-1)) >= LAMP_CHROMA
    core = squares(tinted, LAMP_SIZE) == LAMP_SIZE * LAMP_SIZE
    return tinted & (squares(core, LAMP_SIZE) > 0)


def by_brightness(rgba, lamp, top):
    """A staircase as its cells are chosen from: stretched and grey, its lamps and signs (`lamp`) in the
    status colours.

    A staircase is shown in the colours of whichever wall set the map section has - entry 0 in seven
    sets - so only its brightness carries over from one to the next, the set colours standing in the same
    order of luminance in every set. Its cells are therefore chosen by brightness, against the set's
    colours as greys (grey_palette); chosen by colour, a grey staircase against a set of saturated
    yellows (set 6) found the status frame's green and red nearer than any yellow and came out as
    coloured noise.

    A lamp or sign pixel takes whichever of the status frame's colours is nearest its own: the body of a
    sign its green, the figure lit on it white. Kept in its own colour it lies between the status colour
    and the set's greys - stretched with the rest, a green sign came out nearer the set's brightest grey
    than the green - and is drawn half in grey."""
    lit = stretched(rgba, top)
    y = np.clip(lit[..., :3].astype(float) @ wintex.LUMA, 0, 255)
    c = rgba[..., :3].astype(float)
    status = np.array([fcimage.pc98_rgb(w) for w in SCREEN.values()], float)
    nearest = status[np.argmin(((c[..., None, :] - status) ** 2).sum(-1), -1)]
    out = lit.copy()
    out[..., :3] = np.where(lamp[..., None], nearest, y[..., None]).astype(np.uint8)
    return out


def grey_palette(colours):
    """What a staircase's cells are chosen in: black, the wall set's three colours as greys of their own
    luminance, and the status frame's colours as they are."""
    palette = {wintex.BLACK: np.zeros(3)}
    for i, col in zip(wintex.OWN, colours):
        palette[i] = np.full(3, float(col @ wintex.LUMA))
    palette.update({i: np.array(fcimage.pc98_rgb(w), float) for i, w in SCREEN.items()})
    return palette


def build_stairs(out):
    """FC1300: a full view of a staircase per wall theme, going up in frame 0 and down in frame 1.

    Each is drawn from the Windows picture of the same staircase that FC3000 frames 7 and 8 are drawn
    from, placed in the frame as the scene conversion places it (wincells.placed), its contrast stretched
    up to the set's middle colour (stretched), with the cells chosen as FC3000's are, by brightness
    (by_brightness). The Windows w/up.bmp and w/dn.bmp are the same staircases cut down to their middle
    128 pixels; drawn from those, the stairwell's walls had to be made up from the corridor's texture and
    the dark picture stretched onto the set's colours, which left the view grainy.

    The colours are those of the wall set the most map sections pair the entry with, the other sets
    showing the same pixels in theirs."""
    pairs = pairings(0x25)
    entries = fcimage.entries(open(os.path.join(wintex.SRC, STAIRS + ".BIN"), "rb").read())
    cat = W2P.Catalog()
    jobs = {j["png"]: j for j in W2P.jobs_for_file(cat.win["fc3000"], W2P.resolve("fc3000", cat), cat)}
    folder = os.path.join(out, STAIRS)
    os.makedirs(folder, exist_ok=True)
    prev = os.path.join(out, "_preview")
    for k in range(len(entries)):
        if k not in pairs:
            print(f"{STAIRS} e{k}: no map section uses it; left as the game has it")
            continue
        s, n = pairs[k].most_common(1)[0]
        colours = wall_colours(s)
        img = fcimage.Image(entries[k])
        flat = [c for w in img.palettes[0] for c in fcimage.pc98_rgb(w)] + [255, 0, 255]
        pieces, frames, masks, origin, lamp_at = {}, {}, {}, {}, {}
        for f, png in enumerate(STAIR_SCENES):
            p = wintex.Piece(img, k, f)
            p.lateral = p.depth = 0
            p.face = 2
            p.opening = None
            j = jobs[png]
            bmps = W2P.parse_bmps(open(j["path"], "rb").read())
            picture = wincells.placed(bmps[j["bmp_index"]], p.W, p.H, png, 0, j.get("mode", "auto"))
            pieces[f], masks[f] = p, p.mask
            rgba = np.asarray(picture.convert("RGBA"))
            lamp_at[f] = lamps(rgba)
            frames[f] = by_brightness(rgba, lamp_at[f], float(colours[1] @ wintex.LUMA))
            origin[f] = (p.x, p.y)
        got, err, in_use = wincells.shared_cells(frames, masks, origin, grey_palette(colours),
                                                 sum(int(m.size) // 64 for m in masks.values()),
                                                 accents=lamp_at)
        rows = []
        for f, p in pieces.items():
            png = PILImage.fromarray(got[f], "P")
            png.putpalette(flat)
            png.save(os.path.join(folder, f"{k:02d}_{f:03d}.png"), transparency=wintex.TRANSPARENT)
            rows.append((p, got[f]))
        print(f"{STAIRS} e{k}: going up and down from FC3000's frames 7 and 8, in the colours of wall set "
              f"{s} ({n} map sections), {in_use} cells, smoothed error {err:.0f}")
        preview(rows, colours, os.path.join(prev, f"{STAIRS}_e{k}.png"), "FC3000 f7 / f8")


def build(out=os.path.join(WORK, "windoors")):
    table = wintex.texture_table()
    g = wintex.Geometry([wintex.fit_set(wintex.load_set(s)[2][0]) for s in wintex.SETS])
    entries = fcimage.entries(open(os.path.join(wintex.SRC, DOORS + ".BIN"), "rb").read())
    img = fcimage.Image(entries[DOOR_TEMPLATE])
    pieces = pieces_of(img, DOOR_TEMPLATE)
    shut = next(p for p in pieces if p.frame == CLOSED)
    folder = os.path.join(out, DOORS)
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(folder):
        if name.endswith(".png"):
            os.remove(os.path.join(folder, name))
    prev = os.path.join(out, "_preview")
    os.makedirs(prev, exist_ok=True)
    for name in os.listdir(prev):
        if name.startswith(f"{DOORS}_"):
            os.remove(os.path.join(prev, name))
    json.dump({"count": DOOR_ENTRIES, "template": DOOR_TEMPLATE,
               "blank": list(DOOR_PAD), "blank_from": DOOR_BLANK},
              open(os.path.join(folder, "extend.json"), "w", encoding="utf-8"), indent=1)
    pals = {}
    for s in DOOR_WALLS:
        bmp = table[(s, 0)]
        if not has_door(bmp):
            raise DoorError(f"wall set {s}: {bmp} has no door in its texture")
        colours = wall_colours(s)
        pal = door_palette(colours, img.palettes[0])
        pals[str(s)] = [[f"{w:04X}" for w in pal]]
        levels = wintex.pyramid(wintex.tile(bmp, "door"))
        flat = [c for w in pal for c in fcimage.pc98_rgb(w)] + [255, 0, 255]
        rows = []
        for p in pieces:
            ys, xs = np.nonzero(p.mask)
            off = (np.arange(wintex.SS) + 0.5) / wintex.SS
            ox, oy = np.meshgrid(off, off)
            sx = (p.x + xs[:, None] + ox.ravel()[None, :]).ravel()
            sy = (p.y + ys[:, None] + oy.ravel()[None, :]).ravel()
            u, v = door_uv(p, g, sx, sy, shut)
            ux, vx = door_uv(p, g, sx + 1.0 / wintex.SS, sy, shut)
            uy, vy = door_uv(p, g, sx, sy + 1.0 / wintex.SS, shut)
            size = levels[0].shape[0]
            foot = size * np.maximum.reduce(
                [np.abs(ux - u), np.abs(vx - v), np.abs(uy - u), np.abs(vy - v)])
            rgb = wintex.sample(levels, u, v, foot).reshape(len(xs), wintex.SS * wintex.SS, 3).mean(axis=1)
            field = np.zeros((p.H, p.W, 3))
            field[ys, xs] = rgb
            index = quantise(field, p.mask, colours, (p.x, p.y))
            if p.opening:
                # what the leaves have uncovered is the dark behind the door, not more door
                index[p.mask & (p.index == wintex.BLACK)] = wintex.BLACK
            png = PILImage.fromarray(index, "P")
            png.putpalette(flat)
            png.save(os.path.join(folder, f"{s:02d}_{p.frame:03d}.png"), transparency=wintex.TRANSPARENT)
            rows.append((p, index))
        print(f"{DOORS} e{s}: {len(pieces)} pieces from {bmp} (wall set {s}), "
              + " ".join(f"{int(round(c[0])):02X}{int(round(c[1])):02X}{int(round(c[2])):02X}"
                         for c in colours))
        preview(rows, colours, os.path.join(prev, f"{DOORS}_e{s}.png"), bmp)
    json.dump({k: pals[k] for k in sorted(pals, key=int)},
              open(os.path.join(folder, "palettes.json"), "w", encoding="utf-8"), indent=1)
    print(f"{DOORS} e8-e10: original black doorway (set 10 has no door; 8-9 unused)")
    build_stairs(out)
    return 0


def preview(rows, colours, path, bmp):
    pal_old = np.array([(0, 0, 0), (210, 210, 210), (150, 150, 150), (95, 95, 95)]
                       + [(255, 255, 255)] * 12 + [(25, 0, 35)], np.uint8)
    pal_new = np.array([(0, 0, 0)] + [c.astype(np.uint8) for c in colours]
                       + [fcimage.pc98_rgb(SCREEN[i]) for i in sorted(SCREEN)]
                       + [(255, 255, 255)] * 8 + [(25, 0, 35)], np.uint8)
    tiles = []
    for p, index in rows:
        pair = []
        for pal, a in ((pal_old, p.index), (pal_new, index)):
            field = np.full((wintex.VIEW_H, wintex.VIEW_W, 3), (25, 0, 35), np.uint8)
            py, px = p.y - wintex.VIEW_Y, p.x - wintex.VIEW_X
            y1, x1 = min(py + p.H, wintex.VIEW_H), min(px + p.W, wintex.VIEW_W)
            field[max(py, 0):y1, max(px, 0):x1] = pal[a[:y1 - py, :x1 - px]]
            pair.append(field)
        tiles.append(np.concatenate(pair, axis=1))
    sheet = PILImage.fromarray(np.concatenate(
        [np.pad(t, ((0, 14), (0, 0), (0, 0))) for t in tiles], axis=0))
    draw = ImageDraw.Draw(sheet)
    for i, (p, _index) in enumerate(rows):
        draw.text((4, i * (wintex.VIEW_H + 14) + wintex.VIEW_H + 2),
                  f"frame {p.frame}: lateral {p.lateral} depth {p.depth} "
                  + ("ahead" if p.face == 2 else "left")
                  + (f", opening {p.opening}" if p.opening is not None else "")
                  + f"   PC-98 | {bmp}", fill=(230, 230, 200))
    sheet.save(path)


if __name__ == "__main__":
    sys.exit(build(*sys.argv[1:]))
