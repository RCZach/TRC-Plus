# TRACE

[Download the TRACE 0.5.1 beta](https://github.com/RCZach/TRC-Plus/releases/tag/v0.5.1).
Beta downloads are manual; the in-app updater checks stable releases only. See
[publishing updates](docs/updates.md) for the release process.

## TRACE UI

### Portable Windows release

Extract the entire `TRACE-0.5.1-windows-x64.zip`, then double-click
`TRACE.exe`. It opens its own desktop window. Keep its `_internal` folder beside
the executable. Closing the app window also stops its local backend.
Python and Cheat Engine are not
required. See `START HERE.txt` in the release for the game connection workflow.
The window uses Microsoft Edge WebView2 Runtime and .NET Framework 4.6.2 or
newer, normally available on current Windows 10/11 computers. If WebView2 is
missing, install it from https://developer.microsoft.com/microsoft-edge/webview2/.
Startup errors are recorded in `%LOCALAPPDATA%\TRACE\desktop.log`.

Packaged releases keep each Windows user's settings, workspace, learned names,
and recovery logs in `%LOCALAPPDATA%\TRACE`. Updates can be extracted
into a new folder without replacing those files. Personal rosters, connection
settings, recovery logs, and development tools are excluded from the release.
On first launch, TRACE copies saved files from the previous TRC+ or TRC Roster
Studio data folder if the TRACE folder does not exist yet. The original files
are kept. Install TRACE from a new folder once when upgrading from TRC+; the
renamed app uses a new release package name.

To build on 64-bit Windows with Python 3.11+, install
`python -m pip install -r packaging/requirements-build.txt`, then run
`python packaging/build_windows.py`. The executable folder, versioned ZIP, and
SHA-256 checksum are written to `dist/`.
Run `python packaging/verify_windows.py` to check the extracted release with an
isolated user directory and Python removed from its executable search path.

### Running from source

Double-click `TRACE.cmd` on Windows (Python 3.11+ required). The editor opens at `http://127.0.0.1:8765` and runs only on your computer. Leave its terminal open while using the editor; press Ctrl+C there to stop it.

Alternatively, install with `python -m pip install -e .`, then run `TRACE` or `python -m trace_app.app`. Options: `--port 8765`, `--data path/to/roster.json`, `--profile config/offsets_2k27.json`, `--no-browser`.
For the desktop window from source, install `python -m pip install -e ".[desktop]"`
and run `TRACE --desktop`. Packaged releases default to the desktop window;
`--browser` is available as an explicit fallback, and `--no-browser` runs only
the local server for diagnostics.

If the requested port is occupied, the launcher opens this editor on a separate available port and prints its URL. Use the newly opened page. After updating the code, restart the editor's terminal process; refreshing the browser alone cannot update the running backend.

- Settings is the fourth sidebar page. **Show advanced fields** restores the full Vitals list; the default view shows the everyday identity, hand, Injury 1, and play-type controls in their existing order. This display preference is remembered locally and never removes hidden values. Vitals Potential is a read-only mirror of Attributes → Miscellaneous → Potential, visible in the full list.
- Browse players and teams; search names/IDs and filter players by team.
- Edit player attributes, tendencies, badges, vitals, signatures, advanced values, metadata, names, and team assignments.
- Browse the bundled player field definitions; blank fields are unset, not zero.
- Vitals follows the game's field order. Existing Advanced definitions are shown there as read-only raw values. College / From offers named choices when a live catalog validates; AVG Percent supports exact-build live editing from 0 to 100. Potential is shown from Attributes, where it remains editable.
- Body contains Height, Weight, Wingspan, Shoulder Width, Neck Length, and Trunk Length. Build `6AD2E48C:36532000` supports opt-in live editing of all six. Enter Height in whole inches; the four proportion sliders use 0–100. Body writes preserve packed flags and update the dependent wingspan measurement using the verified native calculation. Reload after in-game changes. Unverified models, inconsistent values, and shared Body data remain read-only. Live and bulk edits support journaling, readback verification, rollback, and exact Undo/Redo. Weight keeps its existing player-record mapping; Body values retain Vitals JSON storage. See [Body mapping and transaction details](docs/body-mappings.md).
- Shoes / Gear follows Body, with the game's ordered shoe, sock, undershirt, shorts, and bagginess controls. Other existing gear definitions remain under Other Gear. Display labels retain their original Gear, Accessories, or Appearance storage and build-specific write restrictions; unverified IDs remain unnamed.
- On build `6AD2E48C:36532000`, 48 additional numeric controls are verified through the running game’s setter code: accessory frequencies/colors, Preferred Shorts Type, undershirt colors, Shorts Length, Skin Type, and Bagginess. Unknown choice labels remain numeric. These controls require matching native code, field layouts, and value limits before opt-in writes. See [the mapping audit](docs/setter-audit-2k27.md).
- Accessories follows Shoes / Gear, with Upper Body and Lower Body filters based on the existing profile groups. Field search works within either group; custom fields without a group remain under Other. The shorts controls shown in Shoes / Gear are not duplicated here. Displaying existing definitions does not verify their in-game choice labels or enable writes on an unsupported connection.
- Hot Zones includes all 14 court zones in game order, with Cold, Neutral, and Hot choices. Each mapping was confirmed against controlled in-game changes on build `6AD2E48C:36532000`; TRC sync resolves these names from the verified profile without **Learn name**, and opt-in live edits use the existing verification and Undo controls. Other builds remain read-only until verified.
- Filter Attributes by scoring, playmaking, athleticism, defense, durability, or miscellaneous (Intangibles and Potential) alongside field search. Custom fields without a category remain available under Other.
- Tendencies has Jump Shooting, Layups and Dunks, Drive Setup, Driving, Passing, Post Game, Freelance, and Defense filters. Badges has Finishing, Shooting, Playmaking, Defense, Physicals, Rebounding, and Personality filters. All 99 tendencies and 69 badges are grouped. Build `6AD2E48C:36532000` supports 16 Personality mappings: Reserved through Enforcer use Unequipped/Equipped; Work Ethic and Marketability use Unequipped/Bronze/Silver/Gold/Hall of Fame. These exact-build fields support opt-in live editing and Undo; other builds cannot write them. Unknown tier patterns are omitted and cannot be overwritten. Search combines with these filters, and custom fields remain under Other. See [Personality mapping evidence](docs/personality-mappings.md).

- Teams has Rotation, Coaching Emphasis, and Staff tabs. On build `6AD2E48C:36532000`, 32 validated coach controls support opt-in live editing and reviewed bulk writes. Coaching Emphasis includes Help Defense, Run Plays Frequency, Zone Usage Frequency, Tempo, tendencies, and Lineup Form Factor. Staff shows seven coach ratings and eight system proficiencies alongside the assigned staff names. Coaching edits share journaling, readback verification, rollback, and Undo/Redo with player edits. Shared or uncertain coach records stay read-only. Rotation minutes and Staff assignments/names remain read-only; playbook editing is not enabled. See [coaching mapping and write support](docs/team-mapping-notes.md#coaching-write-support) and the [November mapping audit](docs/unattended-mapping-2026-11-01.md).
- Review before/after changes, revert a record, discard unsaved changes, or save with Ctrl+S.
- Import a JSON roster after a summary preview, and export the current workspace, including unsaved changes.

Section assignments were cross-checked against the [MyNBA tendency list](https://www.reddit.com/r/NBA2k/comments/1s1xwio/weird_request_for_mynba_tendencies/) and [NBA2KLab's 2K27 badge categories](https://www.nba2klab.com/fuse-react-badges). These references supply display grouping only, not memory-address or write validation.

For a hands-on feature check, follow the [manual walkthrough](docs/manual-walkthrough.md).

The editor supports local JSON workspaces and direct Windows process access for game roster reads, live edits, and reviewed bulk writes. The initial roster uses fictional demo players and teams. Saved workspaces reload from `data/roster.json` by default. The OVR column shows the game's overall rating when a supported, valid read is available; it does not average attributes. Supported live roster reads include primary/secondary positions and team names with validated roster membership. Unknown team assignments are kept separate from free agents.

## TRC export → game workflow

### Direct website sync

With your intended custom roster open in NBA 2K27, connect and **Load game roster**, then select **Sync from TRC**. Trace sends the names in that loaded roster to `https://russellcup.xyz/logs/roster/download/` in one read-only lookup and fetches only matching website players, including players with no pending upgrades. It merges unique matching names into the loaded workspace and opens a game-change preview limited to the seven sections in the existing TRC export: attributes, badges, tendencies, hot zones, signatures, gear, and accessories. Review skipped players and unsupported fields before **Apply to game**. That button authorizes only the reviewed batch; **Start live editing** is for automatic individual edits. Save the roster inside NBA 2K27 afterward.

NBA 2K27 uses [Easy Anti-Cheat](https://support.nba2k.com/hc/en-us/articles/42216723600659-NBA-2K-Anti-Cheat-on-PC). Keep Cheat Engine and debugger tools closed while the game is running; the game exited after Cheat Engine was launched during a mapping investigation. Trace does not require Cheat Engine. If the game reports a security violation during process access, stop live game operations and continue with offline JSON review instead.

TRC's six NBA 2K25 badge names that are absent in 2K27 convert to the selected 2K27 counterparts during import or sync. A zero old tier leaves the new badge untouched, and a positive old tier does not lower a higher existing 2K27 tier. The other new 2K27 badges retain their game values. See the [2K25-to-2K27 field review](docs/2k25-to-2k27-field-review.md) for the exact mapping and possible future choices.

Anyone with Trace can use the read-only player-value endpoint without a token or website login. The endpoint requires requested player names and returns only matching players' seven game-value sections, names, and website player IDs; it does not include account details. Fetching does not mark upgrades completed. Game record IDs and team assignments are retained. Duplicate or missing names are reported and skipped; players must already exist in the loaded roster. Sync stages changes in the workspace and pauses individual live editing; it never automatically applies the batch. Existing local workspace edits are included in the preview. Manual **Import JSON** remains available if the website is unreachable.

NBA 2K27 may keep thousands of NBA and custom players in the same game table. After loading, select **Only show TRC players** to look up matching website names and filter the list without changing any values; select **All players** to return to the full game table. **Sync from TRC** also switches to this filtered view after staging its preview.

### Manual export

1. Start NBA 2K27 normally and load the roster you want to edit. Cheat Engine, a relay, and external memory tools are not required.
2. Double-click `TRACE.cmd` and select **Connection details**. The game folder defaults to `D:\Program Files (x86)\Steam\steamapps\common\NBA 2K27`. Change the folder or executable path there and save if needed. Settings persist in `config/game_connection.json`; `--game-path` and `--settings` are also available.
3. Select **Check game connection**, then **Load game roster**. The editor verifies the running executable at the configured path and reads its player array directly. Loading stages the roster in the workspace; it does not save a JSON file.
4. Select **Import JSON** with your TRC export and leave **Merge matching players** checked. The converter supports name-keyed exports. Target record IDs and team assignments are retained; unmatched or ambiguous names are skipped and reported. Current and historical versions of a player can share a name, so ambiguous matches require an explicit record selection rather than guessing. You can also import directly for local editing without connecting.
5. For individual edits, click **Start live editing** once. This authorizes writes for the loaded game session and checks Windows write access. Change a supported field: it writes after a 450 ms pause, pressing Enter, or leaving the field. No preview/apply step is needed. Supported fields include numeric values, learned animation names, and first/last names under Vitals. Fields without a supported memory mapping and blank values remain local only. On an error, live editing pauses and reports the failure.
6. **Undo game edit** restores the last live edit or bulk update; **Redo** reapplies it. This history belongs to the loaded game session and resets when you reload the roster, change connection settings, or restart the editor. Stopping live editing stops automatic writes; existing edits remain and can still be undone. Local record reverts/discard are disabled while live editing is active; use game Undo instead.
7. For imported batches, use **Review game writes → Apply to game**. Applying the reviewed batch does not start live editing. Names with multiple player versions are still reported rather than automatically matched.
8. **Save JSON workspace** saves a local roster copy, and **Export JSON** creates a named download of your working roster. Save the roster **inside NBA 2K27** to persist game memory edits. Writing a JSON file does not invoke the game's Save action. The game may cache a screen's values; leave and reopen its player edit screen if needed to see a verified memory change.

The editor uses Windows `OpenProcess`, `ReadProcessMemory`, and `WriteProcessMemory` through Python's standard library. It checks the executable's full path, module base, PE headers, PID, process creation time, and current player-array pointer. Read operations request read access; write access is requested only when applying an enabled, matching-build plan. Windows access failures are reported directly. The editor does not install drivers or modify game protections. If the game is running elevated, the editor may need matching privileges.

Plans expire after five minutes. Every affected player identity and edited field is compared before the first write. Unrelated game caches do not invalidate the update. Only changed byte ranges are written and verified; a failure attempts rollback on the same process and array. Recovery bytes and outcomes are flushed to `data/game_updates.jsonl` (or beside a custom `--data` file). In-game activity can invalidate a preview; keep the roster idle during an update. Loading stops at the first empty last name, with a 6,000-record cap. Settings changes invalidate loaded memory snapshots and require reloading. The bundled Cheat Engine artifacts remain development references and are not needed to run the editor.

### JSON format

See `config/roster.example.json` for an importable example. Documents contain `players` and `teams` arrays. IDs are stable, unique strings (`player_id` or `team_id`), and every record needs a name. A player's `team_id` references an included team; omit it or use null for free agents. Import replaces the entire working roster; it does not merge individual players. The saved file changes only when you select **Save workspace**.

Player category objects use field names from the offset profile (for example `attributes["Driving Layup"]`); advanced fields use their profile IDs. Custom fields are preserved. Attribute values accept integers 0–99, tendencies 0–100, and badge levels 0–5. Game attributes use the narrower 25–99 range and encode as `(rating - 25) * 3`. Packed tendencies and badges preserve neighboring bits. Metadata can hold arbitrary JSON values. Blank numeric fields remove the value from the document. Export provides a backup before importing another roster.

Run checks with `python -m pytest -q`.

Starter workspace for an app that reads player data from the TRC website and synchronizes supported values into a running NBA 2K27 process through build-specific memory addresses.

## Current scope

- Define a stable internal player-data model.
- Keep website retrieval separate from game-process access.
- Store memory addresses by NBA 2K27 build instead of hardcoding unknown values.
- Validate data and address mappings before any write is attempted.

The project also includes the currently confirmed NBA 2K27 Cheat Engine artifacts:

- `config/offsets_2k27.json` — player-record layout, attributes, tendencies, badges, vitals, signatures, and 525 additional non-duplicate advanced field definitions.
- `config/2k27_helpers.lua` — Cheat Engine helper functions for locating players and reading/writing supported ratings.

These artifacts are build- and runtime-specific. Verify the exact NBA 2K27 executable and process state before writing values.

## Layout

```text
TRACE/
├── config/
│   ├── 2k27_helpers.lua
│   ├── memory_addresses.example.json
│   └── offsets_2k27.json
├── docs/
│   └── architecture.md
├── src/
│   └── trace_app/
│       ├── __init__.py
│       ├── models.py
│       └── sync.py
└── tests/
    └── test_models.py
```

## Field mappings and named values

The editor expands the existing offset profile into 406 writable field definitions, including 78 signatures, 19 gear fields, 82 accessory fields, 21 vitals (including weight and first/last names), and 2 appearance fields. This adds 191 mappings to the earlier editor. Raw Advanced definitions remain read only: the supported entries are exposed in their appropriate categories. Fourteen duplicate advanced IDs, caches, internal IDs, and unmapped badge names are not silently enabled.

`config/field_values.json` stores observed display-name → numeric-ID pairs separately for each executable build and field. The initial catalog contains 29 observations from the supplied Tyrese Maxey signature screenshots, paired with native memory reads. It does not assume, for example, that a player's name has the same ID for a jumpshot, release, and dribble style.

Mapped signature, gear, and accessory fields accept either a numeric game ID or an observed name. Learned names appear as input suggestions. Unknown named values are rejected during live editing and reported during bulk preview. To expand the catalog, select the exact game player, open the corresponding field in 2K, click **Learn name** in TRACE, and enter the name currently shown in 2K. The editor reads the ID without writing to the game. Conflicting observations cannot overwrite an existing name mapping. Game numeric IDs are still available when no display name has been learned.

Build `6AD2E48C:36532000` includes 559 Home Shoe names obtained from two agreeing loaded shoe catalogs, checked against Air Jordan III, Air Jordan 2010, and Air Jordan XXXIII selections. Duplicate-name conflicts and entries whose two catalog IDs differ are excluded. These names apply to Home Shoe on that build; they do not automatically populate other fields or game builds.

Weight is stored as a 32-bit float in game units. First/last names use conservative 20-code-unit UTF-16 buffers (19 units plus terminator); Undo restores their exact original buffer bytes. Full display names in Overview remain local; edit First Name and Last Name under Vitals to update game names.

All 14 hot zones are mapped for build `6AD2E48C:36532000`, with Cold, Neutral, and Hot choices confirmed through controlled in-game changes. Unmapped-field investigation is handled through read-only development tools; the capture button is no longer shown in the editor.

### Additional verified choices and references

The [unattended mapping pass](docs/read-only-mapping-pass.md) adds College / From
editing through a validated, session-bound catalog (652 unique choices in the
observed roster), numeric Away Shoe style, and six further frequency/color
controls. College labels are stored in JSON; its runtime addresses are never
used as portable field values. Existing journals, verification, rollback and
Undo/Redo apply. The complete college catalog is not assumed: only the validated
span between independently loaded references is offered.

Native enum tables now supply names for accessory frequencies, Skin Type,
Headband Logo Position, and all 16 play types, preserving previously observed
labels. Both injury readouts recognize all 157 native injury types. Changing
or clearing injury types still requires the game; duration editing keeps its
existing active-injury restrictions. Away Shoe names and colorways are not
inferred from Home Shoe.
