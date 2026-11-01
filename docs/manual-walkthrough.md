# TRACE manual walkthrough

Use this guide to walk through the app by hand and note anything that behaves
unexpectedly. It is a practical feature check, not an automated test suite.

## Before you start

1. Launch TRACE with `TRACE.cmd` or the packaged `TRACE.exe`.
2. If you plan to change a roster you care about, use **Export JSON** first and
   save a backup copy somewhere you can find it.
3. Start with the demo or a spare JSON roster. The first section does not need
   NBA 2K27. The game section is optional and clearly separates reading from
   writing.

## Roster workspace

1. **Open the player workspace.** Check that the player list and selected
   player's fields appear. Select **Teams** and **Change review**, then return
   to **Players**. The list counts and selected navigation state should update.
2. **Find a player.** Search by name, then by player ID. Clear the search and
   filter by a team. Confirm the list narrows and returns when the filters are
   cleared.
3. **Edit a player value.** Choose a numeric attribute, note its original
   value, and change it by one point. The new value should remain in the field,
   the edit should be highlighted, and the unsaved-change count should update.
4. **Revert one player.** Select **Revert player changes**. The selected
   player's unsaved values should return to their last saved values. This does
   not reset the player to game defaults.
5. **Review and discard edits.** Change two fields, then select **Review
   changes**. Confirm that each row shows the player, field, previous value,
   and new value. Select **Discard local edits** and confirm the workspace
   returns to its saved state.
6. **Save a workspace edit.** Change one value, review it, then select **Save
   JSON workspace** (or press Ctrl+S). The unsaved-change indicator should
   clear. Restart TRACE and confirm the saved value remains.
7. **Edit a team.** Select **Teams**, choose a team, and change its name or
   editable metadata. Confirm the change appears in review. Revert the team or
   discard the edit if you do not want to keep it.
8. **Export a roster.** Select **Export JSON** and choose a file location.
   Confirm that the downloaded file contains the current workspace, including
   any unsaved changes. Keep the backup from the beginning separate from this
   working export.
9. **Import a roster.** Select **Import JSON** and choose a known roster file,
   such as `config/roster.example.json` or a copy of your export. Review the
   import summary and warnings before confirming. Confirm that the roster
   loads, then export it again if you want to keep the result. Cancel once to
   confirm that closing the import preview leaves the current workspace alone.

## NBA 2K27 connection and reads

These steps read the running game roster but do not write to it.

1. Start NBA 2K27 and load the custom roster you intend to inspect.
2. In TRACE, open **Connection details**. Check the game folder or executable
   path; update it if needed and save the settings.
3. Select **Check game connection**. TRACE should report whether the expected
   NBA 2K27 process is available; the sidebar should say **Connected to NBA 2K27**.
   If it cannot connect, read the displayed
   error and verify the selected executable path before continuing.
4. Select **Load game roster**. Confirm that the players and teams populate in
   TRACE. Loading stages a working copy; it does not save changes inside the
   game.
5. Inspect a few players and fields, then select **Teams**. Confirm that the
   loaded game data is visible and that unsupported or blank fields remain
   empty rather than being treated as zero.

## Optional live-edit check

Only do this when you are ready to make and undo one small change in the
loaded game session. Use a roster you can safely restore.

1. Select **Start live editing**. Confirm that the live-edit status changes
   from off and the game write access is available.
2. On one player, change a supported numeric attribute by one point. Wait a
   moment or press Enter. Check that the game value updates.
3. Select **Undo game edit** and confirm the original value returns. Select
   **Redo**, confirm the changed value returns, then select **Undo game edit**
   once more to leave the game value at its original value.
4. Stop live editing. Confirm the button reads Start live editing. Existing game
   edits remain in place until undone; stopping live editing does not undo
   them.

## Bulk preview and sync

1. With a game roster loaded, import a small JSON roster or use **Sync from
   TRC** if you have a current TRC export available.
2. Review the import/sync summary and any skipped or unsupported fields.
   Confirm that changes appear in the workspace and that the game has not
   changed just from importing or syncing.
3. Select **Review game writes**. Review the before/after list and warnings.
   Cancel the preview to confirm that previewing alone does not apply changes.
4. If you want to verify a real bulk write, use a spare roster and a single
   change you can identify and reverse. Select **Apply to game** only after
   checking the full preview. Confirm the value in NBA 2K27, then use **Undo
   game edit** to restore it.
5. If you have a supported named field, try **Learn name**. Enter the name
   currently shown for that exact player and field in NBA 2K27. Confirm that
   TRACE reads and stores the value for the current build without changing the
   game.


## Finish

1. Undo any test game changes you want to discard. Save inside NBA 2K27 only
   if you intend to keep the game roster changes.
2. Save or discard TRACE workspace changes. Export a final JSON copy if you
   want a separate backup.
3. Close TRACE. In the desktop app, confirm that the unsaved-changes prompt
   appears when there are workspace edits to save or discard.

## Optional packaged-app check

For a portable release, also launch `TRACE.exe` from the extracted release
folder, verify the WebView window opens, use **Check for updates**, and close
the window. The update check should report either an available version or that
TRACE is up to date; checking by itself should not install an update.
