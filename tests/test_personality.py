import hashlib
import json

import pytest

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.game import APPROVED_BUILD_SECTION_LAYOUTS, OBSERVED_BUILD_WRITABLE_FIELDS
from trace_app.roster import RosterError
from test_connections import FakeGame


BUILD = '6ad2e48c:36532000'
NAMES = ['Reserved', 'Friendly', 'Team Player', 'Extremely Confident', 'Keep It Real',
         'Pat My Back', 'Expressive', 'Unpredictable', 'Laid Back', 'Media Ringmaster',
         'Warm Weather Fan', 'Finance Savvy', 'Alpha Dog', 'Enforcer', 'Work Ethic', 'Marketability']


@pytest.fixture
def profile():
    return RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))


@pytest.mark.parametrize('name', NAMES)
def test_personality_preserves_all_neighboring_bits_and_rejects_unknown_states(profile, name):
    field = profile.fields['badges', name]
    binary = name not in ('Work Ethic', 'Marketability')
    mask = ((1 << field.bits) - 1) << (field.offset * 8 + field.shift)
    original = bytes([0xA5] * profile.stride)
    for value in range(2 if binary else 5):
        record = bytearray(original)
        field.encode(record, value)
        assert field.decode(record) == value
        assert not ((int.from_bytes(original, 'little') ^ int.from_bytes(record, 'little')) & ~mask)
    for invalid in (-1, 2 if binary else 5, 7, True, 'Equipped'):
        with pytest.raises(RosterError):
            field.encode(bytearray(original), invalid)
    assert field.verified_build.casefold() == BUILD
    assert (field.offset, field.bits, field.shift, field.kind) == OBSERVED_BUILD_WRITABLE_FIELDS[BUILD]['badges', name]


def test_original_badge_approval_layout_is_unchanged(profile):
    fields = [f for f in profile.fields.values() if f.category == 'badges' and f.writable]
    original = [f for f in fields if f.name not in NAMES]
    def digest(items):
        layout = sorted((f.name, f.offset, f.bits, f.shift, f.kind) for f in items)
        return hashlib.sha256(json.dumps(layout, separators=(',', ':')).encode()).hexdigest()
    assert len(original) == 53
    assert digest(original) == 'cd816c4a1503623b8d14267037f38b014cce61a4ef979ebd1880ecb163f1ce86'
    assert len(fields) == 69
    assert digest(fields) == APPROVED_BUILD_SECTION_LAYOUTS[BUILD]['badges']


def make_game(tmp_path):
    game = FakeGame(tmp_path)
    game.memory.build = BUILD
    game.memory.data[:game.profile.stride] = bytes([0xA5] * game.profile.stride)
    for name in NAMES:
        game.profile.fields['badges', name].encode(game.memory.data, 0)
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    game.identity = game.status()
    game.set_live(True)
    return game


def test_personality_live_undo_redo_restores_exact_bytes(tmp_path):
    game = make_game(tmp_path)
    original = bytes(game.memory.data)
    for name in NAMES:
        game.edit({'player_id': 'game-0', 'category': 'badges', 'field': name,
                   'value': 4 if name in ('Work Ethic', 'Marketability') else 1})
    edited = bytes(game.memory.data)
    for name in reversed(NAMES):
        game.undo()
    assert bytes(game.memory.data) == original
    for name in NAMES:
        game.undo(redo=True)
    assert bytes(game.memory.data) == edited
    assert game.audit_path.exists()


def test_personality_cross_build_and_unsupported_current_tier_fail_closed(tmp_path):
    game = make_game(tmp_path)
    game.memory.build = 'OTHER'
    with pytest.raises(RosterError):
        game.edit({'player_id': 'game-0', 'category': 'badges', 'field': 'Reserved', 'value': 1})
    assert not game.memory.writes
    assert not any(name in game.profile.decode(bytes(game.profile.stride), 'OTHER')['badges'] for name in NAMES)
    game.memory.build = BUILD
    field = game.profile.fields['badges', 'Work Ethic']
    # Stored pattern 7 is representable, but is not one of the supported UI tiers.
    game.memory.data[field.offset] |= 7 << field.shift
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    with pytest.raises(RosterError):
        game.edit({'player_id': 'game-0', 'category': 'badges', 'field': 'Work Ethic', 'value': 4})
    assert not game.memory.writes
