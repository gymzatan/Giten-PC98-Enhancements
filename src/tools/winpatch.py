#!/usr/bin/env python3
"""偽典・女神転生 東京黙示録　Windows 版素材补丁

    winpatch.py [镜像.hdi]

The Windows release's artwork re-projected into the PC-98 game: the dungeon walls, doors and stairs,
the rooms and event pictures, the creatures, and the title screen. The patch works on the game's
files, not on a disk image's bytes - it opens the image, finds DDS98\\ inside it and writes each
FC*.BIN it carries over the one there - so it does not care which dump it is given.

It replaces picture files and remaps each map section's door byte to that section's wall set, so
the converted doors (one FC1400 entry per wall set) show with the walls they belong to. No
translation of this game edits those picture files, and a door byte is not text, so the same patch
fits the Japanese original and any Chinese build alike. The translation patch does write the map
files whole - their names are text - with the game's own door bytes in them, but when it finds this
FC1400 it remaps them itself, so the two patches go on in either order. Each file it writes is
checked first: it knows the original it was built from and what it makes of it, so a file that is
neither is reported and left to the user to decide about, and an image that already carries the
patch is recognised rather than patched twice.

It also turns off, in DDS98.EXE, the line the palette allocator prints over the picture when a colour
finds no hardware slot (tools/nospace.py: two bytes, the same place in every version). The art makes
that more likely - a converted room no longer shares every colour the PC-98 art had it share with
the pictures shown over it (tools/winshare.py mends the known ones) - and the Japanese original has
no other way to lose it. And it makes the allocator hand the enemies of a battle their free slots from
the top (tools/slotorder.py: the same two places in every version), so a room or background left on
screen behind them keeps its colours: a converted room owns more colours than the PC-98 one did, and
the enemies would otherwise take its slots first. Every Chinese build carries both already, and the
translation patch writes its own DDS98.EXE whole, so this too gives the same file in either order. A
DDS98.EXE with neither form at one of those places is a version the patch does not know, and it stops
before writing anything.

The result is written beside the image given, as <name>_WIN.hdi; the image itself is left alone.
"""
import hashlib
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gameimage  # noqa: E402
import mapdoors  # noqa: E402
import nospace  # noqa: E402
import slotorder  # noqa: E402
from fat12 import open_hdi  # noqa: E402
from fat12w import Fat12W  # noqa: E402

# What is printed keeps to characters a Chinese console can put on screen: it runs in whatever code
# page the user's Windows has, and a Japanese middle dot would stop the program dead.
TITLE = "伪典·女神转生 东京默示录　Windows 版素材补丁"
PAYLOAD = os.path.join(getattr(sys, "_MEIPASS", None) or os.path.join(HERE, "..", "build"),
                       "winpatch.zip")
DIR = "DDS98"
SUFFIX = "_WIN"
HASHES = "hashes.json"


class PatchError(Exception):
    pass


def payload(path=PAYLOAD):
    """({name: bytes to write}, {name: {'was': sha1 of the file it replaces, 'now': sha1 of this}})."""
    with zipfile.ZipFile(path) as z:
        marks = json.loads(z.read(HASHES).decode("utf-8"))
        files = {n.rsplit("/", 1)[1]: z.read(n) for n in z.namelist() if n.startswith("files/")}
    return files, marks


def sha(blob):
    return hashlib.sha1(blob).hexdigest()


def survey(fs, files, marks):
    """What each file the patch carries is in this image: ready to write, already written, missing,
    or something the patch has not seen."""
    out = {"ready": [], "done": [], "missing": [], "other": []}
    for name in sorted(files):
        e = fs.find(f"{DIR}/{name}")
        if e is None:
            out["missing"].append(name)
            continue
        got = sha(bytes(fs.read_chain(e["cluster"], e["size"])))
        if got == marks[name]["now"]:
            out["done"].append(name)
        elif got == marks[name]["was"]:
            out["ready"].append(name)
        else:
            out["other"].append(name)
    return out


def room(fs, files, state):
    """Clusters the write needs beyond what it frees, so an image too full to hold it is said so
    before anything is written rather than during."""
    cs = fs.bpb.cluster_size
    need = 0
    for name in state["ready"] + state["other"]:
        e = fs.find(f"{DIR}/{name}")
        need += (len(files[name]) + cs - 1) // cs - len(fs.chain(e["cluster"]) if e["cluster"] else [])
    for name in state["missing"]:
        need += (len(files[name]) + cs - 1) // cs
    return need, len(fs.free_clusters()), cs


def exe_state(fs):
    """(DDS98.EXE's bytes, 'orig' or 'fixed' at the palette allocator's print, 'orig' or 'fixed' at its
    free-slot search)."""
    e = fs.find(f"{DIR}/{nospace.FILE}")
    exe = bytes(fs.read_chain(e["cluster"], e["size"]))
    try:
        printed = nospace.state(exe)
    except nospace.NoSpaceError:
        raise PatchError(f"{nospace.FILE} 里调色板报错（no space）那一处既不是原样也不是已屏蔽的内容，"
                         "补丁不认识这个版本的程序，没有写入任何东西。") from None
    try:
        order = slotorder.state(exe)
    except slotorder.SlotOrderError:
        raise PatchError(f"{slotorder.FILE} 里分配颜色槽的那两处既不是原样也不是修改后的内容，"
                         "补丁不认识这个版本的程序，没有写入任何东西。") from None
    return exe, printed, order


