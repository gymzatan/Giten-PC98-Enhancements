#!/usr/bin/env python3
"""Graphics of DDS98: FC*.BIN as indexed PNG files, and edited frames written back. Run from work/.

    gfx.py extract [dir]   dir (default gfx/): one folder per FC file
                           <entry>_<frame>.png   indexed PNG, colours 0-15 as the entry's
                                                 palette 0, index 16 transparent
                           manifest.json         per entry: palettes (0x0GRB words), which
                                                 colours the entry sets (the others are
                                                 placeholders the game fills from the palette
                                                 on screen), flags, frames (position and
                                                 size in pixels, the PNG)
    gfx.py sheets [dir]    dir/_sheets/<file>.png: thumbnails of every entry's frames
    gfx.py seed            the frames with Japanese text (TEXT_FRAMES) as PNG files in
                           text/gfx/<file>/, for editing; existing files are left alone
    gfx.py check           validate text/gfx/ and re-encode what differs from the game (what
                           make.py hdi does), listing the changed frames

Frames that point at the same layout data share one PNG, named after the first of them.

An edited frame in text/gfx/FCxxxx/<entry>_<frame>.png must stay an indexed PNG of the
frame's size with the extracted palette unchanged (17 colours, same order); pixel values
0-15 are colours, 16 is transparent. Frames whose pixels equal the game's are ignored;
the entries of the others are re-encoded by fcencode.py.

text/gfx/FCxxxx/palettes.json may give an entry new palettes: {"<entry>": [[16 words
"0GRB"], ...]}, every palette the entry has, in order. Only the colours the entry sets may
change - the others are placeholders the game never takes from it. An entry with new palettes
checks its frame PNGs against its new palette 0.

text/gfx/FCxxxx/frames.json may give frames boxes of their own: {"<entry>_<frame>.png":
{"x": X, "y": Y}}, the frame's top-left in pixels from the point the game draws the entry
at - whole cells, as manifest.json gives x and y. Such a PNG may be of any size in whole
cells, and the frame takes that size; the frames that share its picture move with it.
"""
import glob
import json
import os
import re
import struct
import sys

from PIL import Image as PILImage, ImageDraw

import fcencode
import fcimage

SRC = "files/DDS98"
TEXT_ROOT = "text"
GFX_DIR = "gfx"
TRANSPARENT = 16

# Gore CGs: keep pixel indices, but store grayscale palettes so the game shows B&W.
GRAYSCALE_PAL_ENTRIES = {("FC5050", 14), ("FC5050", 15)}


def luma8(r, g, b):
    return int(round(0.299 * r + 0.587 * g + 0.114 * b))


def gray_png_palette(pal_rgb):
    """17 RGB triplets: colours 0-15 as luma, index 16 unchanged (transparent magenta)."""
    out = []
    for i in range(TRANSPARENT):
        r, g, b = pal_rgb[i * 3:i * 3 + 3]
        y = luma8(r, g, b)
        out.extend([y, y, y])
    out.extend(pal_rgb[3 * TRANSPARENT:3 * (TRANSPARENT + 1)] or [255, 0, 255])
    return out


def palette_compatible(got, want):
    """Exact match, or PNG palette is the 8-bit luma of the game palette."""
    n = 3 * (TRANSPARENT + 1)
    got, want = (got or [])[:n], (want or [])[:n]
    if got == want:
        return True
    return got == gray_png_palette(want)


def gray_pc98_word(v):
    g, r, b = (v >> 8) & 15, (v >> 4) & 15, v & 15
    y = int(round(0.299 * r + 0.587 * g + 0.114 * b))
    y = max(0, min(15, y))
    return (y << 8) | (y << 4) | y


def grayscale_entry_palettes(entry):
    n_layout = struct.unpack_from("<H", entry, 0)[0]
    pal_off = 2 + n_layout
    _head, npal, _tail = struct.unpack_from("<3H", entry, pal_off)
    out = bytearray(entry)
    for p in range(npal):
        for i in range(16):
            off = pal_off + 6 + (p * 16 + i) * 2
            v = struct.unpack_from("<H", entry, off)[0]
            struct.pack_into("<H", out, off, gray_pc98_word(v))
    return bytes(out)


