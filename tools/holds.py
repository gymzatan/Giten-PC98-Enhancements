#!/usr/bin/env python3
"""How long each kind of battle message stays on screen: the table in text/holds.json and how the build
applies it.

How the game holds a line. Nothing in the code does: the routines that put a battle message up return at
once. main 0x2E57C does leave a count in ds:0x1bbc (its first argument, through main 0x2E468), which
main 0x2E4F0 counts down once per pass of the main loop before it closes the message window - but that
count only decides when an idle window goes away; the window handle ds:0x1bba is used by nothing
outside that window module, so no battle code waits for it, and the next message simply clears the
window and writes over it. The only hold is script command 210, `1E 10 01 <mode> [count]`, handled by
main 0x2221A:

  mode 2  `count` vsync frames; the left button held or pressed, or the right button held, ends it early
  mode 1  until the left button is pressed anew (main 0x0D852 keeps the press edge per frame), or while
          the right button is held; a prompt blinks at the bottom centre of the window (main 0x29BE2)

A frame is 1/56.42 s on the PC-98's 400-line display. The battle's message files use 210 only after a
damage line (60 frames), before a defeat line (100) and in a few special lines, so every other line is
replaced by the next as fast as the machine can draw.

Where a hold can go. 210 waits where it stands only while `[0x1cea]` is 1, and only two places set it:
main 0x2E57C while it runs a message record for the battle, and ov16:0455E while it shows MS00DB. Anywhere
else it sets the wait up and returns -3 at once. What that does depends on who runs the record: the pass
of ov16:04460, which works out MS00DB 00 for a combatant, stops on it for good (and a mode-1 prompt set
up by then stays armed); the record runner main 0x2080C takes -3 as "go on next frame", lets the state
machine serve the wait, and then carries on after the command - so there the hold is a real wait, it just
does not hold up anything outside the run. Every run is started by main 0x1D406, whose callers are
ov16:0455E and ov16:04460 (MS00DB 00), main 0x1B91E (for main 0x2E57C), and main 0x2080C, 0x209CE and
0x20CFA, which run records named by scripts or queued by main 0x2E52A (MS00DD 59, MS7F04 10 and 11). A hold
added to a record one of those reaches would stop the computing pass early or add a wait somewhere else
- to the end-of-battle summary, which is left to its click. So a hold may be added, removed or made a
click wait only in records nothing runs without waiting:

  MS00DC, MS00DD, MS00DE   run from main 0x2E57C (skills and items through main 0x30420, defeat lines
                           through main 0x305A0) and named by no script but their own. MS00DD 59, the
                           end-of-battle summary, and what it reaches run without waiting; run/holdmap.py
                           checks that no hold of the table is reachable from there.
  MS00DF 03                run only by main 0x2FBBD, through main 0x2E57C.

In MS00DB and MS00DF 00-02, and in any other record a run without waiting reaches, only the length of one
of the game's own mode-2 holds may change: every run is left where it was - a pass that stops at the
command still stops there, and a run that waits there still waits, for as long as the table says.

The table. text/holds.json has one entry per kind of message, and one per hold of the game's own:

  {"message": "MS00DE/0/7@0038", "hold": 60, "after": ["MS00DE/0/7@0038"], "text": "…"}
  {"at": "MS00DD/0/79@0000", "original": 100, "hold": 100, "text": "…"}

"hold" is what to do: 2-255 frames (mode 2), "click" (mode 1), or 0 for no hold. A kind of message is the
translation unit that ends its sentence, or - where a sentence ends with a dictionary word outside every
unit - that word's command; "message" names it as FILE/chunk/record@offset with the offsets of the
original record, as tools/ddsdis.py prints them. "after" lists where the build puts its hold: right after
a unit (whatever its translation became) or right after a command outside the units that goes on to the
next command by itself or returns to it (text, 00A, 101, 102, 23E, dictionary words 001-008, 00D). A hold
put after something runs whenever execution comes out of it, and not when a branch jumps to what follows.
run/mk_holds.py works "after" out; it is not meant to be edited. An entry with "original" is the game's
own command 210 at "at", with the count it has in the game. Every other field only describes the entry.
"""
import json

PATH = "text/holds.json"
FILES = ("MS00DC", "MS00DD", "MS00DE")           # holds may be added, removed and made click waits here
RECORDS = (("MS00DF", 0, 3),)                    # and in these records of the files below
COUNT_ONLY = ("MS00DB", "MS00DF")                # elsewhere only the length of an existing hold may change
GOES_ON = (0x00A, 0x101, 0x102, 0x23E, 0x00D) + tuple(range(0x001, 0x009))
MIN_FRAMES = 2
CLICK = "click"


class HoldError(ValueError):
    pass


