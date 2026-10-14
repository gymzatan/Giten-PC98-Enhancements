#!/usr/bin/env python3
"""gamepad_test.py - the add-on tools/gamepad.py: DDS98.COM's own code run on an emulated CPU (unicorn) against the
game's program, and the add-on put into an image and taken out again.

  * hook_game, called as INT 33h AX=0Ch calls it (ES = the runtime segment of 0871), on DDS98.EXE as each image
    holds it (the Japanese original's, each image's given, each program file given): it recognises every site, counts one hook, and writes a
    far jump to its own stub at each (or points the far calls at 1603:BC2B, 25CA:5957 and 25CA:5960 at itself);
    called a second time it finds the sites changed and writes nothing;
  * game_path finds the program's own path after the environment's strings and makes A:\\DDS98\\DDS98.EXE of
    A:\\DDS98\\DDS98.COM (carry clear); a path with no dot gives carry set;
  * the dungeon's stick (stub_kbhit / stub_getch): a push gives '8' up, '7' left, '9' right, '5' down (about
    turn); held, up / left / right repeat after STEP frames and not before, down does not repeat; no stick leaves
    the game's own kbhit;
  * Y (Ctrl, the key map's byte 538h bit 4) held: free_keys turns the stick's directions into pointer movement,
    FM_MIN pixels a frame rising to FM_MAX, both axes on a diagonal, at most FM_CAP gathered, and the stick does
    not walk - nor after Y is let go until the stick is; free_apply moves the pointer through a stand-in mouse
    driver, keeps it on the screen, takes the driver's answer, and calls nothing with no movement;
  * Shift (bit 0) held: free_arrows does the same with the arrows, which then pick no target - nor after Shift is
    let go until they are; Y and Shift together add up;
  * UI mode put aside by a menu opened from the UI (menu_up) comes back at the next request once the menu is gone
    and the UI is live (choose), not while something newer of the view is live nor with the UI gone;
  * B (BS) in UI mode, or back in it, leaves the UI - the pointer's place there kept - and is not the right
    button; free_apply then puts the pointer in the middle of the view once; out of UI mode B is the right button;
  * what a request reads of the game: win_open finds only windows in the game's open list, pic_ok passes only a
    handle in use within the VM table and a frame below the picture's count (keeping every register), safe_rect
    calls 0871:B948 only then, enum_window reads nothing of a closed window, enum_groups only groups hit-tested in
    the last LIVE - 2 frames;
  * field_objs finds a person (type 1) or a chest (type 3) in the object table, and nothing else;
  * on an image (the Japanese dump): installed() is False; install() adds DDS98\\DDS98.COM, installed() is True and
    a second install refuses; remove() gives every file back; another program named DDS98.COM is refused.

    gamepad_test.py [--image HDI ...] [--exe DDS98.EXE ...]
"""
import argparse
import os
import struct
import sys

from unicorn import UC_ARCH_X86, UC_MODE_16, Uc
from unicorn import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import asm86  # noqa: E402
import gamepad  # noqa: E402
from fat12 import Fat12, open_hdi  # noqa: E402
from fat12w import Fat12W  # noqa: E402
from mz import MZ  # noqa: E402

SRC = os.path.join(WORK, "files", "DDS98")
JP = os.path.join(WORK, "inputs", "Japanese.hdi")
LOAD = 0x1000                           # the game's load segment
COMSEG = 0x9000                         # DDS98.COM's PSP
ENVSEG = 0x8F00
SENT = 0xFFF0                           # a hlt in COMSEG the near calls return to
fails = 0


def check(ok, what):
    global fails
    fails += not ok
    print(("  ok    " if ok else "  FAIL  ") + what)


def machine(com, game=None):
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 0x100000)
    if game is not None:
        uc.mem_write(LOAD * 16, game)
    uc.mem_write(COMSEG * 16 + 0x100, com)
    uc.mem_write(COMSEG * 16 + SENT, b"\xf4")
    return uc


def call(uc, ip, es=0):
    for reg, val in ((X.UC_X86_REG_CS, COMSEG), (X.UC_X86_REG_DS, COMSEG), (X.UC_X86_REG_SS, COMSEG),
                     (X.UC_X86_REG_ES, es), (X.UC_X86_REG_SP, 0xFF00), (X.UC_X86_REG_IP, ip)):
        uc.reg_write(reg, val)
    uc.mem_write(COMSEG * 16 + 0xFF00, struct.pack("<H", SENT))
    uc.reg_write(X.UC_X86_REG_SP, 0xFF00)
    uc.emu_start(COMSEG * 16 + ip, COMSEG * 16 + SENT, count=200_000)


def game_image(exe):
    path = os.path.join(WORK, "build", "_gamepad_test.exe")
    with open(path, "wb") as f:
        f.write(exe)
    try:
        return bytes(MZ(path, base=LOAD).image)
    finally:
        os.remove(path)


