# Script VM, branches and event conditions

## Containers and identities

`ddsfile.py` parses MS/ID files as concatenated encrypted chunks. Each decrypted chunk begins with u16 record count. A record is `[ID:u8][length:u16][payload]`, or `[ID:u8][FFFF][condition A:u8][condition B:u8][length:u16][payload]`. The two condition bytes are preserved as part of the record identity; not every conditional record can safely be chosen by position alone.

Rebuild through `ddsfile.build()` to update lengths and counts. Ordinary records must stay below FFFF bytes and a chunk below 65536 bytes. Record order is retained; record ID does not always equal list position. `units.unit_id()` uses the existing source-unit identities. `enhancement_plan.py` matches `(chunk, record ID, condition)` and checks for ambiguity.

## Tokens and operand grammar

`ddsvm.py` tokenizes using the generated `ddsgrammar.py` command/value tables. Commands below 100 are normally single-byte codes. Prefixes 1D, 1E, 1F select pages 300, 200, 100 respectively; code 162 aliases 1DE. Printable ASCII and half-width kana are text; Shift-JIS lead/trail sequences are interpreted according to the game grammar. Do not find opcodes with a raw byte search inside text.

| Signature | Meaning |
| --- | --- |
| `b`, `w`, `d` | u8, u16, u32 |
| `r` | Relative branch word; destination is after the word plus its value, modulo 65536 |
| `V` | Tagged value operand; `ddsgrammar.VALUES` supplies each tag's following grammar |
| `L` | List entries, terminated by FF; may contain record or branch entries |
| `C`, `D`, `S`, `M`, `B`, `X` | Structured operands handled by the reader's corresponding `op_*` methods |

The structured signatures must be read from `_Reader` in `ddsvm.py`, not guessed from their letters. `Token.rel` lists `(branch field offset, destination)`. `textbuild.layout_record()` relocates those destinations using original token identities when a text unit changes length. `checkvm.py` verifies branch destinations and dictionary sizes. A branch into the middle of a command is rejected.

## Useful commands

| Code | Role / reference |
| --- | --- |
| 000 | Return; with no saved return point, ends the run |
| 001–008 | Run dictionary record from MS7F00–MS7F07 |
| 009,00B | Flag branches (`rbb`) |
| 00A | Newline |
| 00C,00D | Jump/call named file selector and record |
| 018 | Relative jump |
| 019,01A | Set/clear a flag bank and bit |
| 01B,01C | Capture output on/off |
| 101,102,23E | Print a name/value/table string |
| 103,104 | Branch on a list of flag pairs |
| 158,159,15A | Push a return target, drop top return, swap top two |
| 1A4 | Party-membership check, used by the Adonis repair |
| 1F4 | Draw a check threshold |
| 1F5 | The broken threshold-overwrite handler repaired by Fixes |
| 204,205 | Movement/warp commands used by story detours |
| 210 | Wait: mode 1 click, mode 2 frame count |
| 214 | Direction-dependent branch used by Old Shinbashi |
| 23A | Write a runtime character field; Fixes adds missing EXP field 50 |
| 266,2DB,2EA | Picture commands consumed by graphics analysis |
| 2DE,2DF | Write/read hidden affection counters |
| 2E6 | Temporarily transfer inventory into script variables and back |

The exhaustive operand schemas are the source dictionaries, not this introductory subset. Value operands can refer to variables/fields rather than literal bytes. Preserve their selector conventions.

## Event flags

Runtime flag banks are 32-byte bitmaps at `DS:79E2 + bank*20h`, accessed by `1603:7F10`. A new game fills them with ones: **set often means the event has not happened**, progress clears the bit. Map objects are present while their own flag is zero; `3FBA:0014` skips a set one. Flags therefore cannot be interpreted uniformly as “completed=true”.

019 sets, 01A clears. 009/00B branch on the bank/bit; 103/104 use lists, with bank bit 80h indicating the clear condition. Read the original handler when interpreting a new branch. `storyfix.py` documents the actual writers/readers used to establish each condition.

## Established story repairs

