"""Verify the shipped pages against the English BPS image and script-update variants."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import ddsfile
import ddsvm
import enhancement_plan
import mkenhancements as build
from enhancements_test import content
from fat12 import open_hdi
from fat12w import Fat12W


def main(image):
    source = Path(image)
    root = build.STAGE / 'english-adaptation'
    out = root / 'verification'
    out.mkdir(exist_ok=True)
    original = content(source)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    receipts = []

    def apply(kind, src, label, refuse=False):
        title, filename, _n, _d = build.PACKAGES[kind]
        target = out / (label + '.hdi')
        if target.exists():
            target.unlink()
        process = subprocess.run(['node', str(build.HERE / 'webpatch_run.js'), str(build.OUT / title / filename),
                                  str(src), src.name, str(target), kind, 'enhancement'],
                                 capture_output=True, text=True, encoding='utf-8', check=True)
        result = json.loads(process.stdout)
        assert result['ok'] != refuse and target.exists() != refuse, (label, result)
        receipts.append(dict(case=label, **result))
        print(label, 'refused' if refuse else 'applied', flush=True)
        return target

    def variant(src, label, edit):
        raw, hdr, disk, part = open_hdi(str(src))
        fs = Fat12W(disk, part)
        edit(fs)
        raw[hdr:] = disk
        path = out / (label + '.hdi')
        path.write_bytes(raw)
        return path

    fixed = apply('fixes', source, 'fixed')
    rebalanced = apply('rebalance', fixed, 'rebalanced')
    for edition, image in [('fixed', fixed), ('rebalance', rebalanced)]:
        expected = {**original, **{'DDS98/' + n: b for n, b in build.load_files(root / edition).items()}}
        assert content(image) == expected, edition + ' differs from native output'
    assert content(apply('fixes', fixed, 'fixes_again')) == content(fixed)
    assert content(apply('rebalance', rebalanced, 'rebalance_again')) == content(rebalanced)
    apply('rebalance', source, 'requires_fixes', True)
    apply('fixes', rebalanced, 'no_downgrade', True)
    art = apply('art', source, 'art')
    fixed_art = apply('art', fixed, 'fixed_art')
    art_fixed = apply('fixes', art, 'art_fixed')
    assert content(fixed_art) == content(art_fixed)
    rb_art = apply('art', rebalanced, 'rebalanced_art')
    art_rb = apply('rebalance', fixed_art, 'art_rebalanced')
    assert content(rb_art) == content(art_rb)

    markers = {}
    def update_text(fs):
        for name, rid, marker in [('MS0012.BIN', 4, b' FUTURE EVENT TEXT WITH EXTRA WORDS.\n'),
                                  ('MS00DC.BIN', 2, b' FUTURE BATTLE TEXT.\n')]:
            entry = fs.find('DDS98/' + name)
            parsed = ddsfile.parse(bytes(fs.read_chain(entry['cluster'], entry['size'])))
            rec = next(r for r in parsed[0] if r.rid == rid)
            toks = ddsvm.tokenize(rec.payload)
            index = next(i for i, t in enumerate(toks) if t.kind == 'text')
            rec.payload = ddsvm.rebuild(rec.payload, toks, append={index:marker})
            parsed[0].append(ddsfile.Record(0xFA, None, b'Additional translator record.\0'))
            fs.replace('DDS98/' + name, ddsfile.build(parsed))
            markers[name] = marker
    future = variant(source, 'future_input', update_text)
    future_fixed = apply('fixes', future, 'future_fixed')
    future_rb = apply('rebalance', future_fixed, 'future_rebalanced')
    for image in [future_fixed, future_rb]:
        files = content(image)
        for name, marker in markers.items():
            recs = ddsfile.parse(files['DDS98/' + name])[0]
            assert any(marker in r.payload for r in recs), (name, 'future text lost')
            assert any(r.rid == 0xFA and r.payload == b'Additional translator record.\0' for r in recs)
            for r in recs:
                assert not ddsvm.check_branches(r.payload, ddsvm.tokenize(r.payload)), (name, r.rid)
    assert content(apply('fixes', future_fixed, 'future_again')) == content(future_fixed)

    def corrupt_instruction(fs):
        name = 'DDS98/MS0012.BIN'; e = fs.find(name)
        recs = ddsfile.parse(bytes(fs.read_chain(e['cluster'], e['size'])))
        r = next(r for r in recs[0] if r.rid == 4)
        b = bytearray(r.payload); b[4] ^= 1; r.payload = bytes(b)
        fs.replace(name, ddsfile.build(recs))
    conflict = variant(source, 'conflict_input', corrupt_instruction)
    apply('fixes', conflict, 'instruction_conflict', True)
    missing = variant(fixed, 'missing_fix_input', lambda fs: fs.replace('DDS98/MS0052.BIN', original['DDS98/MS0052.BIN']))
    apply('rebalance', missing, 'missing_prerequisite', True)

    own_line = b'A future translator supplied this question.\n\x1e\x10\x01\x01\0'
    def supply_prompt(fs):
        name = 'DDS98/MS6001.BIN'; e = fs.find(name)
        chunks, _ = enhancement_plan.script(bytes(fs.read_chain(e['cluster'], e['size'])))
        chunks[2].append(ddsfile.Record(0x2C, None, own_line))
        fs.replace(name, ddsfile.build(chunks))
    prompt = variant(source, 'supplied_prompt', supply_prompt)
    prompt_fixed = apply('fixes', prompt, 'preserved_prompt')
    assert next(r.payload for r in ddsfile.parse(content(prompt_fixed)['DDS98/MS6001.BIN'])[2] if r.rid == 0x2C) == own_line
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    (out / 'results.json').write_text(json.dumps(dict(cases=receipts, native_outputs_identical=True,
        future_text_and_added_records_preserved=True, relocated_branches_valid=True,
        conflicts_refused_atomically=True, input_sha256=original_hash), indent=2), encoding='utf-8')
    print('Verified', len(receipts), 'page applications.')


if __name__ == '__main__':
    main(sys.argv[1])
