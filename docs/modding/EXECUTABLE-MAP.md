# Executable repairs and formula locations

All addresses refer to the recognized `DDS98.EXE`, not to the HDI. See [ROM-MAP.md](ROM-MAP.md) for main/overlay address conversion. The main MZ header is `3800h` in the reference. Runtime DGROUP is image segment `48FC`; registers and current character pointers are often essential context when examining a routine.

[Executable-Sites.csv](Executable-Sites.csv) records exact file offsets, lengths and before/after bytes from the actual patch definitions. `tools/modmap.py` regenerates it from those modules; it does not rediscover fixes. Some spans are entire assembled helper blocks and include relocation-preserving padding. A span's bytes alone do not establish its entry calling convention.

## Fixes: controls, inventory and visibility

| Module | Reference site(s) | Implementation |
| --- | --- | --- |
| `exekeys.py` | main image `2B605`, `2E140`, `2E157`; unused block `2F038–2F0D3` | Map W/Z/A/D/Q/E/S, case insensitive, to keypad 8/2/4/6/7/9/5; Enter/Space advance waits; flush buffered keys at wait setup |
| `bagexpand.py` | inventory module `25CA:CE00–DF00`, new-game init ov08:1474, callers in ov01/11/12 and script command 2F1 | Expand ordinary slots 48→111, preserve 16 scenario slots; move buffers, bounds, save/read and temporary-transfer paths together |
| `exefix.py` | ov14:03BE, ov12:05FD | Recognize both empty equipment encodings so removed weapons do not create blank item rows |
| `talkwait.py` | Script records determined through the existing VM analysis | Preserve dialogue endings with an advance wait |
| `holds.py`, `holdflow.py` | Script command 210; wait state near main image `2E0E4/2E150` | Add readable battle timing only where the interpreter actually permits it |
| `moonfast.py` | `25CA:8A08,8A66,8B56,8B08,8DC8,8DFE`; helper `8D60–8DC7` | Faster visible lunar phase with a separate original-scale timer for monthly resources |

The keyboard patch does not map keys to arbitrary mouse positions. Menus and ordinary buttons remain mouse-controlled. Its advance routine operates on the game's click-wait state, including mode-2 battle holds. The routine is assembled through `asm86.py`, then CPU-tested against its actual call paths.

The inventory patch reserves `700h` bytes by moving the stack/near-heap boundary: MZ SP 1000→1700 and minalloc 440→4B0. The stack size stays constant; near-heap room is reduced by that reservation. Do not install a second independent inventory-size patch over its buffers.

The moon patch's original phase interval is 1520 internal minutes, changed to 300. The movement-time relationship produces about 300→60 steps per phase; it is not literally a direct byte containing 300 steps. Runtime phase/time words include `DS:98E8/98EA`; flag-bank 7 bits F0 and the resource flags named in `moonfast.py` retain their established roles.

## Fixes: story checks and equipment/combat bugs

| Module / routine | Site(s) | Corrected behavior |
| --- | --- | --- |
| Story movement | main image `3DDF4`, `3E950` | Record departure cell before each step so push-back and backward movement do not skip events |
| `checkfix.py`, threshold | `1603:7D98` | 1F5 reads its operand and returns, preserving 1F4's threshold |
| Script EXP setter | `1603:A424`, `47F4–4804` | Add 23A field 50's missing dword setter |
| Item attribute code | `25CA:E116` | Index the intended attribute, not the unrelated buffer byte |
| Magic accuracy / evasion | `358E:28EC`, `2926`, `296E` | Add sword magic-hit and equipment magic-evasion bonuses to derived values |
| Armor effect 36 | Equipment bonus routine in `statfix.py` | Use the armor's evasion rather than its nonexistent sword-hit term |
| Critical weapon selection | ov16:0000, helper in segment 25CA | Select sword/gun for the actual action class, rather than treating the skill ID or ammunition as the weapon |
| Attack item setup | `25CA:995E` | Build cached hit/power/element/status from the item's own header |
| Status item | `25CA:DFF2` | Read the added status from the filled byte +17, not empty +11 |
| Script attributes | `1603:A354`, `D50E` | Move base/current attributes consistently; do not make temporary curse/clamp effects permanent |
| Multiplier overflow | `358E:2E0A` | Preserve the product's high word rather than truncating to 16 bits |
| Negative speed | `358E:1992` / compare near `1A6E` | Signed lower-bound check; heavy armor cannot wrap to an enormous unsigned speed |
| Added-status defense product | ov16:0F6E and 3B3A | Unsigned interpretation for products that can exceed 32767 |
| Ash status | `358E:3CE4` / added boolean helper | Distinguish status zero from “none” in down/action/share checks |
| EXP division | ov02:0000 | Avoid zero divisor when nobody is eligible for an award |
| COMP skill EXP | ov16:2CE4, `25CA:AC9E` | Train COMP for COMP-program actions instead of training Magic |

`statfix.py` also records the checked ET0001 adjustments matching equipment descriptions. They are part of the fix, not arbitrary balance choices. The code uses the original decoder and cached runtime fields; a table offset and a runtime item-buffer offset may describe different structures.

## Experience award and display

`expshow.py` corrects MS00DD record 52 to print the actual per-member award rather than the pre-split enemy sum. The value reader is `1603:A71C`, index 4; its helper occupies `1603:4805–4847` after the EXP setter's block.