def hook_checks(label, exe, com, labels):
    print(f"== hook_game：{label}")
    uc = machine(com, game_image(exe))
    w = lambda seg, off: struct.unpack("<H", uc.mem_read((LOAD + seg) * 16 + off, 2))[0]  # noqa: E731
    b = lambda seg, off: uc.mem_read((LOAD + seg) * 16 + off, 1)[0]  # noqa: E731
    call(uc, labels["hook_game"], es=LOAD + 0x0871)
    hooks = struct.unpack("<H", uc.mem_read(COMSEG * 16 + labels["hooks"], 2))[0]
    check(hooks == 1, f"认出全部挂钩点（hooks = {hooks}）")
    jumps = [(0x0871, 0x5142, "frame_stub"), (0x0871, 0x83AC, "stub_wait"), (0x25CA, 0x348A, "stub_cells"),
             (0x25CA, 0x1980, "stub_obj"), (0x25CA, 0x561C, "stub_grp"), (0x1603, 0x71C2, "stub_btn"),
             (0x358E, 0xA5B4, "stub_slots"), (0x358E, 0xAA24, "stub_route"), (0x358E, 0x7764, "stub_field")]
    ok = all(b(seg, off) == 0xEA and w(seg, off + 1) == labels[stub] and w(seg, off + 3) == COMSEG
             for seg, off, stub in jumps)
    calls = [(0x1603, 0xBC2B, "stub_sprite"), (0x25CA, 0x5957, "stub_kbhit"), (0x25CA, 0x5960, "stub_getch")]
    ok = ok and all(b(seg, off) == 0x9A and w(seg, off + 1) == labels[stub] and w(seg, off + 3) == COMSEG
                    for seg, off, stub in calls)
    check(ok, f"{len(jumps)} 处远跳转、{len(calls)} 处远调用都指向 DDS98.COM 的入口")
    before = bytes(uc.mem_read(LOAD * 16, len(game_image(exe))))
    call(uc, labels["hook_game"], es=LOAD + 0x0871)
    hooks = struct.unpack("<H", uc.mem_read(COMSEG * 16 + labels["hooks"], 2))[0]
    after = bytes(uc.mem_read(LOAD * 16, len(before)))
    check(hooks == 1 and after == before, "第二次调用不再改动")


def path_checks(com, labels):
    print("== game_path")
    for prog, want in ((b"A:\\DDS98\\DDS98.COM", b"A:\\DDS98\\DDS98.EXE"), (b"C:\\GAMES\\X\\DDS98.COM", b"C:\\GAMES\\X\\DDS98.EXE"),
                       (b"A:\\DDS98\\NODOT", None)):
        uc = machine(com)
        env = b"PATH=A:\\\0COMSPEC=A:\\COMMAND.COM\0\0" + struct.pack("<H", 1) + prog + b"\0"
        uc.mem_write(ENVSEG * 16, env)
        uc.mem_write(COMSEG * 16 + 0x2C, struct.pack("<H", ENVSEG))
        call(uc, labels["game_path"])
        carry = uc.reg_read(X.UC_X86_REG_EFLAGS) & 1
        got = bytes(uc.mem_read(COMSEG * 16 + labels["path"], 80)).split(b"\0", 1)[0]
        if want is None:
            check(carry == 1, f"{prog.decode()}：没有扩展名，carry 置位")
        else:
            check(carry == 0 and got == want, f"{prog.decode()} → {got.decode()}")


