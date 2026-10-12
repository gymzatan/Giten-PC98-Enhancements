#!/usr/bin/env python3
"""Pictures that are part of a room take the room's Windows colours, so the two still share hardware
palette slots. Run from work/, after tools/winrooms.py.

    winshare.py

A picture loaded with kind 0 asks the allocator (0871:8A9A) for a hardware slot for each colour it owns: a
slot already claimed with that colour is shared, anything else takes a free one. A room scene has eleven
free slots (1-3, which the wall set gives up, and 8-15); the HUD holds the rest. The PC-98 art draws the
pictures that belong to a room - the bars of a cell, a close-up of something in it, a door that opens -
in the room's own colours, so they cost no slot: the bars 401Dh are the prison room 5017h's 0667 0445 0223.
Some entries are nothing but that: 5091h is an 8x8 frame holding 邪教の館 5005h's five colours, which the
fusion's script loads (MS003E records 12 and 13) while 5005h is the background.
The Windows art refitted the rooms (tools/winrooms.py, gfx_win_fit/) and left those pictures as they were,
so each of their colours now takes a slot of its own. A prison scene with a prisoner in it then needs
twelve, and the allocator's fallback runs: it prints 「no space(col=...)」 and hands out slot 2
(tools/nospace.py), which recolours whatever else is drawn with slot 2.

The people who stand in a room share with it the same way. A map event's bytes 12-13 point at its NPC
record in the map file ([sprite][variant]..., sprite FF = nobody), and entering the cell shows 4000h + sprite
with a kind-0 load in sprite slot 1Fh over the event's picture, after the entry has released slots 8-15. The
shopkeepers 4079h, 407Fh and 4025h wear the NPC palette (CFA 7C4 2B1 BAC 84C 652 in slots 1-3, 9-11); the
item shop 5038h (道具屋, fourteen shops) owns 0BAC and 084C as well, so shop and shopkeeper fit the eleven
slots with one to spare. The Windows fit of 5038h moved its slot 9 to 0899, and the shop needed twelve; with
0BAC back it needs eleven (its slot 10, 0232 on 5999 pixels, stays).

A corridor scene works the same way with the wall set in place of a room: the wall set keeps slots 0-3, and a
picture drawn in its colours costs nothing. At the end of 東郷神社地下 (M0003 (21,2), MS0015 08) the rock that
seals 高天原, 403Eh, and the opened wall, 403Dh, are wall set 4's 0240 0470 06A0. With the Windows walls'
0453 0342 0221 the rock took three slots of its own, the shimenawa two more, and the dead man or woman who
steps in (405Dh / 4060h, the NPC palette) found no room for 0BAC 084C 0652: slot 2, the walls' middle tone,
turned olive.

FOLLOW names such pictures and, for each index of theirs that the PC-98 art has equal to a slot of the
picture shown with them, that slot: the colour there becomes the other picture's (gfx_win_fit/<file>/
palettes.json when the Windows art refitted it, wingfx_new/ for a wall set, the game's own palette otherwise;
its variant). The Windows wall sets hold their tones the other way round (index 1 the light one, 3 the dark),
so a picture that follows walls takes the slot of the same tone. Pictures that belong to a room take the
room's fitted colours; 5038h takes its shopkeepers' 0BAC back in slot 9 (257 of its pixels, a light grey
there before). Only palettes change, in gfx_win_fit/<picture>/palettes.json; the
pictures keep their pixels, and a picture whose frames gfx_win_fit/ holds gets them stamped with the new
palette 0 (tools/gfx.py checks every frame PNG of an entry against palette 0). Each picture here is shown
with the one it follows, in the scripts or map events FOLLOW names; 401Dh besides over 5031h (MS006C 08, 09,
0B) and over 上野神殿's corridor (MS0020 3D, 3E; wall set 3), neither of which shares a colour with it in the
PC-98 art or now, and 403Fh for a moment over 5047h, the background MS0061 0B puts up before it takes 403Fh
down (one colour shared there in the PC-98 art, 07A5: one slot more for that moment).

Not in FOLLOW: an index whose colour stands for something the room's Windows picture has no colour for -
4087h's bright blue 0B2F sparkle keeps its colour and takes one slot of its own. And colours that belong
to people rather than to the room stay: the card soldiers of M0029 wear 0BAC like their room 5026h
(tools/winrooms.py KEEP holds it in the room instead), and 4042h, in fifty scripts, is drawn in the
default palette 503Eh's PC-98 picture is drawn in.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fcimage  # noqa: E402
import gfx  # noqa: E402

from PIL import Image  # noqa: E402

FIT = os.path.join(WORK, "gfx_win_fit")
WALLS = os.path.join(WORK, "wingfx_new")

# (picture file, entry, file and entry of the picture it follows, that picture's variant,
#  {picture index: slot of the followed picture}, where)
FOLLOW = [
    ("FC4010", 13, "FC5010", 7, 0, {1: 1, 2: 2, 3: 3}, "the bars of the prison cells, MS0013/MS0020/MS005F/MS0063"),
    ("FC4040", 3, "FC5040", 1, 0, {1: 1, 2: 2, 3: 3, 9: 9, 10: 10}, "鬼子母神's shrine door, MS0064 02"),
    ("FC4040", 4, "FC5040", 1, 0, {1: 1, 2: 2, 3: 3}, "the hexagram on it, MS0064 02"),
    ("FC4080", 7, "FC5040", 1, 0, {1: 1, 2: 2, 3: 3}, "the hexagram lit, MS0064 02"),
    ("FC4090", 10, "FC5010", 2, 0, {1: 1, 9: 9}, "銀座線's train doors, MS0026 1D/1E/22"),
    ("FC4090", 11, "FC5010", 2, 0, {10: 10}, "the doors opening, MS0026 1D/1E/22"),
    ("FC5090", 1, "FC5000", 5, 0, {1: 1, 2: 2, 3: 3, 9: 9, 10: 10},
     "邪教の館's palette carrier, MS003E 12/13 in the fusion"),
    ("FC4030", 15, "FC5000", 7, 0, {2: 2, 3: 3}, "the shining 八咫鏡 in 東郷神社, MS0061 0B"),
    ("FC4030", 14, "FC1040", 0, 0, {1: 3, 2: 2, 3: 1},
     "the rock that seals 高天原 at the end of 東郷神社地下's corridor (wall set 4), MS0015 08"),
    ("FC4030", 13, "FC1040", 0, 0, {1: 3, 2: 2, 3: 1}, "the same wall opened onto 高天原's light, MS0015 08"),
    ("FC5030", 8, "FC4070", 9, 0, {9: 9}, "道具屋 and its shopkeeper 4079h (407Fh, 4025h), map event kind 5Bh"),
]


def entry_now(stem, k):
    """Entry k of stem as the Windows art has it: gfx_win_fit/ for rooms and creatures, wingfx_new/ for the
    wall sets, the game's own when neither has a folder for it."""
    import winrooms
    if os.path.isdir(os.path.join(FIT, stem)):
        return winrooms.current_entry(stem, k, [])
    if os.path.isdir(os.path.join(WALLS, stem)):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(os.path.join(WALLS, stem), os.path.join(tmp, gfx.GFX_DIR, stem))
            files, _changes = gfx.edited_files(tmp)
        return list(fcimage.entries(files[stem + ".BIN"]))[k]
    return list(fcimage.entries(open(os.path.join(gfx.SRC, stem + ".BIN"), "rb").read()))[k]


