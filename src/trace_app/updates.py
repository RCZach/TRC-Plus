"""Optional public GitHub Releases updates; never update without a user action."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile

from .paths import user_root
from .version import VERSION, REPOSITORY

MAX_DOWNLOAD = 512 * 1024 * 1024


def version_number(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value)
    if not match:
        raise ValueError('The release must have a version such as v0.3.0.')
    return tuple(map(int, match.groups()))


def read_url(url, limit):
    request = Request(url, headers={'User-Agent': f'Trace/{VERSION}', 'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=30) as response:
        if urlparse(response.url).scheme != 'https':
            raise ValueError('Update downloads must use HTTPS.')
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError('The update response is too large.')
        return content


def asset_url(asset, tag):
    url = asset.get('browser_download_url', '')
    parsed = urlparse(url)
    expected = f'/{REPOSITORY}/releases/download/{tag}/{asset["name"]}'
    if parsed.scheme != 'https' or parsed.netloc != 'github.com' or unquote(parsed.path) != expected or parsed.query or parsed.fragment:
        raise ValueError('The release contains an unexpected download address.')
    return url


def extract_release(archive, destination):
    """Only extract normal files beneath the release's fixed application folder."""
    destination = destination.resolve()
    with ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > 10000 or sum(item.file_size for item in entries) > 1024 ** 3:
            raise ValueError('The update archive is too large.')
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            key = path.as_posix().casefold()
            if (not path.parts or path.parts[0] != 'Trace' or path.is_absolute()
                    or '..' in path.parts or '\\' in item.filename or ':' in item.filename
                    or item.filename.rstrip('/') != path.as_posix()
                    or any(part.endswith((' ', '.')) for part in path.parts)
                    or (item.external_attr >> 16) & 0o170000 == 0o120000
                    or key in seen or not (destination / item.filename).resolve().is_relative_to(destination)):
                raise ValueError('The update archive contains an unsafe path.')
            seen.add(key)
        bundle.extractall(destination)
    app = destination / 'Trace'
    for required in ('Trace.exe', 'Trace Updater.exe'):
        if not (app / required).is_file():
            raise ValueError(f'The release is incomplete: missing {required}.')
    if not list(app.glob('_internal/python3*.dll')):
        raise ValueError('The release is incomplete: missing its Python runtime.')
    return app


class UpdateManager:
    def __init__(self):
        self.release = None
        self.prepared = None

    def check(self):
        self.release = None
        self.prepared = None
        try:
            release = json.loads(read_url(f'https://api.github.com/repos/{REPOSITORY}/releases/latest', 2 * 1024 * 1024))
        except HTTPError as error:
            if error.code == 404:
                return {'current_version': VERSION, 'available': False, 'message': 'No public release is available yet.'}
            raise ValueError(f'GitHub could not check for updates (HTTP {error.code}). Try again later.') from error
        except (URLError, TimeoutError, OSError) as error:
            raise ValueError('Could not reach GitHub. Check your internet connection and try again.') from error
        tag = release.get('tag_name', '')
        newer = version_number(tag) > version_number(VERSION)
        if release.get('draft') or release.get('prerelease'):
            raise ValueError('Only stable, published releases can be installed.')
        result = {'current_version': VERSION, 'version': tag.lstrip('v'), 'available': newer,
                  'notes': str(release.get('body') or '')[:50000],
                  'message': 'An update is available.' if newer else 'You are up to date.'}
        if newer:
            filename = f'Trace-{tag.lstrip("v")}-windows-x64.zip'
            assets = {asset['name']: asset for asset in release.get('assets', [])}
            if filename not in assets:
                raise ValueError('The latest release does not have its Windows app ZIP yet. Try again later.')
            asset = assets[filename]
            asset_url(asset, tag)
            digest = asset.get('digest') or ''
            if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest):
                checksum = assets.get(filename + '.sha256')
                if not checksum:
                    raise ValueError('The latest release does not have a download checksum yet.')
                checksum_text = read_url(asset_url(checksum, tag), 1024).decode('ascii').strip().split()
                if len(checksum_text) != 2 or checksum_text[1] != filename or not re.fullmatch(r'[0-9a-fA-F]{64}', checksum_text[0]):
                    raise ValueError('The release checksum is invalid.')
                digest = 'sha256:' + checksum_text[0]
            self.release = {'tag': tag, 'asset': asset, 'sha256': digest[7:].lower()}
        return result

    def download(self):
        self.prepared = None
        if not self.release:
            raise ValueError('Check for an available update first.')
        base = user_root() / 'updates'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='download-', dir=base) as temporary:
            job = Path(temporary)
            archive = job / 'release.zip'
            asset = self.release['asset']
            request = Request(asset_url(asset, self.release['tag']), headers={'User-Agent': f'Trace/{VERSION}'})
            try:
                with urlopen(request, timeout=30) as response, archive.open('wb') as output:
                    if urlparse(response.url).scheme != 'https':
                        raise ValueError('Update downloads must use HTTPS.')
                    digest, size = hashlib.sha256(), 0
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_DOWNLOAD:
                            raise ValueError('The update download is too large.')
                        digest.update(chunk)
                        output.write(chunk)
            except (URLError, TimeoutError, OSError) as error:
                raise ValueError('The update download failed. Check your connection and try again.') from error
            if digest.hexdigest() != self.release['sha256'] or size != asset.get('size'):
                raise ValueError('The download did not pass its integrity check. Try downloading again.')
            extracted = extract_release(archive, job / 'extracted')
            # Keep only this validated payload after the temporary download is cleaned up.
            destination = Path(tempfile.mkdtemp(prefix='ready-', dir=base))
            shutil.move(str(extracted), destination / 'Trace')
            self.prepared = destination
        return {'ready': True, 'version': self.release['tag'].lstrip('v')}

    def launch_installer(self):
        if not getattr(sys, 'frozen', False) or not self.prepared:
            raise ValueError('Install updates from the packaged desktop app after downloading an update.')
        target = Path(sys.executable).resolve().parent
        if user_root().resolve().is_relative_to(target):
            raise ValueError('Move the app outside its saved-data folder before updating.')
        helper = target / 'Trace Updater.exe'
        if not helper.is_file():
            raise ValueError('The updater is missing. Extract the complete app ZIP again.')
        job = self.prepared
        shutil.copyfile(helper, job / helper.name)
        manifest = job / 'install.json'
        manifest.write_text(json.dumps({'target': str(target), 'parent_pid': os.getpid(), 'args': sys.argv[1:]}), encoding='utf-8')
        process = subprocess.Popen([str(job / helper.name), str(manifest)], cwd=job,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (job / 'ready').exists():
                return
            if process.poll() is not None:
                break
            time.sleep(0.05)
        (job / 'cancelled').write_text('cancelled')
        self.prepared = None
        raise ValueError('The updater could not start. The app has been left open; see the update log in your app data folder.')
