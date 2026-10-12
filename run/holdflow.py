#!/usr/bin/env python3
"""holdflow.py - the scripts a battle message can run, built the way make.py builds them, and followed
through the interpreter's rules. Imported by run/holdmap.py and run/mk_holds.py.

Records. The battle's message files (MS00DB-DF), MS00D8, MS7F04 and every record they can reach through
00C, 00D, dictionary words and list entries. Each is rebuilt as the build writes it - translated units
(tools/textbuild.py), then the holds asked for - and every token of the result remembers the original
token it comes from, so a printed piece is known by its translation unit and a hold by the place the
table names.

The interpreter, as its cases do it (main 0x1BAA4 and what they call):

  prints     text (unless 01B has turned output into capture, until 01C); 101 names, 102 numbers and
             23E table strings, which run a formatted string as a subroutine. A text token that is a
             space (20 or 8140) shows nothing
  calls      00D (file, record); dictionary words 001-008 (record NN of MS7F00-07); in lists of 111, 112,
             114, 116, 118, 11A, 11C, 11E and 2B1 a (file, record) entry, and a branch entry, which
             saves the return point too. All save the point right after the command - the pointer the
             command has read up to (main 0x1E3F2 -> 0x1B690) - and 000 goes back to it
             (main 0x1B564 -> 0x1E54E -> 0x1B71A)
  jumps      00C (file, record) and the entries of lists of 00E, 00F, 113, 115, 117, 119, 11B, 11D and 2B0
             go without saving anything; every list can also match nothing and fall through; 018 jumps;
             the other branch commands (009, 00B, 17F-18A, 1A9, 1AB, 214, 216, 25C-25F, 2B9, 2CE, 2CF)
             jump or fall through
  returns    158 saves its target as a return point and goes on; 159 drops the top return point, 15A
             swaps the top two
  ends       000 with no return point; 157, 1DE, 207, 208, 211 and 2D2 (return -3), 1E5, 233 and 29F
             (return -1): main 0x1B91E stops the run on any negative result
  holds      210 with mode 1 or 3, or mode 0/2 and a count of at least 2

Where waiting is off, main 0x2221A sets a 210's wait up and returns -3 without waiting. The pass of
ov16:04460 stops on it; the record runner main 0x2080C instead takes -3 as "go on next frame" (only -1
ends its run): the state machine serves the wait, and the record carries on after the command - and the
same goes for the other commands that return -3. So runs without waiting are followed on past every 210
and every -3 command, the side a question of what they can reach has to err on.

Roots. main 0x2E57C runs, with waiting allowed: the skill result and attack records (ET0004 header bytes
0x13 and 0x11), every (file, record) byte pair in ET0001 headers, MS00DD 05/4F/50, MS00DE 03/04/44 and
MS00DF 03, and MS00DB 00 is shown by ov16:0455E; an MS00DD or MS00DE record no script names is taken as a
root too. Without waiting: MS00DD 59 and MS7F04 10/11 (main 0x2E52A), MS00DF 00-02 (script commands 1DF,
1DE and 163-165 run them), and every record of MS00D8, MS00DB and MS7F00-07, which scripts elsewhere run.

A message is one run: main 0x2E57C clears the window before each (main 0x2E422 -> 0x28B78). Along each
road the state of the message is carried: nothing shown yet (E); shown and not held (P), with the
category of the last visible piece and whether a newline has come since; held (H), with the hold that
did it. The category of a piece is its translation unit; a piece a dictionary word prints belongs to the
unit of the word's call."""
import collections
import os
import sys

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORK)
sys.path.insert(0, WORK)
sys.path.insert(0, os.path.join(WORK, "tools"))
import expshow  # noqa: E402
import holds  # noqa: E402
from ddsfile import parse  # noqa: E402
from ddsgrammar import COMMANDS  # noqa: E402
from ddstext import Corpus  # noqa: E402
from ddsvm import _Reader, tokenize  # noqa: E402
from tables import ITEM_HEADER, SKILL_HEADER, chunks_of, string_table  # noqa: E402
from textbuild import layout_record  # noqa: E402
from units import Dicts, split_units, unit_id  # noqa: E402
from buildcore import ScriptInputs, JapaneseText  # noqa: E402
import sjis  # noqa: E402

