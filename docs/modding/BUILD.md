# Build from source

Use Python with Tk support for the editors. The native build is verified with Python 3.13. Install the dependencies from the repository root, then enter the `src/` workspace. All later commands and input/output paths in this guide are relative to `src/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# Optional: CPU tests and Windows executable packaging
python -m pip install -r requirements-dev.txt
cd src
```

Node is needed only to run the browser patch under `webpatch_run.js`; the distributed HTML pages themselves need no Node or Python.

## Inputs and directories

The source contains no game image or artwork. Supply a clean Japanese PC-98 HDI, and the English BPS output if building the English payloads. Obtain the English translation separately from [Sneikkimies' translation release](https://www.romhacking.net/translations/7343/). Keep your original image unchanged.

```powershell
python redux.py extract inputs\Japanese.hdi files
python redux.py extract inputs\English.hdi files\English
```

The main build expects `files/DDS98/`. These files supply checked executable bytes, numeric baselines and original graphics. The English reference is separately extracted and normalized by `english_enhancements.py`; do not replace the Japanese reference directory with it.

| Path relative to `src/` | Purpose |
| --- | --- |
| `tools/` | Parsers, patch definitions, payload planning, editors and tests |
| `run/holdflow.py`, `run/mk_holds.py` | Existing interpreter-flow analysis and pacing recipe generation |
| `run/win_to_pc98.py` | Windows BMP catalogue, placement, matching and conversion decisions |
| `text/holds.json` | Authored Japanese battle pacing recipe, using original token identities |
| `text/talkgaps.json` | Authored Japanese/English missing negotiation prompts |
| `text/english_compatibility.json` | Checked repairs for the exact English reference |
| `text/artwork-recipe.json` | Frame selection and authored palette/placement decisions; no pixels |
| `balance.json`, `balance_redesign.json` | Checked numeric adjustments for Fixes and Rebalance |
| `build/`, `dist/`, `files/`, `inputs/` | Local inputs and generated outputs; never committed |

`../docs/enhancements/` supplies the installer documentation. `../docs/modding/` contains this reference and the generated address/event ledgers. These document paths are resolved from the source files themselves; generated game data stays inside the ignored `src/` workspace.

## Native game-file payloads

```powershell
python redux.py build-files --src files/DDS98 --holds text/holds.json --output build/fixed
python redux.py build-files --src files/DDS98 --holds text/holds.json --output build/rebalance --rebalance
```

`nativebuild.build()` calls the existing repair modules in `buildcore.repair_files()`. `rebalance_on=True` means the complete native Fixes + Rebalance output, not a patch applicable to an untouched image. `mkenhancements.py` computes the delta and prerequisite guards for the public Rebalance installer.

For another *valid* native English script set, first generate pacing using its own token positions:

```powershell
python run/mk_holds.py --english --src files/English/DDS98 --output build/english-holds.json
python redux.py build-files --src files/English/DDS98 --holds build/english-holds.json --output build/english-fixed --english
```

The tested translation has specific malformed counts/branches; its ordinary extraction cannot be passed straight to that command. Use `english_enhancements.build()` through the full package command below. Its exact build-reference hash is intentional; it is separate from the runtime installer's structural matching.

## Windows artwork

Copy your Windows installation's entire `ddswin` directory to `inputs/ddswin/`, including `dds.exe`, `fc/` and `w/`. The tools read that copy. The BMP catalogue, projection, fitting, palette sharing and FC encoding source are included.

```powershell
python tools/artbuild.py
```

Run this in a fresh source checkout. It extracts `gfx_orig/`, prepares the catalogue in `gfx/`, writes the raw conversion in `gfx_win/`, fits selected frames into `gfx_win_fit/`, and builds walls, doors, stairs and HUD assets. `mkwinpatch.py` then merges `wingfx_new/`, `windoors/`, `gfx_win_fit/`, `winhud/` into `build/winpatch.zip`.

The batch helper re-fits pictures using the recorded palette decisions and the existing fitter. It is a new conversion, not a promise of pixel-identical reconstruction of every hand-tuned release frame. The [graphics guide](GRAPHICS.md) explains how to inspect and refine it. If you already have an accepted edited-frame workspace, run the individual later stages and `python tools/mkwinpatch.py` directly. Do not publish generated art under the code's MIT license.

## Build the three offline installers

With the Japanese files, verified English HDI and `build/winpatch.zip` prepared:

```powershell
python tools/mkenhancements.py --english-image inputs/English.hdi
```

Outputs are the four individual ZIP packages plus `dist/Giten-Megami-Tensei-Redux.zip`, and editable installer folders under `dist/English/`. The complete ZIP includes all four standalone patch pages, shared documentation and a `START HERE.html` guide. The builder keeps its accepted filenames: `(EN)` refers to the interface/documentation language. Its input handling preserves Japanese or tested English game text.

`--pack-only` reuses already built payload directories after a documentation or interface edit. It does not validate or synthesize missing game inputs. `tools/webpatch.js` owns HDI/FAT operations; `tools/enhancement_runtime.js` applies the plans exported by `enhancement_plan.py`. `webpayload.py` packs the same manifest/blobs as the existing release.

To rebuild only the complete ZIP after editing its guide, with the four already built ZIPs present:

```powershell
python tools/mkenhancements.py --bundle-only
```

This reads `dist/Giten Fixes (EN).zip`, `dist/Giten Rebalance (EN).zip` `dist/Giten Windows Artwork (EN).zip` and `dist/Giten Add-ons (EN).zip`, renders the existing English documents, and adds `docs/enhancements/bundle/START HERE.html` and `START HERE.txt` from the repository. It needs no game disk or payload rebuild. The source HTML patch bytes are copied unchanged. `SHA256SUMS.txt` inside the complete ZIP covers its files.

## Editors

Generate the numeric editor database locally from explicit files:

```powershell
python tools/prepare_editor.py --baseline files/DDS98 --names files/English/DDS98
python tools/demoned.py
python tools/fcedit.py inputs/Game.hdi
```

Use `--names files/DDS98` for Japanese names. The baseline supplies original numbers, while `--names` supplies displayed names/descriptions. Multiline English descriptions are supported. The historical `zh` serialized slot is retained as the display-language slot so the data/editor interfaces stay consistent; no translation database is shipped. Enum IDs keep Japanese lookup labels where a confirmed English label has not been recorded. Race/deity guide annotations are omitted rather than fabricated.

The artwork editor reads everything from its selected image. Both editors stage changes before writing and keep a backup when writing. To build Windows executables after preparing data:

```powershell
python tools/build_editor.py numeric --edition main
python tools/build_editor.py numeric --edition rebalance
python tools/build_editor.py artwork
```

The numeric editor's embedded baseline contains game-derived data; generated executables are not asset-free source artifacts.

## Verification

```powershell
python tools/ddsfile.py check files/DDS98
python tools/checkvm.py
python tools/asm86_test.py
python tools/fcencode_test.py
python tools/fcedit_test.py inputs/Game.hdi
python tools/exekeys_test.py
python tools/statfix_test.py
python tools/rebalance_test.py
python tools/modmap.py
```

After building the installers, the existing structural web tests can also be run with explicit inputs:

```powershell
python tools/enhancements_test.py inputs/Japanese.hdi
python tools/english_enhancements_test.py inputs/English.hdi
```

They exercise the actual embedded HTML code under Node, including longer English strings, unrelated records, relocated branches and rejection of conflicting required instructions.

Game-dependent tests require the extracted Japanese reference in `files/DDS98/`. The FC editor test operates on a temporary copy and checks export/import/write/readback, the backup and an untouched file. The CPU tests exercise the actual patched routines with Unicorn. The full FC corpus round trip is available with `fcencode_test.py corpus`; run it when changing the codec, not for every prose edit.

## Optional controls and target prompt

The fourth installer is `Apply Add-ons.html`. Its independent checkboxes use the shared `addons.py`, `targetprompt.py`, `gamepad.py` and `webpatch.js` rules. The English builder obtains the Japanese and English message files and the DOSBox-X mapper from those modules; `webpayload.addon_part()` serializes the same site definitions for both installer builders.

Run `python tools/gamepad_test.py`, `python tools/targetprompt_test.py` and `python tools/holdshow_test.py` from `src/` to check assembled code, executable conflicts and pacing. They read your extracted Japanese `files/DDS98/DDS98.EXE`; the add-on install/remove checks also use your copy at `inputs/Japanese.hdi`. The integration command `python tools/enaddons_test.py --japanese inputs/Japanese.hdi --english inputs/English.hdi` exercises the four generated English installers against your own reference disks, including adding/removing each option and matching the Python output.

`dosbox/defaults.map` is the emulator's saved default key map. `mkmapper.py` preserves those keyboard bindings and adds the XInput assignments; its output is included in the fourth ZIP and complete bundle. See [controls and executable locations](CONTROLS.md) for the implementation map.