def stick_checks(com, labels):
    """stub_kbhit / stub_getch, far-called as from 25CA:5957 / 5960, with the run-time's kbhit / getch a stub that
    returns 0: a new push of the stick gives its digit, a held one gives it again STEP frames after the last, but
    down (the about turn) only once per push; no stick, the run-time's own."""
    print("== 迷宫里的摇杆（25CA:5957 / 5960）")
    fake = 0xFE00                                   # xor ax,ax / retf: the run-time's kbhit and getch, nothing waiting
    names = {1: "上", 2: "左", 4: "右", 8: "下"}

    def poll(jstick, new, since):
        uc = machine(com)
        uc.mem_write(COMSEG * 16 + fake, b"\x31\xc0\xcb")
        for name in ("f_kbhit", "f_getch"):
            uc.mem_write(COMSEG * 16 + labels[name], struct.pack("<HH", fake, COMSEG))
        put = lambda name, data: uc.mem_write(COMSEG * 16 + labels[name], data)  # noqa: E731
        put("jstick", bytes([jstick]))
        put("jstick_new", bytes([new]))
        put("frame", struct.pack("<H", 1000))
        put("step_at", struct.pack("<H", 1000 - since))
        out = []
        for stub in ("stub_kbhit", "stub_getch"):
            uc.mem_write(COMSEG * 16 + 0xFF00, struct.pack("<HH", SENT, COMSEG))
            for reg, val in ((X.UC_X86_REG_CS, COMSEG), (X.UC_X86_REG_DS, COMSEG), (X.UC_X86_REG_SS, COMSEG),
                             (X.UC_X86_REG_SP, 0xFF00), (X.UC_X86_REG_IP, labels[stub])):
                uc.reg_write(reg, val)
            uc.emu_start(COMSEG * 16 + labels[stub], COMSEG * 16 + SENT, count=10_000)
            out.append(uc.reg_read(X.UC_X86_REG_AX))
        return out[0], chr(out[1]) if out[0] else None
    step = gamepad_step()
    for bit, digit in ((1, "8"), (2, "7"), (4, "9"), (8, "5")):
        got = poll(bit, bit, 0)
        check(got == (1, digit), f"摇杆{names[bit]}刚推：键 {got[1]!r}（应为 {digit!r}）")
    for bit, digit in ((1, "8"), (2, "7"), (4, "9")):
        early, due = poll(bit, 0, step - 1), poll(bit, 0, step)
        check(early == (0, None) and due == (1, digit),
              f"摇杆{names[bit]}按住：{step - 1} 帧时不重复，{step} 帧时再给 {due[1]!r}")
    held = poll(8, 0, 10 * step)
    check(held == (0, None), "摇杆下按住：不重复转身（再推一次才再转）")
    check(poll(0, 0, 10 * step) == (0, None), "没推摇杆：交给游戏自己的 kbhit")


DGROUP = 0x7000                         # stands for the game's DGROUP: the pointer at 1A8 / 1AA
DRIVER = 0xFD00                         # a stand-in mouse driver in COMSEG (INT 33h AX=4 keeps the place, AX=3 gives
DRV_X, DRV_Y = 0xFE80, 0xFE82           # it back within its limits, x at most DRV_MAX_X); a count of calls at DRV_N
DRV_N, DRV_MAX_X = 0xFE84, 600


def driver():
    code, _ = asm86.assemble(f"""
    cmp ax, 4
    jne d3
    inc word ptr cs:[{DRV_N:#x}]
    mov word ptr cs:[{DRV_X:#x}], cx
    mov word ptr cs:[{DRV_Y:#x}], dx
    iret
d3:
    inc word ptr cs:[{DRV_N:#x}]
    mov cx, word ptr cs:[{DRV_X:#x}]
    cmp cx, {DRV_MAX_X}
    jle d4
    mov cx, {DRV_MAX_X}
d4:
    mov dx, word ptr cs:[{DRV_Y:#x}]
    iret
""", org=DRIVER)
    return code


