# Numeric data map

These offsets are relative to **decrypted records**, not ciphertext or HDI bytes. `records.py` resolves table entries through their current pointer lists. `balance.py` checks each field against the expected/original pair before modifying it. The same numeric target can therefore apply to Japanese and English records even when their names/descriptions have different lengths.

## Character and demon files: P2xxxx.BIN

Each file normally contains one encrypted chunk. Its plaintext is a 121–124-byte record, depending on the character family. Its stable ID is also in the filename. `p2fields.py` is the authoritative field map.

| Offset | Width / count | Meaning |
| --- | --- | --- |
| 00 | u32 | Experience |
| 04 | u32 | Currency |
| 08 | u32 | MAG |
| 0C | u16 | HP |
| 0E | u16 | MP |
| 10 | 8 × u16 | ET0004 skill IDs: six held skills, then two enemy-only slots |
| 20 | u8 | Equipment affinity, 0–33; display 1–9 then A–Y |
| 22,24,26,28 | u16 each | Head, body, arms, legs item IDs |
| 2A,2C,2E,30 | u16 each | Accessory, sword, gun, ammunition item IDs |
| 32 | u16 | Dropped item ID |
| 34 | u16 | Record's own ID |
| 36 | 17 bytes | CP932 name field, NUL padded |
| 47 | u8 | Level |
| 4C | u8 | Intuition |
| 4D | u8 | Willpower |
| 4E | u8 | Magic |
| 4F | u8 | Intelligence |
| 50 | u8 | Grace |
| 51 | u8 | Strength |
| 52 | u8 | Vitality |
| 53 | u8 | Agility |
| 54 | u8 | Dexterity |
| 55 | u8 | Charm |
| 56 | u8 | Luck |
| 57 | u8 | CP |
| 58 | u8 | Moon curve row in ET0003 |
| 59–62 | 10 × u8 | Physical, gun, fire, ice, force, electricity, expel, magic, curse, nerve resistance |
| 63–65 | 3 × u8 | Learning-family IDs the demon can teach |
| 66 | u8 | Enemy speed used when constructing the combatant |
| 67 | u8 | Acquisition rate |
| 6A | u8 | ET0005 action-pattern row |
| 73 | u8 | Negotiation type, selecting ET0007's file triplet |

For resistance bytes below FA, ordinary damage percentage is `byte × 2`; 32h means 100%. Confirmed special values are 00 immune, FC absorb and FF reflect. FA, FB, FD and FE are shown raw until their individual meanings are established. Do not assign them convenient invented names.

`48,49,4A,4B,68,6B,6D,6E,75,79` are not given editable semantic fields by `p2fields.py`. Graphics analysis uses `6D` as a palette-variant selector, but the numeric editor still leaves it raw; that observation is not a complete character-record schema. Race, race group, deity and alignment are derived from the ID's classification rather than independently editable bytes in the mapped record.

The program builds a larger runtime character structure. Its field offsets differ from P2 disk offsets: examples are EXP `+6E`, Luck-related terms near `+F8`, gun terms `+104/+110`, and the moon row `+1F8`. Do not write runtime offsets into P2 files.

## ET0004: magic and skills

Decrypt the chunk, read u16 entry count, then that many u16 offsets relative to the chunk start. Each entry is a **20-byte header**, NUL-terminated name, NUL-terminated description. English descriptions can contain newlines. Rebuild pointers through `tables.table_bytes()` or `StringTableFile.build()` when strings change.

| Header offset | Width | Confirmed field |
| --- | --- | --- |
| 00 | u8 | Skill class/system |
| 01 | u8 | Learning family |
| 02 | u8 | Learn level |
| 03 | u8 | Cost |
| 04 | u8 | Use context |
| 05 | u8 | Range |
| 06 | u8 | Target listing |
| 07 | u8 | Number of targets |
| 08 | u8 | Distance |
| 0C | u8 | Element/affinity |
| 0D | u8 | Added status |

Other header bytes remain raw in the generic numeric editor. Interpreter analysis identifies attack/result message selectors at header `11` and `13` (hex); `holdflow.py` consumes them to find battle roots. Read the source's full calling convention before changing those bytes: they are not extra power fields.

