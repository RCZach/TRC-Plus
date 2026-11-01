import json
import struct
import zlib
from pathlib import Path

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.setter_mappings import SETTER_FIELDS
from trace_app.roster import RosterError
from test_connections import FakeGame
from dataclasses import replace
import pytest


def test_native_enum_names_match_explicit_value_tables_and_observed_anchors():
    fixture = json.loads((Path(__file__).parent / 'fixtures' / 'native_enums_2k27.json').read_text())
    enums = {item['enum']: item for item in fixture['enums']}
    for item in enums.values():
        raw = bytes.fromhex(item['table_hex'])
        assert len(raw) == 12 * len(item['entries'])
        for index, entry in enumerate(item['entries']):
            crc, value, padding = struct.unpack_from('<III', raw, index * 12)
            assert crc == zlib.crc32(entry['enum_name'].encode())
            assert value == entry['value'] and padding == 0
        assert item['runtime_match']
    injury = {e['enum_name']: e['value'] for e in enums['PLAYERDATA_INJURY']['entries']}
    assert len(injury) == 157
    assert (injury['NO_INJURY'], injury['APPENDECTOMY'], injury['BACK_SPASMS']) == (0, 1, 3)
    play = {e['enum_name']: e['value'] for e in enums['PLAYERDATA_PLAYTYPE']['entries']}
    assert (play['PNR_POINT'], play['ISO_POINT'], play['SCREEN_MID'], play['SCREEN_3PT']) == (5, 2, 14, 15)


def test_named_options_keep_setter_bounds_and_observed_labels():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8')))
    for key, (_, maximum, _, _, _) in SETTER_FIELDS.items():
        assert profile.fields[key].allowed_values == tuple(range(maximum + 1))
    frequency = next(f for f in profile.document['Accessories'] if f['name'] == 'Headband Frequency')
    assert frequency['options'] == {'Always': 0, 'Often': 1, 'Sometimes': 2, 'Rarely': 3, 'Never': 4}
    play = next(f for f in profile.document['Vitals'] if f['name'] == 'Play Type 1')
    assert len(play['options']) == 16
    assert {k: play['options'][k] for k in ('P&R Point', 'Isolation Point', 'Mid Range', '3PT')} == {
        'P&R Point': 5, 'Isolation Point': 2, 'Mid Range': 14, '3PT': 15}
    catalog = json.loads((DEFAULT_PROFILE.parent / 'field_values.json').read_text(encoding='utf-8'))['builds'][
        '6AD2E48C:36532000']
    for slot in ('INJURY1TYPE', 'INJURY2TYPE'):
        assert {e['value'] for e in catalog['advanced'][slot].values()} == set(range(157))
    # The headband enum has not been shown to represent the UI style labels.
    assert catalog['accessories']['Headband']['Style 1']['value'] == 0
    assert catalog['accessories']['Headband']['Style 2']['value'] == 1


def test_unknown_injury_type_does_not_authorize_duration_write(tmp_path):
    game = FakeGame(tmp_path, writes=True)
    game.memory.build = game.expected_build = '6AD2E48C:36532000'
    for name, value in [('INJURY1TYPE', 255), ('INJURY1STATUS', 4)]:
        replace(game.profile.fields['advanced', name], writable=True).encode(game.memory.data, value)
    game.profile.fields['vitals', 'Injury 1 Duration Days'].encode(game.memory.data, 8)
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    game.identity = game.status()
    game.set_live(True)
    with pytest.raises(RosterError, match='Create or clear injuries'):
        game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'Injury 1 Duration Days', 'value': 9})
    assert not game.memory.writes
