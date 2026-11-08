# Unattended mapping audit — November 1, 2026

Build: `6AD2E48C:36532000`. Actual game access was read-only throughout.
No setter was executed, memory written, in-game roster saved, or personal
workspace overwritten. The audit used the open roster and installed executable.

## Sixteen additional editable controls

| Location | Controls | Evidence |
| --- | --- | --- |
| Teams → Coaching Emphasis | Lineup Form Factor | Its named byte property and the complete `STAFFDATA::SetCoachAttribute` range check/store path |
| Teams → Staff | Coach Offense, Defense, Business, Training, Charisma, Analytics, Potential | Seven named properties and the complete `STAFFDATA::SetAttribute` setter; the coach setter independently writes these same seven bytes |
| Teams → Staff | Balanced, Grit and Grind, Pace and Space, Perimeter, Post, Triangle, Seven Seconds, Defense First proficiencies | Eight named properties and the complete `STAFFDATA::SetSystemAbilityByIndex` byte-store setter |

The seven attribute controls and Lineup Form Factor have a native unsigned
0–100 check. The system setter accepts an unsigned byte without a numeric
range check; TRACE deliberately supports only 0–100, a conservative subset,
and rejects loaded values outside that subset. All eight system values fell
within this range across all 77 observed teams. Labels describe the native
properties and are not claims about exact in-game menu wording.

All relevant complete function bodies, dispatch tables, property name CRCs,
offsets, widths and packed layouts are pinned and checked against the running
build. Known startup type aliases are permitted explicitly: uint8_t/u8 and
uint32_t/u32. Coach Potential is the second byte of a reflected four-byte
word, not an overwrite of that whole word.

These additions bring supported coach values from 16 to 32. The Staff controls
edit the assigned coach's values, not another staff member or the assignment.
Live edits and reviewed bulk writes share the existing ownership, identity,
old-value, journaling, readback, rollback and Undo/Redo guards. No process
addresses are stored as portable roster values.

## Live observations

- Loaded 3,741 players and 77 named teams. All 77 teams passed validation for
  all 32 coach values. All sixteen newly supported values were readable and
  within TRACE's accepted range for every team.
- An unchanged roster preview produced zero changes. A locally staged change
  to each of the sixteen additions produced exactly sixteen coaching changes.
  Game write authorization remained disabled.
- Native rotation normalization routines at module-relative locations already
  identified through setter call references matched the running code in full
  (511 and 1,644 bytes). The first totals and rescales multiple players' packed
  Playing Time fields and then calls the second routine. This is evidence of a
  team-level workflow; it does not establish a safe standalone Minutes editor.

No live heap addresses or personal player/staff records are included here.

## What remains unresolved

The loaded player profile still has 49 unsupported definitions: two Vitals,
twelve Gear, thirty-four Accessories and one Appearance. These are the same gear/accessory,
Face Type, Hair Length and My Player Clothes Type definitions listed in the
[earlier read-only pass](read-only-mapping-pass.md#still-read-only-or-unsupported).
No additional player definition was enabled merely because its current value
looked plausible.

| Area | Reason it remains read-only | Next safe investigation |
| --- | --- | --- |
| Rotation minutes | A seven-bit storage setter alone does not specify the rotation screen's domain, normalization and related state | Trace the rotation screen's getter/commit path through the verified multi-player normalization routines |
| Staff assignments and names | Assignment updates role-indexed references and other state; renaming may affect identity/catalog information | Follow complete assignment and name commit paths and establish exact ownership and companion updates |
| Bench Depth, Bench Utilization, Early Offense and other staff properties | Named storage properties are identified, but their complete write protocol and UI domain are not established by the enabled setters | Locate their actual editing paths rather than borrowing another control's range |
| Injury type creation/clearing | Type, date, status and history form a coordinated workflow | Trace the complete injury commit path, including cleanup |
| Complex clothing, accessories, shoe colorways | Some menu routines update shared configurations or pre-injury accessory state; nearby masks do not establish the full operation | Follow those configuration updates and verify linked-object ownership |
| Linked appearance | Separate APPEARANCEDATA records cannot be treated as player-record offsets | Resolve and validate the actual appearance receiver and sharing before exposing writes |
| Team assignment, contracts, playbooks | Multiple objects or related values are involved | Establish the full transaction and validation rules first |

## Automated verification

Focused transaction, team-reader and UI checks cover every supported byte,
exact Undo/Redo, surrounding packed bits, mixed batches, stale ownership,
code/property/type mismatches, and mutations of each native dispatch table.
The Staff UI displays the additional rating controls separately from Coaching
Emphasis while retaining the existing staged/live editing flow. These are
simulated-memory write tests, not claims of manual in-game confirmation.

Final regression result: **332 passed**. JavaScript syntax and diff whitespace
checks also passed. No game write was used for this verification.
