"""Hot-zone mappings against minimal bytes from controlled in-game captures."""

import json

import pytest

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.roster import RosterError


NAMES = (
    'Under Basket', 'Close Left', 'Close Middle', 'Close Right',
    'Mid-Range Left', 'Mid-Range Left Center', 'Mid-Range Center',
    'Mid-Range Right Center', 'Mid-Range Right', 'Three Left',
    'Three Left Center', 'Three Center', 'Three Right Center', 'Three Right',
)
OFFSETS = (0x177, 0x1CC, 0x1CF, 0x1D2, 0x1D3, 0x1DC, 0x35F, 0x372, 0x37E, 0x37F)
CAPTURES = (
    ('39151688806a40080000', (1, 1, 1, 1, 1, 1, 0, 1, 0, 2, 2, 1, 2, 2)),
    ('39412108007220080001', (1, 0, 0, 2, 2, 0, 1, 1, 2, 0, 0, 1, 1, 1)),
    ('3a590108407200000001', (1, 0, 2, 0, 2, 1, 1, 0, 2, 0, 1, 2, 0, 1)),
    ('38a51848806240108000', (1, 2, 1, 1, 0, 2, 2, 2, 1, 1, 2, 0, 2, 0)),
)


def test_observed_hotzone_captures_decode_and_reproduce_every_changed_byte():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8')))
    assert tuple(item['name'] for item in profile.document['Hotzones']) == NAMES
    records = []
    for observed, states in CAPTURES:
        row = bytearray([0xA5] * profile.stride)
        for offset, value in zip(OFFSETS, bytes.fromhex(observed)):
            row[offset] = value
        assert profile.decode(row, '6AD2E48C:36532000')['hotzones'] == dict(zip(NAMES, states))
        assert profile.decode(row, 'OTHER:BUILD')['hotzones'] == {}
        records.append(row)
    # Forward changes and restoring the initial states must preserve every other bit.
    for before_index, after_index in ((0, 1), (1, 2), (2, 3), (3, 0)):
        row = bytearray(records[before_index])
        for name, state in zip(NAMES, CAPTURES[after_index][1]):
            profile.fields['hotzones', name].encode(row, state)
        assert row == records[after_index]


def test_hotzone_masks_are_disjoint_and_reject_unknown_state():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8')))
    used_bits = set()
    for name in NAMES:
        field = profile.fields['hotzones', name]
        bits = set(range(field.offset * 8 + field.shift, field.offset * 8 + field.shift + field.bits))
        assert not used_bits & bits
        used_bits |= bits
        assert field.verified_build == '6AD2E48C:36532000'
        for state in (0, 1, 2):
            row = bytearray([0xA5] * profile.stride)
            before = bytes(row)
            field.encode(row, state)
            assert field.decode(row) == state
            changed_bits = {i * 8 + bit for i, (a, b) in enumerate(zip(before, row))
                            for bit in range(8) if (a ^ b) & (1 << bit)}
            assert changed_bits <= bits
        with pytest.raises(RosterError, match='supported field value'):
            field.encode(bytearray(profile.stride), 3)
    assert len(used_bits) == 28
