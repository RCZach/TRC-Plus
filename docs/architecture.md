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

`trc.py` converts name-keyed TRC exports and merges unique normalized names without changing target IDs or team assignments. Extra sections survive under metadata. `fields.py` decodes player records from the active profile and handles rating conversion and packed-bit updates. `game.py` uses `windows_memory.py` to connect directly through Win32 process APIs. `settings.py` persists the configured executable location and write settings. The UI edits these settings through a session-protected endpoint; settings changes invalidate snapshots. It validates the full executable path, on-disk and in-memory PE fingerprint, process creation time, and module base. The profile's base pointer and offset chain are resolved at runtime.

Reads keep server-owned snapshots keyed by current record index. Preview creates an expiring, single-use plan; Apply accepts only its token. Writes require an explicitly enabled, matching build fingerprint, a stable process/base, and unchanged player identities/edited fields. They update only changed bytes, verify each byte, attempt rollback on failure, and save recovery snapshots to an audit log before writing. Process exit, pointer movement, stale bytes, or failed writes invalidate the affected plan; rollback uses the pinned process handle and refuses to operate on a moved array. Windows memory operations cannot make writes atomic with concurrent game activity, so the game should remain idle during updates. Loading stops at the first empty last name, matching the existing helper's enumeration rule, with a 6,000-record cap.

Raw Advanced definitions include overlapping fields and caches and remain read only. `mappings.py` promotes existing unique signature, gear, accessory, appearance, and selected vital definitions into writable categories. The 14 ambiguous advanced IDs are excluded. `ValueCatalog` persists display names by exact executable build/category/field; learning reads a loaded player’s current numeric value and does not write memory. Teams, unknown badge aliases, and hotzone offsets require further verification. `build_dry_run_plan` remains available to the older attributes-only synchronization pipeline.

The app is organized around four boundaries:

1. **TRC adapter** — retrieves or imports player data and converts it into the internal model.
2. **Normalizer/validator** — normalizes names, IDs, ratings, and attribute ranges before sync.
3. **Address profile** — selects a verified NBA 2K27 memory map for the exact build and platform.
4. **Sync engine** — compares source and target values, produces a dry-run plan, and only then performs approved writes.

## Safety and correctness requirements

- Never infer an address from a different NBA 2K27 build.
- Validate the target process identity before reading or writing.
- Prefer stable player IDs over name matching.
- Keep writes disabled by default.
- Log each planned and completed field update.
- Fail closed when the build, address profile, or player mapping is unknown.

Live editing is a session-scoped opt-in endpoint. Starting it probes write access and binds authorization to the loaded process/build. Single-field requests use the same transaction writer as bulk Apply. The writer reads fresh record bytes, validates requested old values, preserves unrelated fields/bits, journals and verifies changed ranges, and attempts rollback on failure. Successful transactions feed undo/redo stacks. Undo validates that each affected field still holds the value written by the transaction. Requests are serialized by the local server; the UI also serializes edits and pauses its queue after an error. Imports do not implicitly write fields.

The mapped schema is returned to the UI with explicit writable/kind/bits metadata; frontend live capability follows that schema. Weight uses float32 with decoded readback values. UTF-16 name transactions retain original field buffers so Undo can restore padding exactly. TRC field-name aliases are canonicalized without guessing enum IDs, and conflicting aliases are rejected. Before/after calibration captures are read only and stored with process identity, record bytes, and changed-bit evidence; no inferred offset is automatically enabled.
