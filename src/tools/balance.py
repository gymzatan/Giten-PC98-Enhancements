#!/usr/bin/env python3
"""A set of numeric edits to the game's data, kept apart from the translation.

An edit table is one JSON file — balance.json is just the one the build ships, and the editor can
save and open others:

    {"version": 2,
     "title": "降低头目难度",
     "note":  "why this table exists",
     "edits": {
       "P2177":      {"name": "但他林 第二形态", "note": "why",
                      "u8":  {"47": [25, 20]},      offset in the record: [original, edited]
                      "u16": {"0C": [403, 267]}},   the same, little-endian word
       "ET0004#102": {"name": "ディアラハン", "u8": {"02": [24, 20]}}}}

Every edit names the value it expects to find, so a wrong offset or data the edits were not written
for is refused instead of being written into blindly. A field put back to the value the game shipped
is not an edit at all: it is simply absent. Only numbers are touched, never any text, so the same
table fits the Japanese original and the Chinese build alike.

    balance.py [TABLE.json]     what each edit changes, against files/DDS98

tools/hdipatch.py applies and reverts them in a disk image.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import records  # noqa: E402

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BALANCE_PATH = os.path.join(WORK, "balance.json")
SRC = os.path.join(WORK, "files", "DDS98")
WIDTHS = {"u8": 1, "u16": 2, "u32": 4}
KEY_OF = {w: k for k, w in WIDTHS.items()}
VERSION = 2


class BalanceError(ValueError):
    pass


def empty(title=""):
    return {"version": VERSION, "title": title, "note": "", "edits": {}}


def load(path=BALANCE_PATH):
    if not os.path.exists(path):
        return empty()
    data = json.load(open(path, encoding="utf-8"))
    if data.get("version") != VERSION:
        raise BalanceError(f"{path}: 这是第 {data.get('version')} 版的修改表，本工具用第 {VERSION} 版")
    data.setdefault("title", "")
    data.setdefault("note", "")
    data.setdefault("edits", {})
    return data


def save(data, path=BALANCE_PATH):
    out = {"version": VERSION, "title": data.get("title", ""), "note": data.get("note", ""),
           "edits": {}}
    for target in sorted(data["edits"]):
        entry = data["edits"][target]
        keep = {"name": entry.get("name", target)}
        if entry.get("note"):
            keep["note"] = entry["note"]
        for key in ("u8", "u16", "u32"):
            if entry.get(key):
                keep[key] = {o: entry[key][o] for o in sorted(entry[key], key=lambda s: int(s, 16))}
        out["edits"][target] = keep
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, path)
    return path


def merged(*tables):
    """One table holding the edits of several (make.py: what a package's image carries, for the editor). A record
    named by two of them takes the values of both, its notes joined, as long as no byte is edited by both
    (难度调整's resists and 再平衡's design of 但他林 II); one they both edit is refused."""
    out = empty(" + ".join(t["title"] for t in tables if t.get("title")))
    notes = {}                                  # target -> [(table title, note)] of every table naming it
    for t in tables:
        for target, entry in t["edits"].items():
            notes.setdefault(target, []).append((t.get("title", ""), entry.get("note", "")))
            if target not in out["edits"]:
                out["edits"][target] = entry
                continue
            have = out["edits"][target]
            taken = {b for off, w, _a, _b in edits(have, target) for b in range(off, off + w)}
            if any(b in taken for off, w, _a, _b in edits(entry, target) for b in range(off, off + w)):
                raise BalanceError(f"{target}：两张修改表改了同一处")
            both = dict(have)
            for key in WIDTHS:
                if key in entry:
                    both[key] = {**have.get(key, {}), **entry[key]}
            # each table's note under its title: what one says holds for its own values only
            both["note"] = "\n".join(f"【{title}】{note}" if title else note for title, note in notes[target] if note)
            out["edits"][target] = both
    return out


def edits(entry, target):
    """[(offset, width, original, edited)] of one entry, in offset order."""
    out = []
    for key, width in WIDTHS.items():
        for off, pair in entry.get(key, {}).items():
            if not isinstance(pair, list) or len(pair) != 2:
                raise BalanceError(f"{target} {key} {off}: 应当写成 [原值, 改后值]")
            for v in pair:
                if not 0 <= v < 256 ** width:
                    raise BalanceError(f"{target} {key} {off}: {v} 放不进 {width} 个字节")
            out.append((int(off, 16), width) + tuple(pair))
    return sorted(out)


def by_file(data):
    """{data file: [(target, entry)]} so a file is opened once however many records it holds."""
    out = {}
    for target, entry in data["edits"].items():
        out.setdefault(records.file_of(target), []).append((target, entry))
    return out


def state(plain, target, entry):
    """'original', 'edited', 'mixed', or a description of the values that match neither.

    An edit whose two halves are the same value says only "this field is to hold that value" — it
    cannot tell one state of the record from the other, so it is not read as either."""
    seen, odd = set(), []
    for off, width, original, edited in edits(entry, target):
        now = records.read(plain, target, off, width)
        if original == edited:
            continue
        if now == original:
            seen.add("original")
        elif now == edited:
            seen.add("edited")
        else:
            odd.append(f"{off:02X}={now}（应为 {original} 或 {edited}）")
    if odd:
        return "unknown: " + ", ".join(odd)
    if seen == {"original", "edited"}:
        return "mixed"
    return seen.pop() if seen else "original"


def apply_to(plain, target, entry, revert=False):
    """Write the wanted values into a decrypted file; True when anything changed."""
    want = 2 if revert else 3            # index into (off, width, original, edited)
    changed = False
    for edit in edits(entry, target):
        off, width, target_value = edit[0], edit[1], edit[want]
        if records.read(plain, target, off, width) != target_value:
            records.write(plain, target, off, width, target_value)
            changed = True
    return changed


def plan(data, plain_of):
    """[(file, plaintext, target, entry)] with every record read and checked: one that holds neither
    the original nor the edited values stops the whole table.

    This is for writing a table into an image sight unseen — tools/hdipatch.py and the .bat patches.
    The editor does not check: it has the image open in front of it and shows what each field holds,
    so what it writes is what the user is looking at."""
    out = []
    for stem, items in sorted(by_file(data).items()):
        plain = plain_of(stem)
        for target, entry in items:
            now = state(plain, target, entry)
            if now.startswith("unknown"):
                raise BalanceError(f"{target}：不是这些改动所针对的数据 — {now}")
            out.append((stem, plain, target, entry))
    return out


def apply_table(data, plain_of, revert=False):
    """Write a whole table into the files it names: (records written, files touched)."""
    wrote, stems = [], []
    for stem, items in sorted(by_file(data).items()):
        plain = plain_of(stem)
        for target, entry in items:
            if apply_to(plain, target, entry, revert=revert):
                wrote.append(entry.get("name", target))
                if stem not in stems:
                    stems.append(stem)
    return wrote, stems


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else BALANCE_PATH
    data = load(path)
    print(f"{path}　「{data['title'] or '未命名'}」　{data['note']}")
    total = 0
    for stem, items in sorted(by_file(data).items()):
        plain = records.plain_of(open(os.path.join(SRC, stem + ".BIN"), "rb").read())
        for target, entry in items:
            print(f"\n{target} 「{entry.get('name', target)}」  [{state(plain, target, entry)}]  "
                  f"{entry.get('note', '')}")
            for off, width, original, edited in edits(entry, target):
                now = records.read(plain, target, off, width)
                print(f"    {off:02X}  {original:5d} -> {edited:5d}   （现在 {now}）")
                total += 1
    print(f"\n{len(data['edits'])} 条记录，{total} 个数值")