def set_entry_palettes(entry, palettes):
    """The entry with its palette words replaced; the count and everything else stay."""
    n_layout = struct.unpack_from("<H", entry, 0)[0]
    pal_off = 2 + n_layout
    _head, npal, _tail = struct.unpack_from("<3H", entry, pal_off)
    if npal != len(palettes):
        raise GfxError(f"{npal} palettes in the entry, {len(palettes)} given")
    out = bytearray(entry)
    for p, pal in enumerate(palettes):
        struct.pack_into("<16H", out, pal_off + 6 + p * 32, *pal)
    return bytes(out)


def load_palettes(path, stem, entries):
    """{entry: [palette words]} from palettes.json, each checked against the game's entry."""
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GfxError(f"{path}: {e}") from None
    out = {}
    for key, pals in raw.items():
        if not re.fullmatch(r"\d+", key) or int(key) >= len(entries):
            raise GfxError(f"{path}: {key!r} is not an entry of {stem} (0-{len(entries) - 1})")
        k = int(key)
        img = fcimage.Image(entries[k])
        if len(pals) != len(img.palettes):
            raise GfxError(f"{path}: entry {k} has {len(img.palettes)} palettes, {len(pals)} given")
        words = []
        for p, (pal, game) in enumerate(zip(pals, img.palettes)):
            if len(pal) != 16 or not all(re.fullmatch(r"0[0-9A-F]{3}", w) for w in pal):
                raise GfxError(f"{path}: entry {k} palette {p}: 16 words 0GRB expected")
            vals = [int(w, 16) for w in pal]
            for i, (got, want, own) in enumerate(zip(vals, game, img.owned())):
                if got != want and not own:
                    raise GfxError(f"{path}: entry {k} palette {p} colour {i}: the entry does not set "
                                   f"this colour, so it must stay {want:04X}")
            words.append(vals)
        out[k] = words
    return out

# Frames showing Japanese text: (file, entry, frames, what)
TEXT_FRAMES = [
    ("FC0000", 2, [7], "status panel labels 直 魔 体 器 命 / 精 知 敏 魅 (next to ALIGN, HP, MP)"),
    ("FC0110", 11, [0, 1, 2, 3, 4, 5], "table headers 種族 名称 of the demon lists, six sizes"),
    ("FC3000", 0, [0], "placeholder background: No GRAPHIC 現在、背景制作中!!"),
    ("FC40FF", 0, [0], "red brush title 偽典 女神転生"),
    ("FC5030", 3, [0], "weapon shop background, sign 火気厳禁"),
    ("FC5070", 13, [0], "ending: title 偽典・女神転生 東京黙示録"),
    ("FC5070", 14, [0], "ending: part of the title, 女神 … 録, behind a light"),
    ("FC50F0", 1, [0], "title screen: title 偽典・女神転生 東京黙示録 in the wave effect, step 1 of 5"),
    ("FC50F0", 2, [0], "title screen: wave effect step 2"),
    ("FC50F0", 3, [0], "title screen: wave effect step 3"),
    ("FC50F0", 4, [0], "title screen: wave effect step 4"),
    ("FC50F0", 5, [0], "title screen: the title at rest"),
]


class GfxError(ValueError):
    pass


EXTEND_NAME = "extend.json"
FRAMES_NAME = "frames.json"


def load_positions(path):
    """{frame file name: (x, y)} from frames.json, in pixels."""
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GfxError(f"{path}: {e}") from None
    out = {}
    for name, pos in raw.items():
        if not re.fullmatch(r"\d{2}_\d{3}\.png", name):
            raise GfxError(f"{path}: {name!r} is not a frame file name (<entry>_<frame>.png)")
        if not (isinstance(pos, dict) and set(pos) == {"x", "y"}
                and all(isinstance(pos[a], int) and pos[a] % 8 == 0 for a in "xy")):
            raise GfxError(f'{path}: {name}: {{"x": X, "y": Y}} expected, pixels in whole cells of 8')
        out[name] = (pos["x"], pos["y"])
    return out


