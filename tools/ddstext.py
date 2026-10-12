#!/usr/bin/env python3
"""Load every MS record and expand dictionary references into readable text.

A dictionary reference `NN xx` (NN 01..08) is a subroutine call: 1603:60DA
passes file 0x7F00+NN-1 and record xx to 83C2, which pushes a script frame
(5660) and runs that record (83EA -> 857E -> 8420). Dictionary records are
ordinary script, so they may hold text, commands and further references.

    Corpus(src)                 every script record (MS and ID files), decrypted
    corpus.files[stem]          -> [(chunk, rid, cond, payload)], stem like "ID00C1"
    corpus.expand(payload)      -> [Seg]; references carry their expansion
    plain(segs)                 -> str, text only (0A shown as a newline)
"""
from ddscrypt import decrypt
from ddsvm import iter_tokens
from msdump import chunks, records, script_files

DICT_FILES = [f"MS7F0{k}" for k in range(8)]


class Seg:
    """kind 'text': value = str; 'ref': value = (dict, index), sub = [Seg];
    'cmd': value = (code, raw bytes)."""
    __slots__ = ("kind", "value", "sub", "start", "end")

    def __init__(self, kind, value, start, end, sub=None):
        self.kind, self.value, self.start, self.end, self.sub = kind, value, start, end, sub

    def __repr__(self):
        return f"<{self.kind} {self.value!r}>"


class Corpus:
    def __init__(self, src="files/DDS98"):
        self.src = src
        self.files = {}          # stem -> [(chunk, rid, cond, payload)]
        for stem, path in script_files(src):
            recs = []
            for ci, ch in enumerate(chunks(open(path, "rb").read())):
                for rid, cond, payload in records(decrypt(ch)[1]):
                    recs.append((ci, rid, cond, payload))
            self.files[stem] = recs
        self.dicts = {k: {rid: p for _c, rid, _cd, p in self.files[name]}
                      for k, name in enumerate(DICT_FILES)}

    def expand(self, payload, depth=0):
        if depth > 16:
            raise RecursionError("dictionary references nest deeper than 16")
        out, text, text_at = [], bytearray(), 0

        def flush(end):
            if text:
                out.append(Seg("text", text.decode("cp932", "replace"), text_at, end))
                text.clear()

        for t in iter_tokens(payload):
            if t.kind == "text":
                if not text:
                    text_at = t.start
                text += payload[t.start:t.end]
                continue
            flush(t.start)
            if t.dict_ref:
                k, idx = t.dict_ref
                sub = self.expand(self.dicts[k][idx], depth + 1)
                out.append(Seg("ref", (k, idx), t.start, t.end, sub))
            else:
                out.append(Seg("cmd", (t.code, bytes(payload[t.start:t.end])), t.start, t.end))
        flush(len(payload))
        return out


def plain(segs):
    parts = []
    for s in segs:
        if s.kind == "text":
            parts.append(s.value)
        elif s.kind == "ref":
            parts.append(plain(s.sub))
        elif s.value[0] == 0x0A:
            parts.append("\n")
    return "".join(parts)
