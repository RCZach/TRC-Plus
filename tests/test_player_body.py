import json
import struct
from types import SimpleNamespace

import pytest

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.game import GameConnection
from trace_app.player_body import BODY_BUILD, decode_body, read_body
from trace_app.roster import RosterError


@pytest.mark.parametrize('height,scales,expected', [
    (18796, (1, 1, 1, 1), (74, 50, 50, 50, 50)),
    (19050, (1, 1, 1, 1), (75, 50, 50, 50, 50)),
    (19050, (1, 1, 1.002, 1), (75, 51, 50, 50, 50)),
    (19050, (1.016, 1.004, 1.002, 1.012), (75, 51, 52, 53, 54)),
    (19050, (1.012, 1.008, 1.002, 1.008), (75, 51, 54, 52, 53)),
])
def test_observed_body_captures(height, scales, expected):
    raw = struct.pack('<2H4f', height, 20019, *scales)
    result = decode_body(raw)
    assert tuple(result[name] for name in
                 ('Height', 'Wingspan', 'Shoulder Width', 'Neck Length', 'Trunk Length')) == expected


@pytest.mark.parametrize('scale', [float('nan'), float('inf'), 1.5, 1.0009])
def test_unknown_body_scale_is_not_clamped(scale):
    assert decode_body(struct.pack('<2H4f', 19050, 20019, scale, 1, 1, 1)) == {}


@pytest.mark.parametrize('failure', [None, 'build', 'stride', 'pointer', 'identity', 'moved', 'unstable', 'unreadable'])
def test_linked_body_requires_stable_identity_and_pointer(failure):
    record = bytearray(0x4F8)
    record[:4] = b'Name'
    struct.pack_into('<Q', record, 0x78, 0 if failure == 'pointer' else 0x400000)
    fresh = bytearray(record)
    if failure == 'identity':
        fresh[0] ^= 1
    if failure == 'moved':
        struct.pack_into('<Q', fresh, 0x78, 0x500000)
    raw = struct.pack('<2H4f', 19050, 20019, 1.012, 1.008, 1.002, 1.008)
    calls = []

    def read(address, size):
        calls.append(address)
        if failure == 'unreadable':
            raise RosterError('Unreadable')
        if address == 0x200000:
            return bytes(fresh)
        assert address == 0x400000 and size == 0x14
        return raw if failure != 'unstable' or calls.count(address) == 1 else bytes(size)

    process = SimpleNamespace(build='OTHER' if failure == 'build' else BODY_BUILD, read=read)
    profile = SimpleNamespace(stride=0x500 if failure == 'stride' else 0x4F8)
    result = read_body(process, profile, record, 0x200000)
    assert bool(result) == (failure is None)


def test_body_readouts_never_enter_record_write_mapping():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    for name in ('Height', 'Wingspan', 'Shoulder Width', 'Neck Length', 'Trunk Length'):
        assert ('vitals', name) not in profile.fields
    before = bytes(profile.stride)
    after, edits, warnings = profile.patch(before, {'vitals': {'Height': 75, 'Wingspan': 51}}, build=BODY_BUILD)
    assert after == before and not edits and len(warnings) == 2


def test_preview_ignores_unchanged_body_readouts_but_reports_edits(tmp_path):
    game = GameConnection(json.loads(DEFAULT_PROFILE.read_text()), values_path=tmp_path / 'values.json')
    game.identity = {'build': BODY_BUILD, 'writes_enabled': False}
    game.status = lambda: game.identity
    game.records = {'game-0': bytes(game.profile.stride)}
    game.body_values = {'game-0': {'Height': 75}}
    document = {'players': [{'player_id': 'game-0', 'name': 'Example', 'vitals': {'Height': 75}}], 'teams': []}
    result = game.preview(document)
    assert not result['changes'] and not result['warnings']
    assert document['players'][0]['vitals']['Height'] == 75
    document['players'][0]['vitals']['Height'] = 76
    result = game.preview(document)
    assert not result['changes']
    assert any('Height: no enabled memory mapping' in warning for warning in result['warnings'])
