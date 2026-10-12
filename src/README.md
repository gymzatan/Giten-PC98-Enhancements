# Redux source workspace

This directory contains the MIT-licensed enhancement implementation, conversion and analysis tools, editors, tests and authored patch recipes. It contains no game image, picture pixels, fonts, music or translation database.

Install the dependency lists at the repository root, then run commands from this directory. Start with the [build instructions](../docs/modding/BUILD.md); the [modder guide](../docs/modding/README.md) maps files, numeric fields, formulas, scripts, graphics and saves.

| Path | Purpose |
| --- | --- |
| `redux.py` | Entry points into the existing extraction and native build engines |
| [`tools/`](tools/README.md) | Shared patch definitions, parsers, conversion tools, editors and tests |
| [`run/`](run/README.md) | Script-flow analysis, pacing generation and Windows conversion catalogue |
| [`text/`](text/README.md) | Authored pacing, compatibility, negotiation and artwork recipes |
| `balance.json`, `balance_redesign.json` | Checked numeric edits |
| `files/`, `inputs/` | Your local game inputs; ignored |
| `build/`, `dist/`, graphics work directories | Generated outputs; ignored |

Installer document inputs are in `../docs/enhancements/`. The address and event ledgers are in `../docs/modding/`; `python tools/modmap.py` updates those ledgers directly from the patch definitions.
