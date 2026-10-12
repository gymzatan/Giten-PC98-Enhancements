#!/usr/bin/env python3
"""Place Windows sprites into PC-98 frames and dither them onto those entries' palettes.

    winfit.py [FC...]     default: FC2820 FC2870 FC28A0

Writes gfx_win/ (Windows colours) and gfx_win_fit/ (the game's own slots, and frames.json: where
each frame sits). Every frame the catalogue (run/win_to_pc98.py) maps is converted: the Windows
version has a picture for each of a demon's frames, and one left out shows up in battle as the
PC-98 picture between Windows ones.

FC2630 (式神, with 護法童子 and 天逆神 in its other colouring) keeps its PC-98 drawing: the Windows
version only reshades it inside the PC-98 outline (frames 0, 3 and 4 pixel for pixel) and repeats
frame 0 for frames 1 and 2, and fitted back into the PC-98 colours it only came out coarser - the
user kept the PC-98 one.

A Windows battle picture is a 256x256 canvas, and every canvas is drawn at one scale: entry 2
takes it 1:1 (the 175 demons whose Windows picture is the PC-98 drawing lie on their canvases
pixel for pixel, the PC-98 anchor on canvas x 128), entries 4 and 6 at the fractions
run/win_to_pc98.ZOOM_SCALE_256 gives. So a demon's frames take their canvases whole, at the
scale of their size, with one canvas point on the entry's anchor for all of them - the point
where the Windows entry-2 pictures lie over the PC-98 ones best, silhouette on silhouette
(`anchor`) - and each pose stands where the Windows animation puts it. A frame's box becomes
the whole cells its picture covers, whatever the PC-98 box was: 跺脚鬼's PC-98 frames are
footprints, and the Windows ghost is drawn standing on them.

A demon drawn in one colouring (FC2870, FC28A0) has its colours fitted here, once for its three
sizes, which are the one drawing and carry one palette: the slots its entries set keep the
screen's colours they hold - black, white, the status frame's red, green and yellow - and the
rest are fitted to all its frames together (fcfit.fit_colours) and put in the order of
brightness the game's palette has them in.

A demon with several colourings (FC2820: ダークネス, フォッグ) is dithered onto the colours
gfx_win_fit/ already holds for it, which the fit of the whole set chose from the Windows
version's per-colouring pictures.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(WORK, "run"))
import fcencode  # noqa: E402
import fcfit  # noqa: E402
import fcimage  # noqa: E402
import gfx  # noqa: E402
import wincells  # noqa: E402
import winsource  # noqa: E402
import wintex  # noqa: E402
import win_to_pc98 as W2P  # noqa: E402

FIT = os.path.join(WORK, "gfx_win_fit")
WIN = os.path.join(WORK, "gfx_win")
SRC = os.path.join(WORK, "files", "DDS98")
DEMONS = ("FC2820", "FC2870", "FC28A0")
HUD_RED, HUD_GREEN, HUD_YELLOW = 0x05F4, 0x0C35, 0x0AD1
RESERVED = {0x0000, 0x0FFF, HUD_RED, HUD_GREEN, HUD_YELLOW}
WHITE = 4
CANVAS = 256


def side(k):
    """The canvas's size in pixels at entry k's size."""
    return int(round(CANVAS * W2P.ZOOM_SCALE_256[k]))


def anchor_at(k, C):
    """Where the anchor falls on the canvas shrunk to entry k's size: one pixel up and left of C times
    the scale, where the PC-98's own entry-4 and entry-6 pictures put it."""
    n = side(k)
    if n == CANVAS:
        return C
    return int(round(C[0] * n / CANVAS)) - 1, int(round(C[1] * n / CANVAS)) - 1


