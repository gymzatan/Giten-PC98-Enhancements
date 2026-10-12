#!/usr/bin/env python3
"""FC graphics (FC*.BIN): container, frames, palettes and the 8x8-cell codec.

Reading follows DDS98.EXE 0871:ADC0 and the routines it calls.

    file   = entry*                      entry = [u32 length][length bytes]
             (resource id low nibble = entry number, 0871 ov20:09F8)
    entry  = [u16 len][layout: len bytes]                          0871:ACAC
             [u16 ?][u16 npal][u16 ?][npal x 16 x u16 colours]     0871:A3A2
             [u32 size][u8 no_remap][u8 derived_plane]
             [u16 count0..3][cells: size-10 bytes]                 0871:A4D8

layout = [u16 ?][u16 nframes][nframes x u16 offset into layout]
frame  = [u16 x][u16 y][u16 w][u16 h][w*h x u16 cell]   (8-pixel cells, column by column)
cell   = kind << 12 | index    kind 0: 4 planes, 1: 3 planes, 2: 2 planes, 3: 1 plane,
                               each with a mask

Dictionaries are stored in kind order 0..3, count_k cells each. Every cell is one
code (0871:55F8) decoded into a static 32-byte buffer, row-major, one byte per
column per row, so a code can reuse columns of the previous cell. Kind 0 takes
columns 0-3 as planes and 8 more bytes as the mask (0871:BC80); kind k = 1..3 takes
columns 0..3-k as planes and the next column as the mask (0871:AC5E, BCEE, BD5C,
BDCA). With derived_plane set, the mask is the OR of all four columns instead (no
entry sets it). The drawing (1603:0386, GRCG RMOS through the mask) sets the planes
a kind lacks to 0 (AH), so kind 1 draws colours 0-7, kind 2 0-3, kind 3 0-1.
Colour of a pixel = p3*8 + p2*4 + p1*2 + p0.

An entry with no_remap == 0 has the colours its palette sets remapped at load
(0871:BBBE) to the palette slots allocated for them (0871:8F16); that applies to
kind-0 cells only, and every such entry has kind-0 cells only.
"""
import struct

FILL = [0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x88, 0x88]
DEFAULT = [0x88, 0x88, 0x00, 0xFF, 0xFF, 0x00, 0x88, 0x88, 0x00, 0xFF, 0xFF, 0x00, 0x00, 0xFF, 0x88, 0x88]
KIND_PLANES = {0: 4, 1: 3, 2: 2, 3: 1}


class FormatError(ValueError):
    pass


def entries(data):
    out, pos = [], 0
    while pos < len(data):
        if pos + 4 > len(data):
            raise FormatError("truncated entry length")
        n = struct.unpack_from("<I", data, pos)[0]
        if pos + 4 + n > len(data):
            raise FormatError("entry runs past the end of the file")
        out.append(data[pos + 4:pos + 4 + n])
        pos += 4 + n
    return out


class CellDecoder:
    """0871:55F8 over a byte string; the output buffer persists between cells.

    In the game it persists between entries as well - nothing clears it - so an entry's first cell
    starts from whatever the last picture decoded left. Zeros stand for that here; `buf` sets it
    to something else, to see whether a stream decodes the same whatever came before it (every
    stream of the game's own opens with code 00, which fills all four columns)."""

    def __init__(self, data, pos, buf=None):
        self.d, self.p = data, pos
        self.buf = bytearray(buf) if buf is not None else bytearray(32)

    def byte(self):
        if self.p >= len(self.d):
            raise FormatError("cell stream ends inside a cell")
        v = self.d[self.p]
        self.p += 1
        return v

    def cell(self):
        hdr = self.byte()
        mode = hdr & 0x0F
        flags = hdr
        fill, default = FILL[mode], DEFAULT[mode]
        buf = self.buf

        def flag():
            nonlocal flags
            flags <<= 1
            return (flags >> 8) & 1

        def column_fill(p, v):
            for r in range(8):
                buf[4 * r + p] = v

        def column_literal(p):
            for r in range(8):
                buf[4 * r + p] = self.byte()

        def column_sparse_default(p):              # 0871:570C
            mask = self.byte()
            for r in range(8):
                buf[4 * r + p] = self.byte() if mask & (0x80 >> r) else default

        def column_sparse_repeat(p):               # 0871:56C9
            mask = self.byte()
            last = default
            for r in range(8):
                if mask & (0x80 >> r):
                    last = self.byte()
                buf[4 * r + p] = last

        def column_copy(p, src):                   # 0871:572B
            for r in range(8):
                buf[4 * r + p] = buf[4 * r + src]

        def literal_or_fill(p):                    # 0871:56E6
            if flag():
                column_literal(p)
            else:
                column_fill(p, fill)

        if mode in (0, 1):
            for p in range(4):
                literal_or_fill(p)
        elif mode in (2, 3, 4, 5):
            for p in range(4):
                if flag():
                    column_sparse_default(p)
                else:
                    column_fill(p, fill)
        elif mode in (6, 7):
            sel = self.byte()
            for p in range(4):
                s = (sel >> (6 - 2 * p)) & 3
                if s == 3:
                    literal_or_fill(p)
                else:
                    flag()
                    column_copy(p, s)
        elif mode in (8, 9, 10, 11):
            sel = self.byte()
            for p in range(4):
                s = (sel >> (6 - 2 * p)) & 3
                if s != 3:
                    column_copy(p, s)
                    if flag():
                        mask = self.byte()
                        for r in range(8):
                            if mask & (0x80 >> r):
                                buf[4 * r + p] = self.byte()
                elif flag():
                    column_sparse_default(p)
                else:
                    column_fill(p, fill)
        elif mode in (12, 13):
            for p in range(4):
                if flag():
                    column_sparse_repeat(p)
                else:
                    column_fill(p, fill)
        # modes 14, 15: the previous cell again
        return bytes(buf)


