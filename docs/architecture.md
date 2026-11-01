# Architecture

## Local editor

The Windows executable defaults to `desktop.py`, which embeds the existing UI
in a pywebview/WebView2 desktop window. The local server runs on a worker thread
and stops when the window closes. Downloads use native Save As dialogs, and a
close event checks the frontend's unsaved state on a worker before allowing exit.
WebView2 is required; the obsolete MSHTML renderer is rejected before showing
the window. `--browser` opts into browser mode; `--no-browser` runs the backend
alone for diagnostics. Startup diagnostics go to the user's `desktop.log`.

`app.py` serves the browser UI and a small JSON API on loopback only, with a per-session token on save requests and exact Host checks. It has no external frontend dependencies. `roster.py` owns roster validation and atomic file persistence. Static assets ship with the Python package under `ui/`.

The browser keeps a working roster and a saved baseline. JSON imports are validated and staged, edits are reviewed against the baseline, and Save persists the document through the Python API. Unknown/custom JSON fields survive round trips. The bundled offset profile supplies player field labels; displaying a field does not assert its live address is verified. Game operations are separate authenticated API calls: status, load, preview, and apply. Import conversion and merging also run through the server validator.

`trc.py` converts name-keyed TRC exports and merges unique normalized names without changing target IDs or team assignments. Extra sections survive under metadata. `fields.py` decodes player records from the active profile and handles rating conversion and packed-bit updates. `game.py` uses `windows_memory.py` to connect directly through Win32 process APIs. `settings.py` persists the configured executable location. The UI edits this setting through a session-protected endpoint; settings changes invalidate snapshots. Legacy saved write authorization is ignored; users enable writes explicitly with **Start live editing** for the current session. The connection validates the full executable path, on-disk and in-memory PE fingerprint, process creation time, and module base. The profile's base pointer and offset chain are resolved at runtime.

Reads keep server-owned snapshots keyed by current record index. Preview creates an expiring, single-use plan; Apply accepts only its token. Writes require an explicitly enabled, matching build fingerprint, a stable process/base, and unchanged player identities/edited fields. They update only changed bytes, verify each byte, attempt rollback on failure, and save recovery snapshots to an audit log before writing. Process exit, pointer movement, stale bytes, or failed writes invalidate the affected plan; rollback uses the pinned process handle and refuses to operate on a moved array. Windows memory operations cannot make writes atomic with concurrent game activity, so the game should remain idle during updates. Loading stops at the first empty last name, matching the existing helper's enumeration rule, with a 6,000-record cap.

If the configured player pointer is empty, build `6AD2E48C:36532000` has a validated lookup using six module-relative references observed to point to a validated player table and rechecked after the user reopened the roster. All six must agree on one address, the stride/name layout must match, and a sample of distinct player names must validate on every status check. Observed references that moved into the table or became null when switching rosters were excluded. The six retained references were rechecked against a second roster. The same six module-relative references also resolved the matching roster after a game restart with a new PID and table address; they do not apply to other builds. A name-buffer fingerprint of the first 128 records distinguishes roster replacements that reuse the same table address. A controlled in-game Driving Layup change from 82 to 83 confirmed byte 171 to 174 at record offset `0x43C` on this build. Further in-game observations confirmed Speed 77 to 78 at `0x453` and Driving Layup Tendency 70 to 71 at `0x471` (7 bits, shift 7), with neighboring packed bits unchanged. An additional comparison after the restart observed Rise Up raw level 0 to 1 at `0x4D6` (3 bits, shift 7), Jumpshot Base 197 to 203 at `0x408` (10 bits), and Weight 190.0 to 191.0 at `0x108` (float32). The user identified the jumpshot labels as Goran Dragic and Kris Dunn; these observations are cataloged only for this build. Packed badge/signature neighboring bits were unchanged. Because that comparison spans a restart, it does not isolate unrelated record changes. The six individually observed fields remain documented separately. The user subsequently approved section-level compatibility for the existing Attributes, Tendencies, Badges, and Signatures mappings, plus Weight, on this exact build. All 52 attributes, 99 tendencies, 53 badges, 78 signatures, and Weight are eligible for opt-in live writes. Section approval is pinned to a hash of each section’s current field names, offsets, widths, shifts, and types; a profile change cannot silently authorize a different layout. These approvals are not claims that every field was individually observed in-game. Fields outside the individually confirmed mappings and approved section layouts remain unsupported for live writes through this lookup. Server-side edit/bulk/undo enforcement and frontend labels apply the same allowed field list. Existing transaction, verification, journaling, rollback, and history paths remain in use. The fallback uses the normal first-empty-name enumeration rule; the observed count is not hardcoded.

