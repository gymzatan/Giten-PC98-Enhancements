#!/usr/bin/env python3
"""mk_holds.py - write text/holds.json: every kind of battle message with the hold that follows it, and
every hold of the game's own. After this the file is edited by hand ("hold" only) and checked with
run/holdmap.py --check; running this again keeps the "hold" of every entry that is still there.

What a kind of message is. The records are followed as run/holdflow.py builds and runs them. Every
visible piece a road prints belongs to a translation unit - or, for a dictionary word outside every unit,
to that word's command - and that unit is its category. Where a category's content has all been printed
(right after its unit, or after its command) the roads on are read up to what comes first:

  same   a visible print on the same line while still inside the record invocation that printed the
         category - the sentence goes on (the subject "自己" before "被刺中了", "而且" before a status);
  next   a visible print after a newline, or after that invocation has returned - another sentence;
  end    the end of the run: the category was the last thing shown;
  hold   one of the game's own holds.

A category none of whose roads is "same" ends a sentence: its hold goes right after it. One with a "same"
road is part of a sentence that can go on, and gets no entry unless it can also end a message - then,
like "恢复了N点HP" before either "，HP变成MAX了" or a newline, it gets its hold where the roads that end
the message leave the sentence: on each road that is not "same", the last hold place passed before what
comes first, which no "same" road passes and where only this category is waiting to be held. The connectors (run/holdflow.py CONNECTORS) have no such place and get no entry.

The game's own holds. One met after something is shown (the end of MS00DD 4C and 4D, MS00DE 45 and 46)
held whatever came before it; the holds of those categories replace it, so it is set to 0 - which is
possible only because no run without waiting reaches it. One met before anything is shown (before the
defeat lines of MS00DD 4F and 50) stays as it is.

Defaults: 60 frames (about a second) for the damage and MP-loss lines, which the game held that long, and
the same for every other category that can be the last thing a message shows; 0 for one that never is, since something always
follows it (the next line holds). The whole table is then built and run through run/holdflow.py: no hold
may follow another with nothing new shown, stand where nothing is shown, hold another category's content,
split a sentence, or be reachable where waiting is off, and every message has to end held."""
import collections
import json
import os
import sys
import argparse

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(WORK)
sys.path.insert(0, os.path.join(WORK, "run"))
sys.path.insert(0, os.path.join(WORK, "tools"))
import holdflow as hf  # noqa: E402
import holds  # noqa: E402

cli = argparse.ArgumentParser()
cli.add_argument('--src', default=hf.SRC)
cli.add_argument('--english', action='store_true')
cli.add_argument('--native', action='store_true', help='Use original CP932 text without a translation database')
cli.add_argument('--output', default=holds.PATH)
args = cli.parse_args()
if args.english and args.output == holds.PATH:
    cli.error('English analysis requires its own --output')
OUT = args.output
DEFAULT = 60
LONG = {"MS00DD/0/76@0007": 60, "MS00DD/0/77@0000": 60}
CONNECTORS = hf.CONNECTORS
sys.setrecursionlimit(100000)


def key_of(place):
    k, _off = holds.parse_place(place)
    return k


S = hf.Scripts(args.src, args.english, native=args.native)
if args.english:
    # The accepted connector identities are records; their final unit moves with translation.
    CONNECTORS = {}
    for label, why in hf.CONNECTORS.items():
        key, _ = holds.parse_place(label)
        units = S.source[(int(key[0][2:], 16), key[2])][2]
        unit = units[0] if key[2] == 27 else units[-1]
        CONNECTORS[f'{key[0]}/0/{key[2]}@{unit.start:04X}'] = why
    CONNECTORS.update({
        'MS00DE/0/9@0000': 'Actor prefix; the supplied translation can skip every predicate.',
        'MS00DE/0/10@0000': 'Actor prefix; the supplied translation can skip every predicate.',
    })
zh_of = {}
for key, (payload, toks, units, zh) in S.source.items():
    for n, u in enumerate(units):
        text = zh.get(n)
        zh_of[f"{hf.stem(key[0])}/0/{key[1]}@{u.start:04X}"] = (text if text is not None else u.jp).replace("\n", "⏎")

# ------------------------------------------------------------------ the game's own holds
originals = []
for key, (payload, toks, _units, _zh) in sorted(S.source.items()):
    st = hf.stem(key[0])
    if st not in holds.FILES + holds.COUNT_ONLY:
        continue
    for t in toks:
        raw = payload[t.start:t.end]
        if t.kind == "cmd" and t.code == 0x210 and raw[:4] == b"\x1e\x10\x01\x02" and len(raw) == 5:
            originals.append((f"{st}/0/{key[1]}@{t.start:04X}", raw[4]))
game = [{"at": p, "original": n, "hold": n} for p, n in originals]
recs = S.build(holds.parse(game))
flow = hf.Flow(recs, S.on_roots, True)
met = collections.defaultdict(set)
for s, kd in flow.kind.items():
    if kd == "hold":
        met[recs[s[0]].hold_id(s[1])[1]].add(s[3] if s[3] == "E" else s[3][0])
off_met = {hid[1] for hid in hf.holds_met(hf.Flow(recs, S.off_roots, False), recs)}
removed = set()
for p, n in originals:
    if met[p] - {"E"}:
        if not holds.changeable(key_of(p)) or "E" in met[p] or "H" in met[p] or p in off_met:
            raise SystemExit(f"{p}: the game's hold is met {sorted(met[p])}"
                             + (", and where waiting is off" if p in off_met else ""))
        removed.add(p)
