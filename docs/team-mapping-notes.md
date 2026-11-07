# Team, rotation, and coaching discovery

Build: `6AD2E48C:36532000`. The initial discovery below used read-only access.
The subsequent coaching implementation is described under
[Coaching write support](#coaching-write-support).

## Concrete leads

- The installed executable contains 67 TEAMDATA and 190 STAFFDATA named setters, plus a franchise advanced-rotation entry setter and a separate user-setting PlayerMinutes setter. All 259 have retained code references in this audit.
- Complete TEAMDATA::SetLineupPlayerByIndex, TEAMDATA::SetStaff_Internal, STAFFDATA::SetCoachAttribute, and TEAMDATA::SetPlaybookID routines matched the running exact build byte for byte.
- The normal lineup setter writes player references, with one branch supporting 20 entries at the start of TEAMDATA. This agrees with the independently validated team-membership reader.
- Staff assignment uses a role-indexed array of references and additional update logic. Roles must be resolved before assigning names to slots or exposing staff edits.
- STAFFDATA::SetCoachAttribute checks values against 101 and dispatches through 24 attribute indices. Coach-data reflection lists include HelpDefense, RunPlayTendency, ZoneUsage, Tempo, BenchDepth, and other coaching/emphasis properties. Their exact enum-to-offset mapping remains to be traced.
- A separate franchise game-plan definition contains HelpDefense, RunPlayTendency, ZoneUsage, BenchDepth, BenchUtilization, offensive/defensive settings and AdvancedRotation. A roster default and an active game-plan override must not be treated as interchangeable.

## Rotation minutes

The existing raw PLAYERDATA Playing Time field has a matching named setter, whose complete code also matched the running build. Its packed layout is seven bits beginning at player-record +0x12C bit 15. The code accepts a seven-bit numeric argument; that fact alone does not establish the editor's allowed minutes range.

Across all 77 validated teams in the current loaded roster, the per-player raw values summed to exactly 240. This is strong independent evidence that these are rotation-minute allocations, rather than box-score minutes played. No per-player personal data or heap addresses are included here. An exact in-game rotation readout or the rotation-editor getter path would complete the UI interpretation check before exposing it as editable Minutes.

The GLOBALDATA_PERSISTENT_PER_USER::SetPlayerMinutes name was investigated and rejected as an allocation mapping: its input check permits only two values, so the name alone is not evidence of a player's assigned minute count.

## Next work

1. Resolve the 24 coaching attribute indices and active team-to-staff linkage, then read the matching coach values.
2. Distinguish roster coaching defaults from franchise game-plan overrides.
3. TRACE the rotation-editor read path and advanced-rotation identity/timeline representation.
4. Add readouts first, then reviewed team/linked-object transactions only after identity, range, dependency, journaling, rollback and Undo behavior are supported.


## Initial Teams implementation

Teams now presents exactly Rotation, Coaching Emphasis, and Staff. Details and
Metadata remain preserved in JSON rather than appearing as these tabs. Edit
Plays / Assign Plays are deliberately outside this implementation.

`team_sections.py` adds derived read-only sections during game roster loading:

- Rotation follows the validated team member order and reads Playing Time from
  each player, preserving zero minutes. Totals are calculated from actual data;
  240 is an observed roster result, not a hardcoded replacement.
- Coaching Emphasis reads the assigned Coach role's Help Defense, Run Plays
  Frequency, Zone Usage Frequency, and Tempo. It is explicitly labeled Coach
  defaults. Franchise/game-plan overrides are not resolved by this view.
- Staff shows assigned role/name pairs. The 32 role IDs come from the explicit
  native STAFFDATA_JOB enum table. The TEAMDATA staff setter confirms the
  role-indexed reference array; the referenced staff record must agree with
  its slot through the verified five-bit Job field.

Reflection descriptors independently identify FirstName, LastName, Job and the
four coaching fields by name CRC, offset and width. The coaching descriptors'
uint8_t type tags resolve to canonical u8 during startup; both aliases have
explicit CRCs and the offsets/width/remaining descriptor header must match.
The coach setter also writes the corresponding one-byte fields and checks the
0-100 domain. Full native routines, role table and descriptor headers are
checked against the running exact build before readouts are offered.

Team membership, source-player names/team links, staff-slot arrays, staff
names/job/data and minute values are checked for movement during the read.
Unknown values are omitted and displayed as unavailable rather than zero.
Only portable names, role IDs, player IDs and numeric readouts reach JSON;
heap pointers remain internal. No write allowlist or transaction path is
extended. These controls have no edit handlers. Search works within each tab.


Live verification of the completed tabs loaded 3,741 players and 77 teams.
All 77 teams supplied Rotation, Coaching Emphasis, and Staff readouts, including
605 validated assigned staff records. Each team's observed minutes totaled
240. An unchanged game preview planned zero writes, with writes disabled.
The regression run reported 295 passed and the same two unrelated existing
updater/website-test failures. Focused team-reader and UI tests passed, covering
code/metadata mismatches, type aliases, moved references, missing values, zero
minutes/zone usage, search, and prevention of editable controls.

## Coaching write support

The complete `STAFFDATA::SetCoachAttribute` routine and independently named
reflection descriptors establish sixteen individual byte fields, each accepting
whole numbers from 0 through 100:

- Help Defense, Run Plays Frequency, Zone Usage Frequency, Tempo.
- Off-ball Defense Aggressiveness, On-ball Defense Aggressiveness, Fastbreak,
  Crash Boards, Double Team Frequency.
- Inside Shot Tendency, Close Shot Tendency, Mid-range Shot Tendency,
  Three-point Shot Tendency, Drive Tendency, Post Up Tendency,
  Alley-oop Tendency.

Only those controls become editable, after fresh exact-build code/property,
team identity, coach identity and ownership checks pass. These are assigned
coach defaults; no franchise game-plan override is implied. The other coach
attribute indices remain unsupported rather than being inferred from nearby
bytes. Rotation, staff assignment/name editing and playbooks remain read-only.

Ownership checks enumerate all team roots referenced by the loaded roster,
including unnamed roots. Shared coaches, overlapping records, changed player
links or staff assignments, and uncertain identities fail closed. Runtime
addresses remain private, outside JSON workspaces. Both live editing and
Review Game Writes use the existing transaction engine, including mixed
player/coaching batches, journaling, full-region readback, rollback and exact
Undo/Redo. Unrelated fresh staff bytes are preserved.

Automated fake-memory tests cover all sixteen controls, range validation,
mixed transactions, Undo/Redo, partial-write rollback, changed code/metadata,
stale identities/ownership, unnamed-team sharing, overlapping records, and
read-only previews. UI tests cover staging, live-edit requests, expected old
values, error pausing and the flattened workspace change review. Development
verification against the running game uses read-only loads and previews;
it does not perform in-game write tests or claim manual confirmation of these
new controls.

The completed read-only live check loaded 3,741 players and 77 named teams.
All 77 teams passed ownership/identity validation for all sixteen controls;
ownership enumeration included 78 team roots. An unchanged preview produced
zero changes and a single staged coaching edit produced exactly one coaching
change. Game write authorization remained disabled throughout.

The final regression run reported 326 passed and the same two pre-existing
failures: the updater archive case for `TRACE/trc+.exe` and the website API
mock serialization case. Coaching transaction, team reader and UI checks
passed; JavaScript syntax validation also passed.

## November 1 extension

The [unattended audit](unattended-mapping-2026-11-01.md) adds sixteen more
controls, bringing supported coach values to 32. Lineup Form Factor appears
under Coaching Emphasis. Seven coach ratings and eight system proficiencies
appear under Staff; assignment/name entries stay read-only. Complete native
attribute/system setter bodies, their dispatch tables, and the additional
named property headers are now pinned. The original coaching setter's two
dispatch tables are also checked explicitly. All 77 observed teams passed
the expanded mapping checks using read-only game access.
