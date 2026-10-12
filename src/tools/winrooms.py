#!/usr/bin/env python3
"""Room frames converted from their Windows pictures into gfx_win_fit/ one by one. Run from work/.

    winrooms.py

A room entry draws every frame with one palette per variant. FRAMES holds two kinds of room:
  * frames the catalogue (run/win_to_pc98.py) converted only in part: frame 1's Windows picture was fitted
    and palette 0 refitted to it, while frame 0 kept its PC-98 pixels - so frame 0, which normal play
    shows, came out in the colours of frame 1's picture (バエル's throne room in olive and light blue
    instead of purple). FC5010 entries 6 and 13 also show frame 1, always with variant 1; entry 13's
    frame 1 is fitted again into variant 1, because its earlier conversion drew with slot 12 (below);
  * rooms the catalogue left out although the Windows picture is another drawing: 5090h, the blue grid
    of シャンシャンシティ's 10F and 上野神殿 (drop_win_swap takes FC5070-FC50C0 for ending pictures), 5054h
    in 銀座地下街 (its two Windows pictures, one drawing twice, were named frames 1 and 2), and the rooms
    its structure test took for the PC-98 drawing where Windows renders the same layout anew: 5014h
    (the study of 市ヶ谷ｼｪﾙﾀｰ and 臨海ｺﾛｼｱﾑ) and the subway tunnels 5021h-5023h; and 5030h, the terminal
    room (the dome of the save terminals), which the catalogue's check of where a picture shows left out
    because its cells are map events of kind 40h (MS003C records 01-0E, 15 places), not 79h.
Every map cell and script that shows these pictures (map event byte +9 = 50xxh with +10/+11 =
variant/frame, command 266) uses frame 0 - with variant 0, but variant 1 for 5054h - except 5026h, shown
as frame 1 in all but one of its cells. So the frames shown are fitted here into the variant they are
shown with: one frame on its own, or the frames drawn with one palette together (5026h's two); every
other frame and variant keeps its pixels and colours exactly. The fit is tools/winfit.py's for a demon: the slots the entry sets that hold the screen's
black, white and status colours (winfit.RESERVED, and slot 4) keep them and are drawn with, the rest
are chosen for the picture (tools/fcfit.fit, palette auto with hold) - as the other converted rooms
have it.

KEEP names slots a room keeps in their PC-98 colour, held in the fit and drawn with like the screen's
colours. The allocator gives a colour that two pictures on the screen own one hardware slot, and the
PC-98 art counts on it: the card soldiers of M0029 (40C4h, 4070h, 408Bh, 4066h) own 0BAC in slot 9 as
their room 5026h does, so the scene fits the eleven slots a room has. A refit that moves the room's
slot 9 elsewhere leaves them one slot more to find (tools/winshare.py makes the pictures that are part
of a room follow its new colours instead).

Only slots 0-7 are drawn with, and the slots KEEP names. A room loads its colours through the allocator
(0871:8A9A, kind 0): its own colours take the hardware slots 1-3 the wall set gives up while the room is
shown, and a slot above 7 that the entry sets (FC5010 entry 13 sets 12) gets a hardware slot from 8 up.
The room stays on screen when a battle starts in its cell, and the battle hands slots 8-15 to the
enemies, so those pixels take an enemy's colour - traced in 代代木劳动营's torture room (M0004 section 1),
where 501Dh's slot 12 sat in hardware slot 8 and turned バール兵's orange. Since tools/slotorder.py the
enemies take those slots from 13 down, so a room keeps such a slot as long as it and the enemies need no
more than the six slots 8-13 together - 5026h's slot 9 in M0029's battle (MS0032 record 27) does.

FOLD names rooms whose battles need more than that, so a slot above 7 that the conversion drew with is
folded away: the springs 5037h (FC5030 entry 7), whose battles (MS003A record 1B) bring a pair of demons
from the section's encounters - six new colours as a rule - while the glow on the water sat in slot 9.
The slot's pixels are dithered again with slots 0-4 (black, white and the room's own 1-3) - ordered
dithering on the cell grid, as tools/fcfit.py does, each pixel choosing for every variant of the entry at
once against that variant's own Windows picture (variant v is Windows frame v; the entry's frames hold one
picture) - and the slot takes another slot's colour in every variant, so the allocator gives the two one
hardware slot and the room owns none above 7 in use. Every other pixel and colour stays.

The Windows picture is fcXXXe/NNN.bmp of the release, frame NNN, cropped to the view inside its metal
bezel and covered onto the frame as run/win_to_pc98.convert_one does for a scene plate.

Written: gfx_win_fit/FCxxxx/<entry>_<frame>.png, the entry's palettes in palettes.json, and the entry's
other frame PNGs again with the new palette 0 embedded - tools/gfx.py checks every frame PNG of an
entry against palette 0; their pixels do not change. FOLD runs after FRAMES on the entries as they are
then and finds nothing left to fold the second time. Re-running gives the same files.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(WORK, "run"))
import fcfit  # noqa: E402
import fcimage  # noqa: E402
import gfx  # noqa: E402
from wincells import BAYER8  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

FIT = os.path.join(WORK, "gfx_win_fit")
WIN = os.path.join(WORK, "windows-bmp", "fc")

# (file, entry, the frames fitted together, the variant they are shown with): 5016h the throne room of
# バエル and other bosses (12 places), 5017h (30), 500Ah (13), 501Dh (1; frame 1 in 2 more); 5090h (4 cells,
# 5 times in MS0013's 10F scene), 5054h (2), 5014h (2), 5021h-5023h (65 cells in 8 subway maps), 5026h
# (frame 1 in 27 cells, frame 0 in 1; for KEEP - one palette, so both frames are fitted as one), 5030h (the 15
# save terminals)
FRAMES = [("FC5010", 6, (0,), 0), ("FC5010", 7, (0,), 0), ("FC5000", 10, (0,), 0), ("FC5010", 13, (0,), 0),
          ("FC5010", 13, (1,), 1), ("FC5090", 0, (0,), 0), ("FC5050", 4, (0,), 1), ("FC5010", 4, (0,), 0),
          ("FC5020", 1, (0,), 0), ("FC5020", 2, (0,), 0), ("FC5020", 3, (0,), 0), ("FC5020", 6, (0, 1), 0),
          ("FC5030", 0, (0,), 0)]

# (file, entry): {slot: its PC-98 colour, kept}
KEEP = {("FC5020", 6): {9: 0x0BAC}}

# (file, entry, slot folded, slot it shares)
FOLD = [("FC5030", 7, 9, 3)]            # the springs 5037h: the glow on the water
FOLD_DRAWN = (0, 1, 2, 3, 4)            # the slots its pixels are redrawn with


def windows_picture(stem, k, f, w, h):
    import win_to_pc98 as w2p
    path = os.path.join(WIN, f"fc{stem[2:5].lower()}{k:x}", f"{f:03d}.bmp")
    plate = w2p.extract_cg_plate(Image.open(path))
    return w2p.cover_rgba(w2p.crop_keyed_letterbox(plate), w, h).convert("RGBA")


def current_entry(stem, k, skip):
    """Entry k of stem as gfx_win_fit/ builds it now, without the frame PNGs in `skip`."""
    with tempfile.TemporaryDirectory() as tmp:
        dest = os.path.join(tmp, gfx.GFX_DIR, stem)
        shutil.copytree(os.path.join(FIT, stem), dest)
        for name in skip:
            path = os.path.join(dest, name)
            if os.path.exists(path):
                os.remove(path)
        files, _changes = gfx.edited_files(tmp)
    blob = files.get(stem + ".BIN") or open(os.path.join(gfx.SRC, stem + ".BIN"), "rb").read()
    return list(fcimage.entries(blob))[k]


def convert(stem, k, frames, v):
    """(new entry, fit) for the frames, fitted together into variant v; files written. fcfit fits into
    palette 0, so variant v is put there for the fit and moved back after it."""
    names = [f"{k:02d}_{f:03d}.png" for f in frames]
    from winfit import RESERVED, WHITE
    os.makedirs(os.path.join(FIT, stem), exist_ok=True)
    entry = current_entry(stem, k, names)
    img = fcimage.Image(entry)
    keep = KEEP.get((stem, k), {})
    pals = [list(p) for p in img.palettes]
    for s, colour in keep.items():
        if s not in fcfit.owned(img):
            raise SystemExit(f"{stem} entry {k}: KEEP names slot {s}, which the entry does not set")
        pals[v][s] = colour
    order = list(range(len(pals)))
    order[0], order[v] = v, 0
    shown = gfx.set_entry_palettes(entry, [pals[i] for i in order])
    hold = [i for i in fcfit.owned(img) if pals[v][i] in RESERVED or i == WHITE or i in keep]
    slots = [i for i in fcfit.owned(img) if i < 8 or i in keep]
    fit = fcfit.fit(shown, {f: windows_picture(stem, k, f, *fcfit.frame_size(img, f)) for f in frames},
                    palette="auto", slots=slots, hold=hold)
    fit.palettes = [fit.palettes[i] for i in order]
    new = fcimage.Image(fcfit.apply(entry, fit))
    folder = os.path.join(FIT, stem)
    for f, name in zip(frames, names):
        gfx.frame_png(new, f).save(os.path.join(folder, name), transparency=gfx.TRANSPARENT)
    pal_path = os.path.join(folder, "palettes.json")
    pals = json.load(open(pal_path, encoding="utf-8")) if os.path.exists(pal_path) else {}
    pals[str(k)] = [[f"{v:04X}" for v in p] for p in fit.palettes]
    json.dump({key: pals[key] for key in sorted(pals, key=int)}, open(pal_path, "w", encoding="utf-8"),
              indent=1)
    stamp = gfx.palette_rgb(fit.palettes[0])
    for other in sorted(os.listdir(folder)):
        if other.startswith(f"{k:02d}_") and other.endswith(".png") and other not in names:
            path = os.path.join(folder, other)
            im = Image.open(path)
            im.putpalette(stamp)
            im.save(path, transparency=gfx.TRANSPARENT)
    return new, fit


def _rgb(word):
    return np.array([((word >> 4) & 15) * 17, ((word >> 8) & 15) * 17, (word & 15) * 17], float)


def fold(stem, k, slot, into):
    """Entry k's pixels drawn with `slot` dithered again with FOLD_DRAWN, and `slot` given `into`'s colour in
    every palette (FOLD); files written. Returns (pixels redrawn, {slot drawn with: pixels}, palettes)."""
    folder = os.path.join(FIT, stem)
    pal_path = os.path.join(folder, "palettes.json")
    all_pals = json.load(open(pal_path, encoding="utf-8"))
    pals = [[int(w, 16) for w in p] for p in all_pals[str(k)]]
    names = sorted(n for n in os.listdir(folder) if n.startswith(f"{k:02d}_") and n.endswith(".png"))
    pictures = [np.array(Image.open(os.path.join(folder, n))) for n in names]
    if not pictures or any(not np.array_equal(p, pictures[0]) for p in pictures[1:]):
        raise SystemExit(f"{stem} entry {k}: FOLD takes an entry whose frames hold one picture")
    index = pictures[0]
    h, w = index.shape
    x0, y0 = fcfit.frame_origin(fcimage.Image(current_entry(stem, k, [])), 0)
    targets = [np.array(windows_picture(stem, k, v, w, h))[..., :3].astype(float) for v in range(len(pals))]
    ys, xs = np.nonzero(index == slot)
    want = np.concatenate([t[ys, xs] for t in targets], axis=1)
    threshold = BAYER8[(y0 + ys) % 8, (x0 + xs) % 8]

    # wincells.ordered with every variant's colour side by side: the two slots nearest the pixel in all
    # variants together, and the farther one where the pixel lies past the Bayer threshold toward it
    cols = np.array([np.concatenate([_rgb(p[i]) for p in pals]) for i in FOLD_DRAWN])
    order = np.argsort(((want[:, None, :] - cols[None]) ** 2).sum(-1), axis=1)
    a, b = order[:, 0], order[:, 1]
    span = cols[b] - cols[a]
    u = np.clip(((want - cols[a]) * span).sum(1) / np.maximum((span ** 2).sum(1), 1e-9), 0, 1)
    new = index.copy()
    new[ys, xs] = np.array(FOLD_DRAWN)[np.where(u > threshold, b, a)]
    for p in pals:
        p[slot] = p[into]
    stamp = gfx.palette_rgb(pals[0])
    for name in names:
        im = Image.frombytes("P", (w, h), new.astype(np.uint8).tobytes())
        im.putpalette(stamp)
        im.save(os.path.join(folder, name), transparency=gfx.TRANSPARENT)
    all_pals[str(k)] = [[f"{c:04X}" for c in p] for p in pals]
    json.dump({key: all_pals[key] for key in sorted(all_pals, key=int)}, open(pal_path, "w", encoding="utf-8"),
              indent=1)
    used = {c: int((new[ys, xs] == c).sum()) for c in FOLD_DRAWN}
    return len(ys), used, pals


def main():
    for stem, k, frames, v in FRAMES:
        _new, fit = convert(stem, k, frames, v)
        print(f"{stem} entry {k} frame {'+'.join(map(str, frames))}: {fit.how}, {fit.cells} cells, "
              f"{fit.bytes} bytes; palette {v} " + " ".join(f"{c:04X}" for c in fit.palettes[v]))
    for stem, k, slot, into in FOLD:
        n, used, pals = fold(stem, k, slot, into)
        print(f"{stem} entry {k}: slot {slot} folded into {into}, {n} pixels redrawn "
              + " ".join(f"{c}:{m}" for c, m in used.items() if m)
              + "; slot " + str(into) + " " + " ".join(f"{p[into]:04X}" for p in pals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
