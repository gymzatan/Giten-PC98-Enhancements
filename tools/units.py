#!/usr/bin/env python3
"""Translation units of the script records, and their text form.

A unit is a maximal run of tokens that is rewritten as one piece of text:

    text tokens
    references to plain dictionary entries      shown expanded
    inline commands                              shown as tags

Anything else ends a unit: branches, window control, click waits, `00`, and
references to dictionary entries that are not plain. So does a token that a
branch of the record jumps to, because a unit is only ever entered at its first
token. A run whose text is empty or only spaces is not a unit.

Plain dictionary entry: a MS7F00..07 record made of text, references to plain
entries and a final 00. MS7F03/04 also hold entries with branches and variable
output; a reference to such an entry is the tag {call:K:XX} and the entry's own
text is extracted as units of that record.

Tags carry their operand bytes in hex, exactly as stored:
    {name:OPS}      1F 01  name of a character or demon
    {num:OPS}       1F 02  number
    {spk} {/spk}    1F D2 / 1F D3  speaker field, as in {spk}英美：{/spk}
    {speed:OPS}     1F F9  text speed
    {slow} {/slow}  1F FA / 1F FB
    {call:K:XX}     dictionary K entry XX that is not plain
    {gaiji:HHHH}    a two-byte character outside JIS X 0208 (the user-defined
                    row: EB9F closes flirting lines, "ベイビー{gaiji:EB9F}")
A newline (0A) is a newline in the text.

    units.py stats
"""
import collections
import re
import sys

from checkvm import CUT_FILES, dictionary_sizes, verify
from ddstext import DICT_FILES, Corpus

TAGS = {0x101: "name", 0x102: "num", 0x1F9: "speed"}          # tag with operands
BARE = {0x1D2: "spk", 0x1D3: "/spk", 0x1FA: "slow", 0x1FB: "/slow"}
PREFIX_BYTES = {0x101: b"\x1f\x01", 0x102: b"\x1f\x02", 0x1F9: b"\x1f\xf9",
                0x1D2: b"\x1f\xd2", 0x1D3: b"\x1f\xd3", 0x1FA: b"\x1f\xfa", 0x1FB: b"\x1f\xfb"}
PAIRS = (("spk", "/spk"), ("slow", "/slow"))
TAG_RE = re.compile(r"\{(/?[a-z]+)(?::([0-9A-F:]+))?\}")
BLANK = set(" 　")
DICT_CODE = {k: k + 1 for k in range(8)}                       # dictionary K <- command 01+K


class Dicts:
    """Dictionary entries: which are plain, and the bytes/text they expand to."""

    def __init__(self, corpus):
        self.corpus = corpus
        self.entries = corpus.dicts
        self._plain = {}

    def plain(self, k, idx):
        """Expansion bytes of a plain entry (without its final 00), or None."""
        key = (k, idx)
        if key not in self._plain:
            self._plain[key] = None                                   # cycle guard
            self._plain[key] = self._expand(self.entries[k][idx])
        return self._plain[key]

    def _expand(self, payload):
        from ddsvm import tokenize
        toks = tokenize(payload)
        if not toks or toks[-1].kind != "cmd" or toks[-1].code != 0x00:
            return None
        out = bytearray()
        for t in toks[:-1]:
            if t.kind == "text":
                out += payload[t.start:t.end]
            elif t.dict_ref and self.plain(*t.dict_ref) is not None:
                out += self.plain(*t.dict_ref)
            else:
                return None
        return bytes(out)


