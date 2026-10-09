# Fixes and convenience features

Fixes repairs gameplay defects and adds convenience features while retaining the original Japanese game text and native font. The battle formulas remain those of the original game after correcting the implementation defects below. Rebalance is a separate, optional package.

**Input compatibility:** supported Japanese HDIs only. An English-translated HDI is not supported: this package checks exact file hashes and installs complete Japanese executable, script and data files. It does not merge or preserve an English translation in those replaced files.

## Inventory and stability

- Prevents blank inventory entries created when a disarmed weapon is equipped again. The repair acts on the game program; existing DOS files and boot scripts are preserved.
- Expands the ordinary inventory from 48 to 111 slots. The separate 16 body-part slots remain unchanged. Original saves load with the extra slots empty.
- Releases script context memory after use. The original leak could exhaust memory during prolonged play or automatic battles.
- Moves the game's temporary memory-compaction swap from disk to XMS. This removes the dependency on a `DDS98\VM` directory that could be missing after restoring a save state onto a fresh disk, producing a `VM double fault` exit. An XMS-capable DOS setup remains required; this is not a general promise of emulator save-state compatibility.

## Eight story repairs

1. Jukai appears at Gokokuji after Baal Hadad is defeated even if the party leaves Chuu by teleportation.
2. Event tiles are checked after every step, so walking backwards cannot bypass guards or other events that pushed the party back.
3. The old Shimbashi subway platform returns the party to the north side facing Ginza when entry is refused outside the new moon, preventing a pushback loop.
4. Entering the sickroom during the Hatsudai escape no longer repeats the B8F purification briefing.
5. Takeminakata's negotiations at the waterfront arena require accepting Amaterasu's proposal first.
6. Rainbow Bridge remains available to the party already acting as Amaterasu's envoys when Decarabia kills Hiruko, preserving access to Ariake.
7. After the Harajuku rescue, serious injuries trigger the intended doctor's dialogue and transfer to the administration section, instead of leaving its doors locked.
8. Teleporting into the Shinjuku ground-zero arena cannot bypass reception and take Sonoda into the Adonis duel with Rui, which previously left Sonoda permanently in the party.

## Story checks and rewards

Seven checks originally replace an intended small random threshold with a random number from 0 to 32,767, although attributes cannot exceed 100. They now use the intended threshold. Affected events include the Baal fusion ending, the DB practical test's gun actions, responding to Emi while secluded, and looking at Rui when she brings food.

Two Rui dialogue choices now apply the intended +2/-2 affection changes without falling through into another answer's -1/+1 adjustment. Wendy, Miranda and Josephine correctly award their intended 20, 30 and 3,000 EXP; if a reward crosses a level threshold, the next EXP gain processes the level-up.

## Attributes, equipment, items and EXP

- Eleven weapons/armor pieces now grant their intended attribute bonuses instead of repeatedly increasing base Luck during recalculation. Accessories target their specified attributes instead of all targeting Luck; unspecified Luck accessories retain their original effect.
- Weapon magic accuracy and the barrier unit's magic evasion take effect. Three armor effects that doubled a nonexistent accuracy contribution instead double that item's evasion contribution.
- Gun critical modifiers are counted. Sword and gun skills read the critical modifier of the weapon actually used.
- Attack items use their own power, accuracy, element and additional effects, with the user's magic accuracy. Status items apply their specified statuses.
- Scripted attribute rewards and penalties modify the base value without permanently baking in a cap or temporary halving effect.
- Corrects two 16-bit overflow cases in status-infliction checks and a 150% multiplier. Heavy armor cannot underflow action speed into a huge positive number; minimum speed is 1.
- The ash state counts as incapacitated, and battle EXP distribution handles a party with no eligible recipients without dividing by zero.
- Successful COMP attack programs award COMP skill EXP instead of magic skill EXP, at three points per hit.
- The battle summary reports the EXP each eligible party member actually receives. The ordinary distribution remains total defeated-enemy EXP × 2 ÷ eligible members. Fixes alone does not include the optional level-gap EXP system; Rebalance does.

## Attack skills

The previously zero-power handgun, shotgun, machine gun and laser gun templates now function as gun attacks. They consume HP rather than ammunition and use gun accuracy. Handgun fires twice at one target; shotgun attacks each target in the chosen group; machine gun fires four to six shots among that group; laser gun penetrates the target and the two positions behind it.

Bomb attacks up to three targets in its group and costs 5 HP. Gun skills, including Bomb and enemy projectile skills, use the gun's attack contribution without ammunition power. Ordinary gunshots still use ammunition, and the status screen still displays gun plus ammunition power. The Execution Rider receives its intended Type 89 rifle.

Previously ineffective zero-power physical templates, including sword, blunt, thrust and whip attacks, become real physical attacks. The executable also deducts costs for the affected low-numbered skills.

## Dialogue and graphics repairs

- Adds a click-to-continue wait to the last line of 843 dialogue passages that previously closed immediately.
- Adds 23 missing demon-negotiation prompts, written in Japanese to fit their speakers. These are newly supplied prompts, not a claim to recovered official dialogue.
- Removes the ceiling/floor flash just before overworld battles fade out, using a black texture.
- Supplies neighboring area's battle backdrops where roughly a quarter of overworld areas otherwise specified none.
- Suppresses the persistent `no space` palette debug text.
- Allocates enemy palettes from the high end, reducing battle-background recoloring when the combined content fits the engine's six usable palette slots. The hardware palette budget still applies.

## Convenience changes included in Fixes

**Keyboard:** W/Z/A/D move forward/back/left/right, Q/E turn left/right, and S turns around. Enter or Space advances dialogue and battle-message waits. Menus still use the mouse. See `TROUBLESHOOTING.md`.

**Message pacing:** battle messages pause for approximately one second after being drawn; clicking or pressing an advance key can shorten a wait.

**Dantalion's second form:** fire, ice, force and electricity damage multipliers change from 40% to 60%, matching the final form. A larger percentage means more damage passes through.

**Faster moon:** the visible phase changes after about 60 steps instead of about 300. Moon-dependent battles, negotiation and events follow the faster phase. Monthly chests, refillable Soma/Kushinada vessels, the core shield duration and body-part drying limits retain their original time scale. The vessels refill on an eligible full moon after the original monthly interval; they cannot be farmed every accelerated cycle. The core shield description is adjusted in Japanese to reflect a duration of at most about one day.

These features are installed together. The standalone artwork patch is not required for any of them.
