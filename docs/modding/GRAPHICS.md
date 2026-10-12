# Graphics format and Windows artwork

## Resource IDs and containers

`FCxxxx.BIN` contains repeated `[entry length:u32][entry bytes]` blocks. The resource ID's low nibble selects its entry: for example 5037h is entry 7 of FC5030. Entries contain:

```
u16 layout_length
layout[layout_length]
u16 palette_header
u16 palette_count
u16 palette_mask
palette_count * 16 * u16 color_words
u32 cell_stream_size
u8 no_remap
u8 derived_plane
u16 cell_count[4]
cell_stream[cell_stream_size - 10]
```

`fcimage.py` follows the game's loaders `0871:ADC0`, `ACAC`, `A3A2`, `A4D8`. Uninterpreted header bits retain their stored values. `fcencode.py` checks decoded output when re-encoding; do not fabricate a fresh header solely from the fields understood here.

## Layouts and cells

Layout: u16 header, u16 frame count, then u16 frame offsets relative to the layout. Each frame has u16 x,y,w,h followed by `w*h` cell words. Units are **8 pixels**. Signed x/y placements are stored as two's-complement words. Cells are **column-major** in the frame, not row-major.

Multiple frame offsets can reference the same picture. Export uses the first owner's filename; edit that owner rather than duplicating another frame's PNG. `fcencode.unique_frames()` preserves the identity. `frames.json` can supply top-left pixel placements in whole cells; the PNG's dimensions supply the new extent.

A cell word contains kind in bits 12–13, dictionary index and flip flags. Kind 0 has four bitplanes (colors 0–15), kind 1 three (0–7), kind 2 two (0–3), kind 3 one (0–1), with masks. The decoder's 32-byte state persists between codes, allowing reuse of prior columns. There is not an independent compressed bitmap per frame.

`fcimage.CellDecoder` and `fcencode.CellEncoder` are the authoritative codec pair. `fcencode.MAX_CELLS` limits dictionaries; the fitter also tracks decoded memory cost, with its established 160040-byte cap. Some entries contain unreferenced cells drawn directly by number. The editor refuses unsupported layouts rather than throwing those cells away.

## Palettes and display ownership

Color words are `0GRB`, four bits/channel. RGB conversion is `(R*17,G*17,B*17)`. Exported PNG indices 0–15 use palette 0, index 16 is transparent. An entry may have multiple palettes for different demons/rooms; their pixels are shared.

The renderer has sixteen hardware colors. `Image.owned()` identifies slots an entry may set. Other slots are supplied by the status panel or neighboring pictures. `no_remap=0` routes owned colors through the allocator; its remapping applies to kind-0 cells. Existing remapped entries use kind 0. Don't change borrowed colors just because they look unused in an isolated preview.

Walls use black, three set colors and the panel's white. Doors/stairs load without setting a fresh palette, so they must work with the current wall set. Rooms that remain behind a battle compete with the enemies' colors. Enemy allocation from higher free slots helps, but doesn't remove the limit. `winrooms.py` restricts battle backgrounds and folds the spring's high color into lower owned slots. `winshare.py` makes overlay pictures share their room's colors.

## Useful asset locations

| Resource | Function / conversion module |
| --- | --- |
| FC0000 entry 0 | Status-frame pieces; ten frames |
| FC0000 entry 2, FC0110 entry 9 | Compass base and related panel pieces |
| FC10s0 entry 0 | Wall perspectives for set s |
| FC10s0 entries 4,5 | Ceiling and floor |
| FC1300 | Staircases |
| FC1400 | Doors; Artwork gives one entry per wall set |
| FC2xxx | Demon sprites and palette variants |
| FC3000 | Shared scene plates including the full Windows staircase sources at frames 7,8 |
| FC4xxx | Event images and overlays |
| FC5000/5010/5020/5030 etc. | Rooms, shops, terminals and event backgrounds |
| FC50F0 entry 0 | Full title plate |
| FC50F0 entries 1–5 | Title-wave strips |
| FC50F0 entry 6 | Copyright overlay |

Door map bytes are remapped through `mapdoors.py`. The main scene plate view is 368×200 at (136,64). `wintex.py` derives the perspective geometry from the original wall masks instead of using screen captures.

## Windows sources

Windows `ddswin/fc/*.bin` concatenates BMP files, unrelated to the PC-98 FC cell container. `winbmps.py` extracts every BMP. `run/win_to_pc98.py` maps those files and frames to the PC-98 catalogue, crops monitor bezels, preserves aspect ratio, places sprites and records deliberate keep/crop choices.

Windows `ddswin/w/*.bmp` has 256×256 wall textures with 128×128 quadrants: upper-left ceiling, upper-right wall, lower-left door, lower-right floor. `dds.exe` contains four 16-byte texture slots per wall set. `wintex.texture_table()` checks and reads that actual table. The staircase `up/dn.bmp` files are partial crops; the conversion uses the full FC3000 sources.

The core sprite canvas is 256×256. Entry 2 uses 1:1 scale; entries 4 and 6 use 158/256 and 115/256. `winfit.py` aligns poses to one canvas anchor, fits single-palette demons jointly and dithers multi-palette demons against their selected palette. FC2630 deliberately keeps the original PC-98 drawing. The remake title retains the original title overlays/copyright where the accepted recipe specifies them.

## Conversion pipeline and reproducibility

1. `gfx.extract()` reads original FC data into indexed PNGs and manifests.
2. `win_to_pc98.py` produces the catalogue-matched Windows pictures; its `filter` and `fit` entry points apply the established keep/crop decisions.
3. `fcfit.py` places pictures, fits owned colors on the 4-bit lattice, performs ordered dithering on the screen-aligned 8×8 grid and chooses shared cells when the budget requires it.
4. `wintex.py`, `windoor.py`, `winfit.py`, `winrooms.py`, `winshare.py`, `winhud.py` perform their respective projections, corrections and shared-palette decisions.
5. `mkwinpatch.py` merges those outputs through `gfx.edited_files()` and writes the checked FC payload.
6. `winpatch.py` / the browser installer check old/new hashes, executable palette sites and map door bytes before writing the image.

`text/artwork-recipe.json` exposes the published selection of 21 fitted FC folders / 174 frame PNG identities and their palette/placement decisions without including image pixels. Contact sheets are excluded. The batch helper is intended to make refitting accessible to other artists. New fits may differ from the hand-tuned release. Codec, placement and palette tests establish format correctness, not artistic or gameplay correctness. Preview the rebuilt frames and their rooms/battles before releasing a new artwork patch.

For an accepted edited-frame workspace, each folder has `<entry:02d>_<frame:03d>.png`, optional `palettes.json`, optional `frames.json` and optional `extend.json`. `gfx.edited_files(root)` reads `root/gfx/`. Only slots the original entry owns may change. `extend.json` is used to create the per-wall door entries by cloning an established template; arbitrary count expansion is not inferred.

## Artwork editor

`fcedit.py` lists image files, entries, frames and palettes from the selected HDI. Export produces indexed PNGs and a manifest. Exact indexed imports preserve pixels; ordinary pictures are passed through the existing fitter with explicit placement, outline, palette, slot and dithering choices. The conversion preview is the fitted result, not the full-color source.

Changes stay staged until Write Image. It keeps a timestamped backup, rebuilds FC entries, updates FAT and can be opened again for a pixel/palette check. A new palette can recolor untouched frames sharing the entry; inspect all palette variants. A picture rendered alone can also depend on colors another resource sets, so it is not sufficient evidence of correct in-game sharing.