`expgap.py` preserves the game's split and eligibility checks while applying a level factor per enemy and party member. For enemy level L, member level l and enemy EXP E:

```
g = clamp(L-l, -10, 10)
factor[g] = round(4096 * 2^(g/5))
award = floor(2 * sum(E * factor[g]) / (4096 * eligible_member_count))
```

The defeat hook is `25CA:AA37`; payout lookup is ov02:0029. Runtime original sum is `DS:9B0C`. The level buckets and 48-bit accumulation routines use checked unused space within `1603:4F20–53A0`, preserving relocated words at 4F30 and 513C. The display then reports the protagonist's own gain. Five levels below means ×2, ten or more ×4; five above ×0.5, ten or more ×0.25. Eligibility/status and level-99 handling remain the original game rules.

## Memory and graphics stability

| Module | Site(s) | Purpose |
| --- | --- | --- |
| `ctxfree.py` | `1603:5923` checked tail, changed call at 592C | Free the 12-byte script context node through 7416 instead of only tidying it through 73BE |
| `vmswap.py` | `0871:956C–9754` | Swap the game's virtual-memory resources through XMS instead of V0000.BUF disk writes |
| `nospace.py` | `0871:8AF8` | Skip the palette debug printf, preserve its allocation behavior and relocations |
| `slotorder.py` | hook `0871:8ABB–8ACD`, helper `69C2–6A2B` | Allocate battle enemy colors from high free slots; preserve room-owned colors where the budget permits |
| `worldbackdrop.py`, `battlefield.py` | Checked graphics entries | Consistent world-map and battlefield background treatment |

The palette warning suppression does not create more than sixteen hardware colors. Shared-palette conversion is still required. XMS swapping still needs sufficient emulator memory; it is not a general memory-size detector or an alternate DOS disk driver.

## Rebalance implementation map

The player-facing mathematical specification is [REBALANCE.md](../../REBALANCE.md); the actual assembled code, constants and rounding are in `rebalance.py`. Existing [REFERENCE.md](../../REFERENCE.md) lists skill pools and numerical adjustments. Keep these connected instead of writing a second combat simulator as the patch authority.

| Block | Reference routine(s) | Rule area |
| --- | --- | --- |
| W1 | `358E:296E` | Derived hit/attack/evasion values, stats, route and COMP contributions |
| W2 | `358E:4314` | Maximum HP |
| W3 | `358E:1992` | Speed and armor weight; Strength bears the penalty |
| W4 | ov16:0B40 and 3732 | Physical hit and graze probabilities |
| W5 | ov16:0D04 and 390E; later swings 07BC | Physical damage, critical multiplier and repeated swings |
| W6 | ov16:0964 and 3556 | Criticals and instant kills |
| W7 | ov16:2E22 | Magic accuracy |
| W8 | ov16:3070 | Magic damage |
| W9 | `25CA:8E68` | `sqrt(v/50)` moon multiplier |
| W10 | `358E:0252` | Healing and special heal fractions |
| W11 | ov02:0272,0FBC and helper in segment 1603 | Growth toward lower attributes while preserving the original point award paths |
| Summon action | `358E` assembled label `summon_swap` | COMP holder's action interval for battle summoning |
| W13 | ov16:390E and gun-panel helper | Gun attack terms and displayed values |
| W14 | `25CA:AF8F` | Buff/debuff effects on COMP attack and accuracy |
| W15 | ov16:2E22,3070,323E | COMP program hit/attack integration |
| W16 | `1603:8844` | COMP level contribution in negotiation checks |

[Rebalance-Labels.json](Rebalance-Labels.json) contains **assembled offsets**, grouped by source labels; labels from different blocks can share the same numeric offset. Consult the corresponding block/segment in `rebalance.py` before converting an offset to a file position. It is not a global symbol table of unique linear addresses.

Examples of implemented rules: HP is `floor(min(9999, 5 + Grace + Luck + Lv*(0.99 + 0.297*Vitality + 0.198*Lv)))`; speed is `max(1, round(4*sqrt(Agility) - 0.25*armor/max(1,sqrt(Strength))))`; base physical damage is `0.5227*A^2/(A+max(1,D))`, before the documented multipliers; magic uses `1.9008*S^2/(S+max(1,M))`. Exact clamping, single-precision calculations, integer rounding and random thresholds must be read with the source and CPU tests, not approximated by replacing coefficients in the original routines.

## Code-space ownership and future executables

Known Fixes helper ranges include `25CA:E2E1–E410`, `1603:4288–4303`, `358E:639C–63F9`, EXP setter/display `1603:47F4–4847`, keyboard `25CA:9398`'s unused block, and the ranges listed in their modules. They were established against the reference by branch/call/pointer/relocation analysis and completed execution traces.

They are **occupied by Redux**, and are not a generic free-space list for another mod. Rebalance builds on the Fixes byte states and places its assembled blocks around existing relocated words. A changed English executable must be re-analyzed and its expected states regenerated; structural script matching cannot make machine-code offsets portable automatically.

## Optional control hooks and target-selection pause

[Controls and target pause](CONTROLS.md) describes the runtime COM launcher, target question record, checked overlay/main-image sites and language detection. The executable-site CSV includes `holdshow` and `targetprompt` directly from their authoritative definitions; the controller launcher assembles its own annotated code and labels in `gamepad.py`.
