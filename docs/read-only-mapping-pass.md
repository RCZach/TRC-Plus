# Read-only mapping pass

Build: `6AD2E48C:36532000`. All access to the actual game was read-only. No native setter was executed, game write performed, roster saved in 2K, or personal JSON workspace saved by this pass.

## Newly editable controls

| Control | Verified behavior |
| --- | --- |
| College / From | Named reference to a validated session catalog; 652 unambiguous choices in the observed 654-record span |
| Away Shoe style | Numeric style ID, 0–8191; the named away branch preserves Home Shoe and vendor bits |
| Undershirt frequency | 0–4, with native Always/Often/Sometimes/Rarely/Never choices |
| Left Elbow away color | Numeric ID, 0–7 |
| Left Fingers away color | Numeric ID, 0–7 |
| Left Knee away color | Numeric ID, 0–7 |
| Right Wrist away color | Numeric ID, 0–16 |
| Shorts away color | Numeric ID, 0–7 |

The seven scalar additions bring the complete-code-pinned setter group from 48 to 55 fields. Their entire native code matched the running exact build. The normal encoder rejects out-of-range values rather than reproducing a native clamp. Runtime code, field layouts and accepted value sets remain pinned; a mismatch disables the affected field. Color labels and Away Shoe names are not copied from another control.

## College reference validation

- 362 distinct references in the loaded roster establish 72-byte record spacing. Every record between the lowest and highest references has a valid terminated name. No global catalog boundary is guessed.
- The 654 observed records contain 652 uniquely named choices. Duplicate labels are omitted from qualified lookup. The catalog may be a subset of the game’s complete catalog.
- Process creation, module base, build, stride, roster base, exact field layout, full catalog bytes and multiple incoming references from the loaded roster are checked.
- Public input and JSON values are names. Public numeric-address input is rejected. Public load/preview/edit/bulk/Undo/Redo results do not expose college addresses. Private transaction history retains exact old references so Undo restores the original entry.
- Updates touch only the player’s eight-byte reference at +0xB0. They do not modify shared college records. The isolated Arizona → Argentina capture established that pointer-only record behavior.
- Journaling, exact changed-byte writes, readback, rollback and Undo/Redo use the existing transaction writer. Tests cover mixed/multiple college changes, stale catalogs, duplicate names, failed writes, and renaming source players.
- A fresh read-only roster load returned 3,741 players and validated all 55 scalar guards plus College / From. A named Arizona → Argentina preview succeeded with writes disabled.

## Named menus and readouts

Five native enum name blocks and their explicit CRC32-name/value tables matched the running executable:

| Native enum | Entries | Use |
| --- | --- | --- |
| PLAYERDATA_ACCESSORY_FREQUENCY | 5 | Frequency choices |
| PLAYERDATA_SKINTYPE | 3 | Skin Type choices |
| PLAYERDATA_HEADBANDLOGO_POSITION | 7 | Headband Logo Position choices |
| PLAYERDATA_PLAYTYPE | 16 | All four play-type menus |
| PLAYERDATA_INJURY | 157 | Both read-only injury-type labels |

These populate 23 named choice menus. Existing in-game-observed labels retain priority. Other names are formatted native enum identifiers, not claims that every label exactly matches the game’s current menu wording. The separate Headband enum was deliberately not applied: it does not establish the observed Style 1/Style 2 labels or the setter’s full accepted domain.

## Still read-only or unsupported

- **Potential in Vitals:** intentionally mirrors Attributes and stays read-only, as requested. It is not an unmapped field.
- **Injury types:** full IDs/names are identified, but create/change/clear behavior also touches dates, status and history. Low-level type setters alone do not establish that whole workflow. Existing active-duration edits remain supported.
- **Team assignment:** pointer and membership changes require graph-level handling of source/destination team objects.
- **Contracts:** native setters are located, but their complete UI workflow, option meanings and dependent values have not been established.
- **Linked appearance:** 39 APPEARANCEDATA setter names are located. Their receiver and allocation must be validated separately; offsets are not assumed to be player-record offsets.
- **Raw Advanced and Metadata:** many entries are duplicates, caches, history or workspace data. They are not automatically candidates for live editing.

The remaining existing player-record definitions outside the runtime allowlist are listed below. This excludes the separate injury-type projections, team/contract workflows and intentionally read-only Potential mirror.

| Section | Remaining definitions |
| --- | --- |
| vitals | Face Type, Hair Length |
| gear | Bench Outfit, In Game Hoodie, Pre-Game Outfit, Shirts Items, Shoe Away Color Way, Shoe Home Color Way, Shoe Locked Vendor, Socks Item Away, Socks Item Away Color, Socks Item Home, Socks Item Home Color, Warm-Up Outfit Configuration |
| accessories | Accessories With Headband, Accessories With Out Headband, Facemask Type, Goggles Item Color, Goggles Type, Headband Ability, Headband Custom Color, Is Arm Frequency Paired, Left Arm, Left Arm Tape Item, Left Arm Tape Item Away Color, Left Arm Tape Item Frequency, Left Arm Tape Item Home Color, Left Elbow, Left Fingers, Left Wrist, Right Arm, Right Arm Tape Item, Right Arm Tape Item Away Color, Right Arm Tape Item Frequency, Right Arm Tape Item Home Color, Right Elbow, Right Fingers, Right Wrist, Uses Mouthpiece, Is Knee Frequency Paired, Is Leg Frequency Paired, Left Ankle, Left Knee, Left Leg, Right Ankle, Right Knee, Right Leg, Shorts Items |
| appearance | My Player Clothes Type |

Complex gear/item selections were inspected but left unsupported where their UI routines update a shared configuration object or pre-injury accessory state. Their next safe investigation is additional call/data-flow inspection, not guessing a numeric value or copying another field’s labels.

## Validation

The complete regression run reported 279 passed and the same two previously observed unrelated failures: the updater legacy-executable path case and a website API test’s non-serializable Mock. Focused college, named-enum, setter and UI checks passed; further college/source-player rename integration checks also passed. Syntax and whitespace checks passed. Actual game access remained read-only throughout.

An unchanged preview of all 3,741 loaded players produced zero planned writes. The college catalog remained valid after source-player renames in simulated bulk/Undo tests. Duration edits now also reject injury type IDs outside the verified 1–156 active-type domain.