def load_extend(folder, entries):
    """Grow `entries` by cloning, as extend.json of this folder asks.

    {count, template, blank, blank_from}: the list becomes `count` long; slots
    in `blank` copy original entry `blank_from` (a black doorway), the rest copy
    `template`. Used by the Windows door conversion to give FC1400 one entry per
    wall set (0-7) plus padding up to wall set 10.
    """
    path = os.path.join(folder, EXTEND_NAME)
    if not os.path.exists(path):
        return entries
    try:
        spec = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GfxError(f"{path}: {e}") from None
    count = spec.get("count")
    if not isinstance(count, int) or not len(entries) <= count <= 16:
        raise GfxError(f"{path}: count must be an integer {len(entries)}-16")
    template = spec.get("template", 0)
    blank_from = spec.get("blank_from", 2)
    blank = spec.get("blank", [])
    for name, v in (("template", template), ("blank_from", blank_from)):
        if not isinstance(v, int) or not 0 <= v < len(entries):
            raise GfxError(f"{path}: {name} is not an entry of the original file")
    if not isinstance(blank, list) or not all(isinstance(i, int) and 0 <= i < count for i in blank):
        raise GfxError(f"{path}: blank must be a list of entry indices below count")
    src = {k: blank_from if k in blank else template for k in range(count)}
    return [bytes(entries[src[k]]) for k in range(count)]


def palette_rgb(pal):
    flat = []
    for v in pal:
        flat += list(fcimage.pc98_rgb(v))
    flat += [255, 0, 255]                      # index 16: transparent
    return flat


def frame_offsets(layout):
    return fcencode.frame_offsets(layout) if len(layout) >= 4 else []


def entry_palette(img):
    return img.palettes[0] if img.palettes else [0] * 16


def frame_png(img, f):
    """The frame as an indexed PNG image (None for an empty frame)."""
    W, H, pix = img.indices(f)
    if not W or not H:
        return None
    im = PILImage.new("P", (W, H))
    im.putpalette(palette_rgb(entry_palette(img)))
    im.putdata([TRANSPARENT if c is None else c for c in pix])
    return im


def extract(out="gfx"):
    os.makedirs(out, exist_ok=True)
    n_png = n_entries = 0
    for path in sorted(glob.glob(os.path.join(SRC, "FC*.BIN"))):
        stem = os.path.basename(path)[:-4].upper()
        folder = os.path.join(out, stem)
        os.makedirs(folder, exist_ok=True)
        manifest = {"file": stem + ".BIN", "entries": []}
        for k, entry in enumerate(fcimage.entries(open(path, "rb").read())):
            img = fcimage.Image(entry)
            n_entries += 1
            info = {"entry": k,
                    "palettes": [[f"{v:04X}" for v in p] for p in img.palettes],
                    "palette_head": f"{img.pal_head:04X}", "palette_mask": f"{img.pal_tail:04X}",
                    "sets_colours": [i for i, on in enumerate(img.owned()) if on],
                    "remap": not img.no_remap, "derived_plane": bool(img.derived),
                    "layout_head": struct.unpack_from("<H", img.layout, 0)[0] if img.layout else None,
                    "frames": []}
            done = {}
            offs = frame_offsets(img.layout)
            for f, (x, y, w, h, _words) in enumerate(img.frames):
                name = done.get(offs[f])
                if name is None:
                    name = f"{k:02d}_{f:03d}.png"
                    im = frame_png(img, f)
                    if im is not None:
                        im.save(os.path.join(folder, name), transparency=TRANSPARENT)
                        n_png += 1
                    done[offs[f]] = name
                sx = x - 0x10000 if x & 0x8000 else x
                sy = y - 0x10000 if y & 0x8000 else y
                info["frames"].append({"x": sx * 8, "y": sy * 8, "w": w * 8, "h": h * 8, "png": name})
            manifest["entries"].append(info)
        with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=1)
    print(f"{n_entries} entries, {n_png} PNG files in {out}/")


