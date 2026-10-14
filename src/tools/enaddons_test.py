#!/usr/bin/env python3
"""enaddons_test.py - the English add-on page (dist/English/Giten Add-ons (EN)/Apply Add-ons.html, tools/mkenhancements.py)
run under Node the way the page runs it (tools/webpatch_run.js), against tools/addons.py on the same images.

  * the language bytes (mkenhancements.language_runs): no Fixes, Rebalance, artwork or target-prompt byte, Japanese or
    English, falls in them;
  * on eight images - the Japanese reference HDI and the tested English one, each as it is, with Fixes, with Fixes and
    Rebalance, and with those and Windows Artwork, all made by the shipped English pages: the page reads the right
    language and no add-on; both add-ons in give the image tools/addons.py gives, byte for byte (the disk grown by
    tools/hdigrow.py when, and only when, it has fewer free clusters than the files take: the English disk with
    Fixes and the artwork has none), with the question in the image's language; the page then reads both; the
    target prompt out, then the gamepad out, each as tools/addons.py does, end with the image's every file as
    before; the same ticks again are refused;
  * the order with the other pages: Fixes refuses an image with the target prompt, and Rebalance a Fixes image with
    it, each saying the add-on is why; Fixes over the gamepad alone keeps DDS98.COM and gives the Fixes files; Windows Artwork before or after both
    add-ons gives the same files (the Japanese game with Fixes, the English game without; on the English Fixes disk
    the artwork after the add-ons is two clusters short and refuses);
  * refused, with no output: a Chinese image, an English DDS98.EXE with one run of the language bytes put back to
    the Japanese, a DDS98.COM that is not the add-on's, MS00D9.BIN without the program's sites;
  * the gamepad's hooks are recognised in every image's DDS98.EXE (tools/gamepad_test.py --exe);
  * the input images are unchanged.

    enaddons_test.py [--japanese HDI] [--english HDI]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
sys.path.insert(0, str(HERE))
import addons  # noqa: E402
import ddsfile  # noqa: E402
import hdigrow  # noqa: E402
import mkenhancements as build  # noqa: E402
import nospace  # noqa: E402
import slotorder  # noqa: E402
import targetprompt  # noqa: E402
from fat12 import open_hdi  # noqa: E402
from fat12w import Fat12W  # noqa: E402

JP = WORK / "inputs" / "Japanese.hdi"
EN = build.STAGE / "english-translation-test" / "English.hdi"
OUT = build.STAGE / "verification-addons"
BOTH = {"target": True, "pad": True}
fails = 0
runs = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what, flush=True)


def content(path):
    _raw, _hdr, disk, part = open_hdi(str(path))
    fs = Fat12W(disk, part)
    return {name: bytes(fs.read_chain(e["cluster"], e["size"])) for name, e in fs.walk()}


def node(kind, src, out, picks=None):
    global runs
    title, filename, _o, _d = build.PACKAGES["addons" if kind == "inspect" else kind]
    args = ["node", str(HERE / "webpatch_run.js"), str(build.OUT / title / filename), str(src), src.name, str(out),
            kind, "enhancement"]
    if picks is not None:
        args.append("addons=" + ",".join(f"{k}:{int(v)}" for k, v in picks.items()))
    runs += 1
    return json.loads(subprocess.run(args, capture_output=True, text=True, encoding="utf-8", check=True).stdout)


def page(kind, src, label, picks=None, refuse=False):
    """The page's output for src (a fresh file OUT/label.hdi), or its message when it refuses as wanted."""
    target = OUT / (label + ".hdi")
    if target.exists():
        target.unlink()                 # only this test's own output
    r = node(kind, src, target, picks)
    if refuse:
        check(not r["ok"] and r["refused"] and not target.exists(), f"{label}：拒绝（{r.get('message')}）")
        return r.get("message", "")
    if not (r["ok"] and target.exists()):
        check(False, f"{label}：{r}")
        raise SystemExit(1)
    return target


def inspect(src):
    r = node("inspect", src, OUT / "unused.hdi")
    return r["inspect"] if r["ok"] else r


