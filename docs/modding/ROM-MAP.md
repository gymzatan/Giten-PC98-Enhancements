# Disk and file map

## Address conventions

This is a DOS hard-disk game, not a single cartridge ROM. An HDI byte offset depends on disk geometry, partition placement, cluster allocation and file size. Prefer resolving `DDS98/<file>` through FAT.

| Address kind | Meaning / conversion |
| --- | --- |
| HDI offset | Byte position in the complete image, including its HDI header |
| Disk offset | Position after the HDI header; add the header size to get the HDI offset |
| File offset | Position inside a FAT-resolved file, still encrypted where applicable |
| Chunk offset | Position inside a decrypted chunk; its two-byte on-disk length word is excluded |
| Record offset | Position relative to a table/script/demon record resolved from its identity |
| Main executable `S:O` | `MZ header length + S*16 + O`, with image-relative segment `S` |
| `ovNN:O` | Offset within the overlay's code image; add that overlay's file position and MZ header length |
| `DS:O` | Runtime offset in DGROUP, often state rather than static file data |

`tools/mz.py` reads the main header and overlays. `0x3800` is the reference main header length, not a universal HDI offset. Overlay 16 code starts at reference file offset `0x62A00`; overlay 2 at `0x54C00`. Resolve overlays from headers when analyzing another program build.

## HDI, PC-98 partition and FAT

`fat12.open_hdi()` reads these HDI header fields: header size at `+08` (u32), physical sector size at `+10`, sectors/track at `+14`, heads at `+18`. The first PC-98 partition entry is in physical sector 1. Its start sector/head/cylinder at entry `+08/+09/+0A` becomes `((cylinder*heads)+head)*sectors_per_track+sector`. Multiply by the physical sector size.

At the partition boot sector, the BPB supplies bytes/sector `+0B`, sectors/cluster `+0D`, reserved sectors `+0E`, FAT copies `+10`, root entry count `+11`, total sectors `+13` (or u32 `+20`) and sectors/FAT `+16`. FAT width is derived from cluster count. The reference dumps do not all use the same physical sector size or FAT width; the original Japanese disk and the smaller pre-made dump have different layouts.

`fat12.py` retains its historical filename but reads FAT12 and FAT16. `fat12w.py` replaces files and updates allocation/size metadata. The web implementation uses the same geometry and recognized-state checks. Existing file cluster chains must not be treated as fixed locations. The exact pre-made image's unused tail can be reclaimed by the accepted Artwork installer; [WINDOWS-ARTWORK.md](../../WINDOWS-ARTWORK.md) describes the checked geometry and refusal conditions.

For supported NEC menu IPL images, the automatic-boot flag is six bytes before the end of physical sector 0. `autoboot.py` checks `IPL1` at sector `+04`, signature `55 AA` and the expected flag before setting `80`. It is not a general replacement bootloader. The pre-made English/Japanese HDI still needs its companion boot floppy, as described in the player documentation.

## File families under DDS98

| Files | Contents | Existing parser / editor |
| --- | --- | --- |
| `DDS98.EXE` | DOS MZ main program, relocation table and appended overlays | `mz.py`, `mzinfo.py`, patch modules |
| `MSxxxx.BIN`, `IDxxxx.BIN` | Encrypted script chunks with identified records; ID scripts specialize demons | `ddsfile.py`, `ddsvm.py`, `ddsdis.py` |
| `MS7F00`–`MS7F07` | Script dictionary records used by commands 001–008 | `units.py`, `ddstext.py` |
| `MS6000`, `MS60xx`, `MS61xx` | Base and talk-type negotiation packs | `talkgaps.py` |
| `P2xxxx.BIN` | One encrypted character/demon record | `records.py`, `p2fields.py` |
| `ET0001.BIN` | Item/equipment header + name + description table | `tables.py`, `etfields.py` |
| `ET0004.BIN` | Skill header + name + description table | `tables.py`, `etfields.py` |
| `ET0000`, chunks 2–5 | Race, tribe/deity, class and race-group names | `tables.StringTableFile` |
| `ET000D`, chunk 1 | District names | `tables.StringTableFile` |
| `ET0101` | Object names, each prefixed with 00 | `tables.StringTableFile` |
| `ET0010` | Area records, 29 bytes; 26-byte space-padded name | `tables.py` |
| `ET0003` | Raw moon curves, 28 bytes/row; **not XOR decrypted** | `mkmoon.py` |
| `ET0005` | Enemy action rows, referenced by P2 `+6A` | AI reader in the program / field documentation |
| `ET0007` | Talk type to three loaded negotiation files | `talkgaps.py` |
| Learning-pool resources | Skills and level thresholds | `poolfix.py`, `REFERENCE.md` |
| `Mxxxx.BIN` | Encrypted map sections, names, geometry and events | `tables.py`, `mapdoors.py` |
| `FCxxxx.BIN` | Graphics entries, palettes, frame layouts and cell dictionaries | `fcimage.py`, `fcencode.py`, `gfx.py`, `fcedit.py` |

`ET0018`, `ET0040` debug menus and `ET7F00` compiler symbols are not treated as ordinary translatable name tables. Their presence does not mean the same parser applies.

## Chained XOR encryption

Most data chunks begin with a plaintext u16 byte count `w`. The seed is `(w & 0xFF) XOR (w >> 8)`. For each ciphertext byte `c`, plaintext is `c XOR state`, then `state=c`. Encryption writes `c=plaintext XOR state`, then updates `state=c`. The routines are overlay 20 `0000/0018/0048`; `ddscrypt.py` implements them.

A changed plaintext byte changes later ciphertext. Never patch a decrypted numeric offset directly into the encrypted file. Rebuild the chunk through `ddscrypt.encrypt()` or `records.encode()`, including its new length. Multiple chunks are concatenated independently. `ET0003` is a known raw-data exception, not an alternate cipher guessed by the reader.

## Map sections

The decrypted map begins with u16 zero, u16 name offset and u16 section count, then section pointers at `+06`. Each section needs at least `0x26` bytes for these fields. Wall set is `+22`, palette variant `+23`, door entry `+24`, stairs `+25`; all four are hexadecimal offsets relative to the section's start.

`mapdoors.py` is authoritative for the stored section offsets. A wall byte FF denotes an absent set. Artwork maps the stored door byte to the wall set so resource `1400h + door` selects the matching texture entry. It does not replace map text. Map names can be rebuilt up to 18 bytes through `tables.py`, with the section pointer positions relocated accordingly.