def decode_text(raw):
    """Text of text-token bytes; two-byte codes outside JIS X 0208 become gaiji tags."""
    out, i = [], 0
    while i < len(raw):
        c = raw[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            pair = raw[i:i + 2]
            if c >= 0xEB:
                out.append("{gaiji:" + pair.hex().upper() + "}")
            else:
                out.append(pair.decode("cp932"))
            i += 2
        else:
            out.append(raw[i:i + 1].decode("cp932"))
            i += 1
    return "".join(out)


def token_text(payload, t, dicts):
    """Text form of one token inside a unit, or None when the token ends a unit."""
    raw = payload[t.start:t.end]
    if t.kind == "text":
        return decode_text(raw)
    if t.dict_ref:
        body = dicts.plain(*t.dict_ref)
        if body is not None:
            return decode_text(body)
        k, idx = t.dict_ref
        return f"{{call:{k}:{idx:02X}}}"
    if t.code == 0x0A:
        return "\n"
    if t.code in BARE:
        return "{" + BARE[t.code] + "}"
    if t.code in TAGS:
        ops = raw[len(PREFIX_BYTES[t.code]):]
        return "{" + TAGS[t.code] + ":" + ops.hex().upper() + "}"
    return None


class Unit:
    __slots__ = ("first", "last", "start", "end", "jp")

    def __init__(self, first, last, start, end, jp):
        self.first, self.last, self.start, self.end, self.jp = first, last, start, end, jp


def split_units(payload, toks, dicts):
    """Units of one record: token index range [first, last) and the text."""
    targets = {target for t in toks for _field, target in t.rel}
    units = []
    run, parts = [], []

    def close():
        if run:
            text = "".join(parts)
            plain = TAG_RE.sub("", text).replace("\n", "")
            if plain and not set(plain) <= BLANK:
                a, b = run[0], run[-1] + 1
                units.append(Unit(a, b, toks[a].start, toks[b - 1].end, text))
        run.clear()
        parts.clear()

    for i, t in enumerate(toks):
        s = token_text(payload, t, dicts)
        if s is None:
            close()
            continue
        if run and t.start in targets:
            close()
        run.append(i)
        parts.append(s)
    close()
    return units


def script_units(src="files/DDS98"):
    """Yield (stem, chunk, position, record, tokens, units) for every translatable record."""
    corpus = Corpus(src)
    dicts = Dicts(corpus)
    sizes = dictionary_sizes(src)
    for stem, recs in corpus.files.items():
        if stem + ".BIN" in CUT_FILES:
            continue
        pos_in_chunk = collections.Counter()
        for ci, rid, cond, payload in recs:
            pos = pos_in_chunk[ci]
            pos_in_chunk[ci] += 1
            if stem in DICT_FILES and dicts.plain(DICT_FILES.index(stem), rid) is not None:
                continue
            problems, toks = verify(payload, sizes, False)
            if problems:
                continue
            yield stem, ci, pos, (rid, cond, payload), toks, split_units(payload, toks, dicts)


def stats():
    n_units = n_records = 0
    chars = 0
    unique = collections.Counter()
    tags = collections.Counter()
    longest = []
    per_type = collections.Counter()
    for stem, ci, pos, (rid, cond, payload), toks, units in script_units():
        if units:
            n_records += 1
        for u in units:
            n_units += 1
            per_type[stem[:2] if not stem.startswith("MS7F") else "MS7F"] += 1
            plain = TAG_RE.sub("", u.jp)
            chars += len(plain)
            unique[u.jp] += 1
            for m in TAG_RE.finditer(u.jp):
                tags[m.group(1)] += 1
            longest.append((len(plain), stem, ci, pos, u.start))
    longest.sort(reverse=True)
    uchars = sum(len(TAG_RE.sub("", s)) for s in unique)
    print(f"units {n_units} in {n_records} records ({dict(per_type)}), {chars} characters")
    print(f"distinct unit texts {len(unique)}, {uchars} characters")
    print(f"tags {dict(tags)}")
    print(f"longest units: {longest[:5]}")
    print(f"most repeated: {[(s.replace(chr(10), '⏎')[:20], n) for s, n in unique.most_common(12)]}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["stats"]:
        stats()
    else:
        print(__doc__)


def unit_id(stem, ci, pos, start):
    return f"{stem}/{ci}/{pos}@{start:04X}"