SRC = "files/DDS98"
PRINT_CMDS = {0x101, 0x102, 0x23E}
NEWLINE = 0x00A
DICT_CMDS = set(range(0x001, 0x009))
GOTO_LISTS = {0x00E, 0x00F, 0x113, 0x115, 0x117, 0x119, 0x11B, 0x11D, 0x2B0}
CALL_LISTS = {0x111, 0x112, 0x114, 0x116, 0x118, 0x11A, 0x11C, 0x11E, 0x2B1}
BRANCHES = {0x009, 0x00B, 0x17F, 0x180, 0x181, 0x182, 0x183, 0x185, 0x186, 0x187, 0x188, 0x189, 0x18A,
            0x1A9, 0x1AB, 0x214, 0x216, 0x25C, 0x25D, 0x25E, 0x25F, 0x2B9, 0x2CE, 0x2CF}
ENDS = {0x157, 0x1DE, 0x207, 0x208, 0x211, 0x2D2, 0x1E5, 0x233, 0x29F}
YIELDS = {0x157, 0x1DE, 0x207, 0x208, 0x211, 0x2D2}        # the ends that return -3
PUSH_RET, DROP_RET, SWAP_RET, CAPTURE_ON, CAPTURE_OFF, JUMP, HOLD, RETURN = \
    0x158, 0x159, 0x15A, 0x01B, 0x01C, 0x018, 0x210, 0x000
BLANK = {b" ", b"\x81\x40"}
MAX_DEPTH = 32
# Connectors: units that start a sentence another record finishes, so no hold goes after them - the
# sentence is held by the line that finishes it, what came before them by its own hold. Each is the last
# thing a message shows only on a road the analysis cannot rule out by itself, and a message ending on
# one is reported, not failed:
#   MS00DD 1B  prints 而且 only when var 07 equals 3 (186: jump unless equal), then MS00DD 1C sets var 07
#              again from the same operand (4B 00 00 = word [0x98fc], main 0x2078A) and prints nothing
#              only when it differs from 3; no command of MS00DD 1B-1C, 22-25, 03, 4E or MS7F03 reaches a
#              writer of [0x98fc], so that road does not happen.
#   MS00DD 37, 4C, 4D  print 可是，/而且 before MS00DC 00, whose list (119, first entry at or above the low
#              byte of [0x9b3e]) runs out only above 20; the skill header byte that main 0x31B07 stores
#              there is 00-20 in every ET0004 entry, the other writers' sources were not followed.
CONNECTORS = {"MS00DD/0/27@001C": "而且（MS00DD 1B，后面接 MS00DD 1C 的结果行）",
              "MS00DD/0/55@0090": "可是，（MS00DD 37，后面接 MS00DC 00 的状态行）",
              "MS00DD/0/76@010A": "⏎而且（MS00DD 4C 伤害之后，后面接 MS00DC 00 的状态行）",
              "MS00DD/0/77@003C": "⏎而且（MS00DD 4D 失去 MP 之后，后面接 MS00DC 00 的状态行）"}
DICT_FILES = {0x7F00 + k for k in range(8)}
START_FILES = (0xD8, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF, 0x7F04)


def stem(fid):
    return f"MS{fid:04X}"


def list_entries(payload, t):
    """[('record', file, record) | ('branch', target offset)] of a list command."""
    sig = COMMANDS[t.code]
    rd = _Reader(payload, t.start + (1 if t.code < 0x100 else 2))
    for ch in sig[:sig.index("L")]:
        getattr(rd, "op_" + ch)()
    pos, out, rels = rd.p, [], iter(tgt for _f, tgt in t.rel)
    while payload[pos] != 0xFF:
        out.append(("branch", next(rels)) if payload[pos + 1] else ("record", payload[pos + 2], payload[pos + 3]))
        pos += 4
    return out


def references(payload, t):
    if t.kind != "cmd":
        return []
    if t.code in (0x00C, 0x00D):
        return [(payload[t.start + 1], payload[t.start + 2])]
    if t.code in DICT_CMDS:
        return [(0x7EFF + t.code, payload[t.start + 1])]
    if "L" in COMMANDS.get(t.code, ""):
        return [(e[1], e[2]) for e in list_entries(payload, t) if e[0] == "record"]
    return []


