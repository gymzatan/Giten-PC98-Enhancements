"""Batch Windows-art conversion using the existing catalogue, fitter and encoder.

Run in a fresh source checkout after extracting the Japanese reference into files/.
Put a copy of the Windows installation's ddswin directory in inputs/ddswin/.
The recipe records the published selection, palettes and placements, without pixels.
Refitting is a new conversion; compare its output visually before publishing it.
"""
import json
from pathlib import Path
import shutil
import sys

from PIL import Image

import fcencode
import fcfit
import fcimage
import gfx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "run"))
import win_to_pc98 as w2p


def prepare_selected():
    """Materialize the authored positive selection, independently of similarity filtering."""
    import winfit, winrooms, winsource
    recipe = json.loads((ROOT / "text/artwork-recipe.json").read_text(encoding="utf-8"))
    jobs = winsource.jobs(w2p.Catalog())
    deferred = {(stem, k, f) for stem, k, frames, _variant in winrooms.FRAMES for f in frames}
    for stem, spec in sorted(recipe.items()):
        if stem in winfit.DEMONS:
            cache = {}
            list(winfit.placements(stem, jobs, winfit.anchor(stem, jobs, cache), cache))
            continue
        for name in spec["frames"]:
            if (stem, int(name[:2]), int(name[3:6])) in deferred:
                continue
            source = spec["sources"][name]
            dest = ROOT / "gfx_win" / stem / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source == "original":
                shutil.copy2(ROOT / "gfx_orig" / stem / name, dest)
            elif source == "catalogue":
                job = jobs[(stem, name)]
                bmp = w2p.parse_bmps(Path(job["path"]).read_bytes())[job["bmp_index"]]
                picture = w2p.convert_one(bmp, job["tw"], job["th"], job["pal"], name,
                                          job["entry"], job["mode"])
                picture.save(dest, transparency=gfx.TRANSPARENT)
            else:
                raise ValueError(f"Unknown explicit source for {stem}/{name}: {source}")


def fit_selected(stems=None):
    import winrooms
    recipe = json.loads((ROOT / "text/artwork-recipe.json").read_text(encoding="utf-8"))
    deferred = {(stem, k, f) for stem, k, frames, _variant in winrooms.FRAMES for f in frames}
    for stem, spec in sorted(recipe.items()):
        if stems is not None and stem not in stems:
            continue
        entries = fcimage.entries((ROOT / "files/DDS98" / (stem + ".BIN")).read_bytes())
        dest = ROOT / "gfx_win_fit" / stem
        dest.mkdir(parents=True, exist_ok=True)
        grouped = {}
        for name in spec["frames"]:
            if (stem, int(name[:2]), int(name[3:6])) in deferred:
                continue
            grouped.setdefault(int(name[:2]), []).append(name)
        for k, names in sorted(grouped.items()):
            entry = entries[k]
            palettes = spec["palettes"].get(str(k))
            if palettes is not None:
                entry = gfx.set_entry_palettes(entry, [[int(v, 16) for v in p] for p in palettes])
            image = fcimage.Image(entry)
            offsets = fcencode.frame_offsets(image.layout)
            blanks, boxes = {}, {}
            for name in names:
                frame = int(name[3:6])
                x, y, w, h = fcencode.frame_box(image, frame)
                position = spec["placements"].get(name, {"x": x * 8, "y": y * 8})
                width, height = spec["sizes"][name]
                box = position["x"] // 8, position["y"] // 8, width // 8, height // 8
                if box != (x, y, w, h):
                    blanks[offsets[frame]] = [None] * (width * height)
                    boxes[offsets[frame]] = box
            if boxes:
                entry = fcencode.encode_entry(entry, blanks, boxes)
            pictures = {int(name[3:6]): Image.open(ROOT / "gfx_win" / stem / name).convert("RGBA") for name in names}
            # Reuse the existing fitter; the selected palette is an authored conversion decision.
            fit = fcfit.fit(entry, pictures, palette="own", placement="contain", outline="picture")
            for group in spec["same_picture"]:
                members = [int(name[3:6]) for name in group if int(name[:2]) == k and name in names]
                if len(members) > 1:
                    for frame in members[1:]:
                        fit.index[frame] = fit.index[members[0]].copy()
            new = fcimage.Image(fcfit.apply(entry, fit))
            for frame in pictures:
                gfx.frame_png(new, frame).save(dest / f"{k:02d}_{frame:03d}.png", transparency=gfx.TRANSPARENT)
            print(stem, k, fit.how, flush=True)
        (dest / "palettes.json").write_text(json.dumps(spec["palettes"], indent=1), encoding="utf-8")
        placed = {name: spec["placements"][name] for names in grouped.values() for name in names
                  if name in spec["placements"]}
        if placed:
            (dest / "frames.json").write_text(json.dumps(placed, indent=1), encoding="utf-8")


def main():
    expected = ("gfx", "gfx_orig", "gfx_win", "gfx_win_fit", "wingfx_new", "windoors", "winhud", "windows-bmp")
    occupied = [name for name in expected if (ROOT / name).exists()]
    if occupied:
        raise ValueError("Use a fresh checkout for conversion; existing output directories: " + ", ".join(occupied))
    import winbmps, wintex, windoor, winfit, winrooms, winshare, winhud, mkwinpatch
    gfx.extract("gfx_orig")
    shutil.copytree(ROOT / "gfx_orig", ROOT / "gfx")
    winbmps.build()
    w2p.main()
    w2p.filter_similar_sprites()
    prepare_selected()
    w2p.apply_user_fit()
    fit_selected()
    wintex.main("wingfx_new")
    windoor.build("windoors")
    winfit.main([])
    winrooms.main()
    winshare.main()
    winhud.build()
    mkwinpatch.main()


if __name__ == "__main__":
    main()