def free_checks(com, labels):
    """One VSYNC's free_keys (es = 0, cl = the pad's directions) and free_arrows (bl = the keys as held, low nibble
    the arrows), and free_apply (the game's frame, DS = DGROUP): with Y - Ctrl, the key map's byte 538h bit 4 - held,
    the stick's directions move the pointer and do not walk; with Shift (bit 0) held the arrows do, and pick no
    target; slowly at first, both together on a diagonal; let go of Y or Shift, the stick walks and the arrows pick
    again only after they have been let go; the pointer stays on the screen and takes the driver's answer."""
    print("== 按住 Y（Ctrl）时摇杆、按住 Shift 时方向键自由移动指针")
    uc = machine(com)
    word = lambda off: struct.unpack("<h", uc.mem_read(COMSEG * 16 + off, 2))[0]  # noqa: E731
    setw = lambda off, v: uc.mem_write(COMSEG * 16 + off, struct.pack("<h", v))  # noqa: E731

    def run(label, regs):
        for reg, val in ((X.UC_X86_REG_CS, COMSEG), (X.UC_X86_REG_DS, DGROUP), (X.UC_X86_REG_SS, COMSEG),
                         (X.UC_X86_REG_ES, 0)) + regs:
            uc.reg_write(reg, val)
        uc.mem_write(COMSEG * 16 + 0xFF00, struct.pack("<H", SENT))
        uc.reg_write(X.UC_X86_REG_SP, 0xFF00)
        uc.emu_start(COMSEG * 16 + labels[label], COMSEG * 16 + SENT, count=10_000)

    def keys(ctrl, cl, shift=False, bl=0):
        """-> (cl, bl) as the frame goes on with them"""
        uc.mem_write(0x538, bytes([(0x10 if ctrl else 0) | (1 if shift else 0)]))
        run("free_keys", ((X.UC_X86_REG_CX, cl), (X.UC_X86_REG_AX, 0x55AA)))
        cl = uc.reg_read(X.UC_X86_REG_CX) & 0xFF
        run("free_arrows", ((X.UC_X86_REG_BX, bl), (X.UC_X86_REG_CX, 0x1234), (X.UC_X86_REG_AX, 0x55AA)))
        kept = uc.reg_read(X.UC_X86_REG_CX) == 0x1234 and uc.reg_read(X.UC_X86_REG_AX) == 0x55AA
        return cl, (uc.reg_read(X.UC_X86_REG_BX) & 0xFF) if kept else None

    def fresh():
        for name in ("fm_dx", "fm_dy"):
            setw(labels[name], 0)
        for name in ("fm_h1", "fm_h2", "fm_block", "fm_run", "fm_dirs", "sh_h1", "sh_h2", "arr_block"):
            uc.mem_write(COMSEG * 16 + labels[name], b"\0")
    fresh()
    cl, bl = keys(False, 1, False, 0x21)
    check((cl, bl) == (1, 0x21) and word(labels["fm_dy"]) == 0, "没按 Y、Shift：摇杆照旧走路，方向键照旧跳目标，指针不动")
    cl, _ = keys(True, 1)
    check(cl == 0 and word(labels["fm_dy"]) == -1 and word(labels["fm_dx"]) == 0, "按住 Y 推上：不走路，指针上移 1 点")
    fresh()
    _, bl = keys(False, 0, True, 0x24)
    check(bl == 0x20 and word(labels["fm_dx"]) == 1, "按住 Shift 按右：不跳目标（A 照旧），指针右移 1 点")
    fresh()
    steps = []
    for _ in range(60):
        setw(labels["fm_dy"], 0)
        keys(True, 8)
        steps.append(word(labels["fm_dy"]))
    ramp = steps[0] == 1 and all(b >= a for a, b in zip(steps, steps[1:])) and max(steps) == 8 and steps[45] == 8
    check(ramp, f"按住下：每帧 {steps[0]} 点起，越来越快，约 3/4 秒后每帧 8 点（{steps[:8]}… {steps[-1]}）")
    fresh()
    keys(True, 2 | 1)
    check(word(labels["fm_dx"]) == -1 and word(labels["fm_dy"]) == -1, "斜推（左上）：两个方向一起动")
    fresh()
    keys(True, 1, True, 4)
    check(word(labels["fm_dx"]) == 1 and word(labels["fm_dy"]) == -1, "Y + 摇杆上、Shift + 右同时：合成一个方向")
    fresh()
    for _ in range(80):
        keys(True, 4)
    check(word(labels["fm_dx"]) == 64, f"游戏一帧之间最多攒 64 点（{word(labels['fm_dx'])}）")
    fresh()
    keys(True, 1)
    keys(False, 1)
    keys(False, 1)
    held = keys(False, 1)[0]
    released = keys(False, 0)[0]
    again = keys(False, 1)[0]
    check(held == 0 and released == 0 and again == 1, "先松开 Y、摇杆还推着：不走路；摇杆松开再推才走")
    fresh()
    keys(False, 0, True, 1)
    keys(False, 0, False, 1)
    keys(False, 0, False, 1)
    held = keys(False, 0, False, 1)[1]
    released = keys(False, 0, False, 0)[1]
    again = keys(False, 0, False, 1)[1]
    check(held == 0 and released == 0 and again == 1, "先松开 Shift、方向键还按着：不跳目标；松开再按才跳")

    uc.mem_write(COMSEG * 16 + DRIVER, driver())
    uc.mem_write(COMSEG * 16 + labels["old33"], struct.pack("<HH", DRIVER, COMSEG))

    def apply(x, y, dx, dy):
        uc.mem_write(DGROUP * 16 + 0x1A8, struct.pack("<hh", x, y))
        setw(labels["fm_dx"], dx)
        setw(labels["fm_dy"], dy)
        setw(DRV_N, 0)
        for reg, val in ((X.UC_X86_REG_CS, COMSEG), (X.UC_X86_REG_DS, DGROUP), (X.UC_X86_REG_SS, COMSEG)):
            uc.reg_write(reg, val)
        uc.mem_write(COMSEG * 16 + 0xFF00, struct.pack("<H", SENT))
        uc.reg_write(X.UC_X86_REG_SP, 0xFF00)
        uc.emu_start(COMSEG * 16 + labels["free_apply"], COMSEG * 16 + SENT, count=10_000)
        got = struct.unpack("<hh", uc.mem_read(DGROUP * 16 + 0x1A8, 4))
        return got, (word(DRV_X), word(DRV_Y)), word(DRV_N), (word(labels["fm_dx"]), word(labels["fm_dy"]))
    got, drv, n, left = apply(100, 100, 30, -20)
    check(got == (130, 80) and drv == (130, 80) and n == 2 and left == (0, 0), f"攒下的移动交给鼠标驱动：{got}")
    got, drv, n, _ = apply(20, 390, -150, 40)
    check(got == (0, 399) and drv == (0, 399), f"不出屏幕：{got}")
    got, drv, n, _ = apply(595, 10, 20, 0)
    check(got == (600, 10) and drv == (615, 10), f"驱动自己的范围更窄时，用驱动给回的位置：{got}")
    got, drv, n, _ = apply(50, 60, 0, 0)
    check(got == (50, 60) and n == 0, "没有移动：不调用鼠标驱动")


