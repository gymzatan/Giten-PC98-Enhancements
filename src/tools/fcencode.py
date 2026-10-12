#!/usr/bin/env python3
"""FC write-back: edited frames of an entry encoded back into its cell dictionaries and cell stream.

The game's FC entries all share these properties, and encode_entry() keeps them:
  - the layout is its table of frame offsets and then the records they point at, back to
    back in the order they stand, nothing between or after them;
  - dictionaries are in order of first use: frames in layout order (an offset several
    frames share, once), each frame row by row;
  - kind-0 cell 0 is blank and never referenced (a word without kind and index bits
    draws nothing), and it is coded in full: every entry's cell stream opens with code 00,
    mode 0 filling all four columns with 00. 0871:55F8 never clears its column buffer, so
    a first cell coded as the previous cell again would take the planes of whatever
    picture was decoded before, and the battle's 2x drawer (0871:B1EE, フォッグ and
    ダークネス) draws cell 0 for every empty word, ORing those planes over the view;
  - every other cell is referenced by some frame (FC0000 entry 4 excepted: it has no
    frames, the game draws its cells by number, and it is refused);
  - no cell has plane bits outside its mask;
  - derived_plane is never set (refused as well);
  - an entry that remaps colours (no_remap == 0) has kind-0 cells only (refused otherwise).

Only cells whose pixels an edit changes get new words; every other word keeps its kind
and flip bits. A changed cell that is fully transparent becomes word 0. Otherwise its
kind is the kind of the word it replaces when that kind draws its colours (kind 1:
0-7, kind 2: 0-3, kind 3: 0-1); else kind 0 in an entry whose words are all kind 0
(so every remapping entry), and the kind with the fewest planes drawing its colours in
any other entry. The cell then reuses a cell of that kind with the same pixels, plain
or flipped
with a flip bit combination the entry's words already contain (bit 15 horizontal, 14
vertical; the game's images place flips selectively), or becomes a new cell. Cells no
word references any more are dropped and the dictionaries renumbered in first-use
order, so an unedited entry keeps its layout and dictionaries; its cell codes come
from a cost search over the modes of 0871:55F8 and can differ from the original bytes.

A frame's box - where it sits, in cells from the point the game draws the entry at, and
how many cells it spans - changes where `boxes` gives a new one, for a frame edited at
that size: every cell of it is then placed as a new edit is, and the frames sharing its
record move with it. The layout is written anew from its records in either case, so an
entry whose boxes stay keeps it byte for byte.
"""
import struct

import fcimage

FLIPS = (0x0000, 0x8000, 0x4000, 0xC000)
MAX_CELLS = 0xFFF                      # per kind (0871:A575)
KIND_COLOURS = (16, 8, 4, 2)           # colours a kind draws: planes 4, 3, 2, 1
COPY_MODES = range(6, 12)
BLANK = (None,) * 64


class EncodeError(ValueError):
    pass


def flip_cell(pix, flip):
    """The 64 pixels of a cell drawn with a word's flip bits (flipping twice restores it)."""
    out = []
    for r in range(8):
        row = pix[(7 - r if flip & 0x4000 else r) * 8:][:8]
        out.extend(reversed(row) if flip & 0x8000 else row)
    return tuple(out)


def cell_columns(pix):
    """(4 plane columns of 8 row bytes, 8 mask bytes); planes are 0 where transparent."""
    cols = [[0] * 8 for _ in range(4)]
    mask = [0] * 8
    for r in range(8):
        for b in range(8):
            c = pix[r * 8 + b]
            if c is None:
                continue
            bit = 0x80 >> b
            mask[r] |= bit
            for p in range(4):
                if c >> p & 1:
                    cols[p][r] |= bit
    return [tuple(c) for c in cols], bytes(mask)


def _rows_differing(col, base):
    """Mask byte and bytes of the rows where col differs from base."""
    m, data = 0, []
    for r in range(8):
        if col[r] != base[r]:
            m |= 0x80 >> r
            data.append(col[r])
    return bytes([m] + data)


def _rows_changing(col, start):
    """Mask byte and bytes of the rows where col differs from the row above (start above row 0)."""
    m, data, last = 0, [], start
    for r in range(8):
        if col[r] != last:
            m |= 0x80 >> r
            data.append(col[r])
            last = col[r]
    return bytes([m] + data)