TRACE also tries a read-only fallback based on the public afasca NBA 2K27 offline editor's roster path (module RVA → root + 168 → count at +16 and player table at +24). That project documents a different executable build, so TRACE treats the values as an untrusted candidate: it only accepts the table if the current profile's stride and name offsets match and a sample of distinct player records validates. A roster found through the community fallback can be loaded for reading; that path does not enable live editing. Diagnostics rejects null and out-of-range pointers before following dependent lookup steps.

Raw Advanced definitions include overlapping fields and caches and remain read only. `mappings.py` promotes existing unique signature, gear, accessory, appearance, and selected vital definitions into writable categories. The 14 ambiguous advanced IDs are excluded. `ValueCatalog` persists display names by exact executable build/category/field; learning reads a loaded player’s current numeric value and does not write memory. Team writes and unknown badge aliases require further verification. `build_dry_run_plan` remains available to the older attributes-only synchronization pipeline.

`player_summary.py` adds read-only list information for build `6AD2E48C:36532000`. Primary/secondary position values at `0x12D` were compared against the user's displayed PG, SG/SF, PF/SF, C/PF, and absent-secondary examples. OVR uses the existing float cache at `0x1AC` only when its validity bit at `0x370` is set and the rounded result is in range. Observed values 76.0188 and 87.7723 matched displayed overalls 76 and 88. These cache fields remain unwritable. Attribute edits clear the UI's displayed overall until the roster is reloaded; no attribute average replaces it.

For team display, the observed player pointer at `+0x60` leads to a membership list of up to 20 player pointers. Team nickname, city, and abbreviation were observed at list-relative offsets `0x2FA`, `0x32C`, and `0x350`. Team reads require exact-build/stride checks, valid terminated text, and exact agreement between the team's member pointers and loaded players pointing back to that team. City may be empty for national/special teams. Bibby and Johnson were independently identified by the user as Atlanta Hawks players, matching the observed Hawks/Atlanta/ATL object; 78 linked groups validated in the current roster. Runtime addresses are resolved afresh and never stored as mapping constants. Null, inconsistent, or unreadable links are unknown, not presumed free agents. Team assignment writes remain unsupported.

Additional controlled edits on this build confirmed jersey Number 10 to 90 at `0x114` (7 bits, shift 11), Shoe Home Style 5024 to 5002 at `0x184` (13 bits, shift 0), and Headband 1 to 0 at `0x1C8` (4 bits, shift 22). The user identified the shoe labels as Air Jordan 2010 and Air Jordan III and the headband labels as Style 2 and Style 1; these exact-build names are cataloged. The three field masks preserved neighboring bits and are individually eligible for opt-in editing. The game's UI also changed the home shoe colorway and accessory-related fields during those edits; those companion fields are not thereby enabled or automatically reproduced by changing the observed field alone. Visible rendering after a native write still requires an in-game check.

Under Basket is the first observed hot-zone mapping on this build. An isolated Hot to Cold edit changed only byte `0x1CC` from 22 to 20; Cold to Neutral changed only that byte from 20 to 21. These observations establish bits 0-1 as Cold=0, Neutral=1, Hot=2, with all upper bits preserved. The definition carries an exact-build restriction enforced in decoding, previews, live/bulk writes, and the UI. Pattern 3 is rejected. All 13 remaining zones were subsequently mapped using the screen-confirmed baseline and three controlled batches on the same player/process/roster. Every remaining zone was observed in all three states. Encoding each complete batch reproduced its entire after-record exactly, with no unexplained changes. The 14 two-bit masks are disjoint. Mid-Range Right crosses a byte boundary; an apparent alternative at 0x1CC bit 5 was rejected because it overlaps the independently confirmed Mid-Range Left Center and Center masks. All zones carry the same exact-build restriction and reject state 3. These are individually observed mappings, not a section-wide assumption. Existing transaction, journal, readback, rollback, and Undo paths apply.

