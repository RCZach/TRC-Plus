"""Exercise the compiled updater against an isolated copy of the release."""

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time
import tomllib
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from verify_windows import ROOT, request


def wait_for(callback, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = callback()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError('Timed out waiting for the packaged updater.')


def main():
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    from trace_app.updates import extract_release
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    archive = ROOT / 'dist' / f'Trace-{version}-windows-x64.zip'
    with tempfile.TemporaryDirectory(prefix='updater-smoke-', dir=ROOT / 'build') as directory:
        work = Path(directory).resolve()
        target = extract_release(archive, work / 'install')
        job = work / 'job'
        extract_release(archive, job)
        (target / 'old-install-marker.txt').write_text('previous installation')
        (job / 'Trace' / 'new-install-marker.txt').write_text('updated installation')
        environment = os.environ.copy()
        environment['LOCALAPPDATA'] = str(work / 'user')
        for name in list(environment):
            if name.upper() in ('PATH', 'PYTHONPATH', 'PYTHONHOME'):
                environment.pop(name)
        environment['PATH'] = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32')
        log = work / 'user' / 'Trace' / 'desktop.log'
        arguments = ['--no-browser', '--port', '0']
        old = subprocess.Popen([str(target / 'Trace.exe'), *arguments], env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        helper, restarted_pid = None, None
        try:
            def address():
                content = log.read_text(encoding='utf-8') if log.exists() else ''
                matches = re.findall(r'Trace: (http://127\.0\.0\.1:\d+)', content)
                if not matches:
                    return None
                try:
                    request(matches[-1] + '/api/session')
                except URLError:
                    return None
                return matches[-1]
            url = wait_for(address)
            session = json.loads(request(url + '/api/session'))
            roster = session['roster']
            roster['players'][0]['name'] = 'Updater persistence check'
            request(url + '/api/roster', roster, session['token'])
            shutil.copyfile(target / 'Trace Updater.exe', job / 'helper.exe')
            manifest = job / 'install.json'
            manifest.write_text(json.dumps({'target': str(target), 'parent_pid': old.pid, 'args': arguments}))
            helper = subprocess.Popen([str(job / 'helper.exe'), str(manifest)], env=environment,
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            wait_for(lambda: (job / 'ready').exists())
            assert old.poll() is None
            assert (target / 'old-install-marker.txt').exists(), 'Replaced the app before it exited'
            old.terminate()
            old.wait(timeout=10)
            wait_for(lambda: (job / 'result.json').exists())
            result = json.loads((job / 'result.json').read_text())
            restarted_pid = result['restarted_pid']
            assert result['success']
            assert (target / 'new-install-marker.txt').exists()
            assert not (target / 'old-install-marker.txt').exists()
            assert (Path(result['previous_version']) / 'old-install-marker.txt').exists()
            fresh = json.loads(request(wait_for(address) + '/api/session'))
            assert fresh['token'] != session['token']
            assert fresh['roster'] == roster, 'Saved roster changed during update'
            assert fresh['app_version'] == version
            helper.wait(timeout=15)
            assert helper.returncode == 0
        finally:
            if old.poll() is None:
                old.terminate()
                old.wait(timeout=10)
            if restarted_pid:
                try:
                    os.kill(restarted_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            if helper is not None and helper.poll() is None:
                helper.terminate()
                helper.wait(timeout=10)
            time.sleep(0.5)
    print('PASS: compiled updater waits for exit, replaces the app, retains the previous version, restarts without Python, and preserves the saved roster.')


if __name__ == '__main__':
    main()
