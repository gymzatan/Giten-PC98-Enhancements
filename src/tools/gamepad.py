#!/usr/bin/env python3
"""An add-on: 手柄操作 - a gamepad's or the keyboard's directions drive DDS98: the stick walks, the D-pad (the arrow
keys) moves the pointer from one clickable thing to the next. It is DDS98\\DDS98.COM, so nothing else of an image
changes: every startup this game has (its own AUTOEXEC.BAT, the Chinese builds', the English translation's boot
floppy) runs the command DDS98 in the game's folder, and DOS takes a .COM before an .EXE of the same name. The
program hooks INT 33h (when a mouse driver is there), gives back all memory but its own (about 8 KB), runs
DDS98.EXE from its own folder with the command line it was given (EXEC), and when the game ends puts INT 33h back
and leaves with the game's exit code.

Inputs: the stick is the PC-98 joystick's directions (and, on the world map, W A S D as well - in the dungeon those
are the game's own keys, tools/exekeys.py: W forward, Z back, A / D sidestep, Q / E turn, S about turn); the
D-pad is the arrow keys; A is Return, Space or joystick button 1 (the left button); B is ESC, BS or joystick
button 2 (the right button - in UI mode it leaves the UI instead, the pointer to the middle of the view: the user,
2026-10-13: 「然后再次按 backspace，应该回到画面中间」); Tab goes to the UI and back; Ctrl held makes the stick move
the pointer freely instead of walking (the user, 2026-10-13: 「其实还可以加入 Y 键的功能，按住的时候左摇杆可以自由移动
光标」, given as Ctrl; the D-pad keeps to the targets), and Shift held makes the arrows move it freely instead of
picking targets (「那还是 Shift+方向键算了」). An XInput pad gets there through the emulator: its stick and buttons
A / B as the PC-98 joystick, its D-pad as the arrow keys, X as Tab, Y as Ctrl, LB / RB as the digit keys 4 / 6 (the
dungeon's sidesteps, read by the game itself).

When the game registers its mouse handler 0871:52B6 (INT 33h
AX=0Ch from 0871:7904 through int86x, so ES = the runtime segment of 0871) the program checks the bytes of the
places below in the game's code (the same in the Japanese original and every edition built here) and puts a far
jump into each (or points a far call at itself):

  0871:5142  the frame's input update, run by the VSYNC interrupt: the keys are read from the BIOS's
             pressed-key map at 0:052A (nothing is taken out of the key buffer; a key counts as held while it
             was down in any of the last three frames, as a held key's repeat sends its break code before
             each make code); A holds the left button (DS:1AC), B the right one (DS:1AE) but in UI mode leaves
             it, Tab goes to the UI and back, an arrow asks for the next target that way (held: again after
             FIRST frames, then every NEXT frames); a request no hit test takes up within TTL frames is dropped.
             On the world map's walking screen the arrows walk like the stick, and B waits HOLD frames: let go
             before that, it switches option mode (on: the pointer's place is kept and it goes to the nearest
             option, the arrows pick options; off: the pointer goes back), held, it is the right button (the
             minimap); Tab there switches option mode as well. With Ctrl held (the key map's byte 538h, bit 4)
             the stick's directions are the pointer's instead, and with Shift held (bit 0) the arrows': FM_MIN
             pixels a frame at first, FM_MAX after FM_RAMP frames, gathered for the game's frame; the stick walks
             and the arrows pick targets again only once let go after Ctrl or Shift
  0871:83AC  the wait for the next VSYNC (game context, every frame loop): the PC-98 joystick is read from the
             FM board's OPN(A) register 0Eh, connector 1; the pointer moves by what Ctrl and the stick or Shift and
             the arrows gathered, or to the middle of the view (VIEW_X, VIEW_Y) after B left the UI (INT 33h AX=4,
             then AX=3's answer, kept on the 640 x 400 screen, into DS:1A8/1AA)
  25CA:5957  the dungeon's movement keys (25CA:5956, '1'..'9' through the table DS:17C0 when no movement
  25CA:5960  button is clicked): the far calls to the run-time's kbhit / getch come here first, and the pad's
             stick gives '8' (forward), '7' / '9' (turn left / right) - at once, then every STEP frames while
             held - and '5' (about turn) once per push (the user, 2026-10-13: down turns about, as the readme
             says; repeated while held it would turn back)
  25CA:348A  a window's cell hit test (menus 25CA:4380, the party list 358E:3480, 1F24's screens): the
             window is marked live and its caller remembered
  1603:71C2  the script's button list hit test (choices; [DS:1BC2] window, list at [DS:1BCE])
  25CA:561C  a button group's hit test (the title's NEW GAME / CONTINUE, the map's command panel and arrows,
             the status pages' tabs, the opening's dial pad, scroll buttons): up to four groups are kept
  358E:A5B4  the equipment page's slot list (ov12)
  25CA:1980  the scene objects' hit test (battle targets ov16:2C2E)
  358E:7764  the field's click handler, which the map screen 358E:716E calls each frame while it waits (state
             10h): the game hit-tests the field's objects - the person standing in front (type 1, placed by
             358E:A2D4 from the walking people of DS:9296) and the chest of the cell (type 3, ov18:0024) - only on
             a click, so while one is in the object table (count DS:13F0, records of 1Eh bytes in segment
             DS:6174) they are the scene layer from here (the user, 2026-10-13: 「对话对象和宝箱也要能够自动对准才行」)
  1603:BC2B  script command 2D8/2D9's far call (thunk 07B1:01F8 to ov05:0BF0: is the pointer on scene sprite
             first..last; the 不動像 scene's rope and rock, MS0015/19) now calls here first: the sprites are
             marked live with their range, then the call goes on to the thunk
  358E:AA24  the world map's scripted route: the destination pick ov45:01D6 asks it for the route's next
             point before it looks at a click, and walks there; with no route running (the walking screen,
             marked live) and the stick held (or an arrow out of option mode) it gets a point a step ahead
             instead - the nearest one at the distances
             of wk_dists and the side offsets of wk_offs (the roads are 1-2 pixel lines) that passes the
             checks ov45 makes on a click (on the view, 07B1:06EA on the map, ground 07B1:076E whose
             [3906 + kind] is set) - so the party walks while the key is held, the pointer untouched

The screen's frame is the UI: the command panel (DGROUP's button group PANEL, FIGHT ... STATUS) and the party
list (the window 358E:3480 hit-tests, caller PARTY). Everything else to click is the view: its menu layer (windows,
button lists, the other button groups, the equipment slots) and its scene layer (objects, scene sprites). The
direction pad (DGROUP's button group MOVES) is never a target: the stick and the keys walk. A hit test called
within LIVE frames makes its part live. The arrows stay in the view: of its two layers the one live is used, with
both the one that came up last (objects or sprites coming up, a battle target, a person or a chest in front, or
the statue, pick the scene layer; a window, a choice, a group or the slots, the menu layer); with nothing of the
view live (an empty corridor) the pointer stays where it is. Tab goes to the UI (UI mode): the pointer's place in
the view is kept, and it goes to where Tab last left the UI or else to the nearest UI target; the arrows then pick
UI targets only; Tab again keeps the place in the UI and puts the pointer back where it was in the view - as the
world map's option mode does, whose arrows pick UI targets too; B keeps the place in the UI as well, and puts the
pointer in the middle of the view. Something of the view coming up (a menu opened from the panel, the next
member's turn) puts UI mode aside: once nothing is live beyond what was live before it (the menu left with B or
its own EXIT), the next arrow or B is UI mode's again (the user, 2026-10-13: a DDS menu left with BS left the
arrows dead until Tab). UI mode ends when the UI goes off the screen, which also forgets the place in it. An arrow's
request is served in the game's own context at the next hit test of the layer in use: its targets are listed
with their boxes (each run of cells of each live window still open put through the game's own 348A; the button
list's nodes; each button's picture box from 0871:B948 of each group hit-tested in the last frames; the 8
equipment slots; the objects of type 2 from a 16-pixel grid put through 1980; each scene sprite's box as ov05:0BF0
places it, clicked at its pixel nearest the box's centre), and the pointer (DS:1A8/1AA,
and the mouse driver's by INT 33h AX=4) goes to the nearest one that way - or, when it is on none of them, to
the nearest one whatever the way; with none that way the arrows wrap round, to the target at the far end the other
way in the pointer's column or row (a list's last row, Down, its first; STATUS, Down, FIGHT). The fusion page's chart (ov22:12A6) is only to look at: its rows are the list
window beside it.

What a request reads of the game is checked first, as a window or a group may be gone since its last hit test (the
user, 2026-10-14: 「方向键用多了之后会报错」 - "grp err, max cgen=771, req cgen=28676" over a battle, later "no use hnd
req" and the game stopped): a window only while in the game's list of open windows (DS:7170; its close 25CA:1FB2
clears the record), a group only when hit-tested in the last LIVE - 2 frames (some are a function's locals on the
stack, garbage once it returns: one at DS:BE9A), at most MAXT buttons or list nodes, and before 0871:B948 a picture
handle only within the VM's table and in use (0871:97B4 stops the game otherwise) and a frame only below the
picture's count (0871:B9F0 prints "grp err" otherwise).

The user (2026-10-13): an add-on the patch page offers, and an English patch of its own; the emulator maps an
XInput pad's D-pad to the arrows (DOSBox-X: the bundle's mapper file); Tab returns to where the pointer was, as the
world map's option mode does (「Tab 也改成记住原来的位置」); the arrows never go to the UI or the direction pad, the
UI is Tab's alone (「UI 应该是 Tab 键才把光标移动过去」, 「方向盘…要跳过」); the arrows wrap round at the ends
(「光标还应该实现卷轴式移动」).

    gamepad.py [OUT.COM]       the program (default build/DDS98.COM) and its labels (OUT.labels.json)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from asm86 import assemble  # noqa: E402

NAME = "手柄操作"
DIR = "DDS98"
COM = "DDS98.COM"
OUT = os.path.join(os.path.dirname(HERE), "build", COM)

SOURCE = r"""
LIVE equ 20
MAXT equ 64
FIRST equ 18
NEXT equ 5
TTL equ 60
HOLD equ 30
STEP equ 15
FM_MIN equ 1                    ; the pointer under the stick with Y held: pixels a frame at first,
FM_MAX equ 8                    ; and after FM_RAMP frames held (about 3/4 s);
FM_RAMP equ 42
FM_CAP equ 64                   ; at most this much gathered between two of the game's frames
SCREEN_W equ 640
SCREEN_H equ 400
VIEW_X equ 320                  ; the middle of the view (the field's picture: x 136-503, y 32-230)
VIEW_Y equ 131
PARTY equ 0x3513                ; the party list window's hit test caller (358E:3480): UI
PANEL equ 0x17d2                ; DGROUP's command panel button group (FIGHT ... STATUS): UI
MOVES equ 0x1766                ; DGROUP's direction pad button group: never a target

    jmp install

sig:        db "DPAD"
old33:      dw 0, 0
dgroup:     dw 0
back_frame: dw 0x5148, 0
back_cells: dw 0x348f, 0
back_obj:   dw 0x1985, 0
back_btn:   dw 0x71c7, 0
back_grp:   dw 0x5623, 0
back_slots: dw 0xa5b9, 0
back_route: dw 0xaa29, 0
back_field: dw 0x7769, 0
f_valid:    dw 0x06ea, 0
f_ground:   dw 0x076e, 0
f_kbhit:    dw 0x0d80, 0
f_getch:    dw 0x0da6, 0
wk_flag:    dw 0
wk_px:      dw 0
wk_py:      dw 0
wk_dx:      dw 0
wk_dy:      dw 0
wk_tx:      dw 0
wk_ty:      dw 0
wk_dists:   dw 10, 8, 12, 6, 14, 4, 16, 0
wk_offs:    dw 0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -7, 7, -8, 8
wk_offs_end:
f_rect:     dw 0xb948, 0
f_type:     dw 0x1aba, 0
f_lock:     dw 0x9326, 0
back_wait:  dw 0x83b3, 0
f_sprites:  dw 0x01f8, 0
f_proj:     dw 0xaea8, 0
f_pix:      dw 0xaf18, 0
f_view:     dw 0x16c4, 0
hooks:      dw 0
services:   dw 0
last_n:     dw 0
last_x:     dw 0
last_y:     dw 0
frame:      dw 0
keys_prev:  db 0
ky_h1:      db 0
ky_h2:      db 0
st_h1:      db 0
st_h2:      db 0
stick:      db 0
jstick:     db 0
jstick_new: db 0
walk:       db 0
digit:      db 0
step_at:    dw 0
fm_h1:      db 0
fm_h2:      db 0
fm_block:   db 0
fm_run:     db 0
fm_dirs:    db 0
sh_h1:      db 0
sh_h2:      db 0
arr_block:  db 0
fm_dx:      dw 0
fm_dy:      dw 0
menu:       db 0
restore:    db 0
b_cnt:      db 0
save_x:     dw 0
save_y:     dw 0
mode:       db 0
pending:    db 0
pend_ttl:   db 0
rep_left:   db 0
rep_dir:    db 0
busy:       db 0
req:        db 0
layer:      db 0
inside:     db 0
tab_req:    db 0
ui_mode:    db 0
ui_susp:    db 0
susp_other: db 0
to_view:    db 0
ui_ok:      db 0
ui_x:       dw 0
ui_y:       dw 0
is_ui:      db 0
win_ttl:    resb 16
btn_ttl:    db 0
grp_ttl:    resb 4
slot_ttl:   db 0
obj_ttl:    db 0
spr_ttl:    db 0
wm_ttl:     db 0
joy_ttl:    db 0
joy:        db 0
joy_raw:    db 0
slot_mode:  dw 0
spr_first:  dw 0
spr_last:   dw 0
spr_gfx:    dw 0
spr_rect:   dw 0, 0
spr_left:   dw 0
spr_top:    dw 0
spr_w:      dw 0
spr_h:      dw 0
spr_best:   dw 0
spr_hx:     dw 0
spr_hy:     dw 0
vp_x:       dw 0
vp_y:       dw 0
win_from:   resb 32
grp_off:    resb 8
grp_seg:    resb 8
g_off:      dw 0
g_seg:      dw 0
g_num:      dw 0
b_at:       dw 0
b_idx:      dw 0
cur_x:      dw 0
cur_y:      dw 0
org_x:      dw 0
org_y:      dw 0
lim_x:      dw 0
lim_y:      dw 0
cell_col:   dw 0
cell_row:   dw 0
wnum:       dw 0
half_x:     dw 0
half_y:     dw 0
best_score: dw 0
ntarg:      dw 0
targ:       resb 1024

; ---------------------------------------------------------------- VSYNC: keys -> buttons and requests

frame_stub:                     ; 0871:5142 jumps here (push ds / mov ax,DGROUP / mov ds,ax replaced)
    push ds
    mov ax, word ptr cs:[dgroup]
    mov ds, ax
    push bx
    push cx
    push dx
    push si
    push es
    call keys
    pop es
    pop si
    pop dx
    pop cx
    pop bx
    ljmp cs:[back_frame]

keys:
    inc word ptr cs:[frame]
    mov si, win_ttl
    mov cx, joy_ttl + 1 - win_ttl
k0:
    cmp byte ptr cs:[si], 0
    je k0n
    dec byte ptr cs:[si]
k0n:
    inc si
    loop k0
    call ui_live                ; the UI gone from the screen (a menu over it, another screen): UI mode ends and
    jne kl1                     ; where Tab left the pointer in the UI is forgotten
    mov byte ptr cs:[ui_mode], 0
    mov byte ptr cs:[ui_ok], 0
kl1:
    xor ax, ax
    mov es, ax
    test byte ptr es:[0x52c], 2     ; the stick (walking): W 11h, A 1Dh, S 1Eh, D 1Fh, and the pad's directions,
    je kw1                          ; as the arrows' bits: 1 up, 2 left, 4 right, 8 down
    or al, 1
kw1:
    test byte ptr es:[0x52d], 0x20
    je kw2
    or al, 2
kw2:
    test byte ptr es:[0x52d], 0x40
    je kw3
    or al, 8
kw3:
    test byte ptr es:[0x52d], 0x80
    je kw4
    or al, 4
kw4:
    xor cl, cl                  ; cl = the pad's directions alone (the dungeon walks with them: W A S D there
    cmp byte ptr cs:[joy_ttl], 0  ; are the game's own keys, tools/exekeys.py); the pad, as read by the frame
    je kw8                        ; wait (stale once that stops)
    mov ah, byte ptr cs:[joy]
    test ah, 1                  ; up
    je kw5
    or cl, 1
kw5:
    test ah, 4                  ; left
    je kw6
    or cl, 2
kw6:
    test ah, 8                  ; right
    je kw7
    or cl, 4
kw7:
    test ah, 2                  ; down
    je kw8
    or cl, 8
kw8:
    call free_keys
    mov ah, byte ptr cs:[jstick]
    mov byte ptr cs:[jstick], cl
    not ah
    and ah, cl
    or byte ptr cs:[jstick_new], ah
    or cl, cl
    jne kw8a
    mov byte ptr cs:[jstick_new], 0
kw8a:
    or al, cl
    mov ah, al                  ; a held key's repeat sends its break code before the make code again, so the
    or al, byte ptr cs:[st_h1]    ; key map can show it up for a moment: a key counts as held while it was down
    or al, byte ptr cs:[st_h2]    ; in any of the last three frames
    mov cl, byte ptr cs:[st_h1]
    mov byte ptr cs:[st_h2], cl
    mov byte ptr cs:[st_h1], ah
    mov byte ptr cs:[stick], al
kw9:
    cmp word ptr [0x78c6], 0x16  ; the world map's option mode ends with the world map
    je kw10
    mov byte ptr cs:[menu], 0
kw10:
    mov al, byte ptr es:[0x531]
    shr al, 2
    and al, 0x0f
    mov bl, al
    test byte ptr es:[0x52b], 0x80
    je k1
    or bl, 0x10
k1:
    test byte ptr es:[0x52d], 0x10  ; Return 1Ch
    je k1s
    or bl, 0x20
k1s:
    test byte ptr es:[0x530], 0x10  ; Space 34h: the left button as well
    je k2
    or bl, 0x20
k2:
    test byte ptr es:[0x52a], 1
    je k3
    or bl, 0x40
k3:
    test byte ptr es:[0x52b], 0x40
    je k4
    or bl, 0x40
k4:
    cmp byte ptr cs:[joy_ttl], 0
    je kj_end
    mov al, byte ptr cs:[joy]
    test al, 0x10               ; button 1 (A): the left button
    je kj5
    or bl, 0x20
kj5:
    test al, 0x20               ; button 2 (B): the right button
    je kj_end
    or bl, 0x40
kj_end:
    mov bh, bl                  ; held over the repeat's break code, as the stick
    or bl, byte ptr cs:[ky_h1]
    or bl, byte ptr cs:[ky_h2]
    mov cl, byte ptr cs:[ky_h1]
    mov byte ptr cs:[ky_h2], cl
    mov byte ptr cs:[ky_h1], bh
    call free_arrows
    mov al, byte ptr cs:[stick]  ; the world map walks with the stick, or with the arrows out of option mode
    or al, al
    jne kw_set
    cmp byte ptr cs:[menu], 0
    jne kw_set
    mov al, bl
    and al, 0x0f
kw_set:
    mov byte ptr cs:[walk], al
    mov bh, byte ptr cs:[keys_prev]
    mov byte ptr cs:[keys_prev], bl
    mov dl, bh
    not dl
    and dl, bl
    mov dh, bl
    not dh
    and dh, bh
    test dl, 0x20
    je k5
    mov word ptr [0x1ac], 1
k5:
    test dh, 0x20
    je k6
    mov word ptr [0x1ac], 0
k6:
    test dl, 0x40               ; the right button: on the world map's walking screen it waits HOLD frames -
    je kb1                      ; let go before that, it switches option mode; held, it is the right button
    cmp byte ptr cs:[wm_ttl], 0  ; (the minimap); in UI mode - or back in it, the menu it opened gone - it leaves
    je kb_now                    ; the UI instead (b_view)
    mov byte ptr cs:[b_cnt], 1
    jmp kb1
kb_now:
    call ui_resume
    cmp byte ptr cs:[ui_mode], 0
    je kb_right
    call b_view
    jmp kb1
kb_right:
    mov word ptr [0x1ae], 1
    mov byte ptr cs:[b_cnt], 0xff
kb1:
    test bl, 0x40
    je kb2
    mov al, byte ptr cs:[b_cnt]
    or al, al
    je kb2
    cmp al, 0xff
    je kb2
    inc al
    mov byte ptr cs:[b_cnt], al
    cmp al, HOLD
    jb kb2
    mov word ptr [0x1ae], 1
    mov byte ptr cs:[b_cnt], 0xff
kb2:
    test dh, 0x40
    je k8
    mov al, byte ptr cs:[b_cnt]
    mov byte ptr cs:[b_cnt], 0
    cmp al, 0xff
    jne kb_short
    mov word ptr [0x1ae], 0
    jmp k8
kb_short:
    or al, al
    je k8
    call menu_toggle
k8:
    test dl, 0x10
    je k9
    call tab_key
k9:
    mov al, bl
    and al, 0x0f
    cmp byte ptr cs:[wm_ttl], 0  ; walking on the world map: the arrows walk instead
    je k9a
    cmp byte ptr cs:[menu], 0
    jne k9a
    xor al, al
k9a:
    or al, al
    jne k10
    mov byte ptr cs:[rep_left], 0
    jmp k_ttl
k10:
    mov al, dl
    and al, 0x0f
    je k_held
    call dir_of
    mov byte ptr cs:[rep_dir], al
    mov byte ptr cs:[rep_left], FIRST
    call set_pending
    jmp k_ttl
k_held:
    cmp byte ptr cs:[rep_left], 0  ; held from before option mode: waits for a new press
    je k_ttl
    dec byte ptr cs:[rep_left]
    jne k_ttl
    mov byte ptr cs:[rep_left], NEXT
    mov al, byte ptr cs:[rep_dir]
    call set_pending
k_ttl:
    cmp byte ptr cs:[pend_ttl], 0
    je k_end
    dec byte ptr cs:[pend_ttl]
    jne k_end
    mov byte ptr cs:[pending], 0
    mov byte ptr cs:[tab_req], 0
k_end:
    ret

free_keys:                      ; cl = the pad's directions (es = 0). Y, which the emulator gives as Ctrl (74h: the
    push ax                     ; key map's byte 538h, bit 4), held: the stick's directions go to fm_dirs, for the
    push bx                     ; pointer (free_arrows), and cl comes back 0; the stick walks again only once it has
    mov al, byte ptr es:[0x538] ; been let go after Y. Held over the repeat's break code, as the stick
    and al, 0x10
    mov ah, al
    or al, byte ptr cs:[fm_h1]
    or al, byte ptr cs:[fm_h2]
    mov bl, byte ptr cs:[fm_h1]
    mov byte ptr cs:[fm_h2], bl
    mov byte ptr cs:[fm_h1], ah
    mov byte ptr cs:[fm_dirs], 0
    or al, al
    jne fk_free
    cmp byte ptr cs:[fm_block], 0
    je fk_end
    or cl, cl
    je fk_unblock
    xor cl, cl
    jmp fk_end
fk_unblock:
    mov byte ptr cs:[fm_block], 0
    jmp fk_end
fk_free:
    mov byte ptr cs:[fm_block], 1
    mov byte ptr cs:[fm_dirs], cl
    xor cl, cl
fk_end:
    pop bx
    pop ax
    ret

free_arrows:                    ; bl = the keys as held (es = 0; low nibble the arrows, as the stick's bits). Shift
    push ax                     ; (70h: the key map's byte 538h, bit 0) held: the arrows go to fm_dirs as well and
    push cx                     ; come back cleared - the keyboard's way to move the pointer freely (the user,
    mov al, byte ptr es:[0x538] ; 2026-10-13: 「那还是 Shift+方向键算了」); after Shift they pick targets again only
    and al, 1                   ; once let go. Then fm_dirs moves the pointer: FM_MIN pixels a frame, FM_MAX after
    mov ah, al                  ; FM_RAMP frames held, into fm_dx / fm_dy (at most FM_CAP gathered; free_apply
    or al, byte ptr cs:[sh_h1]  ; moves the pointer in the game's frame)
    or al, byte ptr cs:[sh_h2]
    mov cl, byte ptr cs:[sh_h1]
    mov byte ptr cs:[sh_h2], cl
    mov byte ptr cs:[sh_h1], ah
    or al, al
    je fr_noshift
    mov byte ptr cs:[arr_block], 1
    mov al, bl
    and al, 0x0f
    or byte ptr cs:[fm_dirs], al
    and bl, 0xf0
    jmp fr_move
fr_noshift:
    cmp byte ptr cs:[arr_block], 0
    je fr_move
    test bl, 0x0f
    je fr_unblock
    and bl, 0xf0
    jmp fr_move
fr_unblock:
    mov byte ptr cs:[arr_block], 0
fr_move:
    mov cl, byte ptr cs:[fm_dirs]
    or cl, cl
    jne fr_go
    mov byte ptr cs:[fm_run], 0
    pop cx
    pop ax
    ret
fr_go:
    push bx
    mov al, byte ptr cs:[fm_run]
    cmp al, FM_RAMP
    jae fr_fast
    inc byte ptr cs:[fm_run]
    mov bx, FM_MAX - FM_MIN
    mul bl                      ; ax = run x (MAX - MIN) / RAMP + MIN
    mov bl, FM_RAMP
    div bl
    add al, FM_MIN
    jmp fr_speed
fr_fast:
    mov al, FM_MAX
fr_speed:
    xor ah, ah
    mov bx, ax
    test cl, 1                  ; up
    je fr2
    sub word ptr cs:[fm_dy], bx
fr2:
    test cl, 8                  ; down
    je fr3
    add word ptr cs:[fm_dy], bx
fr3:
    test cl, 2                  ; left
    je fr4
    sub word ptr cs:[fm_dx], bx
fr4:
    test cl, 4                  ; right
    je fr5
    add word ptr cs:[fm_dx], bx
fr5:
    mov ax, word ptr cs:[fm_dx]
    call fm_cap
    mov word ptr cs:[fm_dx], ax
    mov ax, word ptr cs:[fm_dy]
    call fm_cap
    mov word ptr cs:[fm_dy], ax
    pop bx
    pop cx
    pop ax
    ret

fm_cap:                         ; ax within -FM_CAP .. FM_CAP
    cmp ax, FM_CAP
    jle fc1
    mov ax, FM_CAP
    ret
fc1:
    cmp ax, -FM_CAP
    jge fc2
    mov ax, -FM_CAP
fc2:
    ret

set_pending:                    ; a new request (al); it is not Tab's unless Tab says so after
    mov byte ptr cs:[pending], al
    mov byte ptr cs:[pend_ttl], TTL
    mov byte ptr cs:[tab_req], 0
    ret

menu_toggle:                    ; the world map's option mode: on, the pointer's place is kept and it goes to the
    cmp byte ptr cs:[menu], 0     ; nearest option; off, it goes back there (at the next pick, game context)
    jne mt_off
    mov byte ptr cs:[menu], 1
    mov ax, word ptr [0x1a8]
    mov word ptr cs:[save_x], ax
    mov ax, word ptr [0x1aa]
    mov word ptr cs:[save_y], ax
    mov byte ptr cs:[mode], 0
    mov al, 5
    jmp set_pending
mt_off:
    mov byte ptr cs:[menu], 0
    mov byte ptr cs:[pending], 0
    mov byte ptr cs:[tab_req], 0
    mov byte ptr cs:[restore], 1
    ret

tab_key:                        ; Tab: on the world map's walking screen the option mode, as a short B; elsewhere the
    cmp byte ptr cs:[wm_ttl], 0   ; UI (the command panel, the party list). In: the pointer's place in the view is
    je tk_ui                      ; kept, and it goes to where Tab last left the UI, or else to the nearest UI
    jmp menu_toggle               ; target (the request's service); out: the pointer's place in the UI is kept,
tk_ui:                            ; and it goes back to its place in the view (at the next hit test, game context)
    mov byte ptr cs:[ui_susp], 0
    cmp byte ptr cs:[ui_mode], 0
    jne tk_out
    mov ax, word ptr [0x1a8]
    mov word ptr cs:[save_x], ax
    mov ax, word ptr [0x1aa]
    mov word ptr cs:[save_y], ax
    mov byte ptr cs:[restore], 0
    mov byte ptr cs:[ui_mode], 1
    mov al, 5
    call set_pending
    mov byte ptr cs:[tab_req], 1
    ret
tk_out:
    mov ax, word ptr [0x1a8]
    mov word ptr cs:[ui_x], ax
    mov ax, word ptr [0x1aa]
    mov word ptr cs:[ui_y], ax
    mov byte ptr cs:[ui_ok], 1
    mov byte ptr cs:[ui_mode], 0
    mov byte ptr cs:[pending], 0
    mov byte ptr cs:[tab_req], 0
    mov byte ptr cs:[restore], 1
    ret

b_view:                         ; B in UI mode (the user, 2026-10-13: 「然后再次按 backspace，应该回到画面中间」):
    mov byte ptr cs:[ui_susp], 0  ; the UI is left as by Tab (its place kept), not clicked, and the pointer goes to
    call tk_out                   ; the middle of the view (free_apply, game context)
    mov byte ptr cs:[restore], 0
    mov byte ptr cs:[to_view], 1
    ret

view_up:                       ; something to pick came up in the view (a menu, a choice, a battle target): UI
    cmp byte ptr cs:[ui_mode], 0  ; mode ends there, the pointer staying where it is. From UI mode it is only put
    je vu1                        ; aside (the user, 2026-10-13: a DDS menu opened from the panel and left with BS
    push ax                       ; left the arrows dead): ui_susp = the layer that came up (1 menu, 2 scene),
    call live_layers              ; susp_other = what else of the view was live then; once nothing is live beyond
    mov al, byte ptr cs:[mode]    ; that, the next arrow goes on in the UI (choose)
    inc al
    mov byte ptr cs:[ui_susp], al
    not al
    and ah, al
    mov byte ptr cs:[susp_other], ah
    pop ax
vu1:
    mov byte ptr cs:[ui_mode], 0
    mov byte ptr cs:[tab_req], 0
    mov byte ptr cs:[restore], 0
    ret

ui_live:                        ; -> ZF clear when a part of the UI (the command panel group, the party list
    push ax                     ; window) was hit-tested within LIVE frames
    push bx
    xor bx, bx
ul1:
    cmp byte ptr cs:[win_ttl + bx], 0
    je ul2
    push bx
    shl bx, 1
    cmp word ptr cs:[win_from + bx], PARTY
    pop bx
    je ul_yes
ul2:
    inc bx
    cmp bx, 16
    jb ul1
    xor bx, bx
ul3:
    cmp byte ptr cs:[grp_ttl + bx], 0
    je ul4
    push bx
    shl bx, 1
    mov ax, PANEL
    call grp_is
    pop bx
    je ul_yes
ul4:
    inc bx
    cmp bx, 4
    jb ul3
    xor ax, ax
    jmp ul_end
ul_yes:
    mov ax, 1
    or ax, ax
ul_end:
    pop bx
    pop ax
    ret

grp_is:                         ; bx = 2 x a group's slot, ax = an offset in DGROUP -> ZF set when the group is
    cmp word ptr cs:[grp_off + bx], ax  ; DGROUP:ax
    jne gi_end
    push ax
    mov ax, word ptr cs:[dgroup]
    cmp word ptr cs:[grp_seg + bx], ax
    pop ax
gi_end:
    ret

dir_of:                         ; al = arrow bits (1 up, 2 left, 4 right, 8 down) -> al = 1..4 of the lowest
    mov ah, 1
do1:
    test al, 1
    jne do2
    shr al, 1
    inc ah
    jmp do1
do2:
    mov al, ah
    ret

; ---------------------------------------------------------------- the hit tests' entries (game context)

stub_cells:                     ; 25CA:348A jumps here: [sp] ip, cs, row ptr, col ptr, y, x, window
    push bp
    mov bp, sp
    push ax
    push bx
    mov bx, word ptr [bp + 0x12]
    cmp bx, 16
    jae sc_go
    cmp byte ptr cs:[win_ttl + bx], 0  ; a window of the view (not the party list) just came up
    jne sc_live
    cmp word ptr [bp + 2], PARTY
    je sc_live
    call menu_up
sc_live:
    mov byte ptr cs:[win_ttl + bx], LIVE
    shl bx, 1
    mov ax, word ptr [bp + 2]
    mov word ptr cs:[win_from + bx], ax
    call serve_menu
sc_go:
    pop bx
    pop ax
    pop bp
tramp_cells:
    enter 8, 0
    push di
    ljmp cs:[back_cells]

stub_btn:                       ; 1603:71C2 (near) jumps here
    push ax
    cmp byte ptr cs:[btn_ttl], 0
    jne sb_live
    call menu_up
sb_live:
    mov byte ptr cs:[btn_ttl], LIVE
    call serve_menu
    pop ax
    enter 0xa, 0
    push si
    ljmp cs:[back_btn]

stub_obj:                       ; 25CA:1980 jumps here: [sp] ip, cs, y, x
    push ax
    cmp byte ptr cs:[obj_ttl], 0  ; targets in the scene just came up (a battle target): the arrows go there
    jne so_live
    call scene_up
so_live:
    mov byte ptr cs:[obj_ttl], LIVE
    call serve_scene
    pop ax
tramp_obj:
    enter 0x24, 0
    push di
    ljmp cs:[back_obj]

stub_field:                     ; 358E:7764 jumps here: the field's click handler (the dungeon's and the rooms'),
    push ax                     ; which the map screen 358E:716E calls each frame while it waits (state 10h). The
    call field_objs             ; game hit-tests the field's objects (type 1 a person, 3 a chest)
    or ax, ax                   ; only on a click, so while any is in the object table they are the scene layer
    je sf_none                  ; from here (the user, 2026-10-13: 「对话对象和宝箱也要能够自动对准才行」), and a
    cmp byte ptr cs:[obj_ttl], 0  ; request for that layer is served here (DS = DGROUP)
    jne sf_live
    call scene_up
sf_live:
    mov byte ptr cs:[obj_ttl], LIVE
    call serve_scene
sf_none:
    pop ax
    enter 8, 0
    push si
    ljmp cs:[back_field]

field_objs:                     ; -> ax = 1 when the object table (DS:13F0 records of 1Eh bytes in segment DS:6174,
    push bx                     ; the type word first, negative when taken out) holds one of type 1 or 3, else 0
    push cx
    push es
    xor ax, ax
    mov cx, word ptr [0x13f0]
    or cx, cx
    jle fo_end
    mov es, word ptr [0x6174]
    xor bx, bx
fo1:
    cmp word ptr es:[bx], 1
    je fo_yes
    cmp word ptr es:[bx], 3
    je fo_yes
    add bx, 0x1e
    loop fo1
    jmp fo_end
fo_yes:
    mov ax, 1
fo_end:
    pop es
    pop cx
    pop bx
    ret

stub_grp:                       ; 25CA:561C jumps here: [sp] ip, cs, group offset, group segment
    push bp
    mov bp, sp
    push ax
    push bx
    push dx
    mov ax, word ptr [bp + 6]
    mov dx, word ptr [bp + 8]
    xor bx, bx
sg1:
    cmp byte ptr cs:[grp_ttl + bx], 0
    je sg2
    push bx
    shl bx, 1
    cmp word ptr cs:[grp_off + bx], ax
    jne sg1n
    cmp word ptr cs:[grp_seg + bx], dx
    jne sg1n
    pop bx
    jmp sg_set
sg1n:
    pop bx
sg2:
    inc bx
    cmp bx, 4
    jb sg1
    xor bx, bx                  ; not listed: the first slot that has run out
sg3:
    cmp byte ptr cs:[grp_ttl + bx], 0
    je sg_new
    inc bx
    cmp bx, 4
    jb sg3
    jmp sg_go
sg_new:
    push bx
    shl bx, 1
    mov word ptr cs:[grp_off + bx], ax
    mov word ptr cs:[grp_seg + bx], dx
    call grp_frame                ; a group of the view (not the command panel or the direction pad) came up
    pop bx
    je sg_set
    call menu_up
sg_set:
    mov byte ptr cs:[grp_ttl + bx], LIVE
    call serve_menu
sg_go:
    pop dx
    pop bx
    pop ax
    pop bp
    push bp
    mov bp, sp
    push si
    mov si, word ptr [bp + 6]
    ljmp cs:[back_grp]

stub_slots:                     ; 358E:A5B4 (the equipment screen's slot list, ov12) jumps here: [sp] ip, cs, mode
    push bp
    mov bp, sp
    push ax
    mov ax, word ptr [bp + 6]
    mov word ptr cs:[slot_mode], ax
    cmp byte ptr cs:[slot_ttl], 0
    jne sl_live
    call menu_up
sl_live:
    mov byte ptr cs:[slot_ttl], LIVE
    call serve_menu
    pop ax
    pop bp
    enter 2, 0
    push di
    ljmp cs:[back_slots]

stub_route:                     ; 358E:AA24 jumps here: [sp] ip, cs, result pointer (SS). The world map's
    cmp word ptr [0x78c6], 0x16   ; destination pick (ov45:01D6) asks it first for the next point of a
    jne sr_orig                   ; scripted route and walks there with no click; with no route running the
    cmp word ptr [0x394c], 0      ; walking screen is live, and the stick (or the arrows out of option mode)
    jne sr_orig                   ; gives it the next step of its own
    mov byte ptr cs:[wm_ttl], LIVE
    cmp byte ptr cs:[restore], 0
    je sr_walk
    call put_back
sr_walk:
    cmp byte ptr cs:[walk], 0
    je sr_orig
    push bp
    mov bp, sp
    push bx
    mov bx, word ptr [bp]         ; ov45:01D6's frame: its argument, the ground flag
    mov bx, word ptr ss:[bx + 6]
    mov word ptr cs:[wk_flag], bx
    call walk_target
    or ax, ax
    je sr_none
    mov bx, word ptr [bp + 6]
    mov ax, word ptr cs:[wk_tx]
    mov word ptr ss:[bx], ax
    mov ax, word ptr cs:[wk_ty]
    mov word ptr ss:[bx + 2], ax
    mov ax, bx
    mov dx, ss
    pop bx
    pop bp
    retf 2
sr_none:
    pop bx
    pop bp
sr_orig:
    enter 8, 0
    push si
    ljmp cs:[back_route]

put_back:                       ; option mode or the UI left: the pointer goes back where it was
    pusha
    push es
    mov byte ptr cs:[restore], 0
    mov cx, word ptr cs:[save_x]
    mov dx, word ptr cs:[save_y]
    mov word ptr [0x1a8], cx
    mov word ptr [0x1aa], dx
    mov ax, 4
    pushf
    lcall cs:[old33]
    pop es
    popa
    ret

menu_up:                        ; something of the view's menu layer came up: the arrows go there
    mov byte ptr cs:[mode], 0
    jmp view_up

scene_up:                       ; something of the scene layer came up: the arrows go there
    mov byte ptr cs:[mode], 1
    jmp view_up

serve_menu:                     ; in a menu-layer hit test (game context, DS = DGROUP): the pointer put back if
    cmp byte ptr cs:[restore], 0  ; Tab just left the UI, and a request served when the menu layer is in use
    je sm1
    call put_back
sm1:
    cmp byte ptr cs:[pending], 0
    je sm_end
    cmp byte ptr cs:[busy], 0
    jne sm_end
    call choose
    cmp al, 0
    jne sm_end
    call service
sm_end:
    ret

serve_scene:                    ; the same in a scene-layer hit test
    cmp byte ptr cs:[restore], 0
    je ss1
    call put_back
ss1:
    cmp byte ptr cs:[pending], 0
    je ss_end
    cmp byte ptr cs:[busy], 0
    jne ss_end
    call choose
    cmp al, 1
    jne ss_end
    call service
ss_end:
    ret

grp_frame:                      ; bx = 2 x a group's slot -> ZF set when it is the command panel or the direction pad
    push ax
    mov ax, PANEL
    call grp_is
    je gf_end
    mov ax, MOVES
    call grp_is
gf_end:
    pop ax
    ret

walk_target:                    ; [wk_flag] -> ax = 1 and wk_tx, wk_ty = a walkable point a step ahead
    push bx                     ; (walk: 1 up, 2 left, 4 right, 8 down; the roads are 1-2 pixel lines, so each distance
    push cx                     ; of wk_dists is tried at every side offset of wk_offs, each point through the
    push dx                     ; checks ov45 makes on a click: on the view, 06EA on the map, 076E ground
    push si                     ; whose [3906 + kind] is set)
    push di
    push es
    mov es, word ptr [0x6394]
    mov ax, word ptr es:[0x38ac]
    mov word ptr cs:[wk_px], ax
    mov es, word ptr [0x6396]
    mov ax, word ptr es:[0x38ae]
    mov word ptr cs:[wk_py], ax
    xor ax, ax
    xor cx, cx
    mov bl, byte ptr cs:[walk]
    test bl, 1
    je wd1
    mov cx, -1
    jmp wd4
wd1:
    test bl, 2
    je wd2
    mov ax, -1
    jmp wd4
wd2:
    test bl, 8
    je wd3
    mov cx, 1
    jmp wd4
wd3:
    mov ax, 1
wd4:
    mov word ptr cs:[wk_dx], ax
    mov word ptr cs:[wk_dy], cx
    mov si, wk_dists
wt1:
    mov bx, word ptr cs:[si]
    or bx, bx
    jne wt2
    jmp wt_none
wt2:
    mov di, wk_offs
wt2o:
    mov bx, word ptr cs:[si]
    mov ax, word ptr cs:[wk_dx]
    imul bx
    add ax, word ptr cs:[wk_px]
    mov word ptr cs:[wk_tx], ax
    mov ax, word ptr cs:[wk_dy]
    imul bx
    add ax, word ptr cs:[wk_py]
    mov word ptr cs:[wk_ty], ax
    mov bx, word ptr cs:[di]
    cmp word ptr cs:[wk_dx], 0
    je wt3
    add word ptr cs:[wk_ty], bx
    jmp wt4
wt3:
    add word ptr cs:[wk_tx], bx
    jmp wt4
wt_far:
    jmp wt_next
wt4:
    mov ax, word ptr cs:[wk_tx]
    sub ax, word ptr [0x9058]
    jl wt_far
    cmp ax, 368
    jge wt_far
    mov ax, word ptr cs:[wk_ty]
    sub ax, word ptr [0x905a]
    jl wt_far
    cmp ax, 200
    jge wt_far
    push word ptr cs:[wk_tx]
    push word ptr cs:[wk_ty]
    lcall cs:[f_valid]
    or ax, ax
    je wt_far
    push word ptr cs:[wk_flag]
    push word ptr cs:[wk_tx]
    push word ptr cs:[wk_ty]
    lcall cs:[f_ground]
    mov bl, al
    xor bh, bh
    cmp byte ptr [bx + 0x3906], 0
    je wt_far
    mov ax, 1
    jmp wt_end
wt_next:
    add di, 2
    cmp di, wk_offs_end
    jae wt_nextd
    jmp wt2o
wt_nextd:
    add si, 2
    jmp wt1
wt_none:
    xor ax, ax
wt_end:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

stub_wait:                      ; 0871:83AC (wait for the next VSYNC; every frame loop calls it, in the game's own
    push ax                     ; context) jumps here: the PC-98 joystick is read from the FM board's OPN(A),
    push dx                     ; register 0Eh through ports 188h/18Ah (active low: bits 0-3 up down left
    pushf                       ; right, 4-5 buttons 1 and 2; bits 6-7 are the board's timer flags; FFh with
    cli                         ; no board), with interrupts off so the music driver cannot move the register
                                ; latch in between
    push bx
    mov dx, 0x188               ; port B (register 0Fh) bit 6 picks the connector: 0 = the first, where the
    mov al, 0x0f                ; emulators put the host's pad; the sound driver's value is put back after
    out dx, al
    out 0x5f, al                ; the PC-98's 0.6 us wait
    mov dx, 0x18a
    in al, dx
    mov bl, al
    and al, 0xbf
    out dx, al
    out 0x5f, al
    mov dx, 0x188
    mov al, 0x0e
    out dx, al
    out 0x5f, al
    mov dx, 0x18a
    in al, dx
    mov bh, al
    mov byte ptr cs:[joy_raw], al
    mov dx, 0x188
    mov al, 0x0f
    out dx, al
    out 0x5f, al
    mov dx, 0x18a
    mov al, bl
    out dx, al
    mov al, bh
    pop bx
    popf
    not al
    and al, 0x3f
    mov byte ptr cs:[joy], al
    mov byte ptr cs:[joy_ttl], LIVE
    call free_apply
    pop dx
    pop ax
    enter 2, 0
    mov ax, word ptr [0x6da]
    ljmp cs:[back_wait]

free_apply:                     ; the game's frame (stub_wait, DS = DGROUP): the pointer moved by what the stick
    push ax                     ; with Y held or the arrows with Shift held gathered (free_keys, free_arrows), or
    push bx                     ; put in the middle of the view after B left the UI (b_view), kept on the screen,
    push cx                     ; through the mouse driver (INT 33h AX=4) - whose answer (AX=3) is the place, as
    push dx                     ; its own limits may be narrower - and the game's copy DS:1A8/1AA, as put_back does
    push es
    pushf
    cli
    mov cx, word ptr cs:[fm_dx]
    mov dx, word ptr cs:[fm_dy]
    mov word ptr cs:[fm_dx], 0
    mov word ptr cs:[fm_dy], 0
    mov al, byte ptr cs:[to_view]
    mov byte ptr cs:[to_view], 0
    popf
    or al, al
    je fa0
    mov cx, VIEW_X
    mov dx, VIEW_Y
    jmp fa4
fa0:
    mov ax, cx
    or ax, dx
    je fa_end
    add cx, word ptr [0x1a8]
    jge fa1
    xor cx, cx
fa1:
    cmp cx, SCREEN_W - 1
    jle fa2
    mov cx, SCREEN_W - 1
fa2:
    add dx, word ptr [0x1aa]
    jge fa3
    xor dx, dx
fa3:
    cmp dx, SCREEN_H - 1
    jle fa4
    mov dx, SCREEN_H - 1
fa4:
    mov ax, 4
    pushf
    lcall cs:[old33]
    mov ax, 3
    pushf
    lcall cs:[old33]
    mov word ptr [0x1a8], cx
    mov word ptr [0x1aa], dx
fa_end:
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    ret

stub_sprite:                    ; 1603:BC2B (script command 2D8/2D9: is the pointer on scene sprite first..last?)
    push bp                     ; calls here instead of its thunk to ov05:0BF0: [bp+6] y ptr, [bp+0Ah] x ptr,
    mov bp, sp                  ; [bp+0Eh] last, [bp+10h] first, [bp+12h] the button it wants
    push ax
    cmp byte ptr cs:[spr_ttl], 0  ; sprites to hit just came up (the 不動像 scene): the arrows go there
    jne sp_live
    call scene_up
sp_live:
    mov byte ptr cs:[spr_ttl], LIVE
    mov ax, word ptr [bp + 0x10]
    mov word ptr cs:[spr_first], ax
    mov ax, word ptr [bp + 0xe]
    mov word ptr cs:[spr_last], ax
    call serve_scene
    pop ax
    pop bp
    ljmp cs:[f_sprites]

stub_kbhit:                     ; 25CA:5957's far call to the run-time's kbhit, in 25CA:5956: the movement keys
    cmp byte ptr cs:[jstick], 0   ; '1'..'9' the dungeon reads when its movement buttons are not clicked
    je kh_real                    ; (table DS:17C0: 8 forward, 2 back, 7 / 9 turn, 4 / 6 sidestep, 5 about
    test byte ptr cs:[jstick_new], 0x0f  ; turn). The pad's stick gives '8' up, '7' left, '9' right, '5' down:
    jne kh_go                     ; at once when pushed, then again while held, STEP frames after the last -
    test byte ptr cs:[jstick], 7  ; but down, the about turn, once per push (held, it would turn back)
    je kh_real                    ; (the keyboard's W A S D, Q E, Z are the game's own, tools/exekeys.py)
    mov ax, word ptr cs:[frame]
    sub ax, word ptr cs:[step_at]
    cmp ax, STEP
    jb kh_real
kh_go:
    mov byte ptr cs:[jstick_new], 0
    mov ax, word ptr cs:[frame]
    mov word ptr cs:[step_at], ax
    mov al, byte ptr cs:[jstick]
    mov ah, 0x38
    test al, 1
    jne kh_d
    mov ah, 0x37
    test al, 2
    jne kh_d
    mov ah, 0x39
    test al, 4
    jne kh_d
    mov ah, 0x35
kh_d:
    mov byte ptr cs:[digit], ah
    mov ax, 1
    retf
kh_real:
    ljmp cs:[f_kbhit]

stub_getch:                     ; 25CA:5960's far call to the run-time's getch: the stick's digit first
    xor ax, ax
    xchg al, byte ptr cs:[digit]
    or al, al
    je gc_real
    retf
gc_real:
    ljmp cs:[f_getch]

live_layers:                    ; -> ah bit 0: the view's menu layer is live (a window but the party list, a
    push bx                     ; button list, a group but the command panel and the direction pad, the
    xor ah, ah                  ; equipment slots), bit 1: the scene layer (objects, sprites)
    xor bx, bx
ll1:
    cmp byte ptr cs:[win_ttl + bx], 0
    je ll2
    push bx
    shl bx, 1
    cmp word ptr cs:[win_from + bx], PARTY
    pop bx
    je ll2
    mov ah, 1
ll2:
    inc bx
    cmp bx, 16
    jb ll1
    cmp byte ptr cs:[btn_ttl], 0
    je ll3
    mov ah, 1
ll3:
    cmp byte ptr cs:[slot_ttl], 0
    je ll4
    mov ah, 1
ll4:
    xor bx, bx
ll5:
    cmp byte ptr cs:[grp_ttl + bx], 0
    je ll6
    push bx
    shl bx, 1
    call grp_frame
    pop bx
    je ll6
    mov ah, 1
ll6:
    inc bx
    cmp bx, 4
    jb ll5
    cmp byte ptr cs:[obj_ttl], 0
    jne ll7
    cmp byte ptr cs:[spr_ttl], 0
    je ll8
ll7:
    or ah, 2
ll8:
    pop bx
    ret

ui_resume:                      ; UI mode put aside by something of the view (view_up) comes back (ui_mode = 1) once
    push ax                     ; nothing is live beyond what was there before it came up, and the UI still is
    cmp byte ptr cs:[ui_susp], 0
    je ur_end
    call live_layers
    mov al, byte ptr cs:[susp_other]
    not al
    test ah, al
    jne ur_end
    mov byte ptr cs:[ui_susp], 0
    call ui_live
    je ur_end
    mov byte ptr cs:[ui_mode], 1
ur_end:
    pop ax
    ret

choose:                         ; -> al = the layer a request is served in: 0 menu, 1 scene, 0FFh none. In UI mode
    push bx                     ; (or the world map's option mode) the menu layer while the UI is live; else the
    mov al, byte ptr cs:[ui_mode]   ; view's: the one live, or with both the one that came up last
    or al, byte ptr cs:[menu]
    je ch_view
    call ui_live
    mov al, 0
    jne ch_end
    mov al, 0xff
    jmp ch_end
ch_view:
    call ui_resume
    cmp byte ptr cs:[ui_mode], 0
    je ch_v1
    mov al, 0
    jmp ch_end
ch_v1:
    call live_layers
ch_v2:
    mov al, 0xff
    cmp ah, 0
    je ch_end
    mov al, 0
    cmp ah, 1
    je ch_end
    mov al, 1
    cmp ah, 2
    je ch_end
    mov al, byte ptr cs:[mode]
ch_end:
    pop bx
    ret

; ---------------------------------------------------------------- serving a request

service:                        ; al = the layer; DS = DGROUP
    pusha
    push es
    mov byte ptr cs:[layer], al
    mov byte ptr cs:[busy], 1
    xor ah, ah
    xchg ah, byte ptr cs:[pending]
    mov byte ptr cs:[req], ah
    test ah, ah
    jne sv_go
    jmp sv_end
sv_go:
    inc word ptr cs:[services]
    mov word ptr cs:[ntarg], 0
    mov ax, word ptr [0x98f4]
    mov word ptr cs:[cur_x], ax
    mov ax, word ptr [0x98f6]
    mov word ptr cs:[cur_y], ax
    mov al, byte ptr cs:[ui_mode]  ; the UI's targets in UI mode (and the world map's option mode), else the view's
    or al, byte ptr cs:[menu]
    mov byte ptr cs:[is_ui], al
    cmp byte ptr cs:[tab_req], 0  ; Tab into the UI: back to where Tab last left it, else to the nearest UI target
    je sv_enum
    mov byte ptr cs:[tab_req], 0
    cmp byte ptr cs:[ui_ok], 0
    je sv_enum
    mov cx, word ptr cs:[ui_x]
    mov dx, word ptr cs:[ui_y]
    jmp sv_move
sv_enum:
    cmp byte ptr cs:[layer], 0
    jne sv_obj
    call enum_windows
    call enum_groups
    cmp byte ptr cs:[is_ui], 0
    jne sv_pick
    call enum_buttons
    call enum_slots
    jmp sv_pick
sv_obj:
    call enum_objects
    call enum_sprites
sv_pick:
    mov ax, word ptr cs:[ntarg]
    mov word ptr cs:[last_n], ax
    call pick
    test si, si
    je sv_end
    mov bx, si
    call point_of
    cmp byte ptr cs:[si + 1], 7    ; a scene sprite: the pixel found on it
    jne sv_obj3
    mov cx, word ptr cs:[si + 12]
    mov dx, word ptr cs:[si + 14]
    jmp sv_move
sv_obj3:
    cmp byte ptr cs:[si + 1], 3
    jne sv_move
    push cx
    push dx
    push cx
    push dx
    push cs
    call tramp_obj
    pop dx
    pop cx
    cmp ax, word ptr cs:[si + 2]
    je sv_move
    mov cx, word ptr cs:[si + 12]
    mov dx, word ptr cs:[si + 14]
sv_move:
    mov word ptr [0x1a8], cx
    mov word ptr [0x1aa], dx
    mov word ptr cs:[last_x], cx
    mov word ptr cs:[last_y], dx
    mov ax, 4
    pushf
    lcall cs:[old33]
sv_end:
    mov byte ptr cs:[busy], 0
    pop es
    popa
    ret

enum_windows:
    mov word ptr cs:[half_x], 4
    mov word ptr cs:[half_y], 4
    xor bx, bx
ew1:
    cmp byte ptr cs:[win_ttl + bx], 0
    je ew2
    push bx                     ; the party list in UI mode only, every other window out of it
    shl bx, 1
    xor al, al
    cmp word ptr cs:[win_from + bx], PARTY
    jne ew1u
    inc al
ew1u:
    pop bx
    cmp al, byte ptr cs:[is_ui]
    jne ew2
    push bx
    call enum_window
    pop bx
ew2:
    inc bx
    cmp bx, 16
    jb ew1
    ret

enum_window:                    ; bx = window: only one still open - it may have closed since its last hit test, and a
    mov word ptr cs:[wnum], bx  ; closed window's record holds no picture (25CA:1FB2) while its cells' handles may be
    call win_open               ; freed (the user, 2026-10-14: 「方向键用多了之后会报错」 - grp err, no use hnd req)
    je ewo
    ret
ewo:
    imul si, bx, 0x34
    add si, 0x6e30
    les di, ptr [si]
    mov ax, es
    or ax, di
    jne ewp
    ret
ewp:
    mov ax, word ptr es:[di]
    mov cx, word ptr [si + 4]
    call safe_rect
    jnc ewr0
    ret
ewr0:
    mov es, dx
    mov di, ax
    mov ax, word ptr es:[di]
    inc ax
    shl ax, 3
    mov word ptr cs:[org_x], ax
    mov ax, word ptr es:[di + 2]
    inc ax
    shl ax, 3
    mov word ptr cs:[org_y], ax
    mov ax, word ptr [si + 8]
    shl ax, 3
    add ax, word ptr cs:[org_x]
    mov word ptr cs:[lim_x], ax
    mov ax, word ptr [si + 0xa]
    shl ax, 3
    add ax, word ptr cs:[org_y]
    mov word ptr cs:[lim_y], ax
    mov dx, word ptr cs:[org_y]
    add dx, 4
ewr:
    cmp dx, word ptr cs:[lim_y]
    jge ew_end
    mov cx, word ptr cs:[org_x]
    add cx, 4
ewc:
    cmp cx, word ptr cs:[lim_x]
    jge ew_next
    push cx
    push dx
    push word ptr cs:[wnum]
    push cx
    push dx
    push cs
    push cell_col
    push cs
    push cell_row
    push cs
    call tramp_cells
    pop dx
    pop cx
    or ax, ax
    jl ew_skip
    call accept_cell
ew_skip:
    add cx, 8
    jmp ewc
ew_next:
    add dx, 8
    jmp ewr
ew_end:
    ret

accept_cell:                    ; ax = the run's first column, [cell_row]; cx, dx = the cell's centre: a target per run
    push si
    push di
    mov bx, word ptr cs:[cell_row]
    mov bh, bl
    mov bl, al
    mov di, bx
    mov si, word ptr cs:[wnum]
    or si, 0x100
    call add_target
    pop di
    pop si
    ret

win_open:                       ; bx = a window -> ZF set when it is open: in the game's list of open windows (DS:7170,
    push cx                     ; 16 words, FFFFh free; 25CA:21D7 puts a window in, its close 25CA:1FB2 takes it out)
    push si
    mov si, 0x7170
    mov cx, 16
wo1:
    cmp word ptr [si], bx
    je wo_end
    add si, 2
    loop wo1
    or cx, 1
wo_end:
    pop si
    pop cx
    ret

safe_rect:                      ; ax = a picture's VM handle, cx = a frame -> CF set when pic_ok refuses them, else
    call pic_ok                 ; dx:ax = 0871:B948's box record of the frame (registers as B948 leaves them)
    jc sr_ret
    push ax
    push cx
    lcall cs:[f_rect]
    clc
sr_ret:
    ret

pic_ok:                         ; ax = a picture's VM handle, cx = a frame -> CF clear when 0871:B948 may be asked for
    push ax                     ; them: the handle within the VM's table (1..1023: DS:[616A], 8 bytes each) and in use
    push bx                     ; (bit 0 of its first byte - 0871:97B4 stops the game on one that is not, "no use hnd
    push cx                     ; req"), and for a picture of frames (first word 0) the frame below their count
    push dx                     ; (0871:B9F0 prints "grp err, max cgen, req cgen" over the screen otherwise)
    push es
    or ax, ax
    je po_bad
    cmp ax, 1024
    jae po_bad
    mov bx, ax
    shl bx, 3
    mov es, word ptr [0x616a]
    test byte ptr es:[bx], 1
    je po_bad
    push cx                     ; the frame, kept over the lock
    push ax
    lcall cs:[f_lock]           ; 0871:9326 -> dx:ax the picture's data
    pop cx
    mov es, dx
    mov bx, ax
    cmp word ptr es:[bx], 0
    jne po_good
    cmp cx, word ptr es:[bx + 2]
    jae po_bad
po_good:
    clc
    jmp po_end
po_bad:
    stc
po_end:
    pop es
    pop dx
    pop cx
    pop bx
    pop ax
    ret

enum_buttons:
    cmp byte ptr cs:[btn_ttl], 0
    jne eb0
    ret
eb0:
    mov bx, word ptr [0x1bc2]   ; the list's window, if still open (enum_window)
    call win_open
    je eb0o
    ret
eb0o:
    imul si, bx, 0x34
    add si, 0x6e30
    les di, ptr [si]
    mov ax, es
    or ax, di
    jne eb0p
    ret
eb0p:
    mov ax, word ptr es:[di]
    mov cx, word ptr [si + 4]
    call safe_rect
    jnc eb0r
    ret
eb0r:
    mov es, dx
    mov di, ax
    mov ax, word ptr es:[di]
    inc ax
    shl ax, 3
    mov word ptr cs:[org_x], ax
    mov ax, word ptr es:[di + 2]
    inc ax
    shl ax, 3
    mov word ptr cs:[org_y], ax
    mov word ptr cs:[half_y], 8
    les bx, ptr [0x1bce]
    xor di, di
eb1:
    mov ax, es
    or ax, bx
    je eb_end
    cmp di, MAXT                ; a list no longer there cannot run the walk on for ever
    jae eb_end
    test byte ptr es:[bx + 0xc], 1
    jne eb2
    mov ax, word ptr es:[bx + 8]
    shl ax, 2
    mov word ptr cs:[half_x], ax
    mov cx, word ptr es:[bx + 4]
    shl cx, 3
    add cx, word ptr cs:[org_x]
    add cx, ax
    mov dx, word ptr es:[bx + 6]
    shl dx, 3
    add dx, word ptr cs:[org_y]
    add dx, 8
    mov si, 0x200
    call add_target
eb2:
    inc di
    les bx, ptr es:[bx]
    jmp eb1
eb_end:
    ret

enum_groups:                    ; only a group hit-tested in the last few frames: some are a function's locals on the
    xor bx, bx                  ; stack (a battle's at DS:BE9A) and turn to garbage as soon as it returns
eg1:
    cmp byte ptr cs:[grp_ttl + bx], LIVE - 2
    jb eg2
    push bx
    mov word ptr cs:[g_num], bx
    shl bx, 1
    mov ax, MOVES               ; the direction pad never (the stick and the keys walk); the command panel in UI
    call grp_is                 ; mode only, every other group out of it
    je eg_skip
    xor cl, cl
    mov ax, PANEL
    call grp_is
    jne eg1u
    inc cl
eg1u:
    cmp cl, byte ptr cs:[is_ui]
    jne eg_skip
    mov ax, word ptr cs:[grp_off + bx]
    mov word ptr cs:[g_off], ax
    mov ax, word ptr cs:[grp_seg + bx]
    mov word ptr cs:[g_seg], ax
    call enum_group
eg_skip:
    pop bx
eg2:
    inc bx
    cmp bx, 4
    jb eg1
    ret

enum_group:                     ; [g_seg]:[g_off] = a button group (25CA:561C): +1 flags, +2 x (cells), +4 y,
    les di, ptr cs:[g_off]      ; +6 buttons, +8 its pictures, +14h the buttons (10 bytes: +1 flags, +2 picture)
    test byte ptr es:[di + 1], 0x98
    je egr00
    ret
egr00:
    cmp word ptr es:[di + 6], MAXT  ; a group freed since its last hit test may hold anything: no more buttons than
    jbe egr0                        ; targets, and each picture checked (safe_rect)
    ret
egr0:
    mov word ptr cs:[b_idx], 0
    lea ax, [di + 0x14]
    mov word ptr cs:[b_at], ax
egr1:
    les di, ptr cs:[g_off]
    mov ax, word ptr cs:[b_idx]
    cmp ax, word ptr es:[di + 6]
    jl egr2
    ret
egr2:
    mov si, word ptr cs:[b_at]
    test byte ptr es:[si + 1], 0x98
    jne egr_skip
    mov ax, word ptr es:[si + 2]   ; the picture it shows: 2 x its number, + 1 while held (25CA:5116)
    shl ax, 1
    mov dl, byte ptr es:[si]
    and dx, 1
    add ax, dx
    mov cx, ax
    les bx, ptr es:[di + 8]
    mov ax, es
    or ax, bx
    je egr_skip
    mov ax, word ptr es:[bx]
    call safe_rect              ; the picture's box in 8-pixel units: x, y, width, height
    jnc egr_box
egr_skip:
    jmp egr_next
egr_box:
    mov es, dx
    mov bx, ax
    les di, ptr cs:[g_off]
    mov ax, word ptr es:[di + 2]
    shl ax, 3
    mov word ptr cs:[org_x], ax
    mov ax, word ptr es:[di + 4]
    mov word ptr cs:[org_y], ax
    mov es, dx
    mov ax, word ptr es:[bx + 4]
    shl ax, 2
    mov word ptr cs:[half_x], ax
    mov cx, word ptr es:[bx]
    shl cx, 3
    add cx, word ptr cs:[org_x]
    add cx, ax
    mov ax, word ptr es:[bx + 6]
    shl ax, 2
    mov word ptr cs:[half_y], ax
    mov dx, word ptr es:[bx + 2]
    shl dx, 3
    add dx, word ptr cs:[org_y]
    add dx, ax
    mov si, word ptr cs:[g_num]
    or si, 0x400
    mov di, word ptr cs:[b_idx]
    call add_target
egr_next:
    add word ptr cs:[b_at], 10
    inc word ptr cs:[b_idx]
    jmp egr1

enum_slots:                     ; 358E:A5B4's 8 slots: columns 34h-48h, rows 7+3k and 8+3k (mode 1: not 1, 2, 7)
    cmp byte ptr cs:[slot_ttl], 0
    jne es0
    ret
es0:
    mov word ptr cs:[half_x], 84
    mov word ptr cs:[half_y], 8
    xor di, di
es1:
    cmp word ptr cs:[slot_mode], 1
    jne es2
    cmp di, 1
    je es_next
    cmp di, 2
    je es_next
    cmp di, 7
    je es_next
es2:
    mov cx, 500
    imul dx, di, 24
    add dx, 64
    mov si, 0x500
    call add_target
es_next:
    inc di
    cmp di, 8
    jb es1
    ret

enum_sprites:                   ; the scene sprites first..last of the last 2D8/2D9 as ov05:0BF0 places them:
    cmp byte ptr cs:[spr_ttl], 0  ; [30ECh + 2i] set, picture set byte [88F4h + 2i] -> far [306Ch + 4 set],
    jne ep_go                   ; picture byte [88F5h + 2i] -> 0871:B948 box x y w h, position [8934h + 4i]
    ret                         ; through 0871:AEA8 (as the objects), in the view whose origin 25CA:16C4
ep_go:                          ; gives; the point to click is the pixel 0871:AF18 finds on a 4-pixel grid
    push 320                    ; nearest the box's centre
    push 130
    push cs
    push vp_x
    push cs
    push vp_y
    lcall cs:[f_view]
    or ax, ax
    jge ep_view
    ret
ep_view:
    mov ax, 320
    sub ax, word ptr cs:[vp_x]
    mov word ptr cs:[org_x], ax
    mov ax, 130
    sub ax, word ptr cs:[vp_y]
    mov word ptr cs:[org_y], ax
    mov di, word ptr cs:[spr_first]
ep_one:
    cmp di, word ptr cs:[spr_last]
    jle ep_in
    ret
ep_in:
    cmp di, 31
    ja ep_skip
    mov si, di
    shl si, 1
    cmp word ptr [si + 0x30ec], 0
    je ep_skip
    mov bl, byte ptr [si + 0x88f4]
    xor bh, bh
    shl bx, 2
    les bx, ptr [bx + 0x306c]
    mov ax, es
    or ax, bx
    je ep_skip
    mov ax, word ptr es:[bx + 4]
    mov word ptr cs:[spr_gfx], ax
    mov cl, byte ptr [si + 0x88f5]
    xor ch, ch
    mov ax, word ptr es:[bx]
    call safe_rect
    jc ep_skip
    mov word ptr cs:[spr_rect], ax
    mov word ptr cs:[spr_rect + 2], dx
    call sprite_box
    jmp ep_next
ep_skip:
ep_next:
    inc di
    jmp ep_one

sprite_box:                     ; di = the sprite, [spr_rect] its box record -> a target with its click point
    push di
    mov si, di
    shl si, 2
    les bx, ptr cs:[spr_rect]
    push 0x28
    push word ptr [si + 0x8934]
    push word ptr es:[bx]
    push word ptr es:[bx + 4]
    push 0
    lcall cs:[f_proj]
    shl ax, 3
    mov word ptr cs:[spr_left], ax
    les bx, ptr cs:[spr_rect]
    push 0x70
    push word ptr [si + 0x8936]
    mov ax, word ptr es:[bx + 2]
    shl ax, 3
    push ax
    mov ax, word ptr es:[bx + 6]
    shl ax, 3
    push ax
    push 0
    lcall cs:[f_proj]
    mov word ptr cs:[spr_top], ax
    les bx, ptr cs:[spr_rect]
    mov ax, word ptr es:[bx + 4]
    shl ax, 3
    mov word ptr cs:[spr_w], ax
    mov ax, word ptr es:[bx + 6]
    shl ax, 3
    mov word ptr cs:[spr_h], ax
    mov word ptr cs:[spr_best], 0x7fff
    mov dx, 2
sb_row:
    cmp dx, word ptr cs:[spr_h]
    jge sb_done
    mov cx, 2
sb_col:
    cmp cx, word ptr cs:[spr_w]
    jge sb_nextrow
    push cx
    push dx
    push word ptr cs:[spr_gfx]
    push word ptr cs:[spr_rect + 2]
    push word ptr cs:[spr_rect]
    push cx
    push dx
    push 0
    lcall cs:[f_pix]
    pop dx
    pop cx
    or ax, ax
    jle sb_nextcol
    mov ax, word ptr cs:[spr_w]
    shr ax, 1
    sub ax, cx
    jge sb_a1
    neg ax
sb_a1:
    mov bx, word ptr cs:[spr_h]
    shr bx, 1
    sub bx, dx
    jge sb_a2
    neg bx
sb_a2:
    add ax, bx
    cmp ax, word ptr cs:[spr_best]
    jge sb_nextcol
    mov word ptr cs:[spr_best], ax
    mov word ptr cs:[spr_hx], cx
    mov word ptr cs:[spr_hy], dx
sb_nextcol:
    add cx, 4
    jmp sb_col
sb_nextrow:
    add dx, 4
    jmp sb_row
sb_done:
    pop di
    cmp word ptr cs:[spr_best], 0x7fff
    je sb_end
    mov ax, word ptr cs:[spr_w]
    shr ax, 1
    mov word ptr cs:[half_x], ax
    mov cx, word ptr cs:[org_x]
    add cx, word ptr cs:[spr_left]
    add cx, ax
    mov ax, word ptr cs:[spr_h]
    shr ax, 1
    mov word ptr cs:[half_y], ax
    mov dx, word ptr cs:[org_y]
    add dx, word ptr cs:[spr_top]
    add dx, ax
    mov si, 0x700
    push di
    call add_target
    pop di
    mov bx, word ptr cs:[ntarg]  ; the click point goes in its sample (it is the last one listed)
    dec bx
    shl bx, 4
    add bx, targ
    mov ax, word ptr cs:[org_x]
    add ax, word ptr cs:[spr_left]
    add ax, word ptr cs:[spr_hx]
    mov word ptr cs:[bx + 12], ax
    mov ax, word ptr cs:[org_y]
    add ax, word ptr cs:[spr_top]
    add ax, word ptr cs:[spr_hy]
    mov word ptr cs:[bx + 14], ax
sb_end:
    ret

enum_objects:
    mov word ptr cs:[half_x], 8
    mov word ptr cs:[half_y], 8
    mov dx, 8
eor:
    cmp dx, 400
    jge eo_end
    mov cx, 8
eoc:
    cmp cx, 640
    jge eo_next
    push cx
    push dx
    push cx
    push dx
    push cs
    call tramp_obj
    pop dx
    pop cx
    or ax, ax
    jl eo_skip
    mov di, ax
    push ax
    lcall cs:[f_type]
    cmp ax, 1                   ; 2 a battle's target, 1 and 3 the field's (a person, a chest)
    jl eo_skip
    cmp ax, 3
    jg eo_skip
    mov si, 0x300
    call add_target
eo_skip:
    add cx, 16
    jmp eoc
eo_next:
    add dx, 16
    jmp eor
eo_end:
    ret

add_target:                     ; si, di = the target's two id words; cx, dx = a point of it; half_x, half_y
    push ax
    push bx
    push bp
    mov bx, targ
    mov bp, word ptr cs:[ntarg]
at1:
    or bp, bp
    je at_new
    cmp word ptr cs:[bx], si
    jne at2
    cmp word ptr cs:[bx + 2], di
    je at_grow
at2:
    add bx, 16
    dec bp
    jmp at1
at_new:
    cmp word ptr cs:[ntarg], MAXT
    jb at_room
    jmp at_end
at_room:
    inc word ptr cs:[ntarg]
    mov word ptr cs:[bx], si
    mov word ptr cs:[bx + 2], di
    mov word ptr cs:[bx + 12], cx
    mov word ptr cs:[bx + 14], dx
    mov ax, cx
    sub ax, word ptr cs:[half_x]
    mov word ptr cs:[bx + 4], ax
    mov ax, cx
    add ax, word ptr cs:[half_x]
    dec ax
    mov word ptr cs:[bx + 8], ax
    mov ax, dx
    sub ax, word ptr cs:[half_y]
    mov word ptr cs:[bx + 6], ax
    mov ax, dx
    add ax, word ptr cs:[half_y]
    dec ax
    mov word ptr cs:[bx + 10], ax
    jmp at_end
at_grow:
    mov ax, cx
    sub ax, word ptr cs:[half_x]
    cmp ax, word ptr cs:[bx + 4]
    jge ag1
    mov word ptr cs:[bx + 4], ax
ag1:
    mov ax, cx
    add ax, word ptr cs:[half_x]
    dec ax
    cmp ax, word ptr cs:[bx + 8]
    jle ag2
    mov word ptr cs:[bx + 8], ax
ag2:
    mov ax, dx
    sub ax, word ptr cs:[half_y]
    cmp ax, word ptr cs:[bx + 6]
    jge ag3
    mov word ptr cs:[bx + 6], ax
ag3:
    mov ax, dx
    add ax, word ptr cs:[half_y]
    dec ax
    cmp ax, word ptr cs:[bx + 10]
    jle at_end
    mov word ptr cs:[bx + 10], ax
at_end:
    pop bp
    pop bx
    pop ax
    ret

pick:                           ; -> si = the target to go to, or 0
    mov bx, targ                ; a pointer on none of them goes to the nearest one, whatever the way
    mov cx, word ptr cs:[ntarg]
pi1:
    jcxz pi2
    call contains
    je pi3
    add bx, 16
    dec cx
    jmp pi1
pi2:
    mov byte ptr cs:[req], 5
pi3:
    xor si, si
    mov word ptr cs:[best_score], 0x7fff
    mov byte ptr cs:[inside], 0
    mov bx, targ
    mov cx, word ptr cs:[ntarg]
pk1:
    jcxz pk2
    call score_one
    cmp ax, word ptr cs:[best_score]
    jge pk3
    mov word ptr cs:[best_score], ax
    mov si, bx
pk3:
    add bx, 16
    dec cx
    jmp pk1
pk2:
    or si, si                   ; nothing that way: the arrows wrap round, to the target at the far end the other
    jne pk_end                  ; way, in the pointer's column (up / down) or row (left / right) - STATUS, Down,
    cmp byte ptr cs:[req], 5    ; FIGHT; a list's last row, Down, its first
    jae pk_end
    mov bx, targ
    mov cx, word ptr cs:[ntarg]
pw1:
    jcxz pk_end
    call contains
    je pw_next
    call wrap_score
    cmp ax, word ptr cs:[best_score]
    jge pw_next
    mov word ptr cs:[best_score], ax
    mov si, bx
pw_next:
    add bx, 16
    dec cx
    jmp pw1
pk_end:
    ret

wrap_score:                     ; bx = a target -> ax: how far it is from the pointer's column (row), x 4, then from
    push cx                     ; the far end the other way
    push dx
    call point_of
    mov al, byte ptr cs:[req]
    cmp al, 4
    je ws_down
    cmp al, 1
    je ws_up
    cmp al, 3
    je ws_right
    call orth_y                 ; left: the rightmost
    shl ax, 2
    add ax, 1000
    sub ax, cx
    jmp ws_end
ws_right:                       ; right: the leftmost
    call orth_y
    shl ax, 2
    add ax, cx
    jmp ws_end
ws_up:                          ; up: the lowest
    call orth_x
    shl ax, 2
    add ax, 1000
    sub ax, dx
    jmp ws_end
ws_down:                        ; down: the highest
    call orth_x
    shl ax, 2
    add ax, dx
ws_end:
    pop dx
    pop cx
    ret

contains:                       ; bx = a target -> ZF set when the pointer is in its box
    push ax
    mov ax, word ptr cs:[cur_x]
    cmp ax, word ptr cs:[bx + 4]
    jl ct_no
    cmp ax, word ptr cs:[bx + 8]
    jg ct_no
    mov ax, word ptr cs:[cur_y]
    cmp ax, word ptr cs:[bx + 6]
    jl ct_no
    cmp ax, word ptr cs:[bx + 10]
    jg ct_no
    xor ax, ax
    pop ax
    ret
ct_no:
    or ax, 1
    pop ax
    ret

score_one:                      ; bx = a target -> ax = its score, 7FFFh = not that way
    push cx
    push dx
    call point_of
    mov ax, word ptr cs:[cur_x]
    cmp ax, word ptr cs:[bx + 4]
    jl so_out
    cmp ax, word ptr cs:[bx + 8]
    jg so_out
    mov ax, word ptr cs:[cur_y]
    cmp ax, word ptr cs:[bx + 6]
    jl so_out
    cmp ax, word ptr cs:[bx + 10]
    jg so_out
    mov byte ptr cs:[inside], 1
    xor ax, ax
    cmp byte ptr cs:[req], 5
    je so_end
    jmp so_none
so_out:
    sub cx, word ptr cs:[cur_x]
    sub dx, word ptr cs:[cur_y]
    mov al, byte ptr cs:[req]
    cmp al, 5
    je so_near
    cmp al, 1
    je so_up
    cmp al, 4
    je so_down
    cmp al, 2
    je so_left
    mov ax, cx
    jmp so_horz
so_left:
    mov ax, cx
    neg ax
so_horz:
    cmp ax, 4
    jle so_none
    push ax
    call orth_y
    shl ax, 1
    pop cx
    add ax, cx
    jmp so_end
so_up:
    mov ax, dx
    neg ax
    jmp so_vert
so_down:
    mov ax, dx
so_vert:
    cmp ax, 4
    jle so_none
    push ax
    call orth_x
    shl ax, 1
    pop cx
    add ax, cx
    jmp so_end
so_near:
    mov ax, cx
    or ax, ax
    jge sn1
    neg ax
sn1:
    or dx, dx
    jge sn2
    neg dx
sn2:
    add ax, dx
    jmp so_end
so_none:
    mov ax, 0x7fff
so_end:
    pop dx
    pop cx
    ret

orth_x:                         ; bx = a target -> ax = how far the pointer is left or right of its box
    mov ax, word ptr cs:[cur_x]
    cmp ax, word ptr cs:[bx + 4]
    jge ox1
    sub ax, word ptr cs:[bx + 4]
    neg ax
    ret
ox1:
    cmp ax, word ptr cs:[bx + 8]
    jle ox2
    sub ax, word ptr cs:[bx + 8]
    ret
ox2:
    xor ax, ax
    ret

orth_y:
    mov ax, word ptr cs:[cur_y]
    cmp ax, word ptr cs:[bx + 6]
    jge oy1
    sub ax, word ptr cs:[bx + 6]
    neg ax
    ret
oy1:
    cmp ax, word ptr cs:[bx + 10]
    jle oy2
    sub ax, word ptr cs:[bx + 10]
    ret
oy2:
    xor ax, ax
    ret

point_of:                       ; bx = a target -> cx, dx = the centre of its box
    mov cx, word ptr cs:[bx + 4]
    add cx, word ptr cs:[bx + 8]
    inc cx
    sar cx, 1
    mov dx, word ptr cs:[bx + 6]
    add dx, word ptr cs:[bx + 10]
    inc dx
    sar dx, 1
    ret

; ---------------------------------------------------------------- INT 33h: hooking the game

int33:
    cmp ax, 0x0c
    jne i_pass
    cmp dx, 0x52b6
    jne i_pass
    call hook_game
i_pass:
    ljmp cs:[old33]

hook_game:                      ; es = the runtime segment of the game's 0871
    pushf
    pusha
    push ds
    push es
    mov bp, es
    sub bp, 0x0871
    mov ax, bp
    add ax, 0x0871
    mov ds, ax
    cmp word ptr [0x5142], 0xb81e
    jne hg_fail
    mov ax, bp
    add ax, 0x48fc
    cmp word ptr [0x5144], ax
    jne hg_fail
    cmp word ptr [0x5146], 0xd88e
    jne hg_fail
    cmp word ptr [0x83ac], 0x02c8
    jne hg_fail
    cmp word ptr [0x83ae], 0
    jne hg_fail
    cmp word ptr [0x83b0], 0xdaa1
    jne hg_fail
    cmp byte ptr [0x83b2], 0x06
    jne hg_fail
    mov word ptr cs:[dgroup], ax
    mov ax, bp
    add ax, 0x25ca
    mov ds, ax
    cmp word ptr [0x348a], 0x08c8
    jne hg_fail
    cmp word ptr [0x348c], 0
    jne hg_fail
    cmp byte ptr [0x348e], 0x57
    je hg_c2
hg_fail:
    jmp hg_end
hg_c2:
    cmp word ptr [0x1980], 0x24c8
    jne hg_fail
    cmp word ptr [0x1982], 0
    jne hg_fail
    cmp byte ptr [0x1984], 0x57
    jne hg_fail
    cmp word ptr [0x561c], 0x8b55
    jne hg_fail
    cmp word ptr [0x561e], 0x56ec
    jne hg_fail
    cmp word ptr [0x5620], 0x768b
    jne hg_fail
    cmp byte ptr [0x5957], 0x9a
    jne hg_fail
    cmp word ptr [0x5958], 0x0d80
    jne hg_fail
    cmp word ptr [0x595a], bp
    jne hg_fail
    cmp byte ptr [0x5960], 0x9a
    jne hg_fail2
    cmp word ptr [0x5961], 0x0da6
    jne hg_fail2
    cmp word ptr [0x5963], bp
    jne hg_fail2
    cmp byte ptr [0x5622], 0x06
    je hg_c3
hg_fail2:
    jmp hg_end
hg_c3:
    mov ax, bp
    add ax, 0x1603
    mov ds, ax
    cmp word ptr [0x71c2], 0x0ac8
    jne hg_fail2
    cmp word ptr [0x71c4], 0
    jne hg_fail2
    cmp byte ptr [0x71c6], 0x56
    jne hg_fail2
    cmp byte ptr [0xbc2b], 0x9a
    jne hg_fail2
    cmp word ptr [0xbc2c], 0x01f8
    jne hg_fail2
    mov ax, bp
    add ax, 0x07b1
    cmp word ptr [0xbc2e], ax
    jne hg_fail2
    mov ax, bp
    add ax, 0x358e
    mov ds, ax
    cmp word ptr [0xa5b4], 0x02c8
    jne hg_end
    cmp word ptr [0xa5b6], 0
    jne hg_end
    cmp byte ptr [0xa5b8], 0x57
    jne hg_end
    cmp word ptr [0xaa24], 0x08c8
    jne hg_end
    cmp word ptr [0xaa26], 0
    jne hg_end
    cmp byte ptr [0xaa28], 0x56
    jne hg_end
    cmp word ptr [0x7764], 0x08c8
    jne hg_end
    cmp word ptr [0x7766], 0
    jne hg_end
    cmp byte ptr [0x7768], 0x56
    je hg_ok
hg_end:
    pop es
    pop ds
    popa
    popf
    ret
hg_ok:
    mov word ptr cs:[f_kbhit + 2], bp
    mov word ptr cs:[f_getch + 2], bp
    mov ax, bp
    add ax, 0x0871
    mov word ptr cs:[back_frame + 2], ax
    mov word ptr cs:[back_wait + 2], ax
    mov word ptr cs:[f_rect + 2], ax
    mov word ptr cs:[f_lock + 2], ax
    mov word ptr cs:[f_proj + 2], ax
    mov word ptr cs:[f_pix + 2], ax
    mov ax, bp
    add ax, 0x07b1
    mov word ptr cs:[f_valid + 2], ax
    mov word ptr cs:[f_ground + 2], ax
    mov word ptr cs:[f_sprites + 2], ax
    mov ax, bp
    add ax, 0x25ca
    mov word ptr cs:[back_cells + 2], ax
    mov word ptr cs:[back_obj + 2], ax
    mov word ptr cs:[back_grp + 2], ax
    mov word ptr cs:[f_type + 2], ax
    mov word ptr cs:[f_view + 2], ax
    mov ax, bp
    add ax, 0x1603
    mov word ptr cs:[back_btn + 2], ax
    mov ax, bp
    add ax, 0x358e
    mov word ptr cs:[back_slots + 2], ax
    mov word ptr cs:[back_route + 2], ax
    mov word ptr cs:[back_field + 2], ax
    push cs
    pop es
    mov di, keys_prev
    mov cx, grp_seg + 8 - keys_prev
    xor al, al
    cld
    rep stosb
    inc word ptr cs:[hooks]
    mov dx, cs
    cli
    mov ax, bp
    add ax, 0x0871
    mov ds, ax
    mov byte ptr [0x5142], 0xea
    mov word ptr [0x5143], frame_stub
    mov word ptr [0x5145], dx
    mov byte ptr [0x5147], 0x90
    mov byte ptr [0x83ac], 0xea
    mov word ptr [0x83ad], stub_wait
    mov word ptr [0x83af], dx
    mov ax, bp
    add ax, 0x25ca
    mov ds, ax
    mov byte ptr [0x348a], 0xea
    mov word ptr [0x348b], stub_cells
    mov word ptr [0x348d], dx
    mov byte ptr [0x1980], 0xea
    mov word ptr [0x1981], stub_obj
    mov word ptr [0x1983], dx
    mov byte ptr [0x561c], 0xea
    mov word ptr [0x561d], stub_grp
    mov word ptr [0x561f], dx
    mov word ptr [0x5958], stub_kbhit
    mov word ptr [0x595a], dx
    mov word ptr [0x5961], stub_getch
    mov word ptr [0x5963], dx
    mov ax, bp
    add ax, 0x1603
    mov ds, ax
    mov byte ptr [0x71c2], 0xea
    mov word ptr [0x71c3], stub_btn
    mov word ptr [0x71c5], dx
    mov word ptr [0xbc2c], stub_sprite
    mov word ptr [0xbc2e], dx
    mov ax, bp
    add ax, 0x358e
    mov ds, ax
    mov byte ptr [0xa5b4], 0xea
    mov word ptr [0xa5b5], stub_slots
    mov word ptr [0xa5b7], dx
    mov byte ptr [0xaa24], 0xea
    mov word ptr [0xaa25], stub_route
    mov word ptr [0xaa27], dx
    mov byte ptr [0x7764], 0xea
    mov word ptr [0x7765], stub_field
    mov word ptr [0x7767], dx
    jmp hg_end

; ---------------------------------------------------------------- the launcher: DDS98.COM runs DDS98.EXE

install:                        ; DOS runs DDS98.COM for the command DDS98 (a .COM before an .EXE of the name)
    mov ax, cs
    mov ss, ax
    mov sp, stack_top           ; a stack inside what the program keeps while the game runs
    mov ax, 0x3533
    int 0x21
    mov word ptr cs:[old33], bx
    mov word ptr cs:[old33 + 2], es
    mov ax, es
    or ax, bx
    je ln_keep                  ; no mouse driver: nothing to hook (the game wants one itself)
    mov dx, int33
    mov ax, 0x2533
    int 0x21
    mov byte ptr cs:[hooked], 1
ln_keep:
    push cs
    pop es
    mov bx, (prog_end + 15) >> 4
    mov ah, 0x4a                ; keep the program, give the rest of memory to the game
    int 0x21
    call game_path              ; cs:path = this program's own path, .EXE for .COM
    jc ln_failed
    mov word ptr cs:[pb_tail + 2], cs
    mov word ptr cs:[pb_fcb1 + 2], cs
    mov word ptr cs:[pb_fcb2 + 2], cs
    mov word ptr cs:[save_sp], sp
    push cs
    pop ds
    push cs
    pop es
    mov dx, path
    mov bx, pblock
    mov ax, 0x4b00              ; run the game with the command line given
    int 0x21
    cli
    mov bx, cs
    mov ss, bx
    mov sp, word ptr cs:[save_sp]
    sti
    jc ln_failed
    call unhook
    mov ah, 0x4d                ; the game's exit code
    int 0x21
    mov ah, 0x4c
    int 0x21
ln_failed:
    call unhook
    push cs
    pop ds
    mov dx, no_game
    mov ah, 9
    int 0x21
    mov ax, 0x4c01
    int 0x21

unhook:                         ; INT 33h back to the driver, when it still points here
    cmp byte ptr cs:[hooked], 0
    je uh_end
    mov ax, 0x3533
    int 0x21
    cmp bx, int33
    jne uh_end
    mov ax, es
    mov bx, cs
    cmp ax, bx
    jne uh_end
    push ds
    lds dx, ptr cs:[old33]
    mov ax, 0x2533
    int 0x21
    pop ds
uh_end:
    ret

game_path:                      ; -> cs:path (carry set when there is none): the environment holds its strings,
    push ds                     ; an empty one, a word count and the program's own path; .COM becomes .EXE
    mov ds, word ptr cs:[0x2c]
    xor si, si
gp1:
    cmp byte ptr [si], 0
    je gp2
gp1a:
    lodsb
    or al, al
    jne gp1a
    jmp gp1
gp2:
    add si, 3
    push cs
    pop es
    mov di, path
    mov cx, 79
    xor bx, bx                  ; just past the last dot of the name
gp3:
    lodsb
    stosb
    cmp al, 0x2e
    jne gp3a
    mov bx, di
gp3a:
    cmp al, 0x5c
    jne gp3b
    xor bx, bx
gp3b:
    or al, al
    je gp4
    loop gp3
    jmp gp_bad
gp4:
    or bx, bx
    je gp_bad
    mov byte ptr cs:[bx], 0x45
    mov byte ptr cs:[bx + 1], 0x58
    mov byte ptr cs:[bx + 2], 0x45
    mov byte ptr cs:[bx + 3], 0
    pop ds
    clc
    ret
gp_bad:
    pop ds
    stc
    ret

no_game:    db "DDS98.COM: DDS98.EXE could not be run", 13, 10, "$"
pblock:     dw 0                ; the environment: a copy of this program's
pb_tail:    dw 0x80, 0          ; the command line as given
pb_fcb1:    dw 0x5c, 0
pb_fcb2:    dw 0x6c, 0
save_sp:    dw 0
hooked:     db 0
path:       resb 80
stack_area: resb 512
stack_top:
prog_end:
"""


class GamepadError(ValueError):
    pass


def build():
    """(DDS98.COM's bytes, its labels)."""
    code, labels = assemble(SOURCE, org=0x100)
    return code, labels


# ---- on an image's files (tools/addons.py)
def read(fs, path):
    e = fs.find(path)
    return None if e is None else bytes(fs.read_chain(e["cluster"], e["size"]))


def installed(fs, com):
    """Whether the image has the add-on (DDS98\\DDS98.COM, this program); another DDS98.COM is GamepadError."""
    now = read(fs, f"{DIR}/{COM}")
    if now is None:
        return False
    if now != com:
        raise GamepadError(f"镜像里的 {DIR}\\{COM} 不是本补丁的{NAME}程序，补丁不认识，不动它")
    return True


def install(fs, com):
    if installed(fs, com):
        raise GamepadError(f"镜像里已经有{NAME}")
    fs.create(DIR, COM, com)


def remove(fs, com):
    if not installed(fs, com):
        raise GamepadError(f"镜像里没有{NAME}")
    fs.remove(f"{DIR}/{COM}")


def main(argv):
    code, labels = build()
    out = argv[0] if argv else OUT
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "wb") as f:
        f.write(code)
    with open(os.path.splitext(out)[0] + ".labels.json", "w") as f:
        json.dump(labels, f)
    print(f"{out}: {len(code)} bytes, kept in memory {(labels['prog_end'] + 15) // 16 * 16} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
