#!/usr/bin/env python3
"""DDS98 script bytecode: tokenise, parse operands, re-encode with relocation.

Token fetch and classification follow the VM exactly (1603:54FA, 0000:1ED8, and
the _mbctype/_ctype tables read out of DDS98.EXE):

    byte 81-9F/E0-FC  lead byte: the token is two bytes; it is text when the
                      second byte is 40-7E or 80-FC, otherwise an unknown
                      command (dispatched to the default case, no effect)
    byte 20-7E/A1-DF  one-byte text
    anything else     command code; 1D/1E/1F prefix pages 3/2/1

Legacy records: a few files (development leftovers, e.g. MS0031's 「＃暫定：…」)
were compiled by an older script compiler whose byte code the shipped VM no
longer accepts. There is one dispatcher (1603:5A74, called only from 1603:5A33)
and one command table, so negotiation scripts run through the same grammar as
everything else, and a record that needs the old reading cannot be executed as
written - it is dead. `tokenize(..., legacy=True)` applies the old readings only
to prove that; the extractor never offers such records for translation and the
builder copies them unchanged. Old readings, each shown against the shipped form:

    `1F 00 xx`      page-2 command 0x2xx; shipped `1E xx`. Same menu tail:
                    `1F D1 1E 11` x1650 vs `1F D1 1F 00 11` x60. Shipped VM:
                    0x100 falls to the default case.
    `1F 0D/0E/0F`   no operand; shipped form carries a V (`1F 0D 00 00` x688
                    vs `1F 0D 1F E5` x47 in the old files).

Operand signatures come from ddsgrammar.py (see vmscan.py for how they were
derived). Primitive symbols:

    b byte  w word  d dword
    r word, branch target = position after the word + value (16-bit), which
      must be a token boundary of the same record
    V typed value: type byte, then VALUES[type]
    L jump list   until c == FF: [c][s], then r when s != 0, else [file][rec]
    C pair list   [b1][b2] until b1 == FF
    D value list  V until a constant whose low word is FFFF
    S selector    [sel], then bV or V depending on sel (1603:97E6)
    M             [b1][b2], plus [b3] when b2 is 0 or 2 (1603:C1EA)
    B             bytes up to and including FF (1603:C4F2)
    X             [b], then [b][b] when b != 0, else six V (25CA:0956)
"""
import struct

from ddsgrammar import ALIAS, COMMANDS, PREFIX, VALUES

SEL_BV = frozenset({0x00, 0x01, 0x02, 0x03, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x10, 0x12})
SEL_V = frozenset({0x04, 0x05, 0x06, 0x0C, 0x0D, 0x0E, 0x0F, 0x11, 0x13})
DICT_CODES = range(0x01, 0x09)                    # ＠辞書０..７ -> MS7F00..MS7F07
LEGACY_PAGE2 = 0x100                              # `1F 00 xx`, old spelling of `1E xx`
LEGACY_COMMANDS = {0x10D: "", 0x10E: "", 0x10F: ""}
_LEGACY_TABLE = {**COMMANDS, **LEGACY_COMMANDS}


def is_lead(c):
    return 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC


def is_trail(c):
    return 0x40 <= c <= 0x7E or 0x80 <= c <= 0xFC


def is_text1(c):
    return 0x20 <= c <= 0x7E or 0xA1 <= c <= 0xDF


class ParseError(ValueError):
    pass


class Token:
    __slots__ = ("start", "end", "kind", "code", "rel", "dict_ref")

    def __init__(self, start, end, kind, code=None, rel=(), dict_ref=None):
        self.start, self.end, self.kind, self.code = start, end, kind, code
        self.rel = list(rel)          # [(field_offset, target_offset)]
        self.dict_ref = dict_ref      # (dictionary 0..7, index) for ＠辞書 tokens

    def __repr__(self):
        return f"<{self.kind} {self.start:#x}-{self.end:#x} code={self.code}>"


class _Reader:
    def __init__(self, data, pos):
        self.d, self.p, self.rel = data, pos, []

    def byte(self):
        if self.p >= len(self.d):
            raise ParseError(f"operand runs past end of record at {self.p:#x}")
        v = self.d[self.p]
        self.p += 1
        return v

    def word(self):
        lo = self.byte()
        return lo | (self.byte() << 8)

    def run(self, sig):
        for ch in sig:
            getattr(self, "op_" + ch)()

    def op_b(self):
        self.byte()

    def op_w(self):
        self.word()

    def op_d(self):
        self.word()
        self.word()

    def op_r(self):
        field = self.p
        v = self.word()
        self.rel.append((field, (self.p + v) & 0xFFFF))

    def op_V(self):
        self.value()

    def value(self):
        """Parse a typed value; return its low word when it is a constant."""
        t = self.byte()
        start = self.p
        self.run(VALUES.get(t, ""))
        raw = self.d[start:self.p]
        if t in (0x01, 0x05):
            return struct.unpack_from("<H", raw)[0]
        if t == 0x02:
            return struct.unpack_from("<H", raw)[0]
        if t == 0x00:
            return raw[0]
        if t == 0x04:
            return 0xFF00 | raw[0] if raw[0] & 0x80 else raw[0]
        return None

    def op_L(self):
        while True:
            if self.byte() == 0xFF:
                return
            if self.byte():
                self.op_r()
            else:
                self.byte()
                self.byte()

    def op_C(self):
        while True:
            b1 = self.byte()
            self.byte()
            if b1 == 0xFF:
                return

    def op_D(self):
        while self.value() != 0xFFFF:
            pass

    def op_S(self):
        sel = self.byte()
        if sel in SEL_BV:
            self.byte()
            self.value()
        elif sel in SEL_V:
            self.value()

    def op_M(self):
        self.byte()
        if self.byte() in (0, 2):
            self.byte()

    def op_B(self):
        while self.byte() != 0xFF:
            pass

    def op_X(self):
        if self.byte():
            self.byte()
            self.byte()
        else:
            self.run("VVVVVV")


