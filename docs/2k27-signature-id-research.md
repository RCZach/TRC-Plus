# NBA 2K27 signature ID research (offline)

## Result

No new signature name-to-roster-value mapping was established. Keep unknown
signature names out of game writes. This pass did not open Cheat Engine, attach
to the game, or read or write the running process.

## Evidence

- Trace's catalog for exact build `6AD2E48C:36532000` has two previously
  observed `Jumpshot Base` pairs: Goran Dragic = `197` and Kris Dunn = `203`.
  Other signature fields have no name mappings for that build.
- The [NBA 2K27 MyPLAYER Builder animation glossary](https://github.com/lightmatmul/nba2k27-builder-dataset/blob/main/animations/glossary.json)
  contains animation names and symbolic keys, such as
  `SIG_SHOT_JUMPER_GORAN_DRAGIC`, `SIG_SHOT_JUMPER_KRIS_DUNN`, and
  `SIG_SHOT_JUMPER_OSCAR_ROBERTSON`. It has no roster-field integer for those
  entries. Its source is the NBA 2K HQ app and its declared version is
  `202750199`, rather than Trace's NBA2K27.exe build fingerprint. The symbolic
  keys therefore cannot be placed in `field_values.json` as numeric IDs.
- The [Synergy 2K game-data schema](https://github.com/synergy2k-community/gamedata)
  documents animation slots, but publishes no 2K27 roster signature
  name-to-integer table.
- The installed game's large numbered archives have opaque/compressed content;
  their headers do not provide a directly usable signature name table. A
  targeted string check of NBA2K27.exe for several animation labels found no
  usable label-to-value table. No archive was modified or extracted.

## Current preview priority

In the supplied `TRACE-game-update-preview.json`, `Jumpshot Base`, `Release 1`,
and `Release 2` account for 276 missing-ID warnings over 102 distinct
field/name pairs. The most repeated pairs are `Release 1: Oscar Robertson`
(37), `Jumpshot Base: Patrick Mills` (36), `Release 2: Stephen Curry` (18),
`Jumpshot Base: Stephen Curry` (14), and `Release 2: Beluba` (12). The preview
predates the hot-zone fix and is an inventory, not a fresh post-fix warning count.

## Requirement for a mapping

For each field and label, obtain a numeric value from the **same roster field
on the exact Trace-supported executable build**, with independently checked
label and player identity. A symbolic MyPLAYER glossary key, another signature
field, an older build, or a name's list position is insufficient. Record the
evidence in the exact-build catalog and verify that preview resolves only the
expected field/name pairs before enabling an opt-in game update.
