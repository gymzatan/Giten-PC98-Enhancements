"""Prepare the verified English BPS output and call the shared enhancement build."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import ddsfile
import enhancement_plan
from fat12 import open_hdi, Fat12


def build(image, stage):
    import nativebuild
    image, stage = Path(image), Path(stage)
    repairs = json.loads(Path('text/english_compatibility.json').read_text())
    if hashlib.sha256(image.read_bytes()).hexdigest() != repairs['image_sha256']:
        raise ValueError('The build reference must be the verified English BPS output. Runtime script matching is structural.')
    _raw, _hdr, disk, part = open_hdi(str(image))
    fs = Fat12(disk, part)
    original, normalized = stage / 'source', stage / 'normalized'
    original.mkdir(parents=True, exist_ok=True)
    normalized.mkdir(parents=True, exist_ok=True)
    for name, entry in fs.walk():
        if not name.startswith('DDS98/') or name.count('/') != 1:
            continue
        blob = bytes(fs.read_chain(entry['cluster'], entry['size']))
        (original / name.split('/')[1]).write_bytes(blob)
    expected = {(name, ci): (old, count) for name, ci, old, count in repairs['counts']}
    for path in original.iterdir():
        blob = path.read_bytes()
        if path.name.startswith(('MS', 'ID')) and path.suffix == '.BIN':
            chunks, counts = enhancement_plan.script(blob)
            for ci, recs in enumerate(chunks):
                if counts[ci] != len(recs) and expected.get((path.name, ci)) != (counts[ci], len(recs)):
                    raise ValueError(f'{path.name}/{ci}: unexpected count mismatch')
            for edit in repairs['branches']:
                if edit['file'] != path.name:
                    continue
                hits = [r for r in chunks[edit['chunk']] if r.rid == edit['record']]
                if len(hits) != 1:
                    raise ValueError('Ambiguous reference branch repair')
                r = hits[0]; at = edit['field']; old, new = bytes.fromhex(edit['before']), bytes.fromhex(edit['after'])
                if r.payload[at:at + len(old)] != old:
                    raise ValueError('Reference branch precondition differs')
                r.payload = r.payload[:at] + new + r.payload[at + len(old):]
            blob = ddsfile.build(chunks)
        (normalized / path.name).write_bytes(blob)
    hold_path = stage / 'holds.json'
    subprocess.run([sys.executable, 'run/mk_holds.py', '--english', '--src', str(normalized),
                    '--output', str(hold_path)], check=True)
    for edition, rb in (('fixed', False), ('rebalance', True)):
        built = nativebuild.build(rebalance_on=rb, english=True, src=str(normalized),
                                 hold_path=str(hold_path))
        files = {**built['files'], **built['added']}
        for p in normalized.iterdir():
            if p.read_bytes() != (original / p.name).read_bytes() and p.name not in files:
                files[p.name] = p.read_bytes()
        dest = stage / edition
        dest.mkdir(exist_ok=True)
        for p in dest.iterdir():
            if p.is_file() and p.name not in files:
                p.unlink()
        for name, data in files.items():
            (dest / name).write_bytes(data)
    return stage
