"""Guarded preparation of independent coach-default byte updates.

Execution, journaling, readback, rollback and history remain in GameConnection's
single transaction writer, including batches mixed with player/Body changes.
"""

import hashlib
import struct

from .roster import RosterError
from .team_sections import (TEAM_BUILD, TEAM_STAFF_OFFSET, STAFF_SIZE, COACH_FIELDS,
                            CODE_PROOFS, verified_team_sections)


def coaching_value(name, value):
    if name not in COACH_FIELDS or type(value) is not int or not 0 <= value <= 100:
        raise RosterError('Choose a mapped coaching value from 0 to 100.')
    return value


def _links_from_records(records, stride):
    links = []
    for identity, row in records.items():
        index = int(identity.split('-')[1])
        if not 0 <= index < 6000 or len(row) != stride:
            raise RosterError('Loaded roster identities are invalid; reload the roster.')
        links.append((index, row[0x60:0x68], row[0x78:0x80]))
    return sorted(links)


def _check_links(process, profile, context):
    if ((process.pid, process.created, process.module_base, process.build.casefold()) != context['process'] or
            process.build.casefold() != TEAM_BUILD or profile.stride != 0x4F8):
        raise RosterError('Game process or roster layout changed; reload the roster.')
    size = context['links'][-1][0] * profile.stride + 0x80
    raw = process.read(context['base'], size)
    if len(raw) != size or any(raw[i*profile.stride+0x60:i*profile.stride+0x68] != team or
                              raw[i*profile.stride+0x78:i*profile.stride+0x80] != body
                              for i, team, body in context['links']):
        raise RosterError('Team or player structure references changed; reload the roster.')
    if process.read(context['sentinel'], 2) != b'\0\0':
        raise RosterError('The loaded roster length changed; reload the roster.')


def _verified_code(process, profile):
    if 'coaching' not in verified_team_sections(process, profile):
        raise RosterError('Coaching code or property mappings changed; reload the roster.')
    rva, size, digest = CODE_PROOFS['TEAMDATA::SetLineupPlayerByIndex']
    if hashlib.sha256(process.read(process.module_base + rva, size)).hexdigest() != digest:
        raise RosterError('Team membership code changed; reload the roster.')


def _check_owner(context, snapshot):
    pointer = snapshot['coach_pointer']
    if not 0x10000 <= pointer <= 0x7FFFFFFFFFFF - STAFF_SIZE or pointer % 8:
        raise RosterError('The coach record is not valid for editing.')
    slots = context['slots']
    if snapshot['team_pointer'] not in slots or int.from_bytes(slots[snapshot['team_pointer']][:8], 'little') != pointer:
        raise RosterError('The assigned coach changed; reload the roster.')
    references = [(root, role, value) for root, raw in slots.items()
                  for role, value in enumerate(struct.unpack('<32Q', raw)) if value]
    if sum(value == pointer for _, _, value in references) != 1:
        raise RosterError('This coach record is shared; independent team editing is disabled.')
    if any(value != pointer and abs(value - pointer) < STAFF_SIZE for _, _, value in references):
        raise RosterError('Coach records overlap; editing is disabled.')
    end = pointer + STAFF_SIZE
    if pointer < context['module_end'] and end > context['process'][2]:
        raise RosterError('Coach data is not an isolated runtime record; editing is disabled.')
    if not (end <= context['base'] or pointer >= context['array_end']):
        raise RosterError('Coach data overlaps player records; editing is disabled.')
    for root in slots:
        if pointer < root + TEAM_STAFF_OFFSET + 256 and end > root:
            raise RosterError('Coach data overlaps a team object; editing is disabled.')
    for _, _, encoded in context['links']:
        body = int.from_bytes(encoded, 'little')
        if body and pointer < body + STAFF_SIZE and end > body:
            raise RosterError('Coach data overlaps a player structure; editing is disabled.')


def _check_target(process, snapshot):
    pointer = snapshot['team_pointer']
    header = process.read(pointer, 0x358)
    if len(header) != 0x358 or header[:160] + header[0x2FA:0x358] != snapshot['team_signature']:
        raise RosterError('Team identity or membership changed; reload the roster.')
    raw = process.read(snapshot['coach_pointer'], STAFF_SIZE)
    saved = snapshot['data']
    if (len(raw) != STAFF_SIZE or raw[0x50:0xA0] != saved[0x50:0xA0] or
            raw[0x182] != saved[0x182] or raw[0x182] & 31):
        raise RosterError('Coach identity or role changed; reload the roster.')
    return raw


