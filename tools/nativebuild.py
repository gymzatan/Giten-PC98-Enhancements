"""Build language-preserving enhancement files through the shared repair code.

This entry point needs extracted game files and the authored repair recipes,
without a translation database, replacement font, or translated graphics.
"""
import gfx
import holds
import talkgaps
import talkwait
from buildcore import ScriptInputs, JapaneseText, build_scripts, repair_files


def build(*, src="files/DDS98", english=False, extras=True, rebalance_on=False,
          hold_path=holds.PATH, roundtrip=False, edit_gfx=False, root="text"):
    inputs = ScriptInputs(src)
    encoding = JapaneseText()
    text_key = "en" if english else "jp"
    gaps = [] if roundtrip else talkgaps.load()
    bad = talkgaps.problems(encoding, None, gaps, text_key)
    if bad:
        raise ValueError(f"Negotiation recipe {bad[0][0]}: {bad[0][1]}")
    pacing = {} if roundtrip or not extras else holds.load(hold_path)
    waits = {} if roundtrip else talkwait.table(src)
    scripts, hold_sites = build_scripts(inputs, encoding, pacing, waits, src)
    files = dict(scripts)
    talkgaps.apply_to(files, encoding, gaps, src=src, text_key=text_key)
    state = (dict(added={}, unmended={}, unchecked={}, unshown={}, ungapped={}, moon_forms=[])
             if roundtrip else repair_files(files, src, extras, rebalance_on, None, english))
    if not roundtrip and edit_gfx:
        edited, _changes = gfx.edited_files(root)
        files.update(edited)
    return dict(holds=hold_sites, scripts=scripts, files=files, dropped=[], **state)
