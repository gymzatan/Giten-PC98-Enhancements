# Save format and expanded inventory

The inventory patch is mapped in `bagexpand.py`; this document covers the established affected sections. It is not a complete save-file decoder. Unmapped sections must stay unchanged.

## Runtime inventory

The original bag at `DS:866E` contains 64 four-byte entries. Slots 0–47 are ordinary items; 48–63 are scenario body parts. An entry has a u16 word with item ID in its low eleven bits and fitted gem ID in its top five, a count byte, then a flags byte whose bit 7 marks a fitted gem. Low eleven bits 7FF indicate empty. Runtime equipment may also have the all-ones form FFFF; disk templates use zero for no equipment.

The expanded bag at `DS:9B50` contains 127 entries: ordinary slots 0–110, scenario slots 111–126. Gems remain in their existing independent 16-entry table. Runtime extra buffers are:

| Address | Content |
| --- | --- |
| DS:9B50 | Expanded 127 × 4-byte bag |
| DS:9D4C | Extra 63 × 4-byte ordinary slots for temporary script inventory transfer |
| DS:9E48 | 111-word equipment-selection list |
| DS:9F26 | 111 × 4-byte single-item/count list |

Script command 2E6 temporarily copies the original 48 ordinary slots and 16 scenario slots into the original script-variable layout, plus the additional ordinary slots into DS:9D4C. The old temporary bag starts at runtime `4827:0982` (variable index 17). Both the live bag and its temporary-copy tail must survive a save made while the party's items are taken.

## Stored save sections

The original bag block begins at **save-file offset 444h** and stays in its old format: 48 ordinary slots followed by the 16 scenario slots. The original reader/writer at `25CA:DBE4/DC04` therefore remains able to consume that block.

After the game's last ordinary section, the patch appends two 63-entry blocks: extra ordinary bag slots, then their temporary-copy counterpart. Each is 252 bytes; the total tail is **504 bytes**. A reference original save is 25232 bytes and the corresponding expanded save 25736 bytes. Treat those as reference receipts, not a detector for every independently modified save.

Loading an original save leaves the extra slots empty. The original game can read the retained original block of an expanded save but loses the extra slots; it does not reconstruct them elsewhere. The expanded loader preserves scenario slot ordering when translating the old stored layout into the new runtime layout.

## Compatibility rules

Use in-game saves when switching patches. Emulator save states retain the old running program, allocation state, mounted paths and DOS caches; changing an HDI beneath a saved emulator state does not update those structures. `vmswap.py` addresses the established virtual-memory recovery path but does not make arbitrary states interchangeable.

Back up saves before changing editions. Another inventory patch that changes entry size, tail layout, buffers or save order needs an explicit merger, not a relaxed file-size check. `bagexpand_test.py` exercises original/expanded save loading, writing and inventory taken/restored through 2E6 on the emulated CPU.