def python_addons(src, want, english):
    """tools/addons.py on src, the disk grown first (tools/hdigrow.py) when the change does not fit."""
    payload = addons.files(None, english)
    raw = bytearray(Path(src).read_bytes())
    v = hdigrow.volume(raw)
    disk = raw[v["hdr"]:]
    fs = Fat12W(disk, v["part"])
    more = addons.shortfall(fs, payload, want)
    if more:
        raw, _k = hdigrow.grow(raw, more)
        disk = raw[v["hdr"]:]
        fs = Fat12W(disk, v["part"])
    addons.apply(fs, payload, want, say=lambda *_: None)
    raw[v["hdr"]:] = disk
    return bytes(raw)


def variant(src, label, edit):
    raw, hdr, disk, part = open_hdi(str(src))
    fs = Fat12W(disk, part)
    edit(fs)
    raw[hdr:] = disk
    path = OUT / (label + ".hdi")
    path.write_bytes(raw)
    return path


def language_checks():
    print("== 语言字节")
    lang = set()
    for at, jp, _en in build.language_runs():
        lang |= set(range(at, at + len(jp) // 2))
    rd = lambda p: p.read_bytes()  # noqa: E731
    jp = rd(WORK / "files" / "DDS98" / "DDS98.EXE")
    en = rd(build.STAGE / "english-adaptation" / "source" / "DDS98.EXE")
    forms = {"日文 Fixes": (jp, rd(build.STAGE / "fixed" / "DDS98.EXE")),
             "日文 Rebalance": (jp, rd(build.STAGE / "rebalance" / "DDS98.EXE")),
             "英文 Fixes": (en, rd(build.STAGE / "english-adaptation" / "fixed" / "DDS98.EXE")),
             "英文 Rebalance": (en, rd(build.STAGE / "english-adaptation" / "rebalance" / "DDS98.EXE"))}
    for base in (jp, en):
        forms[f"{'英文' if base is en else '日文'} 美术"] = (base, slotorder.apply_to(nospace.apply_to(base)))
        forms[f"{'英文' if base is en else '日文'} 选择对象时暂停"] = (base, targetprompt.apply_to(base))
    for label, (base, made) in forms.items():
        hit = [i for i in lang if made[i] != base[i]]
        check(not hit, f"{label}不写语言字节（共 {len(lang)} 字节）")


def image_checks(name, img, english):
    print(f"== {name}")
    before = content(img)
    got = inspect(img)
    check(got == {"lang": "en" if english else "jp", "addons": {"target": False, "pad": False}}, f"读出 {got}")
    both = page("addons", img, f"{name}_both", BOTH)
    check(both.read_bytes() == python_addons(img, BOTH, english), "两项都加：和 tools/addons.py 逐字节相同")
    grown = both.stat().st_size - img.stat().st_size
    _r, hdr, disk, part = open_hdi(str(img))
    free = len(Fat12W(disk, part).free_clusters())
    check((grown > 0) == (free < 2), f"空簇 {free}：{'加大了 ' + str(grown) + ' 字节' if grown else '没有加大'}")
    files = content(both)
    msg = ddsfile.parse(files["DDS98/" + targetprompt.MSG_FILE])
    check(msg[0][0].payload == targetprompt.payload(None, english), f"问话：{msg[0][0].payload!r}")
    check(inspect(both)["addons"] == BOTH, "加上之后读出两项都在")
    no_target = page("addons", both, f"{name}_pad", {"target": False})
    check(no_target.read_bytes() == python_addons(both, {"target": False}, english), "去掉选择对象时暂停：和 tools/addons.py 相同")
    check(inspect(no_target)["addons"] == {"target": False, "pad": True}, "读出只剩手柄操作")
    none = page("addons", no_target, f"{name}_none", {"pad": False})
    check(none.read_bytes() == python_addons(no_target, {"pad": False}, english), "再去掉手柄操作：和 tools/addons.py 相同")
    check(content(none) == before, "两项都去掉后每个文件都和原来一样")
    page("addons", both, f"{name}_again", BOTH, refuse=True)
    return both


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--japanese", type=Path, default=JP)
    ap.add_argument("--english", type=Path, default=EN)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sums = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.japanese, a.english)}
    language_checks()

    images, withboth = {}, {}
    for lang, src in (("jp", a.japanese), ("en", a.english)):
        images[lang] = src
        images[f"{lang}_fixed"] = page("fixes", src, f"{lang}_fixed")
        images[f"{lang}_rebalanced"] = page("rebalance", images[f"{lang}_fixed"], f"{lang}_rebalanced")
        images[f"{lang}_rebalanced_art"] = page("art", images[f"{lang}_rebalanced"], f"{lang}_rebalanced_art")
    for name, img in images.items():
        withboth[name] = image_checks(name, img, name.startswith("en"))

    print("== 和其他补丁的先后")
    for lang in ("jp", "en"):
        for msg in (page("fixes", withboth[lang], f"{lang}_both_fixes", refuse=True),
                    page("rebalance", withboth[f"{lang}_fixed"], f"{lang}_fixed_both_rebalance", refuse=True)):
            check("target prompt add-on" in msg, "拒绝时说明是选择对象时暂停挡住了")
        pad = page("addons", images[lang], f"{lang}_padonly", {"pad": True})
        fixed_pad = page("fixes", pad, f"{lang}_padonly_fixes")
        want = {**content(images[f"{lang}_fixed"]), "DDS98/" + addons.FILES["pad"]: addons.files()["pad"]}
        check(content(fixed_pad) == want, f"{lang}：手柄操作之后打 Fixes，文件和 Fixes 加 DDS98.COM 相同")
        art_before = page("addons", page("art", images[f"{lang}_fixed"], f"{lang}_fixed_art"), f"{lang}_fixed_art_both", BOTH)
        if lang == "jp":
            art_after = page("art", withboth[f"{lang}_fixed"], f"{lang}_fixed_both_art")
            check(content(art_after) == content(art_before), f"{lang}：Windows 美术在附加补丁之前、之后，文件相同")
        else:
            # the English Fixes disk has two clusters too few for the artwork once the add-ons are in
            page("art", withboth[f"{lang}_fixed"], f"{lang}_fixed_both_art", refuse=True)
            art_after = page("art", withboth[lang], f"{lang}_both_art")
            art_first = page("addons", page("art", images[lang], f"{lang}_art"), f"{lang}_art_both", BOTH)
            check(content(art_after) == content(art_first), f"{lang}（不打 Fixes）：Windows 美术在附加补丁之前、之后，文件相同")

    print("== 拒绝")
    first = build.language_runs()[0]

    def mixed(fs):
        exe = bytearray(fs.read_chain(fs.find("DDS98/DDS98.EXE")["cluster"], fs.find("DDS98/DDS98.EXE")["size"]))
        jp = bytes.fromhex(first[1])
        exe[first[0]:first[0] + len(jp)] = jp
        fs.replace("DDS98/DDS98.EXE", bytes(exe))
    page("addons", variant(a.english, "mixed_input", mixed), "mixed", BOTH, refuse=True)
    foreign = variant(a.japanese, "foreign_input", lambda fs: fs.create("DDS98", addons.FILES["pad"], b"\xb8\x00\x4c\xcd\x21"))
    page("addons", foreign, "foreign", {"target": True}, refuse=True)
    half = variant(a.japanese, "half_input", lambda fs: fs.create("DDS98", targetprompt.MSG_FILE,
                                                                   targetprompt.message_file(None)))
    page("addons", half, "half", {"pad": True}, refuse=True)

    print("== 手柄操作的挂钩点（tools/gamepad_test.py）")
    exes = []
    for name, img in images.items():
        path = OUT / f"{name}.exe"
        path.write_bytes(content(img)["DDS98/DDS98.EXE"])
        exes += ["--exe", str(path)]
    r = subprocess.run([sys.executable, str(HERE / "gamepad_test.py"), *exes], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    check(r.returncode == 0, f"gamepad_test：{r.stdout.strip().splitlines()[-1]}")

    check(all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in sums.items()), "输入的镜像都没变")
    print(f"{runs} 次页面运行；{'全部通过' if not fails else f'{fails} 项失败'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