def iter_tokens(data, legacy=False):
    """Yield the tokens of one record payload. Raises ParseError on malformed data.

    legacy=True reads the old compiler's spellings (see module docstring).
    """
    commands = _LEGACY_TABLE if legacy else COMMANDS
    pos = 0
    while pos < len(data):
        start = pos
        c = data[pos]
        if is_lead(c):
            if pos + 1 >= len(data):
                raise ParseError(f"lead byte at end of record ({pos:#x})")
            if is_trail(data[pos + 1]):
                yield Token(start, pos + 2, "text")
            else:
                yield Token(start, pos + 2, "cmd", (c << 8) | data[pos + 1])
            pos += 2
            continue
        if is_text1(c):
            yield Token(start, pos + 1, "text")
            pos += 1
            continue
        rd = _Reader(data, pos + 1)
        code = c
        while code in PREFIX:
            code = PREFIX[code] + rd.byte()
        if legacy and code == LEGACY_PAGE2:
            code = 0x200 + rd.byte()
        code = ALIAS.get(code, code)
        dict_ref = None
        if code in DICT_CODES:
            dict_ref = (code - 1, data[rd.p] if rd.p < len(data) else None)
        rd.run(commands.get(code, ""))
        yield Token(start, rd.p, "cmd", code, rd.rel, dict_ref)
        pos = rd.p


def tokenize(data, legacy=False):
    """Split one record payload into tokens. Raises ParseError on malformed data."""
    return list(iter_tokens(data, legacy))


def check_branches(data, toks):
    """Every branch target must be a token start or the end of the record."""
    bounds = {t.start for t in toks} | {len(data)}
    bad = []
    for t in toks:
        for field, target in t.rel:
            if target not in bounds:
                bad.append((t.start, field, target))
    return bad


def assemble(pieces):
    """Lay out a record and relocate its branches.

    pieces: [(bytes, old_start, rel)] in order, where rel holds
    (field offset *inside this piece's bytes*, old absolute target) pairs, and
    old_start is the offset this piece had in the original record (None for
    inserted material, which cannot be a branch target). A target equal to the
    original record length maps to the new end.
    """
    out = bytearray()
    new_at = {}
    fields = []
    for raw, old_start, rel in pieces:
        if old_start is not None:
            new_at[old_start] = len(out)
        for field, target in rel:
            fields.append((len(out) + field, target))
        out += raw
    return out, new_at, fields


def relocate(out, new_at, fields, old_len):
    new_at = dict(new_at)
    new_at[old_len] = len(out)
    for field, target in fields:
        if target not in new_at:
            raise ParseError(f"branch target {target:#x} vanished from the record")
        value = (new_at[target] - (field + 2)) & 0xFFFF
        struct.pack_into("<H", out, field, value)
    return bytes(out)


def rebuild(data, toks, replace=None, append=None):
    """Re-encode a record from its tokens.

    replace: {token_index: bytes} substitutes a token's bytes (tokens without
    branch operands; a replacement keeps the original start so branches into it
    land on the replacement's first byte).
    append: {token_index: bytes} puts bytes right after a token (after its
    replacement, if it has one); branches to the next token pass them by.
    Without replacements or additions the result is byte-identical to `data`.
    """
    return layout(data, toks, replace, append)[0]


def layout(data, toks, replace=None, append=None):
    """rebuild(), and where each original token ended up: (bytes, [(start, own, appended)]) with the
    offset of token i's piece in the result and the lengths of its own bytes and of what follows them."""
    replace = replace or {}
    append = append or {}
    pieces, parts = [], []
    for i, t in enumerate(toks):
        raw = replace.get(i, data[t.start:t.end])
        rel = [(field - t.start, target) for field, target in t.rel]
        if i in replace and rel:
            raise ParseError("only operand-free tokens can be replaced")
        app = append.get(i, b"")
        pieces.append((raw + app, t.start, rel))
        parts.append((len(raw), len(app)))
    out, new_at, fields = assemble(pieces)
    placed = [(new_at[t.start],) + parts[i] for i, t in enumerate(toks)]
    return relocate(out, new_at, fields, len(data)), placed
