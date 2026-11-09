"""Prepare a translation's verified reference image and call the shared enhancement build.

build(key, image, stage) for a translation of tools/redux_translations.py: the image's DDS98 files go to
stage/source; stage/normalized holds them with what the translation's patch broke put right - Sneikkimies' English
translation's record counts and branch fields (text/english_compatibility.json), delacannon's overwritten commands
and spans (tools/delacannoncompat.py, text/delacannon_compatibility.json); run/mk_holds.py analyses the battle
lines over them (stage/holds.json); and the native Fixes and Rebalance builds of them go to stage/fixed and
stage/rebalance.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import ddsfile
import enhancement_plan
from fat12 import open_hdi, Fat12


def _sneikkimies(original, normalized):
    repairs = json.loads(Path('text/english_compatibility.json').read_text())
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


def _delacannon(lang, original, normalized):
    import delacannoncompat
    entry = json.loads(Path('text/delacannon_compatibility.json').read_text(encoding='utf-8'))[lang]
    jp = {p.name: p.read_bytes() for p in Path('files/DDS98').iterdir() if p.is_file()}
    files = {p.name: p.read_bytes() for p in original.iterdir() if p.is_file()}
    for name, blob in delacannoncompat.normalize(jp, files, entry).items():
        (normalized / name).write_bytes(blob)


def reference_sha256(key):
    if key == 'sneikkimies':
        return json.loads(Path('text/english_compatibility.json').read_text())['image_sha256']
    lang = key.split('-')[1]
    return json.loads(Path('text/delacannon_compatibility.json').read_text(encoding='utf-8'))[lang]['image_sha256']


def build(key, image, stage):
    import nativebuild
    image, stage = Path(image), Path(stage)
    if hashlib.sha256(image.read_bytes()).hexdigest() != reference_sha256(key):
        raise ValueError(f'{image}: the build reference must be the verified {key} image. '
                         'Runtime script matching is structural.')
    _raw, _hdr, disk, part = open_hdi(str(image))
    fs = Fat12(disk, part)
    original, normalized = stage / 'source', stage / 'normalized'
    for d in (original, normalized):
        d.mkdir(parents=True, exist_ok=True)
        for p in d.iterdir():
            if p.is_file():
                p.unlink()          # only this generated stage's own copies
    for name, entry in fs.walk():
        if not name.startswith('DDS98/') or name.count('/') != 1:
            continue
        (original / name.split('/')[1]).write_bytes(bytes(fs.read_chain(entry['cluster'], entry['size'])))
    if key == 'sneikkimies':
        _sneikkimies(original, normalized)
    else:
        _delacannon(key.split('-')[1], original, normalized)
    hold_path = stage / 'holds.json'
    subprocess.run([sys.executable, 'run/mk_holds.py', '--translation', key, '--src', str(normalized),
                    '--output', str(hold_path)], check=True)
    for edition, rb in (('fixed', False), ('rebalance', True)):
        built = nativebuild.build(rebalance_on=rb, translation=key, src=str(normalized),
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
