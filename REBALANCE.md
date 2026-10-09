# Rebalance

Apply **Fixes first**, then select that output in `Apply Rebalance.html`. Windows Artwork may be installed before or after this step. This package redesigns combat and progression while retaining Japanese game text.

## What changes

Rebalance replaces derived battle-stat formulas, hit/damage curves, critical hits and some progression rules. It retunes bosses and strengthens Newton and his equipment, expands the protagonist's learning pools, makes combat summoning cost an action, and adjusts EXP by level difference. All underlying Fixes repairs remain installed.

`REFERENCE.md` contains the exact derived-stat formulas and a complete numerical ledger generated from the authoritative balance data. IDs refer to the original game's records; names that appear in Japanese are included for matching them to the game.

## Derived stats and leadership

Attributes and character level contribute more strongly relative to equipment. Equipment contributions use the same weights for humans, demons, allies and enemies: sword attack ×0.3, sword accuracy ×0.8, sword evasion ×0.5, defense ×0.75 and gun attack ×0.5. Gun accuracy/evasion and magic contributions retain full weight. These weights are already included in the reference formulas; do not apply them twice.

Human skill levels add attack to their matching category: sword +0.25 per level, gun +0.5, magic +0.5 and COMP +0.75. Demons have no such human skill levels.

If the protagonist has awakened COMP, allied demons use the protagonist's Charm as leadership `L`; other combatants use zero. Leadership adds 0.25L to accuracy/evasion and multiplies the indicated attack values by `(2000 + L) / 2000`. Derived values are rounded once and limited to 1–999 before the game's subsequent modifiers.

## HP, MP, healing and speed

- Party maximum HP = `5 + Grace + Luck + level × (0.99 + 0.297 × Vitality + 0.198 × level)`. The HP-doubling state and 9,999 cap remain; enemies use their recorded HP.
- Maximum MP is unchanged: `min(999, 1.5 × Magic × sqrt(level) + 0.5 × (Willpower + Charm))`.
- Healing = `power + 0.75 × Magic + sqrt(Magic)`, then the original random factor of 80–120%.
- Action speed = `4 × sqrt(Agility) − 0.25 × armor weight / max(1, sqrt(Strength))`, with a minimum of 1. Strength replaces Vitality as the weight-bearing attribute.

## Physical attacks

Hit chance = `1 / (1 + (0.4 × evasion / accuracy)^2)`, limited to 5–97%. Half of missed attacks become grazes. The inputs already include the game's applicable blindness, position and other modifiers.

Base damage = `0.5227 × attack^2 / (attack + max(1, defense))`. Critical damage is ×2.5. Subsequent hits of an ordinary sword attack are halved. Existing immobility, position, graze, skill, moon and random modifiers still apply; graze damage is ×0.25, and the random factor remains 80–120%.

Gun attack = `(0.5 × base + 5 × gunDexterity + 0.5 × level + 0.5 × gunSkillLevel) × (2000 + L) / 2000`. For a human with an equipped gun, `gunDexterity` is Dexterity; otherwise it is zero. Ordinary shots use the current shot's power; special gun attacks use the gun contribution without ammunition. Special gun attack output is scaled by ×0.4, or ×0.35 for machine gun. The derived gun attack is clamped to 1–999 before subsequent buffs.

## Critical hits and instant death

Critical probability = `clamp(0.03 + 0.04 × (attacker Intuition + 0.5 × attacker Intelligence − defender Grace) + 0.0025 × B, 0, 0.35)`, where `B` is weapon critical modifier minus armor critical protection. Critical hits are tested for each attack without the original moon gate.

For the instant-death comparison, `K = (Intuition + 0.5 × Intelligence) / 2 + Luck`. Probability = `0.30 × clamp(attacker K / defender K − 1, 0, 1)`. Its original moon gate remains: the original 0–255 random draw must be below `(((moonAge + 13) mod 14 + 1)^2) / 4`. Allies cannot instantly kill enemies in a boss battle; enemy instant-death attempts retain the game's existing eligibility checks.

## Magic and COMP programs

