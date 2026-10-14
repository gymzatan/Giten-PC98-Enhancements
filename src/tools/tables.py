#!/usr/bin/env python3
"""Text outside the scripts: data tables, character records, map names, EXE strings.

Every source is parsed with its layout checked entry by entry (a file that
does not match raises), yields units, and writes translated units back.

  ET0000 chunks 2-5   race / tribe / class / race-group names    string table
  ET000D chunk 1      district names                             string table
  ET0101              map object names ([00][name\\0])           string table
  ET0001              items: header + name\\0 + description\\0     string table
                      (header length by category, byte 4 of the entry)
  ET0004              skills: 20-byte header + name\\0 + description\\0
  ET0010              area names: 26-byte fields padded with spaces
  P2xxxx              character and demon names: 17-byte field at 0x36 of the
                      122-byte record (121 bytes in P2010-P201F)
  Mxxxx               map name; the map sections move and their offsets are fixed
  DDS98.EXE           Shift-JIS strings of the data segment, in place

"string table" = [count:u16][offset:u16 * count] then the entries; entries may
change length (offsets are rebuilt). Map names may change length up to 18 bytes.
Fixed fields and EXE strings keep their byte length: a translation must fit and
is padded (spaces for ET0010, NUL otherwise). Not extracted: ET0018 and ET0040 (debug menus), ET7F00 (the script
compiler's symbol table).

Unit ids: FILE/chunk/entry/part for tables ("ET0001/0/12/name"), P2xxxx/name,
Mxxxx/name, DDS98.EXE/@file-offset.

    tables.py validate      parse every source and print what was found
"""
import glob
import os
import re
import struct
import sys

from ddscrypt import decrypt, encrypt

SRC = "files/DDS98"
ITEM_HEADER = {1: 21, 2: 13, 3: 16, 4: 23, 5: 17, 6: 13, 7: 13, 8: 12, 9: 29, 10: 12,
               11: 32, 12: 23, 13: 14, 14: 18, 15: 18, 16: 18, 17: 18, 18: 18, 19: 16}
SKILL_HEADER = 20
AREA_RECORD, AREA_FIELD = 29, 26
P2_NAME_AT, P2_NAME_FIELD = 0x36, 17
SECTION_POINTERS, MAP_NAME_MAX = 13, 18
EXE_HEADER = 0x3800                      # DDS98.EXE MZ header size
DGROUP_FILE = 0x48FC * 16 + EXE_HEADER   # data segment start in the file


class LayoutError(ValueError):
    pass


def chunks_of(data):
    out, pos = [], 0
    while pos + 2 <= len(data):
        n = struct.unpack_from("<H", data, pos)[0]
        w, plain = decrypt(data[pos:pos + 2 + n])
        if w != n or pos + 2 + n > len(data):
            raise LayoutError("chunk header does not match its length")
        out.append(plain)
        pos += 2 + n
    if pos != len(data):
        raise LayoutError("trailing bytes after the last chunk")
    return out


def chunks_bytes(plains):
    out = bytearray()
    for p in plains:
        if len(p) > 0xFFFF:
            raise LayoutError(f"chunk of {len(p)} bytes exceeds 65535")
        out += encrypt(p)
    return bytes(out)


def text_of(raw, newlines=False):
    """Decoded text of a stored string; LayoutError when it is not text.

    Set newlines for a string that is written over more than one line, as some of the executable's
    messages are; everywhere else a byte below 0x20 means this is not text at all."""
    try:
        s = raw.decode("cp932")
    except UnicodeDecodeError:
        raise LayoutError(f"not Shift-JIS text: {raw.hex(' ')}") from None
    allowed = "\n" if newlines else ""
    if any(ord(c) < 0x20 and c not in allowed for c in s):
        raise LayoutError(f"control byte in text: {raw.hex(' ')}")
    return s


def encode_lines(text, encode):
    """A DDS98.EXE string: encoded the way a table text is, with its newlines left in place."""
    return b"\n".join(encode(part) for part in text.split("\n"))


def string_table(chunk):
    count = struct.unpack_from("<H", chunk, 0)[0]
    offs = list(struct.unpack_from(f"<{count}H", chunk, 2))
    if not offs or offs[0] != 2 + 2 * count or offs != sorted(offs) or offs[-1] > len(chunk):
        raise LayoutError("not a string table")
    return [chunk[a:b] for a, b in zip(offs, offs[1:] + [len(chunk)])]


