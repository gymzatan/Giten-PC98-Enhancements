"""A picture fitted into the frames of an FC entry: placement, colours, dithering and what it costs.

These are the steps the Windows artwork went through, gathered behind one call for tools/fcedit.py:

  placement   `place` puts the picture in the frame's own size - inside it, filling it, or stretched.
  colours     the entry's palette says which of its sixteen slots it sets (fcimage.Image.owned); only
              those may change. `fit_colours` chooses them on the 4-bit lattice the hardware has, and
              they are paired with the slots in order of brightness, so a slot the game draws bright
              stays bright - what the entry's other palette variants and its unconverted frames were
              drawn against. The other two ways leave the palette alone: draw with those slots in the
              colours they already hold (a picture that shares the screen), or with all sixteen (a
              picture that has the screen to itself).
  dithering   wincells.ordered: ordered dithering on the 8x8 grid the cells sit on, at full strength
              and then a little weaker, which is what keeps a picture inside the cell dictionary.
  cost        fcencode.cell_cost: the cells and the decoded bytes the entry would hold. Past either
              limit the cells are chosen for the pictures together (wincells.shared_cells) with the
              budget the entry has left beside the frames that keep their own.

A fit is returned, not written: `apply` puts one into the entry when the caller wants it.
"""
import os
import struct
import sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcencode
import fcimage
import gfx
import wincells
import wintex
TRANSPARENT = gfx.TRANSPARENT
CELL_LIMIT = fcencode.MAX_CELLS
MEMORY_CAP = 160040
PLAIN_STRENGTHS = (1.0, 0.75)
SHRINK = 0.97
PLACES = ('contain', 'cover', 'stretch')
PALETTES = ('auto', 'own', 'keep')
OUTLINES = ('picture', 'frame', 'opaque')

class FitError(ValueError):
    pass

class Fit:
    """What a conversion produced: the entry's palettes, one index array per frame it drew, and how."""
    __slots__ = ('palettes', 'index', 'how', 'counts', 'bytes', 'notes')

    def __init__(self, palettes, index, how, counts, size, notes):
        self.palettes, self.index, self.how = (palettes, index, how)
        self.counts, self.bytes, self.notes = (counts, size, notes)

    @property
    def cells(self):
        return sum(self.counts.values())

def frame_size(img, f):
    _x, _y, w, h, _words = img.frames[f]
    return (w * 8, h * 8)

def frame_origin(img, f):
    """Where the frame sits on screen, in pixels: the dithering grid follows the screen, not the
    picture, so that neighbouring frames of one view do not break the pattern at their seam."""
    x, y, _w, _h, _words = img.frames[f]
    return ((x - 65536 if x & 32768 else x) * 8, (y - 65536 if y & 32768 else y) * 8)

def owned(img):
    return [i for i, on in enumerate(img.owned()) if on]

def editable(entry):
    """Why this entry cannot be re-encoded, or None. The same four cases fcencode.encode_entry
    refuses, asked without encoding anything, so that a whole image can be listed at once."""
    try:
        img = fcimage.Image(entry)
        n_layout, = struct.unpack_from('<H', entry, 0)
        npal, = struct.unpack_from('<H', entry, 2 + n_layout + 2)
        if entry[2 + n_layout + 6 + 32 * npal + 5]:
            return 'The derived_plane flag is unsupported by the encoder.'
        first = fcencode.unique_frames(img)
        if not first:
            return 'This entry has no frames; the game draws its cells directly by number.'
        missing = fcencode.unreferenced(img, first)
        if missing:
            return f'The dictionary contains cells not referenced by frames ({missing}); the game draws them by number.'
        used = [w for f in first.values() for w in img.frames[f][4] if w & 16383]
        if not img.no_remap and any((w & 12288 for w in used)):
            return 'Remapped entries with kind-1/2/3 cells are unsupported.'
    except (ValueError, IndexError, KeyError, struct.error) as e:
        return f'{type(e).__name__}: {e}'
    return None