| Hot zone | Record offset | Starting bit | Width |
| --- | --- | --- | --- |
| Under Basket | 0x1CC | 0 | 2 |
| Close Left | 0x1CF | 2 | 2 |
| Close Middle | 0x1CC | 2 | 2 |
| Close Right | 0x1CF | 4 | 2 |
| Mid-Range Left | 0x1DC | 3 | 2 |
| Mid-Range Left Center | 0x1CC | 4 | 2 |
| Mid-Range Center | 0x1CC | 6 | 2 |
| Mid-Range Right Center | 0x372 | 3 | 2 |
| Mid-Range Right | 0x37E | 7 | 2 |
| Three Left | 0x1D2 | 6 | 2 |
| Three Left Center | 0x1D3 | 6 | 2 |
| Three Center | 0x177 | 0 | 2 |
| Three Right Center | 0x35F | 5 | 2 |
| Three Right | 0x1CF | 0 | 2 |


The English shoe catalog was located read-only in two agreeing loaded copies on this build. Its observed 128-byte records contain an 80-byte UTF-16 name buffer and two 16-bit IDs immediately before the name. The 601 readable shoe records include the independently observed pairs Air Jordan III=5002 and Air Jordan 2010=5024. Four labels have multiple IDs and are excluded from automatic name resolution. Initially, only the 559 unambiguous names whose two IDs agree are imported into the exact-build Home Shoe catalog (557 additions to the two existing learned names). Entries whose IDs differ remain pending an in-game special-edition selection check. These observations do not populate Away Shoe or other item categories, and no runtime catalog addresses are shipped. Source provenance is retained on imported names; existing learned values are not overwritten.

A third in-game selection confirmed regular Air Jordan XXXIII=5032, matching both catalog ID columns. The user did not find a PE option, so the separate Air Jordan XXXIII PE entry (5125/5032) remains excluded with other differing-ID variants; it is not relabeled as the regular shoe.

Five further numeric Vitals mappings were confirmed together against Mike Bibby's in-game edits: Birth Day 13 to 14, Birth Year 1978 to 1979, Years Pro 12 to 13, Peak Start Age 27 to 26, and Peak End Age 28 to 29. Encoding only those five requested changes reproduced the entire captured after-record exactly, including the shared birthday/peak-age word, with every other bit preserved. These five fields are eligible for opt-in editing; Years Pro is exposed in Vitals with an exact-build restriction while its original Advanced definition remains read only.

The user also confirmed seven displayed numeric Vitals values against native reads: Min Potential=81, Max Potential=93, Bust Percent=1, Boom Percent=7, Play for Winner=74, Financial Security=53, and Loyalty=82. These are screen-readout confirmations rather than before/after change captures. Exact-build Vitals definitions expose these values for opt-in editing while their original raw Advanced definitions remain read only. The potential controls accept 25-99, and percentage/priority controls accept 0-100; the unused seven-bit range above these limits is rejected. Packed-field transaction and undo checks preserve neighboring bits. College / From and AVG Percent were mapped separately below.

Choice-field captures established Birth Month May=5 and June=6, Dominant Hand Left=0/Right=1, Dominant Dunk Hand Left=0/Right=1/Either=2, Forced Non-Starter Off=0/On=2, and Play Initiator No=0/Yes=1. The five initial transitions exactly reproduced the after-record when encoded together; a separate Right to Either dunk-hand change affected only that field's bits. These fields are individually eligible on this build. Month remains numeric (1-12); the other four use the observed named choices. Unobserved forced-starter and dunk-hand states are rejected. Transactions refuse to overwrite any current value outside a field's supported values, preserving the ability to undo without inventing an unknown state. The original Advanced forced-starter definition remains read only.

Location/play-type edits confirmed FIBA Team None=65535 to USA=69, High School Phoenix=87 to Pittsburgh=88, Birthplace Philadelphia=86 to Phoenix=87, and a four-slot rotation of P&R Point=5, Isolation Point=2, Mid Range=14, and 3PT=15. Encoding those seven edits reproduced the whole after-record exactly. These fields are exposed as exact-build Vitals definitions; their Advanced counterparts remain read only. A nearby 128-byte city-record list agreed in two loaded copies and matched the three independent city anchors. Its 113 unique labels populate both location selectors; Athens, Bronx, Honolulu, and Portland each had multiple IDs and are excluded from unqualified name lookup. Existing unnamed numeric IDs remain visible as unnamed IDs and are preserved for undo; no labels are assigned to them. Position and Secondary Position use the previously confirmed position readouts, with native edit/undo tests and frontend position-summary refresh. Position edits clear the displayed overall until reload rather than calculating an estimate.

