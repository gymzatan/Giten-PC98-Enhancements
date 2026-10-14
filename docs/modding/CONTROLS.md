# Controls, target pause and battle-message pacing

The Controls patch works independently of game text and of the other three installers. The English page installs and removes keyboard/gamepad operation and the necessary battle target optimization together. `src/tools/addons.py` defines their order, state inspection, disk-space requirement and install/remove calls. `src/tools/webpatch.js` mirrors those existing rules; `enhancement_runtime.js` supplies the English installer's inspection and checked language selection. There is no separate controller implementation in the web page.

## Target-prompt map

| Location | Meaning |
| --- | --- |
| `DDS98/MS00D9.BIN`, chunk 0, record 0 | Newly authored question and line terminator; original game has no file with this name |
| Overlay 16 `1C18` | Keep the text window visible and stop the battle tick during target selection |
| Overlay 16 `2A9D` | Show the question on the first target-pick frame |
| Overlay 16 `19F2`, `1A52` | Reset the shown flag when a command menu opens |
| Main segment `358E:411C–4147` | Question display and reset routines |
| Main segment `358E:415E` | One-byte shown flag |

These are segment-relative offsets, not HDI offsets. `targetprompt.where()` resolves the overlay from the selected executable's MZ overlay table; main offsets use its `0x3800` header. `targetprompt.SITES` holds both checked byte forms. The generated [executable ledger](Executable-Sites.csv) resolves the file locations from your supplied Japanese executable.

The installer compares all byte runs changed by the tested English executable: 576 bytes of status names and pointers. They are disjoint from the enhancement sites. Matching Japanese selects CP932 「誰に使いますか？」; matching English selects ASCII “Use on whom?”. Mixed or unknown executable states are refused, with no default language guess. Longer or rewritten script text does not determine the question's language.

The executable edits and message file must be present together. Partial installs are refused. Removing Controls restores the original six byte forms and removes both its message file and controller launcher. Apply this option after Fixes/Rebalance; remove Controls before installing either of those later. Artwork preserves both control features; use Artwork first on the full English Fixes reference disk so the control component installer can grow the disk if needed.

## Keyboard/gamepad launcher

`gamepad.py` assembles `DDS98/DDS98.COM`, a launcher that runs the existing executable with runtime input hooks. It does not rewrite startup files or replace game scripts. DOS resolves the start command `DDS98` to COM before EXE; explicitly starting `DDS98.EXE` bypasses the launcher. Its extensive assembly comments describe the input ports, hook preconditions, screen/window records, clickable-target search, panel switching, repeat state and free-pointer acceleration. `gamepad.build()` returns both bytes and assembled labels.

The emulated PC-98 joystick provides the left stick and two mouse buttons. Keyboard hooks provide the arrow-key target navigation, Tab panel switching, Enter/Space confirmation, Esc/Backspace cancellation, W/A/S/D world-map walking and Shift+arrow free-pointer control. `mkmapper.py` maps an XInput pad's hat to arrows, X to Tab, Y to Ctrl and LB/RB to 4/6; the left stick and A/B remain the PC-98 joystick. Controller connection and mapping are emulator settings, not game-language detection.

`gamepad_test.py` executes the assembled routines under Unicorn and checks recognized Japanese/English program states. `enaddons_test.py` compares actual embedded HTML output to `addons.apply()` across original, Fixes, Rebalance and artwork combinations. Unrelated files and in-game saves are preserved. Emulator save states must be recreated after changes because they retain old running hooks.

## Battle-message pacing in Fixes

`holdshow.py` makes a line visible before its own script wait, ignores a mouse button still held from the target click when starting that wait, and extends five short command-panel notices to the game's ordinary notice duration. Its `sites()` returns checked file offsets and byte forms; the same definitions appear in the executable ledger. `holdshow_test.py` checks the assembled drawing/wait routines and coexistence with the target-prompt flag. This repair belongs to Fixes, independently of the fourth installer.