def remap_maps(fs, say=print):
    """Set every map section's door byte to its wall set. Returns (files written, sections changed)."""
    n_files, n_sec = mapdoors.remap_image(fs, DIR)
    if n_sec:
        say(f"  地图门号：{n_files} 个文件、{n_sec} 个分区改为跟随墙套")
    else:
        say("  地图门号：已经全部跟随墙套")
    return n_files, n_sec


def out_name(image):
    folder, base = os.path.split(os.path.abspath(image))
    stem, ext = os.path.splitext(base)
    return os.path.join(folder, stem + SUFFIX + ext)


def apply_to(image, also_other=False, say=print):
    """Write the patched image beside the one given. The image itself is not touched - a patch that
    changed it in place would leave the version it was made from nowhere to go back to."""
    stem = os.path.splitext(os.path.basename(image))[0]
    if stem.upper().endswith(SUFFIX):
        raise PatchError(f"{os.path.basename(image)} 的名字以 {SUFFIX} 结尾，"
                         "这看上去已经是打过补丁的镜像了。请把打补丁前的那个拖进来。")
    raw, header, disk, part = open_hdi(image)
    fs = Fat12W(disk, part)
    patch_fs(fs, os.path.basename(image), also_other, False, say)

    out = out_name(image)
    built = bytearray(raw)
    built[header:] = disk
    kept = None
    if os.path.exists(out):               # an earlier run's image is kept, not written over
        kept = gameimage.backup_name(out)
        os.replace(out, kept)
    tmp = out + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bytes(built))
    os.replace(tmp, out)
    return out, kept


def patch_fs(fs, label, also_other=False, complete=False, say=print):
    """The art on an opened image (apply_to's steps). complete: the image is the one the caller is making anyway, so
    finding the art all there already is no error (webpatch.js artwork's `complete`)."""
    files, marks = payload()
    if fs.find(f"{DIR}/DDS98.EXE") is None:
        raise PatchError(f"{label} 里没有 {DIR}\\DDS98.EXE，这不是本作的镜像")
    exe, printed, order = exe_state(fs)
    state = survey(fs, files, marks)
    say(f"  {len(files)} 个素材文件：{len(state['ready'])} 个待替换，"
        f"{len(state['done'])} 个已经是补丁版，{len(state['missing'])} 个镜像里没有，"
        f"{len(state['other'])} 个被别的改动动过")
    if state["other"]:
        say("  被动过的：" + "、".join(state["other"]))
        if not also_other:
            raise PatchError("这些文件不是补丁认识的原样，直接覆盖会把那边的改动抹掉。"
                             "确认要覆盖的话，在命令行加一个 y 再运行。")
    todo = state["ready"] + state["missing"] + (state["other"] if also_other else [])
    if todo:
        need, free, cs = room(fs, files, state)
        if need > free:
            raise PatchError(f"镜像里的空间不够：还要 {need * cs} 字节，只剩 {free * cs} 字节。"
                             "请用容量更大的镜像，或先删掉些别的文件。")
        wrote = made = 0
        def allocation_order(name):
            e = fs.find(f"{DIR}/{name}")
            old = len(fs.chain(e['cluster'])) if e and e['cluster'] else 0
            return ((len(files[name]) + cs - 1) // cs - old, name)
        for name in sorted(todo, key=allocation_order):
            if fs.find(f"{DIR}/{name}") is None:
                fs.create(DIR, name, files[name])
                made += 1
            else:
                fs.replace(f"{DIR}/{name}", files[name])
                wrote += 1
        say(f"  写入 {wrote} 个文件" + (f"，新增 {made} 个" if made else "")
            + f"，镜像里还剩 {(free - need) * cs} 字节")
    n_maps, n_sec = remap_maps(fs, say)
    new_exe = exe
    if printed == "orig":
        new_exe = nospace.apply_to(new_exe)
        say(f"  {nospace.FILE}：屏蔽调色板报错（no space）")
    else:
        say(f"  {nospace.FILE}：调色板报错已经屏蔽")
    if order == "orig":
        new_exe = slotorder.apply_to(new_exe)
        say(f"  {slotorder.FILE}：战斗中敌人从高位取颜色槽，背景不再被染色")
    else:
        say(f"  {slotorder.FILE}：战斗颜色槽已经从高位分配")
    if new_exe != exe:
        fs.replace(f"{DIR}/{nospace.FILE}", new_exe)
    if not complete and not todo and not n_sec and new_exe == exe:
        raise PatchError("这个镜像里的素材已经全是补丁版了，没有要写的。")


def ask(argv):
    image = argv[0] if argv else input("把镜像文件拖到这里，或输入路径，然后回车：").strip('" ')
    if not image or not os.path.exists(image):
        raise PatchError(f"找不到镜像文件：{image}")
    return image, any(a.lower() in ("y", "yes") for a in argv[1:])


def main(argv):
    try:                                # a console in some other code page still gets to say it
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError):
        pass
    print(TITLE)
    try:
        image, also_other = ask(argv)
        print(f"\n{os.path.basename(image)}：开始写入……")
        out, kept = apply_to(image, also_other)
        if kept:
            print(f"  原来的 {os.path.basename(out)} 已另存为 {os.path.basename(kept)}")
        print(f"\n完成。Windows 素材版是 {out}")
        print(f"（{os.path.basename(image)} 本身没有改动。）")
    except (PatchError, OSError, zipfile.BadZipFile) as e:
        print(f"\n没能完成：{e}")
        return 1
    return 0


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if sys.stdin and sys.stdin.isatty():
        try:                            # isatty() says yes for a redirected console on Windows too
            input("\n按回车关闭。")
        except EOFError:
            pass
    sys.exit(code)
