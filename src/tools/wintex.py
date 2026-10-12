#!/usr/bin/env python3
"""The Windows version's dungeon textures, re-projected into the PC-98 wall pieces. Run from work/.

    wintex.py [OUT]        default: wingfx/

The PC-98 game has no textures: every wall set FC10s0.BIN (s = 0-7, A) holds pre-projected pieces of
the left half of the 3D view, and the Windows version replaced them with one 256x256 texture per set
and colour variant, 2x2 tiles of 128 (upper left ceiling, upper right wall, lower left door, lower
right floor). The Windows exe (dds.exe) names them in a table of four slots per set, one per variant;
a missing variant repeats a set's first texture. This takes each texture and draws it into the PC-98
pieces of the same set, keeping every piece's own outline, and fits that set's colours to it.

What the PC-98 engine does, and this relies on:

  pieces    entry 0, frame lateral*20 + depth*4 + face (1603:3AF74): face 2 is the wall ahead,
            face 3 the wall on the left; the right half of the view is the same frame drawn
            mirrored (flag 8000h, 1603:3B06C), the wall straight ahead is drawn twice (3B193,
            3B1B3). Entry 4 is the ceiling, entry 5 the floor, both at fixed places (3AF0C).
  colours   the set is loaded with the map section's variant (header +23h, main:3B484):
            entry 0 with kind 1, which writes its palette's colours 0-3 to the screen
            (0871:8F16); entries 4 and 5, the doors FC1400 and the stairs FC1300 with kind 2,
            which write nothing and draw in whatever colours 1-3 the screen holds. Colour 4 is
            the white the status frame FC0000 sets. So a set has black, three colours of its
            own per variant, and white, and every variant shares the pieces' pixels.

How the picture is made:

  geometry  the view is 368x200 at (136, 64), centred on x = 320. Plane d (the wall ahead at
            depth d) has half width w_d, read off the pieces; a wall's top and bottom are
            straight lines in w, fitted to every unclipped column of the pieces. The left
            wall of cell (lateral l, depth d) runs from plane d-1 to plane d at
            x = 320 - (2l+1) w; the wall ahead spans 320 - (2l+1) w_d .. 320 - (2l-1) w_d.
            Along a side wall the texture follows 1/w, so it is perspective-correct; floor
            and ceiling repeat the tile once per cell. Each pixel averages 4x4 samples.
  colours   black and white are fixed; three colours are found by k-means over what the
            set's variant-0 texture puts on screen, snapped to the 4-bit levels, ordered
            light to dark (the doors and stairs of several sets share pixels, so the order
            must be the same everywhere), and Floyd-Steinberg dithered into each piece. Every
            variant then gets, per colour, the mean its own texture has over the pixels the
            dithering gave that colour - the variants are recolours of one design. What is
            drawn is that dither with the light taken out of the error diffusion: a pixel
            whose two nearest colours include colour 1 or white takes its nearest, or, in a
            broad light area, the lighter one in an ordered pattern that thins out as the
            pixel darkens (see dither).

Output, one folder per FC file as text/gfx expects: <entry>_<frame>.png for every picture of
entries 0, 4 and 5, and palettes.json with entry 0's palettes (tools/gfx.py applies it). The PNGs of
entries 4 and 5 keep their entries' stored palettes, which the game never shows; _preview/ has the
views as the game would draw them, original beside re-projected.
"""
import json
import os
import sys

import numpy as np
from PIL import Image as PILImage, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fcimage  # noqa: E402

SRC = os.path.join(WORK, "files", "DDS98")
WIN = os.path.join(WORK, "inputs", "ddswin")
SETS = (0, 1, 2, 3, 4, 5, 6, 7, 10)
VIEW_X, VIEW_Y, VIEW_W, VIEW_H = 136, 64, 368, 200
CX = 320
TRANSPARENT = 16
BLACK, WHITE = 0, 4
OWN = (1, 2, 3)
LUMA = np.array([0.299, 0.587, 0.114])
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32
BROAD = 2                               # a broad light area holds a (2*BROAD+1)-pixel square
SS = 4                                  # samples per pixel along each axis
TILE = {"ceiling": (0, 0), "wall": (1, 0), "door": (0, 1), "floor": (1, 1)}   # (column, row) of 2x2


