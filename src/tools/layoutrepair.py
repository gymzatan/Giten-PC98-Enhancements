"""The Japanese game's commands that a same-layout translation overwrote, and their restoration.

delacannon's translation (github.com/delacannon/giten-megami-tensei-tokyo-mokushiroku-i18n) keeps every script
record at its Japanese byte layout: the display content between two commands - text, newlines, dictionary words,
the name/number prints a translator moves within a sentence, and the 1F57 it pads with - keeps its length, so every
other Japanese command stays at its offset. Its tool misreads the operands of some commands (a small last operand
byte and the next command's first byte taken for a dictionary word) and writes the word's translation over them:
jumps, conditions, menu entries and returns become letters ("DB", "Gun ", "Hay ", "ou!"). Those bytes are no text
the game was meant to show; this module puts the Japanese command bytes back and leaves every display byte as the
translation has it.

repairs(jp_blob, tr_blob) -> the edits for one script file; apply(blob, edits) -> the file with them; problems(...)
-> what still does not hold after them (a check, not a further repair).
"""
import ddsfile
import ddsvm
import enhancement_plan

# what a translator writes between two commands: text and newlines are tokens of their own; dictionary words
# (01-08), the name, number and other prints (101, 102, 23E) and the 1F57 padding
PRINTS = {0x101, 0x102, 0x23E}
DISPLAY = set(range(0x001, 0x009)) | {0x00A, 0x157} | PRINTS


def commands(payload):
    """[(start, end)] of the record's commands outside DISPLAY, or None when the record does not parse (the
    game's own dead data)."""
    try:
        toks = ddsvm.tokenize(payload)
    except ddsvm.ParseError:
        return None
    return [(t.start, t.end) for t in toks if t.kind == "cmd" and t.code not in DISPLAY]


def _pairs(jp_blob, tr_blob):
    """(chunk, position, Japanese record, translated record) for every record, paired by position: the
    translation keeps each chunk's records in order and only appends records (to the dictionaries)."""
    a, _ = enhancement_plan.script(jp_blob)
    b, _ = enhancement_plan.script(tr_blob)
    if len(a) != len(b):
        raise ValueError("the translation changed the number of chunks")
    for ci, (ca, cb) in enumerate(zip(a, b)):
        if [(r.rid, r.cond) for r in cb[:len(ca)]] != [(r.rid, r.cond) for r in ca]:
            raise ValueError(f"chunk {ci}: the translation reordered or dropped records")
        for pos, r in enumerate(ca):
            yield ci, pos, r, cb[pos]


def repairs(jp_blob, tr_blob):
    """[{chunk, pos, rid, cond, at, before, after}]: each Japanese command the translation changed, its bytes
    in the translation (before) and in the Japanese game (after). A record whose length differs is refused:
    the module is for translations that keep the layout."""
    out = []
    for ci, pos, ja, tr in _pairs(jp_blob, tr_blob):
        if ja.payload == tr.payload:
            continue
        if len(ja.payload) != len(tr.payload):
            raise ValueError(f"chunk {ci} record {pos}: the translation changed its length")
        spans = commands(ja.payload)
        if spans is None:
            continue
        for start, end in spans:
            was, want = tr.payload[start:end], ja.payload[start:end]
            if was != want:
                out.append(dict(chunk=ci, pos=pos, rid=ja.rid, cond=list(ja.cond) if ja.cond else None,
                                at=start, before=was.hex(), after=want.hex()))
    return out


def apply(blob, edits):
    """The script file with the edits made; each edit's bytes must be as recorded."""
    chunks = ddsfile.parse(blob)
    for e in edits:
        r = chunks[e["chunk"]][e["pos"]]
        if (r.rid, list(r.cond) if r.cond else None) != (e["rid"], e["cond"]):
            raise ValueError(f"chunk {e['chunk']} record {e['pos']}: not record {e['rid']:02X}")
        before, after = bytes.fromhex(e["before"]), bytes.fromhex(e["after"])
        if r.payload[e["at"]:e["at"] + len(before)] != before:
            raise ValueError(f"chunk {e['chunk']} record {e['rid']:02X} +{e['at']}: not the recorded bytes")
        r.payload = r.payload[:e["at"]] + after + r.payload[e["at"] + len(before):]
    return ddsfile.build(chunks)


def problems(jp_blob, repaired_blob, dict_sizes):
    """What a repaired file still has that the Japanese layout rules out: per record, a Japanese command not
    found at its offset, a display span holding a token that runs past the span or is not display content, a
    dictionary word past the end of its dictionary (dict_sizes: [entries in MS7F00..MS7F07] of the translation)."""
    out = []
    for ci, pos, ja, tr in _pairs(jp_blob, repaired_blob):
        if ja.payload == tr.payload:
            continue
        spans = commands(ja.payload)
        if spans is None:
            continue
        where = f"chunk {ci} record {ja.rid:02X}"
        try:
            toks = ddsvm.tokenize(tr.payload)
        except ddsvm.ParseError as e:
            out.append(f"{where}: does not parse ({e})")
            continue
        starts = {t.start: t for t in toks}
        for start, end in spans:
            t = starts.get(start)
            if t is None or t.end != end:
                out.append(f"{where} +{start}: the Japanese command is not a token here")
        inside = [(a, b) for a, b in zip([0] + [e for _, e in spans], [s for s, _ in spans] + [len(tr.payload)])
                  if a < b]
        jp_all = ddsvm.tokenize(ja.payload)
        jp_toks = {(t.start, ja.payload[t.start:t.end]) for t in jp_all}
        for lo, hi in inside:
            # the prints of a span: a translator moves them within the sentence, never changes them
            jp_prints = {ja.payload[t.start:t.end] for t in jp_all
                         if t.kind == "cmd" and t.code in PRINTS and lo <= t.start < hi}
            for t in toks:
                if t.end <= lo or t.start >= hi or (t.start, tr.payload[t.start:t.end]) in jp_toks:
                    continue        # outside the span, or the Japanese game's own token at its own place
                if t.start < lo or t.end > hi:
                    out.append(f"{where} +{t.start}: a token runs out of the display span {lo}-{hi}")
                elif t.kind == "cmd" and t.code not in DISPLAY:
                    out.append(f"{where} +{t.start}: command {t.code:03X} inside the display span {lo}-{hi}")
                elif t.dict_ref and (t.dict_ref[1] is None or t.dict_ref[1] >= dict_sizes[t.dict_ref[0]]):
                    out.append(f"{where} +{t.start}: dictionary word {t.dict_ref} past its dictionary")
                elif t.kind == "cmd" and t.code in PRINTS and tr.payload[t.start:t.end] not in jp_prints:
                    out.append(f"{where} +{t.start}: print {tr.payload[t.start:t.end].hex()} is none of the "
                               f"span's Japanese prints {sorted(p.hex() for p in jp_prints)}")
    return out
