"""Generate editor reference data from explicit, user-supplied extracted files.

python tools/prepare_editor.py --baseline files/DDS98 --names files/English/DDS98
The baseline supplies original numeric values; names supplies the display language.
No image is modified and no translation database is required.
"""
import argparse
import base64
import json
from pathlib import Path

import etfields
import mkmoon
import records
import tables

HERE = Path(__file__).resolve().parent


def names(src, stem):
    blob = (src / (stem + ".BIN")).read_bytes()
    if stem.startswith("P2"):
        return {"name": next(tables.P2File(stem, data=blob).units()).jp}
    prefix = tables.item_prefix if stem == "ET0001" else lambda _e: tables.SKILL_HEADER
    parser = tables.StringTableFile(stem, [0], ["name", "desc"], prefix, data=blob, newlines=True)
    return {u.id: u.jp for u in parser.units()}


def build(baseline, display):
    baseline, display = Path(baseline), Path(display)
    out = {}
    for path in sorted(baseline.glob("P2*.BIN")):
        stem = path.stem
        jp, shown = names(baseline, stem), names(display, stem)
        out[stem] = {"jp": jp["name"], "zh": shown["name"],
                     "base": base64.b64encode(records.plain_of(path.read_bytes())).decode("ascii")}
    for stem in ("ET0001", "ET0004"):
        jp, shown = names(baseline, stem), names(display, stem)
        plain = records.plain_of((baseline / (stem + ".BIN")).read_bytes())
        for index, start in enumerate(etfields.pointers(plain)):
            uid = f"{stem}/0/{index}"
            if uid + "/name" not in jp:
                continue
            out[f"{stem}#{index}"] = {
                "jp": jp[uid + "/name"], "zh": shown[uid + "/name"],
                "jp_desc": jp.get(uid + "/desc", ""), "zh_desc": shown.get(uid + "/desc", ""),
                "base": base64.b64encode(plain[start:start + etfields.head_len(plain, start, stem)]).decode("ascii")}
    return {"records": out}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--names", required=True, type=Path)
    args = parser.parse_args()
    data = build(args.baseline, args.names)
    (HERE / "gamebase.json").write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    (HERE / "moon.json").write_text(json.dumps({"rows": mkmoon.table(args.baseline / "ET0003.BIN")}) + "\n", encoding="utf-8")
    print(f"Prepared {len(data['records'])} records for the numeric editor.")


if __name__ == "__main__":
    main()
