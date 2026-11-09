# Validation scope

The supplied PepsimanGB reference HDI was verified as Japanese: 1,548 game files match the Japanese baseline byte for byte. The English BPS identified in README.md was applied with source, target and patch CRC checks, producing the separately tested English reference.

This Japanese reference HDI was used for 20 runs of the actual scripts and payloads embedded in the English patch pages. The checks cover:

- Fixes and Rebalance outputs matching the shared game's build files exactly.
- Standalone Artwork matching the existing Python artwork patch byte for byte after the documented two-field partition extension.
- Equivalent game-file contents for Fixes/Artwork and Rebalance/Artwork applied in either supported order.
- Repeated installation, prerequisite rejection, modified-executable rejection and already-installed artwork reporting.
- Preservation of an injected original in-game save, a custom startup script and the existing DOS/driver configuration.
- Refusal to consume occupied partition-tail data or a second partition entry.
- All 42 negotiation packs traversed, with all 23 added prompts reachable.
- The original input HDI checksum remaining unchanged.

Sneikkimies' English reference, and delacannon's English and Spanish references, were each used for 17 further runs of the actual embedded page code. These verify:

- Fixes and Rebalance matching the shared native repair pipeline byte for byte, with that translation's input data.
- Standalone Artwork and both supported installation orders, including Rebalance (on delacannon's disks with the merged status labels and list headers).
- Repeat application, missing-Fixes rejection, and refusal to downgrade Rebalance.
- Preservation of longer event/battle text, added newlines and additional unrelated records, with valid relocated branches.
- Preservation of a negotiation question supplied in a previously missing record.
- Precise rejection of changed event operands and missing prerequisite script repairs, without producing output.

Rebuilding Sneikkimies' English through the multi-translation build gave byte-identical Fixes and Rebalance files, hold table and normalized input.

For delacannon's translation, the restored commands were checked over every script record of both languages: afterwards each Japanese command stands at its offset, each display span holds only text, newlines, dictionary words that exist, the span's own name prints and padding, and every branch the Japanese game takes into a line lands on a token, except the one English jump listed in README.md. The battle-line hold analysis (`run/mk_holds.py`) passes over both languages; it accounts for the translation's padding, which ends a battle message where it stands.

The control component page was checked with 162 runs of its embedded code on sixteen disks: the Japanese reference and the three translations' references, each as it is, with Fixes, with Fixes and Rebalance, and with those and Windows Artwork. The checks cover:

- The language read from `DDS98.EXE`, and no Fixes, Rebalance, artwork or target-prompt byte among the bytes each translation changes there.
- Each control component in and out, byte for byte equal to the Python reference, with the question in the disk's language; both out again leaves every file as before.
- The disk grown only when it lacks free clusters: Sneikkimies' English disk with Fixes and Windows Artwork (none free) gains one cylinder; the other fifteen are not resized.
- Fixes and Rebalance refusing a disk with the target prompt and naming it as the reason; Fixes keeping the gamepad control component; Windows Artwork before or after the control features giving the same files where the disk has room for both orders.
- Refusal, without output, of an unsupported-language disk, a program mixing a translation with the Japanese game, another program named `DDS98.COM`, and a target prompt half installed.
- The gamepad's hook sites recognised in every one of these programs and in the Japanese and English Fixes, Rebalance and artwork programs.

In DOSBox-X, the grown English disk with Fixes, Rebalance, Windows Artwork and both control features booted from the companion FDI to its title screen, where the arrow keys moved the pointer, and started a new game. In battles on a test disk carrying the English game's files with both control features, and again with the Japanese game's, “Use on whom?” and 「誰に使いますか？」 stayed up while battle time was stopped, Tab moved between the party list and the enemy, and the attack's message replaced the question.

delacannon's English and Spanish with Fixes, Rebalance, Windows Artwork and both control features (the pages' output, moved into a self-booting DOS disk) reached their title screens in DOSBox-X and loaded an in-game save through **Continue** into a dungeon with the metal frame; their menus, demon list and member status page showed the translation's English or Spanish, and a Spanish dialogue showed its accented letters. The Spanish save list, which the translation's own disk cannot load (its list record stops at a padding wait, and before the command repairs its load menu stops in the script debugger), was verified to load after the list repair, also with the PC-98 artwork. Battles on delacannon's disks were not run in the emulator.

The native builds were repeated and compared against the accepted outputs: 133 Japanese Fixes files, 166 Japanese Rebalance files, 148 English Fixes files and 181 English Rebalance files remained identical.

The supplied English BPS output contains incorrect record counts in 51 script chunks. Fixes corrects those verified headers while preserving their records. It also corrects 19 branch fields in nine records where the translation left stale offsets and the corresponding original control structure matches unambiguously. These are specific checked compatibility repairs. Other translation content and existing defects are retained; this is not a certification of every upstream English script or a completion of its translation.

Copies of the English Fixes and English Fixes + Rebalance + Windows Artwork results were booted in the existing DOSBox-X PC-9821 setup with 16 MB RAM and the companion FDI. They reached their title screens without entering startup commands. A Japanese combined result was also checked. This is a startup smoke check, not a complete playthrough; new-game progression was not verified through the automated mouse controls. Browser processing was verified through the page's actual embedded JavaScript under Node; a full interactive browser session was not part of this verification.
