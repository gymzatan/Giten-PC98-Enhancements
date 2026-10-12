#!/usr/bin/env python3
"""Exercise the shipped English HTML payloads on a supplied Japanese HDI, using existing Python readers/patches.

python tools/enhancements_test.py IMAGE.hdi
Outputs and the machine-readable receipt remain under build/enhancements/verification.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mkenhancements as build
import talkgaps
import winpatch
from fat12 import open_hdi
from fat12w import Fat12W


def content(path):
    _raw, _hdr, disk, part = open_hdi(str(path))
    fs = Fat12W(disk, part)
    return {name: fs.read_chain(e["cluster"], e["size"]) for name, e in fs.walk()}


def main(image):
    image = Path(image).resolve()
    original_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    out = build.STAGE / "verification"
    out.mkdir(parents=True, exist_ok=True)
    receipts = []

    def apply(kind, source, label, refuse=False):
        title, filename, _n, _d = build.PACKAGES[kind]
        target = out / (label + ".hdi")
        if target.exists():
            target.unlink()  # only this generated test output
        result = subprocess.run(["node", str(HERE / "webpatch_run.js"), str(build.OUT / title / filename),
                                 str(source), source.name, str(target), kind, "enhancement"],
                                capture_output=True, text=True, encoding="utf-8", check=True)
        message = json.loads(result.stdout)
        assert message["ok"] != refuse, (label, message)
        assert target.exists() != refuse, label
        if refuse:
            assert message["refused"], (label, message)
        receipts.append({"case": label, **message})
        print(label, "refused as required" if refuse else "applied", flush=True)
        return target

    original = content(image)
    fixed = apply("fixes", image, "fixed")
    fixed_files = content(fixed)
    expected = {**original, **{"DDS98/" + n: b for n, b in build.load_files(build.STAGE / "fixed").items()}}
    assert fixed_files == expected, "Fixes differs from the shared Japanese build output or changed unrelated files"
    rebalanced = apply("rebalance", fixed, "rebalanced")
    expected_rb = {**original, **{"DDS98/" + n: b for n, b in build.load_files(build.STAGE / "rebalance").items()}}
    assert content(rebalanced) == expected_rb, "Rebalance differs from the shared Japanese build output"
    apply("rebalance", image, "raw_rebalance", refuse=True)
    apply("fixes", rebalanced, "downgrade", refuse=True)
    assert content(apply("fixes", fixed, "fixes_again")) == fixed_files
    assert content(apply("rebalance", rebalanced, "rebalance_again")) == expected_rb

    art = apply("art", image, "art_only")
    # The existing Python artwork patch is the independent reference for all graphics and palette edits.
    reference = out / "python_reference.hdi"
    reference_bytes = bytearray(image.read_bytes())
    # Independently set the two documented reference-volume metadata fields before calling the
    # authoritative Python artwork patch. No files are moved or synthesized for this reference.
    header = struct.unpack_from("<I", reference_bytes, 8)[0]
    struct.pack_into("<H", reference_bytes, header + 256 + 14, 614)
    struct.pack_into("<H", reference_bytes, header + 50688 + 19, 30393)
    reference.write_bytes(reference_bytes)
    python_art, _kept = winpatch.apply_to(str(reference), say=lambda *_: None)
    assert art.read_bytes() == Path(python_art).read_bytes(), "HTML artwork differs from the existing Python patch"
    assert len(art.read_bytes()) == len(image.read_bytes()), "Artwork changed the disk's size"
    fix_art = apply("art", fixed, "fixed_art")
    art_fix = apply("fixes", art, "art_fixed")
    assert content(fix_art) == content(art_fix), "Fixes and Artwork order changes game contents"
    rb_art = apply("art", rebalanced, "rebalanced_art")
    art_rb = apply("rebalance", fix_art, "art_rebalanced")
    assert content(rb_art) == content(art_rb), "Rebalance and Artwork order changes game contents"
    apply("art", art, "art_again", refuse=True)
    apply("rebalance", art, "art_without_fixes_rebalance", refuse=True)

    # Exercise preservation using a real original save and deliberately nonstandard startup commands.
    raw, hdr, disk, part = open_hdi(str(image))
    fs = Fat12W(disk, part)
    saved = (build.WORK / "files" / "DDS98" / "SAVE0000.DDS").read_bytes()
    fs.create("DDS98", "SAVE0000.DDS", saved)
    startup = b"@ECHO OFF\r\nREM user startup marker\r\n"
    fs.create(None, "AUTOEXEC.BAT", startup)
    raw[hdr:] = disk
    with_save = out / "with_save.hdi"
    with_save.write_bytes(raw)
    saved_fixed = apply("fixes", with_save, "saved_fixed")
    saved_rb = apply("rebalance", saved_fixed, "saved_rebalanced")
    saved_art = apply("art", saved_rb, "saved_art")
    saved_files = content(saved_art)
    assert saved_files["DDS98/SAVE0000.DDS"] == saved
    assert saved_files["AUTOEXEC.BAT"] == startup
    for path in ("IO.SYS", "MSDOS.SYS", "COMMAND.COM", "DDS98/AUTOEXEC.BAT", "DDS98/CONFIG.SYS"):
        assert saved_files[path] == original[path], path

    raw, hdr, disk, part = open_hdi(str(fixed))
    fs = Fat12W(disk, part)
    exe = bytearray(fixed_files["DDS98/DDS98.EXE"])
    exe[-1] ^= 1
    fs.replace("DDS98/DDS98.EXE", exe)
    raw[hdr:] = disk
    corrupt = out / "modified.hdi"
    corrupt.write_bytes(raw)
    apply("fixes", corrupt, "modified_fixes", refuse=True)
    apply("rebalance", corrupt, "modified_rebalance", refuse=True)

    # The reference-partition extension must never consume other partition or tail data.
    occupied = bytearray(image.read_bytes())
    header = struct.unpack_from("<I", occupied, 8)[0]
    occupied[header + 50688 + 29700 * 1024] = 0x42
    tail_image = out / "occupied_tail.hdi"
    tail_image.write_bytes(occupied)
    apply("art", tail_image, "occupied_tail_art", refuse=True)
    occupied = bytearray(image.read_bytes())
    occupied[header + 256 + 32] = 0xA1
    partition_image = out / "extra_partition.hdi"
    partition_image.write_bytes(occupied)
    apply("art", partition_image, "extra_partition_art", refuse=True)

    count, gaps, reached = talkgaps.audit(talkgaps.Game(lambda name: fixed_files.get("DDS98/" + name)))
    assert not gaps, gaps
    for line in talkgaps.load():
        key = (0xE0 + line["chunk"], line["record"])
        assert any(stem == line["file"] for _label, _caller, stem in reached[key]), line["file"]
    assert hashlib.sha256(image.read_bytes()).hexdigest() == original_hash, "Original image changed"
    receipt = {"input_sha256": original_hash, "cases": receipts, "negotiation_packs": count,
               "checks": ["shared build payload equality", "unrelated files preserved", "Python artwork byte equality",
                          "installation order equality", "prerequisite and modified-file refusals", "save and boot preservation",
                          "negotiation reachability", "original input unchanged"]}
    (out / "results.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {len(receipts)} HTML runs and all content checks; {count} negotiation packs.")


if __name__ == "__main__":
    main(sys.argv[1])
