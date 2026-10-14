# Keyboard & Gamepad Controls

`Apply Controls.html` installs keyboard/gamepad controls together with the battle target prompt and target-selection pause. The battle optimization is a necessary part of the control patch. Click **Install Controls** to install both, or **Remove Controls** to remove both. The fourth patch as a whole is optional; its components are not separate choices.

It works on the supported Japanese game and the tested English translation, with or without Fixes, Rebalance and Windows Artwork, and saves `Giten_Controls.hdi`. If an image has only one component from an older installer, Install completes the package and Remove removes both. Neither action is selected automatically.

The page tells the game's language from `DDS98.EXE`: the English translation changes 576 bytes there (the status names and their pointers), and no other patch writes those bytes. A program whose bytes match neither language is refused.

## Target prompt

When a command waits for its target (after you choose an attack, a skill or an item), the battle text box asks “Use on whom?” in the English game, or 「誰に使いますか？」 in the Japanese game, and battle time stops. No action gauge fills on either side until you pick a target or cancel with the right button. Choosing again after a cancel asks again, and the picked action's own message replaces the question.

The original game stops the clock only while you pick an ally. While you point at an enemy, which covers every sword and gun attack and every attack skill, the enemies, bosses included, keep acting.

The control component changes six places in `DDS98.EXE` and adds `DDS98\MS00D9.BIN`, a message file the game does not otherwise have:

- the target pick clears the battle tick on every frame and keeps the message window open;
- the pick's first frame shows the question;
- the command menu and the skill/item menu reset it, so the next pick asks again;
- two unused status wrappers in the program hold the new code and a one-byte flag.

## Keyboard / gamepad controls

Play with a gamepad or the keyboard. The mouse still works.

