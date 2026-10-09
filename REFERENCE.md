# Formula and data reference

## Derived battle stats

Generated from the same coefficients used to patch the executable. Multiplications shown here already include equipment weights.

| Statistic | Formula |
| --- | --- |
| Sword accuracy | `Agility + 0.5 * Dexterity + 0.25 * Intuition + 0.125 * Intelligence + 0.8 * equipmentSwordAccuracy + 0.25 * L` |
| Sword attack | `(2 * Strength + 0.3 * equipmentSwordAttack + 0.5 * level + 0.25 * swordSkillLevel) * (2000 + L) / 2000` |
| Sword evasion | `Agility + Intuition + 0.5 * Intelligence + 0.5 * equipmentEvasion + 0.25 * L` |
| Physical defense | `Vitality + 0.4 * Grace + 0.75 * equipmentDefense` |
| Gun accuracy | `Dexterity + 0.2 * Intuition + 0.1 * Intelligence + equipmentGunAccuracy + gunLevelBonus + 0.25 * L` |
| Gun attack (status screen) | `(0.5 * equipmentGunAndAmmoAttack + 5 * gunDexterity + 0.5 * level + 0.5 * gunSkillLevel) * (2000 + L) / 2000` |
| Gun evasion | `0.9 * Intuition + 0.45 * Intelligence + 0.4 * Grace + equipmentEvasion + 0.25 * L` |
| Magic accuracy | `0.75 * Intelligence + 0.25 * Magic + equipmentMagicAccuracy + 0.25 * L` |
| Magic attack | `(1.75 * Magic + equipmentMagicAttack + 0.5 * level + 0.5 * magicSkillLevel) * (2000 + L) / 2000` |
| Magic evasion | `0.25 * Intelligence + 0.5 * Grace + 0.5 * Willpower + equipmentMagicEvasion + 0.25 * L` |
| Magic defense | `0.8 * Willpower + 0.4 * Grace + equipmentMagicDefense` |
| COMP accuracy | `0.75 * Intelligence + 0.25 * Charm + equipmentMagicAccuracy + 0.25 * L` |
| COMP attack | `(Intelligence + 1.25 * Charm + equipmentMagicAttack + level + 0.75 * COMPSkillLevel) * (2000 + L) / 2000` |

`gunLevelBonus` is `2 * (gunSkillLevel + 5)` when that skill level is at least 1, otherwise zero. `gunDexterity` is Dexterity for a human with an equipped gun, otherwise zero. `L` is the protagonist's Charm for allied demons when the protagonist has awakened COMP, otherwise zero. Skill levels in these formulas are human skill levels; demons use zero.

The game rounds the total once and clamps derived values to 1–999. HP, damage, hit probability, growth, negotiation and other rules are described in REBALANCE.md.

## Added learning candidates

Japanese labels identify the original skill names; record IDs also apply to the English translation. The gun route's learn thresholds are 1, 5, 5, 10, 15, 20, 25, 35 and 35, in the order below. The original learning roll still decides acquisition.

| Route | Skill ID | In-game name |
| --- | --- | --- |
| Magic | 52 | メギ |
| Magic | 53 | メギド |
| Magic | 54 | メギドラオン |
| Gun | 247 | ボンブ |
| Gun | 3 | ハンドガン |
| Gun | 31 | ダーム |
| Gun | 32 | ダムド |
| Gun | 9 | ショットガン |
| Gun | 33 | ダムドーラ |
| Gun | 4 | マシンガン |
| Gun | 34 | ダムドラオン |
| Gun | 10 | レーザーガン |

## Complete numerical edit ledger

This ledger includes the shared Dantalion adjustment and every boss/Newton edit from the rebalanced data plan. Before/after values are the stored integer values against the original Japanese records. Resistance bytes below 250 represent twice their value as a damage percentage; 250–255 are special codes, not ordinary percentages. Skill/equipment values are record IDs. Japanese names identify the source records; the same record IDs are used in the English translation. The same rows are available in Rebalance-Changes.csv. Executable formulas and learning-pool additions are documented separately above.

