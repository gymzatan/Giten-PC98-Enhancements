#!/usr/bin/env python3
"""Negotiation lines a demon's script asks for that none of the files it loads holds, supplied from
text/talkgaps.json and written into the build.

    talkgaps.py                 every line: file, chunk:record, the Chinese, where it is asked
    talkgaps.py check [HDI]     the table's own checks; with a built image, also every negotiation that
                                talk starts, followed through the image's own files: no question it
                                reaches is empty where a menu comes next, and each added line is listed
                                with the records that reach it

How a negotiation finds its lines. The talk command starts record E0:00 of the demon's negotiation pack.
A call `0D sel rec` (or `0C`, or a jump-list entry) with sel E0-EF reads record rec of the pack's slot
sel-E0 (1603:838C -> ov30:018C). The pack is built when the negotiation starts (ov33:0046): the 16
chunks of MS6000, then of the two MS60xx and the MS61xx files that ET0007 names for the demon's talk type
(P2 byte 73h; a row is [a][b][c], FF = none), then of ID<demon number> when the game has one; a record of
a later file replaces the one with the same id (1603:9458 -> 962E). MS6000 holds a lone 00 for many
records, to be filled by the files after it. Where none of them does, the call shows nothing - and when
a menu comes next, the choices open with no question over them. The game ships such gaps: several ID
files are copies of another demon's script (浮遊霊's ID012B is byte for byte ボディコニアン's ID0132)
and call lines only that demon's talk type has, and some talk types lack a line their own script asks
for. The Japanese original has exactly the same gaps.

text/talkgaps.json lists the lines the build adds: `file`, `chunk`, `record` (hex), `zh`, and `click`
(default true: the record ends with a click wait, as every line of its kind does; false writes the text
alone, for a question the menu follows straight away). `where` says where it is asked and `model` which
line of another file it follows. Each line goes into the file of the pack that asks for it and belongs
to it alone - the demon's ID file, or the talk type's own MS60xx/MS61xx file - so no other demon's
negotiation changes. The record is added to the chunk as a new record; the build fails if the file
already has one with that id.
"""
import collections
import glob
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ddsfile  # noqa: E402
import ddsvm  # noqa: E402
from textbuild import UnitError, encode_unit  # noqa: E402
from units import TAG_RE  # noqa: E402

SRC = os.path.join(WORK, "files", "DDS98")
TABLE = os.path.join(WORK, "text", "talkgaps.json")
CLICK = bytes([0x1E, 0x10, 0x01, 0x01])
END = b"\x00"
MENU = 0x1D0
SHOWS = set(range(0x001, 0x009)) | {0x101, 0x102}      # dictionary words, printed names and values


class TalkGapError(ValueError):
    pass


def load(path=TABLE):
    lines = json.load(open(path, encoding="utf-8"))["lines"]
    for ln in lines:
        ln["record"] = int(ln["record"], 16)
        ln.setdefault("click", True)
    return lines


def chars(lines=None, text_key="zh"):
    """The characters the lines show, for the character map and the font."""
    out = set()
    for ln in lines if lines is not None else load():
        out.update(TAG_RE.sub("", ln[text_key]))
    out.discard("\n")
    return out


def payload(ln, charmap, text_key="zh"):
    return encode_unit(ln[text_key], charmap) + (CLICK if ln["click"] else b"") + END


def problems(charmap, font, lines=None, text_key="zh"):
    """[(line, problem)] of the table: text the build cannot encode or show, a click wait after a line
    that does not end it, a record listed twice."""
    from sjis import is_hanzi
    out = []
    seen = set()
    for ln in lines if lines is not None else load():
        key = (ln["file"], ln["chunk"], ln["record"])
        tag = f"{ln['file']} {0xE0 + ln['chunk']:02X}:{ln['record']:02X}"
        if key in seen:
            out.append((tag, "listed twice"))
        seen.add(key)
        try:
            encode_unit(ln[text_key], charmap)
        except UnitError as e:
            out.append((tag, str(e)))
        if ln["click"] != ln[text_key].endswith("\n"):
            out.append((tag, "a click wait needs the line to end with a newline, and only then"))
        for ch in set(TAG_RE.sub("", ln[text_key])):
            if font is not None and is_hanzi(ch) and font.pattern(ch) is None:
                out.append((tag, f"no WenQuanYi glyph for 「{ch}」"))
    return out


def apply_to(files, charmap, lines=None, src=SRC, text_key="zh"):
    """Add the lines to the script files: files maps a file name to the bytes this build wrote, and a
    file it has not written is read from src. files gains every file touched. -> [(file, chunk, record)]"""
    by_file = collections.defaultdict(list)
    for ln in lines if lines is not None else load():
        by_file[ln["file"] + ".BIN"].append(ln)
    added = []
    for name, lns in sorted(by_file.items()):
        parsed = ddsfile.parse(files.get(name) or open(os.path.join(src, name), "rb").read())
        for ln in lns:
            if ln["chunk"] >= len(parsed):
                raise TalkGapError(f"{name} has no chunk {ln['chunk']}")
            recs = parsed[ln["chunk"]]
            if any(r.rid == ln["record"] for r in recs):
                raise TalkGapError(f"{name} chunk {ln['chunk']} already holds record {ln['record']:02X}")
            recs.append(ddsfile.Record(ln["record"], None, payload(ln, charmap, text_key)))
            added.append((name, ln["chunk"], ln["record"]))
        files[name] = ddsfile.build(parsed)
    return added


# ---- the check on a built image: the negotiation packs as the game assembles them ----