def table_bytes(entries):
    count = len(entries)
    out = bytearray(struct.pack("<H", count))
    pos = 2 + 2 * count
    for e in entries:
        out += struct.pack("<H", pos)
        pos += len(e)
    if pos > 0xFFFF:
        raise LayoutError("string table exceeds 65535 bytes")
    for e in entries:
        out += e
    return bytes(out)


class Unit:
    __slots__ = ("id", "jp", "max_bytes", "pad")

    def __init__(self, uid, jp, max_bytes=None, pad=None):
        self.id, self.jp, self.max_bytes, self.pad = uid, jp, max_bytes, pad


# ----------------------------------------------------------------- sources
class StringTableFile:
    """Chunks of string tables; each entry = prefix + strings, all NUL-terminated."""

    def __init__(self, stem, chunk_ids, parts, prefix, data=None, newlines=False):
        self.stem, self.chunk_ids, self.parts, self.prefix = stem, chunk_ids, parts, prefix
        self.path = os.path.join(SRC, stem + ".BIN")
        self.chunks = chunks_of(open(self.path, "rb").read() if data is None else data)
        self.entries = {}                     # chunk -> [(prefix bytes, [strings])]
        for ci in chunk_ids:
            rows = []
            for i, e in enumerate(string_table(self.chunks[ci])):
                n = self.prefix(e)
                body = e[n:]
                pieces = body.split(b"\x00")
                if n is None or len(pieces) != len(parts) + 1 or pieces[-1] != b"":
                    if e.strip(b"\x00") == b"" and len(e) <= 8:
                        rows.append((e, None))           # an empty slot
                        continue
                    raise LayoutError(f"{stem} chunk {ci} entry {i}: {e[:40].hex(' ')}")
                strings = [text_of(p, newlines=newlines) for p in pieces[:-1]]
                rows.append((e[:n], strings))
            self.entries[ci] = rows

    def units(self):
        for ci, rows in self.entries.items():
            for i, (pre, strings) in enumerate(rows):
                if strings is None:
                    continue
                for part, s in zip(self.parts, strings):
                    if s.strip(" 　"):
                        yield Unit(f"{self.stem}/{ci}/{i}/{part}", s)

    def build(self, texts, encode):
        plains = list(self.chunks)
        for ci, rows in self.entries.items():
            entries = []
            for i, (pre, strings) in enumerate(rows):
                if strings is None:
                    entries.append(pre)
                    continue
                body = b""
                for part, s in zip(self.parts, strings):
                    t = texts.get(f"{self.stem}/{ci}/{i}/{part}")
                    body += (encode(t) if t else s.encode("cp932")) + b"\x00"
                entries.append(pre + body)
            plains[ci] = table_bytes(entries)
        return chunks_bytes(plains)


def item_prefix(entry):
    return ITEM_HEADER.get(entry[4]) if len(entry) > 8 else None


class AreaFile:
    """ET0010: [count:u16] records of [2 bytes][26-byte name, space padded][NUL]."""

    def __init__(self, data=None):
        self.stem = "ET0010"
        self.path = os.path.join(SRC, "ET0010.BIN")
        (self.plain,) = chunks_of(open(self.path, "rb").read() if data is None else data)
        count = struct.unpack_from("<H", self.plain, 0)[0]
        if 2 + count * AREA_RECORD > len(self.plain):
            raise LayoutError("ET0010 too short for its count")
        self.names = []
        for k in range(count):
            at = 2 + k * AREA_RECORD + 2
            field = self.plain[at:at + AREA_FIELD + 1]
            if field[-1] != 0:
                raise LayoutError(f"ET0010 record {k}: no NUL after the field")
            self.names.append((at, text_of(field[:-1]).rstrip(" ")))

    def units(self):
        for k, (_at, name) in enumerate(self.names):
            if name.strip(" 　"):
                yield Unit(f"ET0010/0/{k}", name, AREA_FIELD, " ")

    def build(self, texts, encode):
        plain = bytearray(self.plain)
        for k, (at, _name) in enumerate(self.names):
            t = texts.get(f"ET0010/0/{k}")
            if t:
                raw = encode(t)
                if len(raw) > AREA_FIELD:
                    raise LayoutError(f"ET0010/0/{k}: {len(raw)} bytes > {AREA_FIELD}")
                plain[at:at + AREA_FIELD] = raw.ljust(AREA_FIELD, b" ")
        return chunks_bytes([bytes(plain)])