def hold_210(payload, t):
    mode = payload[t.start + 3]
    return mode in (1, 3) or (mode in (0, 2) and payload[t.start + 4] >= 2)


def within(stack, frame):
    """Whether a state with this stack is still inside the record invocation that had `frame` as its
    stack: in it, in something it called, or in a record it jumped to with 00C or a list."""
    return stack[:len(frame)] == frame


class Record:
    """One record as built. origin[j] is (original token index, 'own' | 'appended')."""

    def __init__(self, key, source, charmap, commands, appends, owners):
        self.key = key
        self.owners = owners                      # token index a hold follows -> the message it is for
        self.orig_payload, self.orig_toks, self.units, zh = source
        new, placed = layout_record(self.orig_payload, self.orig_toks, self.units, zh, charmap, commands,
                                    appends)
        self.payload = new
        self.toks = tokenize(new)
        self.at = {t.start: j for j, t in enumerate(self.toks)}
        self.unit_of = {}
        for u in self.units:
            for i in range(u.first, u.last):
                self.unit_of[i] = u
        self.origin = []
        i = 0
        for t in self.toks:
            while placed[i][0] + placed[i][1] + placed[i][2] <= t.start:
                i += 1
            start, own, app = placed[i]
            if t.end > start + own + app or (t.start < start + own < t.end):
                raise SystemExit(f"{self.name()}@{t.start:04X}: a token runs across two original tokens")
            self.origin.append((i, "own" if t.start < start + own else "appended"))

    def name(self):
        return f"{stem(self.key[0])} {self.key[1]:02X}"

    def unit_end(self, u):
        """Index of the last token the unit's text became, or None when it became nothing."""
        js = [j for j, (i, part) in enumerate(self.origin) if part == "own" and u.first <= i < u.last]
        return js[-1] if js else None

    def unit_id(self, u):
        return unit_id(stem(self.key[0]), 0, self.key[1], u.start)

    def category(self, j):
        """The unit a token belongs to, named by its id, or the place of a token outside every unit."""
        i, part = self.origin[j]
        if part == "own" and i in self.unit_of:
            return self.unit_id(self.unit_of[i])
        return self.orig_label(i)

    def orig_label(self, i):
        off = self.orig_toks[i].start if i < len(self.orig_toks) else len(self.orig_payload)
        return f"{stem(self.key[0])}/0/{self.key[1]}@{off:04X}"

    def hold_id(self, j):
        """('added', message) for a hold the table put after a unit or a token, ('original', place) for the
        game's own."""
        i, part = self.origin[j]
        if part == "appended":
            u = self.unit_of.get(i)
            if u is not None and u.last - 1 != i:
                raise SystemExit(f"{self.orig_label(i)}: a hold inside a unit")
            return ("added", self.owners[i])
        if self.orig_toks[i].code == HOLD:
            return ("original", self.orig_label(i))
        raise SystemExit(f"{self.orig_label(i)}: command 210 the table does not account for")

    def visible(self, j):
        t = self.toks[j]
        return t.kind != "cmd" and self.payload[t.start:t.end] not in BLANK or t.kind == "cmd" and t.code in PRINT_CMDS