base = [{"at": p, "original": n, "hold": 0 if p in removed else n} for p, n in originals]

# ------------------------------------------------------------------ categories on the game's holds that stay
recs = S.build(holds.parse(base))
flow = hf.Flow(recs, S.on_roots, True)
off = hf.Flow(recs, S.off_roots, False)
off_places = off.places()
places = hf.hold_places(recs)
built_place = {label: place for place, label in places.items()}
shown = flow.shown()
entries, fragments, connectors, unheld, problems = {}, [], [], [], []
for c in sorted(shown):
    k = key_of(c)
    if not holds.changeable(k):
        unheld.append(c)
        continue
    end = hf.end_place(recs, c)
    if end is None or end in off_places:
        problems.append(f"{c}: {'its text became nothing' if end is None else 'reachable where waiting is off'}")
        continue
    starts = flow.at(end)
    stray = [s for s in starts if s[3] == "E" or s[3][0] != "P" or s[3][1] != c]
    roads = set()
    for s in starts:
        if s not in stray:
            roads |= hf.roads_from(flow, s, places)
    kinds = {r[0] for r in roads}
    if "hold" in kinds:
        problems.append(f"{c}: one of the game's holds that stay follows it")
        continue
    same = [r for r in roads if r[0] == "same"]
    other = [r for r in roads if r[0] != "same"]
    if not same:
        if stray:
            problems.append(f"{c}: its end is also reached with {sorted({str(s[3])[:40] for s in stray})[:3]} waiting")
            continue
        at = [places[end]]
    elif not other or "end" not in kinds:
        fragments.append(c)
        continue
    else:
        on_same = {p for r in same for p in r[1]}
        chosen = []
        for r in other:
            cands = [p for p in r[1] if p not in on_same
                     and all(s[3] != "E" and s[3][0] == "P" and s[3][1] == c for s in flow.at(built_place[p]))]
            chosen.append(cands[-1] if cands else None)
        if None in chosen or any(sum(1 for p in r[1] if p in set(chosen)) != 1 for r in other):
            if c in CONNECTORS:
                connectors.append(c)
            else:
                problems.append(f"{c}: its sentence goes on on some roads and no place holds it on the others")
            continue
        at = sorted(set(chosen))
    can_end = "end" in kinds
    entries[c] = {"message": c, "hold": LONG.get(c, DEFAULT) if can_end else 0, "can_end": can_end, "after": at}
if set(CONNECTORS) - set(connectors):
    problems.append(f"CONNECTORS lists what is not a connector: {sorted(set(CONNECTORS) - set(connectors))}")
if problems:
    raise SystemExit("\n".join(problems))

# ------------------------------------------------------------------ examples of what each shows
texts = hf.Texts(S)
targets = {hf.end_place(recs, c): c for c in entries}
roads = hf.shortest_roads(flow, S.on_roots, set(targets))
for place, c in targets.items():
    entries[c]["text"] = texts.road(flow, roads[place]) if place in roads else ""
    if c in zh_of:
        entries[c]["own"] = zh_of[c]
    else:
        rec = recs[hf.category_key(c)]
        t = next(t for t in rec.orig_toks if t.start == int(c.split("@")[1], 16))
        entries[c]["own"] = f"（字典 {t.code - 1} 的词条 {rec.orig_payload[t.start + 1]:02X}，不在译文单元里）"

# ------------------------------------------------------------------ the whole table, checked
kept = {}
if os.path.exists(OUT):
    for e in json.load(open(OUT, encoding="utf-8")):
        if "hold" in e and holds.valid_hold(e["hold"]):
            kept[e.get("message") or e.get("at")] = e["hold"]
table = []
for c, e in entries.items():
    e["hold"] = kept.get(c, e["hold"])
    table.append({"message": c, "hold": e["hold"], "text": e["text"], "own": e["own"], "can_end": e["can_end"],
                  "after": e["after"]})
for p, n in originals:
    hold = kept.get(p, 0 if p in removed else n)
    note = ("游戏原有停顿，现由它前面各类消息自己的停顿代替" if p in removed else "游戏原有停顿")
    table.append({"at": p, "original": n, "hold": hold, "text": note})


def order(e):
    k, off = holds.parse_place(e.get("message") or e["at"])
    return k, off


table.sort(key=order)
recs2 = S.build(holds.parse(table))
flow2 = hf.Flow(recs2, S.on_roots, True)
off2 = hf.Flow(recs2, S.off_roots, False)
bad = {n: v for n, v in flow2.notes.items() if n in ("double", "empty", "mismatch", "split", "no-000") and v}
gaps = {c: n for c, n in flow2.gaps().items() if c not in connectors and not (c in entries and entries[c]["hold"] == 0)}
reach = sorted(hid[1] for hid in hf.holds_met(off2, recs2) if hid[0] == "added")
if bad or gaps or reach:
    raise SystemExit(f"the table does not check: {dict((n, sorted(map(str, v))[:5]) for n, v in bad.items())} "
                     f"gaps {sorted(gaps)[:10]} reachable where waiting is off {reach[:10]}")

json.dump(table, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"写入 {OUT}：消息 {len(entries)} 类（默认停 {sum(1 for e in entries.values() if e['hold'])} 类），"
      f"游戏原有停顿 {len(originals)} 处（其中 {len(removed)} 处由消息自己的停顿代替）")
print(f"句子片段 {len(fragments)} 个，连接词 {len(connectors)} 个，不能加停顿的记录里的内容 {len(unheld)} 类")
for c in unheld:
    print(f"  不能加停顿：{c}")