class P2File:
    def __init__(self, path, data=None):
        self.path = path
        self.stem = os.path.basename(path)[:-4].upper()
        (self.plain,) = chunks_of(open(path, "rb").read() if data is None else data)
        field = self.plain[P2_NAME_AT:P2_NAME_AT + P2_NAME_FIELD]
        name, _, rest = field.partition(b"\x00")
        if len(self.plain) not in (121, 122) or rest.strip(b"\x00"):
            raise LayoutError(f"{self.stem}: unexpected name field {field.hex(' ')}")
        self.name = text_of(name)

    def units(self):
        if self.name:
            yield Unit(f"{self.stem}/name", self.name, P2_NAME_FIELD - 1, "\0")

    def build(self, texts, encode):
        t = texts.get(f"{self.stem}/name")
        plain = bytearray(self.plain)
        if t:
            raw = encode(t)
            if len(raw) > P2_NAME_FIELD - 1:
                raise LayoutError(f"{self.stem}/name: {len(raw)} bytes > {P2_NAME_FIELD - 1}")
            plain[P2_NAME_AT:P2_NAME_AT + P2_NAME_FIELD] = raw.ljust(P2_NAME_FIELD, b"\x00")
        return chunks_bytes([bytes(plain)])


class MapFile:
    """[0:u16][name offset:u16][count:u16][count section offsets:u16][name\\0][sections].

    The sections never move. Every section opens with SECTION_POINTERS absolute
    offsets into itself, and those could be moved with them - but the map data
    holds absolute offsets elsewhere as well, which nothing here can find. M0010
    (原宿 shelter) is where that showed: a name one byte longer than the original
    moved the sections by one, and entering the cult house on its ninth floor
    left the game asking its virtual memory for a handle it had never been given
    ("no use hnd req") and dropping back to DOS.

    So a translation that fits the bytes the original name took is padded with
    spaces into that field, and a longer one is written after the sections
    instead, with the name offset in the header pointing at it. Either way every
    byte from the first section on is the byte the game was written against."""

    def __init__(self, path, data=None):
        self.path = path
        self.stem = os.path.basename(path)[:-4].upper()
        (self.plain,) = chunks_of(open(path, "rb").read() if data is None else data)
        zero, name_at, count = struct.unpack_from("<3H", self.plain, 0)
        offs = list(struct.unpack_from(f"<{count}H", self.plain, 6))
        end = self.plain.index(b"\x00", name_at)
        after = name_at > offs[-1]                # a name this build moved out behind the sections
        if zero != 0 or offs != sorted(offs) or offs[-1] > len(self.plain) \
                or (not after and (name_at != 6 + 2 * count or offs[0] != end + 1)):
            raise LayoutError(f"{self.stem}: unexpected header")
        for i, o in enumerate(offs):
            stop = offs[i + 1] if i + 1 < count else len(self.plain)
            ptrs = struct.unpack_from(f"<{SECTION_POINTERS}H", self.plain, o)
            if not all(o + 2 * SECTION_POINTERS <= p <= stop for p in ptrs):
                raise LayoutError(f"{self.stem}: section {i} pointers leave the section")
        self.count, self.name_at, self.offs = count, name_at, offs
        self.name = text_of(self.plain[name_at:end])
        # bytes the name has where the original keeps it, the NUL not counted
        self.field = 0 if after else self.offs[0] - self.name_at - 1

    def units(self):
        if self.name.strip(" 　"):
            yield Unit(f"{self.stem}/name", self.name, MAP_NAME_MAX, None)

    def build(self, texts, encode):
        t = texts.get(f"{self.stem}/name")
        if not t:
            return chunks_bytes([self.plain])
        raw = encode(t)
        if len(raw) > MAP_NAME_MAX:
            raise LayoutError(f"{self.stem}/name: {len(raw)} bytes > {MAP_NAME_MAX}")
        if len(raw) <= self.field:
            raw += b" " * (self.field - len(raw))
            return chunks_bytes([self.plain[:self.name_at] + raw + self.plain[self.offs[0] - 1:]])
        plain = bytearray(self.plain)          # the original name field stays where it is, unused
        struct.pack_into("<H", plain, 2, len(plain))
        plain += raw + b"\x00"
        return chunks_bytes([bytes(plain)])


# A newline is part of a string here: several of the executable's messages are written over two lines,
# and leaving \n out of the run would mean those strings never matched at all.
EXE_STRING = re.compile(
    rb"(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e\xa1-\xdf\x0a]){2,}\x00")