class Scripts:
    """The records a battle message can reach, with their translations, ready to be built."""

    def __init__(self, src=SRC, english=False, native=False):
        self.src, self.english, self.native = src, english, native
        self.native = True
        self.texts = ScriptInputs(src)
        self.charmap = JapaneseText()
        self.dicts = Dicts(Corpus(src))
        self.source = {}                          # (file, record) -> (payload, tokens, units, {unit: zh})
        loaded, todo = set(), list(START_FILES)
        while todo:
            fid = todo.pop()
            if fid in loaded:
                continue
            loaded.add(fid)
            chunks = parse(open(f"{src}/{stem(fid)}.BIN", "rb").read())
            if len(chunks) != 1:
                raise SystemExit(f"{stem(fid)}: {len(chunks)} chunks")
            for pos, r in enumerate(chunks[0]):
                if r.rid != pos:
                    raise SystemExit(f"{stem(fid)}: record {r.rid:02X} at position {pos}")
                tkey = (stem(fid), 0, pos)
                if tkey in self.texts.records:
                    (_rid, _cond, payload), toks, units = self.texts.records[tkey]
                else:
                    payload, toks, units = r.payload, tokenize(r.payload), []
                self.source[(fid, pos)] = (payload, toks, units, self.texts.script.get(tkey, {}))
                for t in toks:
                    if t.kind == "cmd" and t.rel and not (t.code in BRANCHES | GOTO_LISTS | CALL_LISTS
                                                          or t.code in (JUMP, PUSH_RET)):
                        raise SystemExit(f"{stem(fid)} {pos:02X}@{t.start:04X}: command {t.code:03X} branches, "
                                         "and what it does is not known")
                    for f, _r in references(payload, t):
                        if f not in loaded:
                            todo.append(f)
        self.script_refs = collections.defaultdict(set)
        for key, (payload, toks, _units, _zh) in self.source.items():
            for t in toks:
                for ref in references(payload, t):
                    if ref not in self.source:
                        raise SystemExit(f"{stem(key[0])} {key[1]:02X}@{t.start:04X} names {stem(ref[0])} "
                                         f"{ref[1]:02X}, which does not exist")
                    self.script_refs[ref].add(key)
        self.on_roots, self.off_roots = self._roots()

    def _roots(self):
        skill_de, skill_dd = set(), set()
        for e in string_table(chunks_of(open(f"{self.src}/ET0004.BIN", "rb").read())[0]):
            if len(e) >= SKILL_HEADER:
                skill_de.add(e[0x11])
                skill_dd.add(e[0x13])
        item_pairs = set()
        for e in string_table(chunks_of(open(f"{self.src}/ET0001.BIN", "rb").read())[0]):
            head = e[:ITEM_HEADER.get(e[4], 0)] if len(e) > 8 else b""
            for k in range(len(head) - 1):
                if (head[k], head[k + 1]) in self.source and head[k] in (0xDD, 0xDE, 0xDF):
                    item_pairs.add((head[k], head[k + 1]))
        off = ({(0xDD, 0x59), (0x7F04, 0x10), (0x7F04, 0x11), (0xDF, 0x00), (0xDF, 0x01), (0xDF, 0x02)}
               | {k for k in self.source if k[0] in (0xD8, 0xDB) or k[0] in DICT_FILES})
        on = ({(0xDD, r) for r in skill_dd} | {(0xDE, r) for r in skill_de} | item_pairs
              | {(0xDD, 0x05), (0xDD, 0x4F), (0xDD, 0x50), (0xDE, 0x03), (0xDE, 0x04), (0xDE, 0x44),
                 (0xDF, 0x03), (0xDB, 0x00)}
              | {k for k in self.source if k[0] in (0xDD, 0xDE) and not self.script_refs[k] and k != (0xDD, 0x59)})
        return on & set(self.source), off & set(self.source)

    def build(self, table):
        """{(file, record): Record}: every record as make.py writes it with the hold table (the form
        tools/holds.py load() returns), through the same tools/holds.py edits(); the summary's
        experience line then mended as make.py mends it (tools/expshow.py, same length)."""
        recs = {}
        for key, (payload, toks, units, _zh) in self.source.items():
            tkey = (stem(key[0]), 0, key[1])
            entries = table.get(tkey, {"after": {}, "original": {}})
            try:
                commands, appends = holds.edits(tkey, payload, toks, units, entries)
            except holds.HoldError as e:
                raise SystemExit(f"hold table: {e}")
            unit_at = {u.start: u for u in units}
            starts = {t.start: i for i, t in enumerate(toks)}
            owners = {(unit_at[off].last - 1 if off in unit_at else starts[off]): message
                      for off, (_hold, message) in entries["after"].items()}
            try:
                recs[key] = Record(key, self.source[key], self.charmap, commands, appends, owners)
            except ValueError as exc:
                raise ValueError(f'{stem(key[0])}/{key[1]:02X}: {exc}') from exc
        for name, fixes in expshow.by_file(None if self.english else self.charmap, english=self.english).items():
            for fix in fixes:
                if self.english and isinstance(fix, expshow.Wording):
                    continue
                rec = recs[(int(name[2:], 16), fix.rid)]
                sites, _block = fix.edits(rec.payload, len(rec.payload))
                new = bytearray(rec.payload)
                for off, a, b in sites:
                    new[off:off + len(a)] = b
                if [(t.start, t.end) for t in tokenize(bytes(new))] != [(t.start, t.end) for t in rec.toks]:
                    raise SystemExit(f"{rec.name()}: tools/expshow.py 的改动移动了命令的边界")
                rec.payload = bytes(new)
        return recs