def sheets(out="gfx", thumb=160):
    dest = os.path.join(out, "_sheets")
    os.makedirs(dest, exist_ok=True)
    for folder in sorted(glob.glob(os.path.join(out, "FC*"))):
        pngs = sorted(p for p in glob.glob(os.path.join(folder, "*.png")))
        if not pngs:
            continue
        cols = 8
        rows = (len(pngs) + cols - 1) // cols
        sheet = PILImage.new("RGB", (cols * thumb, rows * (thumb + 12)), (48, 48, 48))
        draw = ImageDraw.Draw(sheet)
        for i, p in enumerate(pngs):
            im = PILImage.open(p).convert("RGBA")
            im.thumbnail((thumb, thumb))
            x, y = i % cols * thumb, i // cols * (thumb + 12)
            sheet.paste(im, (x, y + 12), im)
            draw.text((x + 2, y), os.path.basename(p)[:-4], fill=(255, 255, 0))
        sheet.save(os.path.join(dest, os.path.basename(folder) + ".png"))
    print(f"sheets in {dest}")


def fc_entries(stem):
    return fcimage.entries(open(os.path.join(SRC, stem + ".BIN"), "rb").read())


def fc_file(entries):
    return b"".join(struct.pack("<I", len(e)) + e for e in entries)


def seed(root=TEXT_ROOT):
    made = kept = 0
    for stem, k, frames, _what in TEXT_FRAMES:
        img = fcimage.Image(fc_entries(stem)[k])
        folder = os.path.join(root, GFX_DIR, stem)
        os.makedirs(folder, exist_ok=True)
        for f in frames:
            path = os.path.join(folder, f"{k:02d}_{f:03d}.png")
            if os.path.exists(path):
                kept += 1
                continue
            frame_png(img, f).save(path, transparency=TRANSPARENT)
            made += 1
    print(f"{made} PNG files written to {os.path.join(root, GFX_DIR)}, {kept} already there")


def load_frame(path, W, H, pal):
    """Row-major pixels of an edited frame PNG (None = transparent)."""
    im = PILImage.open(path)
    if im.mode != "P":
        raise GfxError(f"{path}: an indexed PNG is needed (as extracted), this one is {im.mode}")
    if im.size != (W, H):
        raise GfxError(f"{path}: {im.size[0]}x{im.size[1]} pixels, the frame is {W}x{H} "
                       f"(a frame of another size needs its place in {FRAMES_NAME})")
    if not palette_compatible((im.getpalette() or []), palette_rgb(pal)):
        raise GfxError(f"{path}: palette differs from the extracted one "
                       f"(keep its {TRANSPARENT + 1} colours in their order, "
                       f"or a luma-grayscale of that palette)")
    pix = []
    for v in im.get_flattened_data():
        if v > TRANSPARENT:
            raise GfxError(f"{path}: pixel value {v}; 0-15 are colours, 16 is transparent")
        pix.append(None if v == TRANSPARENT else v)
    return pix


