# Giten Megami Tensei — PC-98 Enhancement Patches

Three enhancement patches for **Giten Megami Tensei: Tokyo Mokushiroku on PC-98**, supporting the original Japanese game and the tested English fan translation. All patch interfaces and documentation are in English. The selected game's language is retained.

**[Download the three patch packages from Releases](https://github.com/gymzatan/Giten-PC98-Enhancements/releases/latest).**

## Japanese and English HDI compatibility

**The same three packages work with the supported Japanese HDI and the tested English-translated HDI.** `EN` identifies the English interface and documentation; these packages do not include the English translation itself.

| Starting game | Fixes | Windows Artwork | Rebalance |
| --- | --- | --- | --- |
| Supported Japanese HDI | Supported | Supported, independently | Apply Fixes first |
| Tested English fan-translated HDI | Supported; retains translated text | Supported, independently | Apply Fixes first |

For English play, first apply the [English translation BPS](https://www.romhacking.net/translations/7343/) to its required untouched Japanese HDI. Then apply these enhancements to that English result. Applying the translation BPS after enhancements fails its source checksum.

English scripts are patched by chunk, record ID and checked instruction structure. Existing text is copied from your input, and branch offsets are recalculated when instructions are inserted. Dialogue length, line wrapping and additional unrelated records are not tied to whole-script checksums. Numerical edits address data records through their pointer tables. The specific repaired EXP wording, Core Shield description and newly supplied negotiation prompts are in English.

### Future English translation updates

Text edits that retain the relevant instruction structure can continue to work, including longer dialogue and newlines; these cases were tested. Unrelated records and complete printable replacements for the previously missing negotiation questions are retained. A change to a required opcode, event operand, branch destination or numeric field causes a precise conflict report and no output. The executable must still be one of the verified English program states. An update that changes executable code or affected event logic needs a new compatibility check; arbitrary future releases are not automatically certified.

The Japanese path continues to check its accepted native file states. Artwork validates graphics and its executable patch sites independently. These checks protect other modifications from being overwritten.

## Choose a package

| Package | Open this file | Purpose | Prerequisite |
| --- | --- | --- | --- |
| Giten Fixes (EN) | Apply Fixes.html | Gameplay repairs and quality-of-life improvements | Supported Japanese or tested English game HDI |
| Giten Windows Artwork (EN) | Apply Windows Artwork.html | Windows remake graphics adapted to the PC-98 engine | Supported Japanese or tested English game HDI; Fixes is optional |
| Giten Rebalance (EN) | Apply Rebalance.html | New combat formulas, growth, boss tuning and learning pools | An image already processed by Fixes |

For the original combat rules with repairs, use **Fixes**. For redesigned combat, use **Fixes → Rebalance**. Add **Windows Artwork** whenever desired. Artwork works before or after either gameplay patch. You can also use Artwork alone on the original game.

## Apply a patch

1. Close the emulator before selecting a disk. Back up your game and saves.
2. Extract the chosen ZIP to an ordinary folder. Open its `Apply ...html` file in your browser.
3. Select or drop the `.hdi` file. Click **Apply patch** and wait for the result.
4. Click **Save** to download the new disk. The browser may use its Downloads directory or ask where to save it.
5. When applying another package, select the disk downloaded in step 4, not the original disk again.
6. Mount the final disk in your emulator and start the game normally.

The default download names are `Giten_Fixed.hdi`, `Giten_WIN.hdi` and `Giten_Rebalanced.hdi`. The name describes the most recent patch, not the complete set installed: an Artwork result can also contain Fixes and Rebalance. Renaming a disk does not add or remove patches.

The patch reads the selected file and creates a separate result in memory. It never writes back to your selected file. No image is uploaded, and no network connection, Python installation or command line is needed. Use a browser that supports `DecompressionStream` with `deflate-raw`; the page reports an error if decompression is unavailable.

## Supported starting image

The reference input is the PepsimanGB **Pre-Made Hard Disk and Boot Floppy** edition, `Giten Megami Tensei HD.hdi`:

- Size: 31,177,216 bytes.
- SHA-256: `33ba81310d5cbf0e8459c5f09ea50360715591129a46f72c94e1b1ec0c49e77f`.
- This particular HDI is the Japanese game, not an English translation: 1,548 game files, including the executable and dialogue scripts, are byte-identical to the Japanese baseline. The included English readme explains setup; it does not indicate translated game text.

The patch checks the game files it depends on, rather than requiring that entire-disk checksum. A different disk layout can therefore work if the required files are identical. Custom executable, script, map or balance edits may be rejected. Start from the supported Japanese game or its tested English translation; compatibility with other modifications is not guaranteed.

The tested English reference was made with the supplied `giten.bps`:

- BPS SHA-256: `844f8cb5bad009f3f7e2fa179187b0d96b524d860223957dedb6497acab5e6d2`.
- BPS source/target CRC32: `821888c0` / `68968b59`.
- English HDI SHA-256: `c0ad091cc3dea998d81046ffdb418d8c392c0abe0f41c986776634a93db511b7`.

The whole-disk checksum identifies the tested reference; it is not a requirement for script-text updates at runtime. The translation's existing coverage is retained, including any passages it still leaves in Japanese. These enhancements do not complete the translation.

## Booting the PepsimanGB edition

Keep `Giten Megami Tensei Boot FD.fdi` from your own copy. Configure a PC-98 emulator to attach the patched HDI as its hard disk and that FDI as its boot floppy, then boot from the floppy. Its startup script loads the mouse and sound drivers and launches the game from `C:\DDS98`.

The patches preserve the disk's existing DOS files and startup configuration. This edition is not a standalone bootable HDI: opening only its hard disk is insufficient. The packages contain no emulator, BIOS, DOS system files, boot floppy, translation BPS or complete game image. Use the emulator and boot media with which your original copy works.

## Saves and switching editions

In-game save files on the selected image are retained. Start from an in-game save after changing patches. An emulator save state includes the old running executable and memory; loading one can bypass the newly installed code or mix incompatible states.

The expanded inventory reads original saves. Loading an expanded-inventory save in an unpatched game discards items beyond slot 48; preserve a backup before going back. Rebalance recalculates party statistics at battle entry, but it cannot undo changes already made to story flags or past character growth.

To return to the original graphics or rules, rebuild from your untouched original and apply only the packages you want. Do not apply Fixes over Rebalance to try to remove it: that combination is rejected. Each package installs its features together.

## Documentation

`Documentation.html` combines the following English documents for offline reading:

- `FIXES.md`: repairs and convenience features.
- `WINDOWS-ARTWORK.md`: graphics conversion, scope and compatibility.
- `REBALANCE.md`: combat and progression rules.
- `REFERENCE.md`: exact derived-stat formulas, learning-pool additions and numerical edit ledger.
- `Rebalance-Changes.csv`: machine-readable changes using original record IDs and byte offsets.
- `TROUBLESHOOTING.md`: controls, booting, errors and saves.
- `CREDITS.md`: project and original-work credits.
- `VALIDATION.md`: checks performed and their limits.

`SHA256SUMS.txt` lists the files shipped in each package. The three ZIPs share documentation so each can be understood on its own.
