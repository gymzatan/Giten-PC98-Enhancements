"""Export native enhancement outputs as checked record/field edits for the browser.

Game rules remain in make.py and its fix modules. This module only describes their
existing before/after output; the VM grammar comes from ddsvm/ddsgrammar.
"""
import difflib
import hashlib
import struct
from pathlib import Path

import ddscrypt
import ddsfile
import ddsgrammar
import ddsvm
import etfields
import msdump
import records


def script(blob):
    """Read bounded records; retain declared counts for explicit repair preconditions."""
    chunks, counts = [], []
    used = 0
    for ch in msdump.chunks(blob):
        size, plain = ddscrypt.decrypt(ch)
        if size != len(plain):
            raise ValueError('Truncated script chunk')
        pos, recs = 2, []
        while pos < len(plain):
            rid, length = struct.unpack_from('<BH', plain, pos)
            pos += 3
            cond = None
            if length == 65535:
                a, b, length = struct.unpack_from('<BBH', plain, pos)
                cond = (a, b)
                pos += 4
            if pos + length > len(plain):
                raise ValueError('Truncated script record')
            recs.append(ddsfile.Record(rid, cond, plain[pos:pos + length]))
            pos += length
        counts.append(struct.unpack_from('<H', plain)[0])
        chunks.append(recs)
        used += len(ch)
    if used != len(blob):
        raise ValueError('Trailing script data')
    return chunks, counts


def atoms(payload):
    parts = []
    for t in ddsvm.tokenize(payload):
        text = t.kind == 'text' or t.code == 0xA
        raw = payload[t.start:t.end]
        if text and parts and parts[-1]['text']:
            parts[-1]['raw'] += raw
            parts[-1]['end'] = t.end
        else:
            parts.append(dict(start=t.start, end=t.end, text=text, raw=raw, rel=t.rel))
    def address(target, field):
        if target == len(payload):
            return [len(parts), 0]
        for i, a in enumerate(parts):
            if target == a['start'] or a['text'] and a['start'] <= target < a['end']:
                return [i, target - a['start']]
        return ['raw', struct.unpack_from('<H', payload, field)[0]]
    for a in parts:
        raw = bytearray(a['raw'])
        refs = []
        for field, target in a['rel']:
            refs.append([field - a['start'], address(target, field)])
            raw[field - a['start']:field - a['start'] + 2] = b'\0\0'
        a['desc'] = ['T'] if a['text'] else [raw.hex(), refs]
    return parts


def record_plan(before, after):
    a, b = atoms(before), atoms(after)
    # Byte-identical text is retained by reference, including translated names/newlines.
    keys = lambda parts: ['T' if p['text'] else p['desc'][0] for p in parts]
    mapping = {}
    for tag, i, j, k, l in difflib.SequenceMatcher(None, keys(a), keys(b), autojunk=False).get_opcodes():
        if tag == 'equal':
            for old, new in zip(range(i, j), range(k, l)):
                if a[old]['text'] and a[old]['raw'] == b[new]['raw']:
                    mapping[new] = old
    old_desc = [p['desc'] for p in a]
    new_desc = [p['desc'] for p in b]
    recipe = []
    preserved = set(mapping.values())
    for i, p in enumerate(a):
        if p['text'] and i not in preserved:
            old_desc[i] = ['T', p['raw'].hex()]
    for i, p in enumerate(b):
        if i in mapping:
            recipe.append(['copy', mapping[i]])
        else:
            recipe.append(['bytes', p['raw'].hex()])
            if p['text']:
                new_desc[i] = ['T', p['raw'].hex()]
    return dict(before=old_desc, after=new_desc, recipe=recipe)


def spans(a, b):
    if len(a) != len(b):
        raise ValueError('Field edit changed record size')
    out = []
    i = 0
    while i < len(a):
        if a[i] == b[i]:
            i += 1
            continue
        start = i
        while i < len(a) and a[i] != b[i]:
            i += 1
        out.append([start, a[start:i].hex(), b[start:i].hex()])
    return out


def _repaired(name, ci, old, normalized):
    """The record `old` as the build's normalized input has it, for a record of the translation's that does not
    parse (tools/layoutrepair.py restores its commands in place): the normalized payload and the byte spans
    from old to it."""
    if normalized is None:
        raise ValueError(f'{name}/{ci}/{old.rid:02X}: the record does not parse')
    hits = [v for v in script(normalized)[0][ci] if (v.rid, v.cond) == (old.rid, old.cond)]
    if len(hits) != 1 or len(hits[0].payload) != len(old.payload):
        raise ValueError(f'{name}/{ci}/{old.rid:02X}: no repair of the same length for a record that does not parse')
    return hits[0].payload, spans(old.payload, hits[0].payload)


