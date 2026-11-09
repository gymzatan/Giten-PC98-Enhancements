#!/usr/bin/env python3
"""Write text/delacannon_compatibility.json: what the build does to delacannon's translation before the fixes
(tools/english_enhancements.py), for each of its languages.

python tools/delacannoncompat.py EN.hdi ES.hdi   the reference images: the Japanese reference HDI patched by
                                                 delacannon's page patcher (build/enhancements/delacannon/)

Per language:
  image_sha256   the reference image the build accepts
  repairs        how many Japanese commands tools/layoutrepair.py restores (the build recomputes them and
                 stops when the count differs)
  spans          the display spans those repairs still leave broken (layoutrepair.problems), each replaced as
                 a whole: before = the span after the repairs, after = the span the build writes, why

A broken span gets one of these, in this order:
  notext   a span whose Japanese content is prints and newlines only, holding letters in the translation: the
           Japanese span (there is nothing to translate in it).
  print    a name print the tool cut to five bytes ("1F01 00 b 03" of the Japanese "1F01 00 b 03 v"): its last
           operand byte became the next display byte, and where the tool then wrote v after a run of spaces and
           1F57 that run and v go; the print gets v back. The span keeps its length: the pad at its end (spaces
           and 1F57 before its last newline) takes up or gives the difference.
  particle the Japanese conjunction of dictionary 2, word 0B (a dictionary-7 word and 、), at the head of the span,
           that the tool tried to drop: its two bytes, and Japanese text the tool left right behind them, become 1F57.
  name     the span's first Japanese name print, overwritten by letters (the tool's text started early): the
           print again, a space, then the translation's text from the print's end.
Then every Japanese branch that jumps into a display span at the start of a line, where the translation's line
starts elsewhere (the jump lands inside its text or a name print):
  target   the branch's offset (2 bytes) changed to jump to the start of the translation's same line (the line after
           as many newlines of the span).
A Japanese target inside a line has no place in a translation that orders the words otherwise; such a branch is
listed (`unmatched`) and left as the translation has it.
Last, the records a list command (298) runs for its header and each item:
  formatter every 1F57 the translation added there becomes two spaces. The list runs such a record until it returns,
           and a 1F57 returns from it (-3) - inside the captured text the record hands the list - so the list is
           drawn from half a record: delacannon's Spanish load list (MS00AF 27) breaks the CONTINUE menu, and the
           shop and debug lists break alike. The spaces keep the text at its Japanese length.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
sys.path[:0] = [str(HERE), str(WORK)]
import ddsfile  # noqa: E402
import ddsvm  # noqa: E402
import enhancement_plan  # noqa: E402
import layoutrepair  # noqa: E402

OUT = WORK / "text" / "delacannon_compatibility.json"
SOURCE = {"repository": "https://github.com/delacannon/giten-megami-tensei-tokyo-mokushiroku-i18n",
          "commit": "406c4dc9fc8fa9e2d9d53889a7b5a0c6795c7648", "version": "2026.11.03"}
YIELD = b"\x1f\x57"
PARTICLE = b"\x03\x0b"


def dds98(path):
    from fat12 import open_hdi
    from fat12w import Fat12W
    _raw, _hdr, disk, part = open_hdi(str(path))
    fs = Fat12W(disk, part)
    return {n.split("/", 1)[1]: bytes(fs.read_chain(e["cluster"], e["size"])) for n, e in fs.walk()
            if n.startswith("DDS98/") and n.count("/") == 1}


def repad(old, core):
    """`core` laid into a span as long as `old`: the pad at old's end (spaces and 1F57 before its last newline)
    is what gives way."""
    nl = old.endswith(b"\n")
    body = old[:-1] if nl else old
    room = len(old) - len(core) - (1 if nl else 0)
    if room < 0:
        raise ValueError(f"the repaired span is {-room} bytes too long")
    return core + YIELD * (room // 2) + b" " * (room % 2) + (b"\n" if nl else b"")


def strip_pad(b):
    """b without its pad: trailing spaces and 1F57 (before a last newline, which is dropped too)."""
    if b.endswith(b"\n"):
        b = b[:-1]
    while True:
        if b.endswith(YIELD):
            b = b[:-2]
        elif b.endswith(b" "):
            b = b[:-1]
        else:
            return b


def span_tokens(payload, lo, hi):
    return [t for t in ddsvm.tokenize(payload) if lo <= t.start < hi]


def fix_span(jp, tr, lo, hi):
    """(kind, new span bytes) for a broken display span [lo, hi) of a record, or None."""
    js, ts = jp[lo:hi], tr[lo:hi]
    jtoks = span_tokens(jp, lo, hi)
    jtext = [t for t in jtoks if t.kind == "text" or t.dict_ref]
    if not jtext:
        return "notext", js
    jprints = [jp[t.start:t.end] for t in jtoks if t.kind == "cmd" and t.code == 0x101 and t.end - t.start == 6]
    # print: a Japanese six-byte print whose first five bytes stand in the translation with another sixth
    for j in jprints:
        at = ts.find(j[:5])
        if at < 0 or ts[at:at + 6] == j:
            continue
        k = at + 5
        while ts[k:k + 2] == YIELD or ts[k:k + 1] == b" ":
            k += 2 if ts[k:k + 2] == YIELD else 1
        if ts[k:k + 1] == j[5:6]:
            core = ts[:at] + j + ts[k + 1:]            # v found after the run: the run and v go
        else:
            core = ts[:at] + j + ts[at + 5:]           # v lost: the run stays, as the separator it was
        return "print", repad(ts, strip_pad(core))
    if js.startswith(PARTICLE) and ts[1:2] == PARTICLE[1:] and ts[:1] != PARTICLE[:1]:
        k = 2
        while k + 2 <= len(ts) and ts[k:k + 2] == js[k:k + 2] and ddsvm.is_lead(ts[k]):
            k += 2                                     # Japanese text the tool left behind the particle
        return "particle", YIELD * (k // 2) + ts[k:]
    first = jtoks[0] if jtoks else None
    if first is not None and first.kind == "cmd" and first.code == 0x101 and first.start == lo:
        n = first.end - first.start
        if ts[:n] != js[:n] and ts[n - 3:n] == js[n - 3:n]:
            return "name", repad(ts, strip_pad(js[:n] + b" " + ts[n:]))
    return None


def line_start(jp, tr, lo, hi, target):
    """Where the translation's line starts that the Japanese line starting at `target` is, in the display span
    [lo, hi) (the line after as many newlines), or None when no Japanese line starts at the target."""
    def line_ends(payload):
        return [t.end for t in ddsvm.tokenize(payload) if lo <= t.start < hi and t.kind == "cmd" and t.code == 0x00A]
    jl, tl = line_ends(jp), line_ends(tr)
    if target not in jl or len(tl) <= jl.index(target):
        return None
    return tl[jl.index(target)]


def off_targets(jp_blob, blob):
    """[(chunk, position, Japanese record, record, target, span)] of every branch target of the translation's record
    that is no token start of it, is one of the Japanese record (the game's own branches into nowhere are left
    out), and lies inside a display span."""
    out = []
    for ci, pos, ja, tr in layoutrepair._pairs(jp_blob, blob):
        if ja.payload == tr.payload:
            continue
        try:
            jt, tt = ddsvm.tokenize(ja.payload), ddsvm.tokenize(tr.payload)
        except ddsvm.ParseError:
            continue
        js, ts = {t.start for t in jt}, {t.start for t in tt} | {len(tr.payload)}
        spans = layoutrepair.commands(ja.payload)
        bounds = list(zip([0] + [e for _, e in spans], [s for s, _ in spans] + [len(ja.payload)]))
        for target in sorted({tg for t in tt for _f, tg in t.rel if tg in js and tg not in ts}):
            span = next(((lo, hi) for lo, hi in bounds if lo < target < hi), None)
            if span is not None:
                out.append((ci, pos, ja, tr, target, span))
    return out


def spans_of(name, jp_blob, blob, dict_sizes):
    """The span edits a repaired file needs (layoutrepair.problems flags the records)."""
    flagged = {}
    for p in layoutrepair.problems(jp_blob, blob, dict_sizes):
        rid = int(p.split("record ")[1].split()[0], 16)
        at = int(p.split("+")[1].split(":")[0])
        flagged.setdefault(rid, set()).add(at)
    out = []
    for ci, pos, ja, tr in layoutrepair._pairs(jp_blob, blob):
        if ja.rid not in flagged or ja.payload == tr.payload:
            continue
        spans = layoutrepair.commands(ja.payload)
        bounds = list(zip([0] + [e for _, e in spans], [s for s, _ in spans] + [len(ja.payload)]))
        done = set()
        for at in sorted(flagged[ja.rid]):
            span = next(((lo, hi) for lo, hi in bounds if lo <= at < hi), None)
            if span is None or span in done:
                continue
            done.add(span)
            fixed = fix_span(ja.payload, tr.payload, *span)
            if fixed is None:
                raise SystemExit(f"{name} chunk {ci} record {ja.rid:02X} span {span}: no rule repairs it")
            kind, after = fixed
            lo, hi = span
            if len(after) != hi - lo:
                raise SystemExit(f"{name} record {ja.rid:02X} span {span}: the repair changed its length")
            out.append(dict(file=name, chunk=ci, pos=pos, rid=ja.rid, cond=list(ja.cond) if ja.cond else None,
                            at=lo, kind=kind, before=tr.payload[lo:hi].hex(), after=after.hex()))
    return out


def target_edits(name, jp_blob, blob):
    """([edits of the `target` rule], [unmatched targets]) of a file whose broken spans are repaired."""
    edits, unmatched = [], []
    for ci, pos, ja, tr, target, (lo, hi) in off_targets(jp_blob, blob):
        start = line_start(ja.payload, tr.payload, lo, hi, target)
        if start is None:
            unmatched.append(dict(file=name, chunk=ci, rid=ja.rid, target=target))
            continue
        for t in ddsvm.tokenize(tr.payload):
            for field, tg in t.rel:
                if tg == target:
                    old = tr.payload[field:field + 2]
                    new = struct.pack("<H", (start - field - 2) & 0xFFFF)
                    edits.append(dict(file=name, chunk=ci, pos=pos, rid=ja.rid,
                                      cond=list(ja.cond) if ja.cond else None, at=field, kind="target",
                                      before=old.hex(), after=new.hex()))
    return edits, unmatched


def formatters(jp_files):
    """{(file name, record id)} of every record a list command 298 of the Japanese game runs (signature
    bbVVVVbbVVVVV: the bb after the four V name it, MS00ff and the record)."""
    out = set()
    for name, blob in jp_files.items():
        if not (name.startswith("MS") and name.endswith(".BIN")):
            continue
        for chunk in enhancement_plan.script(blob)[0]:
            for r in chunk:
                try:
                    toks = ddsvm.tokenize(r.payload)
                except ddsvm.ParseError:
                    continue
                for t in toks:
                    if t.kind == "cmd" and t.code == 0x298:
                        rd = ddsvm._Reader(r.payload, t.start + 2)
                        rd.run("bbVVVV")
                        out.add((f"MS00{r.payload[rd.p]:02X}.BIN", r.payload[rd.p + 1]))
    return out


def formatter_edits(name, jp_blob, blob, records):
    """The `formatter` rule's edits of a file: in its records `records`, each 1F57 the translation added."""
    edits = []
    for ci, pos, ja, tr in layoutrepair._pairs(jp_blob, blob):
        if ja.rid not in records:
            continue
        jy = {t.start for t in ddsvm.tokenize(ja.payload) if t.kind == "cmd" and t.code == 0x157}
        for t in ddsvm.tokenize(tr.payload):
            if t.kind == "cmd" and t.code == 0x157 and t.start not in jy:
                edits.append(dict(file=name, chunk=ci, pos=pos, rid=ja.rid, cond=list(ja.cond) if ja.cond else None,
                                  at=t.start, kind="formatter", before=YIELD.hex(), after=b"  ".hex()))
    return edits


