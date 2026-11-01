"""Direct game access with server-owned snapshots and reviewed write plans."""

import hashlib
import json
import os
import secrets
import struct
import time
from dataclasses import replace
from pathlib import Path

from .fields import RecordProfile, number
from .roster import RosterError, validate_roster
from .settings import DEFAULT_GAME_PATH
from .windows_memory import WindowsMemory
from .mappings import ValueCatalog
from .paths import default_values_path
from .player_summary import player_summary, read_teams
from .player_body import (read_body, read_body_model, snapshot_body, encode_body,
                          decode_body, body_span, is_body_field, BODY_SIZE, BODY_POINTER, BODY_SCALES)
from .player_college import (read_college, build_college_catalog, validate_college_catalog, COLLEGE_FIELD)
from .setter_mappings import SETTER_FIELDS, verified_setter_fields
from .team_sections import populate_team_sections
from .team_sections import COACH_FIELDS
from .coaching import enable_coaching, prepare_coaching, validate_coaching_context, coaching_value


# Read-only fallback chain reported by the public NBA 2K27 player editor.
# The chain is only a candidate on other builds; _validate_roster_table must
# prove it points to this profile's player records before Trace uses it.
COMMUNITY_ROOT_RVA = 161861320
COMMUNITY_ROSTER_POINTER_OFFSET = 168
COMMUNITY_PLAYER_COUNT_OFFSET = 16
COMMUNITY_PLAYER_TABLE_OFFSET = 24

# Exact pointer references observed on this build and rechecked after a roster
# reload, a switch to another roster, and a game restart. Field write support
# is separately limited below. Excludes references that moved into the table
# on selection or became null while the new roster remained readable.
OBSERVED_PLAYER_POINTERS = {
    '6ad2e48c:36532000': (
        0xAAE3F70, 0xAAE4430, 0xAB452B0, 0xAB45770,
        0xAB49470, 0xAB49930,
    ),
}

# Individually verified through in-game edits, confirmed screen readouts,
# or named setter masks matched against the exact running executable:
# Driving Layup 82 -> 83, Speed 77 -> 78, Driving Layup Tendency 70 -> 71.
# The packed tendency observation also preserved its neighboring bits.
OBSERVED_BUILD_WRITABLE_FIELDS = {
    '6ad2e48c:36532000': {
        ('attributes', 'Driving Layup'): (0x43C, 8, 0, 'bits'),
        ('attributes', 'Speed'): (0x453, 8, 0, 'bits'),
        ('tendencies', 'Driving Layup Tendency'): (0x471, 7, 7, 'bits'),
        ('badges', 'Rise Up'): (0x4D6, 3, 7, 'bits'),
        # Named setter masks checked against this exact running build; the
        # three in-game captures independently anchor the packed block.
        ('badges', 'Reserved'): (0x4D3, 1, 5, 'bits'),
        ('badges', 'Friendly'): (0x4D3, 1, 6, 'bits'),
        ('badges', 'Team Player'): (0x4D3, 1, 7, 'bits'),
        ('badges', 'Extremely Confident'): (0x4D4, 1, 0, 'bits'),
        ('badges', 'Keep It Real'): (0x4D4, 1, 1, 'bits'),
        ('badges', 'Pat My Back'): (0x4D4, 1, 2, 'bits'),
        ('badges', 'Expressive'): (0x4D4, 1, 3, 'bits'),
        ('badges', 'Unpredictable'): (0x4D4, 1, 4, 'bits'),
        ('badges', 'Laid Back'): (0x4D4, 1, 5, 'bits'),
        ('badges', 'Media Ringmaster'): (0x4D4, 1, 6, 'bits'),
        ('badges', 'Warm Weather Fan'): (0x4D4, 1, 7, 'bits'),
        ('badges', 'Finance Savvy'): (0x4D5, 1, 0, 'bits'),
        ('badges', 'Alpha Dog'): (0x4D5, 1, 1, 'bits'),
        ('badges', 'Enforcer'): (0x4D5, 1, 2, 'bits'),
        ('badges', 'Work Ethic'): (0x4D5, 3, 3, 'bits'),
        ('badges', 'Marketability'): (0x4D5, 3, 6, 'bits'),
        ('signatures', 'Jumpshot Base'): (0x408, 10, 0, 'bits'),
        ('vitals', 'Weight'): (0x108, 32, 0, 'float'),
        ('vitals', 'First Name'): (0x28, 320, 0, 'utf16'),
        ('vitals', 'Last Name'): (0, 320, 0, 'utf16'),
        ('vitals', 'Number'): (0x114, 7, 11, 'bits'),
        ('vitals', 'Birth Day'): (0x114, 5, 1, 'bits'),
        ('vitals', 'Birth Month'): (0x36A, 4, 12, 'bits'),
        ('vitals', 'Position'): (0x12D, 3, 0, 'bits'),
        ('vitals', 'Secondary Position'): (0x12D, 3, 3, 'bits'),
        ('vitals', 'Dominant Hand'): (0x12C, 1, 22, 'bits'),
        ('vitals', 'Dominant Dunk Hand'): (0x12C, 2, 23, 'bits'),
        ('vitals', 'Forced Non-Starter'): (0x354, 2, 26, 'bits'),
        ('vitals', 'Play Initiator'): (0x2D6, 1, 5, 'bits'),
        ('vitals', 'FIBA Team'): (0x420, 16, 16, 'bits'),
        ('vitals', 'High School'): (0x100, 16, 16, 'bits'),
        ('vitals', 'Birthplace'): (0x100, 16, 0, 'bits'),
        ('vitals', 'Play Type 1'): (0x1A8, 4, 0, 'bits'),
        ('vitals', 'Play Type 2'): (0x1A8, 4, 4, 'bits'),
        ('vitals', 'Play Type 3'): (0x1A9, 4, 0, 'bits'),
        ('vitals', 'Play Type 4'): (0x1A9, 4, 4, 'bits'),
        ('vitals', 'Birth Year'): (0x110, 12, 16, 'bits'),
        ('vitals', 'Years Pro'): (0x3E0, 5, 17, 'bits'),
        ('vitals', 'Injury 1 Duration Days'): (0x354, 20, 0, 'injury_days'),
        ('vitals', 'Injury 2 Duration Days'): (0x358, 20, 0, 'injury_days'),
        ('vitals', 'Min Potential'): (0x3FC, 7, 0, 'bits'),
        ('vitals', 'Max Potential'): (0x3FC, 7, 7, 'bits'),
        ('vitals', 'Bust Percent'): (0x3FC, 7, 21, 'bits'),
        ('vitals', 'AVG Percent'): (0x358, 7, 20, 'bits'),
        ('vitals', 'Boom Percent'): (0x3FC, 7, 14, 'bits'),
        ('vitals', 'Play for Winner'): (0x2E0, 7, 12, 'bits'),
        ('vitals', 'Financial Security'): (0x2E0, 7, 19, 'bits'),
        ('vitals', 'Loyalty'): (0x2E0, 7, 5, 'bits'),
        ('vitals', 'Peak Age'): (0x114, 6, 18, 'bits'),
        ('vitals', 'Peak End Age'): (0x114, 6, 24, 'bits'),
        ('gear', 'Shoe Home Style'): (0x184, 13, 0, 'bits'),
        ('accessories', 'Headband'): (0x1C8, 4, 22, 'bits'),
        ('hotzones', 'Under Basket'): (0x1CC, 2, 0, 'bits'),
        ('hotzones', 'Close Left'): (0x1CF, 2, 2, 'bits'),
        ('hotzones', 'Close Middle'): (0x1CC, 2, 2, 'bits'),
        ('hotzones', 'Close Right'): (0x1CF, 2, 4, 'bits'),
        ('hotzones', 'Mid-Range Left'): (0x1DC, 2, 3, 'bits'),
        ('hotzones', 'Mid-Range Left Center'): (0x1CC, 2, 4, 'bits'),
        ('hotzones', 'Mid-Range Center'): (0x1CC, 2, 6, 'bits'),
        ('hotzones', 'Mid-Range Right Center'): (0x372, 2, 3, 'bits'),
        ('hotzones', 'Mid-Range Right'): (0x37E, 2, 7, 'bits'),
        ('hotzones', 'Three Left'): (0x1D2, 2, 6, 'bits'),
        ('hotzones', 'Three Left Center'): (0x1D3, 2, 6, 'bits'),
        ('hotzones', 'Three Center'): (0x177, 2, 0, 'bits'),
        ('hotzones', 'Three Right Center'): (0x35F, 2, 5, 'bits'),
        ('hotzones', 'Three Right'): (0x1CF, 2, 0, 'bits'),
    },
}