def place(im, tw, th, how):
    """The picture as an RGBA image of exactly the frame's size.

    contain: the whole picture inside the frame, the rest black; cover: scaled until it fills the
    frame and centre-cropped; stretch: pulled to the frame's shape."""
    if how not in PLACES:
        raise FitError(f'unknown placement {how!r}')
    im = im.convert('RGBA')
    if how == 'stretch' or im.size == (tw, th):
        return im.resize((tw, th), Image.LANCZOS) if im.size != (tw, th) else im
    scale = max(tw / im.width, th / im.height) if how == 'cover' else min(tw / im.width, th / im.height)
    nw, nh = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    small = im.resize((nw, nh), Image.LANCZOS)
    if how == 'cover':
        left, top = ((nw - tw) // 2, (nh - th) // 2)
        return small.crop((left, top, left + tw, top + th))
    out = Image.new('RGBA', (tw, th), (0, 0, 0, 255))
    out.paste(small, ((tw - nw) // 2, (th - nh) // 2), small)
    return out

def drawn_mask(img, f, rgba, outline):
    """Where the converted picture draws: its own opaque pixels, the frame's own outline, or all of it."""
    if outline == 'frame':
        w, h, pix = img.indices(f)
        return np.array([c is not None for c in pix], bool).reshape(h, w)
    if outline == 'opaque':
        return np.ones(rgba.shape[:2], bool)
    if outline != 'picture':
        raise FitError(f'unknown outline {outline!r}')
    return rgba[..., 3] > 0

def fit_colours(samples, fixed, n, rounds=40):
    """n colours on the 4-bit lattice beside the fixed ones: k-means over the picture's colours, then
    each colour in turn moved to the lattice colour that leaves the least error while the others stand.
    No two colours end up the same, so none of the entry's palette slots is wasted."""
    if n == 0 or not len(samples):
        return np.zeros((0, 3))
    q = np.clip(np.round(np.asarray(samples, float) / 17), 0, 15).astype(int)
    key = (q[:, 0] * 16 + q[:, 1]) * 16 + q[:, 2]
    uniq, counts = np.unique(key, return_counts=True)
    bins = np.stack([uniq // 256, uniq // 16 % 16, uniq % 16], 1) * 17.0
    w = counts.astype(float)
    luma = bins @ wintex.LUMA
    order = np.argsort(luma)
    centres = np.array([bins[order[min(len(order) - 1, int(len(order) * (i + 0.5) / n))]] for i in range(n)])
    fixed = np.asarray(fixed, float).reshape(-1, 3)
    for _ in range(rounds):
        allc = np.vstack([fixed, centres]) if len(fixed) else centres
        near = np.argmin(((bins[:, None, :] - allc[None]) ** 2).sum(-1), axis=1) - len(fixed)
        new = centres.copy()
        for k in range(n):
            sel = near == k
            if sel.any():
                new[k] = (bins[sel] * w[sel, None]).sum(0) / w[sel].sum()
        if np.allclose(new, centres):
            break
        centres = new
    centres = wintex.snap(centres)
    fixed_keys = {tuple(c) for c in fixed}
    for _ in range(rounds):
        moved = False
        for k in range(n):
            taken = fixed_keys | {tuple(c) for j, c in enumerate(centres) if j != k}
            others = np.vstack([fixed, np.delete(centres, k, axis=0)])
            base = ((bins[:, None, :] - others[None]) ** 2).sum(-1).min(1) if len(others) else np.full(len(bins), np.inf)
            cand = np.array([b for b in bins if tuple(b) not in taken])
            if not len(cand):
                continue
            err = (np.minimum(base[:, None], ((bins[:, None, :] - cand[None]) ** 2).sum(-1)) * w[:, None]).sum(0)
            best = cand[int(np.argmin(err))]
            if tuple(best) != tuple(centres[k]):
                centres[k] = best
                moved = True
        if not moved:
            break
    return centres

def choose_palette(img, pictures, masks, palette='auto', slots=None, hold=()):
    """(the entry's palette words with the fitted colours in them, the colours to dither against).

    The colours the entry does not set are placeholders: whatever stands in those slots when the game
    draws the picture comes from elsewhere on screen. Three ways to deal with that:

      auto  fit the slots the entry does set to the picture, and draw with those only.
      own   draw with the slots it sets, in the colours they already have - for a picture that shares
            the screen with everything else, like the frame around the view: those slots hold the same
            black, white, red, green and yellow in nearly every palette of the game, so a picture drawn
            in them keeps its colours wherever it is shown, and nothing else is recoloured by the fit.
      keep  draw with all sixteen as the entry has them - only for an entry that fills the screen on
            its own, since the other slots follow whatever else is drawn.

    slots narrows that down to some of them: the picture is then dithered out of those alone, which
    is how a neutral grey is had from a palette of saturated colours - black and white checkered give
    the greys between, where all five would drag in the red and the green as well.

    hold (auto only): slots of the entry that stay as they are and are still drawn with - the screen's
    black, white and status colours, which everything else on screen shows in; the other slots are
    fitted around them, as tools/winfit.py fits a demon."""
    if palette not in PALETTES:
        raise FitError(f'unknown palette mode {palette!r}')
    words = [list(p) for p in img.palettes]
    base = words[0] if words else [0] * 16
    mine = owned(img)
    if palette == 'keep' or not mine or (not words):
        return (words, pick({i: wintex.rgb_of(base[i]) for i in range(16)}, slots))
    if palette == 'own':
        return (words, pick({i: wintex.rgb_of(base[i]) for i in mine}, slots))
    drawn = list(pick({i: None for i in mine}, slots))
    held = [i for i in drawn if i in hold]
    use = [i for i in drawn if i not in hold]
    fixed = [wintex.rgb_of(base[i]) for i in held] if hold else [wintex.rgb_of(base[i]) for i in range(16) if i not in use]
    samples = np.vstack([p[..., :3][masks[f]].reshape(-1, 3) for f, p in pictures.items() if masks[f].any()] or [np.zeros((1, 3))])
    centres = fit_colours(samples, fixed, len(use))
    dark_first = sorted(use, key=lambda i: float(wintex.rgb_of(words[0][i]) @ wintex.LUMA))
    for slot, colour in zip(dark_first, sorted(centres, key=lambda c: float(c @ wintex.LUMA))):
        words[0][slot] = wintex.word(colour)
    return (words, {i: wintex.rgb_of(words[0][i]) for i in drawn})

def pick(colours, slots):
    """`colours` narrowed to `slots`, or all of them when no slots are asked for."""
    if slots is None:
        return colours
    short = [i for i in slots if i not in colours]
    if short:
        raise FitError('This palette mode cannot use slot ' + '、'.join((str(i) for i in short)))
    if not slots:
        raise FitError('At least one color slot is required')
    return {i: colours[i] for i in slots}

def edits_of(img, index):
    """{layout offset: row-major pixels} for {frame: index array}, as fcencode takes them."""
    offs = fcencode.frame_offsets(img.layout)
    out = {}
    for f, idx in index.items():
        out[offs[f]] = [None if v == TRANSPARENT else int(v) for v in idx.reshape(-1)]
    return out

def borrowed_note(index, img):
    """A warning when the fit drew with slots the entry does not set - there is nothing to stop it
    (keeping the palette offers all sixteen), but the result changes colour with what is on screen."""
    got = borrowed_slots(index, img)
    if not got:
        return []
    return ['The picture uses slots this entry does not own (' + '、'.join(map(str, got)) + '). Other pictures supply these colors, so they can change with the scene. Use owned-slot fitting for stable colors.']

def fits(counts, size):
    return max(counts.values()) <= CELL_LIMIT and size <= MEMORY_CAP

def borrowed_slots(index, img):
    """The slots a fitted picture draws with that the entry does not set.

    Their colours come from whatever else is on screen - the room's picture, or the message window's
    own colours, which the game changes from one kind of window to the next - so a picture drawn with
    them does not keep its colours: the same window came out blue in one message and red in the
    next."""
    mine = set(owned(img)) | {TRANSPARENT}
    used = set()
    for a in index.values():
        used |= {int(v) for v in np.unique(a)}
    return sorted(used - mine)

def fit(entry, pictures, palette='auto', slots=None, strength=None, placement='contain', outline='picture', progress=None, hold=()):
    """Fit pictures into an entry's frames.

    pictures: {frame: a PIL image}; palette: one of PALETTES; slots: the only slots to draw with, or
    None for all the mode offers; strength: a fixed dithering strength, or None to take the usual ones
    in turn; hold: slots that keep their colours and are drawn with (choose_palette). Returns a Fit;
    raises FitError when there is no room."""
    img = fcimage.Image(entry)
    offs = fcencode.frame_offsets(img.layout)
    first = fcencode.unique_frames(img)
    say = progress or (lambda _text: None)
    for f in pictures:
        if f >= len(offs):
            raise FitError(f'This entry has no frame {f} 帧')
        if first[offs[f]] != f:
            raise FitError(f'Frame {f} shares the picture of frame {first[offs[f]]}; edit that frame instead')
    rgba, masks, origin = ({}, {}, {})
    for f, im in pictures.items():
        w, h = frame_size(img, f)
        rgba[f] = np.asarray(place(im, w, h, placement).convert('RGBA'))
        masks[f] = drawn_mask(img, f, rgba[f], outline)
        origin[f] = frame_origin(img, f)
    words, colours = choose_palette(img, rgba, masks, palette, slots, hold)
    notes = []
    held = [i for i in owned(img) if i in hold and i in colours and (palette == 'auto')]
    if held:
        notes.append('Slots ' + '、'.join((str(i) for i in held)) + ' keep their original screen/status colors and remain usable.')
    if slots is not None:
        notes.append('Used only slots ' + '、'.join((str(i) for i in slots)) + '; other slots are unused.')
    if not owned(img):
        notes.append('This entry sets no colors. It uses the current screen palette, so the existing 16 colors are retained.')
    elif palette == 'keep':
        notes.append('Kept the entry palette and dithered the picture to its existing 16 colors.')
    elif palette == 'own':
        notes.append(f"Used only the entry's {len(owned(img))} owned slots, keeping their colors.")
    else:
        notes.append(f'Refitted {len(owned(img)) - len(held)} owned slots; externally supplied slots are preserved.')
    if len(img.palettes) > 1 and palette == 'auto':
        notes.append(f'This entry has {len(img.palettes)} palettes. Only palette 0 changed; other variants are preserved.')
    untouched = sorted({first[o] for o in first} - set(pictures))
    if untouched and palette == 'auto':
        notes.append('Unchanged frames (' + '、'.join((str(f) for f in untouched)) + ') keep their pixels but use the new palette.')
    for s in [strength] if strength is not None else PLAIN_STRENGTHS:
        index = {f: wincells.ordered(a[..., :3].astype(float), masks[f], colours, origin[f], s) for f, a in rgba.items()}
        counts, size = fcencode.cell_cost(entry, edits_of(img, index))
        say(f'Ordered dithering, strength {s:g}：{sum(counts.values())} cells, {size} bytes')
        if fits(counts, size):
            return Fit(words, index, f'Ordered dithering, strength {s:g}', counts, size, notes + borrowed_note(index, img))
    blank = {f: np.full(m.shape, TRANSPARENT, np.uint8) for f, m in masks.items()}
    kept, kept_bytes = fcencode.cell_cost(entry, edits_of(img, blank))
    budget = int(min(CELL_LIMIT - kept[0], (MEMORY_CAP - kept_bytes) // 40))
    while budget > 0:
        say(f'Shared-cell selection, budget {budget}')
        index, err, in_use = wincells.shared_cells(rgba, masks, origin, colours, budget)
        counts, size = fcencode.cell_cost(entry, edits_of(img, index))
        if fits(counts, size):
            notes.append('The full cell set exceeds capacity; cells are selected jointly using the existing scene-fitting method.')
            return Fit(words, index, f'Shared cells {in_use} (smoothed error {err:.0f}）', counts, size, notes + borrowed_note(index, img))
        budget = int(budget * SHRINK)
    raise FitError("This picture does not fit; the entry's cell dictionary and decoded memory are occupied by its other frames.")

def apply(entry, fit_result):
    """The entry with a fit's pictures encoded into it and its palettes written."""
    img = fcimage.Image(entry)
    try:
        new = fcencode.encode_entry(entry, edits_of(img, fit_result.index))
    except fcencode.EncodeError as e:
        raise FitError(str(e)) from None
    return gfx.set_entry_palettes(new, fit_result.palettes)

def preview(fit_result, img, f, palette=0):
    """The fitted frame as an RGB image, drawn in the palette the fit gives the entry."""
    words = fit_result.palettes[min(palette, len(fit_result.palettes) - 1)]
    table = np.array([fcimage.pc98_rgb(v) for v in words] + [(40, 40, 48)], np.uint8)
    return Image.fromarray(table[fit_result.index[f]])