Magic hit chance = `1 / (1 + (0.8 × magic evasion / S')^2)`, limited to 5–97%. Here `S' = (skill accuracy + magic accuracy) × (1 − attenuation) × R / 50`. `R` is the skill's multiplier code: negative values use 50, while zero means no hit.

Magic base damage = `1.9008 × S^2 / (S + max(1, magic defense))`, where `S = (0.5 × skill power + magic attack) × (1 − attenuation)`. The existing additional damage modifiers remain.

COMP attack programs use COMP accuracy and COMP attack in these formulas rather than magic accuracy/attack. Magic attack and accuracy buffs/debuffs also affect the corresponding COMP values by the same increment. COMP additions are excluded from the game's sum used to report that a buff has no effect; the six groups' original increments remain unchanged.

## Moon damage

The damage multiplier becomes `sqrt(v / 50)` instead of `2v / 100`, using the attacker's existing moon-age table value `v`. This applies to sword, gun and magic damage. Examples: `v=10` gives about ×0.447, `50` gives ×1, `100` gives about ×1.414, and `200` gives ×2.

Instant-death moon gates and full-moon refusal to negotiate retain their original rules. The faster visible moon from Fixes remains active.

## Growth and learning

One quarter of inclination growth points is redirected to the currently lowest attribute, taking the first in attribute order on a tie. If that minimum is capped, the original reroll behavior applies. Humans additionally gain one Vitality every third level, shown on the level-up screen. Existing hidden Luck growth remains: humans on even levels, demons every third level.

The magic route gains the Megi line, and the gun route gains a dedicated learning pool. See `REFERENCE.md` for the exact lists and IDs. Acquisition still uses the game's existing level-up checks; eligibility does not guarantee learning a skill on that exact level.

## Summoning, battle entry and negotiation

Summoning a demon from COMP during battle consumes one action of the COMP holder: the protagonist, or Emi if the protagonist is absent or unable to act. A character already counting down waits an additional action interval. Summoning outside battle remains free.

At each battle's start, derived stats, maximum HP/MP and speed are recalculated for everyone. This lets existing in-game saves pick up the new formulas; it does not retroactively redistribute past level-up points.

During negotiation, the protagonist's Intuition, Magic, Intelligence, Agility, Dexterity, Charm and Luck checks use `attribute × (100 + C) / 100`, where `C` is COMP level. The recruitment level gate uses `protagonist level × (200 + C) / 200`. Willpower, Strength, Vitality and Grace receive no such boost, and demon-side values and other conditions remain unchanged.

## Level-gap EXP

For every defeated enemy and every eligible member, multiply the enemy's EXP by `2^(clamp(enemy level − member level, −10, 10) / 5)`, then retain the ordinary ×2 and division by the eligible-member count. Five levels below the enemy gives ×2, ten or more gives ×4; five above gives ×0.5, ten or more gives ×0.25. Equal levels give ×1.

The summary reports the protagonist's actual award, since party members can receive different amounts. Eligibility rules remain, including incapacitation and the level-99 limit.

## Content tuning and unchanged systems

The package includes all 36 record edits in the rebalanced boss/Newton equipment plan, plus the shared Dantalion correction already installed by Fixes. The ledger gives original and replacement values by record and field. Newton's skill set includes attacks, a COMP program and resurrection support; his three special equipment records are also strengthened.

| Newton's starting equipment | Adjustments |
| --- | --- |
| 10 mm composite armor, item 438 | Defense 10 → 38; evasion 7 → 12; magic defense 5 → 24; critical protection 15 → 40 |
| Newton Blade, item 733 | Attack 11 → 45; accuracy 10 → 35; critical modifier 7 → 15; maximum hits 2 → 3; magic accuracy 0 → 25; magic attack 0 → 18 |
| Neutron, item 744 | Attack 15 → 45; accuracy 22 → 40; critical modifier 10 → 12; magazine 20 → 60; six shots that can be distributed among one to six targets |

Status sources/caps, MP rules, status effects, existing resistance mechanics, encounter/flee rules, story checks, chests, bargaining and terminal behavior retain their existing logic except for the explicit Fixes repairs and numerical edits. Rebalance is a designed alternate ruleset, not a promise that every play style has identical difficulty.