The repair of attack templates is in `skillfix.py`. It contains checked header edits and the executable dispatch repair; a skill power/label change alone does not implement a missing handler. Exact affected IDs and values are in [REFERENCE.md](../../REFERENCE.md) and [Rebalance-Changes.csv](../../Rebalance-Changes.csv).

## ET0001: items and equipment

The container has the same count/pointer table. Header length depends on the **kind byte at entry +04**. `tables.ITEM_HEADER` gives these lengths in decimal bytes:

| Kind | Header length | Editor category |
| --- | --- | --- |
| 1 | 21 | Medicine |
| 2 | 13 | Incense |
| 3 | 16 | Stone |
| 4 | 23 | Thrown item |
| 5 | 17 | Talisman |
| 6 | 13 | Book |
| 7 | 13 | Software |
| 8 | 12 | Card |
| 9 | 29 | Gem |
| 10 | 12 | Story item |
| 11 | 32 | Weapon |
| 12 | 23 | Gun/bow |
| 13 | 14 | Ammunition |
| 14–18 | 18 | Full body, head, body, arms, legs |
| 19 | 16 | Accessory |

Each header is followed by NUL-terminated name and description. Unknown kinds are not assigned a guessed header length.

Confirmed fields for kind 11 weapons:

| Offset | Width | Meaning |
| --- | --- | --- |
| 05 | u8 | Equipment affinity |
| 09 | u8 | Sword power |
| 0B | u8 | Sword accuracy |
| 0D | u8 | Element/affinity |
| 0E | u8 | Distance |
| 0F,10 | u8 each | Minimum and maximum hit count |
| 11,12 | u8 each | Required Vitality and Dexterity |
| 15 | u8 | Added status |
| 1A | u16 | Activated magic/skill ID |
| 1D | u8 | Magic power |

Confirmed armor/accessory fields for kinds 14–19 are equipment affinity at 05, physical defense at 09, evasion at 0A, and element/affinity at 0D (u8 each). Other categories/bytes remain available as raw offsets in the editor; `statfix.py` documents the executable's additional equipment effects and how they enter runtime derived values. Do not label every raw byte using a different item kind's interpretation.

## Learning pools: ET0030

This is **raw, not XOR encrypted**: u16 body length, then body u16 pool count, followed by `count` entries of `[offset:u16][pool ID:s16]`. Each offset is relative to the body start. Each pool is a sequence of u16 skill IDs ending in FFFF.

The protagonist's awakened routes use pool IDs sword −1, gun −2, magic −3, COMP −4. Companion pools use their runtime human index. `poolfix.py` appends the Rebalance skills and makes the missing gun pool. The combined candidate buffer has room for 63 IDs, an established limit rather than an expandable list.

Learning eligibility remains the game's code, overlay 13 `06D6`: `(character level − skill learn level) × 10 + Intelligence` is compared against the mean of three draws U(10..60). Pool order and learn levels matter; inclusion does not guarantee acquisition on that exact level.

## Moon curves: ET0003

`mkmoon.table()` reads a u16 raw length followed by rows of **28 bytes**. P2 `+58` selects the row. Age 0–27 is displayed as 1/28–28/28, with 15/28 full moon. Original damage multiplier is `2v/100`; Rebalance uses `sqrt(v/50)`. A row value 50 is ×1 in both.

The damage routine is main `25CA:8E68`; runtime character construction copies the P2 row to `+1F8` through overlay 32 `1068`. This curve does not control how fast the visible moon advances. That timer is the separate `moonfast.py` patch.

## Enemy AI and negotiation

P2 `+6A` chooses the ET0005 action row used by overlay 32 `051A`. The row decides ordinary attacks versus skill slots. The enum file records established row labels; it is not an inferred AI generator.

P2 `+73` chooses an ET0007 row `[MS60xx A][MS60xx B][MS61xx C]`, with FF meaning absent. The pack starts from MS6000, overlays those files, then the demon's ID script. See [SCRIPT-VM.md](SCRIPT-VM.md) before editing calls to E0–EF. They resolve through that loaded pack rather than a single globally named file.
