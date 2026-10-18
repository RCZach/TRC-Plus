"""Exercise actual Win32 read/write calls against an isolated test process."""

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from trc_plus.roster import RosterError
from trc_plus.settings import load_settings, save_settings
from trc_plus.windows_memory import ProcessMemory, executable_path, file_build


def test_settings_round_trip_and_write_gate(tmp_path):
    path = tmp_path / 'settings.json'
    assert not load_settings(path)['enable_writes']
    settings = {'game_path': r'D:\Games\NBA 2K27', 'verified_build': 'ab:cd', 'enable_writes': True}
    saved = save_settings(path, settings)
    assert load_settings(path) == saved
    assert saved['verified_build'] == 'AB:CD'
    with pytest.raises(RosterError):
        save_settings(path, {'enable_writes': True})
    assert load_settings(path) == saved
    assert executable_path(r'D:\Games\NBA 2K27').name == 'NBA2K27.exe'


def test_pe_header_validation(tmp_path):
    raw = bytearray(512)
    raw[:2] = b'MZ'
    struct.pack_into('<I', raw, 0x3C, 0x80)
    raw[0x80:0x84] = b'PE\0\0'
    raw[0x84:0x86] = b'\x64\x86'
    raw[0x98:0x9A] = b'\x0b\x02'
    struct.pack_into('<I', raw, 0x88, 0x1234)
    struct.pack_into('<I', raw, 0xD0, 0x5678)
    path = tmp_path / 'fixture.exe'
    path.write_bytes(raw)
    assert file_build(path) == '1234:5678'
    path.write_bytes(b'not a PE executable')
    with pytest.raises(RosterError):
        file_build(path)


@pytest.mark.skipif(os.name != 'nt', reason='Win32 integration test')
def test_native_reads_and_writes_without_cheat_engine(monkeypatch):
    script = """
import ctypes, json, os, sys
buffer = ctypes.create_string_buffer(b'original', 16)
print(json.dumps({'pid': os.getpid(), 'address': ctypes.addressof(buffer)}), flush=True)
sys.stdin.readline()
print(buffer.value.decode(), flush=True)
"""
    child = subprocess.Popen([sys.executable, '-u', '-c', script], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        info = json.loads(child.stdout.readline())
        # Select only the isolated child when other Python processes are running.
        monkeypatch.setattr(ProcessMemory, '_process_ids', lambda self: [info['pid']])
        with ProcessMemory(Path(sys.executable), writable=True) as memory:
            assert memory.pid == child.pid
            assert memory.created > 0
            assert memory.alive()
            assert memory.read(info['address'], 8) == b'original'
            memory.write(info['address'], b'updated\0')
            assert memory.read(info['address'], 8) == b'updated\0'
        child.stdin.write('\n')
        child.stdin.flush()
        assert child.stdout.readline().strip() == 'updated'
        assert child.wait(timeout=5) == 0
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