class Image:
    """One FC entry: frames of cells, palettes, and the decoded cell dictionaries. `buf`: what the cell
    decoder's buffer holds before the first cell (CellDecoder)."""

    def __init__(self, entry, buf=None):
        pos = 0
        (n_layout,) = struct.unpack_from("<H", entry, pos)
        self.layout = entry[pos + 2:pos + 2 + n_layout]
        pos += 2 + n_layout
        self.pal_head, npal, self.pal_tail = struct.unpack_from("<3H", entry, pos)
        pos += 6
        self.palettes = [list(struct.unpack_from("<16H", entry, pos + 32 * k)) for k in range(npal)]
        pos += 32 * npal
        size, self.no_remap, self.derived = struct.unpack_from("<IBB", entry, pos)
        counts = struct.unpack_from("<4H", entry, pos + 6)
        if any(c > 0xFFF for c in counts):
            raise FormatError(f"dictionary count out of range: {counts}")
        self.counts = counts
        dec = CellDecoder(entry, pos + 14, buf)
        self.cells = {k: [] for k in range(4)}
        for kind in range(4):
            planes = KIND_PLANES[kind]
            for _ in range(counts[kind]):
                c = dec.cell()
                rows = [list(c[4 * r:4 * r + 4]) for r in range(8)]
                if self.derived:
                    mask = [r[0] | r[1] | r[2] | r[3] for r in rows]
                elif kind == 0:
                    mask = [dec.byte() for _ in range(8)]
                else:
                    mask = [r[planes] for r in rows]
                rows = [r[:planes] + [0] * (4 - planes) for r in rows]
                self.cells[kind].append((rows, mask))
        self.stream_end = dec.p
        self.stream_size = size
        self.data_start = pos
        self.frames = self._frames()
        self._pix_cache = {}

    def _frames(self):
        if len(self.layout) < 4:
            return []
        _head, n = struct.unpack_from("<2H", self.layout, 0)
        offs = struct.unpack_from(f"<{n}H", self.layout, 4)
        frames = []
        for o in offs:
            x, y, w, h = struct.unpack_from("<4H", self.layout, o)
            cols = struct.unpack_from(f"<{w * h}H", self.layout, o + 8)
            words = tuple(cols[cx * h + cy] for cy in range(h) for cx in range(w))   # to row-major
            frames.append((x, y, w, h, words))
        return frames

    def cell_pixels(self, word):
        """64 colour indices (None = transparent) of the cell a frame word names."""
        cached = self._pix_cache.get(word)
        if cached is not None:
            return cached
        kind, idx = (word >> 12) & 3, word & 0xFFF
        if idx >= len(self.cells[kind]):
            raise FormatError(f"cell {kind}:{idx} beyond dictionary of {len(self.cells[kind])}")
        rows, mask = self.cells[kind][idx]
        out = []
        for r in range(8):
            rr = 7 - r if word & 0x4000 else r
            p0, p1, p2, p3 = rows[rr]
            for b in range(8):
                bit = 0x01 << b if word & 0x8000 else 0x80 >> b
                if not mask[rr] & bit:
                    out.append(None)
                else:
                    out.append((8 if p3 & bit else 0) | (4 if p2 & bit else 0) |
                               (2 if p1 & bit else 0) | (1 if p0 & bit else 0))
        self._pix_cache[word] = out
        return out

    def indices(self, frame):
        """(width, height, [colour index or None per pixel]) of one frame.

        Drawing follows 1603:0386: a word with no kind/index bits (& 3FFF == 0) is
        left transparent, bit 14 flips the cell vertically, bit 15 horizontally,
        every kind draws through its mask."""
        _x, _y, w, h, words = self.frames[frame]
        W, H = w * 8, h * 8
        pix = [None] * (W * H)
        for cy in range(h):
            for cx in range(w):
                word = words[cy * w + cx]
                if not word & 0x3FFF:
                    continue
                cell = self.cell_pixels(word)
                base = cy * 8 * W + cx * 8
                for r in range(8):
                    pix[base + r * W:base + r * W + 8] = cell[r * 8:r * 8 + 8]
        return W, H, pix

    def owned(self):
        """Colours the entry's palette sets (bit 15 = colour 0, 0871:8F16); the rest come from the game."""
        return [bool(self.pal_tail & (0x8000 >> i)) for i in range(16)]

    def render(self, frame, palette=0):
        """(width, height, rgba bytes) of one frame with the entry's own palette."""
        W, H, pix = self.indices(frame)
        pal = self.palettes[palette] if self.palettes else [0] * 16
        rgb = [pc98_rgb(v) for v in pal]
        out = bytearray(W * H * 4)
        for i, c in enumerate(pix):
            if c is not None:
                out[4 * i:4 * i + 4] = bytes(rgb[c]) + b"\xff"
        return W, H, bytes(out)


def pc98_rgb(v):
    """A palette word: 4-bit G, R, B as 0x0GRB (0871:8C40 splits it for ports AA/AC/AE)."""
    g, r, b = (v >> 8) & 15, (v >> 4) & 15, v & 15
    return (r * 17, g * 17, b * 17)
