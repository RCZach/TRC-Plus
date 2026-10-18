"""Direct game access with server-owned snapshots and reviewed write plans."""

import json
import os
import secrets
import struct
import time
from pathlib import Path

from .fields import RecordProfile, number
from .roster import RosterError, validate_roster
from .settings import DEFAULT_GAME_PATH
from .windows_memory import WindowsMemory
from .mappings import ValueCatalog
from .paths import default_values_path


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

    def _status(self, process):
        if not process.alive():
            raise RosterError('NBA 2K27 closed. Start the game and reconnect.')
        pointer = struct.unpack('<Q', process.read(process.module_base + self.profile.pointer_offset, 8))[0]
        for offset in self.profile.base.get('Player Offset Chain', []):
            if pointer == 0:
                break
            pointer = struct.unpack('<Q', process.read(pointer + number(offset), 8))[0]
        if pointer and not 0x10000 <= pointer <= 0x7FFFFFFFFFFF:
            raise RosterError('Player array pointer is invalid for this build. Check the offset profile.')
        return {'connected': True, 'backend': 'native', 'process': process.path.name,
                'path': str(process.path), 'pid': process.pid, 'created': process.created,
                'build': process.build, 'module_base': process.module_base, 'base': pointer,
                'writes_enabled': bool(self.enable_writes and self.expected_build and
                                       process.build.casefold() == self.expected_build.casefold())}

    def status(self):
        with self.memory.open() as process:
            return self._status(process)

    def load(self):
        self.invalidate()
        players, records = [], {}
        stride = self.profile.stride
        first = number(self.profile.base['Offset First Name'])
        last = number(self.profile.base['Offset Last Name'])
        with self.memory.open() as process:
            status = self._status(process)
            if not status['base']:
                raise RosterError('Player array unavailable. Load a roster in NBA 2K27.')
            for index in range(6000):
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
                                'metadata': {'game_index': index}, **self.profile.decode(record)})
                records[identity] = record
                if index % 100 == 0 and self._status(process) != status:
                    raise RosterError('Game connection changed during loading. Try again.')
            if not players:
                raise RosterError('No players found. Load a roster in the game and check the profile.')
            if self._status(process) != status:
                raise RosterError('Game connection changed during loading. Try again.')
        roster = validate_roster({'name': 'NBA 2K27 roster', 'players': players, 'teams': []})
        self.records, self.identity = records, status
        return {'roster': roster, 'status': status, 'field_values': self.field_values()}

    def field_values(self):
        if not self.identity:
            return {}
        build = self.identity['build'].upper()
        return {category: {field: {label: entry['value'] for label, entry in values.items()}
                           for field, values in fields.items()}
                for category, fields in self.catalog.document['builds'].get(build, {}).items()}

    def normalize_value(self, category, name, value):
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
            after, edits, skipped = self.profile.patch(before, player, self.normalize_value)
            changes.extend({'name': player['name'], 'player_id': player['player_id'], **edit} for edit in edits)
            warnings.extend(f"{player['name']}: {warning}" for warning in skipped)
            if before != after:
                patches.append({'player_id': player['player_id'], 'index': int(player['player_id'].split('-')[1]),
                                'before': before.hex(), 'after': after.hex()})
        if changes:
            warnings.append('Full display names, team assignments, metadata, unmapped hotzones, and raw Advanced fields remain local. First/last names and promoted mapped fields can be edited in their category tabs.')
        plan_id = secrets.token_urlsafe(24)
        self.plans = {plan_id: {'created': time.monotonic(), 'patches': patches, 'changes': changes}}
        return {'plan_id': plan_id, 'changes': changes, 'warnings': warnings,
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

    def edit(self, document):
        if not self.live_enabled:
            raise RosterError('Start live editing before changing game values.')
        player_id, category, name = (document.get(key) for key in ('player_id', 'category', 'field'))
        if not all(isinstance(value, str) for value in (player_id, category, name)):
            raise RosterError('A player, category, and field are required.')
        field = self.profile.fields.get((category, name))
        if not field or not field.writable:
            raise RosterError('This field is local only; no enabled game mapping.')
        snapshot = self.records.get(player_id)
        if snapshot is None:
            raise RosterError('This player is not mapped to the loaded game roster.')
        old = field.decode(snapshot)
        if 'expected' in document and document['expected'] != old:
            raise RosterError('Another edit changed this field. Reload the game roster.')
        value = self.normalize_value(category, name, document.get('value'))
        check = bytearray(snapshot)
        field.encode(check, value)
        value = field.decode(check)
        if value == old:
            return {'changes': [], **self.history_state()}
        changes = [{'player_id': player_id, 'category': category, 'field': name, 'old': old, 'value': value}]
        self._write_changes(changes, 'live')
        self.undo_stack.append(changes)
        self.redo_stack = []
        return {'changes': changes, **self.history_state()}

    def undo(self, redo=False):
        stack = self.redo_stack if redo else self.undo_stack
        if not stack:
            raise RosterError('No game edit to redo.' if redo else 'No game edit to undo.')
        original = stack[-1]
        changes = original if redo else [{**change, 'old': change['value'], 'value': change['old'],
                                          **({'restore_bytes': change['raw_before']} if 'raw_before' in change else {})}
                                         for change in reversed(original)]
        self._write_changes(changes, 'redo' if redo else 'undo')
        stack.pop()
        (self.undo_stack if redo else self.redo_stack).append(original)
        return {'changes': changes, **self.history_state()}

    def apply(self, plan_id):
        plan = self.plans.pop(plan_id, None)
        if plan is None or time.monotonic() - plan['created'] > 300:
            raise RosterError('Plan expired. Preview game changes again.')
        if not plan['changes']:
            raise RosterError('No supported game changes to apply.')
        self._write_changes(plan['changes'], 'bulk', plan_id)
        self.undo_stack.append(plan['changes'])
        self.redo_stack = []
        return {'applied': len(plan['changes']), 'changes': plan['changes'], **self.history_state()}

    def _write_changes(self, changes, kind, transaction_id=None):
        if not self.identity or not self.identity['writes_enabled']:
            raise RosterError('Writes require enabled game editing. Start live editing or enable writes in Connection details.')
        grouped = {}
        for change in changes:
            player_id = change['player_id']
            if player_id not in self.records:
                raise RosterError('Unknown game player record.')
            grouped.setdefault(player_id, []).append(change)
        with self.memory.open(writable=True) as process:
            status = self._status(process)
            if status != self.identity or not status['writes_enabled']:
                raise RosterError('Game connection changed. Reload the game roster before applying.')
            patches, refreshed, edits = [], {}, []
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
                for change in fields:
                    field = self.profile.fields[change['category'], change['field']]
                    if field.decode(before) != change['old']:
                        raise RosterError('Roster changed in an edited field; reload before applying.')
                    if field.kind == 'utf16':
                        change.setdefault('raw_before', before[field.offset:field.offset+field.size].hex())
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
                offset = 0
                while offset < len(before):
                    if before[offset] == after[offset]:
                        offset += 1
                        continue
                    start = offset
                    while offset < len(before) and before[offset] != after[offset]:
                        offset += 1
                    edits.append((address + start, before[start:offset], after[start:offset]))
                patches.append({'player_id': player_id, 'before': before.hex(), 'after': after.hex()})
                refreshed[player_id] = after
            if self._status(process) != status:
                raise RosterError('Player array moved. Reload the game roster.')
            transaction_id = transaction_id or secrets.token_urlsafe(24)
            plan = {'kind': kind, 'changes': changes, 'patches': patches}
            self._log(transaction_id, status, plan, 'started')
            attempted = []
            try:
                for address, old, new in edits:
                    if self._status(process) != status:
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
                if self._status(process) != status:
                    raise RosterError('Game connection changed before verification finished.')
            except Exception as error:
                restored = True
                for address, old, _ in reversed(attempted):
                    try:
                        if self._status(process) != status:
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
        self.records.update(refreshed)
        self.plans = {}
