#!/usr/bin/env python3
"""Windows ddswin/fc concatenated BMPs -> PC-98 gfx folder layout as indexed PNGs.

Output: work/gfx_win/FCxxxx/<entry>_<frame>.png  (17-colour P mode, index 16 transparent)

Background CGs: Windows often draws the scene inside a metal-tile monitor
(368x200 plus a black bezel). PC-98 stored only that inner window at x,y,w,h.
Strip the Win surround, keep aspect, and cover the plate into the PC-98 frame.
Dummy 8x8 pads stay dummy; leftover Win frames get new names.
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WIN_FC = ROOT / "inputs" / "ddswin" / "fc"
GFX = ROOT / "gfx"
GFX_ORIG = ROOT / "gfx_orig"  # unpack from DDS98, not the censored gfx/
OUT = ROOT / "gfx_win"
TRANSPARENT = 16
ORPHAN_FC = {
    "fc3700": "FC3702",
    "fc3710": "FC3712",
    "fc40fd": "FC40FF",
}


def pc98_rgb(v):
    g, r, b = (v >> 8) & 15, (v >> 4) & 15, v & 15
    return (r * 17, g * 17, b * 17)


def pal_flat(words):
    """17 RGB triples + pad to 256: colours 0-15 from 0x0GRB words, 16 = magenta."""
    flat = []
    for w in words[:16]:
        v = int(w, 16) if isinstance(w, str) else int(w)
        flat.extend(pc98_rgb(v))
    while len(flat) < 48:
        flat.extend([0, 0, 0])
    flat.extend([255, 0, 255])
    flat.extend([0, 0, 0] * (256 - 17))
    return flat


def parse_bmps(data: bytes):
    pos = 0
    n = 0
    out = []
    while pos + 30 <= len(data) and n < 64:
        if data[pos:pos + 2] != b"BM":
            nxt = data.find(b"BM", pos + 1)
            if nxt < 0:
                break
            pos = nxt
            if pos + 30 > len(data):
                break
        bf_size = struct.unpack_from("<I", data, pos + 2)[0]
        offbits = struct.unpack_from("<I", data, pos + 10)[0]
        w = struct.unpack_from("<i", data, pos + 18)[0]
        h = abs(struct.unpack_from("<i", data, pos + 22)[0])
        bpp = struct.unpack_from("<H", data, pos + 28)[0]
        if bf_size < 54 or pos + bf_size > len(data):
            row = ((abs(w) * bpp + 31) // 32) * 4
            guess = offbits + row * h
            if guess >= 54 and pos + guess <= len(data):
                bf_size = guess
            else:
                break
        chunk = data[pos:pos + bf_size]
        try:
            im = Image.open(io.BytesIO(chunk))
            im.load()
        except Exception:
            break
        out.append(im)
        pos += bf_size
        n += 1
    return out


# Battle/NPC sprites sit on a 256x256 (or 512x256) canvas at one world scale.
# PC-98 only changes zoom: entry 02 = 1:1 with that canvas (the 175 demons whose Windows picture is
# the PC-98 drawing lie on their canvases pixel for pixel), and entries 04/06 are entry 02 shrunk
# about its anchor - the PC-98's own pictures of those demons lie best on the canvas shrunk to 158
# and 115 pixels. Never fit-to-frame — that makes every crop a different scale.
ZOOM_SCALE_256 = {0: 1.0, 1: 1.0, 2: 1.0, 4: 158 / 256, 6: 115 / 256, 8: 0.4}


def _pixlist(im: Image.Image):
    if hasattr(im, "get_flattened_data"):
        return list(im.get_flattened_data())
    return list(im.getdata())


def is_key_rgb(c):
    r, g, b = c[:3]
    return (r + g + b) <= 24 or (r >= 248 and b >= 248 and g <= 12)


def bg_index(im: Image.Image):
    """Palette index of the transparent canvas (corners), or None."""
    w, h = im.size
    corners = [
        im.getpixel((0, 0)),
        im.getpixel((w - 1, 0)),
        im.getpixel((0, h - 1)),
        im.getpixel((w - 1, h - 1)),
    ]
    if im.mode == "P":
        idx, n = Counter(corners).most_common(1)[0]
        if n < 3:
            return None
        pal = im.getpalette() or []
        rgb = tuple(pal[idx * 3:idx * 3 + 3] or (0, 0, 0))
        return idx if is_key_rgb(rgb) else None
    rgb, n = Counter(corners).most_common(1)[0]
    if n < 3 or not is_key_rgb(rgb):
        return None
    return rgb


def sprite_rgba(im: Image.Image):
    """Chroma-key every pixel of the canvas colour (not 'any dark pixel').

    Windows BMPs use a black palette slot (often index 1, not 0) for the
    background *and* for holes inside a pose. Dark fur/legs use other slots.
    """
    w, h = im.size
    key = bg_index(im)
    if key is None:
        return im.convert("RGB"), False
    if im.mode == "P":
        pal = im.getpalette() or [0] * 768
        src = _pixlist(im)
        out = []
        for i in src:
            if i == key:
                out.append((0, 0, 0, 0))
            else:
                r, g, b = pal[i * 3:i * 3 + 3]
                out.append((r, g, b, 255))
        rgba = Image.new("RGBA", (w, h))
        rgba.putdata(out)
        return rgba, True
    src = im.convert("RGB")
    pix = _pixlist(src)
    out = []
    kr, kg, kb = key[:3]
    for i in range(0, len(pix), 3):
        r, g, b = pix[i], pix[i + 1], pix[i + 2]
        if r == kr and g == kg and b == kb:
            out.append((0, 0, 0, 0))
        else:
            out.append((r, g, b, 255))
    rgba = Image.new("RGBA", (w, h))
    rgba.putdata(out)
    return rgba, True


def crop_alpha(rgba: Image.Image):
    a = rgba.split()[-1]
    box = a.getbbox()
    if not box:
        return rgba
    return rgba.crop(box)


def zoom_scale(src_size, png, entry):
    sw, sh = src_size
    if sw >= 496 or sh >= 380:
        return None
    if (sw, sh) == (288, 200) or max(sw, sh) <= 64:
        return 1.0
    e = entry
    m = re.match(r"(\d{2})_", png or "")
    if m:
        e = int(m.group(1))
    if sw in (256, 512) and sh in (200, 256):
        return ZOOM_SCALE_256.get(e, 1.0)
    return 1.0


def _resize_rgba(rgba: Image.Image, nw, nh, resample):
    rgba = rgba.resize((nw, nh), resample)
    r, g, b, a = rgba.split()
    a = a.point(lambda v: 255 if v >= 128 else 0)
    return Image.merge("RGBA", (r, g, b, a))


def place_sprite(rgba: Image.Image, tw, th, scale):
    """Uniform scale, then pad. Bottom-centre (feet stay on the ground).

    The zoom is the battle camera (entry 02 = 1:1 with the Windows canvas). If that
    still does not fit the PC-98 frame, shrink further so the whole creature stays
    inside — cropping a keyed sprite cuts it off. The demons tools/winfit.py converts
    do not come through here: their frames take the size of the canvas instead.
    """
    sw, sh = rgba.size
    if sw <= 0 or sh <= 0:
        return Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    if scale is None:
        scale = 1.0
    if abs(scale - 1.0) > 1e-6:
        rgba = _resize_rgba(rgba, max(1, int(round(sw * scale))),
                            max(1, int(round(sh * scale))), Image.Resampling.BOX)
        sw, sh = rgba.size
    if sw > tw or sh > th:
        fit = min(tw / sw, th / sh)
        rgba = _resize_rgba(rgba, max(1, int(round(sw * fit))),
                            max(1, int(round(sh * fit))), Image.Resampling.LANCZOS)
        sw, sh = rgba.size
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(rgba, ((tw - sw) // 2, th - sh), rgba)
    return canvas


SCREEN = (640, 400)


def snap_ch(v):
    """8-bit channel -> PC-98 4-bit DAC (0, 17, 34, ..., 255)."""
    n = int(round(v / 17.0))
    return max(0, min(15, n)) * 17


def align8(n):
    return max(8, (int(n) + 7) // 8 * 8)


def is_fullscreen(im: Image.Image):
    w, h = im.size
    return w >= 600 and h >= 348


def is_dummy_bmp(im: Image.Image):
    """8x8 pads and 256x256 'DUMMY' plates inside some CG bins."""
    w, h = im.size
    if w * h <= 64:
        return True
    if (w, h) != (256, 256):
        return False
    return len(set(_pixlist(im))) <= 4


def rgb_to_grb_word(r, g, b):
    R = max(0, min(15, int(round(r / 17.0))))
    G = max(0, min(15, int(round(g / 17.0))))
    B = max(0, min(15, int(round(b / 17.0))))
    return f"{(G << 8) | (R << 4) | B:04X}"


def pal_words_from_png(im: Image.Image):
    pal = list(im.getpalette() or [])
    words = []
    for i in range(16):
        rgb = pal[i * 3:i * 3 + 3] or [0, 0, 0]
        words.append(rgb_to_grb_word(*rgb))
    return words


def corner_luma_means(im: Image.Image):
    g = im.convert("RGB")
    w, h = g.size
    out = []
    for box in ((0, 0, 48, 48), (w - 48, 0, w, 48), (0, h - 48, 48, h), (w - 48, h - 48, w, h)):
        hist = g.crop(box).convert("L").histogram()
        tot = sum(hist) or 1
        out.append(sum(i * hist[i] for i in range(256)) / tot)
    return out


def has_tile_chrome(im: Image.Image):
    """Windows event-CG monitor: brushed-metal tiles in all four corners."""
    m = corner_luma_means(im)
    return all(70.0 <= v <= 125.0 for v in m) and (max(m) - min(m)) < 25.0


def border_black_score(im: Image.Image, outer, bar=8, thr=24):
    g = im.convert("L")
    px = g.load()
    x0, y0, x1, y1 = outer
    w, h = g.size
    k = n = 0

    def acc(x, y):
        nonlocal k, n
        if 0 <= x < w and 0 <= y < h:
            n += 1
            if px[x, y] <= thr:
                k += 1

    for y in range(y0, y0 + bar):
        for x in range(x0, x1):
            acc(x, y)
    for y in range(y1 - bar, y1):
        for x in range(x0, x1):
            acc(x, y)
    for y in range(y0 + bar, y1 - bar):
        for x in range(x0, x0 + bar):
            acc(x, y)
        for x in range(x1 - bar, x1):
            acc(x, y)
    return (k / n) if n else 0.0


def find_tile_inner(im: Image.Image):
    """Inner 368x200 of the Win metal-tile + black bezel monitor, or None."""
    w, h = im.size
    if w < 512 or h < 304 or not has_tile_chrome(im):
        return None
    bar = 8
    ow, oh = 384, 216
    best = None
    best_sc = 0.0
    y_first = 88 if h >= 304 else 0
    ys = [y_first] + [y for y in range(0, min(h - oh + 1, 161), 8) if y != y_first]
    for y0 in ys:
        outer = (128, y0, 128 + ow, y0 + oh)
        sc = border_black_score(im, outer, bar=bar)
        if sc > best_sc:
            best_sc = sc
            best = y0
        if sc >= 0.98:
            break
    if best is None or best_sc < 0.85:
        return None
    return (128 + bar, best + bar, 128 + ow - bar, best + oh - bar)


def nonblack_bbox(im: Image.Image, thr=18):
    mask = im.convert("L").point(lambda v: 255 if v > thr else 0)
    return mask.getbbox()


def extract_cg_plate(im: Image.Image):
    """Scene pixels only: drop Win tile chrome / empty black pad when present."""
    rgb = im.convert("RGB")
    box = find_tile_inner(im)
    if box:
        return rgb.crop(box)
    m = corner_luma_means(im)
    if sum(m) / 4.0 <= 18.0:
        bb = nonblack_bbox(im)
        if bb:
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            area = rgb.size[0] * rgb.size[1]
            if bw >= 80 and bh >= 60 and bw * bh <= int(0.85 * area):
                return rgb.crop(bb)
    return rgb


def is_picture_dest(w, h):
    return min(w, h) >= 120 and w * h >= 19200


def dest_canvas(inner_size, tw, th):
    """PNG canvas must equal the PC-98 dest so gfx.py can pack the frame."""
    if tw > 0 and th > 0:
        return tw, th
    iw, ih = inner_size
    return align8(iw), align8(ih)


def contain_rgba(im: Image.Image, tw, th):
    rgb = im.convert("RGB")
    sw, sh = rgb.size
    scale = min(tw / sw, th / sh)
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    if (nw, nh) != (sw, sh):
        rgb = rgb.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(rgb, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


def cover_rgba(im: Image.Image, tw, th):
    """Fill dest, keep aspect, center-crop. Magenta/alpha stays keyed."""
    src = im.convert("RGBA")
    arr = np.asarray(src)
    rgb, al = arr[..., :3].astype(np.int16), arr[..., 3]
    mag = (al < 128) | ((rgb[..., 0] >= 250) & (rgb[..., 2] >= 250) & (rgb[..., 1] <= 8))
    if mag.any():
        arr = arr.copy()
        arr[..., 3] = np.where(mag, 0, arr[..., 3])
        src = Image.fromarray(arr)
    sw, sh = src.size
    if sw <= 0 or sh <= 0:
        return Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    scale = max(tw / max(sw, 1), th / max(sh, 1))
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    if (nw, nh) != (sw, sh):
        src = src.resize((nw, nh), Image.Resampling.LANCZOS)
        r, g, b, a = src.split()
        a = a.point(lambda v: 255 if v >= 128 else 0)
        src = Image.merge("RGBA", (r, g, b, a))
        sw, sh = nw, nh
    left = max(0, (sw - tw) // 2)
    top = max(0, (sh - th) // 2)
    src = src.crop((left, top, left + min(sw, tw), top + min(sh, th)))
    if src.size == (tw, th):
        return src
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(src, ((tw - src.size[0]) // 2, (th - src.size[1]) // 2), src)
    return canvas


def crop_keyed_letterbox(im: Image.Image):
    """Trim chroma-key magenta and solid empty bars; keep dark scene pixels."""
    rgba = im.convert("RGBA")
    arr = np.asarray(rgba)
    rgb = arr[..., :3].astype(np.int16)
    al = arr[..., 3]
    mag = (al < 128) | ((rgb[..., 0] >= 250) & (rgb[..., 2] >= 250) & (rgb[..., 1] <= 8))
    dark = rgb.sum(axis=2) <= 18
    h, w = mag.shape
    has_color = int(((~mag) & (~dark)).sum()) > 80

    def col_blank(x):
        sl = mag[:, x]
        if float(sl.mean()) >= 0.98:
            return True
        return has_color and float((sl | dark[:, x]).mean()) >= 0.98

    def row_blank(y):
        sl = mag[y, :]
        if float(sl.mean()) >= 0.98:
            return True
        return has_color and float((sl | dark[y, :]).mean()) >= 0.98

    x0 = 0
    while x0 < w - 8 and col_blank(x0):
        x0 += 1
    x1 = w
    while x1 > x0 + 8 and col_blank(x1 - 1):
        x1 -= 1
    y0 = 0
    while y0 < h - 8 and row_blank(y0):
        y0 += 1
    y1 = h
    while y1 > y0 + 8 and row_blank(y1 - 1):
        y1 -= 1
    if x0 == 0 and y0 == 0 and x1 == w and y1 == h:
        return rgba
    return rgba.crop((x0, y0, x1, y1))


def crop_screen_strip(im: Image.Image, tw, th, x, y):
    """Take a dest-sized strip out of a 640x400 (or 640x480) screen dump."""
    rgb = im.convert("RGB")
    if rgb.size != SCREEN and rgb.size[0] >= 600 and rgb.size[1] >= 348:
        rgb = to_screen_640x400(rgb)
    x = max(0, int(x))
    y = max(0, int(y))
    if rgb.size[0] >= x + tw and rgb.size[1] >= y + th:
        return rgb.crop((x, y, x + tw, y + th))
    return cover_rgba(rgb, tw, th).convert("RGB")


_FRAME_CACHE: dict[str, dict] = {}


def orig_frames(fc: str) -> dict:
    """png name -> frame dict (x,y,w,h,png) plus entry, from gfx_orig then gfx."""
    if fc in _FRAME_CACHE:
        return _FRAME_CACHE[fc]
    out = {}
    for root in (GFX_ORIG, GFX):
        p = root / fc / "manifest.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for e in data.get("entries") or []:
            for fr in e.get("frames") or []:
                name = fr.get("png")
                if name and name not in out:
                    out[name] = {**fr, "entry": e.get("entry")}
        break
    _FRAME_CACHE[fc] = out
    return out


def save_indexed(path: Path, im: Image.Image):
    if im.mode != "P":
        im = quantize_rgba(im, 16) if im.mode == "RGBA" else quantize_pc98_depth(im.convert("RGB"), 16)
    im.save(path, transparency=TRANSPARENT)


def to_screen_640x400(im: Image.Image):
    """Uniform scale (no stretch) to fill 640x400, center-crop if needed."""
    rgb = im.convert("RGB")
    sw, sh = rgb.size
    tw, th = SCREEN
    if (sw, sh) == (tw, th):
        return rgb
    scale = max(tw / sw, th / sh)
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    if (nw, nh) != (sw, sh):
        rgb = rgb.resize((nw, nh), Image.Resampling.LANCZOS)
        sw, sh = nw, nh
    if sw < tw or sh < th:
        canvas = Image.new("RGB", (tw, th), (0, 0, 0))
        canvas.paste(rgb, ((tw - sw) // 2, (th - sh) // 2))
        return canvas
    left = (sw - tw) // 2
    top = (sh - th) // 2
    return rgb.crop((left, top, left + tw, top + th))


def quantize_pc98_depth(im: Image.Image, ncolors=16):
    """16 colours on the PC-98 4-bit GRB lattice, taken from the source (not the old FC palette)."""
    rgb = im.convert("RGB")
    lut = [snap_ch(i) for i in range(256)]
    r, g, b = rgb.split()
    lattice = Image.merge("RGB", (r.point(lut), g.point(lut), b.point(lut)))
    q = lattice.quantize(colors=ncolors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = list(q.getpalette()[: ncolors * 3] or [])
    while len(pal) < ncolors * 3:
        pal.extend([0, 0, 0])
    for i in range(ncolors):
        pal[i * 3] = snap_ch(pal[i * 3])
        pal[i * 3 + 1] = snap_ch(pal[i * 3 + 1])
        pal[i * 3 + 2] = snap_ch(pal[i * 3 + 2])
    pal.extend([255, 0, 255])
    pal.extend([0, 0, 0] * (256 - ncolors - 1))
    pix = _pixlist(q)
    pix = [min(ncolors - 1, int(p)) for p in pix]
    out = Image.new("P", q.size)
    out.putpalette(pal)
    out.putdata(pix)
    return out


def quantize_rgba(rgba: Image.Image, ncolors=16):
    rgb = Image.new("RGB", rgba.size, (0, 0, 0))
    alpha = rgba.split()[-1]
    rgb.paste(rgba.convert("RGB"), mask=alpha)
    q = quantize_pc98_depth(rgb, ncolors)
    pix = bytearray(q.tobytes())
    for i, a in enumerate(alpha.tobytes()):
        if a < 128:
            pix[i] = TRANSPARENT
    pal = list(q.getpalette() or [0] * 768)
    while len(pal) < 768:
        pal.append(0)
    pal[48:51] = [255, 0, 255]
    out = Image.new("P", q.size)
    out.putpalette(pal)
    out.putdata(list(pix))
    return out


def fit_cg(rgb: Image.Image, tw, th):
    """Deprecated stretch path — kept only as a name; callers should not squash."""
    return contain_rgb(rgb, tw, th)


def contain_rgb(rgb: Image.Image, tw, th):
    rgb = rgb.convert("RGB")
    sw, sh = rgb.size
    if (sw, sh) == (tw, th):
        return rgb
    scale = min(tw / sw, th / sh)
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    if (nw, nh) != (sw, sh):
        rgb = rgb.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (tw, th), (0, 0, 0))
    canvas.paste(rgb, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


def unique_first(frames):
    seen = []
    used = set()
    for i, f in enumerate(frames):
        if f["png"] in used:
            continue
        used.add(f["png"])
        seen.append((i, f))
    return seen


def assign_bmps(n_bmps, frames):
    """(bmp_index, frame_dict) for unique real frames."""
    out = []
    for i, f in unique_first(frames):
        tiny = f["w"] * f["h"] <= 64
        if i < n_bmps:
            src_i = i
        elif n_bmps == 1 and not tiny:
            src_i = 0
        else:
            continue
        if tiny and n_bmps and i < n_bmps:
            # still skip 8x8 if the matching BMP is a full sprite canvas
            continue
        if tiny:
            continue
        out.append((src_i, f))
    if n_bmps == 1 and not out:
        reals = [(i, f) for i, f in unique_first(frames) if f["w"] * f["h"] > 64]
        if reals:
            out.append((0, max(reals, key=lambda t: t[1]["w"] * t[1]["h"])[1]))
    return out


def load_man(fc):
    p = GFX / fc / "manifest.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def pal_of(entry):
    pals = entry.get("palettes") or []
    if pals:
        return pals[0]
    return [
        "0000", "0CFA", "07C4", "02B1", "0FFF", "05F4", "0C35", "0AD1",
        "0000", "0BAC", "084C", "0652", "0AAB", "0AAB", "0008", "0DDD",
    ]


class Catalog:
    def __init__(self):
        self.win = {p.stem.lower(): p for p in WIN_FC.glob("*.bin")}
        self.gfx = {p.name for p in GFX.iterdir() if p.is_dir() and re.fullmatch(r"FC[0-9A-F]{4}", p.name)}

    def exists_win(self, stem):
        return stem.lower() in self.win

    def exists_gfx(self, fc):
        return fc in self.gfx

    def entry_siblings(self, hex4):
        prefix = hex4[:3]
        base = "FC" + prefix.upper() + "0"
        if not self.exists_gfx(base):
            return 0
        n = 0
        for d in "0123456789abcdef":
            stem = "fc" + prefix + d
            if not self.exists_win(stem):
                continue
            other = "FC" + prefix.upper() + d.upper()
            if d != hex4[3] and self.exists_gfx(other) and other != base:
                continue
            n += 1
        return n


def resolve(stem: str, cat: Catalog):
    """('demon', fc, pal) | ('whole', fc) | ('entry', fc, entry) | ('fch', fc, entry) | None"""
    s = stem.lower()
    m5 = re.fullmatch(r"fc([0-9a-f]{3})2([0-9a-f])", s)
    if m5:
        fc = "FC" + m5.group(1).upper() + "0"
        pal = int(m5.group(2), 16)
        if cat.exists_gfx(fc):
            return ("demon", fc, pal)
        return None
    mh = re.fullmatch(r"fch7e([0-9a-f]{2})", s)
    if mh:
        fc = "FC7E" + mh.group(1)[0].upper() + "0"
        entry = int(mh.group(1)[1], 16)
        if cat.exists_gfx(fc):
            return ("fch", fc, entry)
        return None
    m4 = re.fullmatch(r"fc([0-9a-f]{4})", s)
    if not m4:
        return None
    hex4 = m4.group(1)
    exact = "FC" + hex4.upper()
    base = "FC" + hex4[:3].upper() + "0"
    entry = int(hex4[3], 16)
    if s in ORPHAN_FC:
        return ("whole", ORPHAN_FC[s])
    has_exact = cat.exists_gfx(exact)
    has_base = cat.exists_gfx(base)
    if has_exact and exact != base:
        return ("whole", exact)
    if has_exact and exact == base:
        if cat.entry_siblings(hex4) > 1:
            return ("entry", base, entry)
        return ("whole", exact)
    if has_base:
        return ("entry", base, entry)
    return None


def jobs_for_file(path: Path, kind, cat: Catalog):
    """List of dicts: fc, png, tw, th, pal, bmp_index, score, entry, mode."""
    man_fc = kind[1]
    man = load_man(man_fc)
    if not man:
        return []
    data = path.read_bytes()
    bmps = parse_bmps(data)
    if not bmps:
        return []
    n = len(bmps)
    jobs = []
    tag = kind[0]
    full_ix = [i for i, b in enumerate(bmps) if is_fullscreen(b) and not is_dummy_bmp(b)]

    def add(entry_obj, src_i, fr, score, mode="sprite"):
        if src_i >= n or src_i in full_ix:
            return
        if is_dummy_bmp(bmps[src_i]):
            return
        jobs.append({
            "fc": man_fc,
            "png": fr["png"],
            "tw": fr["w"],
            "th": fr["h"],
            "pal": pal_of(entry_obj),
            "bmp_index": src_i,
            "score": score,
            "path": str(path),
            "entry": entry_obj["entry"],
            "mode": mode,
        })

    # Windows CGs: pair plates to PC-98 *picture* slots (not overlay strips).
    # Tile-chrome scenes are cropped to the inner monitor before fitting.
    if full_ix:
        if tag in ("entry", "fch"):
            e_n = kind[2]
            e_obj = next((x for x in man["entries"] if x["entry"] == e_n), man["entries"][0])
            owned = [(e_obj, fr) for fr in e_obj["frames"]]
        elif tag == "demon":
            e_n = 2
            e_obj = next((x for x in man["entries"] if x["entry"] == e_n), man["entries"][0])
            owned = [(e_obj, fr) for fr in e_obj["frames"]]
        else:
            e_n = 0
            e_obj = man["entries"][0]
            owned = []
            for e in man["entries"]:
                for fr in e["frames"]:
                    owned.append((e, fr))
        dests = []
        seen = set()
        taken = set()
        for e, fr in owned:
            if fr["png"] in seen:
                continue
            seen.add(fr["png"])
            if fr["w"] * fr["h"] <= 64:
                taken.add(fr["png"])
                continue
            dests.append((e, fr))
        srcs = [i for i in range(n) if not is_dummy_bmp(bmps[i])]
        for src_i, (e, fr) in zip(srcs, dests):
            mode = "cg" if is_fullscreen(bmps[src_i]) else "native"
            jobs.append({
                "fc": man_fc,
                "png": fr["png"],
                "tw": fr["w"],
                "th": fr["h"],
                "pal": pal_of(e),
                "bmp_index": src_i,
                "score": 80 if mode == "cg" else 70,
                "path": str(path),
                "entry": e["entry"],
                "mode": mode,
            })
            taken.add(fr["png"])
        extra = srcs[len(dests):]
        kslot = 0

        def next_name(entry_n):
            nonlocal kslot
            while True:
                name = f"{entry_n:02d}_{kslot:03d}.png"
                kslot += 1
                if name not in taken:
                    return name

        for src_i in extra:
            name = next_name(e_n)
            taken.add(name)
            mode = "cg" if is_fullscreen(bmps[src_i]) else "native"
            sw, sh = bmps[src_i].size
            jobs.append({
                "fc": man_fc,
                "png": name,
                "tw": SCREEN[0] if mode == "cg" else align8(sw),
                "th": SCREEN[1] if mode == "cg" else align8(sh),
                "pal": pal_of(e_obj),
                "bmp_index": src_i,
                "score": 75,
                "path": str(path),
                "entry": e_n,
                "mode": mode,
            })
        return jobs

    if tag == "demon":
        pal_i = kind[2]
        if pal_i != 0:
            return []
        by_e = {e["entry"]: e for e in man["entries"]}
        e2 = by_e.get(2)
        if not e2 or not e2["frames"]:
            return []
        assigned = assign_bmps(n, e2["frames"])
        for src_i, fr in assigned:
            add(e2, src_i, fr, score=50 + n)
            fi = next(i for i, f in enumerate(e2["frames"]) if f["png"] == fr["png"])
            for ek in (4, 6, 0, 8):
                e = by_e.get(ek)
                if not e or not e["frames"]:
                    continue
                if fi >= len(e["frames"]):
                    continue
                fr2 = e["frames"][fi]
                if fr2["w"] * fr2["h"] <= 64:
                    continue
                add(e, src_i, fr2, score=40)
    elif tag in ("entry", "fch"):
        entry_n = kind[2]
        e = next((x for x in man["entries"] if x["entry"] == entry_n), None)
        if e:
            score = 90 if tag == "fch" else 60
            for src_i, fr in assign_bmps(n, e["frames"]):
                add(e, src_i, fr, score)
    else:
        concat = []
        for e in man["entries"]:
            for fr in e["frames"]:
                concat.append((e, fr))
        used = set()
        owners = []
        for i, (e, fr) in enumerate(concat):
            if fr["png"] in used:
                continue
            used.add(fr["png"])
            owners.append(e)
        frames_as_list = [fr for _e, fr in concat]
        for src_i, fr in assign_bmps(n, frames_as_list):
            e = next(x for x in owners if fr["png"] in {f["png"] for f in x["frames"]})
            add(e, src_i, fr, score=55)
    return jobs


def convert_one(bmp: Image.Image, tw, th, pal, png="", entry=2, mode="auto"):
    if mode == "cg" or is_fullscreen(bmp):
        plate = extract_cg_plate(bmp)
        # Full-screen Win dump of a 640x136 overlay: cut the blit strip.
        if (tw, th) == (640, 136):
            rgb = plate.convert("RGB")
            if rgb.size[0] >= 600 and rgb.size[1] >= 348:
                rgb = to_screen_640x400(rgb)
            if rgb.size[0] >= 640 and rgb.size[1] >= 272:
                return quantize_pc98_depth(rgb.crop((0, 136, 640, 272)), 16)
        # Tiny dest (copyright bar) must not squash a title card.
        if tw * th < 640 * 136 and is_fullscreen(bmp) and (tw, th) != (640, 136):
            return quantize_pc98_depth(to_screen_640x400(plate), 16)
        if tw >= 600 and th >= 348:
            return quantize_pc98_depth(to_screen_640x400(plate), 16)
        return quantize_rgba(cover_rgba(crop_keyed_letterbox(plate), tw, th), 16)
    rgba, keyed = sprite_rgba(bmp)
    if keyed:
        # Battle sprites, even ones whose PC-98 frame is as large as a CG plate
        # (FC2820's fog is 192x136). Cover-cropping that frame chops the creature.
        rgba = crop_alpha(rgba)
        scale = 1.0 if mode == "native" else zoom_scale(bmp.size, png, entry)
        fitted = place_sprite(rgba, tw, th, scale if scale is not None else 1.0)
        return quantize_rgba(fitted, 16)
    if is_picture_dest(tw, th):
        src = extract_cg_plate(bmp)
        return quantize_rgba(cover_rgba(crop_keyed_letterbox(src), tw, th), 16)
    rgb = bmp.convert("RGB")
    if mode == "native" or rgb.size == (tw, th):
        if rgb.size != (tw, th):
            canvas = Image.new("RGB", (tw, th), (0, 0, 0))
            canvas.paste(rgb, ((tw - rgb.size[0]) // 2, (th - rgb.size[1]) // 2))
            rgb = canvas
        return quantize_pc98_depth(rgb, 16)
    return quantize_pc98_depth(contain_rgb(rgb, tw, th), 16)


def rewrite_cg_manifest(fc, jobs, dest_dir: Path):
    """Keep PC-98 blit x,y when the PNG still matches; fix w,h if the plate size changed."""
    src_m = GFX / fc / "manifest.json"
    if src_m.exists():
        man = json.loads(src_m.read_text(encoding="utf-8"))
    else:
        man = {"file": fc + ".BIN", "entries": []}
    if not any(j.get("mode") in ("cg", "native") for j in jobs):
        return False
    written = {p.name: p for p in dest_dir.glob("*.png")}
    jobs_by_e = defaultdict(list)
    for j in jobs:
        jobs_by_e[j["entry"]].append(j)
    existing = {e["entry"]: e for e in man["entries"]}
    for eid, js in jobs_by_e.items():
        e = existing.get(eid)
        if e is None:
            e = {
                "entry": eid,
                "palettes": [],
                "palette_head": "0024",
                "palette_mask": "FFFF",
                "sets_colours": list(range(16)),
                "remap": True,
                "derived_plane": False,
                "layout_head": 0,
                "frames": [],
            }
            man["entries"].append(e)
            existing[eid] = e
        orig = {fr["png"]: fr for fr in e.get("frames") or []}
        new_frames = []
        used = set()
        for j in sorted(js, key=lambda t: t["png"]):
            p = written.get(j["png"])
            if not p:
                continue
            im = Image.open(p)
            w, h = im.size
            old = orig.get(j["png"])
            if old:
                x, y = old["x"], old["y"]
                if abs(w - old["w"]) > 8 or abs(h - old["h"]) > 8:
                    if w >= 600 and h >= 348:
                        x, y = 0, 0
                    else:
                        x = old["x"] + old["w"] // 2 - w // 2
                        y = old["y"] + old["h"] // 2 - h // 2
            else:
                x, y = 0, 0
            new_frames.append({"x": x, "y": y, "w": w, "h": h, "png": j["png"]})
            used.add(j["png"])
        e["frames"] = new_frames
        if new_frames:
            e["palettes"] = [pal_words_from_png(Image.open(dest_dir / new_frames[0]["png"]))]
        e["sets_colours"] = list(range(16))
        e["palette_mask"] = "FFFF"
        e["remap"] = True
    (dest_dir / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    return True


def main():
    cat = Catalog()
    print(f"win bins {len(cat.win)}  gfx FCs {len(cat.gfx)}")
    grouped = defaultdict(list)  # path -> jobs before dedupe
    n_files = 0
    for stem, path in sorted(cat.win.items()):
        kind = resolve(stem, cat)
        if not kind:
            continue
        js = jobs_for_file(path, kind, cat)
        if not js:
            continue
        grouped[str(path)].extend(js)
        n_files += 1

    best = {}
    for js in grouped.values():
        for j in js:
            key = (j["fc"], j["png"])
            old = best.get(key)
            if old is None or j["score"] > old["score"]:
                best[key] = j
    print(f"source files used {n_files}, unique PNG targets {len(best)}")

    by_path = defaultdict(list)
    for j in best.values():
        by_path[j["path"]].append(j)

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    copied_man = set()
    wrote_names = defaultdict(set)
    jobs_by_fc = defaultdict(list)
    errors = []
    for pi, (pstr, js) in enumerate(sorted(by_path.items()), 1):
        try:
            bmps = parse_bmps(Path(pstr).read_bytes())
        except Exception as e:
            errors.append((pstr, str(e)))
            continue
        for j in js:
            if drop_win_swap(j["fc"], j["png"]):
                continue
            if j["bmp_index"] >= len(bmps):
                errors.append((j["fc"], j["png"], "bmp_index"))
                continue
            try:
                im = convert_one(bmps[j["bmp_index"]], j["tw"], j["th"], j["pal"],
                                 j.get("png", ""), j.get("entry", 2), j.get("mode", "auto"))
            except Exception as e:
                errors.append((j["fc"], j["png"], str(e)))
                continue
            dest_dir = OUT / j["fc"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / j["png"]
            im.save(dest, transparency=TRANSPARENT)
            written += 1
            wrote_names[j["fc"]].add(j["png"])
            jobs_by_fc[j["fc"]].append(j)
            if j["fc"] not in copied_man:
                src_m = GFX / j["fc"] / "manifest.json"
                if src_m.exists():
                    shutil.copy2(src_m, dest_dir / "manifest.json")
                copied_man.add(j["fc"])
        if pi % 25 == 0 or pi == len(by_path):
            print(f"  {pi}/{len(by_path)} files, {written} pngs")

    n_stale = 0
    n_cg_man = 0
    for fc, names in wrote_names.items():
        dest_dir = OUT / fc
        for p in dest_dir.glob("*.png"):
            if p.name not in names:
                p.unlink()
                n_stale += 1
        if rewrite_cg_manifest(fc, jobs_by_fc[fc], dest_dir):
            n_cg_man += 1

    report = {
        "out": str(OUT),
        "source_files": n_files,
        "pngs": written,
        "folders": len(copied_man),
        "cg_manifests": n_cg_man,
        "stale_removed": n_stale,
        "errors": errors[:50],
        "n_errors": len(errors),
    }
    (OUT / "_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {written} PNGs in {len(copied_man)} FC folders -> {OUT}")
    print(f"rewrote {n_cg_man} CG manifests, removed {n_stale} leftover overlay PNGs")
    if errors:
        print(f"{len(errors)} errors, first: {errors[:5]}")
    filt = filter_similar_sprites()
    report["sprite_filter"] = filt
    (OUT / "_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def gold_dir(fc: str) -> Path | None:
    """PC-98 original art for similarity. Never compare against censored gfx/."""
    for root in (GFX_ORIG, GFX):
        d = root / fc
        if d.exists():
            return d
    return None


def sprite_kind(fc: str):
    """demon / char / skill / cg, else None (UI — always kept)."""
    if not re.fullmatch(r"FC[0-9A-F]{4}", fc):
        return None
    n = int(fc[2:], 16)
    if 0x2000 <= n < 0x3000 or n in (0x3702, 0x3712):
        return "demon"
    if 0x7E00 <= n < 0x7EFF:
        return "char"
    if 0x4000 <= n <= 0x40FF:
        return "char"
    if 0x6000 <= n < 0x7000:
        return "skill"
    if 0x3000 <= n < 0x3700 or 0x5000 <= n < 0x6000:
        return "cg"
    return None


def drop_win_swap(fc: str, name: str) -> bool:
    """Do not replace these PC-98 plates with Windows dumps.

    Ending title/credits/CGs are the same shots. PC-98 stores magenta-keyed
    layers (title text, body-without-head, corpse hole, wings, angels);
    Windows already flattened the composite into one BMP. Game Over /
    Continue and the FC5050 pie-slice event CG have the same split.
    FC40xx overworld NPCs are the same characters; Win only changes AA and
    in-box scale, or dumps a full scene onto a keyed overlay slot.
    """
    if not re.fullmatch(r"FC[0-9A-F]{4}", fc):
        return False
    n = int(fc[2:], 16)
    if n == 0x40FF:
        return True
    # Title copyright is a 160x64 keyed overlay; Win fc50f6.bin is a baked title card.
    if n == 0x50F0:
        try:
            ent = int(name[:2])
        except ValueError:
            return False
        return ent == 6
    if 0x5070 <= n <= 0x50C0:
        # entry 0 of FC5090 is no ending picture but a room: シャンシャンシティ 10F and 上野神殿
        return (fc, name) not in REDRAWN
    if n in (0x50D0, 0x50E0):
        return True
    if n == 0x5050:
        try:
            ent = int(name[:2])
        except ValueError:
            return False
        return ent in (14, 15)
    if fc == "FC5060":
        try:
            ent = int(name[:2])
        except ValueError:
            return False
        # same event CGs, painted vs dither; keep map/tower/U-PLAN plates
        return ent in (3, 4, 5, 7, 8, 9, 10, 11, 13, 14)
    # Overworld NPCs / object overlays: same drawing as PC-98, or a flattened
    # Windows composite stuffed into a magenta-keyed layer slot.
    if 0x4000 <= n < 0x40FF:
        g = gold_dir(fc)
        if g is not None:
            gp = g / name
            if gp.exists():
                try:
                    with Image.open(gp) as gim:
                        return is_pc98_char_overlay(gim)
                except OSError:
                    return False
    return False


def is_portrait_scrap(fc: str, win_im: Image.Image) -> bool:
    """fch portrait bins received leftover overlay scraps (white bar, vine)."""
    if not re.fullmatch(r"FC[0-9A-F]{4}", fc):
        return False
    if not (0x7E00 <= int(fc[2:], 16) < 0x7EFF):
        return False
    arr = np.asarray(png_rgba(win_im))
    rgb, al = arr[..., :3].astype(np.int16), arr[..., 3]
    keep = al >= 128
    keep &= ~((rgb[..., 0] >= 250) & (rgb[..., 2] >= 250) & (rgb[..., 1] <= 8))
    ink = keep & (rgb.sum(axis=2) > 30)
    nink = int(ink.sum())
    pix = max(1, win_im.size[0] * win_im.size[1])
    if nink / pix < 0.08:
        return True
    ys, xs = np.where(ink)
    if not ys.size:
        return True
    bw = int(xs.max() - xs.min() + 1)
    bh = int(ys.max() - ys.min() + 1)
    return min(bw, bh) <= 24 and max(bw, bh) >= 80


def prune_manifest(d: Path):
    man = d / "manifest.json"
    if not man.exists():
        return
    present = {p.name for p in d.glob("*.png")}
    try:
        data = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for e in data.get("entries") or []:
        e["frames"] = [fr for fr in (e.get("frames") or []) if fr.get("png") in present]
    data["entries"] = [e for e in (data.get("entries") or []) if e.get("frames")]
    if not data["entries"] and not present:
        try:
            man.unlink()
        except OSError:
            pass
        return
    man.write_text(json.dumps(data, indent=1), encoding="utf-8")


def png_rgba(im: Image.Image):
    if im.mode != "P":
        return im.convert("RGBA")
    pal = im.getpalette() or [0] * 768
    tr = im.info.get("transparency", TRANSPARENT)
    out = []
    for p in _pixlist(im):
        if p == tr or p == TRANSPARENT:
            out.append((0, 0, 0, 0))
            continue
        r, g, b = pal[p * 3:p * 3 + 3] or (0, 0, 0)
        if r >= 248 and b >= 248 and g <= 12:
            out.append((0, 0, 0, 0))
        else:
            out.append((r, g, b, 255))
    rgba = Image.new("RGBA", im.size)
    rgba.putdata(out)
    return rgba


def keyed_frac(im: Image.Image) -> float:
    """Share of pixels that are transparent or chroma-key magenta."""
    arr = np.asarray(png_rgba(im))
    rgb, al = arr[..., :3].astype(np.int16), arr[..., 3]
    keyed = (al < 128) | ((rgb[..., 0] >= 250) & (rgb[..., 2] >= 250) & (rgb[..., 1] <= 8))
    return float(keyed.mean())


def is_pc98_char_overlay(im: Image.Image) -> bool:
    """PC-98 stored the character/object as a magenta-keyed overlay, not a scene."""
    if max(im.size) <= 16:
        return True
    return max(im.size) < 360 and keyed_frac(im) >= 0.18


def _hue_deg(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d < 0.06:
        return None
    if mx == r:
        h = (g - b) / d
    elif mx == g:
        h = 2.0 + (b - r) / d
    else:
        h = 4.0 + (r - g) / d
    return (h * 60.0) % 360.0


def _mean_hue_rgb(rgba: Image.Image):
    rs = gs = bs = n = 0
    s_sin = s_cos = 0.0
    nh = 0
    for r, g, b, a in rgba.getdata():
        if a < 128:
            continue
        rs += r
        gs += g
        bs += b
        n += 1
        h = _hue_deg(r, g, b)
        if h is None:
            continue
        rad = math.radians(h)
        s_sin += math.sin(rad)
        s_cos += math.cos(rad)
        nh += 1
    if not n:
        return (0.0, 0.0, 0.0), None, 0
    mean = (rs / n, gs / n, bs / n)
    hue = (math.degrees(math.atan2(s_sin, s_cos)) % 360.0) if nh else None
    return mean, hue, n


def _sil_iou(a: Image.Image, b: Image.Image, n=64):
    def mask(im):
        al = im.split()[-1].point(lambda v: 255 if v >= 128 else 0)
        box = al.getbbox()
        if not box:
            return Image.new("L", (n, n), 0)
        c = al.crop(box)
        c.thumbnail((n, n), Image.Resampling.NEAREST)
        canvas = Image.new("L", (n, n), 0)
        canvas.paste(c, ((n - c.size[0]) // 2, n - c.size[1]))
        return canvas

    p1, p2 = list(mask(a).getdata()), list(mask(b).getdata())
    inter = sum(1 for x, y in zip(p1, p2) if x > 127 and y > 127)
    union = sum(1 for x, y in zip(p1, p2) if x > 127 or y > 127)
    return (inter / union) if union else 1.0


def _prep_cmp(rgba: Image.Image, n=64, crop=True, treat_black=False):
    a = rgba.convert("RGBA")
    if crop:
        arr = np.asarray(a)
        rgb, al = arr[..., :3].astype(np.int16), arr[..., 3]
        keep = al >= 128
        keep &= ~((rgb[..., 0] >= 250) & (rgb[..., 2] >= 250) & (rgb[..., 1] <= 8))
        if treat_black:
            keep &= rgb.sum(axis=2) > 30
        ys, xs = np.where(keep)
        if ys.size:
            a = a.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    rgb = a.convert("RGB")
    rgb.thumbnail((n, n), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (n, n), (255, 0, 255))
    canvas.paste(rgb, ((n - rgb.size[0]) // 2, (n - rgb.size[1]) // 2))
    return canvas


def structure_score(pc_im: Image.Image, win_im: Image.Image, crop=True, n=64, treat_black=False):
    """Luminance correlation + mean abs diffs after bbox-normalize."""
    a = _prep_cmp(png_rgba(pc_im), n, crop, treat_black)
    b = _prep_cmp(png_rgba(win_im), n, crop, treat_black)
    ga = list(a.convert("L").getdata())
    gb = list(b.convert("L").getdata())
    k = len(ga) or 1
    ma, mb = sum(ga) / k, sum(gb) / k
    num = sum((x - ma) * (y - mb) for x, y in zip(ga, gb))
    d1 = math.sqrt(sum((x - ma) ** 2 for x in ga)) or 1.0
    d2 = math.sqrt(sum((y - mb) ** 2 for y in gb)) or 1.0
    corr = num / (d1 * d2)
    mad = sum(abs(x - y) for x, y in zip(ga, gb)) / k
    pa, pb = list(a.getdata()), list(b.getdata())
    rgbmad = sum(
        abs(x[0] - y[0]) + abs(x[1] - y[1]) + abs(x[2] - y[2]) for x, y in zip(pa, pb)
    ) / (3 * k)
    return corr, mad, rgbmad


def art_significantly_different(pc_im: Image.Image, win_im: Image.Image, kind="demon"):
    """Keep only a real redraw. Same pose/portrait with extra AA does not count."""
    b = png_rgba(win_im)
    arr = np.asarray(b)
    rgb, al = arr[..., :3].astype(np.int16), arr[..., 3]
    keep = al >= 128
    keep &= ~((rgb[..., 0] >= 250) & (rgb[..., 2] >= 250) & (rgb[..., 1] <= 8))
    ink = keep & (rgb.sum(axis=2) > 30)
    if int(ink.sum()) < 80:
        return False
    ys, xs = np.where(ink)
    content_frac = 0.0
    if ys.size:
        content_frac = (
            (int(xs.max()) - int(xs.min()) + 1)
            * (int(ys.max()) - int(ys.min()) + 1)
            / max(1, win_im.size[0] * win_im.size[1])
        )
    # Talk/scene plates fill the window; a sprite dumped on black should still crop.
    is_plate = (
        kind in ("cg", "char")
        and max(win_im.size) >= 360
        and content_frac >= 0.40
    )
    crop = not is_plate
    n = 80 if is_plate else 64
    wa, pa = win_im.size[0] * win_im.size[1], max(1, pc_im.size[0] * pc_im.size[1])
    treat_black = (not is_plate) and wa > 4 * pa
    corr, mad, rgbmad = structure_score(
        pc_im, win_im, crop=crop, n=n, treat_black=treat_black
    )
    if kind in ("demon", "skill"):
        # too similar = same drawing; very low corr = usually the wrong sprite in the slot
        return 0.12 <= corr < 0.50
    if kind == "char":
        # Standing NPCs and object overlays: same pose, Win is AA + inset in the box.
        if is_pc98_char_overlay(pc_im):
            return False
        # Fullscreen dump into a small filled plate (e.g. forest around a hole).
        ww, hh = win_im.size
        if max(pc_im.size) < 280 and ww >= 600 and hh >= 348:
            return False
    # CG / talk portraits: same composition+lines → drop
    if corr >= 0.80:
        return False
    if corr >= 0.70 and mad < 14 and rgbmad < 16:
        return False
    return True


# Windows redraws of room frames normal play shows, kept whatever the structure test says: a room laid
# out like the PC-98 one can correlate at 0.80 in luminance in other colours and with other walls
# (FC5000 10_000, FC5010 13_000 do; the study 5014h and the subway tunnels 5021h-5023h, rendered anew
# on the PC-98 layout, reach 0.95). tools/winrooms.py converts them into gfx_win_fit/, reading the
# Windows pictures itself - also 5054h, whose two Windows pictures (one drawing twice) this catalogue
# names frames 1 and 2 of FC5050 entry 4, and 5090h (drop_win_swap below).
REDRAWN = {("FC5000", "10_000.png"), ("FC5010", "06_000.png"), ("FC5010", "07_000.png"),
           ("FC5010", "13_000.png"), ("FC5010", "04_000.png"), ("FC5020", "01_000.png"),
           ("FC5020", "02_000.png"), ("FC5020", "03_000.png"), ("FC5090", "00_000.png")}


def filter_similar_sprites():
    """Drop Win plates that are the same drawing as PC-98 (or a mismatched slot)."""
    kept = dropped = skipped = 0
    by_kind = Counter()
    drop_kind = Counter()
    examples = {"keep": [], "drop": []}

    def consider(kind, fc, p, keep):
        nonlocal kept, dropped
        if keep:
            kept += 1
            by_kind[kind] += 1
            if len(examples["keep"]) < 12:
                examples["keep"].append(f"{fc}/{p.name}")
        else:
            try:
                p.unlink()
            except OSError:
                return
            dropped += 1
            drop_kind[kind] += 1
            if len(examples["drop"]) < 12:
                examples["drop"].append(f"{fc}/{p.name}")

    for d in sorted(OUT.iterdir()):
        if not d.is_dir():
            continue
        kind = sprite_kind(d.name)
        if not kind:
            continue

        pngs = list(d.glob("*.png"))
        forced = []
        rest = []
        for p in pngs:
            if drop_win_swap(d.name, p.name):
                forced.append(p)
            else:
                rest.append(p)
        for p in forced:
            consider(kind, d.name, p, False)
        pngs = rest
        gdir = gold_dir(d.name)
        if not gdir:
            prune_manifest(d)
            if not any(d.glob("*.png")):
                man = d / "manifest.json"
                if man.exists():
                    try:
                        man.unlink()
                    except OSError:
                        pass
                try:
                    d.rmdir()
                except OSError:
                    pass
            continue
        if kind == "demon":
            poses = defaultdict(dict)
            leftovers = []
            for p in pngs:
                m = re.fullmatch(r"(\d{2})_(\d{3})\.png", p.name)
                if not m:
                    leftovers.append(p)
                    continue
                poses[m.group(2)][int(m.group(1))] = p
            for _pose, ents in poses.items():
                p02 = ents.get(2)
                keep_pose = False
                if p02 and p02.exists():
                    gp = gdir / p02.name
                    if not gp.exists():
                        keep_pose = True
                    else:
                        with Image.open(p02) as imw, Image.open(gp) as imp:
                            if max(imw.size) <= 16:
                                keep_pose = False
                            else:
                                try:
                                    keep_pose = art_significantly_different(imp, imw, "demon")
                                except Exception:
                                    keep_pose = False
                else:
                    # 02 already removed as similar; 04/06 only look different because of zoom
                    keep_pose = False
                for p in ents.values():
                    if not p.exists():
                        continue
                    consider(kind, d.name, p, keep_pose)
            pngs = leftovers

        for p in pngs:
            if not p.exists():
                continue
            with Image.open(p) as imw:
                w, h = imw.size
                tiny = max(w, h) <= 16 or w * h <= 64
                payload = None if tiny else imw.copy()
            if tiny:
                gp = gdir / p.name
                keep_dummy = False
                if gp.exists():
                    with Image.open(gp) as gim:
                        gw, gh = gim.size
                        keep_dummy = max(gw, gh) <= 16 or gw * gh <= 64
                consider(kind, d.name, p, keep_dummy)
                continue
            if d.name == "FC50F0" or (d.name, p.name) in REDRAWN:
                consider(kind, d.name, p, True)
                continue
            if payload is not None and is_portrait_scrap(d.name, payload):
                consider(kind, d.name, p, False)
                continue
            gp = gdir / p.name
            if not gp.exists():
                consider(kind, d.name, p, True)
                continue
            with Image.open(gp) as imp:
                try:
                    keep = art_significantly_different(imp, payload, kind)
                except Exception:
                    keep = True
            consider(kind, d.name, p, keep)

        prune_manifest(d)
        if not any(d.glob("*.png")):
            man = d / "manifest.json"
            if man.exists():
                try:
                    man.unlink()
                except OSError:
                    pass
            try:
                d.rmdir()
            except OSError:
                pass
    rec = {
        "kept": kept,
        "dropped": dropped,
        "skipped_nonsprite": skipped,
        "kept_by": dict(by_kind),
        "dropped_by": dict(drop_kind),
        "examples": examples,
    }
    print(
        f"sprite filter: kept {kept}  dropped {dropped}  "
        f"(structure vs PC-98)  skip {skipped}"
    )
    print("  kept", dict(by_kind), "dropped", dict(drop_kind))
    print("  drop e.g.", examples["drop"][:8])
    print("  keep e.g.", examples["keep"][:8])
    return rec


def restore_gfx_win_manifest(fc: str):
    dest_dir = OUT / fc
    src = None
    for root in (GFX_ORIG, GFX):
        p = root / fc / "manifest.json"
        if p.exists():
            src = p
            break
    if src is None:
        prune_manifest(dest_dir)
        return
    man = json.loads(src.read_text(encoding="utf-8"))
    present = {p.name for p in dest_dir.glob("*.png")}
    listed = set()
    by_e = {}
    for e in man.get("entries") or []:
        e["frames"] = [fr for fr in (e.get("frames") or []) if fr.get("png") in present]
        listed.update(fr["png"] for fr in e["frames"])
        if e["frames"]:
            png = dest_dir / e["frames"][0]["png"]
            if png.exists():
                with Image.open(png) as im:
                    e["palettes"] = [pal_words_from_png(im)]
                e["sets_colours"] = list(range(16))
                e["palette_mask"] = "FFFF"
        for fr in e["frames"]:
            png = dest_dir / fr["png"]
            if not png.exists():
                continue
            with Image.open(png) as im:
                w, h = im.size
            if (w, h) != (fr["w"], fr["h"]):
                fr["w"], fr["h"] = w, h
                if (w, h) == SCREEN:
                    fr["x"], fr["y"] = 0, 0
        by_e[e["entry"]] = e
    for name in sorted(present - listed):
        m = re.fullmatch(r"(\d{2})_(\d{3})\.png", name)
        if not m:
            continue
        eid = int(m.group(1))
        e = by_e.get(eid)
        if e is None:
            continue
        with Image.open(dest_dir / name) as im:
            w, h = im.size
        sibling = next((fr for fr in e["frames"] if fr["w"] * fr["h"] > 64), None)
        e["frames"].append({
            "x": sibling["x"] if sibling else 0,
            "y": sibling["y"] if sibling else 0,
            "w": w,
            "h": h,
            "png": name,
        })
    man["entries"] = [e for e in (man.get("entries") or []) if e.get("frames")]
    (dest_dir / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")


def _refit_png(fc: str, name: str, mode="cover"):
    p = OUT / fc / name
    fr = orig_frames(fc).get(name)
    if not p.exists() or not fr:
        return False
    tw, th = fr["w"], fr["h"]
    with Image.open(p) as im:
        src = png_rgba(im)
    if mode == "strip":
        out = crop_screen_strip(src, tw, th, fr.get("x") or 0, fr.get("y") or 0)
        save_indexed(p, out)
    else:
        save_indexed(p, cover_rgba(crop_keyed_letterbox(src), tw, th))
    return True


def composite_pc98_title_on_win():
    """Deprecated name — FC50F0/01-05 overlays on Win 00. Kept as alias."""
    return overlay_pc98_fc50f0_strips()


def overlay_pc98_fc50f0_strips(thr=50):
    """PC-98 01-05 are y=136 overlays (scanlines / title). Key against orig 00, blit onto Win 00."""
    orig = GFX_ORIG / "FC50F0"
    dest = OUT / "FC50F0"
    bg_path = orig / "00_000.png"
    win_path = dest / "00_000.png"
    if not bg_path.exists() or not win_path.exists():
        return []
    with Image.open(bg_path) as bgo, Image.open(win_path) as wino:
        orig_bg = np.asarray(bgo.convert("RGB"))
        win_bg = np.asarray(wino.convert("RGB"))
    y0, y1 = 136, 272
    ref = orig_bg[y0:y1]
    done = []
    for name in ("01_000.png", "02_000.png", "03_000.png", "04_000.png", "05_000.png"):
        src = orig / name
        if not src.exists():
            continue
        with Image.open(src) as im:
            fg = np.asarray(im.convert("RGB"))
        if fg.shape[:2] != ref.shape[:2]:
            continue
        delta = np.abs(fg.astype(np.int16) - ref.astype(np.int16)).sum(axis=2)
        mask = delta >= thr
        plate = win_bg[y0:y1].copy()
        plate[mask] = fg[mask]
        save_indexed(dest / name, Image.fromarray(plate))
        done.append(name)
    return done


def apply_user_fit():
    """Apply keep/crop decisions without dropping remaining plates except FC40FF."""
    done = []

    d40 = OUT / "FC40FF"
    if d40.exists():
        for p in list(d40.iterdir()):
            p.unlink()
        d40.rmdir()
        done.append("dropped FC40FF")

    for name in ("12_000.png", "12_001.png", "12_002.png", "12_003.png"):
        if _refit_png("FC4010", name, "cover"):
            done.append(f"crop FC4010/{name}")
    for name in ("10_000.png", "10_001.png", "10_002.png", "10_003.png", "10_004.png"):
        if _refit_png("FC4090", name, "cover"):
            done.append(f"fill FC4090/{name}")
    if _refit_png("FC3000", "00_005.png", "cover"):
        done.append("crop FC3000/00_005")

    for fc in ("FC3000", "FC3001", "FC3003", "FC4040", "FC5060"):
        d = OUT / fc
        if not d.is_dir():
            continue
        frames = orig_frames(fc)
        for p in sorted(d.glob("*.png")):
            if fc == "FC3000" and p.name == "00_005.png":
                continue
            fr = frames.get(p.name)
            if not fr or not is_picture_dest(fr["w"], fr["h"]):
                continue
            with Image.open(p) as im:
                canvas = im.size
                rgba = png_rgba(im)
            if canvas != (fr["w"], fr["h"]):
                _refit_png(fc, p.name, "cover")
                done.append(f"canvas {fc}/{p.name}")
                continue
            arr = np.asarray(rgba)
            rgb, al = arr[..., :3].astype(np.int16), arr[..., 3]
            ink = al >= 128
            ink &= ~((rgb[..., 0] >= 250) & (rgb[..., 2] >= 250) & (rgb[..., 1] <= 8))
            ink &= rgb.sum(axis=2) > 18
            ys, xs = np.where(ink)
            if not ys.size:
                continue
            bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
            if bw < fr["w"] * 0.88 or bh < fr["h"] * 0.88:
                _refit_png(fc, p.name, "cover")
                done.append(f"fill {fc}/{p.name}")

    # FC5050: keep extras under free names; restore orig 8x8 dummy slots.
    sibling = {
        "02_001.png": ("02_002.png", "02_000.png"),
        "04_001.png": ("04_002.png", "04_000.png"),
        "06_001.png": ("06_003.png", "06_000.png"),
        "06_002.png": ("06_004.png", "06_000.png"),
        "12_000.png": ("12_002.png", "12_001.png"),
    }
    d5050 = OUT / "FC5050"
    gold5050 = GFX_ORIG / "FC5050"
    frames5050 = orig_frames("FC5050")
    for old, (new, sib) in sibling.items():
        src = d5050 / old
        if not src.exists():
            continue
        with Image.open(src) as im:
            big = im.size[0] * im.size[1] > 64
            rgba = png_rgba(im) if big else None
        if big and rgba is not None:
            sfr = frames5050.get(sib) or {"w": 368, "h": 200}
            save_indexed(d5050 / new, cover_rgba(crop_keyed_letterbox(rgba), sfr["w"], sfr["h"]))
            done.append(f"extra FC5050/{old}->{new}")
        dummy = gold5050 / old
        if dummy.exists():
            shutil.copy2(dummy, src)
            done.append(f"dummy FC5050/{old}")
        elif big:
            src.unlink()

    # FC50F0: Win 00 is a real 640x400 plate; then 01-05 are y=136 strips.
    f50 = OUT / "FC50F0"
    f50.mkdir(parents=True, exist_ok=True)
    bin0 = WIN_FC / "fc50f0.bin"
    if bin0.exists():
        bmps = parse_bmps(bin0.read_bytes())
        if bmps:
            im = convert_one(bmps[0], 640, 400, [], "00_000.png", 0, "cg")
            save_indexed(f50 / "00_000.png", im)
            done.append("made FC50F0/00_000")
    overlays = overlay_pc98_fc50f0_strips()
    if overlays:
        done.append("FC50F0/01-05 = Win 00 + PC-98 overlay (" + ",".join(overlays) + ")")
    orig6 = GFX_ORIG / "FC50F0" / "06_000.png"
    if orig6.exists():
        shutil.copy2(orig6, f50 / "06_000.png")
        done.append("FC50F0/06 = PC-98 copyright overlay")

    for fc in ("FC4010", "FC4090", "FC3000", "FC3001", "FC3003", "FC4040",
               "FC5050", "FC5060", "FC50F0"):
        if (OUT / fc).is_dir():
            restore_gfx_win_manifest(fc)

    print("apply_user_fit:")
    for line in done:
        print(" ", line)
    print(f"  {len(done)} steps")
    return done


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    if len(sys.argv) > 1 and sys.argv[1] == "filter":
        filter_similar_sprites()
    elif len(sys.argv) > 1 and sys.argv[1] == "fit":
        apply_user_fit()
    else:
        main()
