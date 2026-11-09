# Authored patch recipes

These files are editable source inputs, not extracted game files.

- `holds.json`: battle-message timing keyed by original file/chunk/record/token identity. The `after` positions come from the existing flow analysis.
- `talkgaps.json`: newly authored Japanese, English and Spanish prompts for missing negotiation records. Original upstream translation text is not included.
- `english_compatibility.json`: exact count/branch repairs established against the verified English BPS output. It is intentionally not an automatic compatibility detector for future releases.
- `delacannon_compatibility.json`: for delacannon's English and Spanish references, how many overwritten commands `tools/layoutrepair.py` restores, the spans and branches it still has to put right, and the padding turned into spaces in list records. `tools/delacannoncompat.py` generates it from the reference images.
- `artwork-recipe.json`: selected fitted frame identities, palette decisions, dimensions and placements. It contains no PNG/BMP pixels. Dedicated room conversions are handled by `winrooms.py`.

Numeric recipes are the `src/`-level `balance.json` and `balance_redesign.json`. [The modder guide](../../docs/modding/README.md) explains field offsets, branch identities and rebuilding.