def file_plan(name, before, after, normalized=None):
    """normalized: the file as the build's normalized input has it (tools/english_enhancements.py), for the
    records of `before` that do not parse: their edit carries `repair`, the byte spans that make them the
    normalized record, and the recipe starts from that."""
    if before is None:
        return dict(type='add', data=after.hex())
    if name.startswith(('MS', 'ID')) and name.endswith('.BIN'):
        a, counts = script(before)
        b, new_counts = script(after)
        assert len(a) == len(b)
        edits, count_edits = [], []
        for ci, (old, new) in enumerate(zip(a, b)):
            if counts[ci] != len(old):
                count_edits.append([ci, counts[ci], len(old)])
            for r in new:
                matches = [v for v in old if (v.rid, v.cond) == (r.rid, r.cond)]
                if not matches:
                    edits.append(dict(chunk=ci, rid=r.rid, cond=r.cond, add=r.payload.hex()))
                elif any(v.payload == r.payload for v in matches):
                    continue
                elif len(matches) != 1:
                    raise ValueError(f'{name}/{ci}/{r.rid:02X}: ambiguous identity')
                elif matches[0].payload != r.payload:
                    try:
                        plan = record_plan(matches[0].payload, r.payload)
                    except ddsvm.ParseError:
                        start, repair = _repaired(name, ci, matches[0], normalized)
                        plan = dict(record_plan(start, r.payload), repair=repair)
                    edits.append(dict(chunk=ci, rid=r.rid, cond=r.cond, **plan))
        return dict(type='script', records=edits, counts=count_edits)
    if name in ('ET0001.BIN', 'ET0004.BIN'):
        a, b = records.plain_of(before), records.plain_of(after)
        pa, pb = etfields.pointers(a), etfields.pointers(b)
        assert len(pa) == len(pb)
        edits = []
        for i, (x, y) in enumerate(zip(pa, pb)):
            end_a = pa[i + 1] if i + 1 < len(pa) else len(a)
            end_b = pb[i + 1] if i + 1 < len(pb) else len(b)
            old, new = bytes(a[x:end_a]), bytes(b[y:end_b])
            if old != new:
                edits.append([i, spans(old, new)])
        return dict(type='table', records=edits)
    if name.startswith('P2') or name.startswith('M0'):
        wa, a = ddscrypt.decrypt(before)
        wb, b = ddscrypt.decrypt(after)
        return dict(type='cipher', edits=spans(a, b))
    if len(before) == len(after) and name != 'DDS98.EXE':
        return dict(type='fields', edits=spans(before, after))
    return dict(type='exact', before=hashlib.sha1(before).hexdigest(), data=after.hex())


def bare(desc):
    """A record description without its text bytes: what the instructions and branches must match."""
    return [['T'] if d[0] == 'T' else d for d in desc]


def older_records(old_blobs, target, settled):
    """{(chunk, rid, cond): [step, ...]}: for each record of a script that an earlier release left different both
    from `target` (this build's output of the file) and from `settled` (the state this plan's own edits start from),
    the record recipe from that old record to the target's (record_plan), one per distinct old record. Earlier
    releases changed instructions only, so every text part is copied from the player's disk; a step that would carry
    text, or a release that added, removed or reordered records, raises."""
    t_chunks, t_counts = script(target)
    s_chunks = script(settled)[0] if settled is not None else None
    out = {}
    for blob in old_blobs:
        o_chunks, o_counts = script(blob)
        if o_counts != t_counts or len(o_chunks) != len(t_chunks):
            raise ValueError('an earlier release changed the chunk layout')
        for ci, (old, new) in enumerate(zip(o_chunks, t_chunks)):
            olds = {(r.rid, r.cond): r.payload for r in old}
            news = {(r.rid, r.cond): r.payload for r in new}
            if len(olds) != len(old) or len(news) != len(new) or set(olds) != set(news):
                raise ValueError(f'chunk {ci}: an earlier release added, removed or duplicated a record')
            sets = {(r.rid, r.cond): r.payload for r in s_chunks[ci]} if s_chunks else {}
            for key, payload in news.items():
                if olds[key] == payload or olds[key] == sets.get(key):
                    continue
                step = record_plan(olds[key], payload)
                if any(d[0] == 'T' and len(d) > 1 for d in step['before'] + step['after']):
                    raise ValueError(f'chunk {ci}, record {key[0]:02X}: an earlier release changed its text')
                steps = out.setdefault((ci,) + key, [])
                if step not in steps:
                    steps.append(step)
    return out


