# TRC+

[Download the Windows app](https://github.com/RCZach/TRC-Plus/releases/latest).
Version 0.3.0 adds **Check for updates** and optional **Update and restart**
inside the desktop app. See [publishing updates](docs/updates.md) for the release
process. Older versions need this ZIP installed once to gain the update button.

## TRC+ UI

### Portable Windows release

Extract the entire `TRC+-0.3.0-windows-x64.zip`, then double-click
`TRC+.exe`. It opens its own desktop window. Keep its `_internal` folder beside
the executable. Closing the app window also stops its local backend.
Python and Cheat Engine are not
required. See `START HERE.txt` in the release for the game connection workflow.
The window uses Microsoft Edge WebView2 Runtime and .NET Framework 4.6.2 or
newer, normally available on current Windows 10/11 computers. If WebView2 is
missing, install it from https://developer.microsoft.com/microsoft-edge/webview2/.
Startup errors are recorded in `%LOCALAPPDATA%\TRC+\desktop.log`.

Packaged releases keep each Windows user's settings, workspace, learned names,
and recovery logs in `%LOCALAPPDATA%\TRC+`. Updates can be extracted
into a new folder without replacing those files. Personal rosters, connection
settings, recovery logs, and development tools are excluded from the release.
On first launch, TRC+ copies saved files from the previous TRC Roster Studio
data folder if the TRC+ folder does not exist yet. The original files are kept.

To build on 64-bit Windows with Python 3.11+, install
`python -m pip install -r packaging/requirements-build.txt`, then run
`python packaging/build_windows.py`. The executable folder, versioned ZIP, and
SHA-256 checksum are written to `dist/`.
Run `python packaging/verify_windows.py` to check the extracted release with an
isolated user directory and Python removed from its executable search path.

### Running from source

Double-click `TRC+.cmd` on Windows (Python 3.11+ required). The editor opens at `http://127.0.0.1:8765` and runs only on your computer. Leave its terminal open while using the editor; press Ctrl+C there to stop it.

Alternatively, install with `python -m pip install -e .`, then run `trc-plus` or `python -m trc_plus.app`. Options: `--port 8765`, `--data path/to/roster.json`, `--profile config/offsets_2k27.json`, `--no-browser`.
For the desktop window from source, install `python -m pip install -e ".[desktop]"`
and run `trc-plus --desktop`. Packaged releases default to the desktop window;
`--browser` is available as an explicit fallback, and `--no-browser` runs only
the local server for diagnostics.

If the requested port is occupied, the launcher opens this editor on a separate available port and prints its URL. Use the newly opened page. After updating the code, restart the editor's terminal process; refreshing the browser alone cannot update the running backend.

- Browse players and teams; search names/IDs and filter players by team.
- Edit player attributes, tendencies, badges, vitals, signatures, advanced values, metadata, names, and team assignments.
- Browse the bundled player field definitions; blank fields are unset, not zero.
- Edit team names and imported metadata. Team memory field definitions are not available yet.
- Review before/after changes, revert a record, discard unsaved changes, or save with Ctrl+S.
- Import a JSON roster after a summary preview, and export the current workspace, including unsaved changes.

The editor supports local JSON workspaces and direct Windows process access for game roster reads, live edits, and reviewed bulk writes. The initial roster uses fictional demo players and teams. Saved workspaces reload from `data/roster.json` by default. The AVG column is the arithmetic mean of known attributes, not NBA 2K's overall rating.

## TRC export → game workflow

### Direct website sync

With your intended custom roster open in NBA 2K27, connect and **Load game roster**, then select **Sync from TRC**. This fetches the current pending-upgrade export from `https://russellcup.xyz/logs/upgrades/download/`, merges unique matching names into the loaded workspace, and opens the game-change preview. Review skipped players and unsupported fields before **Apply to game**. If writes are disabled, select **Start live editing** once and preview again. Save the roster inside NBA 2K27 afterward.

The website currently serves this export without a login. No website changes or credentials are needed. Fetching is read only and does not mark upgrades completed. An empty export means no pending upgrades. It contains players with incomplete upgrade logs, rather than every league player. Game record IDs and team assignments are retained. Duplicate or missing names are reported and skipped; players must already exist in the loaded roster. Sync stages changes in the workspace and pauses individual live editing; it never automatically applies the batch. Existing local workspace edits are included in the preview. Manual **Import JSON** remains available if the website is unreachable.

### Manual export

1. Start NBA 2K27 normally and load the roster you want to edit. Cheat Engine, a relay, and external memory tools are not required.
2. Double-click `TRC+.cmd` and select **Connection details**. The game folder defaults to `D:\Program Files (x86)\Steam\steamapps\common\NBA 2K27`. Change the folder or executable path there and save if needed. Settings persist in `config/game_connection.json`; `--game-path` and `--settings` are also available.
3. Select **Check game connection**, then **Load game roster**. The editor locates the running executable at the configured path and reads its player array directly. Loading stages the roster in the workspace; it does not save the local file. The connection shows the executable fingerprint (`PE timestamp:SizeOfImage`, hexadecimal).
4. Select **Import JSON** with your TRC export and leave **Merge matching players** checked. The converter supports name-keyed exports. Target record IDs and team assignments are retained; unmatched or ambiguous names are skipped and reported. Current and historical versions of a player can share a name, so ambiguous matches require an explicit record selection rather than guessing. You can also import directly for local editing without connecting.
5. For individual edits, click **Start live editing** once. This authorizes writes for the loaded game session and checks Windows write access. Change a supported field: it writes after a 450 ms pause, pressing Enter, or leaving the field. No preview/apply step is needed. Supported fields include numeric values, learned animation names, and first/last names under Vitals. Fields without a supported memory mapping and blank values remain local only. On an error, live editing pauses and reports the failure.
6. **Undo game edit** restores the last live edit or bulk update; **Redo** reapplies it. This history belongs to the loaded game session and resets when you reload the roster, change connection settings, or restart the editor. Stopping live editing stops automatic writes; existing edits remain and can still be undone. Local record reverts/discard are disabled while live editing is active; use game Undo instead.
7. For imported batches, use **Preview bulk changes → Apply to game**. Starting live editing also enables this write path without manually entering a build fingerprint. The Connection details write settings remain available for explicitly configuring bulk writes. Names with multiple player versions are still reported rather than automatically matched.
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
TRC+/
├── config/
│   ├── 2k27_helpers.lua
│   ├── memory_addresses.example.json
│   └── offsets_2k27.json
├── docs/
│   └── architecture.md
├── src/
│   └── trc_plus/
│       ├── __init__.py
│       ├── models.py
│       └── sync.py
└── tests/
    └── test_models.py
```

## Field mappings and named values

The editor expands the existing offset profile into 406 writable field definitions, including 78 signatures, 19 gear fields, 82 accessory fields, 21 vitals (including weight and first/last names), and 2 appearance fields. This adds 191 mappings to the earlier editor. Raw Advanced definitions remain read only: the supported entries are exposed in their appropriate categories. Fourteen duplicate advanced IDs, caches, internal IDs, and unmapped badge names are not silently enabled.

`config/field_values.json` stores observed display-name → numeric-ID pairs separately for each executable build and field. The initial catalog contains 29 observations from the supplied Tyrese Maxey signature screenshots, paired with native memory reads. It does not assume, for example, that a player's name has the same ID for a jumpshot, release, and dribble style.

Mapped signature, gear, and accessory fields accept either a numeric game ID or an observed name. Learned names appear as input suggestions. Unknown named values are rejected during live editing and reported during bulk preview. To expand the catalog, select the exact game player, open the corresponding field in 2K, click **Learn name** in TRC+, and enter the name currently shown in 2K. The editor reads the ID without writing to the game. Conflicting observations cannot overwrite an existing name mapping. Game numeric IDs are still available when no display name has been learned.

Weight is stored as a 32-bit float in game units. First/last names use conservative 20-code-unit UTF-16 buffers (19 units plus terminator); Undo restores their exact original buffer bytes. Full display names in Overview remain local; edit First Name and Last Name under Vitals to update game names.

Hotzone offsets and some named values such as Dunk Emotion remain unverified. Use **Capture unmapped field** to select a player and record a before snapshot, make exactly one change in 2K, commit it there, and compare. Captures are saved under `data/mapping_captures` and can be exported. Reports include changed bytes/bits and overlapping known fields; suspected hash/cache locations are marked. These are observations, not automatically enabled mappings. Verify candidates with repeated independent changes before adding a definition.
