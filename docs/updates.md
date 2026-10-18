# Publishing and installing TRC+ updates

The public repository is https://github.com/RCZach/TRC-Plus. The app's **Check
for updates** button looks at its latest stable GitHub Release. Checking never
installs anything. Users read the release notes and choose **Update and
restart**. The app requires saved workspace changes and no pending game edits
before downloading or installing. Internet failures leave the current app usable.

Downloads must match the release's SHA-256 digest (or the generated checksum
sidecar). The ZIP is checked for unsafe paths and missing application files.
Only public releases with version tags such as `v0.3.0` and a matching
`TRC+-0.3.0-windows-x64.zip` asset are supported. Drafts, prereleases, older
versions, and GitHub's source-code ZIPs are not installed.

The separate bundled updater waits for the running app to exit, copies the
validated release to a sibling folder, preserves the old installation as
`TRC+-previous-<unique id>`, and restarts the app at the original path. It restores
the old app if replacement or starting the executable fails. Each user's
workspace, settings, logs, and learned mappings remain in `%LOCALAPPDATA%\TRC+`.
Update diagnostics are kept under its `updates` subfolder. The portable app must
be in a folder the user can update; no elevation is requested automatically.
Close any additional copies of TRC+ before installing an update.

## Publish the next release

1. Make the changes and update `pyproject.toml` and `src/trc_plus/version.py` to
   the same version. The UI reads the exact version from the running server.
2. Commit the changes and push to the repository.
3. Create and push the corresponding tag, for example `v0.4.0`.
4. The **Publish Windows release** GitHub Actions workflow runs the tests, builds
   the desktop app and updater, verifies the ZIP, and publishes the release with
   the ZIP, checksum, and generated release notes. Users can then install it.

For a manual release, run `python packaging/build_windows.py`,
`python packaging/verify_windows.py`, and `python packaging/verify_update_windows.py`.
Publish the versioned ZIP and its `.zip.sha256` file from `dist/` as GitHub
Release assets. Publishing a release makes it available; pushing code without
publishing a release does not change installed apps.

Versions before 0.3.0 do not contain the updater. Users install 0.3.0 once by
extracting its ZIP, then future versions can be installed using the app button.
