#!/usr/bin/env python3
"""Lines of dialogue that close by themselves, and the click waits that hold them.

    talkwait.py              every place the build adds a wait, with the line it holds

A line of dialogue stays on screen until the player clicks only because the script says so: command
210 in mode 1, `1E 10 01 01`, waits for a fresh left click with the prompt blinking at the bottom of
the window (tools/holds.py has the handler). Nothing waits at the end of a record - when a talk
record returns, the window goes - so the authors put 210 after the last line as well: 6017 times a
line is followed by 210 and then the end of its record. In 1061 places the 210 is missing, and the
line is drawn and gone before it can be read; MS0054/0/8 shows it within one record, where each
branch's last line ends 0A 210 000 except the one at 01D2, which ends 0A 000.

The build puts `1E 10 01 01` right after such a line - after the last token of the unit, so after the
whole of its translation - wherever all of these hold:

  the file is a script of the field, MS00**: the maps and their events. Not MS00D1 (the developer's
      picture viewer) nor the battle's message files MS00DB-MS00DF, whose holds follow their own
      rules (tools/holds.py); and none of the files whose records hand back to a menu of the
      engine's own - the shops and services of MS01** ("では、御用向きをどうぞ。" before the list of
      what is on offer) and the demon negotiation of MS6***, where the talk system carries on after
      the line - since the menu keeps the line on screen while it is up, and a click there would only
      be one more click per purchase;
  no script calls the record with 0D, so it is not a piece of some other record's dialogue that goes
      on after it returns;
  the record waits for a click somewhere already, so it is paced by clicks and the new wait is the
      same command its other lines use;
  the unit is followed by the end of the record, by 000, or by a jump straight to one.

A wait added after a unit runs whenever execution comes out of that unit; a branch to the command
after it passes it by, as it should - the wait belongs to that line alone.
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from units import script_units  # noqa: E402

SRC = os.path.join(os.path.dirname(HERE), "files", "DDS98")
CLICK = bytes([0x1E, 0x10, 0x01, 0x01])
HOLD, END, JUMP, CALL = 0x210, 0x000, 0x018, 0x00D
SKIP = ("MS00D1", "MS00DB", "MS00DC", "MS00DD", "MS00DE", "MS00DF")


def field_script(stem):
    return stem.startswith("MS00") and stem not in SKIP


def clicks(payload, toks):
    """Whether the record already waits for a click somewhere."""
    return any(t.code == HOLD and payload[t.start + 3:t.start + 4] == b"\x01" for t in toks)


def closes(toks, i):
    """Whether execution out of token i-1 reaches the end of the record at token i."""
    if i >= len(toks):
        return True
    t = toks[i]
    if t.code == END:
        return True
    if t.code == JUMP and t.rel:
        target = t.rel[0][1]
        at = {x.start: x for x in toks}.get(target)
        return at is None or at.code == END
    return False


def table(src=SRC):
    """{(stem, chunk, position): {token index: bytes to put after it}} - the waits the build adds, on
    the tokens of the game's own records (the ones script_units gives)."""
    records = [r for r in script_units(src) if field_script(r[0])]
    called = set()
    for stem, ci, _pos, (_rid, _cond, payload), toks, _units in records:
        for t in toks:
            if t.code == CALL and t.end - t.start >= 3:
                called.add((stem, payload[t.start + 1] & 0x0F, payload[t.start + 2]))
    out = {}
    for stem, ci, pos, (rid, _cond, payload), toks, units in records:
        if (stem, ci, rid) in called or not units or not clicks(payload, toks):
            continue
        adds = {u.last - 1: CLICK for u in units if closes(toks, u.last)}
        if adds:
            out[(stem, ci, pos)] = adds
    return out


def main():
    waits = table()
    places = [(key, i) for key, adds in sorted(waits.items()) for i in sorted(adds)]
    by_file = collections.Counter(key[0] for key, _i in places)
    print(f"{len(places)} 处，{len(waits)} 条记录：" + "、".join(f"{s}×{n}" for s, n in sorted(by_file.items())))
    units = {(s, c, p): (rec, toks, us) for s, c, p, rec, toks, us in script_units(SRC)}
    for key, i in places:
        (rid, _cond, _payload), _toks, us = units[key]
        u = next(u for u in us if u.last - 1 == i)
        print(f"  {key[0]}/{key[1]}/{rid}@{u.start:04X}  {u.jp[:60]!r}")


if __name__ == "__main__":
    main()
