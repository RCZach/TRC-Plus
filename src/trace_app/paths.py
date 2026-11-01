"""Keep bundled resources separate from each user's writable files."""

import os
import shutil
import sys
import tempfile
from pathlib import Path


def resource_root():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def user_root():
    if getattr(sys, 'frozen', False):
        local = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        destination = local / 'Trace'
        legacy_sources = (local / 'TRC+', local / 'TRC Roster Studio')
        legacy = next((path for path in legacy_sources if path.is_dir()), None)
        if not destination.exists() and legacy is not None:
            # Copy legacy user state so the original and any interrupted migration remain safe.
            with tempfile.TemporaryDirectory(prefix='trace-migration-', dir=local) as temporary:
                staged = Path(temporary) / 'workspace'
                shutil.copytree(legacy, staged)
                try:
                    staged.rename(destination)
                except FileExistsError:
                    pass  # Another launch finished migrating first.
        return destination
    return resource_root()


def default_values_path():
    destination = user_root() / 'config' / 'field_values.json'
    bundled = resource_root() / 'config' / 'field_values.json'
    if destination != bundled and not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        contents = bundled.read_bytes()
        try:
            with destination.open('xb') as output:
                output.write(contents)
        except FileExistsError:
            pass
    return destination
