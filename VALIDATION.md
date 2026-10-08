# Validation scope

The supplied PepsimanGB reference HDI was used for 20 runs of the actual scripts and payloads embedded in the English patch pages. The checks cover:

- Fixes and Rebalance outputs matching the shared game's build files exactly.
- Standalone Artwork matching the existing Python artwork patch byte for byte after the documented two-field partition extension.
- Equivalent game-file contents for Fixes/Artwork and Rebalance/Artwork applied in either supported order.
- Repeated installation, prerequisite rejection, modified-executable rejection and already-installed artwork reporting.
- Preservation of an injected original in-game save, a custom startup script and the existing DOS/driver configuration.
- Refusal to consume occupied partition-tail data or a second partition entry.
- All 42 negotiation packs traversed, with all 23 added prompts reachable.
- The original input HDI checksum remaining unchanged.

The two existing Chinese game payloads remained identical to the accepted release, and all 16 existing Chinese web-patch regression cases passed.

A copy of the Fixes + Rebalance + Windows Artwork result was booted in the existing DOSBox-X PC-9821 setup with 16 MB RAM and the companion FDI. It reached the Windows-artwork title screen without entering a startup command. This is a startup smoke check, not a complete playthrough. Browser processing was verified through the page's actual embedded JavaScript under Node; a full interactive browser session was not part of this verification.
