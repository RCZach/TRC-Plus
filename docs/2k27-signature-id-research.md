# NBA 2K27 signature ID research (offline)

## Registered enum lookup implemented

Trace now resolves native animation symbols for build `6AD2E48C:36532000`
using `config/signature_values_2k27.json`: 53 registered enums, 4,756 enum
entries, and 71 existing Signature fields, plus the native Chew Gum boolean.
Repeated use of one enum in several
fields does not create a new ID namespace. These are static-code/reflection
bindings, not observations of every animation in the live roster menu.

`scripts/extract_animation_enums.py` now defaults to the authoritative path:
four RIP-relative LEA instructions supply the descriptor, header, explicit
value table and symbolic name block. The header supplies the count and type
CRC; each explicit 12-byte entry must match its symbol's CRC and reserved zero.
Up to seven alignment bytes may separate the entries and header. Native packed
reflection records must point to that descriptor, have the matching enum CRC,
and match the existing profile's absolute bit position and width. All 71
bindings have two matching property records. The shipped catalog retains
registration bytes, headers, table/name hashes and property evidence. Running
the extractor again reproduced every shipped enum and field binding exactly.

The original heuristic scan remains available with `--heuristic` for discovery.
The registered path corrects its overcounts: Dunk Package has 167 entries,
Triple Threat Style 14, and Moving Behind The Back 42. None is the explicit
Dunk Package value 166; Default is separately 0. Old-build observations are
not transferred.

Name lookup accepts only unique punctuation/case-normalized symbol matches,
for example Stephen Curry or Shai Gilgeous-Alexander. Native symbols are
formatted for the choice list; these are not claims of exact localized menu
spellings. The exact build and individual field layout must match. Conflicting
learned/native IDs stop resolution. Existing learned values remain available,
and the new catalog is read from bundled resources so existing installations
do not need their personal learned catalog replaced. Packaging includes it.

The English-label crosswalk now supplies 2,885 labels, joined only through
exact `enum + symbol` keys present in the current native tables. Its source is
the verbatim NBA 2K HQ glossary published in the
[builder dataset](https://github.com/lightmatmul/nba2k27-builder-dataset/blob/main/animations/glossary.json),
Git blob `8e2087db0262262146303da7508f75ae49c76418` (HQ api_version `202750199`).
This app version is not the executable fingerprint. The glossary supplies
English labels only; it never supplies roster IDs, field bindings, menu
availability, attribute requirements or write authorization. Exact native
symbols absent from that glossary remain unnamed. Abbreviated layup symbols
are not expanded by initials or guessed player matches. Conflicting label
targets, including conflicts with a native symbol's spelling, fail closed.
`--glossary FILE --glossary-source URL_OR_REVISION` adds the same label join
when running the extractor with a local copy of the full glossary.

Chew Gum's two agreeing packed property records name `GumChewer`, type
`bool32`, at player +0x10C bit 30. The existing profile matches exactly.
Standard false/true labels provide Off=0 and On=1; there is no animation enum
or transferred old-build observation. Neighboring bits still use the existing
masked writer. The catalog retains both property headers under `primitives`.

A reviewed spelling alias now maps Jumpshot Base: Harry Giles to the unique
`HARRY_GILES_III` symbol (262), corroborated by the NBA player page. Its evidence
is retained under `label_reviews`, separately from HQ labels. General suffix
removal and abbreviated-player expansion remain disabled. See
[the targeted verification queue](animation-verification-queue.md) for six
layup checks, six dunk descriptions, and seven names absent from their relevant
extracted lists. Candidate IDs in that queue are not enabled label mappings.

The supplied Signature menu screenshots establish additional field-name
translations, described in [the menu observations](signature-menu-observations.md).
Go-To Dunk Package is the first dunk slot, Crossover Combos is the native
IsoCrossCombo control, and the export's Regular Breakdown Combos uses Breakdown
Combos. Other displayed labels are accepted as aliases for existing fields.
No canonical field names, layouts, native IDs or section write hashes changed.
Imports canonicalize the source before merging. For TRC merge sources,
conflicting aliases skip only the ambiguous field and return a warning listing
both original names/values; other fields and players continue. The old workspace
value is retained and the ambiguous field is excluded from the TRC write scope.
Default canonicalization, including game previews, still rejects conflicts.

On the supplied 32-player export, 487 of 555 Signature requests now resolve
using the native lookup, label crosswalk, boolean labels, field-name aliases and
existing numeric values (up from 374, then 439 and 484). This is an offline name/layout
coverage count, not a live write test. Unresolved values remain unchanged in
the import and are skipped at game preview. Of the 68 remaining requests,
36 use four controls needing mapping/conversion decisions, seven use five layup
names without glossary labels, nine use descriptive dunk labels without a source
crosswalk, and 16 use other missing/renamed choices. See the
[remaining-value inventory](animation-sync-gaps.md). No nearest-name substitution,
cross-field ID copying, or automatic category remapping is performed.

No game process was opened and no game value was changed. No offsets or write
allowlists were expanded. Resolved names go through the existing reviewed
preview/apply transaction engine. Tests cover exact build/layout boundaries,
proof CRCs and hashes, ambiguous names, conflicting observations, explicit
nonsequential values, registration bounds, and packed Apply/Undo/Redo against
mock process bytes.

## Initial bulk discovery (historical)

An offline inspection of the installed `6AD2E48C:36532000` executable found
native symbolic animation name blocks and explicit CRC32-name/value tables.
The earlier search for display names with spaces missed these underscore-based
symbols. Individual manual observation is therefore not the only available route.

Run `python scripts/extract_animation_enums.py PATH_TO_NBA2K27_EXE OUTPUT_JSON --heuristic`
to reproduce discovery without opening the game process. The extractor matches
every symbol's CRC against contiguous 12-byte explicit records and reads each
record's stored value; it does not use the name's list position as its ID.
Matching duplicate tables must agree. Missing or conflicting tables remain
unresolved. Output includes file offsets and table hashes for further inspection.
The name-block parser is a discovery heuristic; symbol boundaries and the native
registration that binds each enum to its roster field still need verification.

The discovered jumpshot and release blocks each contain 884 symbols with four
matching explicit tables. Their Goran Dragic=197 and Kris Dunn=203 entries agree
with the two previously observed Jumpshot Base anchors. This supports further
investigation, but does not independently establish Release 1/2 field bindings.
Other candidate blocks include Free Throw (308), Motion Style (380),
Dribble Style (49), and Layup (94). Counts describe extracted native symbols,
not a claim that all choices appear in the roster editor's menu.

No learned catalog entries, memory layouts, or write allowlists were changed.
Next: verify native enum registration and field bindings, resolve ambiguous
website/display spellings, and validate a small number of independent anchors
before promoting qualified mappings through Trace's existing transaction path.
Unresolved dunk-package and other blocks require additional boundary/table work.

Three synthetic extractor tests cover explicit nonsequential values, matching
duplicates, conflicting duplicates, and missing tables.

## Earlier result

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

## User-confirmed Booker label

The user explicitly confirmed that LUP_D_BOOKER denotes Devin Booker and
requested the name translation. Layup Package: Devin Booker now resolves to
native-table ID 11 for the exact supported build. Its label review records
the user confirmation separately from HQ label evidence. No paired in-game
read or game write was performed by the agent. This resolves two more export
requests; the remaining five abbreviated layup names stay unresolved.