| Event / file and record | Relevant condition and correction |
| --- | --- |
| Jukai at Gokokuji, MS0061/0/06 | Use Baal-Hadad/progress flags 00:DA,00:BB and escort state 00:D3, rather than relying on farewell flag 00:C4 that teleporting out can skip |
| Old Shinbashi, MS0026/0/21 | Non-new-moon exits inspect the came-from direction; a party from the south is placed north instead of being trapped beyond rubble |
| Hatsudai sickroom, MS0051/0/06 | Gate the briefing with escape flag 00:01; do not let reuse of 09:2D for rations replay the earlier meeting |
| Colosseum proposal, MS0012/0/04 | Require accepted proposal 00:F1 in addition to bombing state 00:B2 |
| Rainbow Bridge, MS0012/0/04 | Bombing only removes 01:0D's bridge for a party not already acting as the accepted proposal's envoy |
| Return from Harajuku, MS0052/0/02 | The clinic chooses the scene written for a wounded returning party, using the summons/scene flags rather than always jumping to ordinary revival |
| Adonis duel, MS0062/0/04 | Party-membership command 1A4 checks Sonoda; the duel cannot be entered with him still present |
| Ground Zero guide, MS0062/0/05 | With Sonoda still present, return to the intended entrance instead of clearing the receptionist route |
| Engine tile-event recheck | Record the departure cell at the start of each move so push-back/warp followed by backward movement cannot bypass the event |

The eight feature-level story fixes span multiple edits. [Event-Edits.json](Event-Edits.json) lists the source's exact records and fixed operands; `storyfix.Detour` appends checked command blocks without moving the original record body. For a new translation, text can differ while the required command structure must still match uniquely.

## Attribute checks, affection and EXP gifts

`checkfix.py` removes 1F5's unintended rand() overwrite after the threshold 1F4 produced. The established checks involve the Baal merge, DB practical exam, Emi's prologue voice and Rui's food visit. It does not turn the checks into unconditional successes.

MS0020 record 3F and MS0032 record 26 have affection answer blocks that fall through into the other answer's −1/+1. Changing the earlier steps from 2 to 3 preserves the shared control flow and leaves the intended net ±2. The hidden counters are at runtime `4827:08E6 + 4*n`, with index 2 for Yuuka and 3 for Rui.

Runtime field 50 (EXP) had no 23A setter. The added handler writes the dword at character `+6E`; dispatch table entry is `1603:A424`, code is `1603:47F4`. MS0008 record 2B can then actually grant the scripted 20,30 or first-time 3000 EXP. Crossing a threshold is settled at the next ordinary award; the fix does not create a separate level-up engine.

## Negotiation packs

The talk command starts E0:00. E0–EF select one of the loaded pack's sixteen chunks, not a global file suffix. The pack begins with MS6000, then ET0007's talk-type files, then the demon's ID file; later records override earlier ones with the same ID. Calls and list entries must be followed through this composition.

`talkgaps.py` adds 23 authored prompts to the file belonging to the caller's pack. `text/talkgaps.json` has `file`, `chunk`, hex `record`, `jp`, `en` and optional `click`. It does not replace the upstream English translation. A duplicate record or unencodable prompt fails the build. The existing audit follows actual pack composition to find empty questions before menus.

## Battle-message timing

Wait command 210 is `1E 10 01 <mode> [count]`. Mode 1 waits for a new click, mode 2 waits vsync frames and can be shortened by an advance input. PC-98 400-line timing is about 56.42 Hz; 60 frames is about a second.

Waiting permission lives at runtime `[1CEA]`. Outside the battle message paths, a wait can return −3 rather than block immediately. Some runners resume next frame; the computing pass stops. `holdflow.py` follows these different caller semantics and return stacks. It rejects inserted waits reachable from computation-only paths.

`holds.json` addresses the **original** token/unit location. `after` positions come from `mk_holds.py`; do not manually move them to suit translated byte lengths. Native English pacing must be regenerated from that English script set. Connector fragments are retained as flow exceptions, not turned into independent held sentences.
