#!/usr/bin/env python3
"""One way to name and reach any editable record in the game's data.

A target is written as the data file's name, optionally followed by "#" and a record number:

    P2177        the whole of a demon file, whose single chunk is the record
    ET0004#102   record 102 of a table file, found through the table's own pointer list
    ET0001#315

Offsets in an edit are counted from the start of the record, not the file, so they stay valid when a
build moves a record: the Chinese build's names are not the same length as the Japanese ones, so a
table's pointer list differs between the two, and the base is resolved against whichever file is in
front of us at the time.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etfields  # noqa: E402
import tables  # noqa: E402
from tables import chunks_bytes, chunks_of  # noqa: E402

TARGET = re.compile(r"^([A-Za-z0-9_]+)(?:#(\d+))?$")


class RecordError(ValueError):
    pass


def parse(target):
    """'ET0004#102' -> ('ET0004', 102); 'P2177' -> ('P2177', None)."""
    m = TARGET.match(target)
    if not m:
        raise RecordError(f"看不懂的目标名：{target}")
    return m.group(1), (int(m.group(2)) if m.group(2) is not None else None)


def file_of(target):
    return parse(target)[0]


def plain_of(blob):
    """The one decrypted chunk of a data file."""
    chunks = chunks_of(blob)
    if len(chunks) != 1:
        raise RecordError(f"这个文件有 {len(chunks)} 个块，不是单块表")
    return bytearray(chunks[0])


def encode(plain):
    return chunks_bytes([bytes(plain)])


def base_of(plain, target):
    """Where the record starts inside the file's plaintext."""
    stem, index = parse(target)
    if index is None:
        return 0
    ptrs = etfields.pointers(plain)
    if not 0 <= index < len(ptrs):
        raise RecordError(f"{stem} 只有 {len(ptrs)} 条记录，没有第 {index} 条")
    return ptrs[index]


def length_of(plain, target):
    """How many bytes of the record an edit may touch."""
    stem, index = parse(target)
    if index is None:
        return len(plain)
    return etfields.head_len(plain, base_of(plain, target), stem)


def read(plain, target, off, width):
    base = base_of(plain, target)
    if off + width > length_of(plain, target):
        raise RecordError(f"{target} 的记录放不下偏移 0x{off:02X}")
    if width == 1:
        return plain[base + off]
    return struct.unpack_from("<H" if width == 2 else "<I", plain, base + off)[0]


def write(plain, target, off, width, value):
    base = base_of(plain, target)
    if off + width > length_of(plain, target):
        raise RecordError(f"{target} 的记录放不下偏移 0x{off:02X}")
    if width == 1:
        plain[base + off] = value
    else:
        struct.pack_into("<H" if width == 2 else "<I", plain, base + off, value)


def names(plain, target):
    """(japanese name, record kind) of a record, for showing which one it is."""
    stem, index = parse(target)
    if index is None:
        raw, _, _rest = bytes(plain[tables.P2_NAME_AT:tables.P2_NAME_AT
                                    + tables.P2_NAME_FIELD]).partition(b"\x00")
        return tables.text_of(raw), None
    base = base_of(plain, target)
    head = etfields.head_len(plain, base, stem)
    raw, _, _rest = bytes(plain[base + head:]).partition(b"\x00")
    return tables.text_of(raw), (None if stem == "ET0004" else plain[base + 4])
