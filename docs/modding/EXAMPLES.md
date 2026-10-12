# Small modification examples

Run from `src/`. Add `tools/` to the Python import path. These examples call the existing formats and edit engines; they do not infer new offsets or write a complete translation.

## Inspect one event record

```powershell
python redux.py inspect-script files/DDS98/MS0032.BIN --record 0x26
```

The output includes the conditional-record metadata, original token start/end offsets, command IDs and branch field/destination pairs. IDs shown by the grammar are logical VM codes; a prefixed code's raw bytes differ from its integer code. A record in another chunk needs `--chunk` explicitly.

To inspect an event repair, look up that file/record in `../docs/modding/Event-Edits.json`, then read its corresponding class in `storyfix.py` or `checkfix.py`. For a translated record, re-tokenize and locate the structural precondition rather than copying its Japanese byte position.

## Create and apply a checked numeric table

This example changes one demon's level by one, using the value read from the supplied image as its explicit precondition. Replace the target with the demon you intend to edit. It changes a copy and lets `GameImage.save()` retain the copy's pre-edit state too.

```python
import shutil
import sys
sys.path.insert(0, "tools")
import balance, gameimage, records

shutil.copy2("inputs/Game.hdi", "build/MyMod.hdi")
image = gameimage.GameImage("build/MyMod.hdi")
target = "P2177"
plain = image.plain(records.file_of(target))
old = records.read(plain, target, 0x47, 1)
if old >= 99:
    raise ValueError("Choose a level below 99")
table = balance.empty("One demon level adjustment")
table["edits"][target] = {"name": target, "u8": {"47": [old, old + 1]}}
balance.save(table, "build/MyMod.json")
wrote, stems = balance.apply_table(table, image.plain)
backup = image.save(stems)
print(wrote, backup)
```

Create `build/` beforehand. `u8/u16/u32` widths are part of the schema and offset strings are hexadecimal. The JSON schema's `version` field is retained by `balance.empty()`; it describes the serialized format, not a release number. The same file can be inspected/applied/reverted by:

```powershell
python tools/hdipatch.py status build/MyMod.hdi build/MyMod.json
python tools/hdipatch.py revert build/MyMod.hdi build/MyMod.json
```

For an ET entry, use `ET0004#102` or another decimal record index. `records.base_of()` resolves its pointer, and only the numeric header's length can be edited. A character's displayed power may come from a runtime formula instead; changing an unrelated disk byte will not change that formula.

## Export a frame from a supplied HDI

```python
import sys
from pathlib import Path
sys.path.insert(0, "tools")
import fcimage, gfx
from fat12 import open_hdi, Fat12

raw, header, disk, part = open_hdi("inputs/Game.hdi")
fs = Fat12(disk, part)
entry = fs.find("DDS98/FC5030.BIN")
if entry is None:
    raise ValueError("FC5030 was not found")
blob = bytes(fs.read_chain(entry["cluster"], entry["size"]))
image = fcimage.Image(fcimage.entries(blob)[0])
Path("build/export").mkdir(parents=True, exist_ok=True)
gfx.frame_png(image, 0).save("build/export/FC5030_e00_f000.png", transparency=16)
```

Use the artwork editor for replacing it. Keep indexed palette order and index-16 transparency for a pixel-exact import. For arbitrary RGB pictures, preview all palette variants and verify the cell budget before writing.

## Change a formula

Start at the block in `rebalance.py` listed by `EXECUTABLE-MAP.md`. The assembly emitter labels, relocation holes, calling convention, x87-emulator encoding, clamps and rounding all belong to that implementation. Edit the coefficient or intended rule there, run its existing CPU tests with adjusted design expectations, rebuild native payloads and regenerate the browser plan. Do not directly edit a base64 payload or replace an instruction's immediate without checking the entire affected routine.

## Share a mod

Publish authored code, checked numeric tables, structural script edits or a patch, with the needed input and dependencies stated. Avoid whole game files/images. If combining with Redux, retain MIT attribution and identify the changed feature. Include a concrete reproduction and describe which scenes or formula thresholds were tested. Use the source ledgers to explain conflicting sites rather than accepting all unrecognized bytes.