class _Reader(ddsvm._Reader):
    """The VM's operand reader, noting the [file][rec] entries of jump lists."""

    def __init__(self, data, pos):
        super().__init__(data, pos)
        self.targets = []

    def op_L(self):
        while True:
            if self.byte() == 0xFF:
                return
            if self.byte():
                self.op_r()
            else:
                sel, rec = self.byte(), self.byte()
                self.targets.append((sel, rec))


def references(payload_bytes):
    """[(token start, command, sel, rec)] of every record a payload reaches through a selector E0-EF:
    the calls 0D, the jumps 0C and the entries of jump lists (command given as the list's own)."""
    out = []
    for t in ddsvm.iter_tokens(payload_bytes):
        if t.kind != "cmd":
            continue
        if t.code in (0x00C, 0x00D):
            out.append((t.start, t.code, payload_bytes[t.start + 1], payload_bytes[t.start + 2]))
        sig = ddsvm.COMMANDS.get(t.code, "")
        if "L" in sig:
            rd = _Reader(payload_bytes, t.start + (2 if payload_bytes[t.start] in ddsvm.PREFIX else 1))
            rd.run(sig)
            out += [(t.start, t.code, s, r) for s, r in rd.targets]
    return [x for x in out if 0xE0 <= x[2] <= 0xEF]


class Game:
    """The negotiation files, talk types and demons of a set of game files (an image, or files/DDS98)."""

    def __init__(self, read):
        self.read = read
        self._parsed = {}
        et7 = read("ET0007.BIN")
        self.rows = [et7[2 + 3 * i:5 + 3 * i] for i in range(struct.unpack_from("<H", et7)[0] // 3)]

    def parsed(self, stem):
        if stem not in self._parsed:
            blob = self.read(stem + ".BIN")
            self._parsed[stem] = None if blob is None else ddsfile.parse(blob)
        return self._parsed[stem]

    def stems(self, talk_type, demon=None):
        a, b, c = self.rows[talk_type]
        out = ["MS6000"] + [f"MS60{x:02X}" for x in (a, b) if x != 0xFF] + ([f"MS61{c:02X}"] if c != 0xFF else [])
        if demon is not None and self.parsed(f"ID{demon:04X}") is not None:
            out.append(f"ID{demon:04X}")
        return out

    def pack(self, stems, conditional):
        """{(sel, rec): (stem, payload)}; conditional records load when `conditional` says so."""
        out = {}
        for stem in stems:
            for ci, recs in enumerate((self.parsed(stem) or [])[:16]):
                for r in recs:
                    if r.cond is None or conditional:
                        out[(0xE0 + ci, r.rid)] = (stem, r.payload)
        return out


def _empty(entry):
    return entry is None or entry[1] in (b"", END)


def _first_shown(pack, payload_bytes, start, depth=0):
    """What the straight path from `start` shows first: 'menu', 'text' or None (the record ends)."""
    for t in ddsvm.iter_tokens(payload_bytes):
        if t.start < start:
            continue
        if t.kind == "text" or t.code in SHOWS:
            return "text"
        if t.code == MENU:
            return "menu"
        if t.code in (0x00C, 0x00D):
            sel, rec = payload_bytes[t.start + 1], payload_bytes[t.start + 2]
            target = pack.get((sel, rec)) if 0xE0 <= sel <= 0xEF else None
            if not _empty(target) and depth < 4:
                got = _first_shown(pack, target[1], 0, depth + 1)
                if got:
                    return got
            if t.code == 0x00C:
                return None
        elif t.code in (0x000, 0x018):
            return None
    return None


def audit(game, entries=((0xE0, 0x00),)):
    """Every talk type's pack, and every demon's that has an ID file, followed from the entries with
    both sides of every branch taken and conditional records both loaded and not. -> (packs followed,
    [(pack, caller, record)] of calls to an empty record with a menu next, {(sel, rec): {(pack, caller,
    file the record came from)}} of every record reached)."""
    from records import plain_of
    labels = [(f"type {tt}", game.stems(tt)) for tt in range(len(game.rows))]
    for name in sorted(n for n in os.listdir(SRC) if n.upper().startswith("P2") and n.upper().endswith(".BIN")):
        plain = plain_of(game.read(name))
        demon, tt = struct.unpack_from("<H", plain, 0x34)[0], plain[0x73]
        if tt < len(game.rows) and game.parsed(f"ID{demon:04X}") is not None:
            labels.append((f"{demon:04X}", game.stems(tt, demon)))
    gaps, reached = set(), collections.defaultdict(set)
    for label, stems in labels:
        for conditional in (False, True):
            pack = game.pack(stems, conditional)
            seen, todo = set(), list(entries)
            while todo:
                key = todo.pop()
                if key in seen:
                    continue
                seen.add(key)
                entry = pack.get(key)
                if _empty(entry):
                    continue
                try:
                    refs = references(entry[1])
                except ddsvm.ParseError:
                    continue
                caller = f"{entry[0]} {key[0]:02X}:{key[1]:02X}"
                for at, code, sel, rec in refs:
                    target = pack.get((sel, rec))
                    reached[(sel, rec)].add((label, caller, None if _empty(target) else target[0]))
                    todo.append((sel, rec))
                    if code == 0x00D and _empty(target) and _first_shown(pack, entry[1], at + 3) == "menu":
                        gaps.add((label, caller, f"{sel:02X}:{rec:02X}"))
    return len(labels), sorted(gaps), reached


def main(argv):
    from buildcore import JapaneseText
    key = "en" if "--english" in argv else "jp"
    lines = load()
    bad = problems(JapaneseText(), None, lines, key)
    for row in lines:
        print(f"{row['file']} {row['chunk']:02X}:{row['record']:02X} {row[key]}")
    for where, problem in bad:
        print(where, problem)
    return bool(bad)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