# User-approved section compatibility after representative live observations.
# Pin the approved field layouts: later profile changes require new approval.
# These hashes describe layouts, not individual in-game verification results.
APPROVED_BUILD_SECTION_LAYOUTS = {
    '6ad2e48c:36532000': {
        'attributes': '2c723b277ae8b108d37f43d6c5663b6d938f259b0cf636fa03c9f731158bfa82',
        'tendencies': '1ce733f432acde2ddbcd82833981e237d4533d7093783dad20cf4fd870ee8acd',
        'badges': '3052a6823311c2e948ae097cdb40371e469acb299af602777464a42842fd4a10',
        'signatures': '0e9d663aee7c993f5414c2144a1b3cbcb33be8fc5ded83369475dee03824e6a6',
    },
}

NAME_STATE_LAYOUTS = {
    'FIRSTNAMEVETTED': (0x110, 1, 31, 'bits'),
    'LASTNAMEVETTED': (0x114, 1, 0, 'bits'),
    'FIRSTLASTNAMESID': (0x2E8, 16, 0, 'bits'),
}


class GameConnection:
    def __init__(self, profile, memory=None, expected_build=None, enable_writes=False,
                 audit_path=Path('data/game_updates.jsonl'), game_path=DEFAULT_GAME_PATH, values_path=None):
        self.profile = RecordProfile(profile)
        self.memory = memory or WindowsMemory(game_path)
        self.expected_build = expected_build
        self.enable_writes = enable_writes
        self.audit_path = audit_path
        self.catalog = ValueCatalog(values_path if values_path is not None else default_values_path())
        self.records = {}
        self.body_values = {}
        self.college_catalog = None
        self.college_labels = {}
        self.body_snapshots = {}
        self.team_snapshots = {}
        self.team_ownership = None
        self.identity = None
        self.plans = {}
        self.live_enabled = False
        self.undo_stack, self.redo_stack = [], []
        self.captures = {}

    def configure(self, settings):
        self.memory = WindowsMemory(settings['game_path'])
        self.expected_build = settings['verified_build']
        self.enable_writes = settings['enable_writes']
        self.invalidate()

    def invalidate(self):
        self.records, self.identity, self.plans = {}, None, {}
        self.body_values = {}
        self.college_catalog = None
        self.college_labels = {}
        self.body_snapshots = {}
        self.team_snapshots = {}
        self.team_ownership = None
        self.live_enabled = False
        self.undo_stack, self.redo_stack = [], []
        self.captures = {}

    def capture_change(self, document):
        player_id = document.get('player_id')
        if not isinstance(player_id, str) or not self.identity or player_id not in self.records:
            raise RosterError('Select a player from the loaded game roster.')
        label = document.get('label')
        if not isinstance(label, str) or not label.strip() or len(label) > 160:
            raise RosterError('Describe the single field being changed, such as Hotzones / Close Left.')
        with self.memory.open() as process:
            if self._status(process) != self.identity:
                raise RosterError('Game connection changed. Reload its roster.')
            address = self.identity['base'] + int(player_id.split('-')[1]) * self.profile.stride
            record = process.read(address, self.profile.stride)
            self._check_player_identity(record, self.records[player_id])
        capture_id = secrets.token_hex(16)
        self.captures = {capture_id: {'player_id': player_id, 'label': label.strip(),
                                    'created': time.monotonic(), 'status': self.identity.copy(), 'before': record.hex()}}
        return {'capture_id': capture_id, 'label': label.strip(), 'build': self.identity['build']}

    def compare_change(self, document):
        capture_id = document.get('capture_id')
        if not isinstance(capture_id, str):
            raise RosterError('A before-snapshot capture ID is required.')
        capture = self.captures.get(capture_id)
        if not capture or time.monotonic() - capture['created'] > 600:
            raise RosterError('Capture expired. Take another before snapshot.')
        with self.memory.open() as process:
            if self._status(process) != capture['status']:
                raise RosterError('Game connection changed during capture.')
            address = self.identity['base'] + int(capture['player_id'].split('-')[1]) * self.profile.stride
            after = process.read(address, self.profile.stride)
        before = bytes.fromhex(capture['before'])
        self._check_player_identity(after, before)
        changed = []
        for offset, (a, b) in enumerate(zip(before, after)):
            if a != b:
                changed.append({'offset': hex(offset), 'before': a, 'after': b,
                                'changed_bits': [bit for bit in range(8) if (a ^ b) & (1 << bit)],
                                'suspected_cache': 0xE8 <= offset <= 0xEF or 0x1AA <= offset <= 0x1BA})
        if not changed:
            raise RosterError('No player-record change detected. Make one change in 2K and commit it to the roster, then compare again.')
        known = [{'category': field.category, 'field': field.name, 'before': field.decode(before), 'after': field.decode(after)}
                 for field in self.profile.fields.values() if field.decode(before) != field.decode(after)]
        report = {**capture, 'after': after.hex(), 'changed_bytes': changed, 'known_fields': known,
                  'note': 'Observation only. Changed locations are candidates, not automatically enabled offsets.'}
        self.audit_path.parent.joinpath('mapping_captures').mkdir(parents=True, exist_ok=True)
        path = self.audit_path.parent / 'mapping_captures' / f'{document["capture_id"]}.json'
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        return {'report': report, 'path': str(path.resolve())}

    def _check_player_identity(self, current, snapshot):
        for offset in [number(self.profile.base['Offset Last Name']), number(self.profile.base['Offset First Name'])]:
            if current[offset:offset + 40] != snapshot[offset:offset + 40]:
                raise RosterError('Player record changed. Reload the game roster.')

    def _validate_roster_table(self, process, address, count):
        """Check that a candidate table contains the profile's expected names."""
        if not 0x10000 <= address <= 0x7FFFFFFFFFFF or not 100 <= count <= 10000:
            return False
        stride = self.profile.stride
        first = number(self.profile.base['Offset First Name'])
        last = number(self.profile.base['Offset Last Name'])
        sample_count = min(count, 128)
        try:
            sample = process.read(address, sample_count * stride)
        except RosterError:
            return False
        valid, unique = 0, set()
        for index in range(sample_count):
            record = sample[index * stride:(index + 1) * stride]
            names = []
            for offset, width in ((first, 24), (last, 20)):
                raw = record[offset:offset + width * 2]
                try:
                    value = raw.decode('utf-16-le').split('\0', 1)[0].strip()
                except UnicodeDecodeError:
                    value = ''
                if not value or len(value) > width or not any(char.isalpha() for char in value):
                    break
                if any(not char.isprintable() for char in value):
                    break
                names.append(value)
            if len(names) == 2:
                valid += 1
                unique.add(tuple(names))
        return valid >= min(100, sample_count) and len(unique) >= min(80, sample_count)

    def _community_roster_candidate(self, process):
        """Try a documented community pointer path, then validate before use.

        The source editor verifies a different executable build. This path is
        therefore never trusted on its own and is only attempted for the same
        player stride/name layout. No value from this probe enables writes.
        """
        if (self.profile.stride != 0x4F8 or
                number(self.profile.base['Offset First Name']) != 0x28 or
                number(self.profile.base['Offset Last Name']) != 0):
            return None
        try:
            root = struct.unpack('<Q', process.read(
                process.module_base + COMMUNITY_ROOT_RVA, 8))[0]
            if not 0x10000 <= root <= 0x7FFFFFFFFFFF:
                return None
            roster = struct.unpack('<Q', process.read(
                root + COMMUNITY_ROSTER_POINTER_OFFSET, 8))[0]
            if not 0x10000 <= roster <= 0x7FFFFFFFFFFF:
                return None
            count = struct.unpack('<I', process.read(
                roster + COMMUNITY_PLAYER_COUNT_OFFSET, 4))[0]
            table = struct.unpack('<Q', process.read(
                roster + COMMUNITY_PLAYER_TABLE_OFFSET, 8))[0]
        except (RosterError, OSError, struct.error):
            return None
        if self._validate_roster_table(process, table, count):
            return table, count
        return None

    def _observed_roster_candidate(self, process, validate_names=True):
        """Accept observed references only with exact build/layout and consensus."""
        offsets = OBSERVED_PLAYER_POINTERS.get(process.build.casefold())
        if (not offsets or self.profile.stride != 0x4F8 or
                number(self.profile.base['Offset First Name']) != 0x28 or
                number(self.profile.base['Offset Last Name']) != 0):
            return None
        try:
            pointers = [struct.unpack('<Q', process.read(process.module_base + offset, 8))[0]
                        for offset in offsets]
        except (RosterError, OSError, struct.error):
            return None
        if len(set(pointers)) != 1:
            return None
        table = pointers[0]
        # 128 is the validation sample size, not an inferred roster count.
        if (0x10000 <= table <= 0x7FFFFFFFFFFF and
                (not validate_names or self._validate_roster_table(process, table, 128))):
            return table
        return None

    def _name_state_fields(self, build):
        if build.casefold() != '6ad2e48c:36532000':
            return {}
        fields = {}
        for name, layout in NAME_STATE_LAYOUTS.items():
            field = self.profile.fields.get(('advanced', name))
            if field is None or (field.offset, field.bits, field.shift, field.kind) != layout:
                raise RosterError('Name companion fields do not match the observed build layout.')
            # These internal companions never become public writable fields.
            fields[name] = replace(field, writable=True)
        return fields

    def _status(self, process, name_masks=()):
        if not process.alive():
            raise RosterError('NBA 2K27 closed. Start the game and reconnect.')
        pointer = struct.unpack('<Q', process.read(process.module_base + self.profile.pointer_offset, 8))[0]
        for offset in self.profile.base.get('Player Offset Chain', []):
            if pointer == 0:
                break
            pointer = struct.unpack('<Q', process.read(pointer + number(offset), 8))[0]
        array_count = None
        array_source = 'profile'
        roster_identity = None
        if pointer == 0:
            # Only a transaction that already pinned a fully validated roster
            # may mask its own changed name bytes. Pointer consensus remains
            # mandatory even if an intermediate rename affects name validation.
            observed = self._observed_roster_candidate(process, validate_names=not name_masks)
            if observed:
                pointer = observed
                array_source = 'validated build references'
                sample = process.read(pointer, 128 * self.profile.stride)
                name_sample = bytearray(b''.join(
                    sample[index * self.profile.stride:index * self.profile.stride + 88]
                    for index in range(128)))
                for index, offset, size in name_masks:
                    if not (0 <= index < 128 and 0 <= offset < 88 and 0 < size <= 88-offset):
                        raise RosterError('Invalid internal name transaction mask.')
                    start = index * 88 + offset
                    name_sample[start:start+size] = bytes(size)
                roster_identity = hashlib.sha256(name_sample).hexdigest()
        if pointer == 0:
            candidate = self._community_roster_candidate(process)
            if candidate:
                pointer, array_count = candidate
                array_source = 'validated community path'
        if pointer and not 0x10000 <= pointer <= 0x7FFFFFFFFFFF:
            raise RosterError('Player array pointer is invalid for this build. Check the offset profile.')
        body_model = None
        if pointer and self.profile.stride == 0x4F8 and array_source in ('profile', 'validated build references'):
            try:
                body_model = read_body_model(process)
            except (RosterError, OSError):
                pass
        college_valid = validate_college_catalog(process, self.profile, self.college_catalog, pointer)
        verified_fields = None
        if array_source == 'validated build references':
            allowed_fields = set()
            try:
                name_state_valid = bool(self._name_state_fields(process.build))
            except RosterError:
                name_state_valid = False
            for key, layout in OBSERVED_BUILD_WRITABLE_FIELDS.get(process.build.casefold(), {}).items():
                field = self.profile.fields.get(key)
                if key in (('vitals', 'First Name'), ('vitals', 'Last Name')) and not name_state_valid:
                    continue
                if (field and field.writable and (field.offset, field.bits, field.shift, field.kind) == layout and
                        (not field.verified_build or field.verified_build.casefold() == process.build.casefold())):
                    allowed_fields.add(key)
            for category, expected_layout in APPROVED_BUILD_SECTION_LAYOUTS.get(process.build.casefold(), {}).items():
                fields = [field for field in self.profile.fields.values()
                          if field.category == category and field.writable]
                layouts = sorted((field.name, field.offset, field.bits, field.shift, field.kind) for field in fields)
                actual_layout = hashlib.sha256(json.dumps(layouts, separators=(',', ':')).encode()).hexdigest()
                if actual_layout == expected_layout:
                    allowed_fields.update((field.category, field.name) for field in fields)
            if body_model:
                allowed_fields.update(('vitals', name) for name in ('Height', 'Wingspan', 'Shoulder Width', 'Neck Length', 'Trunk Length'))
            allowed_fields.update(verified_setter_fields(process, self.profile))
            if college_valid:
                allowed_fields.add(COLLEGE_FIELD)
            verified_fields = [list(key) for key in sorted(allowed_fields)]
        return {'connected': True, 'backend': 'native', 'process': process.path.name,
                'path': str(process.path), 'pid': process.pid, 'created': process.created,
                'build': process.build, 'module_base': process.module_base, 'base': pointer,
                'array_count': array_count, 'array_source': array_source,
                'roster_identity': roster_identity,
                'college_writable': college_valid,
                'college_catalog_identity': self.college_catalog['sha256'] if college_valid else None,
                'body_writable': body_model is not None,
                'body_model_identity': body_model['fingerprint'] if body_model else None,
                'writable_fields': verified_fields,
                'writes_enabled': bool(pointer and (array_source == 'profile' or
                                       bool(verified_fields)) and
                                       self.enable_writes and self.expected_build and
                                       process.build.casefold() == self.expected_build.casefold())}

    def status(self):
        with self.memory.open() as process:
            return self._status(process)

    def diagnostics(self):
        """Collect a read-only report explaining each known roster lookup step."""
        with self.memory.open() as process:
            report = {
                'process': process.path.name,
                'pid': process.pid,
                'build': process.build,
                'module_base': f'0x{process.module_base:X}',
                'profile': {
                    'pointer_offset': f'0x{self.profile.pointer_offset:X}',
                    'stride': f'0x{self.profile.stride:X}',
                    'first_name_offset': f'0x{number(self.profile.base["Offset First Name"]):X}',
                    'last_name_offset': f'0x{number(self.profile.base["Offset Last Name"]):X}',
                    'pointer_chain': self.profile.base.get('Player Offset Chain', []),
                },
                'probes': {},
                'read_only': True,
            }

            def probe(label, address, size, fmt):
                try:
                    value = struct.unpack(fmt, process.read(address, size))[0]
                    report['probes'][label] = {
                        'address': f'0x{address:X}',
                        'value': f'0x{value:X}' if fmt != '<I' else value,
                    }
                    return value
                except (RosterError, OSError, struct.error) as error:
                    report['probes'][label] = {
                        'address': f'0x{address:X}', 'error': str(error)[:240],
                    }
                    return None

            def pointer_probe(label, address):
                value = probe(label, address, 8, '<Q')
                if value is not None:
                    valid = 0x10000 <= value <= 0x7FFFFFFFFFFF
                    report['probes'][label]['valid_pointer'] = valid
                    if not valid:
                        report['probes'][label]['reason'] = (
                            'Null pointer; lookup stops here.' if value == 0 else
                            'Outside the supported user-space pointer range; lookup stops here.')
                        return None
                return value

            address = process.module_base + self.profile.pointer_offset
            pointer = pointer_probe('profile_pointer_slot', address)
            if pointer:
                for index, offset in enumerate(self.profile.base.get('Player Offset Chain', [])):
                    pointer = pointer_probe(f'profile_chain_{index}', pointer + number(offset))
                    if not pointer:
                        break

            observed_offsets = OBSERVED_PLAYER_POINTERS.get(process.build.casefold(), ())
            if observed_offsets:
                observed = [pointer_probe(f'observed_build_pointer_{index}', process.module_base + offset)
                            for index, offset in enumerate(observed_offsets)]
                consensus = all(observed) and len(set(observed)) == 1
                report['observed_build_lookup'] = {
                    'references_agree': bool(consensus),
                    'validated': bool(consensus and self._observed_roster_candidate(process)),
                    'read_only': True,
                }

            root_address = process.module_base + COMMUNITY_ROOT_RVA
            root = pointer_probe('community_root_pointer', root_address)
            roster = pointer_probe('community_roster_pointer', root + COMMUNITY_ROSTER_POINTER_OFFSET) if root else None
            count = probe('community_player_count', roster + COMMUNITY_PLAYER_COUNT_OFFSET, 4, '<I') if roster else None
            table = pointer_probe('community_player_table', roster + COMMUNITY_PLAYER_TABLE_OFFSET) if roster else None
            if table and count and 100 <= count <= 10000:
                valid = self._validate_roster_table(process, table, count)
                report['probes']['community_player_table']['validated'] = valid
                report['probes']['community_player_table']['count'] = count
                if valid:
                    sample_count = min(count, 5)
                    sample = process.read(table, sample_count * self.profile.stride)
                    first = number(self.profile.base['Offset First Name'])
                    last = number(self.profile.base['Offset Last Name'])
                    report['sample_players'] = []
                    for index in range(sample_count):
                        row = sample[index * self.profile.stride:(index + 1) * self.profile.stride]
                        first_name = row[first:first + 48].decode('utf-16-le').split('\0', 1)[0]
                        last_name = row[last:last + 40].decode('utf-16-le').split('\0', 1)[0]
                        report['sample_players'].append(f'{first_name} {last_name}'.strip())
            return report

    def load(self):
        self.invalidate()
        players, records, body_values, body_snapshots = [], {}, {}, {}
        team_snapshots = {}
        team_ownership = None
        stride = self.profile.stride
        first = number(self.profile.base['Offset First Name'])
        last = number(self.profile.base['Offset Last Name'])
        with self.memory.open() as process:
            status = self._status(process)
            if not status['base']:
                raise RosterError(
                    f'No player array was found at profile offset 0x{self.profile.pointer_offset:X} '
                    f'for game build {status["build"]}. Confirm a roster is open in NBA 2K27. '
                    'Trace also checked the read-only fallback paths, but could not validate them. '
                    'The player layout or game-build offsets may have changed.'
                )
            for index in range(min(status.get('array_count') or 6000, 6000)):
                address = status['base'] + index * stride
                if not any(process.read(address + last, 2)):
                    break
                record = process.read(address, stride)
                def name_at(offset, characters):
                    value = record[offset:offset + characters * 2].decode('utf-16-le').split('\0', 1)[0]
                    if any(ord(char) < 32 for char in value):
                        raise RosterError('Invalid player names in memory. Check the offset profile.')
                    return value
                name = f'{name_at(first, 24)} {name_at(last, 20)}'.strip()
                identity = f'game-{index}'
                players.append({'player_id': identity, 'name': name,
                                'metadata': {'game_index': index, **player_summary(self.profile, record, status['build'])},
                                **self.profile.decode(record, status['build'])})
                body_values[identity] = read_body(process, self.profile, record, address)
                if body_values[identity]:
                    try:
                        body_snapshots[identity] = snapshot_body(process, self.profile, record, address)
                        body_values[identity] = decode_body(body_snapshots[identity]['data'])
                    except (RosterError, OSError):
                        body_values[identity] = {}
                players[-1]['vitals'].update(body_values[identity])
                players[-1]['metadata'].update(read_college(process, self.profile, record, address))
                records[identity] = record
                if index % 100 == 0 and self._status(process) != status:
                    raise RosterError('Game connection changed during loading. Try again.')
            if not players:
                raise RosterError('No players found. Load a roster in the game and check the profile.')
            teams = read_teams(process, self.profile, status['base'], players, records)
            populate_team_sections(process, self.profile, status['base'], players, records, teams, team_snapshots)
            model = read_body_model(process) if status.get('body_writable') else None
            body_owners = {}
            for identity, raw in records.items():
                child = int.from_bytes(raw[BODY_POINTER:BODY_POINTER+8], 'little')
                body_owners.setdefault(child, []).append(identity)
            for player in players:
                snapshot = body_snapshots.get(player['player_id'])
                editable = bool(model and snapshot and body_owners.get(snapshot['pointer']) == [player['player_id']])
                if editable:
                    try:
                        editable = body_span(snapshot['data'], model) == (int.from_bytes(snapshot['data'][2:4], 'little') & 0x7FFF)
                    except RosterError:
                        editable = False
                player['metadata']['body_editable'] = editable
            if self._status(process) != status:
                raise RosterError('Game connection changed during loading. Try again.')
            team_ownership = enable_coaching(process, self.profile, status['base'], records, team_snapshots, teams)
            self.college_catalog = build_college_catalog(process, self.profile, records, status['base'])
            for player in players:
                label = player['metadata'].get('college_from')
                if label:
                    player['vitals']['College / From'] = label
                    pointer = int.from_bytes(records[player['player_id']][0xB0:0xB8], 'little')
                    self.college_labels[pointer] = label
            final_status = self._status(process)
            expected_status = {**status, 'college_writable': final_status['college_writable'],
                               'college_catalog_identity': final_status['college_catalog_identity']}
            if status['writable_fields'] is not None:
                expected_fields = {tuple(k) for k in status['writable_fields']}
                if final_status['college_writable']:
                    expected_fields.add(COLLEGE_FIELD)
                expected_status['writable_fields'] = [list(k) for k in sorted(expected_fields)]
            if final_status != expected_status:
                self.invalidate()
                raise RosterError('Game connection changed while resolving the college catalog.')
            status = final_status
        roster = validate_roster({'name': 'NBA 2K27 roster', 'players': players, 'teams': teams})
        self.records, self.identity = records, status
        self.body_values = body_values
        self.body_snapshots = body_snapshots
        self.team_snapshots, self.team_ownership = team_snapshots, team_ownership
        return {'roster': roster, 'status': status, 'field_values': self.field_values()}

    def field_values(self):
        if not self.identity:
            return {}
        build = self.identity['build'].upper()
        result = {category: {field: {label: entry['value'] for label, entry in values.items()}
                           for field, values in fields.items()}
                for category, fields in self.catalog.document['builds'].get(build, {}).items()}
        if self.college_catalog:
            result.setdefault('vitals', {})['College / From'] = {name: name for name in self.college_catalog['choices']}
        return result

    def _public_changes(self, changes):
        labels = self.college_catalog['names'] if self.college_catalog else self.college_labels
        return [{**change, **({k: labels.get(change[k], 'Unknown college') for k in ('old', 'value') if k in change}
                  if (change.get('category'), change.get('field')) == COLLEGE_FIELD else {})} for change in changes]

    def normalize_value(self, category, name, value):
        if (category, name) == COLLEGE_FIELD:
            if not self.college_catalog or not self.identity or not self.identity.get('college_writable') or not isinstance(value, str):
                raise RosterError('College / From: choose a named entry from the loaded game catalog.')
            matches = [ptr for label, ptr in self.college_catalog['choices'].items() if label.casefold() == value.strip().casefold()]
            if len(matches) != 1:
                raise RosterError('College / From: the name is absent or ambiguous in the loaded catalog.')
            return matches[0]
        field = self.profile.fields.get((category, name))
        if isinstance(value, str) and field and field.kind != 'utf16':
            if not self.identity:
                raise RosterError('Load a game roster to resolve build-specific named values.')
            return self.catalog.resolve(self.identity['build'], category, name, value)
        return value

    def learn_value(self, document):
        player_id, category, name = (document.get(key) for key in ('player_id', 'category', 'field'))
        if not all(isinstance(value, str) for value in (player_id, category, name)):
            raise RosterError('A loaded player, category, and field are required.')
        field = self.profile.fields.get((category, name))
        if not self.identity or player_id not in self.records or not field or not field.writable or field.kind != 'bits':
            raise RosterError('Select a mapped numeric game field on a loaded player.')
        with self.memory.open() as process:
            if self._status(process) != self.identity:
                raise RosterError('Game connection changed. Reload the roster before learning names.')
            address = self.identity['base'] + int(player_id.split('-')[1]) * self.profile.stride
            current = process.read(address, self.profile.stride)
            snapshot = self.records[player_id]
            for offset, size in [(number(self.profile.base['Offset Last Name']), 40),
                                 (number(self.profile.base['Offset First Name']), 40)]:
                if current[offset:offset+size] != snapshot[offset:offset+size]:
                    raise RosterError('Player identity changed. Reload before learning a name.')
            value = field.decode(current)
        # Refresh only the learned field, retaining conflict checks for other values.
        refreshed = bytearray(snapshot)
        field.encode(refreshed, value)
        result = self.catalog.learn(self.identity['build'], category, name, document.get('label'), value, player_id)
        self.records[player_id] = bytes(refreshed)
        self.plans = {}
        return {'mapping': result, 'field_values': self.field_values(),
                'changes': [{'player_id': player_id, 'category': category, 'field': name, 'value': value}]}

    def preview(self, document):
        if not self.identity:
            raise RosterError('Load the game roster before planning changes.')
        if self.status() != self.identity:
            raise RosterError('Game connection changed. Reload its roster.')
        document = self.profile.canonical_document(document)
        changes, warnings, patches = [], [], []
        for player in document['players']:
            before = self.records.get(player['player_id'])
            if before is None:
                warnings.append(f"{player['name']}: no game record; merge TRC into the loaded game roster first.")
                continue
            body_requested = {name: value for name, value in player.get('vitals', {}).items()
                              if is_body_field('vitals', name) and value != self.body_values.get(player['player_id'], {}).get(name)}
            for name in list(player.get('vitals', {})):
                if is_body_field('vitals', name):
                    player['vitals'].pop(name)
            if player.get('vitals', {}).get('College / From') == self.college_labels.get(int.from_bytes(before[0xB0:0xB8], 'little')):
                player['vitals'].pop('College / From', None)
            after, edits, skipped = self.profile.patch(before, player, self.normalize_value, self.identity['build'])
            if body_requested:
                try:
                    snapshot = self.body_snapshots.get(player['player_id'])
                    if not self.identity.get('body_writable') or not snapshot:
                        raise RosterError('no enabled memory mapping for this loaded Body structure')
                    with self.memory.open() as process:
                        model = read_body_model(process)
                    if model['fingerprint'] != self.identity.get('body_model_identity'):
                        raise RosterError('Body model changed; reload before previewing')
                    body_after = encode_body(snapshot['data'], body_requested, model)
                    old_values, new_values = decode_body(snapshot['data']), decode_body(body_after)
                    edits.extend({'category': 'vitals', 'field': name, 'old': old_values[name], 'value': new_values[name]}
                                 for name in body_requested if old_values[name] != new_values[name])
                except RosterError as error:
                    skipped.extend(f'{name}: {error}; skipped.' for name in body_requested)
            allowed = self.identity.get('writable_fields')
            if allowed is not None:
                allowed = {tuple(key) for key in allowed}
                for edit in edits:
                    if (edit['category'], edit['field']) not in allowed:
                        skipped.append(f"{edit['field']}: read only; not enabled for this build.")
                edits = [edit for edit in edits if (edit['category'], edit['field']) in allowed]
            changes.extend({'name': player['name'], 'player_id': player['player_id'], **edit} for edit in edits)
            warnings.extend(f"{player['name']}: {warning}" for warning in skipped)
            if before != after:
                patches.append({'player_id': player['player_id'], 'index': int(player['player_id'].split('-')[1]),
                                'before': before.hex(), 'after': after.hex()})
        for team in document['teams']:
            section = team.get('coaching', {})
            if not isinstance(section, dict) or not isinstance(section.get('values', {}), dict):
                raise RosterError('Team coaching values must be an object.')
            saved = self.team_snapshots.get(team['team_id'])
            for name, value in section.get('values', {}).items():
                old = saved['data'][COACH_FIELDS[name]] if saved and name in COACH_FIELDS else None
                if value == old:
                    continue
                try:
                    coaching_value(name, value)
                    if not saved or name not in saved.get('writable_fields', []):
                        raise RosterError('no independently owned, verified coach mapping')
                    changes.append({'team_id': team['team_id'], 'name': saved['name'], 'category': 'coaching',
                                    'field': name, 'old': old, 'value': value})
                except RosterError as error:
                    warnings.append(f"{team['name']} / {name}: {error}; skipped.")
        requested_coaching = [c for c in changes if 'team_id' in c]
        if requested_coaching:
            with self.memory.open() as process:
                if self._status(process) != self.identity:
                    raise RosterError('Game connection changed; reload the roster.')
                prepare_coaching(process, self.profile, self.team_ownership, self.team_snapshots, requested_coaching)
        if changes:
            warnings.append('Full display names, team assignments, metadata, unmapped hotzones, and raw Advanced fields remain local. First/last names and promoted mapped fields can be edited in their category tabs.')
        plan_id = secrets.token_urlsafe(24)
        self.plans = {plan_id: {'created': time.monotonic(), 'patches': patches, 'changes': changes}}
        return {'plan_id': plan_id, 'changes': self._public_changes(changes), 'warnings': warnings,
                'writes_enabled': self.identity['writes_enabled']}

    def _log(self, plan_id, status, plan, outcome):
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open('a', encoding='utf-8') as file:
            file.write(json.dumps({'time': time.time(), 'plan_id': plan_id, 'status': status,
                                   'outcome': outcome, **plan}) + '\n')
            file.flush()
            os.fsync(file.fileno())

    def history_state(self):
        return {'live_enabled': self.live_enabled, 'undo_count': len(self.undo_stack),
                'redo_count': len(self.redo_stack)}

    def set_live(self, enabled):
        if type(enabled) is not bool:
            raise RosterError('Live editing must be true or false.')
        if enabled:
            if not self.identity:
                raise RosterError('Load the game roster before starting live editing.')
            if (self.identity.get('array_source') != 'profile' and
                    not self.identity.get('writable_fields')):
                raise RosterError('Trace found the roster using a recovery path. Reading is available, but live editing needs a verified profile for this game build.')
            with self.memory.open(writable=True) as process:
                status = self._status(process)
                if status != self.identity:
                    raise RosterError('Game connection changed. Reload its roster.')
                # Explicitly starting live editing authorizes writes for this session/build.
                self.expected_build, self.enable_writes = status['build'], True
                self.identity = self._status(process)
            self.plans = {}
        self.live_enabled = enabled
        return {'status': self.status(), **self.history_state()}

    def edit_team(self, document):
        if not self.live_enabled:
            raise RosterError('Start live editing before changing game values.')
        identity, category, name = (document.get(key) for key in ('team_id', 'category', 'field'))
        if 'player_id' in document or not all(isinstance(v, str) for v in (identity, category, name)) or category != 'coaching':
            raise RosterError('A mapped team, coaching category and field are required.')
        saved = self.team_snapshots.get(identity)
        if not saved or name not in saved.get('writable_fields', []):
            raise RosterError('This coaching field is read only for the loaded team.')
        value = coaching_value(name, document.get('value'))
        old = saved['data'][COACH_FIELDS[name]]
        if 'expected' in document and (type(document['expected']) is not int or document['expected'] != old):
            raise RosterError('Another edit changed this coaching field; reload the roster.')
        if value == old:
            return {'changes': [], **self.history_state()}
        changes = [{'team_id': identity, 'category': 'coaching', 'field': name, 'old': old, 'value': value}]
        self._write_changes(changes, 'live')
        self.undo_stack.append(changes)
        self.redo_stack = []
        return {'changes': changes, **self.history_state()}

    def edit(self, document):
        if 'team_id' in document:
            return self.edit_team(document)
        if not self.live_enabled:
            raise RosterError('Start live editing before changing game values.')
        player_id, category, name = (document.get(key) for key in ('player_id', 'category', 'field'))
        if not all(isinstance(value, str) for value in (player_id, category, name)):
            raise RosterError('A player, category, and field are required.')
        body_field = is_body_field(category, name)
        field = self.profile.fields.get((category, name))
        if not body_field and (not field or not field.writable):
            raise RosterError('This field is local only; no enabled game mapping.')
        snapshot = self.records.get(player_id)
        if snapshot is None:
            raise RosterError('This player is not mapped to the loaded game roster.')
        if body_field:
            body_snapshot = self.body_snapshots.get(player_id)
            if not self.identity.get('body_writable') or not body_snapshot:
                raise RosterError('Body editing requires a verified loaded Body structure. Reload the roster.')
            old = decode_body(body_snapshot['data']).get(name)
        else:
            old = field.decode(snapshot)
        if 'expected' in document and (self.normalize_value(category, name, document['expected']) if (category, name) == COLLEGE_FIELD else document['expected']) != old:
            raise RosterError('Another edit changed this field. Reload the game roster.')
        value = self.normalize_value(category, name, document.get('value'))
        if not body_field:
            check = bytearray(snapshot)
            field.encode(check, value)
            value = field.decode(check)
        if value == old:
            return {'changes': [], **self.history_state()}
        changes = [{'player_id': player_id, 'category': category, 'field': name, 'old': old, 'value': value}]
        self._write_changes(changes, 'live')
        self.undo_stack.append(changes)
        self.redo_stack = []
        return {'changes': self._public_changes(changes), **self.history_state()}

    def undo(self, redo=False):
        stack = self.redo_stack if redo else self.undo_stack
        if not stack:
            raise RosterError('No game edit to redo.' if redo else 'No game edit to undo.')
        original = stack[-1]
        changes = [{**change, **({'restore_body': change['body_after']} if 'body_after' in change else {})}
                   for change in original] if redo else [{**change, 'old': change['value'], 'value': change['old'],
                                          **({'restore_bytes': change['raw_before']} if 'raw_before' in change else {}),
                                          **({'restore_body': change['body_before']} if 'body_before' in change else {}),
                                          **({'restore_name_state': change['name_state_before']} if 'name_state_before' in change else {})}
                                         for change in reversed(original)]
        self._write_changes(changes, 'redo' if redo else 'undo')
        stack.pop()
        (self.undo_stack if redo else self.redo_stack).append(original)
        return {'changes': self._public_changes(changes), **self.history_state()}

    def apply(self, plan_id):
        plan = self.plans.pop(plan_id, None)
        if plan is None or time.monotonic() - plan['created'] > 300:
            raise RosterError('Plan expired. Preview game changes again.')
        if not plan['changes']:
            raise RosterError('No supported game changes to apply.')
        self._write_changes(plan['changes'], 'bulk', plan_id)
        self.undo_stack.append(plan['changes'])
        self.redo_stack = []
        return {'applied': len(plan['changes']), 'changes': self._public_changes(plan['changes']), **self.history_state()}

    def _write_changes(self, changes, kind, transaction_id=None):
        if not self.identity or not self.identity['writes_enabled']:
            raise RosterError('Writes require enabled game editing. Start live editing or enable writes in Connection details.')
        grouped = {}
        team_changes = []
        allowed = self.identity.get('writable_fields')
        for change in changes:
            if 'team_id' in change:
                team_changes.append(change)
                continue
            if allowed is not None and [change['category'], change['field']] not in allowed:
                raise RosterError('This field is read only; it has not been verified or approved for this game build.')
            player_id = change['player_id']
            if player_id not in self.records:
                raise RosterError('Unknown game player record.')
            grouped.setdefault(player_id, []).append(change)
        with self.memory.open(writable=True) as process:
            status = self._status(process)
            if status != self.identity or not status['writes_enabled']:
                raise RosterError('Game connection changed. Reload the game roster before applying.')
            if any((c['category'], c['field']) == COLLEGE_FIELD for c in changes) and not status.get('college_writable'):
                raise RosterError('College / From catalog changed or is not validated; reload the roster.')
            requested_setter_fields = {(c['category'], c['field']) for c in changes} & SETTER_FIELDS.keys()
            if requested_setter_fields and requested_setter_fields - verified_setter_fields(process, self.profile):
                raise RosterError('Named setter code, field layout, or accepted values changed; reload a supported build.')
            patches, refreshed, edits, refreshed_body, body_guards = [], {}, [], {}, []
            model = None
            owners = {}
            if any(is_body_field(c['category'], c['field']) for c in changes):
                if not status.get('body_writable'):
                    raise RosterError('The loaded Body model is not verified for editing.')
                model = read_body_model(process)
                if model['fingerprint'] != status.get('body_model_identity'):
                    raise RosterError('The Body model changed. Reload the game roster.')
                for identity in self.records:
                    parent = status['base'] + int(identity.split('-')[1])*self.profile.stride
                    child = int.from_bytes(process.read(parent+BODY_POINTER, 8), 'little')
                    owners.setdefault(child, []).append(identity)

            def append_edits(address, before, after):
                offset = 0
                while offset < len(before):
                    if before[offset] == after[offset]:
                        offset += 1
                        continue
                    start = offset
                    while offset < len(before) and before[offset] != after[offset]:
                        offset += 1
                    edits.append((address+start, before[start:offset], after[start:offset]))

            coaching_regions, coaching_targets = [], {}
            if team_changes:
                coaching_regions, coaching_targets = prepare_coaching(process, self.profile, self.team_ownership,
                                                                      self.team_snapshots, team_changes)
                for region in coaching_regions:
                    append_edits(region['address'], region['before'], region['after'])
                    patches.append({**{k: v for k, v in region.items() if k not in ('before', 'after')},
                                    'region': 'coach', 'before': region['before'].hex(), 'after': region['after'].hex(),
                                    'ownership_fingerprint': self.team_ownership['fingerprint']})
            for player_id, fields in grouped.items():
                address = status['base'] + int(player_id.split('-')[1]) * self.profile.stride
                before = process.read(address, self.profile.stride)
                snapshot = self.records[player_id]
                # Guard player identity and requested values, not unrelated game caches.
                for offset, size in [(number(self.profile.base['Offset Last Name']), 40),
                                     (number(self.profile.base['Offset First Name']), 48)]:
                    if before[offset:offset + size] != snapshot[offset:offset + size]:
                        raise RosterError('Player record changed. Reload the game roster.')
                after = bytearray(before)
                body_fields = [c for c in fields if is_body_field(c['category'], c['field'])]
                if body_fields:
                    saved = self.body_snapshots.get(player_id)
                    current = snapshot_body(process, self.profile, before, address)
                    pointer, body_before = current['pointer'], current['data']
                    if not saved or current != saved:
                        raise RosterError('Body values or pointer changed. Reload the game roster.')
                    array_end = status['base'] + (max(int(i.split('-')[1]) for i in self.records)+1)*self.profile.stride
                    if (status['base']-BODY_SIZE < pointer < array_end or owners.get(pointer) != [player_id]):
                        raise RosterError('Body data is shared or overlaps player records; editing is disabled.')
                    old_values = decode_body(body_before)
                    for change in body_fields:
                        if old_values.get(change['field']) != change['old']:
                            raise RosterError('A Body value changed. Reload before applying.')
                    restores = {c['restore_body'] for c in body_fields if 'restore_body' in c}
                    if restores:
                        if len(restores) != 1 or any('restore_body' not in c for c in body_fields):
                            raise RosterError('Invalid internal Body recovery data.')
                        body_after = bytes.fromhex(restores.pop())
                        if (len(body_after) != BODY_SIZE or
                                body_span(body_after, model) != (int.from_bytes(body_after[2:4], 'little') & 0x7FFF)):
                            raise RosterError('Invalid Body recovery measurements.')
                        # Recovery may restore only the requested fields and
                        # the dependent span, including exact original floats.
                        allowed = {2, 3}
                        for change in body_fields:
                            if change['field'] == 'Height':
                                allowed.update((0, 1))
                            else:
                                offset = BODY_SCALES[change['field']][0]
                                allowed.update(range(offset, offset+4))
                        if (any(a != b and i not in allowed for i, (a, b) in enumerate(zip(body_before, body_after))) or
                                ((body_before[1] ^ body_after[1]) & 0x80) or ((body_before[3] ^ body_after[3]) & 0x80)):
                            raise RosterError('Body recovery would overwrite unrelated data.')
                    else:
                        body_after = encode_body(body_before, {c['field']: c['value'] for c in body_fields}, model)
                    new_values = decode_body(body_after)
                    for change in body_fields:
                        if new_values.get(change['field']) != change['value']:
                            raise RosterError('Body recovery value does not match the requested change.')
                        change.setdefault('body_before', body_before.hex())
                        change.setdefault('body_after', body_after.hex())
                    body_guards.append((address+BODY_POINTER, pointer))
                    append_edits(pointer, body_before, body_after)
                    patches.append({'player_id': player_id, 'region': 'body', 'address': pointer,
                                    'pointer_offset': BODY_POINTER, 'before': body_before.hex(), 'after': body_after.hex()})
                    refreshed_body[player_id] = {'pointer': pointer, 'data': body_after}
                for change in fields:
                    if is_body_field(change['category'], change['field']):
                        continue
                    field = self.profile.fields[change['category'], change['field']]
                    if (change['category'], change['field']) == COLLEGE_FIELD and (change['old'] not in self.college_catalog['names'] or change['value'] not in self.college_catalog['names']):
                        raise RosterError('College / From: reference is outside the validated catalog.')
                    if field.verified_build and status['build'].casefold() != field.verified_build.casefold():
                        raise RosterError('This field is not mapped for the running game build.')
                    if field.allowed_values is not None and field.decode(before) not in field.allowed_values:
                        raise RosterError('The current field value is not recognized; validate it before editing.')
                    if change['category'] == 'vitals' and change['field'] in ('Injury 1 Duration Days', 'Injury 2 Duration Days'):
                        slot = 1 if change['field'] == 'Injury 1 Duration Days' else 2
                        active_type = self.profile.fields['advanced', f'INJURY{slot}TYPE'].decode(before)
                        active_status = self.profile.fields['advanced', f'INJURY{slot}STATUS'].decode(before)
                        duration = field.decode(before)
                        if not 1 <= active_type <= 156 or active_status not in (1, 4) or not duration or change['value'] <= 0:
                            raise RosterError('Create or clear injuries inside NBA 2K27; Trace can adjust an existing active injury duration.')
                    if field.decode(before) != change['old']:
                        raise RosterError('Roster changed in an edited field; reload before applying.')
                    if field.kind == 'utf16':
                        change.setdefault('raw_before', before[field.offset:field.offset+field.size].hex())
                        state_fields = self._name_state_fields(status['build'])
                        if state_fields:
                            change.setdefault('name_state_before', {name: item.decode(after) for name, item in state_fields.items()})
                            if 'restore_name_state' in change:
                                restored_state = change['restore_name_state']
                                if not isinstance(restored_state, dict) or set(restored_state) != set(state_fields):
                                    raise RosterError('Invalid internal name state recovery data.')
                                for name, value in restored_state.items():
                                    state_fields[name].encode(after, value)
                            else:
                                flag = 'FIRSTNAMEVETTED' if change['field'] == 'First Name' else 'LASTNAMEVETTED'
                                state_fields[flag].encode(after, 1)
                                state_fields['FIRSTLASTNAMESID'].encode(after, 65535)
                    if 'restore_bytes' in change:
                        raw = bytes.fromhex(change['restore_bytes'])
                        if len(raw) != field.size or field.kind != 'utf16':
                            raise RosterError('Invalid internal name recovery data.')
                        after[field.offset:field.offset+field.size] = raw
                        if field.decode(after) != change['value']:
                            raise RosterError('Name recovery data does not match the requested value.')
                    else:
                        field.encode(after, change['value'])
                after = bytes(after)
                append_edits(address, before, after)
                patches.append({'player_id': player_id, 'before': before.hex(), 'after': after.hex()})
                refreshed[player_id] = after
            name_masks = []
            if status['array_source'] == 'validated build references':
                for address, old, new in edits:
                    index, offset = divmod(address-status['base'], self.profile.stride)
                    if 0 <= index < 128 and offset < 88:
                        name_masks.append((index, offset, min(len(new), 88-offset)))

            def transaction_status():
                if coaching_targets:
                    validate_coaching_context(process, self.profile, self.team_ownership, coaching_targets)
                if any(int.from_bytes(process.read(address, 8), 'little') != pointer for address, pointer in body_guards):
                    raise RosterError('Body pointer moved during the transaction.')
                return self._status(process, name_masks) if name_masks else self._status(process)

            guard_status = transaction_status() if name_masks else status
            if self._status(process) != status:
                raise RosterError('Player array moved. Reload the game roster.')
            transaction_id = transaction_id or secrets.token_urlsafe(24)
            plan = {'kind': kind, 'changes': changes, 'patches': patches}
            self._log(transaction_id, status, plan, 'started')
            attempted = []
            try:
                for address, old, new in edits:
                    if transaction_status() != guard_status:
                        raise RosterError('Game connection changed during the update.')
                    if process.read(address, len(old)) != old:
                        raise RosterError('A game value changed during the update.')
                    attempted.append((address, old, new))
                    process.write(address, new)
                    if process.read(address, len(new)) != new:
                        raise RosterError('Game memory verification failed.')
                for address, _, new in edits:
                    if process.read(address, len(new)) != new:
                        raise RosterError('A game value changed before verification finished.')
                for region in coaching_regions:
                    if process.read(region['address'], len(region['after'])) != region['after']:
                        raise RosterError('Coach data changed before verification finished.')
                for snapshot in refreshed_body.values():
                    if process.read(snapshot['pointer'], BODY_SIZE) != snapshot['data']:
                        raise RosterError('Body data changed before verification finished.')
                if transaction_status() != guard_status:
                    raise RosterError('Game connection changed before verification finished.')
                final_status = self._status(process) if name_masks else status
                if name_masks:
                    # Normal validation must accept the completed names too.
                    if ({k: v for k, v in final_status.items() if k != 'roster_identity'} !=
                            {k: v for k, v in status.items() if k != 'roster_identity'}):
                        raise RosterError('The renamed roster failed validation.')
                    if transaction_status() != guard_status:
                        raise RosterError('Game connection changed after name verification.')
                    for address, _, new in edits:
                        if process.read(address, len(new)) != new:
                            raise RosterError('A name value changed after verification.')
            except Exception as error:
                restored = True
                for address, old, _ in reversed(attempted):
                    try:
                        if transaction_status() != guard_status:
                            restored = False
                            break
                        process.write(address, old)
                        if process.read(address, len(old)) != old:
                            restored = False
                    except Exception:
                        restored = False
                self.invalidate()
                outcome = 'rolled-back' if restored else 'rollback-failed'
                self._log(transaction_id, status, plan, outcome)
                raise RosterError(f'Game update failed: {error} ({outcome}). Reload the game roster before continuing.') from error
            try:
                self._log(transaction_id, status, plan, 'applied')
            except OSError:
                self.invalidate()
                raise RosterError('Game values were applied, but the completion log could not be saved. Reload before continuing.')
        for region in coaching_regions:
            self.team_snapshots[region['team_id']]['data'] = region['after']
        self.records.update(refreshed)
        self.body_snapshots.update(refreshed_body)
        self.body_values.update({identity: decode_body(snapshot['data']) for identity, snapshot in refreshed_body.items()})
        self.identity = final_status
        self.plans = {}
