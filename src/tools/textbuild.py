#!/usr/bin/env python3
"""Write translated units back into script records.

encode_unit(text, charmap)       unit text (characters, newlines, tags) -> bytes
encode_plain(text, charmap)      table text (characters only) -> bytes
check_tags(jp, zh)               the tag rules a translation must keep
rebuild_record(payload, toks, units, texts, charmap, commands, appends)
                                 new payload with the given units replaced,
                                 commands rewritten and commands put after
                                 tokens (tools/holds.py); branches relocated,
                                 record re-verified
layout_record(...)               the same, and where each original token went

Tag rules: the translation holds the same tags as the Japanese, as a multiset;
the structural tags (speaker field, text speed, slow text) keep their order,
while names, numbers, dictionary calls and gaiji may move freely.
"""
import collections

from ddsvm import layout, tokenize
from units import BARE, PREFIX_BYTES, TAG_RE, TAGS

STRUCTURAL = {"spk", "/spk", "slow", "/slow", "speed"}
FREE = {"name", "num", "call", "gaiji"}
_BY_NAME = {name: code for code, name in {**TAGS, **BARE}.items()}


class UnitError(ValueError):
    pass


def tags_of(text):
    return [(m.group(1), m.group(2)) for m in TAG_RE.finditer(text)]


def encode_tag(name, ops):
    if name in BARE.values():
        if ops is not None:
            raise UnitError(f"{{{name}}} takes no operand")
        return PREFIX_BYTES[_BY_NAME[name]]
    if ops is None:
        raise UnitError(f"{{{name}}} needs an operand")
    if name in TAGS.values():
        return PREFIX_BYTES[_BY_NAME[name]] + bytes.fromhex(ops)
    if name == "call":
        k, _, idx = ops.partition(":")
        return bytes([0x01 + int(k), int(idx, 16)])
    if name == "gaiji":
        raw = bytes.fromhex(ops)
        if len(raw) != 2:
            raise UnitError(f"{{gaiji:{ops}}} must be two bytes")
        return raw
    raise UnitError(f"unknown tag {{{name}}}")


def encode_unit(text, charmap):
    out = bytearray()
    pos = 0
    for m in TAG_RE.finditer(text):
        out += _encode_chars(text[pos:m.start()], charmap)
        out += encode_tag(m.group(1), m.group(2))
        pos = m.end()
    out += _encode_chars(text[pos:], charmap)
    return bytes(out)


def encode_plain(text, charmap):
    """A table text: characters only, no tags and no newline."""
    if "\n" in text:
        raise UnitError("a newline in a table text")
    return _encode_chars(text, charmap)


def _encode_chars(s, charmap):
    out = bytearray()
    for ch in s:
        if ch in "{}":
            raise UnitError("a brace that is not part of a tag")
        try:
            out += charmap.encode_char(ch)
        except ValueError as e:
            raise UnitError(str(e)) from None
    return out


def check_tags(jp, zh):
    """List of problems with the tags of a translation."""
    a, b = tags_of(jp), tags_of(zh)
    problems = []
    if collections.Counter(a) != collections.Counter(b):
        missing = collections.Counter(a) - collections.Counter(b)
        extra = collections.Counter(b) - collections.Counter(a)
        if missing:
            problems.append("missing " + " ".join(_fmt(t) for t in missing.elements()))
        if extra:
            problems.append("unexpected " + " ".join(_fmt(t) for t in extra.elements()))
    elif [t for t in a if t[0] in STRUCTURAL] != [t for t in b if t[0] in STRUCTURAL]:
        problems.append("speaker/speed/slow tags out of order")
    stray = TAG_RE.sub("", zh)
    if "{" in stray or "}" in stray:
        problems.append("a brace that is not part of a tag")
    return problems


def _fmt(tag):
    name, ops = tag
    return "{" + name + (":" + ops if ops is not None else "") + "}"


def rebuild_record(payload, toks, units, texts, charmap, commands=None, appends=None):
    """texts: {unit index: text}; commands: {token index: bytes} replacing tokens outside the
    translated units; appends: {token index: bytes} put after tokens outside them or after the last
    token of one, which is after the unit's whole text. Returns the new payload."""
    return layout_record(payload, toks, units, texts, charmap, commands, appends)[0]


def layout_record(payload, toks, units, texts, charmap, commands=None, appends=None):
    """rebuild_record(), and where each original token's bytes went (tools/ddsvm.py layout())."""
    replace = {}
    for k, text in texts.items():
        u = units[k]
        for i in range(u.first, u.last):
            if toks[i].rel:
                raise UnitError(f"unit @{u.start:04X} contains a branch operand")
            replace[i] = b""
        replace[u.first] = encode_unit(text, charmap)
    in_units = {i for u in units for i in range(u.first, u.last)}
    unit_ends = {u.last - 1 for u in units}
    for i, raw in (commands or {}).items():
        if i in replace:
            raise UnitError(f"command @{toks[i].start:04X} is part of a translated unit")
        replace[i] = raw
    for i in appends or {}:
        if i in in_units and i not in unit_ends:
            raise UnitError(f"an addition after @{toks[i].start:04X} would go inside a unit")
    new, placed = layout(payload, toks, replace, appends)
    tokenize(new)
    return new, placed
