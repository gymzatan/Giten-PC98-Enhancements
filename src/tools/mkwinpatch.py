#!/usr/bin/env python3
"""Pack the Windows-art conversion's payload: the FC files the patch writes into a disk image of the game.

    mkwinpatch.py           build/winpatch.zip (make.py patch runs it before the web patches)

The FC files are built here from the game's own and the converted pictures alone - the walls of
wingfx_new, the doors and stairs of windoors, the rooms, creatures and title of gfx_win_fit, the grey
frame of winhud - with no translation mixed in. The patch also remaps each map section's door byte
to that section's wall set, so FC1400 can hold one door per wall (Windows keeps the door in the wall
texture), and in DDS98.EXE skips the palette allocator's 「no space」 line (tools/nospace.py) and
makes it hand a battle's enemies their free slots from the top (tools/slotorder.py; tools/winpatch.py
does both on the image). That lets the art go on the Japanese original and any Chinese build: the FC
files are the same in all of them, the door bytes are not text, and the places in DDS98.EXE are the
same in every version. The translation writes the map files whole, since their names are text, and
remaps their door bytes the same way when it finds this FC1400, and its DDS98.EXE carries both
changes as well, so translation and art go on in either order.

tools/winpatch.py applies the payload (the reference the web patches are checked against); tools/mkwebpatch.py puts
it into the WIN_mod bundles' web patches, after the translation, and into Windows素材补丁.html, the art alone.
"""
import hashlib
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gfx  # noqa: E402
import winpatch  # noqa: E402

SOURCES = ("wingfx_new", "windoors", "gfx_win_fit", "winhud")
SRC = os.path.join(WORK, "files", "DDS98")
ROOT = os.path.join(WORK, "build", "winpatch_gfx")
PAYLOAD = os.path.join(WORK, "build", "winpatch.zip")
# Files the WIN_mod releases up to 2026-10-07 wrote converted and the patch now gives back to the game: the payload
# carries the game's own file, marked as replacing the converted one ({name: sha1 of that converted file}), so an
# image made with one of those releases gets the original back and any other image already holds it.
RESTORED = {
    "FC2630.BIN": "c829486f96040603fb0628e6c63d37f46e2bf50a",   # 式神 / 護法童子 / 天逆神 keep the PC-98 drawing
}


def merged(root):
    """The asset folders laid over one another in order, as one text/gfx-shaped tree."""
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "gfx"))
    for src in SOURCES:
        for name in sorted(os.listdir(os.path.join(WORK, src))):
            folder = os.path.join(WORK, src, name)
            if not name.startswith("FC") or not os.path.isdir(folder):
                continue
            dest = os.path.join(root, "gfx", name)
            os.makedirs(dest, exist_ok=True)
            for item in sorted(os.listdir(folder)):
                if item in ("palettes.json", gfx.FRAMES_NAME):
                    have = {}
                    if os.path.exists(os.path.join(dest, item)):
                        have = json.load(open(os.path.join(dest, item), encoding="utf-8"))
                    have.update(json.load(open(os.path.join(folder, item), encoding="utf-8")))
                    order = int if item == "palettes.json" else str
                    json.dump({k: have[k] for k in sorted(have, key=order)},
                              open(os.path.join(dest, item), "w", encoding="utf-8"), indent=1)
                    continue
                shutil.copy2(os.path.join(folder, item), os.path.join(dest, item))
    return root


def pack(files, path=PAYLOAD):
    """The files to write and, for each, the hash of the file it replaces: the game's own, or for a RESTORED
    file the converted one a release wrote."""
    marks = {}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, blob in sorted(files.items()):
            was = RESTORED.get(name) or hashlib.sha1(open(os.path.join(SRC, name), "rb").read()).hexdigest()
            marks[name] = {"was": was, "now": hashlib.sha1(blob).hexdigest()}
            z.writestr(f"files/{name}", blob)
        z.writestr(winpatch.HASHES, json.dumps(marks, indent=1))
    return path, marks


def main():
    """build/winpatch.zip from the asset folders; returns (payload path, FC files, frames changed, bytes grown)."""
    files, changes = gfx.edited_files(merged(ROOT))
    for name in RESTORED:
        if name in files:
            raise SystemExit(f"{name} 在 RESTORED 里（还给游戏原图），素材文件夹里却又有它的转换图")
        files[name] = open(os.path.join(SRC, name), "rb").read()
    grew = sum(len(b) for b in files.values()) - sum(
        os.path.getsize(os.path.join(SRC, n)) for n in files)
    pack(files)
    print(f"{PAYLOAD}  {os.path.getsize(PAYLOAD)} 字节"
          f"（{len(files)} 个 FC 文件，{len(changes)} 帧，镜像里多占 {grew} 字节）")
    return PAYLOAD, len(files), len(changes), grew


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
