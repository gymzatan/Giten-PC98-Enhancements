# Source modules

The code is MIT licensed. Inputs and generated game-derived data are excluded. See [the modder guide](../../docs/modding/README.md) for building, offsets and examples.

| Area | Modules |
| --- | --- |
| Shared build | `buildcore`, `nativebuild`, `english_enhancements`, `mkenhancements`, `webpayload` |
| Disk and executable formats | `fat12`, `fat12w`, `gameimage`, `mz`, `mzinfo`, `ddscrypt` |
| Scripts | `ddsfile`, `ddsvm`, `ddsgrammar`, `ddstext`, `units`, `textbuild`, `checkvm`, `ddsdis` |
| Game fixes | `exekeys`, `bagexpand`, `exefix`, `storyfix`, `checkfix`, `statfix`, `skillfix`, `expshow`, `expgap`, `ctxfree`, `vmswap`, `moonfast`, `holds`, `talkwait`, `talkgaps` |
| Graphics and palette repairs | `battlefield`, `worldbackdrop`, `nospace`, `slotorder`, `mapdoors` |
| Numeric edits and redesign | `records`, `p2fields`, `etfields`, `balance`, `poolfix`, `rebalance` |
| Artwork | `fcimage`, `fcencode`, `fcfit`, `gfx`, `winbmps`, `wintex`, `windoor`, `winfit`, `winrooms`, `winshare`, `winhud`, `mkwinpatch`, `winpatch`, `winsource`, `winresult`, `artbuild` |
| Editors | `demoned`, `gamedata`, `prepare_editor`, `fcedit`, `build_editor` |
| Assembly and analysis | `asm16`, `asm86`, `rmtest`, `int86scan`, `vmscan`, `mkgrammar`, `fileref`, `msdump`, `modmap` |
| Web runtime | `webpatch.js`, `enhancement_runtime.js`, English message map and `webpatch_run.js` |

`*_test.py` files contain the existing codec, editor and CPU checks. Game-dependent tests expect the explicit extracted reference in `files/DDS98/`, run from `src/`. Create `build/` before running the executable CPU tests.

Some internal field labels/comments retain original Japanese or development-language notation. These are lookup anchors, not a bundled translation database. The public GUI presentation and detailed user/modder documents are in English.