Injury captures established more than a type/duration pair. Creating Injury 1 as Appendectomy at seven days set type=1, duration=10080, status=4, a start date, and original type=1. A duration-only seven-to-eight-day edit changed 10080 to 11520 with every other record bit unchanged. Creating Injury 2 as Back Spasms at ten days set type=3, duration=14400, status=1, a start date, original type=3, and the latest-injury slot flag. Its isolated ten-to-eleven-day edit changed 14400 to 15840 with every other bit unchanged. Thus both observed durations use 1440 units per displayed day.

The two Vitals duration controls use an `injury_days` codec, restricted to this build and whole-day values within the 20-bit capacity (0-728 for decoding). Live edits require a nonzero existing type, an observed active status (1 or 4), and positive old/new durations. Zero-duration clearing and injury creation are rejected; the raw type/status/date/history fields remain read only. Non-whole-day raw durations are not rounded or overwritten. Duration writes use the existing transaction path, preserve every surrounding bit, and support exact undo. Known injury labels are shown read-only from the observed catalog; they do not authorize type writes.

Name captures on this build confirmed both UTF-16 buffers and their companion state: an isolated Joe to Joey edit set FIRSTNAMEVETTED=1 and FIRSTLASTNAMESID=65535 while leaving LASTNAMEVETTED=0; a later Johnson to Johnsone edit set LASTNAMEVETTED=1. Restoring visible spellings inside 2K leaves these edited-name flags and sentinel ID set. Native name transactions reproduce the observed companion updates, journal their exact prior values, and restore those values plus full original name buffers on Undo. Companion layouts must match before name writes are enabled.

During a native rename, the roster identity guard masks only the exact name bytes scheduled for that transaction, after a full original identity check. All other sampled name bytes and process/pointer identity remain guarded. Intermediate name validation may be bypassed only inside that pinned transaction; the completed names must pass normal roster validation before commit. The session identity is then refreshed to the newly written names. Mock-process tests cover first/last edits, combined names, undo/redo, partial-write rollback, invalid companion layouts, and refusal to roll back onto an unrelated roster change.

The app is organized around four boundaries:

1. **TRC adapter** — retrieves or imports player data and converts it into the internal model.
2. **Normalizer/validator** — normalizes names, IDs, ratings, and attribute ranges before sync.
3. **Address profile** — selects a verified NBA 2K27 memory map for the exact build and platform.
4. **Sync engine** — compares source and target values, produces a dry-run plan, and only then performs approved writes.

## Safety and correctness requirements

The 16 Personality badge definitions are verified for build
`6AD2E48C:36532000` through the named native setter masks, matched against the
running executable, the registered badge-level enum, and three isolated
in-game boolean changes. They extend the original 53 badge mappings to 69,
with the original layouts unchanged and the updated section hash pinned to
the verified union. Boolean controls allow only 0/1; Work Ethic and
Marketability allow only tiers 0–4. Unsupported current values cannot be
overwritten. These fields use the existing packed-field transaction and
history path. See [the mapping evidence](personality-mappings.md) for exact
layouts, internal names, enum verification, and the distinction between
code-confirmed and individually observed fields.

Body values on build `6AD2E48C:36532000` follow the player-record pointer at
`+0x78` to a separate allocation. Its `+0x0` low 15 bits store tenths of a
millimetre: observed Height 74 to 75 inches changed 18796 to 19050. The high
bit is unrelated and preserved. The four
float32 scales decode as `50 + (scale - 1) / step`: Wingspan at `+0xC` and
Shoulder Width at `+0x8` use step 0.002; Neck Length at `+0x10` and Trunk Length
at `+0x4` use step 0.004. All four were observed at 50; Wingspan was isolated
at 51. Two combined captures confirmed Shoulder/Neck/Trunk at 52/53/54 and
54/52/53 respectively. These are not observations at every slider value.
The low 15-bit measurement at `+0x2` changes with Height, Wingspan, and Shoulder
Width; its calculation has now been traced through the native forward helper
and model geometry routine, reproducing all five saved captures exactly.
Reads require the exact build and stride, a readable aligned
pointer, stable player identity/pointer/data, and finite integral slider
readouts within 0–100. Unknown values are omitted. These definitions are kept
outside RecordProfile because their offsets are relative to another allocation.
The transaction writer now prepares both player-record and Body ranges before
any write. Body edits require runtime code hashes and constants matching the
verified calculation, a supported stable 22-bone model, unchanged Body data and
pointer, consistent stored measurements, and exclusive ownership by one loaded
player. The model fingerprint participates in session identity. Body pointers
are guarded through write verification and rollback; a moved pointer prevents
rollback into the old allocation. Journals include the separate region's
address and full before/after bytes. Undo and Redo restore the exact captured
bytes and refuse stale or unrelated changes. Mixed bulk edits remain one
transaction and one history entry. Weight retains its existing player-record
mapping. See [Body mapping details](body-mappings.md).