class Flow:
    """Every state a run can reach from the roots over built records."""

    def __init__(self, recs, roots, waiting):
        self.recs, self.waiting = recs, waiting
        self.kind, self.succ = {}, {}
        self.notes = collections.defaultdict(set)
        work = [(r, 0, (), "E", False, 0) for r in sorted(roots)]
        while work:
            s = work.pop()
            if s in self.kind:
                continue
            kd, nx, notes = self.step(s)
            self.kind[s], self.succ[s] = kd, nx
            for n in notes:
                self.notes[n[0]].add(n[1:])
            work.extend(x for x in nx if x not in self.kind)

    def category(self, k, j, stack):
        if k[0] not in DICT_FILES:
            return self.recs[k].category(j)
        for rk, rj, rph in reversed(stack):
            if rk[0] not in DICT_FILES:
                if rph != 2:
                    break
                return self.recs[rk].category(rj)
        return self.recs[k].orig_label(self.recs[k].origin[j][0])

    def step(self, s):
        """(kind, successors, notes) of a state."""
        k, j, stack, pend, cap, phase = s
        rec = self.recs[k]
        toks = rec.toks

        def go(k2=k, j2=j, stack2=stack, pend2=pend, cap2=cap, phase2=0):
            if len(stack2) > MAX_DEPTH:
                raise SystemExit(f"{rec.name()}: return points nest deeper than {MAX_DEPTH}")
            return (k2, j2, stack2, pend2, cap2, phase2)

        if phase == 2:
            return None, [go(j2=j + 1)], ()
        if j >= len(toks):
            return "out", [], (("no-000", k),)
        t = toks[j]
        c = t.code if t.kind == "cmd" else None
        on = go(phase2=2)
        if t.kind != "cmd" or c in PRINT_CMDS:
            if cap or not rec.visible(j):
                return None, [on], ()
            notes = ()
            if pend[0] == "H" and pend[2] and within(stack, pend[4]):
                notes = (("split", pend[3], (k, j)),)
            return "print", [go(pend2=("P", self.category(k, j, stack), True), phase2=2)], notes
        if c == NEWLINE:
            p2 = pend if pend == "E" else (pend[0], pend[1], False) + pend[3:]
            return None, [go(pend2=p2, phase2=2)], ()
        if c == RETURN:
            if stack:
                (rk, rj, rph), rest = stack[-1], stack[:-1]
                return None, [go(rk, rj, rest, phase2=rph)], ()
            return "out", [], ()
        if c in ENDS:
            if not self.waiting and c in YIELDS:
                return None, [on], ()
            return "out", [], ()
        if c == HOLD:
            if not self.waiting:
                return "hold", [on], ()
            if not hold_210(rec.payload, t):
                return None, [on], ()
            hid = rec.hold_id(j)
            if pend == "E":
                return "hold", [on], ((("empty", hid, (k, j)),) if hid[0] == "added" else ())
            if pend[0] == "P":
                notes = (("mismatch", hid, pend[1], (k, j)),) if hid[0] == "added" and hid[1] != pend[1] else ()
                return "hold", [go(pend2=("H", pend[1], pend[2], hid, stack), phase2=2)], notes
            return "hold", [on], (("double", pend[3], hid, (k, j)),)
        if c in DICT_CMDS or c == 0x00D:
            return None, [go(references(rec.payload, t)[0], 0, stack + ((k, j, 2),))], ()
        if c == 0x00C:
            return None, [go(references(rec.payload, t)[0], 0)], ()
        if c == JUMP:
            return None, [go(j2=rec.at.get(t.rel[0][1], len(toks)))], ()
        if c == PUSH_RET:
            return None, [go(stack2=stack + ((k, rec.at.get(t.rel[0][1], len(toks)), 0),), phase2=2)], ()
        if c == DROP_RET:
            return None, [go(stack2=stack[:-1], phase2=2)], ()
        if c == SWAP_RET:
            swapped = stack[:-2] + stack[-1:] + stack[-2:-1] if len(stack) >= 2 else stack
            return None, [go(stack2=swapped, phase2=2)], ()
        if c == CAPTURE_ON:
            return None, [go(cap2=True, phase2=2)], ()
        if c == CAPTURE_OFF:
            return None, [go(cap2=False, phase2=2)], ()
        if c in GOTO_LISTS or c in CALL_LISTS:
            ret = stack + ((k, j, 2),) if c in CALL_LISTS else stack
            succ = [on]
            for e in list_entries(rec.payload, t):
                if e[0] == "record":
                    succ.append(go((e[1], e[2]), 0, ret))
                else:
                    succ.append(go(j2=rec.at.get(e[1], len(toks)), stack2=ret))
            return None, succ, ()
        if t.rel:
            return None, [on] + [go(j2=rec.at.get(tgt, len(toks))) for _f, tgt in t.rel], ()
        return None, [on], ()

    def places(self):
        """(record, token index, phase) of every state."""
        return {(s[0], s[1], s[5]) for s in self.kind}

    def gaps(self):
        """{category: number of run ends} for runs that end with something shown and not held."""
        out = collections.Counter()
        for s, kd in self.kind.items():
            if kd == "out" and s[3] != "E" and s[3][0] == "P":
                out[s[3][1]] += 1
        return out

    def shown(self):
        """Every category something visible is printed under."""
        return {s[3][1] for s in self.kind if s[3] != "E" and s[3][0] == "P"}

    def at(self, place):
        """States at a place (record, token index, phase)."""
        if not hasattr(self, "_by_place"):
            self._by_place = collections.defaultdict(list)
            for s in self.kind:
                self._by_place[(s[0], s[1], s[5])].append(s)
        return self._by_place.get(place, [])


