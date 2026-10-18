import copy
import json
import struct

import pytest

from trc_plus.app import DEFAULT_PROFILE
from trc_plus.fields import RecordProfile
from trc_plus.mappings import ValueCatalog, expand_profile
from trc_plus.roster import RosterError, validate_roster
from test_connections import FakeGame


def test_profile_expansion_is_idempotent_and_keeps_engine_fields_read_only():
    source = json.loads(DEFAULT_PROFILE.read_text())
    original = copy.deepcopy(source)
    expanded = expand_profile(source)
    assert source == original
    assert expand_profile(expanded) == expanded
    profile = RecordProfile(source)
    assert profile.fields['signatures', 'Dribble Style'].writable
    assert profile.fields['gear', 'Shoe Home Style'].writable
    assert profile.fields['accessories', 'Headband'].writable
    assert profile.fields['vitals', 'Weight'].kind == 'float'
    assert profile.fields['vitals', 'First Name'].kind == 'utf16'
    assert not profile.fields['advanced', 'WEIGHT'].writable
    assert not profile.fields['advanced', 'CACHEDOVERALLRATINGNEVERCALL'].writable
    assert ('advanced', 'POINTS') in profile.ambiguous
    assert not profile.document['Hotzones']


def test_float_and_utf16_encoding_reject_invalid_values_and_preserve_neighbors():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    record = bytearray([0xA5] * profile.stride)
    field = profile.fields['vitals', 'Weight']
    old = bytes(record)
    field.encode(record, 200.5)
    assert field.decode(record) == 200.5
    assert record[:field.offset] == old[:field.offset]
    assert record[field.offset+field.size:] == old[field.offset+field.size:]
    for value in (True, -1, 0, float('nan'), float('inf'), 1e100):
        with pytest.raises(RosterError):
            field.encode(record, value)
    name = profile.fields['vitals', 'Last Name']
    before = bytes(record)
    name.encode(record, 'Jokić')
    assert name.decode(record) == 'Jokić'
    assert record[40:] == before[40:]
    for value in ('A' * 20, 'bad\0name', '', 123):
        with pytest.raises(RosterError):
            name.encode(record, value)


def test_catalog_is_build_scoped_and_conflicts_never_overwrite(tmp_path):
    path = tmp_path / 'values.json'
    catalog = ValueCatalog(path)
    catalog.learn('ABC:DEF', 'signatures', 'Dribble Style', 'Tyrese Maxey', 33, 'game-0')
    assert catalog.resolve('abc:def', 'signatures', 'Dribble Style', 'TYRESE MAXEY') == 33
    assert ValueCatalog(path).resolve('ABC:DEF', 'signatures', 'Dribble Style', 'Tyrese Maxey') == 33
    before = path.read_bytes()
    with pytest.raises(RosterError, match='different game ID'):
        catalog.learn('ABC:DEF', 'signatures', 'Dribble Style', 'Tyrese Maxey', 34, 'game-0')
    assert path.read_bytes() == before
    with pytest.raises(RosterError, match='no verified game ID'):
        catalog.resolve('NEW:BUILD', 'signatures', 'Dribble Style', 'Tyrese Maxey')


def test_learned_name_can_be_written_live_and_undone_without_guessing(tmp_path):
    game = FakeGame(tmp_path)
    field = game.profile.fields['signatures', 'Dribble Style']
    field.encode(game.memory.data, 33)
    observed = game.learn_value({'player_id': 'game-0', 'category': 'signatures', 'field': 'Dribble Style', 'label': 'Observed style'})
    assert observed['mapping']['value'] == 33
    assert not game.memory.writes
    field.encode(game.memory.data, 12)
    game.learn_value({'player_id': 'game-0', 'category': 'signatures', 'field': 'Dribble Style', 'label': 'Other observed style'})
    game.set_live(True)
    result = game.edit({'player_id': 'game-0', 'category': 'signatures', 'field': 'Dribble Style', 'value': 'Observed style'})
    assert result['changes'][0]['value'] == 33
    assert field.decode(game.memory.data) == 33
    game.undo()
    assert field.decode(game.memory.data) == 12
    before = bytes(game.memory.data)
    with pytest.raises(RosterError, match='no verified game ID'):
        game.edit({'player_id': 'game-0', 'category': 'signatures', 'field': 'Dribble Style', 'value': 'Unobserved style'})
    assert bytes(game.memory.data) == before


def test_capture_records_changes_but_never_enables_unknown_offsets(tmp_path):
    game = FakeGame(tmp_path)
    capture = game.capture_change({'player_id': 'game-0', 'label': 'Hotzones / Close Left: Neutral to Hot'})
    with pytest.raises(RosterError, match='No player-record change'):
        game.compare_change({'capture_id': capture['capture_id']})
    game.memory.data[0x200] ^= 0b10000001
    game.memory.data[0xE8] ^= 1
    result = game.compare_change({'capture_id': capture['capture_id']})
    offsets = {change['offset']: change for change in result['report']['changed_bytes']}
    assert offsets['0x200']['changed_bits'] == [0, 7]
    assert offsets['0xe8']['suspected_cache']
    assert not game.memory.writes
    assert not game.profile.document['Hotzones']
    assert len(list((tmp_path / 'mapping_captures').glob('*.json'))) == 1


def test_promoted_fields_work_with_live_undo_and_legacy_trc_sections(tmp_path):
    game = FakeGame(tmp_path)
    weight = game.profile.fields['vitals', 'Weight']
    weight.encode(game.memory.data, 200)
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    game.set_live(True)
    original = bytes(game.memory.data)
    game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'Weight', 'value': 201.5})
    game.undo()
    assert bytes(game.memory.data) == original
    old = {'players': [{'player_id': 'a', 'name': 'Player', 'metadata': {'trc_extra': {'Gear': {'Shoe Home': 'Known shoe'}, 'Hotzones': {'Close Left': 'Hot'}}}}]}
    canonical = game.profile.canonical_document(old)
    assert canonical['players'][0]['gear']['Shoe Home Style'] == 'Known shoe'
    assert canonical['players'][0]['hotzones']['Close Left'] == 'Hot'
    assert 'Gear' in canonical['players'][0]['metadata']['trc_extra']


def test_name_undo_restores_exact_original_bytes_including_unused_padding(tmp_path):
    game = FakeGame(tmp_path)
    first = game.profile.fields['vitals', 'First Name']
    last = game.profile.fields['vitals', 'Last Name']
    first.encode(game.memory.data, 'Tyrese')
    last.encode(game.memory.data, 'Maxey')
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    original = bytes(game.memory.data)
    game.set_live(True)
    game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'First Name', 'value': 'Tyrese Test'})
    assert first.decode(game.memory.data) == 'Tyrese Test'
    game.undo()
    assert bytes(game.memory.data) == original
    game.undo(redo=True)
    game.undo()
    assert bytes(game.memory.data) == original