- Never infer an address from a different NBA 2K27 build.
- Validate the target process identity before reading or writing.
- Prefer stable player IDs over name matching.
- Keep writes disabled by default.
- Log each planned and completed field update.
- Fail closed when the build, address profile, or player mapping is unknown.

Live editing is a session-scoped opt-in endpoint. Starting it probes write access and binds authorization to the loaded process/build. Single-field requests use the same transaction writer as bulk Apply. The writer reads fresh record bytes, validates requested old values, preserves unrelated fields/bits, journals and verifies changed ranges, and attempts rollback on failure. Successful transactions feed undo/redo stacks. Undo validates that each affected field still holds the value written by the transaction. Requests are serialized by the local server; the UI also serializes edits and pauses its queue after an error. Imports do not implicitly write fields.

The mapped schema is returned to the UI with explicit writable/kind/bits metadata; frontend live capability follows that schema. Weight uses float32 with decoded readback values. UTF-16 name transactions retain original field buffers so Undo can restore padding exactly. TRC field-name aliases are canonicalized without guessing enum IDs, and conflicting aliases are rejected. Before/after calibration captures are read only and stored with process identity, record bytes, and changed-bit evidence; no inferred offset is automatically enabled.


## College / From and AVG Percent

On build `6AD2E48C:36532000`, an isolated College / From change from Arizona
to Argentina changed only the player-record reference at `+0xB0`. Reading the
old and new 64-bit references returned the exact displayed names as terminated
UTF-8 text in a 48-byte name area. Immediate neighboring records were also
named college/country entries at 72-byte spacing; that observation does not
establish catalog boundaries or authorize reference writes. `player_college.py`
reads the current label only after checking build/stride, pointer range and
alignment, termination, text validity, and stable player identity/reference/name
bytes. Only the label is stored as `metadata.college_from`; runtime addresses
are never persisted as roster values. Vitals displays it read-only. Editing
requires a validated live catalog resolver and reference transaction checks.

The user confirmed AVG Percent=92, Bust=1, and Boom=7. An isolated AVG 92 to 91
edit changed exactly the existing BORINGPERCENT definition at `+0x358`, seven
bits starting at bit 20. Encoding that edit reproduced the entire after-record
with Bust/Boom and every other bit unchanged. Vitals exposes AVG Percent as an
individually enabled exact-build field with values 0-100; the original raw
Advanced definition remains read-only. Its bits neighbor Injury 2 duration,
so normal masked writes, journaling, verification and Undo remain required.


## Additional bounded setters

The [setter audit](setter-audit-2k27.md) identifies 48 further displayed packed
fields whose complete bounded setter routines matched the running build:
42 accessory frequency/color controls, Preferred Shorts Type, both undershirt
colors, Shorts Length, Skin Type, and Jersey Bagginess. Numeric bounds come
from each routine's successful read/AND/OR/write path, not guessed enum names.
`setter_mappings.py` pins each layout, complete code SHA-256, and accepted
value set. The observed-build allowlist requires all three to match; the
transaction writer independently checks requested setter fields even when
the ordinary profile-pointer path is used. A code/layout/range/build mismatch
leaves the affected field unsupported. Definitions carry exact-build limits;
raw Advanced definitions remain read-only. The writer preserves every other
bit and uses existing journals, verification, rollback, and Undo/Redo.
These are static-code plus runtime-code confirmations, not claims that all
48 fields were manually edited in 2K or that their visual effects were tested.


## Field display preferences

The fourth sidebar page, Settings, provides Show advanced fields. It initially
filters Vitals only, preserving the existing game order and all hidden roster
values. The everyday list is First Name, Last Name, Position, College / From,
Birthplace, Number, Dominant Hand, Dominant Dunk Hand, Injury 1 Type, Injury 1
Duration Days, Play Initiator, and Play Types 1-4. Full Vitals remains available
when the toggle is enabled. The preference is stored in browser localStorage
outside the roster; unavailable storage falls back to the current session.
The desktop WebView already uses persistent storage. Settings does not create
roster changes, save JSON, or authorize game writes.

