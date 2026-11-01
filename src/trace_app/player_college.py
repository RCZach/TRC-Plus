"""Observed College / From labels and validated session-bound catalog references."""

import hashlib
import math

from .roster import RosterError


COLLEGE_BUILD = '6ad2e48c:36532000'
COLLEGE_POINTER = 0xB0
COLLEGE_NAME_SIZE = 48
COLLEGE_RECORD_SIZE = 72
COLLEGE_FIELD = ('vitals', 'College / From')


def college_name(raw):
    if len(raw) != COLLEGE_NAME_SIZE or b'\0' not in raw:
        return None
    try:
        name = raw.split(b'\0', 1)[0].decode('utf-8')
    except UnicodeError:
        return None
    return name if name.strip() and not any(ord(c) < 32 or ord(c) == 127 for c in name) else None


def build_college_catalog(process, profile, records, base):
    """Resolve only the bounded span between independently loaded references.

    No global catalog start/count or heap address is assumed. A 72-byte stride
    was independently observed between Arizona and Argentina and across 362
    distinct references. Every included name and source reference must agree.
    """
    if process.build.casefold() != COLLEGE_BUILD or profile.stride != 0x4F8:
        return None
    sources = {}
    for identity, row in records.items():
        ptr = int.from_bytes(row[COLLEGE_POINTER:COLLEGE_POINTER + 8], 'little')
        if 0x10000 <= ptr <= 0x7FFFFFFFFFFF - COLLEGE_RECORD_SIZE and ptr % 8 == 0:
            sources.setdefault(ptr, identity)
    pointers = sorted(sources)
    if len(pointers) < 3 or math.gcd(*(b-a for a, b in zip(pointers, pointers[1:]))) != COLLEGE_RECORD_SIZE:
        return None
    start, end = pointers[0], pointers[-1] + COLLEGE_RECORD_SIZE
    if end - start > COLLEGE_RECORD_SIZE * 2048 or not (end <= base or start >= base + len(records) * profile.stride):
        return None
    try:
        raw = process.read(start, end - start)
        if len(raw) != end - start:
            return None
        names = {}
        for offset in range(0, len(raw), COLLEGE_RECORD_SIZE):
            name = college_name(raw[offset:offset + COLLEGE_NAME_SIZE])
            if name is None:
                return None
            names[start + offset] = name
        anchors = []
        # Several distinct source players keep catalog ownership grounded even
        # if one of these players is the target of a college edit.
        for pointer in pointers[::max(1, len(pointers)//12)][:16]:
            identity = sources[pointer]
            index = int(identity.split('-')[1])
            fresh = process.read(base + index * profile.stride, profile.stride)
            if fresh[:0x58] != records[identity][:0x58] or fresh[COLLEGE_POINTER:COLLEGE_POINTER+8] != pointer.to_bytes(8, 'little'):
                return None
            anchors.append((index, pointer))
        if process.read(start, len(raw)) != raw:
            return None
        by_label = {}
        for pointer, name in names.items():
            by_label.setdefault(name.strip().casefold(), []).append(pointer)
        return {'start': start, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                'names': names, 'choices': {names[ptrs[0]]: ptrs[0] for ptrs in by_label.values() if len(ptrs) == 1},
                'anchors': anchors, 'base': base, 'pid': process.pid, 'created': process.created,
                'module_base': process.module_base}
    except (RosterError, OSError):
        return None


def validate_college_catalog(process, profile, catalog, base):
    if (not catalog or process.build.casefold() != COLLEGE_BUILD or profile.stride != 0x4F8 or
            (catalog['pid'], catalog['created'], catalog['module_base'], catalog['base']) !=
            (process.pid, process.created, process.module_base, base)):
        return False
    field = profile.fields.get(COLLEGE_FIELD)
    if (not field or not field.writable or (field.offset, field.bits, field.shift, field.kind) !=
            (COLLEGE_POINTER, 64, 0, 'college_reference') or (field.verified_build or '').casefold() != COLLEGE_BUILD):
        return False
    try:
        raw = process.read(catalog['start'], catalog['size'])
        if len(raw) != catalog['size'] or hashlib.sha256(raw).hexdigest() != catalog['sha256']:
            return False
        matching = 0
        for index, pointer in catalog['anchors']:
            row = process.read(base + index * profile.stride, profile.stride)
            # Process/roster and transaction guards own player identity checks.
            # Names are editable; pinning them again here would invalidate our
            # own name transactions when they update catalog source players.
            if len(row) == profile.stride and int.from_bytes(row[COLLEGE_POINTER:COLLEGE_POINTER+8], 'little') in catalog['names']:
                matching += 1
        return matching >= 2
    except (RosterError, OSError):
        return False


def read_college(process, profile, record, player_address):
    if (process.build.casefold() != COLLEGE_BUILD or profile.stride != 0x4F8 or
            len(record) != profile.stride):
        return {}
    pointer_bytes = record[COLLEGE_POINTER:COLLEGE_POINTER + 8]
    pointer = int.from_bytes(pointer_bytes, 'little')
    if not 0x10000 <= pointer <= 0x7FFFFFFFFFFF - COLLEGE_NAME_SIZE or pointer % 8:
        return {}
    try:
        raw = process.read(pointer, COLLEGE_NAME_SIZE)
        name = college_name(raw)
        if name is None:
            return {}
        fresh = process.read(player_address, profile.stride)
        if (len(fresh) != profile.stride or fresh[:0x58] != record[:0x58] or
                fresh[COLLEGE_POINTER:COLLEGE_POINTER + 8] != pointer_bytes or
                process.read(pointer, COLLEGE_NAME_SIZE) != raw):
            return {}
        # Persist the label only. Runtime references are never roster values.
        return {'college_from': name}
    except (RosterError, OSError, UnicodeError):
        return {}