def canvas(cache, j):
    """The job's Windows picture as its keyed 256x256 RGBA canvas."""
    path = j["path"]
    if path not in cache:
        cache[path] = W2P.parse_bmps(open(path, "rb").read())
    rgba, keyed = W2P.sprite_rgba(cache[path][j["bmp_index"]])
    if not keyed or rgba.size != (CANVAS, CANVAS):
        raise SystemExit(f"{os.path.basename(path)} 第 {j['bmp_index']} 张不是透明底的 256×256 战斗画布")
    return rgba


def canvas_at(rgba, k):
    """The canvas at entry k's size, as an RGBA array: shrunk with a box filter and its alpha cut at
    128, as place_sprite shrinks a sprite."""
    n = side(k)
    if n != CANVAS:
        rgba = rgba.resize((n, n), Image.Resampling.BOX)
    a = np.asarray(rgba).copy()
    a[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
    return a


def cut(arr, opaque, a, fill):
    """(x, y, arr cut to the whole cells round its opaque part): x, y where that box sits, in pixels
    from the anchor, which lies at `a` on arr."""
    ys, xs = np.nonzero(opaque)
    x0 = (int(xs.min()) - a[0]) // 8 * 8
    y0 = (int(ys.min()) - a[1]) // 8 * 8
    x1 = -((a[0] - int(xs.max()) - 1) // 8) * 8
    y1 = -((a[1] - int(ys.max()) - 1) // 8) * 8
    out = np.full((y1 - y0, x1 - x0) + arr.shape[2:], fill, arr.dtype)
    sx, sy = a[0] + x0, a[1] + y0
    cx0, cy0 = max(0, sx), max(0, sy)
    cx1, cy1 = min(arr.shape[1], a[0] + x1), min(arr.shape[0], a[1] + y1)
    out[cy0 - sy:cy1 - sy, cx0 - sx:cx1 - sx] = arr[cy0:cy1, cx0:cx1]
    return x0, y0, out


def overlap(a, b):
    """c[dy, dx] = pixels of b on a with b's top-left at (dx, dy) of a, b wholly inside a."""
    sh = (a.shape[0] + b.shape[0], a.shape[1] + b.shape[1])
    c = np.fft.irfft2(np.fft.rfft2(a.astype(float), sh) * np.fft.rfft2(b[::-1, ::-1].astype(float), sh), sh)
    return np.rint(c[b.shape[0] - 1:a.shape[0], b.shape[1] - 1:a.shape[1]]).astype(int)


def anchor(fc, jobs, cache):
    """The canvas point that sits on the entry's anchor, for every picture of fc: where the Windows
    entry-2 pictures lie over the PC-98 ones best, all frames at once, silhouette on silhouette. For a
    drawing the Windows version took over from the PC-98 this is exact; for a redrawing it is where
    the two agree most."""
    img = fcimage.Image(fcimage.entries(open(os.path.join(SRC, fc + ".BIN"), "rb").read())[2])
    R = 2 * CANVAS
    total = np.zeros((CANVAS + 2 * R, CANVAS + 2 * R), int)
    for (f, png), j in sorted(jobs.items()):
        if f != fc or j["entry"] != 2:
            continue
        frame = int(png[3:6])
        W, H, pix = img.indices(frame)
        mine = np.array([c is not None for c in pix]).reshape(H, W)
        theirs = np.asarray(canvas(cache, j))[..., 3] >= 128
        pad = np.zeros((CANVAS + 2 * H, CANVAS + 2 * W), bool)
        pad[H:H + CANVAS, W:W + CANVAS] = theirs
        c = overlap(pad, mine)           # c[dy, dx]: the PC-98 frame's top-left at canvas (dx - W, dy - H)
        x, y, _w, _h = fcencode.frame_box(img, frame)
        ox, oy = R - W - 8 * x, R - H - 8 * y
        total[oy:oy + c.shape[0], ox:ox + c.shape[1]] += c
    cy, cx = np.unravel_index(int(np.argmax(total)), total.shape)
    return int(cx) - R, int(cy) - R


def boxes_of(img, where):
    """{layout offset: (x, y, w, h) in cells} for {frame: (x, y, w, h) in pixels}, as fcencode takes them."""
    offs = fcencode.frame_offsets(img.layout)
    return {offs[f]: (x // 8, y // 8, w // 8, h // 8) for f, (x, y, w, h) in where.items()}


def save_places(fit_dir, where):
    """frames.json: where each frame file's box sits, for gfx.py."""
    json.dump({png: {"x": x, "y": y} for png, (x, y) in sorted(where.items())},
              open(os.path.join(fit_dir, gfx.FRAMES_NAME), "w", encoding="utf-8"), indent=1)


def slots_of(path):
    """Indices the existing fit picture already uses, plus transparent."""
    im = Image.open(path)
    used = {int(v) for v in im.get_flattened_data()}
    used.discard(gfx.TRANSPARENT)
    pal = list(im.getpalette() or [])
    rgb = {i: tuple(pal[i * 3:i * 3 + 3] or (0, 0, 0)) for i in used}
    return rgb, pal


def save_p(path, idx, pal, size):
    im = Image.new("P", size)
    flat = list(pal) + [0] * (768 - len(pal))
    flat[48:51] = [255, 0, 255]
    im.putpalette(flat)
    im.putdata([int(v) for v in idx.reshape(-1)])
    im.save(path, transparency=gfx.TRANSPARENT)


def pal_bytes(words):
    flat = []
    for w in words:
        flat += list(fcimage.pc98_rgb(int(w, 16) if isinstance(w, str) else w))
    flat += [255, 0, 255]
    return flat + [0] * (768 - len(flat))


def placements(fc, jobs, C, cache):
    """[(png, job, (x, y), placed RGBA picture)] for every frame of fc the catalogue maps: its canvas at
    the scale of its entry's size with C on the anchor, cut to the cells it covers, (x, y) where that
    box sits. Each is written to gfx_win/ as well."""
    win_dir = os.path.join(WIN, fc)
    os.makedirs(win_dir, exist_ok=True)
    out = []
    for (f, png), j in sorted(jobs.items()):
        if f != fc:
            continue
        a = canvas_at(canvas(cache, j), j["entry"])
        x, y, pic = cut(a, a[..., 3] > 0, anchor_at(j["entry"], C), 0)
        placed = Image.fromarray(pic)
        W2P.save_indexed(os.path.join(win_dir, png), placed)
        out.append((png, j, (x, y), placed))
    return out


def rebuild_single(fc, jobs):
    """A demon in one colouring: its colours fitted to all its frames, and every frame dithered."""
    fit_dir = os.path.join(FIT, fc)
    entries = fcimage.entries(open(os.path.join(SRC, fc + ".BIN"), "rb").read())
    cache = {}
    frames = placements(fc, jobs, anchor(fc, jobs, cache), cache)
    imgs = {k: fcimage.Image(entries[k]) for k in sorted({j["entry"] for _png, j, _xy, _p in frames})}
    first = imgs[min(imgs)]
    base, own = first.palettes[0], fcfit.owned(first)
    for k, img in imgs.items():
        if img.palettes[0] != base or fcfit.owned(img) != own:
            raise SystemExit(f"{fc} 条目 {k} 的调色板和条目 {min(imgs)} 不同，不能按一套颜色拟合")
    keep = [i for i in own if base[i] in RESERVED or i == WHITE]
    pick = [i for i in own if i not in keep]
    rgb = {png: np.asarray(p.convert("RGB"), np.float32) for png, _j, _xy, p in frames}
    mask = {png: np.asarray(p.split()[-1]) >= 128 for png, _j, _xy, p in frames}
    samples = np.vstack([rgb[png][mask[png]] for png, _j, _xy, _p in frames])
    centres = fcfit.fit_colours(samples, [wintex.rgb_of(base[i]) for i in keep], len(pick))
    words = list(base)
    dark_first = sorted(pick, key=lambda i: float(wintex.rgb_of(base[i]) @ wintex.LUMA))
    for slot, colour in zip(dark_first, sorted(centres, key=lambda c: float(c @ wintex.LUMA))):
        words[slot] = wintex.word(colour)
    colours = {i: wintex.rgb_of(words[i]) for i in own}

    index, where = {}, {}
    for png, _j, xy, p in frames:
        index[png] = wincells.ordered(rgb[png], mask[png], colours, xy, 1.0)
        where[png] = xy + p.size
    for k, img in imgs.items():
        mine = {int(png[3:6]): idx for png, idx in index.items() if int(png[:2]) == k}
        boxes = boxes_of(img, {int(png[3:6]): box for png, box in where.items() if int(png[:2]) == k})
        counts, size = fcencode.cell_cost(entries[k], fcfit.edits_of(img, mine), boxes)
        if not fcfit.fits(counts, size):
            raise SystemExit(f"{fc} 条目 {k}：{counts} 个 cell、解码 {size} 字节，超出游戏的上限"
                             f"（每种 {fcfit.CELL_LIMIT} 个、{fcfit.MEMORY_CAP} 字节）")
    for old in os.listdir(fit_dir) if os.path.isdir(fit_dir) else []:
        if old.endswith(".png") and old not in index:
            os.remove(os.path.join(fit_dir, old))
    os.makedirs(fit_dir, exist_ok=True)
    flat = pal_bytes(words)
    for png, _j, _xy, p in frames:
        save_p(os.path.join(fit_dir, png), index[png], flat, p.size)
    save_places(fit_dir, {png: box[:2] for png, box in where.items()})
    json.dump({str(k): [[f"{w:04X}" for w in words]] for k in imgs},
              open(os.path.join(fit_dir, "palettes.json"), "w", encoding="utf-8"), indent=1)
    print("  " + " ".join(f"{i}:{words[i]:04X}" for i in own))
    return len(frames)


def rebuild_dither(fc, jobs):
    """A demon in several colourings: every frame dithered onto the colours gfx_win_fit/ holds for it."""
    fit_dir = os.path.join(FIT, fc)
    cache = {}
    where = {}
    for png, _j, xy, placed in placements(fc, jobs, anchor(fc, jobs, cache), cache):
        dest = os.path.join(fit_dir, png)
        if not os.path.exists(dest):
            raise SystemExit(f"{fc} {png}：gfx_win_fit 里没有这一帧，不知道它按哪几种颜色画")
        slots, pal = slots_of(dest)
        rgb = np.asarray(placed.convert("RGB"), np.float32)
        mask = np.asarray(placed.split()[-1]) >= 128
        if len(slots) == 1:
            only = next(iter(slots))
            idx = np.full(mask.shape, gfx.TRANSPARENT, np.uint8)
            idx[mask] = only
        else:
            idx = wincells.ordered(rgb, mask, slots, xy, 1.0)
        save_p(dest, idx, pal, placed.size)
        where[png] = xy
    save_places(fit_dir, where)
    return len(where)


def colourings(fc, jobs):
    """How many palette variants the entries of fc the catalogue maps carry."""
    entries = fcimage.entries(open(os.path.join(SRC, fc + ".BIN"), "rb").read())
    return max(len(fcimage.Image(entries[j["entry"]]).palettes) for (f, _png), j in jobs.items() if f == fc)


def rebuild(fc, jobs):
    if colourings(fc, jobs) == 1:
        return rebuild_single(fc, jobs)
    return rebuild_dither(fc, jobs)


def main(names=None):
    names = list(names) or list(DEMONS)
    unknown = [fc for fc in names if fc not in DEMONS]
    if unknown:
        raise SystemExit(f"{'、'.join(unknown)} 不在转换的恶魔里（{' '.join(DEMONS)}）")
    jobs = winsource.jobs(W2P.Catalog())
    for fc in names:
        n = rebuild(fc, jobs)
        print(f"{fc}: {n} frames")


if __name__ == "__main__":
    main(sys.argv[1:])
