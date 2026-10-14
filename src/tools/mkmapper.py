#!/usr/bin/env python3
"""The bundle's DOSBox-X mapper file, mapper-giten.map: an XInput pad for the add-on 手柄操作 (tools/gamepad.py).

work/dosbox/defaults.map is the shipped emulator's own default mapper file (dosbox-x.exe sha1 21e24f75, its mapper
editor's Save, started with -startmapper, machine pc9821, joysticktype 4axis and no mapper file). A mapper file
replaces every bind (MAPPER_LoadBinds clears them all first), so the bundle's is that whole file with:
  - the joystick's default binds, as CreateDefaultBinds makes them (the editor ran with no pad open and saved those
    events empty);
  - the D-pad (hat 0) as the arrow keys, X (button 2) as Tab, Y (button 3) as the left Ctrl (held, the stick moves
    the pointer: tools/gamepad.py free_keys; the user, 2026-10-13: 「按住的时候左摇杆可以自由移动光标」, Ctrl
    chosen), LB / RB (buttons 4 / 5) as the digit keys 4 / 6 (the dungeon's sidesteps, which the game reads
    itself); those host inputs drive no emulated joystick event.
The left stick and A / B (buttons 0 / 1) stay the emulated joystick, which the PC-98 FM board reports to the game
(joysticktype auto: 4axis with one pad). SDL2's XInput order: buttons 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB, 6 Back,
7 Start; hat 0 the D-pad (1 up, 2 right, 4 down, 8 left).

    mkmapper.py [OUT]       default build/mapper-giten.map
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
DEFAULTS = os.path.join(WORK, "dosbox", "defaults.map")
NAME = "mapper-giten.map"
OUT = os.path.join(WORK, "build", NAME)

JOY_DEFAULTS = {
    "jbutton_0_0": ['"stick_0 button 0"'], "jbutton_0_1": ['"stick_0 button 1"'],
    "jbutton_0_2": [], "jbutton_0_3": [],
    "jbutton_0_4": [], "jbutton_0_5": [],
    "jbutton_1_0": ['"stick_1 button 0"'], "jbutton_1_1": ['"stick_1 button 1"'],
    "jaxis_0_0-": ['"stick_0 axis 0 0"'], "jaxis_0_0+": ['"stick_0 axis 0 1"'],
    "jaxis_0_1-": ['"stick_0 axis 1 0"'], "jaxis_0_1+": ['"stick_0 axis 1 1"'],
    "jaxis_0_2-": ['"stick_0 axis 2 0"'], "jaxis_0_2+": ['"stick_0 axis 2 1"'],
    "jaxis_0_3-": ['"stick_0 axis 3 0"'], "jaxis_0_3+": ['"stick_0 axis 3 1"'],
    "jaxis_1_0-": ['"stick_1 axis 0 0"'], "jaxis_1_0+": ['"stick_1 axis 0 1"'],
    "jaxis_1_1-": ['"stick_1 axis 1 0"'], "jaxis_1_1+": ['"stick_1 axis 1 1"'],
    "jhat_0_0_0": [], "jhat_0_0_1": [], "jhat_0_0_2": [], "jhat_0_0_3": [],
}
PAD_KEYS = {
    "key_up": '"stick_0 hat 0 1"', "key_right": '"stick_0 hat 0 2"', "key_down": '"stick_0 hat 0 4"',
    "key_left": '"stick_0 hat 0 8"', "key_tab": '"stick_0 button 2"', "key_lctrl": '"stick_0 button 3"',
    "key_4": '"stick_0 button 4"', "key_6": '"stick_0 button 5"',
}


def build(defaults=DEFAULTS):
    lines = open(defaults, encoding="ascii").read().splitlines()
    if lines[0] != "[SDL2]":
        raise SystemExit(f"{defaults}: not an SDL2 mapper file")
    seen, out = set(), []
    for line in lines:
        name, _, binds = line.partition(" ")
        if name in JOY_DEFAULTS:
            out.append(" ".join([name] + JOY_DEFAULTS[name]))
            seen.add(name)
        elif name in PAD_KEYS:
            if not binds.strip():
                raise SystemExit(f"{defaults}: {name} has no default bind")
            out.append(f"{name} {binds.strip()} {PAD_KEYS[name]}")
            seen.add(name)
        else:
            out.append(line.rstrip())
    missing = (set(JOY_DEFAULTS) | set(PAD_KEYS)) - seen
    if missing:
        raise SystemExit(f"{defaults}: no line for {sorted(missing)}")
    return ("\n".join(out) + "\n").encode("ascii")


def main(argv):
    out = argv[0] if argv else OUT
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    data = build()
    with open(out, "wb") as f:
        f.write(data)
    print(f"{out}: {data.count(b'\n')} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
