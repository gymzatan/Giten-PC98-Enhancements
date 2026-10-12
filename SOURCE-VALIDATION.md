# Source verification

The `src/` source workspace was exercised independently of the private localization tree. The full package builder generated three offline HTML/ZIP packages using explicit Japanese and English inputs and an accepted local artwork payload.

All native game-file outputs matched the accepted releases byte for byte: Japanese Fixes 132 files, Japanese Fixes + Rebalance 165, English Fixes 148, English Fixes + Rebalance 181. The English normalization and pacing preparation ran through the exported modules, not a precomputed replacement engine.

The relocated `src/` workspace also passed its CLI path checks, regenerated identical address/event ledgers, reproduced all four native file sets, and retained the exact embedded core and payload in all three generated HTML installers. Documentation inputs were resolved from `docs/enhancements/` outside the source workspace.

The following existing checks passed from the source directory:

- `asm86_test.py`: 67 known instruction encodings, branch assembly and refusal cases.
- `fcencode_test.py`: 30,000 cell-code cases, edited entries, mixed cell kinds and resized frame boxes.
- `exekeys_test.py`: patched keyboard and advance-wait routines on the emulated CPU.
- `bagexpand_test.py`: expanded inventory, save/load and temporary item transfer.
- `checkfix_test.py`: the checked story EXP setter/dispatch.
- `statfix_test.py`: equipment, combat and attribute repair paths.
- `rebalance_test.py`: actual patched formula/growth/summon/COMP paths and threshold cases.
- `fcedit_test.py` with the verified English image: export, exact indexed import, ordinary-image conversion, image write/readback, backup and untouched-file checks.

The numeric editor's generated reference database was opened successfully with 1,485 records, 309 named skills and 744 named items. English names/descriptions came from the player's reference image. `src/tools/gamebase.json` and `src/tools/moon.json` are generated locally and excluded from source distribution.

The original gameplay release verification remains in [VALIDATION.md](VALIDATION.md). Those startup and browser-installation receipts are reused. This source release is not a new full playthrough. The conversion code and authored choices are shared, but a new artwork fit is not claimed to be pixel-identical to every curated release frame.