class WintexError(ValueError):
    pass


def texture_table():
    """{(set, variant): bmp name} from dds.exe's table of four 16-byte slots per set."""
    exe = open(os.path.join(WIN, "dds.exe"), "rb").read()
    at = exe.find(b"w\\wall00_0.bmp\0")
    if at < 0 or exe.find(b"w\\wall00_0.bmp\0", at + 1) >= 0:
        raise WintexError("dds.exe: the texture table is not where it should be")
    out = {}
    for s in SETS:
        for v in range(4):
            raw = exe[at + 16 * (s * 4 + v):at + 16 * (s * 4 + v) + 16].split(b"\0")[0].decode("ascii")
            if not raw.startswith("w\\wall") or not raw.endswith(".bmp"):
                raise WintexError(f"dds.exe: slot {s}/{v} holds {raw!r}")
            out[(s, v)] = raw[2:]
    return out


def tile(bmp, name):
    im = np.asarray(PILImage.open(os.path.join(WIN, "w", bmp)).convert("RGB"), np.float64)
    if im.shape[:2] != (256, 256):
        raise WintexError(f"{bmp}: {im.shape[1]}x{im.shape[0]}, a 256x256 texture expected")
    c, r = TILE[name]
    return im[r * 128:(r + 1) * 128, c * 128:(c + 1) * 128]


def bilinear(t, u, v):
    """Bilinear, wrapping; u across, v down, both in tile units."""
    h, w = t.shape[:2]
    fx, fy = np.mod(u, 1.0) * w - 0.5, np.mod(v, 1.0) * h - 0.5
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    ax, ay = (fx - x0)[:, None], (fy - y0)[:, None]
    x0, y0 = x0 % w, y0 % h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    return (t[y0, x0] * (1 - ax) * (1 - ay) + t[y0, x1] * ax * (1 - ay)
            + t[y1, x0] * (1 - ax) * ay + t[y1, x1] * ax * ay)


def pyramid(t):
    """The tile and its halvings, each texel the mean of four (the tile repeats, so 128 halves cleanly)."""
    levels = [t]
    while levels[-1].shape[0] > 1:
        a = levels[-1]
        levels.append((a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) / 4)
    return levels


def sample(levels, u, v, footprint):
    """Trilinear: footprint is how many texels of the full tile one sample spans."""
    lod = np.clip(np.log2(np.maximum(footprint, 1.0)), 0, len(levels) - 1)
    lo = np.floor(lod).astype(int)
    hi = np.minimum(lo + 1, len(levels) - 1)
    frac = (lod - lo)[:, None]
    out = np.zeros((len(u), 3))
    for k in np.unique(np.concatenate([lo, hi])):
        near = bilinear(levels[k], u, v)
        wlo = np.where(lo == k, 1 - frac[:, 0], 0.0)[:, None]
        whi = np.where((hi == k) & (hi != lo), frac[:, 0], 0.0)[:, None]
        out += near * (wlo + whi)
    return out


class Piece:
    def __init__(self, img, entry, frame):
        x, y, w, h, _words = img.frames[frame]
        self.entry, self.frame = entry, frame
        self.x = (x - 0x10000 if x & 0x8000 else x) * 8
        self.y = (y - 0x10000 if y & 0x8000 else y) * 8
        W, H, pix = img.indices(frame)
        self.W, self.H = W, H
        self.index = np.array([TRANSPARENT if p is None else p for p in pix], np.uint8).reshape(H, W)
        self.mask = self.index != TRANSPARENT
        self.lateral, rest = divmod(frame, 20)
        self.depth, self.face = divmod(rest, 4)


def owners(img):
    """Frames that own their picture (the others point at the same layout data)."""
    from fcencode import frame_offsets
    offs = frame_offsets(img.layout) if len(img.layout) >= 4 else []
    seen, out = set(), []
    for f, o in enumerate(offs):
        if o not in seen:
            seen.add(o)
            out.append(f)
    return out


