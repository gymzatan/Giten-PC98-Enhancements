# Compatibility and verification

## Reference inputs

| Input | SHA-256 |
| --- | --- |
| PepsimanGB pre-made Japanese HDI | `33ba81310d5cbf0e8459c5f09ea50360715591129a46f72c94e1b1ec0c49e77f` |
| Verified output of the separately supplied English BPS | `c0ad091cc3dea998d81046ffdb418d8c392c0abe0f41c986776634a93db511b7` |

The English translation is [Sneikkimies' Giten Megami Tensei translation release](https://www.romhacking.net/translations/7343/), distributed separately. Redux's source repository does not include the BPS or its translated game scripts.

The ordinary Japanese original was also tested through the actual three installers. Image geometry differs between dumps; FAT resolution and checked states are what matter. Do not identify a language solely from the HDI filename.

## Build-time reference versus runtime adaptation

`english_enhancements.py` accepts the exact verified BPS output as a **build reference**. It fixes 51 declared-record-count headers and 19 stale branch fields under explicit expected bytes, then calls `nativebuild.py`. Those corrections are in `text/english_compatibility.json`.

The browser installer consumes structural script plans exported from the native outputs. It retains translated text runs by reference, matches record ID/condition and command/operand structures, and relocates valid branches. Numeric edits use record-relative offsets resolved from each input's current table pointers. It does not overwrite a whole translated MS/ID/ET file with Japanese text.

Future English releases that change only text can remain compatible where these checks still match. Event-logic changes, changed conditions, extra/removed commands, ambiguous identities and modified executable bytes require review. The installer refuses them rather than claiming universal compatibility. Do not remove that refusal to make a newer image “work”.

For a new validated English reference, identify its hash, inspect the actual mismatches, update only established compatibility repairs and regenerate pacing from its scripts. Old malformed-branch repairs must not be applied to a corrected future script solely because its filename matches.

## Shared repair ownership

`buildcore.py` contains the accepted repair sequence. The localization-independent native builder consumes the existing script identities through `ScriptInputs`; it doesn't rebuild a second script parser. `webpayload.py` owns manifest packing, and `enhancement_plan.py` exports differences from the native game files. The same actual repair modules supply Python builds, browser checks and modder ledgers.

`StringTableFile`'s optional `newlines=True` lets the numeric editor display established multiline English descriptions. Existing strict callers keep their default behavior. No encoding detector or translation replacement is introduced.

## Verification scope

The exported source independently reproduced all accepted native payload files:

| Build | Files compared | Result |
| --- | --- | --- |
| Japanese Fixes | 132 | Byte-identical |
| Japanese Fixes + Rebalance | 165 | Byte-identical |
| English Fixes | 148 | Byte-identical |
| English Fixes + Rebalance | 181 | Byte-identical |

The numeric editor's locally generated baseline/display database contains 1,485 records. Its names and descriptions come from explicit Japanese/English inputs rather than a bundled translation database. Codec, editor write/readback and relevant CPU-test receipts are maintained in [SOURCE-VALIDATION.md](../../SOURCE-VALIDATION.md).

Previously completed release checks include browser-core installation, independent Japanese Artwork, checked prerequisite rejection, text-preserving English adaptation and combined title-screen startup. See [VALIDATION.md](../../VALIDATION.md). Those receipts are reused; this source publication does not claim a new complete playthrough.

Artwork refitting is separately scoped: source includes all converter/codec stages and authored selection metadata, but not hand-tuned release pixels. A newly generated fit needs visual inspection in its actual palette-sharing contexts. The native gameplay byte comparisons do not imply that a newly fitted artwork result is pixel-identical to the released artwork.