class CellEncoder:
    """Cell codes for 0871:55F8, tracking its 4-column buffer that persists from cell to cell.

    The buffer also persists from one entry to the next, so what it holds when an entry's first cell
    is decoded depends on what the game loaded before: unknown here (None) until a cell has written
    all four columns, and "the previous cell again" (mode 14) is only offered once it is known."""

    def __init__(self):
        self.cols = None

    def encode(self, target):
        """target: 4 columns (tuples of 8 bytes, None where any value will do) -> code bytes."""
        old = self.cols
        best = None
        if old is not None and all(t is None or t == old[p] for p, t in enumerate(target)):
            best = (bytes([14]), list(old))
        for mode in range(14):
            got = self._mode(mode, target, old)
            if best is None or len(got[0]) < len(best[0]):
                best = got
        self.cols = best[1]
        return best[0]

    @staticmethod
    def _mode(mode, target, old):
        fill = (fcimage.FILL[mode],) * 8
        default = (fcimage.DEFAULT[mode],) * 8
        new = list(old) if old is not None else [None] * 4
        head = mode
        sel = 0
        body = bytearray()
        for p in range(4):
            t = target[p]
            options = []                                   # (bytes, flag, selector, column)
            if mode in COPY_MODES:
                # Only from a column this cell has already written. The game's own 500,000 cells copy
                # from nothing else - not once from a column's own place, not once from one still
                # holding the cell before. What 0871:572B reads in those two cases is therefore
                # untested by any picture the game ships, and a cell that guessed wrong comes out as
                # the texture scrambled.
                for s in range(p):
                    src = new[s]
                    if t is None or t == src:
                        options.append((b"", 0, s, src))
                    elif mode >= 8:
                        options.append((_rows_differing(t, src), 1, s, t))
            if t is None or t == fill:
                options.append((b"", 0, 3, fill))
            if t is not None:
                if mode in (0, 1, 6, 7):
                    options.append((bytes(t), 1, 3, t))
                elif mode in (12, 13):
                    options.append((_rows_changing(t, default[0]), 1, 3, t))
                else:
                    options.append((_rows_differing(t, default), 1, 3, t))
            data, flag, s, col = min(options, key=lambda o: len(o[0]))
            head |= flag << (7 - p)
            sel |= s << (6 - 2 * p)
            body += data
            new[p] = col
        code = bytes([head]) + (bytes([sel]) if mode in COPY_MODES else b"") + bytes(body)
        return code, new


def frame_offsets(layout):
    _head, n = struct.unpack_from("<2H", layout, 0)
    return list(struct.unpack_from(f"<{n}H", layout, 4))


def unique_frames(img):
    """{layout offset: index of the first frame using it}, in layout order."""
    first = {}
    if len(img.layout) >= 4:
        for f, o in enumerate(frame_offsets(img.layout)):
            first.setdefault(o, f)
    return first


def frame_box(img, f):
    """(x, y, w, h) of a frame in cells: where it sits from the entry's anchor, and its size."""
    x, y, w, h, _words = img.frames[f]
    return (x - 0x10000 if x & 0x8000 else x), (y - 0x10000 if y & 0x8000 else y), w, h


def unreferenced(img, first):
    used = {q: set() for q in range(4)}
    used[0].add(0)
    for f in first.values():
        for w in img.frames[f][4]:
            if w & 0x3FFF:
                used[(w >> 12) & 3].add(w & 0xFFF)
    return {q: img.counts[q] - len(used[q]) for q in range(4) if img.counts[q] != len(used[q])}


def _kind(cell, hint, all_kind0):
    top = max(c for c in cell if c is not None)
    if hint is not None and top < KIND_COLOURS[hint]:
        return hint
    if all_kind0:
        return 0
    return next(q for q in (3, 2, 1, 0) if top < KIND_COLOURS[q])


def cell_target(cell, q):
    """Buffer columns a kind-q cell needs (None = any value) and the mask bytes kind 0 appends."""
    cols, mask = cell_columns(cell)
    if q == 0:
        return cols, mask
    n = 4 - q
    return cols[:n] + [tuple(mask)] + [None] * (3 - n), b""


