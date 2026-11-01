import json
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace

import pytest

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.roster import RosterError
from trace_app.team_sections import (TEAM_BUILD, CODE_PROOFS, PROPERTY_PROOFS, STAFF_ROLES, COACH_FIELDS,
                                     populate_team_sections, verified_team_sections)


def fixture_data(failure=None):
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8')))
    proof = json.loads((Path(__file__).parent / 'fixtures' / 'team_layout_2k27.json').read_text())
    module, base, root, staff = 0x100000, 0x200000, 0x400000, 0x500000
    memory = {module + int(rva, 16): bytearray.fromhex(raw) for rva, raw in proof['code'].items()}
    for entry in proof['properties']:
        memory[module + entry['rva']] = bytearray.fromhex(entry['hex'])
    if failure == 'canonical_type':
        for name in ('HelpDefense', 'RunPlayTendency', 'ZoneUsage', 'Tempo'):
            memory[module + PROPERTY_PROOFS[name][0]][4:8] = zlib.crc32(b'u8').to_bytes(4, 'little')
    if failure == 'code':
        memory[module + CODE_PROOFS['PLAYERDATA::SetPlayingTime'][0]][0] ^= 1
    if failure == 'property':
        memory[module + PROPERTY_PROOFS['HelpDefense'][0]][8] ^= 1
    if failure == 'type':
        memory[module + PROPERTY_PROOFS['HelpDefense'][0]][4:8] = bytes(4)
    if failure == 'names':
        memory[module + PROPERTY_PROOFS['FirstName'][0]][8] ^= 1
    data = bytearray(profile.stride * 2)
    players, records = [], {}
    for index, minutes in enumerate((29, 35)):
        raw = bytearray(profile.stride)
        raw[:4] = 'AA'.encode('utf-16-le')
        first = f'Player{index}'.encode('utf-16-le')
        raw[40:40+len(first)] = first
        struct.pack_into('<Q', raw, 0x60, root)
        replace(profile.fields['advanced', 'PLAYINGTIME'], writable=True).encode(raw, minutes)
        records[f'game-{index}'] = bytes(raw)
        data[index*profile.stride:(index+1)*profile.stride] = raw
        players.append({'player_id': f'game-{index}', 'team_id': 'team-0', 'metadata': {'game_index': index}})
    memory[base] = data
    team = bytearray(0x1400)
    struct.pack_into('<2Q', team, 0, base, base + profile.stride)
    struct.pack_into('<Q', team, 0xF70, staff)
    memory[root] = team
    raw = bytearray(0x1A0)
    for offset, text in ((0x50, 'Morgan'), (0x78, 'Coach')):
        encoded = text.encode('utf-16-le')
        raw[offset:offset+len(encoded)] = encoded
    for offset, value in ((0x165, 50), (0x15A, 70), (0x15C, 8), (0x164, 75)):
        raw[offset] = value
    if failure == 'job':
        raw[0x182] = 1
    if failure == 'unknown_value':
        raw[0x165] = 200
    memory[staff] = raw
    if failure == 'membership':
        struct.pack_into('<Q', team, 8, base)
    if failure == 'player_identity':
        data[0] ^= 1
    if failure == 'unreadable':
        memory.pop(staff)
    calls = {}

    def read(address, size):
        calls[address] = calls.get(address, 0) + 1
        if failure == 'moving_staff' and address == staff and calls[address] == 2:
            changed = bytearray(raw)
            changed[0x50] ^= 1
            return bytes(changed)
        if failure == 'moving_team' and address == root and calls[address] == 2:
            changed = bytearray(team[:size])
            changed[0] ^= 1
            return bytes(changed)
        for start, contents in memory.items():
            if start <= address and address + size <= start + len(contents):
                return bytes(contents[address-start:address-start+size])
        raise RosterError('Unreadable fixture')

    process = SimpleNamespace(build='OTHER' if failure == 'build' else TEAM_BUILD,
                              module_base=module, read=read)
    teams = [{'team_id': 'team-0', 'name': 'Example Team', 'metadata': {}}]
    return process, profile, base, players, records, teams


@pytest.mark.parametrize('failure', [None, 'canonical_type', 'code', 'property', 'type', 'names',
                                   'job', 'unknown_value', 'membership', 'player_identity',
                                   'unreadable', 'moving_staff', 'moving_team', 'build'])
def test_team_sections_require_code_metadata_membership_and_stable_references(failure):
    process, profile, base, players, records, teams = fixture_data(failure)
    populate_team_sections(process, profile, base, players, records, teams)
    team = teams[0]
    if failure in ('membership', 'player_identity', 'moving_team', 'build'):
        assert not any(k in team for k in ('rotation', 'staff', 'coaching'))
        return
    assert ('rotation' in team) == (failure != 'code')
    if 'rotation' in team:
        assert team['rotation']['minutes'] == {'game-0': 29, 'game-1': 35}
        assert team['rotation']['total_minutes'] == 64  # Do not invent/force a 240-minute total.
    if failure == 'names':
        assert 'staff' not in team and 'coaching' not in team
    elif failure in ('job', 'unreadable', 'moving_staff'):
        assert team['staff']['entries'] == [] and 'coaching' not in team
    else:
        assert team['staff']['entries'] == [{'role_code': 0, 'role': 'COACH', 'name': 'Morgan Coach'}]
        assert ('coaching' in team) == (failure not in ('property', 'type'))
        if 'coaching' in team:
            expected = {'Run Plays Frequency': 70, 'Zone Usage Frequency': 8, 'Tempo': 75}
            if failure != 'unknown_value':
                expected['Help Defense'] = 50
            expected.update({name: 0 for name in COACH_FIELDS if name not in ('Help Defense', 'Run Plays Frequency', 'Zone Usage Frequency', 'Tempo')})
            assert team['coaching']['values'] == expected
    assert str(0x400000) not in json.dumps(team) and str(0x500000) not in json.dumps(team)
    assert not profile.fields['advanced', 'PLAYINGTIME'].writable


def test_staff_role_ids_come_from_explicit_native_table():
    raw = bytes.fromhex(PROPERTY_PROOFS['STAFFDATA_JOB'][1])
    assert len(STAFF_ROLES) == 32 and len(raw) == 32 * 12
    for index, name in enumerate(STAFF_ROLES):
        crc, value, pad = struct.unpack_from('<III', raw, index * 12)
        assert crc == zlib.crc32(name.encode()) and value == index and pad == 0