def near(uc, ip, ds=COMSEG, regs=()):
    """A near call into DDS98.COM's code at ip, returning to SENT."""
    for reg, val in ((X.UC_X86_REG_CS, COMSEG), (X.UC_X86_REG_DS, ds), (X.UC_X86_REG_SS, COMSEG)) + tuple(regs):
        uc.reg_write(reg, val)
    uc.mem_write(COMSEG * 16 + 0xFF00, struct.pack("<H", SENT))
    uc.reg_write(X.UC_X86_REG_SP, 0xFF00)
    uc.emu_start(COMSEG * 16 + ip, COMSEG * 16 + SENT, count=50_000)


def ui_checks(com, labels):
    """view_up (through menu_up / scene_up) and choose: UI mode put aside by something coming up in the view comes
    back at the next request once nothing is live beyond what was there before, while the UI (here the party list)
    is live; not while that thing or something newer is live, nor with the UI gone."""
    print("== 从界面打开的菜单关掉以后，方向键回到界面")
    live = 20
    b = lambda name, k=0: labels[name] + k  # noqa: E731

    def setup(ui_live, obj):
        uc = machine(com)
        for name, n in (("win_ttl", 16), ("grp_ttl", 4)):
            uc.mem_write(COMSEG * 16 + b(name), bytes(n))
        for name in ("btn_ttl", "slot_ttl", "obj_ttl", "spr_ttl", "ui_susp", "susp_other", "menu"):
            uc.mem_write(COMSEG * 16 + b(name), b"\0")
        if ui_live:
            uc.mem_write(COMSEG * 16 + b("win_ttl"), bytes([live]))
            uc.mem_write(COMSEG * 16 + b("win_from"), struct.pack("<H", 0x3513))
        uc.mem_write(COMSEG * 16 + b("obj_ttl"), bytes([live if obj else 0]))
        uc.mem_write(COMSEG * 16 + b("ui_mode"), b"\1")
        return uc

    def menu_window(uc, on):
        uc.mem_write(COMSEG * 16 + b("win_ttl", 1), bytes([live if on else 0]))
        uc.mem_write(COMSEG * 16 + b("win_from", 2), struct.pack("<H", 0x1234))

    def choose(uc):
        near(uc, labels["choose"])
        return uc.reg_read(X.UC_X86_REG_AX) & 0xFF, uc.mem_read(COMSEG * 16 + b("ui_mode"), 1)[0]
    uc = setup(True, False)
    near(uc, labels["menu_up"])
    menu_window(uc, True)
    during = choose(uc)
    menu_window(uc, False)
    after = choose(uc)
    check(during == (0, 0) and after == (0, 1), f"界面里打开菜单再取消：菜单在时选菜单 {during}，取消后回到界面 {after}")
    uc = setup(True, True)
    near(uc, labels["menu_up"])
    menu_window(uc, False)
    got = choose(uc)
    check(got == (0, 1), f"面前有人（场景层一直在）时也回到界面：{got}")
    uc = setup(True, False)
    near(uc, labels["menu_up"])
    menu_window(uc, False)
    uc.mem_write(COMSEG * 16 + b("obj_ttl"), bytes([live]))
    got = choose(uc)
    check(got == (1, 0), f"菜单关掉后又出现了新的目标：留在画面里选目标 {got}")
    uc = setup(False, False)
    near(uc, labels["menu_up"])
    got = choose(uc)
    check(got[1] == 0 and uc.mem_read(COMSEG * 16 + b("ui_susp"), 1)[0] == 0, f"界面已经不在画面上：不回去 {got}")