def changeable(key):
    """Whether holds may be added to and removed from the record (stem, chunk, record)."""
    return key[0] in FILES or key in RECORDS


def goes_on(t):
    """Whether execution comes out of a token into the next one - by itself, or by returning to it."""
    return t.kind != "cmd" or t.code in GOES_ON


def encode(hold):
    """Command 210 for a hold: frames in mode 2, a click wait in mode 1."""
    if hold == CLICK:
        return bytes([0x1E, 0x10, 0x01, 0x01])
    return bytes([0x1E, 0x10, 0x01, 0x02, hold])


def valid_hold(hold):
    return hold == CLICK or (isinstance(hold, int) and not isinstance(hold, bool)
                             and (hold == 0 or MIN_FRAMES <= hold <= 255))


def parse_place(at):
    """'MS00DD/0/22@0009' -> ((stem, chunk, record), offset)."""
    try:
        path, off = at.split("@")
        stem, ci, pos = path.split("/")
        return (stem, int(ci), int(pos)), int(off, 16)
    except (ValueError, AttributeError):
        raise HoldError(f"{at}: not FILE/chunk/record@offset") from None


def load(path=PATH):
    """The table of a file, as parse() gives it."""
    return parse(json.load(open(path, encoding="utf-8")))


def parse(entries):
    """{(stem, chunk, record): {"after": {offset: (hold, message)}, "original": {offset: (hold, count)}}}."""
    table = {}
    messages = set()
    for entry in entries:
        if not isinstance(entry, dict) or not valid_hold(entry.get("hold")):
            raise HoldError(f"{entry}: hold must be 0, {MIN_FRAMES}-255 or \"{CLICK}\"")
        hold = entry["hold"]
        if "original" in entry:
            key, off = parse_place(entry.get("at"))
            where = entry["at"]
            if not changeable(key) and key[0] not in COUNT_ONLY:
                raise HoldError(f"{where}: not one of the battle's message files")
            if not changeable(key) and (hold == 0 or hold == CLICK):
                raise HoldError(f"{where}: in {key[0]} a hold can be made longer or shorter, not removed or "
                                "made a click wait")
            slot = table.setdefault(key, {"after": {}, "original": {}})["original"]
            if off in slot:
                raise HoldError(f"{where}: listed twice")
            slot[off] = (hold, entry["original"])
            continue
        message = entry.get("message")
        if not isinstance(message, str) or message in messages:
            raise HoldError(f"{entry}: every kind of message needs its own \"message\"")
        messages.add(message)
        places = entry.get("after")
        if not isinstance(places, list) or not places:
            raise HoldError(f"{message}: \"after\" must list where the hold goes")
        for at in places:
            key, off = parse_place(at)
            if not changeable(key):
                raise HoldError(f"{message}: {at} is in a record where holds cannot be added")
            slot = table.setdefault(key, {"after": {}, "original": {}})["after"]
            if off in slot:
                raise HoldError(f"{at}: the place of two holds ({slot[off][1]} and {message})")
            slot[off] = (hold, message)
    return table


def edits(key, payload, toks, units, entries):
    """(replace, append) for one record's entries, each checked against the record, as {token index: bytes}:
    an original hold must be the game's mode-2 command 210 with the count the table says, and is replaced
    by the hold the table asks for or by nothing; an added hold goes after the last token of the unit
    starting at its offset, or after the token there when no unit starts there - a token outside every
    unit that goes on by itself."""
    starts = {t.start: i for i, t in enumerate(toks)}
    unit_at = {u.start: u for u in units}
    in_unit = {i for u in units for i in range(u.first, u.last)}
    replace, append = {}, {}
    for off, (hold, message) in entries["after"].items():
        where = f"{key[0]}/{key[1]}/{key[2]}@{off:04X}"
        if off in unit_at:
            i = unit_at[off].last - 1
        elif off in starts:
            i = starts[off]
            if i in in_unit:
                raise HoldError(f"{message}: {where} is inside a translation unit")
            if not goes_on(toks[i]):
                raise HoldError(f"{message}: {where} does not go on to the next command by itself")
        else:
            raise HoldError(f"{message}: {where} is not the start of a token")
        if hold:
            append[i] = encode(hold)
    for off, (hold, count) in entries["original"].items():
        where = f"{key[0]}/{key[1]}/{key[2]}@{off:04X}"
        i = starts.get(off)
        raw = payload[toks[i].start:toks[i].end] if i is not None else b""
        if i is None or toks[i].code != 0x210 or raw[:4] != b"\x1e\x10\x01\x02" or len(raw) != 5:
            raise HoldError(f"{where}: not the game's own mode-2 hold")
        if raw[4] != count:
            raise HoldError(f"{where}: the game holds {raw[4]} frames here, the table says {count}")
        if hold != count:
            replace[i] = encode(hold) if hold else b""
    return replace, append