| Profile | Record | In-game name | Field / record offset | Width | Original | Patched |
| --- | --- | --- | --- | --- | --- | --- |
| Fixes | P2177 | ダンタリオン | Fire resistance code @0x5B | u8 | 20 | 30 |
| Fixes | P2177 | ダンタリオン | Ice resistance code @0x5C | u8 | 20 | 30 |
| Fixes | P2177 | ダンタリオン | Force resistance code @0x5D | u8 | 20 | 30 |
| Fixes | P2177 | ダンタリオン | Electricity resistance code @0x5E | u8 | 20 | 30 |
| Rebalance | ET0001#438 | １０ミリ複合装甲 | Equipment data @0x09 | u8 | 10 | 38 |
| Rebalance | ET0001#438 | １０ミリ複合装甲 | Equipment data @0x0A | u8 | 7 | 12 |
| Rebalance | ET0001#438 | １０ミリ複合装甲 | Equipment data @0x0B | u8 | 5 | 24 |
| Rebalance | ET0001#438 | １０ミリ複合装甲 | Equipment data @0x0C | u8 | 15 | 40 |
| Rebalance | ET0001#733 | ニュートンブレイド | Equipment data @0x09 | u8 | 11 | 45 |
| Rebalance | ET0001#733 | ニュートンブレイド | Equipment data @0x0B | u8 | 10 | 35 |
| Rebalance | ET0001#733 | ニュートンブレイド | Equipment data @0x0C | u8 | 7 | 15 |
| Rebalance | ET0001#733 | ニュートンブレイド | Equipment data @0x10 | u8 | 2 | 3 |
| Rebalance | ET0001#733 | ニュートンブレイド | Equipment data @0x1C | u8 | 0 | 25 |
| Rebalance | ET0001#733 | ニュートンブレイド | Equipment data @0x1D | u8 | 0 | 18 |
| Rebalance | ET0001#744 | ニュートロン | Equipment data @0x09 | u8 | 15 | 45 |
| Rebalance | ET0001#744 | ニュートロン | Equipment data @0x0A | u8 | 22 | 40 |
| Rebalance | ET0001#744 | ニュートロン | Equipment data @0x0B | u8 | 10 | 12 |
| Rebalance | ET0001#744 | ニュートロン | Equipment data @0x11 | u8 | 20 | 60 |
| Rebalance | ET0001#744 | ニュートロン | Equipment data @0x12 | u8 | 1 | 6 |
| Rebalance | ET0001#744 | ニュートロン | Equipment data @0x13 | u8 | 17 | 22 |
| Rebalance | P200D | ニュートン | Skill slot 1 @0x10 | u16 | 184 | 144 |
| Rebalance | P200D | ニュートン | Skill slot 2 @0x12 | u16 | 186 | 38 |
| Rebalance | P200D | ニュートン | Skill slot 3 @0x14 | u16 | 259 | 19 |
| Rebalance | P200D | ニュートン | Skill slot 4 @0x16 | u16 | 142 | 163 |
| Rebalance | P200D | ニュートン | Skill slot 5 @0x18 | u16 | 0 | 259 |
| Rebalance | P200D | ニュートン | Skill slot 6 @0x1A | u16 | 0 | 41 |
| Rebalance | P200D | ニュートン | Skill slot 7 @0x1C | u16 | 0 | 112 |
| Rebalance | P200D | ニュートン | Skill slot 8 @0x1E | u16 | 0 | 113 |
| Rebalance | P2021 | バールハダド | Magic @0x4E | u8 | 47 | 94 |
| Rebalance | P2021 | バールハダド | Intelligence @0x4F | u8 | 46 | 92 |
| Rebalance | P2021 | バールハダド | Enemy speed @0x66 | u8 | 18 | 31 |
| Rebalance | P2021 | バールハダド | AI action row @0x6A | u8 | 7 | 8 |
| Rebalance | P2021 | バールハダド | HP @0x0C | u16 | 5276 | 7914 |
| Rebalance | P2021 | バールハダド | Skill slot 1 @0x10 | u16 | 38 | 297 |
| Rebalance | P2021 | バールハダド | Skill slot 2 @0x12 | u16 | 41 | 305 |
| Rebalance | P2021 | バールハダド | Skill slot 3 @0x14 | u16 | 305 | 41 |
| Rebalance | P2021 | バールハダド | Skill slot 4 @0x16 | u16 | 156 | 38 |
| Rebalance | P2021 | バールハダド | Skill slot 6 @0x1A | u16 | 76 | 83 |
| Rebalance | P2021 | バールハダド | Skill slot 7 @0x1C | u16 | 0 | 85 |
| Rebalance | P2021 | バールハダド | Skill slot 8 @0x1E | u16 | 0 | 76 |
| Rebalance | P2045 | トヨタマヒメ | Intuition @0x4C | u8 | 61 | 48 |
| Rebalance | P2045 | トヨタマヒメ | Willpower @0x4D | u8 | 46 | 36 |
| Rebalance | P2045 | トヨタマヒメ | Magic @0x4E | u8 | 55 | 43 |
| Rebalance | P2045 | トヨタマヒメ | Intelligence @0x4F | u8 | 63 | 50 |
| Rebalance | P2045 | トヨタマヒメ | Grace @0x50 | u8 | 77 | 61 |
| Rebalance | P2045 | トヨタマヒメ | Strength @0x51 | u8 | 80 | 63 |
| Rebalance | P2045 | トヨタマヒメ | Vitality @0x52 | u8 | 93 | 73 |
| Rebalance | P2045 | トヨタマヒメ | Agility @0x53 | u8 | 54 | 43 |
| Rebalance | P2045 | トヨタマヒメ | Dexterity @0x54 | u8 | 56 | 44 |
| Rebalance | P2045 | トヨタマヒメ | Charm @0x55 | u8 | 92 | 73 |
| Rebalance | P2045 | トヨタマヒメ | HP @0x0C | u16 | 1952 | 1633 |
| Rebalance | P2045 | トヨタマヒメ | MP @0x0E | u16 | 590 | 462 |
| Rebalance | P204C | ジャターユ | Intuition @0x4C | u8 | 35 | 24 |
| Rebalance | P204C | ジャターユ | Willpower @0x4D | u8 | 35 | 24 |
| Rebalance | P204C | ジャターユ | Magic @0x4E | u8 | 42 | 29 |
| Rebalance | P204C | ジャターユ | Intelligence @0x4F | u8 | 25 | 17 |
| Rebalance | P204C | ジャターユ | Grace @0x50 | u8 | 33 | 23 |
| Rebalance | P204C | ジャターユ | Strength @0x51 | u8 | 50 | 34 |
| Rebalance | P204C | ジャターユ | Vitality @0x52 | u8 | 49 | 33 |
| Rebalance | P204C | ジャターユ | Agility @0x53 | u8 | 44 | 30 |
| Rebalance | P204C | ジャターユ | Dexterity @0x54 | u8 | 20 | 14 |
| Rebalance | P204C | ジャターユ | Charm @0x55 | u8 | 56 | 38 |
| Rebalance | P204C | ジャターユ | HP @0x0C | u16 | 777 | 609 |
| Rebalance | P204C | ジャターユ | MP @0x0E | u16 | 384 | 265 |
| Rebalance | P2055 | アピス | Intuition @0x4C | u8 | 43 | 29 |
| Rebalance | P2055 | アピス | Willpower @0x4D | u8 | 34 | 23 |
| Rebalance | P2055 | アピス | Magic @0x4E | u8 | 22 | 15 |
| Rebalance | P2055 | アピス | Intelligence @0x4F | u8 | 25 | 17 |
| Rebalance | P2055 | アピス | Grace @0x50 | u8 | 45 | 31 |
| Rebalance | P2055 | アピス | Strength @0x51 | u8 | 59 | 40 |
| Rebalance | P2055 | アピス | Vitality @0x52 | u8 | 47 | 32 |
| Rebalance | P2055 | アピス | Agility @0x53 | u8 | 45 | 31 |
| Rebalance | P2055 | アピス | Dexterity @0x54 | u8 | 25 | 17 |
| Rebalance | P2055 | アピス | Charm @0x55 | u8 | 24 | 16 |
| Rebalance | P2055 | アピス | HP @0x0C | u16 | 483 | 367 |
| Rebalance | P2055 | アピス | MP @0x0E | u16 | 169 | 115 |
| Rebalance | P208C | ヤト | Intuition @0x4C | u8 | 24 | 14 |
| Rebalance | P208C | ヤト | Willpower @0x4D | u8 | 22 | 12 |
| Rebalance | P208C | ヤト | Magic @0x4E | u8 | 27 | 15 |
| Rebalance | P208C | ヤト | Intelligence @0x4F | u8 | 19 | 11 |
| Rebalance | P208C | ヤト | Grace @0x50 | u8 | 18 | 10 |
| Rebalance | P208C | ヤト | Strength @0x51 | u8 | 33 | 19 |
| Rebalance | P208C | ヤト | Vitality @0x52 | u8 | 33 | 19 |
| Rebalance | P208C | ヤト | Agility @0x53 | u8 | 31 | 17 |
| Rebalance | P208C | ヤト | Dexterity @0x54 | u8 | 15 | 8 |
| Rebalance | P208C | ヤト | Charm @0x55 | u8 | 26 | 15 |
| Rebalance | P208C | ヤト | HP @0x0C | u16 | 247 | 173 |
| Rebalance | P208C | ヤト | MP @0x0E | u16 | 170 | 95 |
| Rebalance | P2098 | タムズ | Magic @0x4E | u8 | 20 | 50 |
| Rebalance | P2098 | タムズ | Intelligence @0x4F | u8 | 15 | 38 |
| Rebalance | P2098 | タムズ | Strength @0x51 | u8 | 61 | 99 |
| Rebalance | P2098 | タムズ | Enemy speed @0x66 | u8 | 16 | 62 |
| Rebalance | P2098 | タムズ | HP @0x0C | u16 | 5100 | 6000 |
| Rebalance | P2098 | タムズ | Skill slot 1 @0x10 | u16 | 299 | 182 |
| Rebalance | P2098 | タムズ | Skill slot 2 @0x12 | u16 | 33 | 293 |
| Rebalance | P2098 | タムズ | Skill slot 3 @0x14 | u16 | 67 | 198 |
| Rebalance | P2098 | タムズ | Skill slot 4 @0x16 | u16 | 198 | 33 |
| Rebalance | P2098 | タムズ | Skill slot 5 @0x18 | u16 | 293 | 299 |
| Rebalance | P2098 | タムズ | Equipment slot 4 @0x28 | u16 | 0 | 701 |
| Rebalance | P20ED | アドニス | Level @0x47 | u8 | 46 | 55 |
| Rebalance | P20ED | アドニス | Intuition @0x4C | u8 | 28 | 31 |
| Rebalance | P20ED | アドニス | Willpower @0x4D | u8 | 42 | 46 |
| Rebalance | P20ED | アドニス | Magic @0x4E | u8 | 34 | 92 |
| Rebalance | P20ED | アドニス | Intelligence @0x4F | u8 | 29 | 80 |
| Rebalance | P20ED | アドニス | Grace @0x50 | u8 | 12 | 13 |
| Rebalance | P20ED | アドニス | Strength @0x51 | u8 | 43 | 70 |
| Rebalance | P20ED | アドニス | Vitality @0x52 | u8 | 38 | 42 |
| Rebalance | P20ED | アドニス | Agility @0x53 | u8 | 36 | 39 |
| Rebalance | P20ED | アドニス | Dexterity @0x54 | u8 | 20 | 22 |
| Rebalance | P20ED | アドニス | Charm @0x55 | u8 | 31 | 34 |
| Rebalance | P20ED | アドニス | Luck @0x56 | u8 | 7 | 8 |
| Rebalance | P20ED | アドニス | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P20ED | アドニス | Curse resistance code @0x61 | u8 | 0 | 50 |
| Rebalance | P20ED | アドニス | Enemy speed @0x66 | u8 | 17 | 47 |
| Rebalance | P20ED | アドニス | HP @0x0C | u16 | 3592 | 5927 |
| Rebalance | P20ED | アドニス | MP @0x0E | u16 | 1528 | 1820 |
| Rebalance | P20ED | アドニス | Skill slot 1 @0x10 | u16 | 79 | 61 |
| Rebalance | P20ED | アドニス | Skill slot 2 @0x12 | u16 | 80 | 202 |
| Rebalance | P20ED | アドニス | Skill slot 3 @0x14 | u16 | 156 | 297 |
| Rebalance | P20ED | アドニス | Skill slot 4 @0x16 | u16 | 292 | 41 |
| Rebalance | P20ED | アドニス | Skill slot 6 @0x1A | u16 | 41 | 292 |
| Rebalance | P20ED | アドニス | Skill slot 7 @0x1C | u16 | 81 | 76 |
| Rebalance | P20F3 | アドニス | Strength @0x51 | u8 | 21 | 24 |
| Rebalance | P20F3 | アドニス | Enemy speed @0x66 | u8 | 15 | 27 |
| Rebalance | P20F3 | アドニス | HP @0x0C | u16 | 207 | 248 |
| Rebalance | P20F3 | アドニス | Skill slot 1 @0x10 | u16 | 296 | 37 |
| Rebalance | P20F3 | アドニス | Skill slot 2 @0x12 | u16 | 198 | 296 |
| Rebalance | P20F3 | アドニス | Skill slot 3 @0x14 | u16 | 149 | 198 |
| Rebalance | P20F3 | アドニス | Skill slot 4 @0x16 | u16 | 201 | 149 |
| Rebalance | P20F3 | アドニス | Skill slot 5 @0x18 | u16 | 37 | 201 |
| Rebalance | P20F3 | アドニス | Equipment slot 1 @0x22 | u16 | 0 | 482 |
| Rebalance | P20F3 | アドニス | Equipment slot 2 @0x24 | u16 | 0 | 532 |
| Rebalance | P20F3 | アドニス | Equipment slot 3 @0x26 | u16 | 0 | 616 |
| Rebalance | P20F3 | アドニス | Equipment slot 4 @0x28 | u16 | 0 | 658 |
| Rebalance | P20F4 | アドニス | Level @0x47 | u8 | 18 | 23 |
| Rebalance | P20F4 | アドニス | Intuition @0x4C | u8 | 16 | 18 |
| Rebalance | P20F4 | アドニス | Willpower @0x4D | u8 | 21 | 24 |
| Rebalance | P20F4 | アドニス | Magic @0x4E | u8 | 17 | 19 |
| Rebalance | P20F4 | アドニス | Intelligence @0x4F | u8 | 16 | 18 |
| Rebalance | P20F4 | アドニス | Grace @0x50 | u8 | 6 | 7 |
| Rebalance | P20F4 | アドニス | Strength @0x51 | u8 | 20 | 58 |
| Rebalance | P20F4 | アドニス | Vitality @0x52 | u8 | 18 | 20 |
| Rebalance | P20F4 | アドニス | Agility @0x53 | u8 | 18 | 20 |
| Rebalance | P20F4 | アドニス | Dexterity @0x54 | u8 | 10 | 11 |
| Rebalance | P20F4 | アドニス | Charm @0x55 | u8 | 15 | 17 |
| Rebalance | P20F4 | アドニス | Luck @0x56 | u8 | 4 | 5 |
| Rebalance | P20F4 | アドニス | Magic resistance code @0x60 | u8 | 10 | 50 |
| Rebalance | P20F4 | アドニス | Enemy speed @0x66 | u8 | 15 | 31 |
| Rebalance | P20F4 | アドニス | AI action row @0x6A | u8 | 12 | 27 |
| Rebalance | P20F4 | アドニス | HP @0x0C | u16 | 177 | 2549 |
| Rebalance | P20F4 | アドニス | MP @0x0E | u16 | 126 | 160 |
| Rebalance | P20F4 | アドニス | Skill slot 1 @0x10 | u16 | 296 | 85 |
| Rebalance | P20F4 | アドニス | Skill slot 2 @0x12 | u16 | 198 | 37 |
| Rebalance | P20F4 | アドニス | Skill slot 3 @0x14 | u16 | 129 | 151 |
| Rebalance | P20F4 | アドニス | Skill slot 4 @0x16 | u16 | 149 | 198 |
| Rebalance | P20F4 | アドニス | Skill slot 5 @0x18 | u16 | 37 | 296 |
| Rebalance | P20F4 | アドニス | Skill slot 6 @0x1A | u16 | 154 | 149 |
| Rebalance | P20F4 | アドニス | Skill slot 7 @0x1C | u16 | 256 | 129 |
| Rebalance | P20F4 | アドニス | Skill slot 8 @0x1E | u16 | 130 | 254 |
| Rebalance | P20F4 | アドニス | Equipment slot 1 @0x22 | u16 | 0 | 477 |
| Rebalance | P20F4 | アドニス | Equipment slot 3 @0x26 | u16 | 0 | 614 |
| Rebalance | P20F4 | アドニス | Equipment slot 4 @0x28 | u16 | 0 | 655 |
| Rebalance | P20F8 | アリス | Level @0x47 | u8 | 28 | 34 |
| Rebalance | P20F8 | アリス | Intuition @0x4C | u8 | 20 | 22 |
| Rebalance | P20F8 | アリス | Willpower @0x4D | u8 | 28 | 31 |
| Rebalance | P20F8 | アリス | Magic @0x4E | u8 | 23 | 59 |
| Rebalance | P20F8 | アリス | Intelligence @0x4F | u8 | 20 | 59 |
| Rebalance | P20F8 | アリス | Grace @0x50 | u8 | 8 | 9 |
| Rebalance | P20F8 | アリス | Strength @0x51 | u8 | 28 | 31 |
| Rebalance | P20F8 | アリス | Vitality @0x52 | u8 | 25 | 28 |
| Rebalance | P20F8 | アリス | Agility @0x53 | u8 | 25 | 28 |
| Rebalance | P20F8 | アリス | Dexterity @0x54 | u8 | 14 | 15 |
| Rebalance | P20F8 | アリス | Charm @0x55 | u8 | 21 | 23 |
| Rebalance | P20F8 | アリス | Luck @0x56 | u8 | 5 | 6 |
| Rebalance | P20F8 | アリス | Enemy speed @0x66 | u8 | 16 | 64 |
| Rebalance | P20F8 | アリス | AI action row @0x6A | u8 | 14 | 27 |
| Rebalance | P20F8 | アリス | HP @0x0C | u16 | 1472 | 1435 |
| Rebalance | P20F8 | アリス | MP @0x0E | u16 | 207 | 250 |
| Rebalance | P20F8 | アリス | Skill slot 1 @0x10 | u16 | 60 | 163 |
| Rebalance | P20F8 | アリス | Skill slot 2 @0x12 | u16 | 58 | 182 |
| Rebalance | P20F8 | アリス | Skill slot 3 @0x14 | u16 | 61 | 202 |
| Rebalance | P20F8 | アリス | Skill slot 4 @0x16 | u16 | 138 | 41 |
| Rebalance | P20F8 | アリス | Skill slot 5 @0x18 | u16 | 182 | 138 |
| Rebalance | P20F8 | アリス | Skill slot 6 @0x1A | u16 | 202 | 61 |
| Rebalance | P20F8 | アリス | Skill slot 7 @0x1C | u16 | 41 | 60 |
| Rebalance | P20F8 | アリス | Equipment slot 1 @0x22 | u16 | 0 | 500 |
| Rebalance | P20F8 | アリス | Equipment slot 2 @0x24 | u16 | 0 | 578 |
| Rebalance | P20F8 | アリス | Equipment slot 3 @0x26 | u16 | 0 | 629 |
| Rebalance | P20F8 | アリス | Equipment slot 4 @0x28 | u16 | 0 | 685 |
| Rebalance | P2173 | ムールムール | Level @0x47 | u8 | 48 | 55 |
| Rebalance | P2173 | ムールムール | Intuition @0x4C | u8 | 22 | 24 |
| Rebalance | P2173 | ムールムール | Willpower @0x4D | u8 | 24 | 26 |
| Rebalance | P2173 | ムールムール | Magic @0x4E | u8 | 47 | 99 |
| Rebalance | P2173 | ムールムール | Intelligence @0x4F | u8 | 41 | 88 |
| Rebalance | P2173 | ムールムール | Grace @0x50 | u8 | 17 | 18 |
| Rebalance | P2173 | ムールムール | Strength @0x51 | u8 | 49 | 53 |
| Rebalance | P2173 | ムールムール | Vitality @0x52 | u8 | 33 | 35 |
| Rebalance | P2173 | ムールムール | Agility @0x53 | u8 | 23 | 25 |
| Rebalance | P2173 | ムールムール | Dexterity @0x54 | u8 | 24 | 26 |
| Rebalance | P2173 | ムールムール | Charm @0x55 | u8 | 24 | 26 |
| Rebalance | P2173 | ムールムール | Luck @0x56 | u8 | 18 | 19 |
| Rebalance | P2173 | ムールムール | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P2173 | ムールムール | Gun resistance code @0x5A | u8 | 50 | 25 |
| Rebalance | P2173 | ムールムール | Enemy speed @0x66 | u8 | 17 | 43 |
| Rebalance | P2173 | ムールムール | HP @0x0C | u16 | 3328 | 2288 |
| Rebalance | P2173 | ムールムール | MP @0x0E | u16 | 2048 | 2339 |
| Rebalance | P2173 | ムールムール | Skill slot 1 @0x10 | u16 | 174 | 202 |
| Rebalance | P2173 | ムールムール | Skill slot 2 @0x12 | u16 | 171 | 93 |
| Rebalance | P2173 | ムールムール | Skill slot 3 @0x14 | u16 | 182 | 283 |
| Rebalance | P2173 | ムールムール | Skill slot 4 @0x16 | u16 | 176 | 305 |
| Rebalance | P2173 | ムールムール | Skill slot 5 @0x18 | u16 | 70 | 182 |
| Rebalance | P2173 | ムールムール | Skill slot 6 @0x1A | u16 | 273 | 102 |
| Rebalance | P2173 | ムールムール | Skill slot 7 @0x1C | u16 | 273 | 88 |
| Rebalance | P2173 | ムールムール | Skill slot 8 @0x1E | u16 | 88 | 76 |
| Rebalance | P2174 | ダンタリオン | Level @0x47 | u8 | 44 | 55 |
| Rebalance | P2174 | ダンタリオン | Intuition @0x4C | u8 | 21 | 24 |
| Rebalance | P2174 | ダンタリオン | Willpower @0x4D | u8 | 22 | 25 |
| Rebalance | P2174 | ダンタリオン | Magic @0x4E | u8 | 44 | 99 |
| Rebalance | P2174 | ダンタリオン | Intelligence @0x4F | u8 | 38 | 99 |
| Rebalance | P2174 | ダンタリオン | Grace @0x50 | u8 | 16 | 18 |
| Rebalance | P2174 | ダンタリオン | Strength @0x51 | u8 | 45 | 51 |
| Rebalance | P2174 | ダンタリオン | Vitality @0x52 | u8 | 31 | 35 |
| Rebalance | P2174 | ダンタリオン | Agility @0x53 | u8 | 22 | 25 |
| Rebalance | P2174 | ダンタリオン | Dexterity @0x54 | u8 | 23 | 26 |
| Rebalance | P2174 | ダンタリオン | Charm @0x55 | u8 | 23 | 26 |
| Rebalance | P2174 | ダンタリオン | Luck @0x56 | u8 | 17 | 19 |
| Rebalance | P2174 | ダンタリオン | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P2174 | ダンタリオン | Magic resistance code @0x60 | u8 | 50 | 0 |
| Rebalance | P2174 | ダンタリオン | Enemy speed @0x66 | u8 | 17 | 36 |
| Rebalance | P2174 | ダンタリオン | HP @0x0C | u16 | 2880 | 6048 |
| Rebalance | P2174 | ダンタリオン | MP @0x0E | u16 | 1840 | 2288 |
| Rebalance | P2174 | ダンタリオン | Skill slot 1 @0x10 | u16 | 25 | 202 |
| Rebalance | P2174 | ダンタリオン | Skill slot 2 @0x12 | u16 | 83 | 137 |
| Rebalance | P2174 | ダンタリオン | Skill slot 3 @0x14 | u16 | 17 | 140 |
| Rebalance | P2174 | ダンタリオン | Skill slot 4 @0x16 | u16 | 79 | 282 |
| Rebalance | P2174 | ダンタリオン | Skill slot 5 @0x18 | u16 | 36 | 27 |
| Rebalance | P2174 | ダンタリオン | Skill slot 6 @0x1A | u16 | 100 | 38 |
| Rebalance | P2174 | ダンタリオン | Skill slot 7 @0x1C | u16 | 75 | 102 |
| Rebalance | P2174 | ダンタリオン | Skill slot 8 @0x1E | u16 | 253 | 76 |
| Rebalance | P2177 | ダンタリオン | Magic @0x4E | u8 | 29 | 44 |
| Rebalance | P2177 | ダンタリオン | Intelligence @0x4F | u8 | 25 | 38 |
| Rebalance | P2177 | ダンタリオン | Magic resistance code @0x60 | u8 | 50 | 0 |
| Rebalance | P2177 | ダンタリオン | Enemy speed @0x66 | u8 | 15 | 22 |
| Rebalance | P2177 | ダンタリオン | HP @0x0C | u16 | 403 | 726 |
| Rebalance | P2177 | ダンタリオン | Skill slot 6 @0x1A | u16 | 100 | 85 |
| Rebalance | P2199 | バール | Level @0x47 | u8 | 52 | 60 |
| Rebalance | P2199 | バール | Intuition @0x4C | u8 | 55 | 59 |
| Rebalance | P2199 | バール | Willpower @0x4D | u8 | 53 | 57 |
| Rebalance | P2199 | バール | Magic @0x4E | u8 | 58 | 99 |
| Rebalance | P2199 | バール | Intelligence @0x4F | u8 | 36 | 68 |
| Rebalance | P2199 | バール | Grace @0x50 | u8 | 42 | 45 |
| Rebalance | P2199 | バール | Strength @0x51 | u8 | 90 | 97 |
| Rebalance | P2199 | バール | Vitality @0x52 | u8 | 82 | 88 |
| Rebalance | P2199 | バール | Agility @0x53 | u8 | 64 | 69 |
| Rebalance | P2199 | バール | Dexterity @0x54 | u8 | 27 | 29 |
| Rebalance | P2199 | バール | Charm @0x55 | u8 | 77 | 83 |
| Rebalance | P2199 | バール | Luck @0x56 | u8 | 10 | 11 |
| Rebalance | P2199 | バール | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P2199 | バール | Curse resistance code @0x61 | u8 | 0 | 50 |
| Rebalance | P2199 | バール | Enemy speed @0x66 | u8 | 19 | 43 |
| Rebalance | P2199 | バール | HP @0x0C | u16 | 8756 | 4925 |
| Rebalance | P2199 | バール | MP @0x0E | u16 | 2768 | 3184 |
| Rebalance | P2199 | バール | Skill slot 1 @0x10 | u16 | 132 | 297 |
| Rebalance | P2199 | バール | Skill slot 3 @0x14 | u16 | 282 | 305 |
| Rebalance | P2199 | バール | Skill slot 4 @0x16 | u16 | 307 | 41 |
| Rebalance | P2199 | バール | Skill slot 5 @0x18 | u16 | 305 | 306 |
| Rebalance | P2199 | バール | Skill slot 6 @0x1A | u16 | 306 | 83 |
| Rebalance | P2199 | バール | Skill slot 7 @0x1C | u16 | 88 | 85 |
| Rebalance | P219B | ベルフェゴール | Level @0x47 | u8 | 38 | 40 |
| Rebalance | P219B | ベルフェゴール | Intuition @0x4C | u8 | 44 | 45 |
| Rebalance | P219B | ベルフェゴール | Willpower @0x4D | u8 | 42 | 43 |
| Rebalance | P219B | ベルフェゴール | Magic @0x4E | u8 | 47 | 99 |
| Rebalance | P219B | ベルフェゴール | Intelligence @0x4F | u8 | 30 | 78 |
| Rebalance | P219B | ベルフェゴール | Grace @0x50 | u8 | 33 | 34 |
| Rebalance | P219B | ベルフェゴール | Strength @0x51 | u8 | 73 | 75 |
| Rebalance | P219B | ベルフェゴール | Vitality @0x52 | u8 | 68 | 70 |
| Rebalance | P219B | ベルフェゴール | Agility @0x53 | u8 | 52 | 53 |
| Rebalance | P219B | ベルフェゴール | Dexterity @0x54 | u8 | 23 | 24 |
| Rebalance | P219B | ベルフェゴール | Charm @0x55 | u8 | 59 | 61 |
| Rebalance | P219B | ベルフェゴール | Enemy speed @0x66 | u8 | 18 | 35 |
| Rebalance | P219B | ベルフェゴール | HP @0x0C | u16 | 5360 | 6700 |
| Rebalance | P219B | ベルフェゴール | MP @0x0E | u16 | 1940 | 2040 |
| Rebalance | P219B | ベルフェゴール | Skill slot 1 @0x10 | u16 | 294 | 297 |
| Rebalance | P219B | ベルフェゴール | Skill slot 2 @0x12 | u16 | 33 | 306 |
| Rebalance | P219B | ベルフェゴール | Skill slot 3 @0x14 | u16 | 297 | 294 |
| Rebalance | P219B | ベルフェゴール | Skill slot 4 @0x16 | u16 | 92 | 33 |
| Rebalance | P219B | ベルフェゴール | Skill slot 5 @0x18 | u16 | 98 | 88 |
| Rebalance | P219B | ベルフェゴール | Skill slot 6 @0x1A | u16 | 250 | 0 |
| Rebalance | P219B | ベルフェゴール | Skill slot 7 @0x1C | u16 | 88 | 0 |
| Rebalance | P219B | ベルフェゴール | Skill slot 8 @0x1E | u16 | 306 | 0 |
| Rebalance | P219B | ベルフェゴール | Equipment slot 1 @0x22 | u16 | 0 | 504 |
| Rebalance | P219B | ベルフェゴール | Equipment slot 2 @0x24 | u16 | 0 | 586 |
| Rebalance | P219B | ベルフェゴール | Equipment slot 3 @0x26 | u16 | 0 | 640 |
| Rebalance | P219C | バルベリス | Level @0x47 | u8 | 36 | 37 |
| Rebalance | P219C | バルベリス | Magic @0x4E | u8 | 24 | 60 |
| Rebalance | P219C | バルベリス | Intelligence @0x4F | u8 | 25 | 62 |
| Rebalance | P219C | バルベリス | Strength @0x51 | u8 | 35 | 90 |
| Rebalance | P219C | バルベリス | Enemy speed @0x66 | u8 | 15 | 42 |
| Rebalance | P219C | バルベリス | AI action row @0x6A | u8 | 12 | 27 |
| Rebalance | P219C | バルベリス | HP @0x0C | u16 | 2228 | 5570 |
| Rebalance | P219C | バルベリス | MP @0x0E | u16 | 936 | 961 |
| Rebalance | P219C | バルベリス | Skill slot 1 @0x10 | u16 | 292 | 282 |
| Rebalance | P219C | バルベリス | Skill slot 2 @0x12 | u16 | 295 | 202 |
| Rebalance | P219C | バルベリス | Skill slot 3 @0x14 | u16 | 204 | 292 |
| Rebalance | P219C | バルベリス | Skill slot 4 @0x16 | u16 | 282 | 295 |
| Rebalance | P219C | バルベリス | Skill slot 6 @0x1A | u16 | 202 | 204 |
| Rebalance | P219C | バルベリス | Skill slot 7 @0x1C | u16 | 88 | 172 |
| Rebalance | P219C | バルベリス | Skill slot 8 @0x1E | u16 | 172 | 88 |
| Rebalance | P219D | バエル | Enemy speed @0x66 | u8 | 15 | 8 |
| Rebalance | P219D | バエル | AI action row @0x6A | u8 | 24 | 27 |
| Rebalance | P219D | バエル | HP @0x0C | u16 | 1364 | 818 |
| Rebalance | P219D | バエル | Skill slot 1 @0x10 | u16 | 128 | 172 |
| Rebalance | P219D | バエル | Skill slot 2 @0x12 | u16 | 281 | 202 |
| Rebalance | P219D | バエル | Skill slot 3 @0x14 | u16 | 129 | 281 |
| Rebalance | P219D | バエル | Skill slot 4 @0x16 | u16 | 132 | 29 |
| Rebalance | P219D | バエル | Skill slot 5 @0x18 | u16 | 130 | 132 |
| Rebalance | P219D | バエル | Skill slot 6 @0x1A | u16 | 29 | 128 |
| Rebalance | P219D | バエル | Skill slot 7 @0x1C | u16 | 63 | 129 |
| Rebalance | P219E | バールゼフォン | Strength @0x51 | u8 | 26 | 39 |
| Rebalance | P219E | バールゼフォン | Magic resistance code @0x60 | u8 | 0 | 50 |
| Rebalance | P219E | バールゼフォン | Enemy speed @0x66 | u8 | 14 | 13 |
| Rebalance | P219E | バールゼフォン | HP @0x0C | u16 | 784 | 1098 |
| Rebalance | P219E | バールゼフォン | Skill slot 1 @0x10 | u16 | 8 | 172 |
| Rebalance | P219E | バールゼフォン | Skill slot 2 @0x12 | u16 | 280 | 83 |
| Rebalance | P219E | バールゼフォン | Skill slot 3 @0x14 | u16 | 32 | 85 |
| Rebalance | P219E | バールゼフォン | Skill slot 4 @0x16 | u16 | 100 | 280 |
| Rebalance | P219E | バールゼフォン | Skill slot 5 @0x18 | u16 | 85 | 151 |
| Rebalance | P219E | バールゼフォン | Skill slot 6 @0x1A | u16 | 84 | 149 |
| Rebalance | P219E | バールゼフォン | Skill slot 7 @0x1C | u16 | 79 | 198 |
| Rebalance | P219E | バールゼフォン | Skill slot 8 @0x1E | u16 | 172 | 8 |
| Rebalance | P219F | イシュタル | Magic @0x4E | u8 | 65 | 99 |
| Rebalance | P219F | イシュタル | Intelligence @0x4F | u8 | 40 | 80 |
| Rebalance | P219F | イシュタル | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P219F | イシュタル | Curse resistance code @0x61 | u8 | 0 | 70 |
| Rebalance | P219F | イシュタル | Enemy speed @0x66 | u8 | 20 | 51 |
| Rebalance | P219F | イシュタル | HP @0x0C | u16 | 9848 | 4432 |
| Rebalance | P219F | イシュタル | Skill slot 1 @0x10 | u16 | 38 | 144 |
| Rebalance | P219F | イシュタル | Skill slot 2 @0x12 | u16 | 34 | 54 |
| Rebalance | P219F | イシュタル | Skill slot 3 @0x14 | u16 | 19 | 305 |
| Rebalance | P219F | イシュタル | Skill slot 4 @0x16 | u16 | 45 | 41 |
| Rebalance | P219F | イシュタル | Skill slot 6 @0x1A | u16 | 48 | 76 |
| Rebalance | P219F | イシュタル | Skill slot 7 @0x1C | u16 | 0 | 91 |
| Rebalance | P219F | イシュタル | Skill slot 8 @0x1E | u16 | 0 | 86 |
| Rebalance | P21A0 | アシラト | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P21A0 | アシラト | Gun resistance code @0x5A | u8 | 50 | 25 |
| Rebalance | P21A0 | アシラト | Enemy speed @0x66 | u8 | 19 | 20 |
| Rebalance | P21A0 | アシラト | HP @0x0C | u16 | 7224 | 4334 |
| Rebalance | P21A0 | アシラト | Skill slot 4 @0x16 | u16 | 38 | 41 |
| Rebalance | P21A0 | アシラト | Skill slot 5 @0x18 | u16 | 41 | 102 |
| Rebalance | P21A0 | アシラト | Skill slot 6 @0x1A | u16 | 102 | 195 |
| Rebalance | P21A0 | アシラト | Skill slot 7 @0x1C | u16 | 195 | 88 |
| Rebalance | P21A0 | アシラト | Skill slot 8 @0x1E | u16 | 88 | 76 |
| Rebalance | P21A1 | モラクス | Magic @0x4E | u8 | 47 | 94 |
| Rebalance | P21A1 | モラクス | Intelligence @0x4F | u8 | 43 | 86 |
| Rebalance | P21A1 | モラクス | Strength @0x51 | u8 | 51 | 99 |
| Rebalance | P21A1 | モラクス | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P21A1 | モラクス | Gun resistance code @0x5A | u8 | 50 | 25 |
| Rebalance | P21A1 | モラクス | Fire resistance code @0x5B | u8 | 30 | 251 |
| Rebalance | P21A1 | モラクス | Enemy speed @0x66 | u8 | 17 | 42 |
| Rebalance | P21A1 | モラクス | HP @0x0C | u16 | 4828 | 7242 |
| Rebalance | P21A1 | モラクス | Skill slot 1 @0x10 | u16 | 17 | 207 |
| Rebalance | P21A1 | モラクス | Skill slot 2 @0x12 | u16 | 33 | 293 |
| Rebalance | P21A1 | モラクス | Skill slot 3 @0x14 | u16 | 90 | 144 |
| Rebalance | P21A1 | モラクス | Skill slot 4 @0x16 | u16 | 144 | 92 |
| Rebalance | P21A1 | モラクス | Skill slot 5 @0x18 | u16 | 63 | 206 |
| Rebalance | P21A1 | モラクス | Skill slot 6 @0x1A | u16 | 187 | 63 |
| Rebalance | P21A1 | モラクス | Skill slot 7 @0x1C | u16 | 88 | 83 |
| Rebalance | P21A1 | モラクス | Skill slot 8 @0x1E | u16 | 91 | 76 |
| Rebalance | P21A2 | ハアゲンティ | Magic @0x4E | u8 | 43 | 64 |
| Rebalance | P21A2 | ハアゲンティ | Intelligence @0x4F | u8 | 39 | 58 |
| Rebalance | P21A2 | ハアゲンティ | Enemy speed @0x66 | u8 | 17 | 18 |
| Rebalance | P21A2 | ハアゲンティ | AI action row @0x6A | u8 | 15 | 27 |
| Rebalance | P21A2 | ハアゲンティ | HP @0x0C | u16 | 3912 | 3521 |
| Rebalance | P21A2 | ハアゲンティ | Skill slot 1 @0x10 | u16 | 37 | 92 |
| Rebalance | P21A2 | ハアゲンティ | Skill slot 2 @0x12 | u16 | 32 | 95 |
| Rebalance | P21A2 | ハアゲンティ | Skill slot 3 @0x14 | u16 | 95 | 75 |
| Rebalance | P21A2 | ハアゲンティ | Skill slot 4 @0x16 | u16 | 303 | 37 |
| Rebalance | P21A2 | ハアゲンティ | Skill slot 7 @0x1C | u16 | 75 | 32 |
| Rebalance | P21A2 | ハアゲンティ | Skill slot 8 @0x1E | u16 | 92 | 303 |
| Rebalance | P21A2 | ハアゲンティ | Equipment slot 1 @0x22 | u16 | 0 | 504 |
| Rebalance | P21A2 | ハアゲンティ | Equipment slot 3 @0x26 | u16 | 0 | 640 |
| Rebalance | P21A2 | ハアゲンティ | Equipment slot 4 @0x28 | u16 | 0 | 693 |
| Rebalance | P21A3 | ヴェパル | Level @0x47 | u8 | 25 | 32 |
| Rebalance | P21A3 | ヴェパル | Intuition @0x4C | u8 | 13 | 15 |
| Rebalance | P21A3 | ヴェパル | Willpower @0x4D | u8 | 15 | 17 |
| Rebalance | P21A3 | ヴェパル | Magic @0x4E | u8 | 27 | 62 |
| Rebalance | P21A3 | ヴェパル | Intelligence @0x4F | u8 | 25 | 56 |
| Rebalance | P21A3 | ヴェパル | Grace @0x50 | u8 | 12 | 14 |
| Rebalance | P21A3 | ヴェパル | Strength @0x51 | u8 | 27 | 31 |
| Rebalance | P21A3 | ヴェパル | Vitality @0x52 | u8 | 23 | 26 |
| Rebalance | P21A3 | ヴェパル | Agility @0x53 | u8 | 16 | 18 |
| Rebalance | P21A3 | ヴェパル | Dexterity @0x54 | u8 | 17 | 19 |
| Rebalance | P21A3 | ヴェパル | Charm @0x55 | u8 | 14 | 16 |
| Rebalance | P21A3 | ヴェパル | Luck @0x56 | u8 | 12 | 14 |
| Rebalance | P21A3 | ヴェパル | Enemy speed @0x66 | u8 | 15 | 38 |
| Rebalance | P21A3 | ヴェパル | AI action row @0x6A | u8 | 20 | 27 |
| Rebalance | P21A3 | ヴェパル | HP @0x0C | u16 | 1264 | 1589 |
| Rebalance | P21A3 | ヴェパル | MP @0x0E | u16 | 868 | 1105 |
| Rebalance | P21A3 | ヴェパル | Skill slot 1 @0x10 | u16 | 258 | 59 |
| Rebalance | P21A3 | ヴェパル | Skill slot 2 @0x12 | u16 | 40 | 61 |
| Rebalance | P21A3 | ヴェパル | Skill slot 3 @0x14 | u16 | 195 | 40 |
| Rebalance | P21A3 | ヴェパル | Skill slot 4 @0x16 | u16 | 257 | 258 |
| Rebalance | P21A3 | ヴェパル | Skill slot 5 @0x18 | u16 | 59 | 257 |
| Rebalance | P21A3 | ヴェパル | Skill slot 6 @0x1A | u16 | 61 | 195 |
| Rebalance | P21A3 | ヴェパル | Equipment slot 1 @0x22 | u16 | 0 | 495 |
| Rebalance | P21A3 | ヴェパル | Equipment slot 2 @0x24 | u16 | 0 | 552 |
| Rebalance | P21A3 | ヴェパル | Equipment slot 3 @0x26 | u16 | 0 | 640 |
| Rebalance | P21A3 | ヴェパル | Equipment slot 4 @0x28 | u16 | 0 | 670 |
| Rebalance | P21A4 | ヴェパル | Magic @0x4E | u8 | 34 | 68 |
| Rebalance | P21A4 | ヴェパル | Intelligence @0x4F | u8 | 31 | 62 |
| Rebalance | P21A4 | ヴェパル | Enemy speed @0x66 | u8 | 16 | 41 |
| Rebalance | P21A4 | ヴェパル | AI action row @0x6A | u8 | 20 | 27 |
| Rebalance | P21A4 | ヴェパル | HP @0x0C | u16 | 2236 | 2012 |
| Rebalance | P21A4 | ヴェパル | Skill slot 1 @0x10 | u16 | 258 | 308 |
| Rebalance | P21A4 | ヴェパル | Skill slot 3 @0x14 | u16 | 308 | 258 |
| Rebalance | P21A4 | ヴェパル | Skill slot 4 @0x16 | u16 | 195 | 257 |
| Rebalance | P21A4 | ヴェパル | Skill slot 5 @0x18 | u16 | 257 | 195 |
| Rebalance | P21A4 | ヴェパル | Equipment slot 1 @0x22 | u16 | 0 | 495 |
| Rebalance | P21A4 | ヴェパル | Equipment slot 3 @0x26 | u16 | 0 | 640 |
| Rebalance | P21A4 | ヴェパル | Equipment slot 4 @0x28 | u16 | 0 | 670 |
| Rebalance | P21A5 | ☆デカラビア | Level @0x47 | u8 | 36 | 42 |
| Rebalance | P21A5 | ☆デカラビア | Intuition @0x4C | u8 | 16 | 17 |
| Rebalance | P21A5 | ☆デカラビア | Willpower @0x4D | u8 | 19 | 21 |
| Rebalance | P21A5 | ☆デカラビア | Magic @0x4E | u8 | 34 | 99 |
| Rebalance | P21A5 | ☆デカラビア | Intelligence @0x4F | u8 | 32 | 99 |
| Rebalance | P21A5 | ☆デカラビア | Grace @0x50 | u8 | 16 | 17 |
| Rebalance | P21A5 | ☆デカラビア | Strength @0x51 | u8 | 36 | 39 |
| Rebalance | P21A5 | ☆デカラビア | Vitality @0x52 | u8 | 31 | 34 |
| Rebalance | P21A5 | ☆デカラビア | Agility @0x53 | u8 | 20 | 22 |
| Rebalance | P21A5 | ☆デカラビア | Dexterity @0x54 | u8 | 21 | 23 |
| Rebalance | P21A5 | ☆デカラビア | Charm @0x55 | u8 | 18 | 19 |
| Rebalance | P21A5 | ☆デカラビア | Luck @0x56 | u8 | 15 | 16 |
| Rebalance | P21A5 | ☆デカラビア | Enemy speed @0x66 | u8 | 16 | 68 |
| Rebalance | P21A5 | ☆デカラビア | AI action row @0x6A | u8 | 24 | 27 |
| Rebalance | P21A5 | ☆デカラビア | HP @0x0C | u16 | 1782 | 5702 |
| Rebalance | P21A5 | ☆デカラビア | MP @0x0E | u16 | 1296 | 1507 |
| Rebalance | P21A5 | ☆デカラビア | Skill slot 1 @0x10 | u16 | 29 | 304 |
| Rebalance | P21A5 | ☆デカラビア | Skill slot 3 @0x14 | u16 | 283 | 30 |
| Rebalance | P21A5 | ☆デカラビア | Skill slot 4 @0x16 | u16 | 125 | 283 |
| Rebalance | P21A5 | ☆デカラビア | Equipment slot 1 @0x22 | u16 | 0 | 504 |
| Rebalance | P21A5 | ☆デカラビア | Equipment slot 2 @0x24 | u16 | 0 | 586 |
| Rebalance | P21A5 | ☆デカラビア | Equipment slot 3 @0x26 | u16 | 0 | 640 |
| Rebalance | P21A5 | ☆デカラビア | Equipment slot 4 @0x28 | u16 | 0 | 695 |
| Rebalance | P21A6 | アバドン | Level @0x47 | u8 | 24 | 25 |
| Rebalance | P21A6 | アバドン | Magic @0x4E | u8 | 26 | 27 |
| Rebalance | P21A6 | アバドン | Intelligence @0x4F | u8 | 24 | 25 |
| Rebalance | P21A6 | アバドン | Strength @0x51 | u8 | 26 | 68 |
| Rebalance | P21A6 | アバドン | Enemy speed @0x66 | u8 | 15 | 42 |
| Rebalance | P21A6 | アバドン | HP @0x0C | u16 | 1168 | 2803 |
| Rebalance | P21A6 | アバドン | MP @0x0E | u16 | 820 | 853 |
| Rebalance | P21A6 | アバドン | Skill slot 1 @0x10 | u16 | 201 | 227 |
| Rebalance | P21A6 | アバドン | Skill slot 2 @0x12 | u16 | 198 | 23 |
| Rebalance | P21A6 | アバドン | Skill slot 3 @0x14 | u16 | 17 | 201 |
| Rebalance | P21A6 | アバドン | Skill slot 4 @0x16 | u16 | 170 | 204 |
| Rebalance | P21A6 | アバドン | Skill slot 5 @0x18 | u16 | 204 | 170 |
| Rebalance | P21A6 | アバドン | Skill slot 6 @0x1A | u16 | 23 | 198 |
| Rebalance | P21A6 | アバドン | Skill slot 8 @0x1E | u16 | 227 | 17 |
| Rebalance | P21A8 | ラマシュトゥ | Level @0x47 | u8 | 44 | 49 |
| Rebalance | P21A8 | ラマシュトゥ | Intuition @0x4C | u8 | 29 | 62 |
| Rebalance | P21A8 | ラマシュトゥ | Willpower @0x4D | u8 | 19 | 40 |
| Rebalance | P21A8 | ラマシュトゥ | Magic @0x4E | u8 | 26 | 54 |
| Rebalance | P21A8 | ラマシュトゥ | Intelligence @0x4F | u8 | 14 | 30 |
| Rebalance | P21A8 | ラマシュトゥ | Grace @0x50 | u8 | 24 | 50 |
| Rebalance | P21A8 | ラマシュトゥ | Strength @0x51 | u8 | 42 | 88 |
| Rebalance | P21A8 | ラマシュトゥ | Vitality @0x52 | u8 | 52 | 99 |
| Rebalance | P21A8 | ラマシュトゥ | Agility @0x53 | u8 | 40 | 84 |
| Rebalance | P21A8 | ラマシュトゥ | Dexterity @0x54 | u8 | 16 | 34 |
| Rebalance | P21A8 | ラマシュトゥ | Charm @0x55 | u8 | 41 | 86 |
| Rebalance | P21A8 | ラマシュトゥ | Luck @0x56 | u8 | 13 | 14 |
| Rebalance | P21A8 | ラマシュトゥ | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P21A8 | ラマシュトゥ | Enemy speed @0x66 | u8 | 16 | 34 |
| Rebalance | P21A8 | ラマシュトゥ | HP @0x0C | u16 | 4744 | 2965 |
| Rebalance | P21A8 | ラマシュトゥ | MP @0x0E | u16 | 1152 | 1280 |
| Rebalance | P21A8 | ラマシュトゥ | Skill slot 1 @0x10 | u16 | 208 | 306 |
| Rebalance | P21A8 | ラマシュトゥ | Skill slot 2 @0x12 | u16 | 184 | 276 |
| Rebalance | P21A8 | ラマシュトゥ | Skill slot 3 @0x14 | u16 | 302 | 202 |
| Rebalance | P21A8 | ラマシュトゥ | Skill slot 4 @0x16 | u16 | 19 | 302 |
| Rebalance | P21A8 | ラマシュトゥ | Skill slot 5 @0x18 | u16 | 168 | 188 |
| Rebalance | P21A8 | ラマシュトゥ | Skill slot 6 @0x1A | u16 | 34 | 168 |
| Rebalance | P21A8 | ラマシュトゥ | Skill slot 8 @0x1E | u16 | 188 | 76 |
| Rebalance | P21A9 | オセ | Magic @0x4E | u8 | 43 | 86 |
| Rebalance | P21A9 | オセ | Intelligence @0x4F | u8 | 37 | 74 |
| Rebalance | P21A9 | オセ | Strength @0x51 | u8 | 44 | 99 |
| Rebalance | P21A9 | オセ | Enemy speed @0x66 | u8 | 16 | 35 |
| Rebalance | P21A9 | オセ | AI action row @0x6A | u8 | 12 | 27 |
| Rebalance | P21A9 | オセ | HP @0x0C | u16 | 2732 | 6830 |
| Rebalance | P21A9 | オセ | Skill slot 1 @0x10 | u16 | 208 | 283 |
| Rebalance | P21A9 | オセ | Skill slot 2 @0x12 | u16 | 184 | 63 |
| Rebalance | P21A9 | オセ | Skill slot 3 @0x14 | u16 | 33 | 226 |
| Rebalance | P21A9 | オセ | Skill slot 4 @0x16 | u16 | 168 | 208 |
| Rebalance | P21A9 | オセ | Skill slot 5 @0x18 | u16 | 90 | 168 |
| Rebalance | P21A9 | オセ | Skill slot 6 @0x1A | u16 | 63 | 33 |
| Rebalance | P21A9 | オセ | Skill slot 7 @0x1C | u16 | 75 | 90 |
| Rebalance | P21A9 | オセ | Skill slot 8 @0x1E | u16 | 250 | 75 |
| Rebalance | P21A9 | オセ | Equipment slot 1 @0x22 | u16 | 0 | 499 |
| Rebalance | P21A9 | オセ | Equipment slot 2 @0x24 | u16 | 0 | 586 |
| Rebalance | P21A9 | オセ | Equipment slot 4 @0x28 | u16 | 0 | 681 |
| Rebalance | P21AA | アイム | Magic @0x4E | u8 | 34 | 85 |
| Rebalance | P21AA | アイム | Intelligence @0x4F | u8 | 29 | 72 |
| Rebalance | P21AA | アイム | Enemy speed @0x66 | u8 | 16 | 34 |
| Rebalance | P21AA | アイム | HP @0x0C | u16 | 2168 | 3469 |
| Rebalance | P21AA | アイム | Skill slot 1 @0x10 | u16 | 20 | 139 |
| Rebalance | P21AA | アイム | Skill slot 2 @0x12 | u16 | 289 | 20 |
| Rebalance | P21AA | アイム | Skill slot 3 @0x14 | u16 | 17 | 289 |
| Rebalance | P21AA | アイム | Skill slot 5 @0x18 | u16 | 142 | 290 |
| Rebalance | P21AA | アイム | Skill slot 6 @0x1A | u16 | 139 | 144 |
| Rebalance | P21AA | アイム | Skill slot 7 @0x1C | u16 | 290 | 17 |
| Rebalance | P21AA | アイム | Skill slot 8 @0x1E | u16 | 144 | 142 |
| Rebalance | P21AB | イポス | Magic @0x4E | u8 | 37 | 99 |
| Rebalance | P21AB | イポス | Intelligence @0x4F | u8 | 32 | 96 |
| Rebalance | P21AB | イポス | Enemy speed @0x66 | u8 | 16 | 26 |
| Rebalance | P21AB | イポス | HP @0x0C | u16 | 2652 | 5304 |
| Rebalance | P21AB | イポス | Skill slot 1 @0x10 | u16 | 80 | 169 |
| Rebalance | P21AB | イポス | Skill slot 2 @0x12 | u16 | 37 | 80 |
| Rebalance | P21AB | イポス | Skill slot 3 @0x14 | u16 | 210 | 88 |
| Rebalance | P21AB | イポス | Skill slot 4 @0x16 | u16 | 186 | 37 |
| Rebalance | P21AB | イポス | Skill slot 5 @0x18 | u16 | 41 | 210 |
| Rebalance | P21AB | イポス | Skill slot 6 @0x1A | u16 | 88 | 41 |
| Rebalance | P21AB | イポス | Skill slot 8 @0x1E | u16 | 169 | 186 |
| Rebalance | P21AC | アスタルテ | Magic @0x4E | u8 | 53 | 66 |
| Rebalance | P21AC | アスタルテ | Intelligence @0x4F | u8 | 33 | 41 |
| Rebalance | P21AC | アスタルテ | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P21AC | アスタルテ | Curse resistance code @0x61 | u8 | 0 | 50 |
| Rebalance | P21AC | アスタルテ | Enemy speed @0x66 | u8 | 19 | 37 |
| Rebalance | P21AC | アスタルテ | HP @0x0C | u16 | 6960 | 3480 |
| Rebalance | P21AC | アスタルテ | Skill slot 1 @0x10 | u16 | 184 | 144 |
| Rebalance | P21AC | アスタルテ | Skill slot 2 @0x12 | u16 | 207 | 41 |
| Rebalance | P21AC | アスタルテ | Skill slot 3 @0x14 | u16 | 144 | 137 |
| Rebalance | P21AC | アスタルテ | Skill slot 5 @0x18 | u16 | 38 | 54 |
| Rebalance | P21AC | アスタルテ | Skill slot 6 @0x1A | u16 | 74 | 86 |
| Rebalance | P21AC | アスタルテ | Skill slot 7 @0x1C | u16 | 41 | 102 |
| Rebalance | P21AD | 豊饒の山羊 | Physical resistance code @0x59 | u8 | 50 | 25 |
| Rebalance | P21AD | 豊饒の山羊 | Gun resistance code @0x5A | u8 | 50 | 25 |
| Rebalance | P21AD | 豊饒の山羊 | Enemy speed @0x66 | u8 | 13 | 14 |
| Rebalance | P21AD | 豊饒の山羊 | HP @0x0C | u16 | 4600 | 2760 |