def b_checks(com, labels):
    """keys (one VSYNC, DS = DGROUP, the key map at 0:052A) with BS (0Eh: byte 52Bh bit 6) newly down: in UI mode
    (the party list live) it leaves the UI, keeping the pointer's place there, and is not the right button, also
    while held and when let go; then free_apply puts the pointer in the middle of the view through the stand-in
    mouse driver, once. Out of UI mode it is the right button (DS:1AE) - also with UI mode put aside by a menu still
    open; with that menu gone it is back in UI mode and leaves it."""
    print("== 界面状态下按 B（Backspace）：回到画面中间")
    b = lambda name, k=0: COMSEG * 16 + labels[name] + k  # noqa: E731

    def setup(ui):
        uc = machine(com)
        uc.mem_write(COMSEG * 16 + DRIVER, driver())
        uc.mem_write(b("old33"), struct.pack("<HH", DRIVER, COMSEG))
        uc.mem_write(b("win_ttl"), bytes([20]) + bytes(15))
        uc.mem_write(b("win_from"), struct.pack("<H", 0x3513))
        for name in ("ui_mode", "ui_ok", "ui_susp", "to_view", "keys_prev", "ky_h1", "ky_h2", "b_cnt", "wm_ttl",
                     "joy_ttl", "menu", "restore"):
            uc.mem_write(b(name), b"\0")
        uc.mem_write(b("ui_mode"), bytes([ui]))
        uc.mem_write(DGROUP * 16 + 0x1A8, struct.pack("<hhhh", 560, 48, 0, 0))
        return uc

    def frame(uc, bs):
        uc.mem_write(0x52B, bytes([0x40 if bs else 0]))
        near(uc, labels["keys"], DGROUP)
        return struct.unpack("<h", uc.mem_read(DGROUP * 16 + 0x1AE, 2))[0]
    v = lambda uc, name: uc.mem_read(b(name), 1)[0]  # noqa: E731
    uc = setup(1)
    right = [frame(uc, True), frame(uc, True)]
    ui_xy = struct.unpack("<hh", uc.mem_read(b("ui_x"), 4))
    check(right == [0, 0] and v(uc, "ui_mode") == 0 and v(uc, "to_view") == 1 and v(uc, "ui_ok") == 1
          and ui_xy == (560, 48), f"界面状态：离开界面（记下界面里的位置 {ui_xy}），不当右键")
    for _ in range(4):
        frame(uc, False)
    check(frame(uc, False) == 0 and v(uc, "menu") == 0 and v(uc, "ui_mode") == 0, "松开 B：不补发右键、不进选项模式")
    uc.mem_write(DGROUP * 16 + 0x1A8, struct.pack("<hh", 560, 48))
    setw = lambda addr, val: uc.mem_write(addr, struct.pack("<H", val))  # noqa: E731
    setw(COMSEG * 16 + DRV_N, 0)
    near(uc, labels["free_apply"], DGROUP)
    got = struct.unpack("<hh", uc.mem_read(DGROUP * 16 + 0x1A8, 4))
    drv = struct.unpack("<hh", uc.mem_read(COMSEG * 16 + DRV_X, 4))
    check(got == (320, 131) and drv == (320, 131) and v(uc, "to_view") == 0, f"游戏的下一帧：指针到画面中间 {got}")
    setw(COMSEG * 16 + DRV_N, 0)
    near(uc, labels["free_apply"], DGROUP)
    n = struct.unpack("<H", uc.mem_read(COMSEG * 16 + DRV_N, 2))[0]
    check(n == 0, "只放一次（之后不再调用鼠标驱动）")
    uc = setup(0)
    right = frame(uc, True)
    check(right == 1 and v(uc, "to_view") == 0, "不在界面状态：B 照旧是右键")
    uc = setup(0)
    uc.mem_write(b("ui_susp"), b"\1")
    uc.mem_write(b("win_ttl", 1), bytes([20]))
    uc.mem_write(b("win_from", 2), struct.pack("<H", 0x1234))
    right = frame(uc, True)
    check(right == 1 and v(uc, "ui_mode") == 0 and v(uc, "to_view") == 0,
          "界面里打开的菜单还在：B 是右键（取消菜单）")
    uc = setup(0)
    uc.mem_write(b("ui_susp"), b"\1")
    right = frame(uc, True)
    check(right == 0 and v(uc, "ui_mode") == 0 and v(uc, "to_view") == 1 and v(uc, "ui_susp") == 0,
          "菜单取消以后（回到界面状态）再按 B：离开界面，不当右键")


