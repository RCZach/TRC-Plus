import hashlib
import io
import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

import pytest

from trace_app import updates
from trace_app.app import create_server
from trace_app.update_installer import replace_application


def release(version='0.5.3', **overrides):
    name = f'TRACE-{version}-windows-x64.zip'
    return {'tag_name': 'v' + version, 'body': 'New features', 'assets': [
        {'name': name, 'size': 1, 'digest': 'sha256:' + 'a' * 64,
         'browser_download_url': f'https://github.com/{updates.REPOSITORY}/releases/download/v{version}/{name}'}], **overrides}


@pytest.mark.parametrize('version,newer', [('0.2.0', False), ('0.4.1', False), ('0.5.0', False), ('0.5.1', False), ('0.5.2', False), ('0.5.3', True), ('0.10.0', True), ('1.0.0', True)])
def test_version_check_is_numeric_and_never_downgrades(monkeypatch, version, newer):
    monkeypatch.setattr(updates, 'read_url', lambda *args: json.dumps(release(version)).encode())
    manager = updates.UpdateManager()
    assert manager.check()['available'] is newer
    assert bool(manager.release) is newer


def test_missing_release_is_reported_without_error(monkeypatch):
    def missing(*args):
        raise HTTPError('url', 404, 'Not found', {}, None)
    monkeypatch.setattr(updates, 'read_url', missing)
    assert updates.UpdateManager().check()['available'] is False


@pytest.mark.parametrize('change', ['draft', 'prerelease', 'bad-url', 'missing-checksum'])
def test_unusable_releases_are_not_installable(monkeypatch, change):
    document = release()
    if change in ('draft', 'prerelease'):
        document[change] = True
    elif change == 'bad-url':
        document['assets'][0]['browser_download_url'] = 'https://example.com/app.zip'
    else:
        document['assets'][0].pop('digest')
    monkeypatch.setattr(updates, 'read_url', lambda *args: json.dumps(document).encode())
    manager = updates.UpdateManager()
    with pytest.raises(ValueError):
        manager.check()
    assert manager.release is None


def test_checksum_sidecar_fallback(monkeypatch):
    document = release()
    asset = document['assets'][0]
    asset.pop('digest')
    document['assets'].append({'name': asset['name'] + '.sha256',
                               'browser_download_url': asset['browser_download_url'] + '.sha256'})
    monkeypatch.setattr(updates, 'read_url', lambda url, limit: (
        ('b' * 64 + '  ' + asset['name']).encode() if url.endswith('.sha256') else json.dumps(document).encode()))
    manager = updates.UpdateManager()
    assert manager.check()['available']
    assert manager.release['sha256'] == 'b' * 64


def zip_content(extra=None):
    output = io.BytesIO()
    with ZipFile(output, 'w') as archive:
        for name in ['TRACE/TRACE.exe', 'TRACE/TRACE Updater.exe', 'TRACE/_internal/python311.dll']:
            archive.writestr(name, b'test')
        if extra:
            archive.writestr(extra, b'unsafe')
    return output.getvalue()


@pytest.mark.parametrize('name', ['../escape', 'TRACE/../escape', 'TRACE/file:stream', 'TRACE/..\\escape', 'Other/app.exe', 'TRACE/bad./file'])
def test_archive_cannot_escape_or_replace_duplicate_files(tmp_path, name):
    archive = tmp_path / 'update.zip'
    archive.write_bytes(zip_content(name))
    with pytest.raises(ValueError, match='unsafe path'):
        updates.extract_release(archive, tmp_path / 'extracted')
    assert not (tmp_path / 'extracted').exists()


@pytest.mark.parametrize('valid', [True, False])
def test_download_checks_digest_before_extracting(tmp_path, monkeypatch, valid):
    payload = zip_content()
    class Response(io.BytesIO):
        url = 'https://release-assets.githubusercontent.com/asset'
    monkeypatch.setattr(updates, 'urlopen', lambda *args, **kwargs: Response(payload))
    monkeypatch.setattr(updates, 'user_root', lambda: tmp_path)
    manager = updates.UpdateManager()
    asset = release()['assets'][0]
    asset['size'] = len(payload)
    manager.release = {'tag': 'v0.5.2', 'asset': asset,
                       'sha256': hashlib.sha256(payload).hexdigest() if valid else '0' * 64}
    if valid:
        assert manager.download()['ready']
        assert (manager.prepared / 'TRACE' / 'TRACE.exe').is_file()
    else:
        with pytest.raises(ValueError, match='integrity'):
            manager.download()
        assert manager.prepared is None


def app_folder(path, value):
    path.mkdir(parents=True)
    (path / '_internal').mkdir()
    (path / 'TRACE.exe').write_text(value)
    return path


def test_install_retains_old_version_and_does_not_touch_saved_data(tmp_path):
    old = app_folder(tmp_path / 'install' / 'TRACE', 'old')
    staged = app_folder(tmp_path / 'staged' / 'TRACE', 'new')
    state = tmp_path / 'user' / 'roster.json'
    state.parent.mkdir()
    state.write_text('saved roster')
    launches = []
    backup = replace_application(old, staged, launches.append)
    assert (old / 'TRACE.exe').read_text() == 'new'
    assert (backup / 'TRACE.exe').read_text() == 'old'
    assert state.read_text() == 'saved roster'
    assert launches == [old / 'TRACE.exe']


def test_install_restores_old_app_when_restart_fails(tmp_path):
    old = app_folder(tmp_path / 'install' / 'TRACE', 'old')
    staged = app_folder(tmp_path / 'staged' / 'TRACE', 'new')
    attempts = []
    def launch(executable):
        attempts.append(executable.read_text())
        if len(attempts) == 1:
            raise OSError('Restart failed')
    with pytest.raises(OSError, match='Restart failed'):
        replace_application(old, staged, launch)
    assert (old / 'TRACE.exe').read_text() == 'old'
    assert attempts == ['new', 'old']


def test_update_api_requires_session_and_desktop_for_install(tmp_path, monkeypatch):
    monkeypatch.setattr(updates.UpdateManager, 'check', lambda _: {'available': False})
    server = create_server(0, tmp_path / 'roster.json', settings_path=tmp_path / 'settings.json')
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(url + '/api/session') as response:
            token = json.load(response)['token']
        request = Request(url + '/api/updates/check', data=b'{}')
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
        request.add_header('X-Editor-Token', token)
        with urlopen(request) as response:
            assert json.load(response) == {'available': False}
        request = Request(url + '/api/updates/install', data=b'{}', headers={'X-Editor-Token': token})
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
