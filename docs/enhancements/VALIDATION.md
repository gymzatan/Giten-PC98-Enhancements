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

The English reference was used for 17 further runs of the actual embedded page code. These verify:

- Fixes and Rebalance matching the shared native repair pipeline byte for byte, with English input data.
- Standalone Artwork and both supported installation orders, including Rebalance.
- Repeat application, missing-Fixes rejection, and refusal to downgrade Rebalance.
- Preservation of longer English event/battle text, added newlines and additional unrelated records, with valid relocated branches.
- Preservation of an English negotiation question supplied in a previously missing record.
- Precise rejection of changed event operands and missing prerequisite script repairs, without producing output.

The add-on page was checked with 84 runs of its embedded code on eight disks: the Japanese reference and the English reference, each as it is, with Fixes, with Fixes and Rebalance, and with those and Windows Artwork. The checks cover:

- The language read from `DDS98.EXE`, and no Fixes, Rebalance, artwork or target-prompt byte among the 576 bytes that tell it.
- Each add-on in and out, byte for byte equal to the Python reference, with the question in the disk's language; both out again leaves every file as before.
- The disk grown only when it lacks free clusters: the English disk with Fixes and Windows Artwork (none free) gains one cylinder; the other seven are not resized.
- Fixes and Rebalance refusing a disk with the target prompt and naming it as the reason; Fixes keeping the gamepad add-on; Windows Artwork before or after the add-ons giving the same files where the disk has room for both orders.
- Refusal, without output, of a unsupported-language disk, a program mixing the two languages, another program named `DDS98.COM`, and a target prompt half installed.
- The gamepad's hook sites recognised in every one of these programs and in the Japanese and English Fixes, Rebalance and artwork programs.

In DOSBox-X, the grown English disk with Fixes, Rebalance, Windows Artwork and both add-ons booted from the companion FDI to its title screen, where the arrow keys moved the pointer, and started a new game. In battles on a test disk carrying the English game's files with both add-ons, and again with the Japanese game's, “Use on whom?” and 「誰に使いますか？」 stayed up while battle time was stopped, Tab moved between the party list and the enemy, and the attack's message replaced the question.

The native builds were repeated and compared against the accepted outputs: 133 Japanese Fixes files, 166 Japanese Rebalance files, 148 English Fixes files and 181 English Rebalance files remained identical.

The supplied English BPS output contains incorrect record counts in 51 script chunks. Fixes corrects those verified headers while preserving their records. It also corrects 19 branch fields in nine records where the translation left stale offsets and the corresponding original control structure matches unambiguously. These are specific checked compatibility repairs. Other translation content and existing defects are retained; this is not a certification of every upstream English script or a completion of its translation.

Copies of the English Fixes and English Fixes + Rebalance + Windows Artwork results were booted in the existing DOSBox-X PC-9821 setup with 16 MB RAM and the companion FDI. They reached their title screens without entering startup commands. A Japanese combined result was also checked. This is a startup smoke check, not a complete playthrough; new-game progression was not verified through the automated mouse controls. Browser processing was verified through the page's actual embedded JavaScript under Node; a full interactive browser session was not part of this verification.