def fit_set(pieces):
    """({depth: half width of plane depth}, top line, bottom line) read off one set's entry-0 pieces.

    The far edge of the left wall at depth d is plane d; a wall's top and bottom, column by column
    where the view does not clip them, are straight lines in w = 320 - x."""
    side = [p for p in pieces if p.face == 3 and p.lateral == 0]
    w = {}
    for p in side:
        cols = np.nonzero(p.mask.any(axis=0))[0]
        w[p.depth] = CX - (p.x + cols.max() + 1)
    tops, bottoms = [], []
    for p in side:
        for c in range(p.W):
            rows = np.nonzero(p.mask[:, c])[0]
            if not len(rows):
                continue
            x = CX - (p.x + c + 0.5)
            top, bottom = p.y + rows[0], p.y + rows[-1] + 1
            if top > VIEW_Y:
                tops.append((x, top))
            if bottom < VIEW_Y + VIEW_H:
                bottoms.append((x, bottom))
    return w, np.polyfit(*zip(*tops), 1), np.polyfit(*zip(*bottoms), 1)


class Geometry:
    """The view's planes and wall edges, one for every set: the engine projects them all alike, so
    each number is the median over the sets, which no single set's drawing detail can pull aside."""

    def __init__(self, fits):
        depths = sorted(set.intersection(*(set(w) for w, _t, _b in fits)))
        if depths != list(range(depths[0], depths[-1] + 1)) or len(depths) < 3:
            raise WintexError(f"planes {depths}: not enough of the view to fit")
        self.w = {d: float(np.median([w[d] for w, _t, _b in fits])) for d in depths}
        self.top = np.median([t for _w, t, _b in fits], axis=0)          # top = a*w + b, a < 0
        self.bottom = np.median([b for _w, _t, b in fits], axis=0)       # bottom = a*w + b, a > 0
        if not (self.top[0] < 0 < self.bottom[0]):
            raise WintexError(f"wall edges top {self.top}, bottom {self.bottom}: not a view")
        inv = {d: 1.0 / self.w[d] for d in depths}
        lo, hi = depths[0], depths[-1]
        for d in range(lo - 1, -2, -1):        # the planes behind the view and beyond the last
            inv[d] = 2 * inv[d + 1] - inv[d + 2]
        for d in range(hi + 1, hi + 3):
            inv[d] = 2 * inv[d - 1] - inv[d - 2]
        self.inv = inv

    def edges(self, w):
        return np.polyval(self.top, w), np.polyval(self.bottom, w)

    def cell_depth(self, inv):
        """Continuous depth coordinate from 1/w, plane d at d; linear beyond the outermost planes."""
        ds = sorted(self.inv)
        xs = np.array([self.inv[d] for d in ds])
        out = np.interp(inv, xs, ds)
        lo = inv < xs[0]
        out[lo] = ds[0] + (inv[lo] - xs[0]) / (xs[1] - xs[0]) * (ds[1] - ds[0])
        hi = inv > xs[-1]
        out[hi] = ds[-1] + (inv[hi] - xs[-1]) / (xs[-1] - xs[-2]) * (ds[-1] - ds[-2])
        return out


def uv_wall(p, g, xs, ys):
    l, d = p.lateral, p.depth
    if p.face == 2:
        w = np.full_like(xs, g.w[d])
        u = (xs - (CX - (2 * l + 1) * g.w[d])) / (2 * g.w[d])
    else:
        w = (CX - xs) / (2 * l + 1)
        u = (1.0 / w - g.inv[d - 1]) / (g.inv[d] - g.inv[d - 1])
    top, bottom = g.edges(w)
    return u, (ys - top) / (bottom - top)


def uv_flat(g, xs, ys, ceiling):
    a, b = g.top if ceiling else g.bottom
    w = np.maximum((ys - b) / a, 1e-3)
    return (xs - CX) / (2 * w) + 0.5, g.cell_depth(1.0 / w)