Vitals Potential reads the Attributes Potential value directly and is read-only;
no duplicate Vitals value is maintained. Legacy/custom Vitals Potential values
remain preserved in the document but are not displayed as a competing control.
Navigation to Settings hides roster controls and does not select a nonexistent
roster collection. Late roster-list/inspector refreshes ignore non-roster pages.


## College reference transactions and further native enum evidence

The later [mapping pass](read-only-mapping-pass.md) extends the initial read-only
college readout. A roster load independently supplied 362 distinct college
references, with a greatest-common-divisor spacing of 72 bytes. Every one of
the 654 records between the lowest and highest references had a valid,
terminated name. Duplicate names are excluded from qualified lookup; 652
choices remained. This is an observed bounded span, not a guessed global
catalog start/count. Runtime catalog bytes must remain identical, and several
loaded player records must still reference entries in that span. Build,
stride, process creation, module base, roster base and field layout are guarded.

The private `college_reference` codec writes only player +0xB0. GameConnection
resolves submitted labels to validated catalog entries; numeric references are
rejected at the public normalization boundary. Public load/preview/edit/bulk/
Undo responses and JSON field values contain labels, not addresses. Raw
references remain only in private session history and normal local recovery
journals. Catalog mutation, moved sources, wrong layouts, ambiguous names and
stale player bytes fail closed. The existing changed-byte writer handles
journaling, readback, rollback and exact Undo/Redo. No referenced college record
is modified. The record-level pointer-only behavior is independently anchored
by the prior isolated Arizona-to-Argentina capture.

Six further bounded setters use scaled LEA addition instead of OR. Their
accepted argument ranges cannot carry into neighboring bits, and their complete
code matches the running build. They supply Left Elbow/Fingers/Knee Away Color,
Right Wrist Away Color, Shorts Away Color and Undershirt Frequency. Away Shoe
style is separately proven by the named high-13-bit branch in the shared style
routine. Its numeric range is 0-8191; no Home Shoe labels or colorways are
transferred. All seven use the existing code/layout/range pins.

Five native enum name blocks and their unique explicit CRC32-name/value tables
matched the running executable: PLAYERDATA_INJURY (157), ACCESSORY_FREQUENCY
(5), SKINTYPE (3), HEADBANDLOGO_POSITION (7), and PLAYTYPE (16). Names improve 23
choice controls and both injury readouts. User-observed aliases retain priority.
Headband's separate enum was not applied because it does not establish the
screen's Style 1/Style 2 interpretation or the setter's full accepted domain.
Injury type creation/clearing, linked appearance, team and complex item-selection
protocols remain unsupported by this pass.


## Team section readouts

The Teams inspector uses Rotation, Coaching Emphasis and Staff rather than the
player category schema. `team_sections.populate_team_sections` enriches teams
after their name and membership links validate. `team_sections.py` separately
pins team/staff/Playing Time native code, reflection property headers, and the
explicit 32-role enum. It supports the exact 6AD2E48C:36532000 build only and
handles the known uint8_t-to-u8 reflection type alias. Per-group read checks
reject moved memberships, player identities, staff arrays/records and minutes.
Missing or invalid values are omitted, with no fabricated zero or staff name.

These sections contain portable roster data; runtime pointers are never
serialized into a workspace. Rotation and Staff remain read-only. Coaching
values are staff defaults, distinct from franchise game-plan overrides.
Playbooks and advanced rotation timelines remain out of scope.

`coaching.py` prepares 16 independently verified, integer 0–100 coach-default
byte updates. It does not execute a separate writer. Team changes use the
existing session-protected edit endpoint and `GameConnection` transaction
engine alongside player/Body changes, with the same journal, rollback,
readback and Undo/Redo behavior. They require a separate private team mapping;
the player-field allowlist grants no team authorization.

Ownership validation includes every team referenced by the loaded player
array, including unnamed teams. The coach must have exactly one incoming
staff-slot reference, occupy the Coach role, and not overlap known module,
player, team, Body or other referenced staff regions. Before preview and
writing, guards recheck the exact process/build, native code and property
headers, player team/Body links, roster-end sentinel, all staff-slot arrays,
team membership/name signature and coach name/role. Requested old values
must match a fresh read. Transactions preserve unrelated staff bytes and
verify the whole resulting staff record. Private addresses are used only by
server-side snapshots and local recovery journals. See
[team mapping notes](team-mapping-notes.md#coaching-write-support).
