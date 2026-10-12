#!/usr/bin/env python3
"""Validate the script grammar against every script record in the game (MS and ID files).

A record passes a grammar when
  * it tokenises to exactly its end,
  * every branch target lands on a token boundary of that record,
  * every ＠辞書 index exists in its dictionary (MS7F00..MS7F07),
  * rebuilding it from its tokens reproduces the original bytes.

Each record is classified:
  shipped     passes the shipped VM's grammar - translatable
  legacy      fails it but passes the old compiler's reading (ddsvm, legacy=True):
              dead code the shipped VM cannot run; copied unchanged
  textless    fails both but holds no Shift-JIS text: nothing to translate, and
              the builder copies it unchanged (MS6F00 chunk 31 / MS6F1F are
              such tables)
  superseded  fails both, but every text run in it occurs in shipped records
  cut         in a file listed in CUT_FILES, with the evidence
  failing     none of the above - an unexplained gap, reported in full

Commands that fall to the dispatcher's default case are counted, not failed:
the VM accepts them, but they would point at a grammar gap if frequent.

    checkvm.py [src] [--save snap.json] [--against snap.json]

--save writes the classification; --against compares with a saved one and lists
regressions first (a record whose class got worse: shipped -> anything else,
legacy -> failing), so a grammar change can be shown not to break any record.
"""
import collections
import json
import os
import re
import sys

from ddscrypt import decrypt
from ddsgrammar import COMMANDS
from ddstext import Corpus, plain
from ddsvm import ParseError, check_branches, rebuild, tokenize
from msdump import chunks, records, script_files

RANK = {"shipped": 0, "legacy": 1, "textless": 1, "superseded": 1, "cut": 1, "failing": 2}

# Files the shipped game cannot reach. MS0031: compiled by the old compiler
# (20 of its 28 records need the legacy reading, including the entry menu
# record 00), holds developer placeholders (「＃暫定：ゲームオーバーです。そのルーチンへ。」,
# 「下は暫定です。冥界をクリアして、蘇ったものとし…」), its story lines occur nowhere in
# shipped records, and no shipped script names it (`fileref.py 31`: 0 references,
# while MS0030 and MS0032 are named 22 and 76 times).
CUT_FILES = {"MS0031.BIN"}

JP_RUN = re.compile(r"[぀-ヿ一-鿿！-～]{2,}")


def text_runs(payload):
    """Runs of two or more kana/kanji/full-width characters in the raw bytes."""
    return JP_RUN.findall(payload.decode("cp932", "replace"))


def dictionary_sizes(src):
    sizes = {}
    for k in range(8):
        data = open(os.path.join(src, f"MS7F0{k}.BIN"), "rb").read()
        sizes[k] = 1 + max(rid for c in chunks(data) for rid, _, _ in records(decrypt(c)[1]))
    return sizes


def verify(payload, sizes, legacy):
    """-> (problems, tokens or None)."""
    try:
        toks = tokenize(payload, legacy)
    except ParseError as e:
        return [f"parse: {e}"], None
    problems = []
    bad = check_branches(payload, toks)
    if bad:
        s, field, target = bad[0]
        problems.append(f"{len(bad)} branch(es) off token boundaries; first: token@{s:#x} "
                        f"field@{field:#x} -> {target:#x} (record length {len(payload):#x})")
    for t in toks:
        if t.dict_ref:
            d, idx = t.dict_ref
            if idx is None or idx >= sizes[d]:
                problems.append(f"＠辞書{d}[{idx}] out of range ({sizes[d]})")
    if not bad and rebuild(payload, toks) != payload:
        problems.append("rebuild differs")
    return problems, toks


def main(src="files/DDS98", save=None, against=None):
    sizes = dictionary_sizes(src)
    corpus = Corpus(src)
    stats = collections.Counter()
    unknown = collections.Counter()
    klass = {}
    failures = []
    pending = []
    shipped_text = []
    per_file = collections.defaultdict(collections.Counter)
    for stem, path in script_files(src):
        name = stem + ".BIN"
        for ci, ch in enumerate(chunks(open(path, "rb").read())):
            for rid, _cond, payload in records(decrypt(ch)[1]):
                where = f"{name} chunk {ci} record {rid:02X}"
                stats["records"] += 1
                stats["bytes"] += len(payload)
                problems, toks = verify(payload, sizes, legacy=False)
                if not problems:
                    klass[where] = "shipped"
                    shipped_text.append(plain(corpus.expand(payload)))
                    for t in toks:
                        if t.kind == "text":
                            stats["text tokens"] += 1
                            continue
                        stats["commands"] += 1
                        stats["branches"] += len(t.rel)
                        stats["dictionary refs"] += bool(t.dict_ref)
                        if t.code not in COMMANDS:
                            unknown[t.code] += 1
                elif not verify(payload, sizes, legacy=True)[0]:
                    klass[where] = "legacy"
                else:
                    pending.append((where, name, payload, problems))
    blob = "\x00".join(shipped_text)
    for where, name, payload, problems in pending:
        runs = text_runs(payload)
        if name in CUT_FILES:
            klass[where] = "cut"
        elif not runs:
            klass[where] = "textless"
        elif all(r in blob for r in runs):
            klass[where] = "superseded"
        else:
            klass[where] = "failing"
            missing = [r for r in runs if r not in blob]
            failures.extend((where, p) for p in problems)
            failures.append((where, f"text not in shipped records: {' | '.join(missing)[:80]}"))
    for where, k in klass.items():
        per_file[where.split()[0]][k] += 1
    counts = collections.Counter(klass.values())
    print(f"{'records':16}: {stats['records']}  ("
          + ", ".join(f"{k} {counts[k]}" for k in RANK if counts[k]) + ")")
    for k in ("bytes", "text tokens", "commands", "branches", "dictionary refs"):
        print(f"{k:16}: {stats[k]}" + ("  (shipped records)" if k != "bytes" else ""))
    print(f"default-case codes seen: {sum(unknown.values())} "
          f"({', '.join(f'{c:#x}x{n}' for c, n in unknown.most_common(12))})")
    mixed = {f: c for f, c in per_file.items() if set(c) - {"shipped"}}
    if mixed:
        print("files with non-shipped records:")
        for f, c in sorted(mixed.items()):
            print(f"  {f}: " + ", ".join(f"{k} {c[k]}" for k in RANK if c[k]))
    if against:
        before = json.load(open(against, encoding="utf-8"))
        worse = sorted(w for w, k in klass.items() if RANK[k] > RANK[before.get(w, "shipped")])
        better = sorted(w for w, k in klass.items() if RANK[k] < RANK[before.get(w, "shipped")])
        print(f"against {against}: {len(better)} improved, {len(worse)} regressions")
        for w in worse[:25]:
            print(f"  REGRESSION {w}: {before.get(w)} -> {klass[w]}")
    if save:
        json.dump({w: k for w, k in klass.items() if k != "shipped"},
                  open(save, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print(f"failures: {len(failures)} in {counts['failing']} records")
    for where, why in failures[:25]:
        print(f"  {where}: {why}")
    return 1 if failures else 0


def cli(argv):
    args, opts, i = [], {}, 0
    while i < len(argv):
        if argv[i] in ("--save", "--against"):
            opts[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    return main(*args, **opts)


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