def render(p, g, levels, kind):
    """RGB (H, W, 3) of a piece, averaged over SS x SS samples, each filtered to the texels it covers;
    NaN where the piece is transparent."""
    ys, xs = np.nonzero(p.mask)
    off = (np.arange(SS) + 0.5) / SS
    ox, oy = np.meshgrid(off, off)
    sx = (p.x + xs[:, None] + ox.ravel()[None, :]).ravel()
    sy = (p.y + ys[:, None] + oy.ravel()[None, :]).ravel()

    def uv(x, y):
        return uv_wall(p, g, x, y) if kind == "wall" else uv_flat(g, x, y, kind == "ceiling")

    u, v = uv(sx, sy)
    ux, vx = uv(sx + 1.0 / SS, sy)
    uy, vy = uv(sx, sy + 1.0 / SS)
    size = levels[0].shape[0]
    footprint = size * np.maximum.reduce([np.abs(ux - u), np.abs(vx - v), np.abs(uy - u), np.abs(vy - v)])
    rgb = sample(levels, u, v, footprint).reshape(len(xs), SS * SS, 3).mean(axis=1)
    out = np.full((p.H, p.W, 3), np.nan)
    out[ys, xs] = rgb
    return out


def snap(rgb):
    return np.clip(np.round(np.asarray(rgb) / 17.0), 0, 15) * 17


def kmeans3(samples, fixed, rounds=30):
    """Three free centres beside the fixed ones, started at luminance terciles."""
    luma = samples @ LUMA
    order = np.argsort(luma)
    centres = np.array([samples[order[int(len(order) * q)]] for q in (5 / 6, 3 / 6, 1 / 6)])
    for _ in range(rounds):
        allc = np.vstack([fixed, centres])
        near = np.argmin(((samples[:, None, :] - allc[None]) ** 2).sum(-1), axis=1) - len(fixed)
        new = np.array([samples[near == k].mean(axis=0) if (near == k).any() else centres[k]
                        for k in range(3)])
        if np.allclose(new, centres):
            break
        centres = new
    return centres


def opening(mask, r):
    """The pixels of `mask` covered by some (2r+1)-pixel square lying wholly inside it."""
    H, W = mask.shape
    offs = [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)]
    pad = np.pad(mask, r)
    core = np.logical_and.reduce([pad[r + dy:r + dy + H, r + dx:r + dx + W] for dy, dx in offs])
    pad = np.pad(core, r)
    return mask & np.logical_or.reduce([pad[r + dy:r + dy + H, r + dx:r + dx + W] for dy, dx in offs])