def holds_met(flow, recs):
    """hold_id() of every command 210 a flow reaches."""
    out = set()
    for s, kd in flow.kind.items():
        rec = recs[s[0]]
        if kd in ("hold", "out") and s[5] == 0 and s[1] < len(rec.toks):
            t = rec.toks[s[1]]
            if t.kind == "cmd" and t.code == HOLD:
                out.add(rec.hold_id(s[1]))
    return out


def category_key(category):
    """(file, record) of the record a category belongs to."""
    path, _off = category.split("@")
    st_, _ci, rid = path.split("/")
    return int(st_[2:], 16), int(rid)


def end_place(recs, category):
    """Where a category's content has all been printed: right after its unit's last built token, or right
    after its token. None when the unit's text became nothing."""
    key = category_key(category)
    rec = recs[key]
    off = int(category.split("@")[1], 16)
    for u in rec.units:
        if u.start == off:
            j = rec.unit_end(u)
            return None if j is None else (key, j, 2)
    i = next(n for n, t in enumerate(rec.orig_toks) if t.start == off)
    js = [j for j, (oi, part) in enumerate(rec.origin) if oi == i and part == "own"]
    return (key, js[-1], 2)


def hold_places(recs):
    """{built place (record, token index, 2): table place} where the build can put a hold: after the last
    token of a unit, or after a token outside every unit that goes on by itself."""
    out = {}
    for key, rec in recs.items():
        if not holds.changeable((stem(key[0]), 0, key[1])):
            continue
        for u in rec.units:
            j = rec.unit_end(u)
            if j is not None:
                out[(key, j, 2)] = rec.unit_id(u)
        in_unit = set(rec.unit_of)
        for i, t in enumerate(rec.orig_toks):
            if i in in_unit or not holds.goes_on(t):
                continue
            js = [j for j, (oi, part) in enumerate(rec.origin) if oi == i and part == "own"]
            if js:
                out[(key, js[-1], 2)] = rec.orig_label(i)
    return out