| Gamepad | Keyboard | Action |
| --- | --- | --- |
| Left stick | PC-98 joystick | Walk. In a dungeon: up steps forward, down turns around, left and right turn. On the world map: walk straight in that direction |
| — | W / A / S / D | Walk on the world map (in a dungeon the Fixes keyboard controls apply) |
| D-pad | Arrow keys | Move the pointer to the nearest clickable thing in that direction within the view: menu entries, options, battle targets, the person standing in front of the party, a chest, the opening dial pad, equipment slots. With nothing to click in the view (an empty corridor) the pointer stays where it is. On the world map the D-pad walks |
| A | Enter / Space / joystick button 1 | Left button |
| B | Esc / Backspace / joystick button 2 | Right button. In the interface (after X) it returns to the view instead, with the pointer in the middle of the view |
| X | Tab | Go to the interface: the command panel on the right and the party list at the bottom (where skills and items for allies pick their target); the D-pad then moves among those. Press again to return: the pointer goes back exactly where it was in the view |
| Y (hold) | Ctrl (hold) | The stick moves the pointer freely instead of walking: slowly at first, then faster, anywhere on the screen. The D-pad still jumps between targets. After Y is let go, the stick walks again once it has been let go too |
| — | Shift (hold) + arrow keys | The arrow keys move the pointer freely, as the stick does with Y. After Shift is let go, the arrow keys jump between targets again once they have been let go too |
| LB / RB | 4 / 6 | Step sideways in a dungeon (the game's own keys) |

At the end of a list or panel the D-pad wraps round: Down on the last entry goes to the first (STATUS to FIGHT on the command panel), Right on the rightmost target goes to the leftmost. The D-pad never reaches the interface by itself, and never the direction pad below the command panel (walk with the stick or the keys). The next time X goes to the interface, the pointer returns to the button it last left there. A menu opened from the interface, such as DDS or STATUS on the command panel, takes the D-pad while it is open; once it is closed (with B or its own EXIT), the D-pad is back in the interface. When something new comes up in the view, such as the next member's turn in battle, the pointer is back in the view on its own.

On the world map, a short press of B (or X) moves the pointer to the commands on the right, where the D-pad picks one; another short press of B (or X) puts the pointer back where it was. Holding B is the right button, which opens the small map.

The control component is one file, `DDS98\DDS98.COM`. The boot floppy's startup script ends with `CD C:\DDS98` and `DDS98`, and DOS runs a `.COM` file before an `.EXE` of the same name, so this file starts first. It hooks the mouse driver's interrupt, starts `DDS98.EXE` with the same command line, and unhooks the interrupt when the game ends. When the game registers its mouse handler, the control component checks the game's code at every place it hooks before changing anything in memory; the program on the disk is not changed. While the game runs it keeps about 8 KB of conventional memory. No startup file is changed.

### Connecting a gamepad

The game reads a PC-98 joystick (one stick, two buttons) and the keyboard. Set up your emulator so that:

- the left stick and A and B are the PC-98 joystick;
- the D-pad is the arrow keys;
- X is Tab;
- Y is Ctrl;
- LB and RB are the 4 and 6 keys.

Use the emulator's own joystick and key settings, or a tool such as Steam Input or JoyToKey.

**DOSBox-X:** the Controls ZIP and the complete Redux ZIP include both `dosbox-x.conf` and `mapper-giten.map`. The configuration already sets `mapperfile = mapper-giten.map` in `[sdl]`. The mapper preserves all default key and joystick bindings and adds the assignments above for an XInput gamepad (SDL button order: 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB; hat 0 the D-pad). DOSBox-X passes the stick to the emulated PC-98 only while a gamepad is connected.

### Use the supplied DOSBox-X configuration

In a **new emulator folder**, place these files together:

```text
dosbox-x.exe          Your Windows DOSBox-X installation and its required files
dosbox-x.conf         Included configuration
mapper-giten.map      Included XInput mapping
Giten_Controls.hdi    The final image saved by Apply Controls.html
Boot.fdi             Your own Giten Megami Tensei Boot FD.fdi, copied and renamed
```

Double-click `dosbox-x.exe`. The configuration uses PC-9821, 16 MB RAM and relative filenames, attaches `Giten_Controls.hdi`, and boots from `Boot.fdi`. This is the boot setup required by the supported PepsimanGB pre-made HDI, in Japanese or with the tested English translation. The emulator, game image and boot floppy are supplied by you.

**An HDI that already boots by itself:** replace both commands under `[autoexec]` in the supplied configuration with this single command:

```text
boot Giten_Controls.hdi
```

**An existing working emulator setup:** keep its configuration and boot commands. Copy `mapper-giten.map` beside it and set `mapperfile = mapper-giten.map` in `[sdl]`. Back up an existing configuration before replacing it. If you use the supplied configuration with a different final image name, change `Giten_Controls.hdi` in its boot commands to that filename.

## Disk space

Each control component's file takes one cluster of the disk (8 KiB on the reference disk). The English game with Fixes and Windows Artwork fills the reference disk completely: the artwork takes the last free clusters, including the 693 KiB tail it reclaims. When the chosen disk has fewer free clusters than the control features need, the page grows the image by whole cylinders at its end (one cylinder of the reference disk is 49.5 KiB, six clusters) and says so in its log. The HDI header's size and cylinder count, the partition's end cylinder and the volume's size follow; no file moves. The page grows only a disk whose single DOS volume already reaches its end, and refuses any other.

## Order with the other patches

- **Fixes and Rebalance** check `DDS98.EXE` as a whole and refuse one that has the target prompt in it, without producing an output. Apply them before Controls. To add them later, remove Controls first, apply them, then install Controls again.
- **Windows Artwork:** apply it before the control features. It checks its own places in `DDS98.EXE` only and keeps both control features, but on the English game with Fixes the reference disk has room for everything only in this order: with the control features already in, the artwork is two clusters short and refuses, and a disk the control component page has grown is no longer the reference layout, whose tail the artwork reclaims. On the Japanese game either order works.
The launcher alone adds a file, but this installer always pairs it with the battle optimization. Apply the whole Controls patch last.

## Saves

Adding or removing an control component changes no save file. Use an in-game save across the change, not an emulator save state: a save state holds the old running program.
