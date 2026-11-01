from pathlib import Path
import sys

from trace_app import paths


def test_frozen_resources_and_user_files_are_separate(tmp_path, monkeypatch):
    bundle = tmp_path / 'bundle'
    local = tmp_path / 'user'
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(bundle), raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(local))
    assert paths.resource_root() == bundle
    assert paths.user_root() == local / 'Trace'
    (bundle / 'config').mkdir(parents=True)
    (bundle / 'config' / 'field_values.json').write_text('{"version": 1, "builds": {}}')
    catalog = paths.default_values_path()
    assert catalog == paths.user_root() / 'config' / 'field_values.json'
    assert catalog.read_bytes() == (bundle / 'config' / 'field_values.json').read_bytes()
    catalog.write_text('{"version": 1, "builds": {"CUSTOM": {}}}')
    (bundle / 'config' / 'field_values.json').write_text('new release catalog')
    assert paths.default_values_path().read_text() == '{"version": 1, "builds": {"CUSTOM": {}}}'


def test_source_defaults_use_project_not_working_directory(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.chdir(tmp_path)
    root = Path(paths.__file__).resolve().parents[2]
    assert paths.resource_root() == paths.user_root() == root
    assert paths.default_values_path() == root / 'config' / 'field_values.json'


def test_frozen_upgrade_preserves_legacy_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    legacy = tmp_path / 'TRC Roster Studio'
    files = {
        'data/roster.json': '{"name": "My roster"}',
        'data/game_updates.jsonl': '{"result": "saved"}\n',
        'config/game_connection.json': '{"enable_writes": false}',
        'config/field_values.json': '{"builds": {"CUSTOM": {}}}',
    }
    for name, contents in files.items():
        path = legacy / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')

    destination = paths.user_root()
    assert destination == tmp_path / 'Trace'
    for name, contents in files.items():
        assert (destination / name).read_text(encoding='utf-8') == contents
        assert (legacy / name).read_text(encoding='utf-8') == contents

    (destination / 'data/roster.json').write_text('New workspace', encoding='utf-8')
    assert paths.user_root() == destination
    assert (destination / 'data/roster.json').read_text(encoding='utf-8') == 'New workspace'
    assert not list(tmp_path.glob('trace-migration-*'))


def test_failed_migration_can_be_retried(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    legacy = tmp_path / 'TRC Roster Studio'
    legacy.mkdir()
    (legacy / 'roster.json').write_text('Saved roster', encoding='utf-8')
    copytree = paths.shutil.copytree
    with monkeypatch.context() as patch:
        def interrupted_copy(source, destination):
            destination.mkdir()
            raise OSError('Interrupted copy')
        patch.setattr(paths.shutil, 'copytree', interrupted_copy)
        with pytest.raises(OSError, match='Interrupted copy'):
            paths.user_root()
    assert not (tmp_path / 'Trace').exists()
    assert not list(tmp_path.glob('trace-migration-*'))
    assert paths.shutil.copytree is copytree
    assert (paths.user_root() / 'roster.json').read_text(encoding='utf-8') == 'Saved roster'
