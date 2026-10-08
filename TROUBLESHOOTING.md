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

Movement keys are case-insensitive. Menus, targets and general interface buttons still need the mouse. Advance keys do not select arbitrary on-screen menu buttons. Artwork alone retains the original game's controls and message timing.

## The disk does not boot

First confirm the unmodified game boots in the same emulator configuration. The PepsimanGB pre-made hard disk uses the companion boot floppy; attach both and boot the floppy. Its script expects the game hard disk at `C:` and the boot floppy at `A:`. The enhancement packages preserve that setup rather than installing DOS or replacing your startup script.

Use a PC-98 emulator configuration. A standard IBM-compatible DOS machine is not the target platform. Configure the emulator's hard-disk path to the final downloaded HDI; a newly saved file is not automatically mounted. The existing floppy's startup script launches the game without manually typing its executable name when mounted as intended.

## The patch reports unsupported files

The listed files do not match the exact original or accepted patched state for this package. Use your untouched supported Japanese disk. If applying Rebalance, first apply Fixes and then select the saved Fixes result. Do not apply a gameplay patch over a translated image or an unrelated mod and assume its changes will be preserved.

If you installed custom balance changes, keep that customized image separately. These packages do not merge arbitrary modifications. Renaming a file does not bypass the checks.

## Not enough space

This is free space inside the virtual hard disk, not free space on the host computer. Keep the original reference image's capacity and avoid filling it with unrelated files. The page produces no downloadable image on failure. Do not remove game resources to make room.

For the exact reference layout, Artwork reclaims its unused 693 KiB tail as described in WINDOWS-ARTWORK.md. An unexpected extra partition, occupied FAT tail or nonblank unpartitioned data is refused. Different layouts still need enough existing free space.

## The page cannot decompress, or never produces a Save link

Open the extracted HTML directly in a browser with `DecompressionStream` support for `deflate-raw`. Read the error at the end of the log. Keep the page open until processing finishes. The saved HTML already contains the payload; it needs no server or internet access. Corrupted or incomplete copies should be replaced with a fresh extraction and checked against `SHA256SUMS.txt`.

## Where did the patched disk go?

Applying and saving are separate steps. After processing, click the page's Save link and check your browser's download location. Confirm which disk you selected for the next patch. Browsers may append a number to repeated downloads; use the most recently saved result you intended to patch.

## No audio, broken fonts or no mouse

The packages preserve the Japanese game's existing DOS drivers and native font requirements. They do not bundle an emulator or configure host audio. Check the original game in the same setup, the emulator's PC-98 font/sound support, and that the companion boot floppy loads the mouse and game sound drivers. These are separate from patch processing.

## Old save states behave strangely

Fully restart the emulator on the new disk and load an in-game save. A save state restores memory containing the previous executable and can keep using old formulas, text pointers or graphics. The XMS swap repair solves a particular missing-directory crash, not every combination of save state and changed disk.

## Can I apply a patch twice?

Fixes and Rebalance accept their own complete installed state, preserving the same game-file contents. Applying Fixes over Rebalance is not supported. Artwork reports that no output is needed when everything it installs is already present. To remove an edition or the artwork, rebuild from the original disk and retain your backed-up in-game saves.

## Reporting a problem

Include the package name, input image checksum, browser or emulator details, full patch log, installation order, and an exact description of the failing action. For a game issue, include whether it also occurs in the unmodified original and whether you loaded an in-game save or an emulator save state. Do not distribute a complete game disk as part of a public report.