def stale_checks(com, labels):
    """What the add-on reads of the game's windows and pictures, which may be gone since their last hit test:
    win_open finds a window only in the game's open list (DS:7170, 16 words, FFFFh free); pic_ok (and safe_rect
    through it) passes a picture handle only within the VM table (1..1023, DS:[616A], 8 bytes each) and in use, and a
    frame of a frame picture (first word 0) only below its count - keeping every register; enum_window on a window
    not open returns before reading it."""
    print("== 失效的窗口和图片：只读还开着的窗口、还在用的图片句柄和范围内的帧")
    TSEG, PIC = 0x5000, 0xFC00                      # the VM table's segment; a picture record in COMSEG
    LOCK, RECT, NLOCK, NRECT = 0xFB00, 0xFB40, 0xFB80, 0xFB82
    uc = machine(com)
    lock, _ = asm86.assemble(f"""
    inc word ptr cs:[{NLOCK:#x}]
    mov ax, {PIC:#x}
    mov dx, cs
    mov bx, 0x1111
    mov cx, 0x2222
    mov es, cx
    retf 2
""", org=LOCK)
    rect, _ = asm86.assemble(f"""
    inc word ptr cs:[{NRECT:#x}]
    mov ax, {PIC:#x}
    mov dx, cs
    retf 4
""", org=RECT)
    uc.mem_write(COMSEG * 16 + LOCK, lock)
    uc.mem_write(COMSEG * 16 + RECT, rect)
    uc.mem_write(COMSEG * 16 + labels["f_lock"], struct.pack("<HH", LOCK, COMSEG))
    uc.mem_write(COMSEG * 16 + labels["f_rect"], struct.pack("<HH", RECT, COMSEG))
    uc.mem_write(DGROUP * 16 + 0x616A, struct.pack("<H", TSEG))
    uc.mem_write(TSEG * 16 + 5 * 8, b"\x01")
    uc.mem_write(TSEG * 16 + 6 * 8, b"\x00")
    uc.mem_write(DGROUP * 16 + 0x7170, struct.pack("<16h", 3, 0, 9, *([-1] * 13)))
    w = lambda off: struct.unpack("<H", uc.mem_read(COMSEG * 16 + off, 2))[0]  # noqa: E731

    def regs_run(label, ax, bx, cx):
        uc.mem_write(COMSEG * 16 + NLOCK, b"\0\0\0\0")
        near(uc, labels[label], DGROUP, ((X.UC_X86_REG_AX, ax), (X.UC_X86_REG_BX, bx), (X.UC_X86_REG_CX, cx),
                                         (X.UC_X86_REG_DX, 0x4444), (X.UC_X86_REG_ES, 0x3333)))
        return uc.reg_read(X.UC_X86_REG_EFLAGS)

    got = []
    for n in (3, 0, 9, 1, 15):
        got.append(bool(regs_run("win_open", 0, n, 0x5555) & 0x40) and uc.reg_read(X.UC_X86_REG_CX) == 0x5555)
    check(got == [True, True, True, False, False], f"只有开着的窗口（列表里的 3、0、9）算开着：{got}")

    def pic(handle, frame, kind=0, count=10):
        uc.mem_write(COMSEG * 16 + PIC, struct.pack("<HH", kind, count))
        flags = regs_run("pic_ok", handle, 0x7777, frame)
        kept = (uc.reg_read(X.UC_X86_REG_AX), uc.reg_read(X.UC_X86_REG_BX), uc.reg_read(X.UC_X86_REG_CX),
                uc.reg_read(X.UC_X86_REG_DX), uc.reg_read(X.UC_X86_REG_ES)) == (handle, 0x7777, frame, 0x4444, 0x3333)
        return (not flags & 1), kept
    cases = [((0, 0), False, "句柄 0"), ((1024, 0), False, "句柄 1024（表外）"), ((6, 0), False, "没在用的句柄"),
             ((5, 9), True, "在用的句柄、第 9 帧（共 10 帧）"), ((5, 10), False, "第 10 帧（超出 10 帧）"),
             ((5, 28676), False, "第 28676 帧（截图里的 req cgen）")]
    for (h, f), want, what in cases:
        ok, kept = pic(h, f)
        check(ok == want and kept, f"{what}：{'可以' if ok else '不读'}，寄存器不变")
    ok, kept = pic(5, 9999, kind=1)
    check(ok and kept, "不是逐帧的图（第一个字不为 0）：游戏不查帧数，照读")
    uc.mem_write(COMSEG * 16 + NRECT, b"\0\0")
    flags = regs_run("safe_rect", 6, 0, 0)
    check(flags & 1 and w(NRECT) == 0, "safe_rect：不在用的句柄，不调用 0871:B948")
    uc.mem_write(COMSEG * 16 + PIC, struct.pack("<HH", 0, 10))
    flags = regs_run("safe_rect", 5, 0, 2)
    check(not flags & 1 and w(NRECT) == 1 and uc.reg_read(X.UC_X86_REG_AX) == PIC, "safe_rect：可以的就调用 B948")
    uc.mem_write(COMSEG * 16 + NLOCK, b"\0\0\0\0")
    near(uc, labels["enum_window"], DGROUP, ((X.UC_X86_REG_BX, 1),))
    check(w(NRECT) == 0 and w(NLOCK) == 0, "已经关掉的窗口（不在列表里）：一样都不读")
    # a button group at DGROUP:2000 (one button, picture 1 -> frame 2 of handle 5), kept in slot 0
    grp = DGROUP * 16 + 0x2000
    uc.mem_write(grp, bytes(0x14 + 10))
    uc.mem_write(grp + 6, struct.pack("<hHH", 1, 0x2100, DGROUP))
    uc.mem_write(DGROUP * 16 + 0x2100, struct.pack("<H", 5))
    uc.mem_write(grp + 0x14 + 2, struct.pack("<H", 1))
    uc.mem_write(COMSEG * 16 + labels["grp_off"], struct.pack("<4H", 0x2000, 0, 0, 0))
    uc.mem_write(COMSEG * 16 + labels["grp_seg"], struct.pack("<4H", DGROUP, 0, 0, 0))
    uc.mem_write(COMSEG * 16 + labels["dgroup"], struct.pack("<H", DGROUP))
    uc.mem_write(COMSEG * 16 + labels["is_ui"], b"\0")
    seen = []
    for ttl in (20, 18, 17, 5):
        uc.mem_write(COMSEG * 16 + labels["grp_ttl"], bytes([ttl, 0, 0, 0]))
        uc.mem_write(COMSEG * 16 + labels["ntarg"], b"\0\0")
        uc.mem_write(COMSEG * 16 + NRECT, b"\0\0")
        near(uc, labels["enum_groups"], DGROUP)
        seen.append(w(NRECT))
    check(seen == [1, 1, 0, 0], f"按钮组只读最近 3 帧内被命中测试过的（栈上的按钮组函数一返回就成了乱码）：{seen}")