def apply_spans(blob, edits):
    chunks = ddsfile.parse(blob)
    for e in edits:
        r = chunks[e["chunk"]][e["pos"]]
        before, after = bytes.fromhex(e["before"]), bytes.fromhex(e["after"])
        if r.rid != e["rid"] or r.payload[e["at"]:e["at"] + len(before)] != before:
            raise ValueError(f"{e['file']} record {e['rid']:02X} +{e['at']}: not the recorded span")
        r.payload = r.payload[:e["at"]] + after + r.payload[e["at"] + len(before):]
    return ddsfile.build(chunks)


def normalize(jp_files, files, entry):
    """The translation's files with the repairs and span edits made (entry: one language of the JSON)."""
    sizes = dict_sizes(files)
    lists = formatters(jp_files)
    out, count = {}, 0
    for name, blob in files.items():
        jp = jp_files.get(name)
        if jp is None or blob == jp or not (name.startswith(("MS", "ID")) and name.endswith(".BIN")):
            out[name] = blob
            continue
        reps = layoutrepair.repairs(jp, blob)
        count += len(reps)
        blob = layoutrepair.apply(blob, reps) if reps else blob
        mine = [e for e in entry["spans"] if e["file"] == name]
        blob = apply_spans(blob, mine) if mine else blob
        left = layoutrepair.problems(jp, blob, sizes)
        if left:
            raise ValueError(f"{name}: {left[0]}")
        off = {(ci, ja.rid, target) for ci, _p, ja, _t, target, _s in off_targets(jp, blob)}
        if off != {(u["chunk"], u["rid"], u["target"]) for u in entry["unmatched"] if u["file"] == name}:
            raise ValueError(f"{name}: branch targets off the translation's tokens {sorted(off)}, "
                             "not the ones text/delacannon_compatibility.json lists")
        if formatter_edits(name, jp, blob, {rid for f, rid in lists if f == name}):
            raise ValueError(f"{name}: a list's record still holds a 1F57 of the translation's")
        out[name] = blob
    if count != entry["repairs"]:
        raise ValueError(f"{count} commands restored, text/delacannon_compatibility.json says {entry['repairs']}")
    return out