def _dictionaries(img):
    """(cells of each kind as pixel tuples, {(kind, pixels): index} of the cells a frame may reuse).

    Kind-0 cell 0 is the blank one a word without kind and index bits draws, and is never reused by
    name."""
    cells = {q: [tuple(img.cell_pixels(q << 12 | i)) for i in range(img.counts[q])] for q in range(4)}
    index = {}
    for q in range(4):
        for i, cell in enumerate(cells[q]):
            if (q, i) != (0, 0):
                index.setdefault((q, cell), i)
    return cells, index


def _check_boxes(first, edits, boxes):
    for o, (x, y, w, h) in boxes.items():
        if o not in first:
            raise EncodeError(f"no frame at layout offset {o}")
        if o not in edits:
            raise EncodeError(f"frame {first[o]}: a new box needs the frame's pixels at that size")
        if not (w > 0 and h > 0 and -0x8000 <= x < 0x8000 and -0x8000 <= y < 0x8000):
            raise EncodeError(f"frame {first[o]}: box at {x},{y} of {w}x{h} cells")


def _assign(img, first, edits, all_kind0, flips, cells, index, boxes):
    """({layout offset: [(flip, kind, cell index) or None]}, {layout offset: the pixels it draws}).

    Every cell of every frame placed: an unedited frame keeps its own words, and an edited one reuses
    a cell the entry already holds - plain or under a flip its own words use - and adds to `cells` and
    `index` only what is left. A frame given a new box has no words of its own to keep."""
    words, targets = {}, {}
    for o, f in first.items():
        _x, _y, w, h, orig = img.frames[f]
        if o in boxes:
            _x, _y, w, h = boxes[o]
            orig = (0,) * (w * h)
        W = w * 8
        if o not in edits:
            words[o] = [(wd & 0xC000, (wd >> 12) & 3, wd & 0xFFF) if wd & 0x3FFF else None
                        for wd in orig]
            targets[o] = img.indices(f)[2]
            continue
        pix = list(edits[o])
        if len(pix) != W * h * 8:
            raise EncodeError(f"frame {f}: {len(pix)} pixels given, the frame has {W * h * 8}")
        targets[o] = pix
        out = []
        for cy in range(h):
            for cx in range(w):
                base = cy * 8 * W + cx * 8
                cell = tuple(pix[base + r * W + b] for r in range(8) for b in range(8))
                ow = orig[cy * w + cx]
                if cell == (tuple(img.cell_pixels(ow)) if ow & 0x3FFF else BLANK):
                    out.append((ow & 0xC000, (ow >> 12) & 3, ow & 0xFFF) if ow & 0x3FFF else None)
                    continue
                if cell == BLANK:
                    out.append(None)
                    continue
                q = _kind(cell, (ow >> 12) & 3 if ow & 0x3FFF else None, all_kind0)
                for flip in flips:
                    idx = index.get((q, flip_cell(cell, flip)))
                    if idx is not None:
                        out.append((flip, q, idx))
                        break
                else:
                    idx = len(cells[q])
                    index[(q, cell)] = idx
                    cells[q].append(cell)
                    out.append((0, q, idx))
        words[o] = out
    return words, targets


def cell_cost(entry, edits, boxes=None):
    """({kind: cells the entry would hold}, bytes they take decoded) if `edits` (and `boxes`) were
    encoded into it.

    The assignment encode_entry makes, stopped before the cell codes are written, so that a conversion
    can ask what a picture costs before paying for the encoding. Counting an entry's distinct 8x8
    patterns instead ignores both the cells it already holds and the flips it draws them under, and
    reads far above the truth. A cell takes (4 - kind) * 8 + 8 bytes decoded - four planes and a mask
    for kind 0, one plane fewer for each kind above it."""
    img = fcimage.Image(entry)
    first = unique_frames(img)
    boxes = dict(boxes or {})
    _check_boxes(first, edits, boxes)
    used = [w for f in first.values() for w in img.frames[f][4] if w & 0x3FFF]
    all_kind0 = not any(w & 0x3000 for w in used)
    flips = [F for F in FLIPS if not F or any(w & 0xC000 == F for w in used)]
    cells, index = _dictionaries(img)
    words, _targets = _assign(img, first, edits, all_kind0, flips, cells, index, boxes)
    order = {q: ({0} if q == 0 else set()) for q in range(4)}
    for items in words.values():
        for item in items:
            if item is not None:
                order[item[1]].add(item[2])
    counts = {q: len(order[q]) for q in range(4)}
    return counts, sum(counts[q] * ((4 - q) * 8 + 8) for q in range(4))


