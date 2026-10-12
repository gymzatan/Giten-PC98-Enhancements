# Giten Megami Tensei Redux

Three enhancement patches in one download for **Giten Megami Tensei: Tokyo Mokushiroku on PC-98**, supporting the original Japanese game and the tested English fan translation. All patch interfaces and documentation are in English. The selected game's language is retained.

**English translation patch:** the English translation supported by Redux comes from [Sneikkimies](https://www.romhacking.net/community/8677/)' [Giten Megami Tensei translation release](https://www.romhacking.net/translations/7343/). It is distributed separately from the Redux enhancements.

## Start here

1. Download **[Giten-Megami-Tensei-Redux.zip](https://github.com/gymzatan/Giten-PC98-Enhancements/releases/download/english-enhancements/Giten-Megami-Tensei-Redux.zip)**. It contains all three patches and the English manual.
2. Extract the whole ZIP and open **`START HERE.html`** in your browser.
3. To install all three, follow this sequence. **Use each newly saved disk as the next input.**

| Open | Select | Save |
| --- | --- | --- |
| `Apply Fixes.html` | Your Japanese game HDI, or the English-translated HDI | `Giten_Fixed.hdi` |
| `Apply Rebalance.html` | The `Giten_Fixed.hdi` just saved | `Giten_Rebalanced.hdi` |
| `Apply Windows Artwork.html` | The `Giten_Rebalanced.hdi` just saved | `Giten_WIN.hdi` |

**Play the final `Giten_WIN.hdi`.** In this sequence it contains all three patches. If you want original combat rules with repairs and new artwork, skip Rebalance and feed `Giten_Fixed.hdi` into Artwork. Artwork can also be used alone.

For English play, apply Sneikkimies' translation **before** Redux. The translation remains a separate download. Use the PC-98 emulator and boot setup that runs your original copy; the PepsimanGB pre-made HDI needs its companion boot floppy. Restart and load an in-game save after changing patches.

## Features

### 1. Fixes — Easier controls, more space, and game repairs

#### Everyday improvements

- **Keyboard controls:** W/Z/A/D move forward/back/left/right; Q/E turn; S turns around. Enter or Space advances dialogue and battle-message waits. Menus still use the mouse.
- **Larger inventory:** ordinary item capacity increases from **48 to 111 slots**. The separate 16 body-part slots remain unchanged, and original saves can be loaded.
- **Easier-to-read dialogue and battles:** dialogue endings that used to close immediately now wait for input. Battle messages pause for about one second; a click or advance key can shorten the wait.
- **Faster moon phases:** the visible phase advances after about **60 steps instead of 300**. Monthly chests, refillable vessels and other long-duration timers keep their original time scale.

#### Story, equipment, and combat repairs

- **Eight story-event repairs:** prevents blocked routes, repeated briefings, movement exploits and unintended party retention. Examples include Jukai's appearance after teleporting out of Chuu, the Hatsudai sickroom briefing, and reception checks before the Adonis duel.
- **Correct choices and rewards:** repairs seven attribute checks, Rui's affection changes, and missing EXP awards from Wendy, Miranda and Josephine.
- **Weapons and equipment work as intended:** restores attribute bonuses, magic accuracy/evasion effects, gun critical modifiers, and the effects of attack/status items. Previously ineffective gun and physical attack skills become usable; gun skills use HP rather than ammunition.
- **Better feedback and negotiation:** the battle summary shows the actual EXP award. COMP attacks grant COMP skill EXP, and 23 missing demon-negotiation prompts are supplied in the selected game's language.
- **Fewer interruptions and graphical faults:** fixes blank inventory entries, script-memory leaks, several overflow/divide-by-zero cases and the missing-directory VM error; repairs battle backdrops and palette allocation, and suppresses the persistent `no space` warning.

Fixes retains the original combat formulas with implementation repairs. The optional Rebalance package changes the rules. [Full Fixes guide](FIXES.md).

### 2. Windows Artwork — A visual upgrade you can use on its own

- **Windows remake environments:** replaces dungeon walls, doors and stairs, plus room and story-event pictures.
- **Windows demon artwork:** replaces demon sprites and poses with the remake's renditions, using their adapted scale and placement.
- **Remake title screen and metal frame:** replaces the title artwork and turns the surrounding gold interface frame and lower compass panel into gray metal. Command buttons and direction controls retain their familiar green.
- **Adapted for the PC-98 renderer:** door selectors match each area's wall set, scene overlays use their intended shared palettes, and palette fixes reduce debug warnings and background recoloring.

Artwork works **independently**, or before/after either gameplay patch. It retains the selected game's text and gameplay rules apart from the included graphics/palette repairs. [Full Artwork guide](WINDOWS-ARTWORK.md).

### 3. Rebalance — Broader character builds and revised combat

#### Changes you notice while playing

- **More skills to learn:** the protagonist's magic route gains the Megi line, and the gun route gains a dedicated learning pool. The original level-up learning checks still decide when skills are acquired.
- **More rounded growth:** one quarter of inclination growth points goes to the lowest attribute. Humans also gain one Vitality every third level. Past level-up allocations are retained.
- **Retuned bosses and Newton:** revises boss statistics and strengthens Newton's skill set and three special equipment pieces, including resurrection support and a six-shot gun.
- **Summoning has a combat cost:** calling a demon from COMP during battle consumes one action of the COMP holder. Summoning outside battle remains free.
- **Level-aware EXP:** lower-level party members receive more EXP from stronger enemies, while over-levelled members receive less. Each member's award is calculated separately.
- **COMP helps recruitment:** COMP level strengthens specified attribute checks and increases the protagonist's effective recruitment level limit.

#### Combat-system changes

- **Stats matter more:** attributes and human skill levels contribute more to combat, while several equipment contributions are reduced. After COMP awakens, the protagonist's Charm supports allied demons.
- **Revised hit, damage, and critical-hit rules:** physical and magic attacks use new accuracy/damage curves; some physical misses become grazes, critical hits use a new probability and multiplier, and ordinary critical checks no longer depend on the moon gate.
- **Updated HP, healing, speed, and moon effects:** adjusts HP growth and healing, uses Strength to handle armor weight, and revises moon damage scaling. Combat stats are recalculated at battle entry so existing in-game saves use the new rules.

Rebalance requires **Fixes first**; Windows Artwork is optional. [Full Rebalance guide](REBALANCE.md) · [Exact formulas and numerical ledger](REFERENCE.md).

## Choose your patches

| Patch | Open this file | Purpose | Prerequisite |
| --- | --- | --- | --- |
| Fixes | Apply Fixes.html | Gameplay repairs and quality-of-life improvements | Supported Japanese or tested English game HDI |
| Windows Artwork | Apply Windows Artwork.html | Windows remake graphics adapted to the PC-98 engine | Supported Japanese or tested English game HDI; Fixes is optional |
| Rebalance | Apply Rebalance.html | New combat formulas, growth, boss tuning and learning pools | An image already processed by Fixes |

For the original combat rules with repairs, use **Fixes**. For redesigned combat, use **Fixes → Rebalance**. Add **Windows Artwork** whenever desired. Artwork works before or after either gameplay patch. You can also use Artwork alone on the original game.

## Apply a patch

1. Close the emulator before selecting a disk. Back up your game and saves.
2. Extract the complete Redux ZIP and open `START HERE.html`, then choose the patch you want. Individual patch ZIPs also contain their own `Apply ...html` file.
3. Select or drop the `.hdi` file. Click **Apply patch** and wait for the result.
4. Click **Save** to download the new disk. The browser may use its Downloads directory or ask where to save it.
5. When applying another package, select the disk downloaded in step 4, not the original disk again.
6. Mount the final disk in your emulator and start the game normally.

The default download names are `Giten_Fixed.hdi`, `Giten_WIN.hdi` and `Giten_Rebalanced.hdi`. The name describes the most recent patch, not the complete set installed: an Artwork result can also contain Fixes and Rebalance. Renaming a disk does not add or remove patches.

The patch reads the selected file and creates a separate result in memory. It never writes back to your selected file. No image is uploaded, and no network connection, Python installation or command line is needed. Use a browser that supports `DecompressionStream` with `deflate-raw`; the page reports an error if decompression is unavailable.

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
