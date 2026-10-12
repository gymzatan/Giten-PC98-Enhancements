# Analysis and conversion entry points

- `holdflow.py` follows the existing interpreter semantics, including calls, return stacks, dictionaries, formatted strings and wait-enabled/disabled roots.
- `mk_holds.py --native --src files/DDS98 --output build/japanese-holds.json` generates native Japanese pacing identities; `--english` generates English pacing from its own token positions.
- `win_to_pc98.py` contains the Windows BMP catalogue, sprite placement, scene cropping and established keep/crop decisions. The portable input is `inputs/ddswin/fc/`.

Run from the repository root. [Build instructions](../docs/modding/BUILD.md) connect these tools to the shared repair/graphics pipeline. They do not require a localization database.
