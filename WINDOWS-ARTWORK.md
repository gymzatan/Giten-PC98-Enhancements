# Windows Artwork

This independent patch adapts graphics from the Windows remake for the PC-98 game. It can be applied to the original supported Japanese image, a Fixes image, or a Fixes + Rebalance image. It does not require the Fixes package and does not translate game text.

**English-translated HDIs: compatibility is not verified.** Artwork also edits map door selectors and executable palette sites, so it cannot be assumed compatible merely because it is a graphics patch. A translation may change those files or the graphics it replaces. The supported combinations below refer to the Japanese game and this project's enhancement patches.

## Replaced graphics

- Dungeon walls, doors and stairs.
- Room and event pictures.
- Demon sprites and poses.
- Title screen.
- The surrounding gold frame and lower compass panel become gray metal while retaining the original geometry, screws, seams, black panels and white lines. Command buttons, direction controls and menu text retain their original green.

This is a palette conversion for the PC-98 renderer, not a port of the Windows executable. Every entry is mapped to its available colors and original palette-slot budget. Transparent outlines and drawing structure follow the PC-98 format.

Demon sprites use the Windows rendition's scale and position, consistently across poses. The footprint demon is represented by its whole body standing over its footprints; the mist sprite occupies a larger part of the battle window.

## Doors, overlays and palette compatibility

Doors are supplied per wall set, and each dungeon section's door selector is changed to match its wall selector. This prevents locations such as Hatsudai from inheriting the wrong area's door. Applying Fixes after Artwork reapplies that door mapping when it replaces maps.

Overlaid room graphics share palettes with their backgrounds: cell bars, shrine close-ups, train doors, the Yata mirror and the fusion-room palette follow the original drawing relationships. The rock and opened passage beneath Togo Shrine use the Windows wall palette. The item-shop backdrop retains the pale gray-blue shared with its shopkeeper.

The spring scene uses one fewer palette slot to leave room for two enemies; its water glow is dithered using the remaining colors. The PC-98 engine still has a finite palette budget, so this conversion cannot eliminate every possible overlap with arbitrary custom graphics.

The patch also suppresses `no space` debug text and changes the two enemy palette-allocation sites in `DDS98.EXE`. Those repairs are already present in Fixes. No other Fixes or Rebalance features are installed by Artwork alone.

## File checks and applying again

The reference PepsimanGB disk has fourteen unused cylinders after its DOS partition. Its original free space is slightly too small for the complete artwork. On that exact recognized layout, this package extends the existing FAT12 partition into the unused 693 KiB tail. The HDI file size, cluster size, existing file locations and startup code stay unchanged. It checks the partition table, FAT capacity and unused tail before doing so; unexpected tail data causes refusal. Other disk layouts are not resized.

Before replacement, artwork hashes distinguish original files, files already supplied by this patch, missing entries and files modified by something else. Unrecognized modified artwork or unsupported executable patch sites cause refusal instead of overwriting another mod.

The patch replaces the selected `DDS98\FC*.BIN` graphics, remaps door selectors in `M0*.BIN` and updates the palette sites. It retains saves, unrelated files and DOS startup configuration. If every artwork file, door mapping and executable site is already patched, the page reports that no new image is needed.

To restore PC-98 artwork, return to your original image and apply only the gameplay packages you want. The artwork package is an installer, not an uninstall or graphics-toggle tool.
