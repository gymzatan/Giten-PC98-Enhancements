# Controls and troubleshooting

## Controls with Fixes installed

| Key | Action |
| --- | --- |
| W | Step forward |
| Z | Step backward |
| A / D | Strafe left / right |
| Q / E | Turn left / right |
| S | Turn around |
| Enter / Space | Advance a dialogue or battle-message wait |
| Numeric keypad 8 / 2 / 4 / 6 | Original forward / backward / left / right controls |
| Numeric keypad 7 or 1 / 9 or 3 / 5 | Original turn left / turn right / turn around |

Movement keys are case-insensitive. Menus, targets and general interface buttons still need the mouse, unless the Gamepad control component is installed: then the arrow keys move the pointer between the menus and targets in the view, Tab goes to the command panel and party list and back, Enter and Space are the left button and Esc and Backspace the right button (see CONTROLS.md). Artwork alone retains the original game's controls and message timing.

## The gamepad does nothing

The game sees only what the emulator passes it: the PC-98 joystick and the keyboard. Check that the emulator maps the stick and two buttons to its PC-98 joystick and the D-pad to the arrow keys (CONTROLS.md). DOSBox-X reads `mapper-giten.map` only when `mapperfile` in `[sdl]` names it, and passes the stick on only while the gamepad is connected. If the arrow keys do not move the pointer either, confirm that `DDS98\DDS98.COM` is on the disk and that the game is started with `DDS98`, not `DDS98.EXE`.

## The disk does not boot

First confirm the unmodified game boots in the same emulator configuration. The PepsimanGB pre-made hard disk uses the companion boot floppy; attach both and boot the floppy. Its script expects the game hard disk at `C:` and the boot floppy at `A:`. The enhancement packages preserve that setup rather than installing DOS or replacing your startup script.

Use a PC-98 emulator configuration. A standard IBM-compatible DOS machine is not the target platform. Configure the emulator's hard-disk path to the final downloaded HDI; a newly saved file is not automatically mounted. The existing floppy's startup script launches the game without manually typing its executable name when mounted as intended.

## Can I use an English-translated HDI?

Yes, all four packages support the tested English BPS output identified in README.md. Apply that translation first, then Fixes and optionally Rebalance; Artwork can be applied independently or in either supported order. The original PepsimanGB HDI is Japanese until the translation BPS is applied.

## The patch reports unsupported files

A required program, resource or instruction does not match an accepted state. For an English script conflict, the error identifies the file, chunk and record ID. Text-only changes can work, but changed event logic or executable code requires a compatibility update. If applying Rebalance, apply Fixes first and select that saved result. If Fixes or Rebalance names `DDS98.EXE` on a disk with the target prompt control component, untick the target prompt on `Apply Controls.html` first, apply Fixes or Rebalance, then tick it again. Keep a copy of the updated translation and report the exact conflict.

If you installed custom balance changes, keep that customized image separately. These packages do not merge arbitrary modifications. Renaming a file does not bypass the checks.

## Not enough space

This is free space inside the virtual hard disk, not free space on the host computer. Keep the original reference image's capacity and avoid filling it with unrelated files. The page produces no downloadable image on failure. Do not remove game resources to make room.

For the exact reference layout, Artwork reclaims its unused 693 KiB tail as described in WINDOWS-ARTWORK.md. An unexpected extra partition, occupied FAT tail or nonblank unpartitioned data is refused. Different layouts still need enough existing free space.

## The page cannot decompress, or never produces a Save link

Open the extracted HTML directly in a browser with `DecompressionStream` support for `deflate-raw`. Read the error at the end of the log. Keep the page open until processing finishes. The saved HTML already contains the payload; it needs no server or internet access. Corrupted or incomplete copies should be replaced with a fresh extraction and checked against `SHA256SUMS.txt`.

## Where did the patched disk go?

Applying and saving are separate steps. After processing, click the page's Save link and check your browser's download location. Confirm which disk you selected for the next patch. Browsers may append a number to repeated downloads; use the most recently saved result you intended to patch.

## No audio, broken fonts or no mouse

The packages preserve the selected game's existing DOS drivers and font requirements. They do not bundle an emulator or configure host audio. Check the original game in the same setup, the emulator's PC-98 font/sound support, and that the companion boot floppy loads the mouse and game sound drivers. These are separate from patch processing.

## Old save states behave strangely

Fully restart the emulator on the new disk and load an in-game save. A save state restores memory containing the previous executable and can keep using old formulas, text pointers or graphics. The XMS swap repair solves a particular missing-directory crash, not every combination of save state and changed disk.

## Can I apply a patch twice?

Fixes and Rebalance accept their own complete installed state, preserving the same game-file contents. Applying Fixes over Rebalance is not supported. Artwork reports that no output is needed when everything it installs is already present. To remove an edition or the artwork, rebuild from the original disk and retain your backed-up in-game saves. The control features are the exception: `Apply Controls.html` takes either one out again, and reports that nothing needs changing when the disk already has the control features as ticked.

## Reporting a problem

Include the package name, input image checksum, browser or emulator details, full patch log, installation order, and an exact description of the failing action. For a game issue, include whether it also occurs in the unmodified original and whether you loaded an in-game save or an emulator save state. Do not distribute a complete game disk as part of a public report.