ROAD_LIMIT = 5000


def roads_from(flow, start, places):
    """What comes first on each road from a state that has content waiting: ('same', ...) a visible print
    with no newline since the last visible piece and still inside the invocation the state is in - the same
    sentence going on; ('next', ...) a visible print after a newline or after that invocation has returned;
    ('hold', ...) a hold; ('end', ...) the end of the run. Each comes with the hold places passed on the
    way, in order."""
    frame = start[2]
    out = set()
    path = []

    def walk(s, newline, on_path):
        if len(out) > ROAD_LIMIT:
            raise SystemExit(f"more than {ROAD_LIMIT} roads on from {start[:2]}")
        kd = flow.kind[s]
        if kd == "print":
            out.add(("same" if not newline and within(s[2], frame) else "next", tuple(path)))
            return
        if kd in ("hold", "out"):
            out.add(("hold" if kd == "hold" else "end", tuple(path)))
            return
        rec = flow.recs[s[0]]
        t = rec.toks[s[1]] if s[1] < len(rec.toks) else None
        nl = newline or (s[5] == 0 and t is not None and t.kind == "cmd" and t.code == NEWLINE)
        place = (s[0], s[1], s[5])
        added = place in places and s is not start
        if added:
            path.append(places[place])
        for x in flow.succ[s]:
            if x not in on_path:
                on_path.add(x)
                walk(x, nl, on_path)
                on_path.discard(x)
        if added:
            path.pop()

    walk(start, start[3] != "E" and not start[3][2], {start})
    return out


PLACEHOLDER = {0x01: "〈武器〉", 0x02: "〈枪〉", 0x03: "〈行动者〉", 0x05: "〈对象〉", 0x07: "〈敌人〉", 0x1A: "〈主角〉"}


class Texts:
    """What a road shows, as text: Chinese decoded through the character map, names and numbers as
    placeholders."""

    def __init__(self, scripts):
        self.holder = {} if scripts.english or scripts.native else scripts.charmap.holder

    def token(self, rec, j):
        t = rec.toks[j]
        raw = rec.payload[t.start:t.end]
        if t.kind == "cmd":
            if t.code == 0x101:
                return PLACEHOLDER.get(rec.key[1], "〈名字〉") if rec.key[0] == 0x7F03 else "〈名字〉"
            return "〈数字〉" if t.code == 0x102 else "〈名称〉"
        if len(raw) == 2:
            code = sjis.sjis_to_jis(raw)
            if code in self.holder:
                return self.holder[code]
        return raw.decode("cp932", "replace")

    def road(self, flow, states):
        out = []
        for s in states:
            rec = flow.recs[s[0]]
            kd = flow.kind[s]
            t = rec.toks[s[1]] if s[1] < len(rec.toks) else None
            if kd == "print":
                out.append(self.token(rec, s[1]))
            elif kd is None and s[5] == 0 and t is not None and t.kind == "cmd" and t.code == NEWLINE:
                out.append("⏎")
            elif kd == "hold":
                out.append("【停】")
        return "".join(out).strip("⏎")


def shortest_roads(flow, roots, targets):
    """{place: states from a root to a state there} for the places in `targets`, on the road that prints
    the fewest visible pieces on the way, so an example shows as little besides the message as it can."""
    dist, prev = {}, {}
    work = collections.deque()
    for r in sorted(roots):
        s = (r, 0, (), "E", False, 0)
        if s in flow.kind and s not in dist:
            dist[s], prev[s] = 0, None
            work.append(s)
    while work:
        s = work.popleft()
        for x in flow.succ[s]:
            d = dist[s] + (1 if flow.kind[x] == "print" else 0)
            if x not in dist or d < dist[x]:
                dist[x], prev[x] = d, s
                (work.append if d > dist[s] else work.appendleft)(x)
    found = {}
    for s, d in dist.items():
        place = (s[0], s[1], s[5])
        if place in targets and (place not in found or d < dist[found[place]]):
            found[place] = s
    out = {}
    for place, s in found.items():
        path, x = [], s
        while x is not None:
            path.append(x)
            x = prev[x]
        out[place] = path[::-1]
    return out
