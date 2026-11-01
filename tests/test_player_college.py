import json
from types import SimpleNamespace

import pytest

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.player_college import COLLEGE_BUILD, read_college
from trace_app.roster import RosterError


@pytest.mark.parametrize('failure', [None, 'build', 'stride', 'pointer', 'identity', 'moved',
                                   'unstable', 'unreadable', 'unterminated', 'encoding', 'control'])
def test_college_requires_stable_named_reference(failure):
    row = bytearray(0x4F8)
    row[:4] = b'Name'
    row[0xB0:0xB8] = (0 if failure == 'pointer' else 0x400000).to_bytes(8, 'little')
    fresh = bytearray(row)
    if failure == 'identity':
        fresh[0] ^= 1
    if failure == 'moved':
        fresh[0xB0:0xB8] = (0x500000).to_bytes(8, 'little')
    raw = b'Arizona'.ljust(48, b'\0')
    if failure == 'unterminated':
        raw = b'A' * 48
    if failure == 'encoding':
        raw = b'\xff'.ljust(48, b'\0')
    if failure == 'control':
        raw = b'A\nB'.ljust(48, b'\0')
    calls = []

    def read(address, size):
        calls.append(address)
        if failure == 'unreadable':
            raise RosterError('Unreadable')
        if address == 0x200000:
            return bytes(fresh)
        assert address == 0x400000 and size == 48
        return raw if failure != 'unstable' or calls.count(address) == 1 else bytes(48)

    process = SimpleNamespace(build='OTHER' if failure == 'build' else COLLEGE_BUILD, read=read)
    profile = SimpleNamespace(stride=0x500 if failure == 'stride' else 0x4F8)
    assert read_college(process, profile, row, 0x200000) == (
        {'college_from': 'Arizona'} if failure is None else {})


def test_avg_percent_observed_change_preserves_injury_and_adjacent_bits():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8')))
    field = profile.fields['vitals', 'AVG Percent']
    assert (field.offset, field.bits, field.shift) == (0x358, 7, 20)
    row = bytearray([0xA5] * profile.stride)
    field.encode(row, 92)
    before = bytes(row)
    field.encode(row, 91)
    assert field.decode(row) == 91
    allowed = 127 << (0x358 * 8 + 20)
    assert not ((int.from_bytes(before, 'little') ^ int.from_bytes(row, 'little')) & ~allowed)
    field.encode(row, 92)
    assert row == before
    for value in (-1, 101, 127):
        with pytest.raises(RosterError, match='supported field value'):
            field.encode(row, value)
    assert 'AVG Percent' not in profile.decode(row, 'OTHER:BUILD')['vitals']
    assert 'College / From' not in profile.decode(row, COLLEGE_BUILD)['vitals']
