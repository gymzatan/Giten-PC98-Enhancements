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

The native builds were repeated and compared against the accepted outputs: 132 Japanese Fixes files, 165 Japanese Rebalance files, 148 English Fixes files and 181 English Rebalance files remained identical.

The supplied English BPS output contains incorrect record counts in 51 script chunks. Fixes corrects those verified headers while preserving their records. It also corrects 19 branch fields in nine records where the translation left stale offsets and the corresponding original control structure matches unambiguously. These are specific checked compatibility repairs. Other translation content and existing defects are retained; this is not a certification of every upstream English script or a completion of its translation.

Copies of the English Fixes and English Fixes + Rebalance + Windows Artwork results were booted in the existing DOSBox-X PC-9821 setup with 16 MB RAM and the companion FDI. They reached their title screens without entering startup commands. A Japanese combined result was also checked. This is a startup smoke check, not a complete playthrough; new-game progression was not verified through the automated mouse controls. Browser processing was verified through the page's actual embedded JavaScript under Node; a full interactive browser session was not part of this verification.
