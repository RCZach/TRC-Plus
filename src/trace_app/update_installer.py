"""Independent helper: wait for the old process, replace the app, and restart."""

import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid


def replace_application(target, staged, launch):
    target, staged = target.resolve(), staged.resolve()
    if target == target.parent or staged.name != 'Trace' or target == staged or target.is_relative_to(staged) or staged.is_relative_to(target):
        raise ValueError('Unexpected update installation folders.')
    for directory in (target, staged):
        if not (directory / 'Trace.exe').is_file() or not (directory / '_internal').is_dir():
            raise ValueError('The application folder is incomplete.')
    suffix = uuid.uuid4().hex
    incoming = target.parent / f'.Trace-incoming-{suffix}'
    backup = target.parent / f'Trace-previous-{suffix}'
    # Both paths are verified siblings of the explicitly selected app folder.
    assert incoming.parent == backup.parent == target.parent
    shutil.copytree(staged, incoming)
    moved = False
    try:
        for attempt in range(40):
            try:
                target.rename(backup)
                moved = True
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.25)
        incoming.rename(target)
        launch(target / 'Trace.exe')
    except Exception:
        if moved:
            if target.exists():
                target.rename(target.parent / f'Trace-failed-{suffix}')
            backup.rename(target)
            launch(target / 'Trace.exe')
        raise
    return backup


def main(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    job = manifest_path.parent
    document = json.loads(manifest_path.read_text(encoding='utf-8'))
    arguments = document.get('args', [])
    if not isinstance(arguments, list) or not all(isinstance(value, str) for value in arguments):
        raise ValueError('Unexpected restart arguments.')
    target = Path(document['target']).resolve()
    if target == target.parent or not (target / 'Trace.exe').is_file():
        raise ValueError('Unexpected installation folder.')
    staged = job / 'Trace'
    if not (staged / 'Trace.exe').is_file():
        raise ValueError('The downloaded application is missing.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x100000, False, document['parent_pid'])
    if not handle:
        raise OSError('Could not wait for the running app. Leave it open and try again.')
    # Probe write access before telling the current app to close.
    probe = target.parent / f'.trc-update-probe-{uuid.uuid4().hex}'
    probe.write_text('')
    probe.unlink()
    try:
        if (job / 'cancelled').exists():
            return
        (job / 'ready').write_text('ready')
        if kernel.WaitForSingleObject(handle, 120000) != 0:
            raise TimeoutError('The app did not close in time. Please try the update again.')
    finally:
        kernel.CloseHandle(handle)
    if (job / 'cancelled').exists():
        return

    restarted = []

    def launch(executable):
        process = subprocess.Popen([str(executable), *arguments], cwd=executable.parent, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        restarted.append(process.pid)
        time.sleep(1)
        if process.poll() is not None:
            raise OSError('The updated app exited during startup.')

    backup = replace_application(target, staged, launch)
    (job / 'result.json').write_text(json.dumps({'success': True, 'previous_version': str(backup),
                                                'restarted_pid': restarted[-1]}), encoding='utf-8')
