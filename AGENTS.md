# Trace project guidance

## Purpose

Trace is a local Windows desktop roster editor and synchronization tool for
NBA 2K27. It imports and merges player data from TRC exports, lets users edit
and review roster changes, and can read or write supported values in a running
game process. It is not a hosted web service. The local server and UI run on
the user's computer; user workspaces, settings, learned names, and recovery
logs are stored in that user's local application data folder in packaged
releases.

## Read before changing behavior

- `README.md` describes installation, workflows, supported features, and the
  roster JSON format.
- `docs/architecture.md` describes the UI/API boundaries, process access,
  transaction and recovery behavior, and mapping limitations.
- `docs/updates.md` describes packaging, release publication, and in-app
  updates.
- `docs/releases/` contains version-specific release notes.

## Architecture

- `src/trace_app/app.py` hosts the loopback-only server and application entry
  points; the static UI is in `src/trace_app/ui/`.
- Roster validation and persistence, TRC conversion, field mapping, game
  process access, and settings are separated into their respective modules in
  `src/trace_app/`.
- `config/offsets_2k27.json` contains build-specific game field definitions.
  Treat each executable build and mapping as distinct; do not transfer an
  address or assume a field is writable based on a different build.
- `packaging/` builds and verifies the portable Windows app and updater.
  `.github/workflows/release.yml` publishes a release when a version tag is
  pushed.

## Safety and correctness

- Keep the app local and loopback-bound. Do not expose its server or APIs to
  the network.
- Game writes must remain opt-in, build- and process-validated, reviewed, and
  fail closed when identity, mappings, or field values are uncertain.
- Never guess memory addresses, enum IDs, player identity matches, or game
  behavior. Keep unverified fields read-only until evidence supports a mapping.
- Preserve unrelated bytes and packed bits when changing a field. Keep
  validation, journaling, readback verification, rollback, and undo/redo
  guarantees intact when modifying write paths.
- Imports and previews must not write to the game implicitly. A JSON save is
  separate from saving roster changes inside NBA 2K27.
- NBA 2K27 uses Easy Anti-Cheat. The user observed the game exit after an agent
  launched Cheat Engine while the game was open, even though no process was
  attached. Do not launch Cheat Engine, debuggers, memory scanners, or other
  instrumentation alongside a running game for Trace research. Use offline
  data, existing exports, and user-provided game screenshots for mapping
  investigations. Do not disable or work around anti-cheat protections.
- Do not commit personal rosters, connection settings, recovery logs, or
  machine-specific data. Follow `.gitignore` and packaging exclusions.

## Packaging and releases

Keep the versions in `pyproject.toml` and `src/trace_app/version.py` aligned.
The release workflow expects a `v<version>` tag and builds and verifies the
Windows package and updater before publishing. See `docs/updates.md` for the
full release procedure and manual commands.