def edited_files(root=TEXT_ROOT):
    """({FC file name: rebuilt bytes}, [(file, entry, frame, old entry size, new entry size)])
    for the frames under root/gfx that differ from the game."""
    base = os.path.join(root, GFX_DIR)
    files, changes = {}, []
    for folder in sorted(glob.glob(os.path.join(base, "*"))):
        stem = os.path.basename(folder)
        if not os.path.isdir(folder) or not re.fullmatch(r"FC[0-9A-F]{4}", stem) \
                or not os.path.exists(os.path.join(SRC, stem + ".BIN")):
            raise GfxError(f"{folder}: not the folder of an FC file of the game (FCxxxx)")
        entries = load_extend(folder, fc_entries(stem))
        images, edits, boxes = {}, {}, {}
        pal_path = os.path.join(folder, "palettes.json")
        extend_path = os.path.join(folder, EXTEND_NAME)
        frames_path = os.path.join(folder, FRAMES_NAME)
        new_pals = load_palettes(pal_path, stem, entries) if os.path.exists(pal_path) else {}
        placed = load_positions(frames_path) if os.path.exists(frames_path) else {}
        skip = {os.path.normcase(p) for p in (pal_path, extend_path, frames_path)}
        for path in sorted(glob.glob(os.path.join(folder, "*"))):
            if os.path.normcase(path) in skip:
                continue
            name = os.path.basename(path)
            m = re.fullmatch(r"(\d{2})_(\d{3})\.png", name)
            if not m:
                raise GfxError(f"{path}: not a frame file (<entry>_<frame>.png), palettes.json, "
                               f"{FRAMES_NAME} or {EXTEND_NAME}")
            k, f = int(m.group(1)), int(m.group(2))
            if k >= len(entries):
                raise GfxError(f"{path}: {stem} has {len(entries)} entries")
            img = images.get(k) or images.setdefault(k, fcimage.Image(entries[k]))
            offs = frame_offsets(img.layout)
            if f >= len(offs):
                raise GfxError(f"{path}: entry {k} has {len(offs)} frames")
            owner = offs.index(offs[f])
            if owner != f:
                raise GfxError(f"{path}: frame {f} shows the picture of frame {owner}; "
                               f"edit {k:02d}_{owner:03d}.png")
            box = was = fcencode.frame_box(img, f)
            if name in placed:
                W, H = PILImage.open(path).size
                if W % 8 or H % 8:
                    raise GfxError(f"{path}: {W}x{H} pixels; a frame is whole cells of 8x8")
                box = (placed[name][0] // 8, placed[name][1] // 8, W // 8, H // 8)
            pal = new_pals[k][0] if k in new_pals else entry_palette(img)
            pix = load_frame(path, box[2] * 8, box[3] * 8, pal)
            if box != was or pix != img.indices(f)[2]:
                edits.setdefault(k, {})[offs[f]] = pix
                if box != was:
                    boxes.setdefault(k, {})[offs[f]] = box
                changes.append([stem, k, f])
        missing = sorted(n for n in placed if not os.path.exists(os.path.join(folder, n)))
        if missing:
            raise GfxError(f"{frames_path}: no frame file {', '.join(missing)} beside it")
        if stem == "FC5050":
            for gk in (14, 15):
                if gk < len(entries):
                    edits.setdefault(gk, {})
        for k, pals in new_pals.items():
            if pals != fcimage.Image(entries[k]).palettes:
                edits.setdefault(k, {})
                if not any(c[:2] == [stem, k] for c in changes):
                    changes.append([stem, k, "palettes"])
        if not edits:
            continue
        for k, frame_edits in sorted(edits.items()):
            try:
                # an entry that only takes new palettes keeps its encoded pictures byte for byte
                new = (fcencode.encode_entry(entries[k], frame_edits, boxes.get(k))
                       if frame_edits or (stem, k) in GRAYSCALE_PAL_ENTRIES else entries[k])
            except fcencode.EncodeError as e:
                raise GfxError(f"{stem} entry {k}: {e}") from None
            if (stem, k) in GRAYSCALE_PAL_ENTRIES:
                new = grayscale_entry_palettes(new)
            if k in new_pals:
                new = set_entry_palettes(new, new_pals[k])
            for c in changes:
                if c[:2] == [stem, k]:
                    c += [len(entries[k]), len(new)]
            if (stem, k) in GRAYSCALE_PAL_ENTRIES and not any(c[:2] == [stem, k] for c in changes):
                changes.append([stem, k, 0, len(entries[k]), len(new)])
            entries[k] = new
        files[stem + ".BIN"] = fc_file(entries)
    return files, [tuple(c) for c in changes]


def check(root=TEXT_ROOT):
    files, changes = edited_files(root)
    print(f"{len(changes)} edited frames, {len(files)} FC files rebuilt")
    for stem, k, f, old, new in changes:
        print(f"  {stem} entry {k} frame {f}: entry {old} -> {new} bytes")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if cmd == "extract":
            extract(*sys.argv[2:])
        elif cmd == "sheets":
            sheets(*sys.argv[2:])
        elif cmd == "seed" and len(sys.argv) == 2:
            seed()
        elif cmd == "check" and len(sys.argv) == 2:
            sys.exit(check())
        else:
            print(__doc__)
            sys.exit(2)
    except GfxError as e:
        print("ERROR", e)
        sys.exit(1)
