"""Smoke-test the actual ZIP with an isolated user and no Python on PATH."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import tomllib
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
HTTP = build_opener(ProxyHandler({}))


def request(url, document=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token is not None:
        headers['X-Editor-Token'] = token
    data = None if document is None else json.dumps(document).encode('utf-8')
    with HTTP.open(Request(url, data=data, headers=headers), timeout=5) as response:
        return response.read()


@contextmanager
def running_app(executable, work, environment, port):
    log = Path(environment['LOCALAPPDATA']) / 'TRACE' / 'desktop.log'
    if log.exists():
        log.write_text('')
    with (work / f'launch-{port}.log').open('wb') as output:
        process = subprocess.Popen(
            [str(executable), '--no-browser', '--port', str(port)], cwd=work,
            env=environment, stdout=output, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                contents = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
                match = re.search(r'TRACE: (http://127\.0\.0\.1:\d+)', contents)
                if match:
                    yield match[1], contents
                    break
                if process.poll() is not None:
                    raise AssertionError(f'Executable exited: {contents}')
                time.sleep(0.1)
            else:
                raise AssertionError(f'Executable startup timed out: {contents}')
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


def main():
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    archive = ROOT / 'dist' / f'TRACE-{version}-windows-x64.zip'
    with tempfile.TemporaryDirectory(prefix='release-smoke-', dir=ROOT / 'build') as directory:
        work = Path(directory).resolve()
        with ZipFile(archive) as bundle:
            names = bundle.namelist()
            for name in names:
                assert (work / name).resolve().is_relative_to(work), name
            assert not any('/data/' in name or name.endswith('game_connection.json') for name in names)
            bundle.extractall(work)
        executable = work / 'TRACE' / 'TRACE.exe'
        signature_values = json.loads((work / 'TRACE' / '_internal' / 'config' /
                                       'signature_values_2k27.json').read_text(encoding='utf-8'))
        assert signature_values['fields'] and signature_values['enums'], 'Native animation catalog is missing'
        pythonnet_assembly = work / 'TRACE' / '_internal' / 'pythonnet' / 'runtime' / 'Python.Runtime.dll'
        internet_mark = Path(str(pythonnet_assembly) + ':Zone.Identifier')
        internet_mark.write_text('[ZoneTransfer]\nZoneId=3\n', encoding='ascii')
        environment = os.environ.copy()
        environment['LOCALAPPDATA'] = str(work / 'user')
        for name in list(environment):
            if name.upper() in ('PATH', 'PYTHONPATH', 'PYTHONHOME', 'LOCALAPPDATA'):
                environment.pop(name)
        environment['LOCALAPPDATA'] = str(work / 'user')
        environment['PATH'] = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32')
        state = work / 'user' / 'TRACE'
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            with running_app(executable, work, environment, port) as (url, log):
                assert not internet_mark.exists(), 'Downloaded .NET assembly stayed blocked'
                assert not url.endswith(f':{port}'), 'Occupied-port fallback failed'
                assert 'already in use' in log
                page = request(url + '/')
                assert b'<title>TRACE</title>' in page
                assert b'aria-label="TRACE home"' in page
                assert b'ROSTER STUDIO' not in page.upper()
                script = request(url + '/app.js')
                assert len(script) > 1000
                assert b"link.download='TRACE-roster.json'" in script
                assert len(request(url + '/style.css')) > 1000
                session = json.loads(request(url + '/api/session'))
                assert session['app_version'] == version, 'Packaged app version is incorrect'
                assert session['profile']['Attributes']
                assert session['game_settings']['enable_writes'] is False
                token = session['token']
                roster = session['roster']
                roster['players'][0]['name'] = 'Release Persistence Check'
                try:
                    request(url + '/api/roster', roster)
                except HTTPError as error:
                    assert error.code == 403
                else:
                    raise AssertionError('Missing session token accepted')
                request(url + '/api/roster', roster, token)
                settings = {'game_path': r'C:\Games\NBA 2K27', 'verified_build': '', 'enable_writes': False}
                request(url + '/api/game/settings', settings, token)
                assert json.loads((state / 'data' / 'roster.json').read_text(encoding='utf-8')) == roster
                assert json.loads((state / 'config' / 'game_connection.json').read_text()) == settings
                values = state / 'config' / 'field_values.json'
                catalog = json.loads(values.read_text(encoding='utf-8'))
                assert catalog['builds'], 'Bundled named values are missing'
                catalog['builds']['TEST-USER-CATALOG'] = {}
                values.write_text(json.dumps(catalog), encoding='utf-8')
        with running_app(executable, work, environment, 0) as (url, _):
            session = json.loads(request(url + '/api/session'))
            assert session['roster'] == roster
            assert session['game_settings'] == settings
            assert 'TEST-USER-CATALOG' in json.loads(values.read_text(encoding='utf-8'))['builds']
        assert not (work / 'data').exists(), 'Saved relative to working directory'
        assert not (executable.parent / 'config').exists(), 'Saved beside executable'
        # Exercise the old-to-new data migration using the actual executable.
        legacy = work / 'user' / 'TRC Roster Studio'
        state.rename(legacy)
        with running_app(executable, work, environment, 0) as (url, _):
            session = json.loads(request(url + '/api/session'))
            assert session['roster'] == roster
            assert session['game_settings'] == settings
            assert 'TEST-USER-CATALOG' in json.loads(values.read_text(encoding='utf-8'))['builds']
        assert (legacy / 'data' / 'roster.json').exists(), 'Original workspace removed'
    print('PASS: extracted ZIP starts without Python on PATH; UI and profiles load; occupied-port fallback, session protection, saves, and restart persistence work.')


if __name__ == '__main__':
    main()