def compile_plan(original, fixed, rebalanced, kind, exe_forms, older=None, normalized=None):
    """The checked edits that make this build's `kind` output from a translation's input. `older` =
    {file: [[chunk, rid, cond, steps], ...]} (tools/redux_older.json en.records): each record an earlier release left
    in another form gets the recipes from those forms ('older' on its edit), so such a disk is updated in place.
    `normalized`: the build's normalized input ({file: bytes}), for the input's records that do not parse
    (file_plan)."""
    normalized = normalized or {}
    before = original if kind == 'fixes' else {**original, **fixed}
    output = fixed if kind == 'fixes' else rebalanced
    plans = {n: file_plan(n, before.get(n), data, normalized.get(n)) for n, data in output.items()
             if data != before.get(n)}
    guards = {}
    if kind == 'rebalance':
        for n, data in fixed.items():
            check = file_plan(n, original.get(n), data, normalized.get(n))
            change = plans.get(n)
            if n == 'DDS98.EXE':
                continue
            if check['type'] == 'script':
                changed = {(e['chunk'], e['rid'], tuple(e['cond'] or ()))
                           for e in change['records']} if change else set()
                check['records'] = [dict(e, guard=True) for e in check['records']
                                    if (e['chunk'], e['rid'], tuple(e['cond'] or ())) not in changed]
            elif check['type'] in ('table', 'cipher', 'fields'):
                def guard_spans(edits, replaced):
                    excluded = {o + i for o, a, _ in replaced for i in range(len(a) // 2)}
                    return [[o + i, v, v] for o, _a, b in edits for i in range(len(b) // 2)
                            if o + i not in excluded for v in [b[2*i:2*i+2]]]
                if check['type'] == 'table':
                    repl = dict(change['records']) if change else {}
                    check['records'] = [[rid, guard_spans(edits, repl.get(rid, []))] for rid, edits in check['records']]
                else:
                    check['edits'] = guard_spans(check['edits'], change['edits'] if change else [])
            elif change:
                continue
            guards[n] = check
    for n, entries in (older or {}).items():
        target = {**before, **output}[n]
        plan = plans.setdefault(n, dict(type='script', records=[], counts=[]))
        if plan['type'] != 'script':
            raise ValueError(f'{n}: an earlier release changed it; only scripts are updated record by record')
        t_chunks = script(target)[0]
        steps = set()
        for ci, rid, cond, alts in entries:
            cond = tuple(cond) if cond is not None else None
            steps.add((ci, rid, cond))
            edit = next((e for e in plan['records'] if (e['chunk'], e['rid'], e['cond']) == (ci, rid, cond)
                         and 'add' not in e), None)
            if edit is None:
                # a record this plan leaves as it is: an edit that only checks it, with the way from the old form
                [payload] = [r.payload for r in t_chunks[ci] if (r.rid, r.cond) == (rid, cond)]
                edit = dict(chunk=ci, rid=rid, cond=cond, **record_plan(payload, payload))
                plan['records'].append(edit)
            if any(bare(a['after']) != bare(edit['after']) for a in alts):
                raise ValueError(f'{n} chunk {ci}, record {rid:02X}: redux_older.json leads elsewhere than this '
                                 f'build; rerun tools/reduxolder.py')
            edit['older'] = [dict(before=a['before'], after=a['after'], recipe=a['recipe']) for a in alts]
        if n in guards and guards[n]['type'] == 'script':
            # those records are checked by their edits now, which also accept the old forms
            guards[n]['records'] = [g for g in guards[n]['records'] if (g['chunk'], g['rid'], g['cond']) not in steps]
    return dict(files=plans, guards=guards, exe=exe_forms,
                grammar=dict(prefix=ddsgrammar.PREFIX, alias=ddsgrammar.ALIAS,
                             commands=ddsgrammar.COMMANDS, values=ddsgrammar.VALUES,
                             selBV=sorted(ddsvm.SEL_BV), selV=sorted(ddsvm.SEL_V)))