def coaching_ownership(process, profile, base, records):
    _verified_code(process, profile)
    links = _links_from_records(records, profile.stride)
    if not links:
        raise RosterError('Load the game roster before editing coaching values.')
    context = {'base': base, 'links': links,
               'array_end': base + (links[-1][0]+1)*profile.stride,
               'module_end': process.module_base + int(process.build.split(':')[1], 16),
               'process': (process.pid, process.created, process.module_base, process.build.casefold()), 'slots': {}}
    last_name = profile.base['Offset Last Name']
    context['sentinel'] = context['array_end'] + (int(last_name, 0) if isinstance(last_name, str) else last_name)
    _check_links(process, profile, context)
    for pointer in sorted({int.from_bytes(team, 'little') for _, team, _ in links} - {0}):
        if not 0x10000 <= pointer <= 0x7FFFFFFFFFFF - TEAM_STAFF_OFFSET - 256 or pointer % 8:
            raise RosterError('A referenced team could not be validated for coach ownership.')
        raw = process.read(pointer + TEAM_STAFF_OFFSET, 256)
        if len(raw) != 256 or any(value and (not 0x10000 <= value <= 0x7FFFFFFFFFFF - STAFF_SIZE or value % 8)
                                  for value in struct.unpack('<32Q', raw)):
            raise RosterError('Staff ownership could not be validated; reload the roster.')
        context['slots'][pointer] = raw
    context['fingerprint'] = hashlib.sha256(b''.join(i.to_bytes(4, 'little')+team+body for i, team, body in links) +
        b''.join(root.to_bytes(8, 'little')+raw for root, raw in context['slots'].items())).hexdigest()
    return context


def validate_coaching_context(process, profile, context, snapshots):
    if not context:
        raise RosterError('Coaching code or property mappings changed; reload the roster.')
    _verified_code(process, profile)
    _check_links(process, profile, context)
    for pointer, expected in context['slots'].items():
        if process.read(pointer + TEAM_STAFF_OFFSET, 256) != expected:
            raise RosterError('Staff assignments changed; reload the roster.')
    for snapshot in snapshots.values():
        _check_owner(context, snapshot)
        _check_target(process, snapshot)


def enable_coaching(process, profile, base, records, snapshots, teams):
    try:
        context = coaching_ownership(process, profile, base, records)
        validate_coaching_context(process, profile, context, {})
    except (RosterError, OSError):
        return None
    for team in teams:
        snapshot = snapshots.get(team['team_id'])
        if not snapshot or 'coaching' not in team:
            continue
        try:
            _check_owner(context, snapshot)
            raw = _check_target(process, snapshot)
            if raw != snapshot['data']:
                continue
            fields = [name for name, offset in COACH_FIELDS.items() if raw[offset] <= 100]
            snapshot['writable_fields'] = fields
            team['coaching']['writable_fields'] = fields
            team['coaching']['read_only'] = not bool(fields)
        except (RosterError, OSError):
            continue
    try:
        validate_coaching_context(process, profile, context, {})
    except (RosterError, OSError):
        for team in teams:
            if 'coaching' in team:
                team['coaching'].pop('writable_fields', None)
                team['coaching']['read_only'] = True
        for snapshot in snapshots.values():
            snapshot.pop('writable_fields', None)
        return None
    return context


def prepare_coaching(process, profile, context, snapshots, changes):
    grouped = {}
    for change in changes:
        identity = change.get('team_id')
        if identity not in snapshots or change.get('category') != 'coaching' or 'player_id' in change:
            raise RosterError('This team or coaching field is not mapped to the loaded roster.')
        coaching_value(change.get('field'), change.get('value'))
        if change['field'] not in snapshots[identity].get('writable_fields', []):
            raise RosterError('This coaching field is read only for the loaded team.')
        grouped.setdefault(identity, []).append(change)
    targets = {identity: snapshots[identity] for identity in grouped}
    validate_coaching_context(process, profile, context, targets)
    regions = []
    for identity, fields in grouped.items():
        saved = snapshots[identity]
        before = _check_target(process, saved)
        after = bytearray(before)
        seen = set()
        for change in fields:
            name = change['field']
            offset = COACH_FIELDS[name]
            if name in seen or before[offset] != change.get('old') or before[offset] > 100:
                raise RosterError('A coaching value changed; reload before applying.')
            seen.add(name)
            after[offset] = change['value']
        regions.append({'team_id': identity, 'address': saved['coach_pointer'],
                        'before': before, 'after': bytes(after), 'team_pointer': saved['team_pointer'],
                        'team_signature': saved['team_signature'].hex()})
    validate_coaching_context(process, profile, context, targets)
    return regions, targets
