#!/usr/bin/env python3
"""Disks made by earlier English Redux releases, so that Apply Fixes / Apply Rebalance update such a disk in place.

tools/redux_older.json holds, per page (fixes, rebalance), what tools/mkenhancements.py puts in the payload for it:
  jp.accept   {file: [sha1, ...]}  every state an earlier release left the file in on the Japanese game; accepted
  jp.rewrite  [file, ...]          Rebalance only: Fixes files such a disk still has in an older state; Rebalance
                                   writes this build's Fixes file over them
  en.exe      {fixed|rebalance: [sha1, ...]}  the English program states earlier releases left (whole file)
  en.records  {file: [[chunk, rid, cond, [step, ...]], ...]}  for each script record an earlier release left
              different, the recipe from that old record to this build's (enhancement_plan.older_records); only
              instructions, every text part is copied from the player's disk
The page writes this build's files over an accepted older state, so the result is what this build makes.

    python tools/reduxolder.py    rewrite tools/redux_older.json for this build (needs the release archive)

The data comes from the states the released pages themselves produced, kept in build/enhancements/release-archive/:
- downloaded/: every superseded release asset (taken off the GitHub release 2026-11-08, sha256 in old-assets.sha256);
- pages.py: the Apply pages inside those zips and the current dist zips, one per content (pages/index.json);
- oldruns.py: each era's pages run by webpatch_run.js on the Japanese reference disk and the tested English one, in
  the release's order (Fixes, Rebalance, Artwork, Controls); runs/<name>.hdi and runs/files.json. A run's name lists
  the page versions applied (en-F1R1A1 = English, Fixes 1, Rebalance 1, Artwork 1).
When a release is superseded, add its pages there (pages.py, then an era in oldruns.py) before taking them down, and
rerun this. A build whose Fixes or Rebalance output changes needs it rerun too: mkenhancements stops when the file no
longer fits the build.

A page never meets Controls here: its own message has the player remove Controls first (Apply Controls.html), and the
removal leaves the state without Controls. Artwork's states are included; they differ from the ones without it only
in the art files and the art sites of DDS98.EXE, which no earlier release changed differently.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
DATA = HERE / "redux_older.json"
ARCHIVE = WORK / "build" / "enhancements" / "release-archive"
RUNS = ARCHIVE / "runs"
DIR = "DDS98/"


def load(kind):
    """The payload additions for the `kind` page (fixes or rebalance)."""
    return json.loads(DATA.read_text(encoding="utf-8"))[kind]


def _runs():
    path = RUNS / "files.json"
    if not path.exists():
        raise SystemExit(f"reduxolder: {path} is missing; run {ARCHIVE / 'oldruns.py'} first")
    return json.loads(path.read_text(encoding="utf-8"))


def reference(base):
    """{file name: sha1}: the reference disk `base` itself, every file of its game folder."""
    entry = _runs()[base]
    return {n[len(DIR):].upper(): h for n, h in entry["files"].items() if n.upper().startswith(DIR)}


def states(base, rebalance, art=True):
    """[(run name, {file name: sha1})]: the released runs on `base` ('jp' or 'en') with Fixes and without Controls;
    with Rebalance when `rebalance`, without it otherwise; with or without Artwork, or only without when not `art`."""
    out = []
    for name, entry in _runs().items():
        prefix, _, combo = name.partition("-")
        if prefix != base or not entry.get("ok") or not combo:
            continue
        letters = set(re.findall(r"[FRAC]", combo))
        if "F" not in letters or "C" in letters or ("R" in letters) != rebalance or ("A" in letters and not art):
            continue
        files = {n[len(DIR):].upper(): h for n, h in entry["files"].items() if n.upper().startswith(DIR)}
        out.append((name, files))
    if not out:
        raise SystemExit(f"reduxolder: no released {base} runs {'with' if rebalance else 'without'} Rebalance")
    return out


def hashes(base, rebalance, art=True):
    """{file name: [sha1, ...]} over states(base, rebalance, art), first seen first."""
    out = {}
    for _name, files in states(base, rebalance, art):
        for n, h in files.items():
            seen = out.setdefault(n, [])
            if h not in seen:
                seen.append(h)
    return out


def blobs(base, rebalance, name, skip=()):
    """The distinct contents of file `name` in states(base, rebalance, art=False), except those whose sha1 is in
    `skip`, read from the run disks (Artwork touches no file read here)."""
    from fat12 import open_hdi
    from fat12w import Fat12W
    out, seen = [], set(skip)
    for run, files in states(base, rebalance, art=False):
        h = files.get(name)
        if h is None or h in seen:
            continue
        seen.add(h)
        _raw, _hdr, disk, part = open_hdi(str(RUNS / (run + ".hdi")))
        fs = Fat12W(disk, part)
        [data] = [fs.read_chain(e["cluster"], e["size"]) for n, e in fs.walk() if n.upper() == DIR + name]
        if hashlib.sha1(data).hexdigest() != h:
            raise SystemExit(f"reduxolder: {run}.hdi {name} is not the state files.json recorded")
        out.append(data)
    return out


def kind_data(kind, original, fixed, rebalanced, en_original, en_fixed, en_rebalanced, forms):
    """The redux_older.json entry of the `kind` page for this build's outputs (as mkenhancements.payload reads them);
    `forms` = mkenhancements.forms. Raises when an earlier release changed a file the page would leave alone."""
    import enhancement_plan
    sha1 = lambda b: hashlib.sha1(b).hexdigest()
    rebalances = (False,) if kind == "fixes" else (False, True)
    # Japanese: whole files
    older, plain = {}, {}
    for rebalance in rebalances:
        for into, art in ((older, True), (plain, False)):
            for n, hs in hashes("jp", rebalance, art).items():
                into[n] = list(dict.fromkeys(into.get(n, []) + hs))
    delta = set(fixed) if kind == "fixes" else {n for n, b in rebalanced.items() if b != fixed.get(n, original.get(n))}
    written = set(fixed) | delta
    rewrite = [] if kind == "fixes" else \
        [n for n in sorted(set(fixed) - delta) if any(h not in forms(n, fixed[n]) for h in plain.get(n, ()))]
    untouched = reference("jp")
    accept = {}
    for n, hs in older.items():
        if n in written:
            # what the page accepts without this file (mkenhancements.payload's required lists)
            if kind == "fixes":
                known = forms(n, original.get(n)) + forms(n, fixed[n])
            else:
                below = fixed.get(n, original.get(n))
                known = forms(n, below) + forms(n, rebalanced.get(n, below))
            if any(h not in known for h in hs):
                accept[n] = hs
        elif any(h != untouched.get(n) for h in plain.get(n, ())):
            raise ValueError(f"{n}: an earlier release changed it and the {kind} page would not update it")
    # English: the program whole, scripts record by record
    exe = {label: hashes("en", rebalance)["DDS98.EXE"] for label, rebalance in (("fixed", False), ("rebalance", True))}
    settled = en_original if kind == "fixes" else {**en_original, **en_fixed}
    target = {**settled, **(en_fixed if kind == "fixes" else en_rebalanced)}
    en_untouched, old = reference("en"), {}
    for rebalance in rebalances:
        for n, hs in hashes("en", rebalance, art=False).items():
            if n == "DDS98.EXE" or all(h == en_untouched.get(n) for h in hs):
                continue
            keep = [sha1(b) for b in (target.get(n), settled.get(n)) if b is not None]
            if all(h in keep for h in hs):
                continue
            if n not in target or not n.startswith(("MS", "ID")):
                raise ValueError(f"{n}: an earlier release changed it and the {kind} page would not update it")
            old.setdefault(n, []).extend(blobs("en", rebalance, n, skip=keep))
    records = {}
    for n, contents in sorted(old.items()):
        steps = enhancement_plan.older_records(contents, target[n], settled.get(n))
        if steps:
            records[n] = [[ci, rid, list(cond) if cond is not None else None, alts]
                          for (ci, rid, cond), alts in steps.items()]
    return {"jp": {"accept": accept, "rewrite": rewrite}, "en": {"exe": exe, "records": records}}


def main():
    sys.path.insert(0, str(HERE))
    import mkenhancements as m
    original = m.load_files(WORK / "files" / "DDS98")
    fixed, rebalanced = m.load_files(m.STAGE / "fixed"), m.load_files(m.STAGE / "rebalance")
    english = m.STAGE / "english-adaptation"
    en = [m.load_files(english / d) for d in ("source", "fixed", "rebalance")]
    data = {kind: kind_data(kind, original, fixed, rebalanced, *en, m.forms) for kind in ("fixes", "rebalance")}
    DATA.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    for kind, d in data.items():
        print(f"{kind}: jp accept {len(d['jp']['accept'])} files, rewrite {d['jp']['rewrite']}; en exe "
              f"{ {k: len(v) for k, v in d['en']['exe'].items()} }, records "
              f"{ {n: len(v) for n, v in d['en']['records'].items()} }")
    print(DATA)


if __name__ == "__main__":
    main()