def field_checks(com, labels):
    """field_objs: whether the object table (count DS:13F0, records of 1Eh bytes in segment DS:6174, the type word
    first) holds a field object, type 1 or 3."""
    print("== 场地上的对象（面前的人、宝箱：类型 1、3）")
    seg = 0x6000
    for types, want in (([], 0), ([2, 2], 0), ([-1, 2], 0), ([2, 1], 1), ([3], 1), ([-1, -1, 3], 1)):
        uc = machine(com)
        uc.mem_write(DGROUP * 16 + 0x13F0, struct.pack("<h", len(types)))
        uc.mem_write(DGROUP * 16 + 0x6174, struct.pack("<H", seg))
        for i, t in enumerate(types):
            uc.mem_write(seg * 16 + 0x1E * i, struct.pack("<h", t))
        near(uc, labels["field_objs"], DGROUP)
        got = uc.reg_read(X.UC_X86_REG_AX)
        check(got == want, f"对象类型 {types or '（没有对象）'}：{'有' if got else '没有'}场地对象")


def gamepad_step():
    """STEP of tools/gamepad.py's source: the frames between two repeats of a held stick."""
    for line in open(gamepad.__file__, encoding="utf-8"):
        if line.startswith("STEP equ "):
            return int(line.split()[2], 0)
    raise SystemExit("tools/gamepad.py 里没有 STEP")


def image_checks(com):
    print("== 镜像上加装与卸载（日文 dump）")
    raw, hdr, disk, part = open_hdi(JP)
    fs = Fat12W(disk, part)
    before = {n: bytes(fs.read_chain(e["cluster"], e["size"])) for n, e in fs.walk()}
    check(gamepad.installed(fs, com) is False, "未加装")
    gamepad.install(fs, com)
    check(gamepad.installed(fs, com) is True and gamepad.read(fs, "DDS98/DDS98.COM") == com, "加装后有 DDS98\\DDS98.COM")
    try:
        gamepad.install(fs, com)
        check(False, "第二次加装被拒绝")
    except gamepad.GamepadError:
        check(True, "第二次加装被拒绝")
    gamepad.remove(fs, com)
    after = {n: bytes(fs.read_chain(e["cluster"], e["size"])) for n, e in fs.walk()}
    check(after == before, "卸载后每个文件都和原来一样")
    fs.create("DDS98", "DDS98.COM", b"\xb8\x00\x4c\xcd\x21")
    try:
        gamepad.installed(fs, com)
        check(False, "别的 DDS98.COM 被拒绝")
    except gamepad.GamepadError:
        check(True, "别的 DDS98.COM 被拒绝")


def exe_of(path):
    raw, hdr, disk, part = open_hdi(path)
    fs = Fat12(disk, part)
    e = fs.find("DDS98/DDS98.EXE")
    return bytes(fs.read_chain(e["cluster"], e["size"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", action="append", default=[])
    ap.add_argument("--exe", action="append", default=[])
    a = ap.parse_args()
    com, labels = gamepad.build()
    check(gamepad.build()[0] == com, f"DDS98.COM 每次汇编都一样（{len(com)} 字节）")
    hook_checks("原始日文版", open(os.path.join(SRC, "DDS98.EXE"), "rb").read(), com, labels)
    for path in a.image:
        hook_checks(os.path.basename(path), exe_of(path), com, labels)
    for path in a.exe:
        hook_checks(path, open(path, "rb").read(), com, labels)
    path_checks(com, labels)
    stick_checks(com, labels)
    free_checks(com, labels)
    ui_checks(com, labels)
    b_checks(com, labels)
    stale_checks(com, labels)
    field_checks(com, labels)
    image_checks(com)
    print(f"{'全部通过' if not fails else f'{fails} 项失败'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
