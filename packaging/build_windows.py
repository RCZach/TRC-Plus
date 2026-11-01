"""Build a self-contained Windows folder and shareable ZIP using PyInstaller."""

import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = 'TRACE'


def main():
    if sys.platform != 'win32' or struct.calcsize('P') != 8:
        raise SystemExit('Build this release using 64-bit Python on Windows.')
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    sys.path.insert(0, str(ROOT / 'src'))
    from trace_app.version import VERSION
    if VERSION != version:
        raise SystemExit('Update version.py and pyproject.toml to the same release version.')
    release_root = ROOT / 'dist' / version
    version_tuple = tuple(int(part) for part in version.split('.')) + (0,)
    version_info = ROOT / 'build' / 'windows-version.txt'
    version_info.parent.mkdir(parents=True, exist_ok=True)
    version_info.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={version_tuple!r}, prodvers={version_tuple!r},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', '{APP_NAME} roster editor'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', '{APP_NAME}'),
    StringStruct('OriginalFilename', '{APP_NAME}.exe'),
    StringStruct('ProductName', '{APP_NAME}'),
    StringStruct('ProductVersion', '{version}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""", encoding='utf-8')
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
        '--name', APP_NAME, '--distpath', str(release_root), '--workpath', str(ROOT / 'build'),
        '--version-file', str(version_info),
        '--specpath', str(ROOT / 'build'), '--paths', str(ROOT / 'src'),
        '--paths', str(ROOT / 'build' / 'desktop-deps'),
        '--collect-data', 'trace_app',
        '--collect-data', 'webview',
        '--hidden-import', 'webview.platforms.edgechromium',
        '--exclude-module', 'webview.platforms.qt',
        '--exclude-module', 'webview.platforms.gtk',
        '--exclude-module', 'webview.platforms.cocoa',
        '--exclude-module', 'webview.platforms.cef',
        '--add-data', f'{ROOT / "config" / "offsets_2k27.json"};config',
        '--add-data', f'{ROOT / "config" / "field_values.json"};config',
        str(ROOT / 'packaging' / 'windows_launcher.py'),
    ], cwd=ROOT, check=True)
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed',
        '--name', 'TRACE Updater', '--distpath', str(release_root / APP_NAME),
        '--workpath', str(ROOT / 'build' / 'updater'), '--specpath', str(ROOT / 'build'),
        '--paths', str(ROOT / 'src'), str(ROOT / 'packaging' / 'updater_launcher.py'),
    ], cwd=ROOT, check=True)
    shutil.copyfile(ROOT / 'packaging' / 'START HERE.txt', release_root / APP_NAME / 'START HERE.txt')
    archive = Path(shutil.make_archive(
        str(ROOT / 'dist' / f'TRACE-{version}-windows-x64'),
        'zip', root_dir=release_root, base_dir=APP_NAME,
    ))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='ascii')
    print(f'\nShare this ZIP: {archive}\nSHA-256: {checksum}')


if __name__ == '__main__':
    main()