JP_CHARS = re.compile(r"[぀-ヿ一-鿿]")
PRINTF = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[hlL]?[diouxXcsfeEgGp%]")
# Matches that are not text: floating-point constant tables.
EXE_NOT_TEXT = {0x0529C3, 0x052A6D, 0x052AF7}
# Leading bytes a match took from the field before the string: the id byte of an
# ailment record ([id][7-byte name]), the 48h high byte of a far pointer to
# DGROUP 48FC, "DNL" before 哀願的 (the pointer table after the attitude
# names targets 哀願的 itself), and ten far pointers into 25CA (xx60 25CA)
# before the command panel's 「[ITEM] 使用できる人が居ません」.
EXE_LEAD = {0x04DFFC: 40, 0x04ECF4: 1, 0x04ED84: 1, 0x04ED8C: 1, 0x04F4E4: 3, 0x04F52D: 1,
            0x050491: 1, 0x0504B1: 1, 0x050699: 1}


class ExeFile:
    """NUL-terminated Shift-JIS strings with Japanese in the data segment, rewritten in place.

    A translation keeps the string's byte length at most (NUL padded) and the
    same printf conversions in the same order."""

    def __init__(self, data=None):
        self.stem = "DDS98.EXE"
        self.path = os.path.join(SRC, "DDS98.EXE")
        self.data = open(self.path, "rb").read() if data is None else data
        main_end = struct.unpack_from("<H", self.data, 4)[0] * 512
        self.strings = []
        seen = set()
        for m in EXE_STRING.finditer(self.data, DGROUP_FILE, main_end):
            if m.start() in EXE_NOT_TEXT:
                seen.add(m.start())
                continue
            lead = EXE_LEAD.get(m.start(), 0)
            seen.add(m.start()) if lead else None
            raw = m.group()[lead:-1]
            try:
                s = text_of(raw, newlines=True)
            except LayoutError:
                continue
            if len(JP_CHARS.findall(s)) >= 2:
                self.strings.append((m.start() + lead, len(raw), s))
        missing = (EXE_NOT_TEXT | set(EXE_LEAD)) - seen
        if missing:
            raise LayoutError(f"DDS98.EXE: expected matches not found at {sorted(missing)}")

    def units(self):
        for at, n, s in self.strings:
            yield Unit(f"DDS98.EXE/@{at:06X}", s, n, "\0")

    def build(self, texts, encode):
        data = bytearray(self.data)
        for at, n, s in self.strings:
            t = texts.get(f"DDS98.EXE/@{at:06X}")
            if t:
                if PRINTF.findall(t) != PRINTF.findall(s):
                    raise LayoutError(f"DDS98.EXE/@{at:06X}: printf conversions differ from the Japanese")
                raw = encode_lines(t, encode)
                if len(raw) > n:
                    raise LayoutError(f"DDS98.EXE/@{at:06X}: {len(raw)} bytes > {n}")
                data[at:at + n] = raw.ljust(n, b"\x00")
        return bytes(data)


def sources():
    out = [
        StringTableFile("ET0000", [2, 3, 4, 5], ["name"], lambda e: 0),
        StringTableFile("ET000D", [1], ["name"], lambda e: 0),
        StringTableFile("ET0101", [0], ["name"], lambda e: 1 if e[:1] == b"\x00" else None),
        StringTableFile("ET0001", [0], ["name", "desc"], item_prefix),
        StringTableFile("ET0004", [0], ["name", "desc"], lambda e: SKILL_HEADER),
        AreaFile(),
    ]
    out += [P2File(p) for p in sorted(glob.glob(os.path.join(SRC, "P2*.BIN")))]
    out += [MapFile(p) for p in sorted(glob.glob(os.path.join(SRC, "M0*.BIN")))]
    out.append(ExeFile())
    return out


def validate():
    total = 0
    for src in sources():
        units = list(src.units())
        total += len(units)
        rebuilt = src.build({}, None)
        original = open(src.path, "rb").read()
        same = "identical" if rebuilt == original else "DIFFERS"
        if not src.stem.startswith(("P2", "M0")) or rebuilt != original:
            sample = " | ".join(u.jp for u in units[:4])
            print(f"{src.stem}: {len(units)} units, rebuild {same}; {sample[:80]}")
    p2 = sum(1 for s in sources() if s.stem.startswith("P2"))
    print(f"(P2: {p2} files, M: 100 files rebuilt identically unless listed)")
    print(f"{total} units")


if __name__ == "__main__":
    if sys.argv[1:2] == ["validate"]:
        validate()
    else:
        print(__doc__)