def dict_sizes(files):
    return [len(enhancement_plan.script(files[f"MS7F0{k}.BIN"])[0][0]) for k in range(8)]


def main(argv):
    jp_files = {p.name: p.read_bytes() for p in (WORK / "files" / "DDS98").iterdir() if p.is_file()}
    lists = formatters(jp_files)
    out = {"source": SOURCE}
    for lang, path in zip(("en", "es"), argv):
        path = Path(path)
        files = dds98(path)
        sizes = dict_sizes(files)
        count, spans, unmatched = 0, [], []
        for name in sorted(files):
            jp = jp_files.get(name)
            if jp is None or files[name] == jp or not (name.startswith(("MS", "ID")) and name.endswith(".BIN")):
                continue
            reps = layoutrepair.repairs(jp, files[name])
            count += len(reps)
            blob = layoutrepair.apply(files[name], reps) if reps else files[name]
            broken = spans_of(name, jp, blob, sizes)
            blob = apply_spans(blob, broken) if broken else blob
            lines, lost = target_edits(name, jp, blob)
            blob = apply_spans(blob, lines) if lines else blob
            listed = formatter_edits(name, jp, blob, {rid for f, rid in lists if f == name})
            spans += broken + lines + listed
            unmatched += lost
        entry = {"image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "repairs": count, "spans": spans,
                 "unmatched": unmatched}
        normalize(jp_files, files, entry)               # every file passes layoutrepair.problems afterwards
        out[lang] = entry
        print(f"{lang}: {count} commands restored, {len(spans)} spans "
              f"({', '.join(sorted({s['kind'] for s in spans}))})")
        for s in spans:
            if s["kind"] == "formatter":
                continue
            show = lambda h: bytes.fromhex(h).decode("cp932", "replace").replace("\x1f", "~").replace("\n", "|")
            print(f"  {s['file']} {s['rid']:02X} +{s['at']} {s['kind']}: {show(s['before'])!r} -> {show(s['after'])!r}")
        listed = sorted({(s["file"], s["rid"]) for s in spans if s["kind"] == "formatter"})
        print(f"  formatter: {sum(s['kind'] == 'formatter' for s in spans)} 1F57 in {len(listed)} list records: "
              + ", ".join(f"{f[:6]} {r:02X}" for f, r in listed))
        for u in unmatched:
            print(f"  unmatched: {u['file']} {u['rid']:02X} target {u['target']}")
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main(sys.argv[1:])
