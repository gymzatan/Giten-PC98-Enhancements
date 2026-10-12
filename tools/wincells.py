#!/usr/bin/env python3
"""A Windows picture put into a PC-98 frame, and the 8x8 cells chosen to draw it.

    placed(bmp, w, h, png, entry, mode)     the Windows picture in the frame, full colour, as
                                            run/win_to_pc98.py places it before reducing colours
    ordered(rgb, mask, palette, origin, s)  ordered dithering on the cell grid
    shared_cells(frames, masks, origin, palette, cells)
                                            the cells chosen for pictures together, each place drawn
                                            with the cell that looks most like the picture there

Used by the scene conversion (FC3000 entry 0, whose ten pictures cannot each be dithered inside one
entry's cell dictionary) and by tools/windoor.py for the dungeon staircases (FC1300), which are drawn
from the same Windows pictures of a staircase as FC3000 frames 7 and 8.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(WORK, "run"))
import wintex  # noqa: E402

TRANSPARENT = 16
BAYER8 = (np.array([[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26],
                    [12, 44, 4, 36, 14, 46, 6, 38], [60, 28, 52, 20, 62, 30, 54, 22],
                    [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
                    [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]]) + 0.5) / 64
CANDIDATE_STRENGTHS = (1.0, 0.5, 0.0)   # the ways a cell may be dithered when cells are chosen
# The status frame's red, green and yellow. A cell holding one may only draw a place whose own picture
# has it: measured as colour alone, a grey cell sprinkled with a lamp's green from elsewhere comes nearer
# a teal screen than any grey does, and repeated over the screen the specks became a pattern of arrows
# (FC3000 frame 2).
ACCENTS = {0x05F4, 0x0C35, 0x0AD1}
BLUR = np.array([1, 4, 6, 4, 1], np.float32) / 16


def placed(bmp, tw, th, png, entry, mode):
    """The Windows picture placed in the frame, as RGBA (alpha 0 = transparent), following
    win_to_pc98.convert_one's cases but stopping before its colour reduction. A picture that comes out
    at another size than the frame's is put into it the way win_to_pc98.apply_user_fit puts an
    oversized plate.

    run/win_to_pc98.py is imported here rather than with the module: placing a Windows picture is what
    needs it, and the dithering and cell choosing below - which tools/fcedit.py ships on their own -
    do not."""
    import win_to_pc98 as W2P  # noqa: E402
    im = _placed(bmp, tw, th, png, entry, mode)
    if im.size != (tw, th):
        im = W2P.cover_rgba(W2P.crop_keyed_letterbox(im), tw, th)
    return im


def _placed(bmp, tw, th, png, entry, mode):
    import win_to_pc98 as W2P  # noqa: E402
    if mode == "cg" or W2P.is_fullscreen(bmp):
        plate = W2P.extract_cg_plate(bmp)
        if (tw, th) == (640, 136):
            rgb = plate.convert("RGB")
            if rgb.size[0] >= 600 and rgb.size[1] >= 348:
                rgb = W2P.to_screen_640x400(rgb)
            if rgb.size[0] >= 640 and rgb.size[1] >= 272:
                return rgb.crop((0, 136, 640, 272)).convert("RGBA")
        if tw * th < 640 * 136 and W2P.is_fullscreen(bmp) and (tw, th) != (640, 136):
            return W2P.to_screen_640x400(plate).convert("RGBA")
        if tw >= 600 and th >= 348:
            return W2P.to_screen_640x400(plate).convert("RGBA")
        return W2P.cover_rgba(W2P.crop_keyed_letterbox(plate), tw, th)
    rgba, keyed = W2P.sprite_rgba(bmp)
    if keyed:
        rgba = W2P.crop_alpha(rgba)
        scale = 1.0 if mode == "native" else W2P.zoom_scale(bmp.size, png, entry)
        return W2P.place_sprite(rgba, tw, th, scale if scale is not None else 1.0)
    if W2P.is_picture_dest(tw, th):
        src = W2P.extract_cg_plate(bmp)
        return W2P.cover_rgba(W2P.crop_keyed_letterbox(src), tw, th)
    rgb = bmp.convert("RGB")
    if mode == "native" or rgb.size == (tw, th):
        if rgb.size != (tw, th):
            canvas = Image.new("RGB", (tw, th), (0, 0, 0))
            canvas.paste(rgb, ((tw - rgb.size[0]) // 2, (th - rgb.size[1]) // 2))
            rgb = canvas
        return rgb.convert("RGBA")
    return W2P.contain_rgb(rgb, tw, th).convert("RGBA")


def ordered(rgb, mask, palette, origin, strength):
    """Ordered dithering on the 8x8 grid the cells sit on: a pixel takes the lighter of the two colours
    nearest its own where it lies past the mid-point between them by more than the Bayer threshold of
    that grid place, scaled by `strength` (0 = the nearer colour). Flat areas come out as one repeated
    cell, which is what keeps an entry inside the cell dictionary."""
    keys = np.array(list(palette))
    cols = np.array([palette[i] for i in keys], float)
    ys, xs = np.nonzero(mask)
    c = rgb[mask]
    d = ((c[:, None, :] - cols[None]) ** 2).sum(-1)
    order = np.argsort(d, axis=1)
    a, b = order[:, 0], order[:, 1]
    span = cols[b] - cols[a]
    u = np.clip(((c - cols[a]) * span).sum(1) / np.maximum((span ** 2).sum(1), 1e-9), 0, 1)
    thr = BAYER8[(origin[1] + ys) % 8, (origin[0] + xs) % 8]
    pick = np.where(u > 0.5 + (thr - 0.5) * strength, b, a)
    idx = np.full(mask.shape, TRANSPARENT, np.uint8)
    idx[ys, xs] = keys[pick]
    return idx


def blurred(blocks):
    """8x8 RGB blocks (n, 8, 8, 3) smoothed inside themselves, as the eye mixes a dither: two cells that
    look alike from a normal distance come out alike here even where their pixels differ."""
    out = blocks
    for axis in (1, 2):
        pad = [(0, 0)] * 4
        pad[axis] = (2, 2)
        p = np.pad(out, pad, mode="edge")
        take = [slice(None)] * 4
        acc = 0
        for i, wgt in enumerate(BLUR):
            take[axis] = slice(i, i + 8)
            acc = acc + wgt * p[tuple(take)]
        out = acc
    return out


def cells_of(a):
    """(rows*cols, 8, 8, ...) blocks of an array whose sides are whole cells, row-major."""
    h, w = a.shape[:2]
    return a.reshape(h // 8, 8, w // 8, 8, *a.shape[2:]).swapaxes(1, 2).reshape(-1, 8, 8, *a.shape[2:])


def flips_of(b):
    """The four orientations the encoder may reuse a cell in (fcencode.FLIPS), last axes 8x8."""
    return (b, b[..., :, ::-1], b[..., ::-1, :], b[..., ::-1, ::-1])


def shared_cells(frames, masks, origin, palette, cells, rounds=10, accents=None):
    """({frame: index array}, mean smoothed error, cells in use) for pictures drawn with a set of at
    most `cells` 8x8 cells chosen for all of them together, every place drawn with the cell - in any of
    the four orientations the encoder reuses a cell in - that looks most like the picture there.

    Coarser pixels and weaker dithering spend a cell dictionary evenly: a black wall gets as many
    distinct cells as the lit console in front of it, and the whole entry loses its detail to pay for the
    wall. Choosing the cells spends them where the pictures differ - a dark floor is a handful of cells
    used thousands of times, and what is left draws the parts one looks at. With cells to spare, every
    place simply gets the way of dithering it that looks most like the picture.

    frames: {frame: RGBA array}; masks: {frame: where it draws}; origin: {frame: its place on screen};
    palette: {slot: rgb} it may use; accents: {frame: where its picture has ACCENTS colours}, outside
    which a pixel is dithered without them - a grey between two colours far apart otherwise finds an
    accent the second nearest colour and is sprinkled with it - or None for a picture that may have
    them anywhere.

    How alike two cells look is measured on both smoothed (blurred), so a dither that mixes to the right
    colour counts as that colour. The candidates are the picture's own cells dithered at each of
    CANDIDATE_STRENGTHS; the set is started k-means++ style (each new cell taken where the set so far fits
    worst), then refined by turns: every place takes its nearest cell, every cell becomes the candidate
    of its places that serves them best together. A cell holding an accent only draws places whose own
    candidates hold one. Cells holding transparent pixels are kept as dithered - an outline is not
    approximated - and count against `cells`."""
    pal = np.zeros((17, 3), np.float32)
    for i, c in palette.items():
        pal[i] = c
    keys = sorted(frames)
    plain = {i: c for i, c in palette.items() if wintex.word(c) not in ACCENTS}
    target, cand, fixed_at = [], [], []
    for f in keys:
        rgb = frames[f][..., :3].astype(np.float32)
        target.append(blurred(cells_of(rgb)).reshape(-1, 192))
        dithered = []
        for s in CANDIDATE_STRENGTHS:
            idx = ordered(rgb, masks[f], palette, origin.get(f, (0, 0)), s)
            if accents is not None:
                idx = np.where(accents[f], idx, ordered(rgb, masks[f], plain, origin.get(f, (0, 0)), s))
            dithered.append(cells_of(idx))
        cand.append(np.stack(dithered, 1))                          # (n, strengths, 8, 8)
        fixed_at.append((dithered[0] == TRANSPARENT).any((1, 2)))
    T = np.vstack(target)
    C = np.vstack(cand)
    fixed = np.concatenate(fixed_at)
    n = len(T)

    # every distinct candidate once, with its four orientations' smoothed looks
    canon, pos_cand = {}, np.zeros(C.shape[:2], np.int64)
    blocks = []
    for p in range(n):
        for s in range(C.shape[1]):
            views = flips_of(C[p, s])
            key = min(v.tobytes() for v in views)
            u = canon.get(key)
            if u is None:
                u = canon[key] = len(blocks)
                blocks.append(np.frombuffer(key, np.uint8).reshape(8, 8))
            pos_cand[p, s] = u
    B = np.stack(blocks)
    look = blurred(pal[B.astype(np.int64)]).astype(np.float32)          # (u, 8, 8, 3)
    # flipped as cells are (rows and columns the last two axes), laid out as T is (row, column, colour)
    F = np.stack([np.ascontiguousarray(v.transpose(0, 2, 3, 1)).reshape(len(B), 192)
                  for v in flips_of(look.transpose(0, 3, 1, 2))], 1)
    Fn = (F ** 2).sum(-1)                                                # (u, 4)
    Tn = (T ** 2).sum(-1)
    # cells with an accent, and places whose own candidates have one (ACCENTS)
    accent_slots = [i for i, c in palette.items() if wintex.word(c) in ACCENTS]
    lit = np.isin(B, accent_slots).any((1, 2))                           # (u,)
    wants = np.isin(C, accent_slots).any((1, 2, 3))                      # (n,)
    BAR = np.float32(1e12)

    def against(rows, us):
        """Smoothed error of places `rows` against candidates `us`, the better orientation of each:
        (len(rows), len(us))."""
        d = Tn[rows, None] + Fn[us].reshape(1, -1) - 2 * (T[rows] @ F[us].reshape(-1, 192).T)
        d = np.maximum(d, 0).reshape(len(rows), len(us), 4).min(2)
        return d + BAR * (lit[us][None, :] & ~wants[rows][:, None])

    def nearest(centres):
        """(index into `centres`, orientation, error) of every place's best cell."""
        cf, cn = F[centres].reshape(-1, 192), Fn[centres].reshape(-1)
        barred = np.repeat(lit[centres], 4)
        best = np.empty(n, np.int64)
        err = np.empty(n, np.float32)
        for s in range(0, n, 512):
            d = np.maximum(Tn[s:s + 512, None] + cn[None] - 2 * (T[s:s + 512] @ cf.T), 0)
            d = d + BAR * (barred[None, :] & ~wants[s:s + 512, None])
            j = np.argmin(d, 1)
            best[s:s + 512] = j
            err[s:s + 512] = d[np.arange(len(j)), j]
        return best // 4, best % 4, err

    # places with transparency keep their own cells, which are part of the set from the start
    kept = {int(pos_cand[p, 0]) for p in np.nonzero(fixed)[0]}
    counts = np.bincount(pos_cand[~fixed, 0], minlength=len(B))
    centres = sorted(kept) + [int(np.argmax(counts))]
    chosen = set(centres)
    d_min = against(np.arange(n), np.array(centres)).min(1)
    rng = np.random.default_rng(0)
    while len(centres) < cells:
        w = np.where(fixed, 0, d_min).astype(np.float64)
        if w.sum() <= 0:
            break
        p = int(rng.choice(n, p=w / w.sum()))
        own = pos_cand[p]
        u = int(own[int(np.argmin(against(np.array([p]), own)[0]))])
        d_min[p] = 0
        if u in chosen:
            continue
        centres.append(u)
        chosen.add(u)
        d_min = np.minimum(d_min, against(np.arange(n), np.array([u]))[:, 0])
    centres = np.array(centres)

    for _ in range(rounds):
        who, _flip, err = nearest(centres)
        changed = False
        taken = set(int(c) for c in centres)
        for j in range(len(centres)):
            if int(centres[j]) in kept:
                continue
            members = np.nonzero((who == j) & ~fixed)[0]
            if not len(members):
                # an unused cell goes to the place the set serves worst
                order = np.argsort(np.where(fixed, -1, err))[::-1]
                for worst in order[:32]:
                    u = int(pos_cand[worst, 0])
                    if u not in taken:
                        taken.discard(int(centres[j]))
                        centres[j] = u
                        taken.add(u)
                        err[worst] = 0
                        changed = True
                        break
                continue
            pool = np.unique(np.concatenate([pos_cand[members].reshape(-1), [centres[j]]]))
            if len(pool) > 96:
                pool = np.unique(np.concatenate([rng.choice(pool, 95, replace=False), [centres[j]]]))
            pool = np.array([u for u in pool if u == centres[j] or int(u) not in taken])
            cost = against(members, pool).sum(0)
            best = int(pool[int(np.argmin(cost))])
            if best != centres[j]:
                taken.discard(int(centres[j]))
                centres[j] = best
                taken.add(best)
                changed = True
        if not changed:
            break
    who, flip, err = nearest(centres)

    out, at = {}, 0
    for f in keys:
        h, w = masks[f].shape
        rows, cols = h // 8, w // 8
        idx = np.empty((h, w), np.uint8)
        for cy in range(rows):
            for cx in range(cols):
                p = at + cy * cols + cx
                if fixed[p]:
                    block = C[p, 0]
                else:
                    block = flips_of(B[centres[who[p]]])[flip[p]]
                idx[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = block
        out[f] = idx
        at += rows * cols
    in_use = len({int(centres[j]) for j in who[~fixed]} | kept)
    return out, float(err.mean()), in_use