def _layout(img, first, words, boxes):
    """The layout written anew: the table of frame offsets, then every record - box, then words
    column by column - back to back in the order the records stood."""
    head, n = struct.unpack_from("<2H", img.layout, 0)
    at = 4 + 2 * n
    moved, body = {}, bytearray()
    for o in sorted(first):
        x, y, w, h = boxes.get(o) or frame_box(img, first[o])
        moved[o] = at + len(body)
        body += struct.pack("<4H", x & 0xFFFF, y & 0xFFFF, w, h)
        body += struct.pack(f"<{w * h}H", *[words[o][cy * w + cx] for cx in range(w) for cy in range(h)])
    layout = struct.pack(f"<2H{n}H", head, n, *[moved[o] for o in frame_offsets(img.layout)]) + body
    if len(layout) > 0xFFFF:
        raise EncodeError(f"the layout would take {len(layout)} bytes; its length is a 16-bit word")
    return bytes(layout)


def encode_entry(entry, edits, boxes=None):
    """entry: an FC entry as stored; edits: {layout offset: row-major pixels of the frame,
    colour 0-15 or None for transparent}; boxes: {layout offset: (x, y, w, h)} in cells for frames
    that take a new box, each of them in `edits` at that size. -> the entry with those frames
    replaced."""
    (n_layout,) = struct.unpack_from("<H", entry, 0)
    (npal,) = struct.unpack_from("<H", entry, 2 + n_layout + 2)
    if entry[2 + n_layout + 6 + 32 * npal + 5]:
        raise EncodeError("entries with derived_plane set are not supported (the game has none)")
    img = fcimage.Image(entry)
    first = unique_frames(img)
    missing = unreferenced(img, first)
    if missing:
        raise EncodeError(f"dictionary cells no frame references {missing}: the game draws "
                          "them by number, so this entry cannot be re-encoded")
    if not first:
        raise EncodeError("entry has no frames")
    unknown = sorted(set(edits) - set(first))
    if unknown:
        raise EncodeError(f"no frame at layout offsets {unknown}")
    boxes = dict(boxes or {})
    _check_boxes(first, edits, boxes)
    used = [w for f in first.values() for w in img.frames[f][4] if w & 0x3FFF]
    all_kind0 = not any(w & 0x3000 for w in used)
    if not img.no_remap and not all_kind0:
        raise EncodeError("an entry that remaps colours and has kind 1-3 cells (the game has none)")
    flips = [F for F in FLIPS if not F or any(w & 0xC000 == F for w in used)]

    cells, index = _dictionaries(img)
    words, targets = _assign(img, first, edits, all_kind0, flips, cells, index, boxes)

    # Renumber after the whole entry is known. New unique cells may temporarily
    # exceed 0xFFF while unused originals still sit in `cells`; packing into a
    # 12-bit word before this drop overflows into the kind bits (IndexError).
    order = {q: [] for q in range(4)}
    order[0].append(0)
    renumber = {(0, 0): 0}
    packed = {}
    for o, f in first.items():
        packed_words = []
        for item in words[o]:
            if item is None:
                packed_words.append(0)
                continue
            flip, q, idx = item
            key = (q, idx)
            if key not in renumber:
                renumber[key] = len(order[q])
                order[q].append(idx)
            packed_words.append(flip | q << 12 | renumber[key])
        packed[o] = packed_words
    words = packed
    for q in range(4):
        if len(order[q]) > MAX_CELLS:
            raise EncodeError(f"{len(order[q])} different kind-{q} cells, the game takes {MAX_CELLS}")

    layout = _layout(img, first, words, boxes)
    enc = CellEncoder()
    stream = bytearray()
    for q in range(4):
        for i in order[q]:
            target, mask = cell_target(cells[q][i], q)
            stream += enc.encode(target) + mask
    palettes = entry[2 + len(img.layout):img.data_start]
    new = (struct.pack("<H", len(layout)) + bytes(layout) + palettes
           + struct.pack("<IBB4H", 10 + len(stream), img.no_remap, img.derived,
                         *[len(order[q]) for q in range(4)])
           + bytes(stream))
    check = fcimage.Image(new)
    for o, f in first.items():
        if check.indices(f)[2] != targets[o] or frame_box(check, f) != (boxes.get(o) or frame_box(img, f)):
            raise EncodeError(f"frame {f} decodes differently after encoding")
    return new
