import json
import struct
from dataclasses import replace

import pytest

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.player_summary import SUMMARY_BUILD, player_summary, read_teams
from trace_app.roster import RosterError


@pytest.fixture
def profile():
    return RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))


@pytest.mark.parametrize('primary,secondary,overall,expected_position,expected_overall', [
    (0, 5, 76.018768, 'PG', 76),
    (1, 2, 87.772331, 'SG / SF', 88),
    (3, 2, 85.8665, 'PF / SF', 86),
    (4, 3, 89.27879, 'C / PF', 89),
])
def test_observed_player_summary(profile, primary, secondary, overall, expected_position, expected_overall):
    record = bytearray(profile.stride)
    record[0x12D] = primary | secondary << 3
    record[0x370] = 1 << 6
    struct.pack_into('<f', record, 0x1AC, overall)
    summary = player_summary(profile, record, SUMMARY_BUILD)
    assert summary['position'] == expected_position
    assert summary['overall'] == expected_overall
    assert summary['team_status'] == 'unknown'
    assert 'position' not in player_summary(profile, record, 'OTHER:BUILD')


@pytest.mark.parametrize('value,valid', [(76.0, False), (float('nan'), True), (float('inf'), True), (0, True), (150, True)])
def test_invalid_overall_does_not_become_a_rating(profile, value, valid):
    record = bytearray(profile.stride)
    record[0x370] = 64 if valid else 0
    struct.pack_into('<f', record, 0x1AC, value)
    assert 'overall' not in player_summary(profile, record, SUMMARY_BUILD)


def test_changed_field_layout_is_not_used(profile):
    record = bytearray(profile.stride)
    record[0x370] = 64
    field = profile.fields['advanced', 'CACHEDOVERALLRATINGNEVERCALL']
    profile.fields['advanced', field.name] = replace(field, offset=0x1B0)
    struct.pack_into('<f', record, 0x1B0, 88)
    record[0x12D] = 7 | 6 << 3
    summary = player_summary(profile, record, SUMMARY_BUILD)
    assert 'overall' not in summary
    assert 'position' not in summary


@pytest.mark.parametrize('failure', [None, 'empty_city', 'membership', 'duplicate', 'text', 'unreadable', 'null', 'build'])
def test_team_names_require_validated_membership(profile, failure):
    base, pointer = 0x200000, 0x400000
    players = [{'player_id': f'game-{index}', 'name': name,
                'metadata': {'game_index': index, 'team_status': 'unknown'}}
               for index, name in enumerate(['Mike Bibby', 'Joe Johnson'])]
    records = {}
    for player in players:
        record = bytearray(profile.stride)
        struct.pack_into('<Q', record, 0x60, 0 if failure == 'null' else pointer)
        records[player['player_id']] = bytes(record)
    raw = bytearray(0x358)
    struct.pack_into('<2Q', raw, 0, base, base + profile.stride)
    for offset, value in [(0x2FA, 'Hawks'), (0x32C, 'Atlanta'), (0x350, 'ATL')]:
        encoded = value.encode('utf-16-le')
        raw[offset:offset + len(encoded)] = encoded
    if failure == 'membership':
        struct.pack_into('<Q', raw, 8, base + profile.stride * 2)
    if failure == 'duplicate':
        struct.pack_into('<Q', raw, 8, base)
    if failure == 'text':
        raw[0x350:0x358] = 'ABCD'.encode('utf-16-le')
    if failure == 'empty_city':
        raw[0x32C:0x350] = bytes(36)

    class Process:
        build = 'OTHER:BUILD' if failure == 'build' else SUMMARY_BUILD

        def read(self, address, size):
            assert address == pointer and size == len(raw)
            if failure == 'unreadable':
                raise RosterError('Unreadable team object')
            return bytes(raw)

    teams = read_teams(Process(), profile, base, players, records)
    if failure in (None, 'empty_city'):
        assert teams[0]['name'] == ('Hawks' if failure == 'empty_city' else 'Atlanta Hawks')
        assert teams[0]['metadata']['abbreviation'] == 'ATL'
        assert all(p['team_id'] == teams[0]['team_id'] for p in players)
    else:
        assert teams == []
        assert all('team_id' not in p and p['metadata']['team_status'] == 'unknown' for p in players)
