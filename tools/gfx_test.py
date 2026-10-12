#!/usr/bin/env python3
"""Self-test of the graphics write-back (gfx.py seed / edited_files). Run from work/.

Uses a scratch text root under build/gfx_test/ (removed first)."""
import glob
import json
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image as PILImage  # noqa: E402

import fcimage  # noqa: E402
import gfx  # noqa: E402

ROOT = "build/gfx_test"
FAILS = []


def expect(ok, what):
    if not ok:
        FAILS.append(what)
        print("FAIL", what)


def rejected(what, needle):
    try:
        gfx.edited_files(ROOT)
    except gfx.GfxError as e:
        expect(needle in str(e), f"{what}: message {str(e)!r}")
        return
    expect(False, f"{what}: accepted")


def png_path(stem, k, f):
    return os.path.join(ROOT, gfx.GFX_DIR, stem, f"{k:02d}_{f:03d}.png")


def test_container():
    bad = [p for p in glob.glob(os.path.join(gfx.SRC, "FC*.BIN"))
           if gfx.fc_file(fcimage.entries(open(p, "rb").read())) != open(p, "rb").read()]
    expect(not bad, f"FC files rebuild from their entries unchanged ({len(bad)} differ)")


def test_seed_and_edit():
    gfx.seed(ROOT)
    n = sum(len(frames) for _s, _k, frames, _w in gfx.TEXT_FRAMES)
    expect(len(glob.glob(os.path.join(ROOT, gfx.GFX_DIR, "*", "*.png"))) == n, f"seed writes {n} files")
    files, changes = gfx.edited_files(ROOT)
    expect(not files and not changes, "seeded files equal the game: nothing rebuilt")

    stem, k, f = "FC50F0", 6, 0                         # copyright lines, transparent background
    path = png_path(stem, k, f)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = fcimage.Image(gfx.fc_entries(stem)[k])
    gfx.frame_png(img, f).save(path, transparency=gfx.TRANSPARENT)
    im = PILImage.open(path)
    px = im.load()
    for y in range(2, 14):
        for x in range(4, 60):
            px[x, y] = 15 if (x // 4 + y // 4) % 2 else gfx.TRANSPARENT
    im.save(path, transparency=gfx.TRANSPARENT)
    files, changes = gfx.edited_files(ROOT)
    expect([c[:3] for c in changes] == [(stem, k, f)], f"one edited frame found ({changes})")
    old = gfx.fc_entries(stem)
    new = fcimage.entries(files.get(stem + ".BIN", b""))
    expect(len(new) == len(old) and all(a == b for i, (a, b) in enumerate(zip(old, new)) if i != k),
           "other entries of the file unchanged")
    if len(new) == len(old):
        got = fcimage.Image(new[k]).indices(f)[2]
        want = [None if v == gfx.TRANSPARENT else v for v in PILImage.open(path).get_flattened_data()]
        expect(got == want, "rebuilt entry decodes to the edited PNG")
    return path


def test_rejections(path):
    good = open(path, "rb").read()
    PILImage.open(path).convert("RGB").save(path)
    rejected("RGB PNG", "indexed PNG is needed")
    open(path, "wb").write(good)

    im = PILImage.open(path)
    im.crop((0, 0, im.width - 8, im.height)).save(path, transparency=gfx.TRANSPARENT)
    rejected("wrong size", "pixels, the frame is")
    open(path, "wb").write(good)

    im = PILImage.open(path)
    pal = im.getpalette()
    pal[3:6] = [1, 2, 3]
    im.putpalette(pal)
    im.save(path, transparency=gfx.TRANSPARENT)
    rejected("changed palette", "palette differs")
    open(path, "wb").write(good)

    im = PILImage.open(path)
    pal = (im.getpalette() + [0] * 768)[:768]
    im.putpalette(pal)
    im.putpixel((0, 0), 17)
    im.save(path, transparency=gfx.TRANSPARENT)
    rejected("pixel value 17", "pixel value 17")
    open(path, "wb").write(good)

    stray = os.path.join(os.path.dirname(path), "notes.txt")
    open(stray, "w").write("x")
    rejected("stray file", "not a frame file")
    os.remove(stray)

    shared = None
    for p in sorted(glob.glob(os.path.join(gfx.SRC, "FC*.BIN"))):
        for k, entry in enumerate(fcimage.entries(open(p, "rb").read())):
            layout = fcimage.Image(entry).layout
            offs = gfx.frame_offsets(layout)
            dup = [f for f, o in enumerate(offs) if offs.index(o) != f]
            if dup:
                shared = (os.path.basename(p)[:-4], k, dup[0], offs.index(offs[dup[0]]))
                break
        if shared:
            break
    if shared:
        stem, k, f, owner = shared
        img = fcimage.Image(gfx.fc_entries(stem)[k])
        extra = png_path(stem, k, f)
        os.makedirs(os.path.dirname(extra), exist_ok=True)
        gfx.frame_png(img, owner).save(extra, transparency=gfx.TRANSPARENT)
        rejected("frame sharing another frame's picture", f"edit {k:02d}_{owner:03d}.png")
        os.remove(extra)
    expect(shared is not None, "an entry with a shared frame exists for the test")

    bogus = os.path.join(ROOT, gfx.GFX_DIR, "FC9999")
    os.makedirs(bogus)
    rejected("unknown folder", "not the folder of an FC file")
    os.rmdir(bogus)
    files, changes = gfx.edited_files(ROOT)
    expect(len(changes) == 1, "back to the one valid edit")


def test_boxes():
    """frames.json: a frame at a size and place of its own, and what is refused around it."""
    stem, k = "FC2870", 2                               # frames 0-2 share one picture
    folder = os.path.join(ROOT, gfx.GFX_DIR, stem)
    os.makedirs(folder, exist_ok=True)
    img = fcimage.Image(gfx.fc_entries(stem)[k])
    path, frames = png_path(stem, k, 0), os.path.join(folder, gfx.FRAMES_NAME)
    W, H = 72, 160
    im = PILImage.new("P", (W, H))
    im.putpalette(gfx.palette_rgb(gfx.entry_palette(img)))
    pix = [gfx.TRANSPARENT if (x // 4 + y // 6) % 3 == 0 else (x + 2 * y) % 16 for y in range(H) for x in range(W)]
    im.putdata(pix)
    im.save(path, transparency=gfx.TRANSPARENT)
    rejected("another size without frames.json", f"needs its place in {gfx.FRAMES_NAME}")
    json.dump({"02_000.png": {"x": -40, "y": -144}}, open(frames, "w", encoding="utf-8"))
    files, changes = gfx.edited_files(ROOT)
    expect([c[:3] for c in changes if c[0] == stem] == [(stem, k, 0)], f"the grown frame is an edit ({changes})")
    out = fcimage.Image(fcimage.entries(files[stem + ".BIN"])[k])
    want = [None if v == gfx.TRANSPARENT else v for v in pix]
    expect(all(out.frames[f][:4] == (0x10000 - 5, 0x10000 - 18, 9, 20) for f in (0, 1, 2))
           and out.indices(1)[2] == want, "frames 0-2 take the box from frames.json and draw the PNG")
    json.dump({"02_000.png": {"x": -40, "y": -140}}, open(frames, "w", encoding="utf-8"))
    rejected("a place off the cell grid", "whole cells of 8")
    json.dump({"02_000.png": {"x": -40, "y": -144}, "02_003.png": {"x": 0, "y": 0}},
              open(frames, "w", encoding="utf-8"))
    rejected("a place for a frame file that is not there", "no frame file 02_003.png")
    im.crop((0, 0, W, H - 4)).save(path, transparency=gfx.TRANSPARENT)
    json.dump({"02_000.png": {"x": -40, "y": -144}}, open(frames, "w", encoding="utf-8"))
    rejected("a size off the cell grid", "whole cells of 8x8")
    gfx.frame_png(img, 0).save(path, transparency=gfx.TRANSPARENT)
    json.dump({"02_000.png": {"x": -32, "y": -16}}, open(frames, "w", encoding="utf-8"))
    files, changes = gfx.edited_files(ROOT)
    out = fcimage.Image(fcimage.entries(files[stem + ".BIN"])[k])
    expect(out.frames[0][:2] == (0x10000 - 4, 0x10000 - 2) and out.indices(0)[2] == img.indices(0)[2],
           "the game's own picture in a moved box is an edit too")
    shutil.rmtree(folder)


def test_extend():
    """FC1400 grow-by-clone: extra entries copy the template, blank slots copy the doorway."""
    src = gfx.fc_entries("FC1400")
    folder = os.path.join(ROOT, gfx.GFX_DIR, "FC1400")
    os.makedirs(folder, exist_ok=True)
    json.dump({"count": 11, "template": 0, "blank": [8, 9, 10], "blank_from": 2},
              open(os.path.join(folder, gfx.EXTEND_NAME), "w", encoding="utf-8"), indent=1)
    got = gfx.load_extend(folder, src)
    expect(len(got) == 11, f"extend to 11 entries ({len(got)})")
    expect(got[0] == src[0] and got[7] == src[0], "slots 0-7 clone entry 0")
    expect(got[8] == src[2] and got[10] == src[2], "slots 8-10 clone the black doorway")
    expect(len(gfx.load_extend(os.path.join(ROOT, gfx.GFX_DIR, "FC50F0"),
                               gfx.fc_entries("FC50F0")))
           == len(gfx.fc_entries("FC50F0")), "no extend.json leaves the file as it is")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shutil.rmtree(ROOT, ignore_errors=True)
    test_container()
    edited = test_seed_and_edit()
    test_extend()
    test_boxes()
    test_rejections(edited)
    shutil.rmtree(ROOT, ignore_errors=True)
    print("OK" if not FAILS else f"{len(FAILS)} failures")
    sys.exit(1 if FAILS else 0)