def main():
    for stem, k, room_stem, room_k, room_v, pairs, where in FOLLOW:
        room = fcimage.Image(entry_now(room_stem, room_k))
        img = fcimage.Image(entry_now(stem, k))
        owned = [i for i, o in enumerate(img.owned()) if o]
        pals = [list(p) for p in img.palettes]
        for i, s in pairs.items():
            if i not in owned:
                raise SystemExit(f"{stem} entry {k}: index {i} is not a colour the entry sets")
            for p in pals:
                p[i] = room.palettes[room_v][s]
        folder = os.path.join(FIT, stem)
        os.makedirs(folder, exist_ok=True)
        pal_path = os.path.join(folder, "palettes.json")
        table = json.load(open(pal_path, encoding="utf-8")) if os.path.exists(pal_path) else {}
        table[str(k)] = [[f"{c:04X}" for c in p] for p in pals]
        json.dump({key: table[key] for key in sorted(table, key=int)}, open(pal_path, "w", encoding="utf-8"),
                  indent=1)
        stamp = gfx.palette_rgb(pals[0])
        for name in sorted(os.listdir(folder)):
            if name.startswith(f"{k:02d}_") and name.endswith(".png"):
                path = os.path.join(folder, name)
                im = Image.open(path)
                im.putpalette(stamp)
                im.save(path, transparency=gfx.TRANSPARENT)
        print(f"{stem} entry {k} ({where}): " + ", ".join(
            f"[{i}] {img.palettes[0][i]:04X}->{pals[0][i]:04X}" for i in pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
