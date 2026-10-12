#!/usr/bin/env python3
"""Script container files (MS*.BIN, ID*.BIN): parse into records and write back.

    file   = chunk+                chunk = [len:u16][len bytes, ddscrypt]
    chunk  = [count:u16] record*count        (after decryption)
    record = [id:u8][len:u16][payload]
           | [id:u8][FFFF][a:u8][b:u8][len:u16][payload]   conditional record

The game reads the encryption header word as the chunk's byte count (1603:9458),
so a rebuilt chunk always gets header = its new length. Record order inside a
chunk is kept as stored.

    ddsfile.py check [src]     rebuild every script file unchanged; must be
                               byte-identical to the original
"""
import struct
import sys

from ddscrypt import decrypt, encrypt
from msdump import chunks, records, script_files


class Record:
    __slots__ = ("rid", "cond", "payload")

    def __init__(self, rid, cond, payload):
        self.rid, self.cond, self.payload = rid, cond, payload


def parse(data):
    """-> [[Record]] per chunk."""
    out = []
    for ch in chunks(data):
        w, plain = decrypt(ch)
        if w != len(ch) - 2:
            raise ValueError(f"chunk header {w} != chunk length {len(ch) - 2}")
        out.append([Record(rid, cond, bytes(p)) for rid, cond, p in records(plain)])
    return out


def build_chunk(recs):
    plain = bytearray(struct.pack("<H", len(recs)))
    for r in recs:
        if len(r.payload) >= 0xFFFF:
            raise ValueError(f"record {r.rid:02X} too long ({len(r.payload)} B)")
        if r.cond is None:
            plain += struct.pack("<BH", r.rid, len(r.payload))
        else:
            plain += struct.pack("<BHBBH", r.rid, 0xFFFF, r.cond[0], r.cond[1], len(r.payload))
        plain += r.payload
    if len(plain) > 0xFFFF:
        raise ValueError(f"chunk too long ({len(plain)} B)")
    return encrypt(bytes(plain))


def build(parsed):
    return b"".join(build_chunk(recs) for recs in parsed)


def check(src="files/DDS98"):
    bad = 0
    n = 0
    for stem, path in script_files(src):
        data = open(path, "rb").read()
        n += 1
        if build(parse(data)) != data:
            bad += 1
            print(f"{stem}: rebuild differs")
    print(f"{n} script files rebuilt, {bad} differ")
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]:
        sys.exit(check(*sys.argv[2:]))
    print(__doc__)