def dither(rgb, mask, palette, origin):
    """Floyd-Steinberg, serpentine, error kept inside the mask. palette: {index: rgb}; origin: the
    picture's place on screen. Returns (dithered, shown), both index arrays.

    A pixel chooses only between the two colours nearest its own, so carried error can shade it
    between them but never throws in a colour from the far side of the palette - no white sparks
    in a brown wall. `shown` differs where one of those two colours is colour 1 or white: light is
    kept out of the error diffusion, which scatters specks of it over darker surfaces and frays
    the edges of light lines. Such a pixel takes its nearest colour - a light line stays solid -
    unless it lies in a broad light area, one holding a (2*BROAD+1)-pixel square of pixels whose
    nearest is colour 1 or white. There it takes the lighter of its two colours where it lies past
    the mid-point toward it by more than a 4x4 ordered threshold of the remaining half, so the area
    fades out in even steps as it darkens. The error travels on as dithered, so every pixel outside
    the light range keeps the plain dither's colour."""
    idx = np.full(mask.shape, TRANSPARENT, np.uint8)
    keys = np.array(list(palette))
    cols = np.array([palette[k] for k in keys], np.float64)
    own = np.where(mask[..., None], rgb, 0.0)
    work = own.copy()
    H, W = mask.shape
    for y in range(H):
        xs = range(W) if y % 2 == 0 else range(W - 1, -1, -1)
        step = 1 if y % 2 == 0 else -1
        for x in xs:
            if not mask[y, x]:
                continue
            c = work[y, x]
            pair = np.argsort(((cols - own[y, x]) ** 2).sum(1))[:2]
            k = int(pair[np.argmin(((cols[pair] - c) ** 2).sum(1))])
            idx[y, x] = keys[k]
            err = c - cols[k]
            for dx, dy, wt in ((step, 0, 7), (-step, 1, 3), (0, 1, 5), (step, 1, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and ny < H and mask[ny, nx]:
                    work[ny, nx] += err * wt / 16

    ys, xs = np.nonzero(mask)
    c = own[ys, xs]
    order = np.argsort(((c[:, None, :] - cols[None]) ** 2).sum(-1), axis=1)
    first, second = order[:, 0], order[:, 1]
    light = np.isin(keys, (OWN[0], WHITE))
    lit = light[first] | light[second]
    nearest_light = np.zeros(mask.shape, bool)
    nearest_light[ys, xs] = light[first]
    broad = opening(nearest_light, BROAD)[ys, xs]
    luma = cols @ LUMA
    lo = np.where(luma[first] <= luma[second], first, second)
    hi = np.where(luma[first] <= luma[second], second, first)
    span = cols[hi] - cols[lo]
    u = np.clip(((c - cols[lo]) * span).sum(1) / np.maximum((span ** 2).sum(1), 1e-9), 0, 1)
    threshold = BAYER[(origin[1] + ys) % 4, (origin[0] + xs) % 4]
    faded = np.where(u > 0.5 + 0.5 * threshold, hi, lo)
    shown = idx.copy()
    shown[ys, xs] = np.where(lit, keys[np.where(broad, faded, first)], idx[ys, xs])
    return idx, shown


def word(rgb):
    r, g, b = (int(round(c / 17)) for c in rgb)
    return (g << 8) | (r << 4) | b


def rgb_of(w):
    return np.array(fcimage.pc98_rgb(w), np.float64)


def load_set(s):
    stem = f"FC{0x1000 | s << 4:04X}"
    entries = fcimage.entries(open(os.path.join(SRC, stem + ".BIN"), "rb").read())
    imgs = {k: fcimage.Image(entries[k]) for k in (0, 4, 5)}
    pieces = {k: [p for p in (Piece(imgs[k], k, f) for f in owners(imgs[k])) if p.mask.any()]
              for k in imgs}
    return stem, imgs, pieces


def build_set(s, table, g, out):
    stem, imgs, pieces = load_set(s)
    variants = len(imgs[0].palettes)
    textures = [table[(s, v)] for v in range(variants)]

    def views(bmp):
        got = {}
        for k, kind in ((0, "wall"), (4, "ceiling"), (5, "floor")):
            levels = pyramid(tile(bmp, kind))
            for p in pieces[k]:
                got[(k, p.frame)] = render(p, g, levels, kind)
        return got

    shown = {bmp: views(bmp) for bmp in sorted(set(textures))}
    ref = shown[textures[0]]
    samples = np.vstack([r[~np.isnan(r[..., 0])] for r in ref.values()])
    fixed = np.array([rgb_of(imgs[0].palettes[0][BLACK]), rgb_of(0x0FFF)])
    centres = snap(kmeans3(samples, fixed))
    order = np.argsort(-(centres @ LUMA))
    centres = centres[order]
    palette = {BLACK: fixed[0], OWN[0]: centres[0], OWN[1]: centres[1], OWN[2]: centres[2], WHITE: fixed[1]}
    dithered, index = {}, {}
    for k in pieces:
        for p in pieces[k]:
            dithered[(k, p.frame)], index[(k, p.frame)] = dither(ref[(k, p.frame)], p.mask, palette, (p.x, p.y))

    palettes = []
    for v in range(variants):
        pal = list(imgs[0].palettes[v])
        view = shown[textures[v]]
        for slot in OWN:
            picked = np.vstack([view[key][dithered[key] == slot] for key in dithered])
            colour = snap(picked.mean(axis=0)) if len(picked) else palette[slot]
            pal[slot] = word(colour)
        palettes.append(pal)

    folder = os.path.join(out, stem)
    os.makedirs(folder, exist_ok=True)
    for k in pieces:
        stored = palettes[0] if k == 0 else imgs[k].palettes[0]
        flat = [c for w in stored for c in fcimage.pc98_rgb(w)] + [255, 0, 255]
        for p in pieces[k]:
            im = PILImage.fromarray(index[(k, p.frame)], "P")
            im.putpalette(flat)
            im.save(os.path.join(folder, f"{k:02d}_{p.frame:03d}.png"), transparency=TRANSPARENT)
    with open(os.path.join(folder, "palettes.json"), "w", encoding="utf-8") as f:
        json.dump({"0": [[f"{w:04X}" for w in pal] for pal in palettes]}, f, indent=1)
    return stem, imgs, pieces, index, palettes, textures


def compose(pieces, index, palette, original, layout):
    """A view as the engine draws it: ceiling and floor, then walls from far to near, the right half
    mirrored. layout "corridor": both side walls at every depth and the wall ahead at the last;
    "room": the walls ahead of every lateral at depth 1, and only the nearest side walls."""
    view = np.zeros((VIEW_H, VIEW_W, 3), np.uint8)
    rgb = np.array([fcimage.pc98_rgb(w) for w in palette] + [(0, 0, 0)], np.uint8)

    def put(p, flip):
        pix = p.index if original else index[(p.entry, p.frame)]
        m = p.mask
        if flip:
            pix, m = pix[:, ::-1], m[:, ::-1]
            x0 = 2 * CX - p.x - p.W
        else:
            x0 = p.x
        for yy in range(p.H):
            for xx in range(p.W):
                if m[yy, xx]:
                    vx, vy = x0 + xx - VIEW_X, p.y + yy - VIEW_Y
                    if 0 <= vx < VIEW_W and 0 <= vy < VIEW_H:
                        view[vy, vx] = rgb[pix[yy, xx]]

    for k in (4, 5):
        for p in pieces[k]:
            put(p, False)
    walls = sorted(pieces[0], key=lambda p: (-p.depth, -p.lateral, -p.face))
    last = max(p.depth for p in walls if p.face == 2 and p.lateral == 0)
    for p in walls:
        if layout == "corridor":
            wanted = (p.face == 3 and p.lateral == 0) or (p.face == 2 and p.lateral == 0 and p.depth == last)
        else:
            wanted = (p.face == 2 and p.depth == 1) or (p.face == 3 and p.lateral == 0 and p.depth == 0)
        if wanted:
            put(p, False)
            put(p, True)
    return view


def main(out=os.path.join(WORK, "wingfx")):
    table = texture_table()
    g = Geometry([fit_set(load_set(s)[2][0]) for s in SETS])
    print("planes " + " ".join(f"{d}:{g.w[d]:g}" for d in sorted(g.w))
          + f"  top {g.top[0]:.3f}w+{g.top[1]:.1f}  bottom {g.bottom[0]:.3f}w+{g.bottom[1]:.1f}")
    prev = os.path.join(out, "_preview")
    os.makedirs(prev, exist_ok=True)
    for s in SETS:
        stem, imgs, pieces, index, palettes, textures = build_set(s, table, g, out)
        rows = []
        for v, pal in enumerate(palettes):
            for layout in ("corridor", "room"):
                a = compose(pieces, index, imgs[0].palettes[v], True, layout)
                b = compose(pieces, index, pal, False, layout)
                rows.append((f"{stem} variant {v} {layout}: PC-98 | {textures[v]}", a, b))
        sheet = PILImage.new("RGB", (VIEW_W * 2 + 24, len(rows) * (VIEW_H + 20)), (40, 40, 48))
        draw = ImageDraw.Draw(sheet)
        for i, (label, a, b) in enumerate(rows):
            y = i * (VIEW_H + 20)
            draw.text((4, y + 3), label, fill=(230, 230, 200))
            sheet.paste(PILImage.fromarray(a), (8, y + 18))
            sheet.paste(PILImage.fromarray(b), (VIEW_W + 16, y + 18))
        sheet.save(os.path.join(prev, f"{stem}.png"))
        print(f"{stem}: {len(palettes)} variants from {', '.join(textures)}; "
              + " | ".join(" ".join(f"{w:04X}" for w in pal[1:4]) for pal in palettes))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
