"""Direct Windows process memory access using only the Python standard library."""

import ctypes
import os
import struct
from ctypes import wintypes as W
from pathlib import Path

from .roster import RosterError


class ProcessEntry(ctypes.Structure):
    _fields_ = [('dwSize', W.DWORD), ('cntUsage', W.DWORD), ('th32ProcessID', W.DWORD),
                ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', W.DWORD),
                ('cntThreads', W.DWORD), ('th32ParentProcessID', W.DWORD),
                ('pcPriClassBase', W.LONG), ('dwFlags', W.DWORD), ('szExeFile', W.WCHAR * 260)]


class ModuleEntry(ctypes.Structure):
    _fields_ = [('dwSize', W.DWORD), ('th32ModuleID', W.DWORD), ('th32ProcessID', W.DWORD),
                ('GlblcntUsage', W.DWORD), ('ProccntUsage', W.DWORD),
                ('modBaseAddr', ctypes.c_void_p), ('modBaseSize', W.DWORD),
                ('hModule', W.HMODULE), ('szModule', W.WCHAR * 256), ('szExePath', W.WCHAR * 260)]


def kernel():
    if os.name != 'nt':
        raise RosterError('Direct game connection requires Windows.')
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RosterError('Install 64-bit Python to connect to NBA 2K27.')
    dll = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateToolhelp32Snapshot': ([W.DWORD, W.DWORD], W.HANDLE),
        'Process32FirstW': ([W.HANDLE, ctypes.POINTER(ProcessEntry)], W.BOOL),
        'Process32NextW': ([W.HANDLE, ctypes.POINTER(ProcessEntry)], W.BOOL),
        'Module32FirstW': ([W.HANDLE, ctypes.POINTER(ModuleEntry)], W.BOOL),
        'Module32NextW': ([W.HANDLE, ctypes.POINTER(ModuleEntry)], W.BOOL),
        'OpenProcess': ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
        'CloseHandle': ([W.HANDLE], W.BOOL),
        'QueryFullProcessImageNameW': ([W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)], W.BOOL),
        'GetProcessTimes': ([W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4, W.BOOL),
        'GetExitCodeProcess': ([W.HANDLE, ctypes.POINTER(W.DWORD)], W.BOOL),
        'ReadProcessMemory': ([W.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                               ctypes.POINTER(ctypes.c_size_t)], W.BOOL),
        'WriteProcessMemory': ([W.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                ctypes.POINTER(ctypes.c_size_t)], W.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(dll, name)
        function.argtypes, function.restype = args, result
    return dll


def windows_error(action):
    code = ctypes.get_last_error()
    detail = ctypes.FormatError(code).strip()
    hint = ' Try running the editor as administrator if the game is elevated.' if code == 5 else ''
    return RosterError(f'{action}: Windows error {code}: {detail}.{hint}')


def executable_path(location):
    path = Path(location).expanduser().resolve()
    return path if path.suffix.casefold() == '.exe' else path / 'NBA2K27.exe'


def read_pe_build(read):
    """PE header reader shared by on-disk and remote-memory verification."""
    if read(0, 2) != b'MZ':
        raise RosterError('Game executable has an invalid DOS header.')
    pe = struct.unpack('<I', read(0x3C, 4))[0]
    if not 0x40 <= pe <= 1024 * 1024 or read(pe, 4) != b'PE\0\0':
        raise RosterError('Game executable has an invalid PE header.')
    if read(pe + 4, 2) != b'\x64\x86' or read(pe + 24, 2) != b'\x0b\x02':
        raise RosterError('The configured executable must be a 64-bit Windows game.')
    stamp = struct.unpack('<I', read(pe + 8, 4))[0]
    size = struct.unpack('<I', read(pe + 0x50, 4))[0]
    return f'{stamp:X}:{size:X}'


def file_build(path):
    try:
        with Path(path).open('rb') as file:
            def read(offset, size):
                file.seek(offset)
                data = file.read(size)
                if len(data) != size:
                    raise RosterError('Truncated game executable header.')
                return data
            return read_pe_build(read)
    except OSError as error:
        raise RosterError(f'Game executable not accessible at {path}. Set the correct game folder in Connection details.') from error


class WindowsMemory:
    def __init__(self, location):
        self.path = executable_path(location)

    def open(self, writable=False):
        return ProcessMemory(self.path, writable)


class ProcessMemory:
    def __init__(self, path, writable=False):
        self.path, self.writable = Path(path), writable
        self.dll = kernel()
        self.handle = None

    def _snapshot(self, flags, pid=0):
        for _ in range(3):
            handle = self.dll.CreateToolhelp32Snapshot(flags, pid)
            if handle not in (None, ctypes.c_void_p(-1).value):
                return handle
            if ctypes.get_last_error() != 24:  # ERROR_BAD_LENGTH: module list changed.
                break
        raise windows_error('Could not inspect the running game')

    def _process_ids(self):
        snapshot = self._snapshot(2)
        try:
            entry = ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            present = self.dll.Process32FirstW(snapshot, ctypes.byref(entry))
            ids = []
            while present:
                if entry.szExeFile.casefold() == self.path.name.casefold():
                    ids.append(entry.th32ProcessID)
                present = self.dll.Process32NextW(snapshot, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise windows_error('Could not enumerate game processes')
            return ids
        finally:
            self.dll.CloseHandle(snapshot)

    def _image_path(self, handle):
        buffer = ctypes.create_unicode_buffer(32768)
        size = W.DWORD(len(buffer))
        if not self.dll.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise windows_error('Could not verify the game executable path')
        return Path(buffer.value).resolve()

    def _module_base(self, pid):
        snapshot = self._snapshot(0x8 | 0x10, pid)
        try:
            entry = ModuleEntry()
            entry.dwSize = ctypes.sizeof(entry)
            present = self.dll.Module32FirstW(snapshot, ctypes.byref(entry))
            while present:
                if entry.szModule.casefold() == self.path.name.casefold():
                    return entry.modBaseAddr
                present = self.dll.Module32NextW(snapshot, ctypes.byref(entry))
            raise windows_error('Could not locate the game module')
        finally:
            self.dll.CloseHandle(snapshot)

    def __enter__(self):
        # Verify the installed file before attaching; no broad process privileges.
        installed_build = file_build(self.path)
        ids = self._process_ids()
        if not ids:
            raise RosterError(f'{self.path.name} is not running. Start NBA 2K27 and load your roster.')
        candidates = []
        try:
            for pid in ids:
                handle = self.dll.OpenProcess(0x1000 | 0x10, False, pid)
                if not handle:
                    raise windows_error('Windows denied access to the game')
                try:
                    if os.path.normcase(str(self._image_path(handle))) == os.path.normcase(str(self.path.resolve())):
                        candidates.append((pid, handle))
                        handle = None
                finally:
                    if handle:
                        self.dll.CloseHandle(handle)
            if len(candidates) != 1:
                raise RosterError('No unique running game matches the configured folder. Check Connection details or close duplicate game instances.')
            self.pid, self.handle = candidates.pop()
            self.module_base = self._module_base(self.pid)
            creation, exit_time, kernel_time, user_time = (W.FILETIME() for _ in range(4))
            if not self.dll.GetProcessTimes(self.handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                             ctypes.byref(kernel_time), ctypes.byref(user_time)):
                raise windows_error('Could not verify the game process lifetime')
            self.created = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            self.build = read_pe_build(lambda offset, size: self.read(self.module_base + offset, size))
            if installed_build != self.build:
                raise RosterError('The running game differs from the configured executable. Restart the game after an update.')
            if self.writable:
                handle = self.dll.OpenProcess(0x1000 | 0x10 | 0x20 | 0x8, False, self.pid)
                if not handle:
                    raise windows_error('Windows denied memory write access')
                # The read handle pins the original process object while opening write access.
                other_creation = W.FILETIME()
                if not self.dll.GetProcessTimes(handle, ctypes.byref(other_creation), ctypes.byref(exit_time),
                                                 ctypes.byref(kernel_time), ctypes.byref(user_time)):
                    self.dll.CloseHandle(handle)
                    raise windows_error('Could not verify write access')
                if ((other_creation.dwHighDateTime << 32) | other_creation.dwLowDateTime) != self.created:
                    self.dll.CloseHandle(handle)
                    raise RosterError('Game restarted while connecting. Try again.')
                self.dll.CloseHandle(self.handle)
                self.handle = handle
            return self
        except Exception:
            self.close()
            raise
        finally:
            for _, handle in candidates:
                self.dll.CloseHandle(handle)

    def close(self):
        if self.handle:
            self.dll.CloseHandle(self.handle)
            self.handle = None

    def __exit__(self, *_):
        self.close()

    def read(self, address, size):
        if not self.handle or address <= 0 or not 0 < size <= 8 * 1024 * 1024:
            raise RosterError('Invalid memory read request.')
        buffer = ctypes.create_string_buffer(size)
        count = ctypes.c_size_t()
        if not self.dll.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(count)) or count.value != size:
            raise windows_error(f'Could not read game memory at 0x{address:X}')
        return buffer.raw

    def write(self, address, data):
        if not self.handle or not self.writable or address <= 0 or not data:
            raise RosterError('Game memory write access is not enabled.')
        count = ctypes.c_size_t()
        buffer = ctypes.create_string_buffer(data, len(data))
        if not self.dll.WriteProcessMemory(self.handle, address, buffer, len(data), ctypes.byref(count)) or count.value != len(data):
            raise windows_error(f'Could not write game memory at 0x{address:X}')

    def alive(self):
        code = W.DWORD()
        return bool(self.dll.GetExitCodeProcess(self.handle, ctypes.byref(code)) and code.value == 259)
