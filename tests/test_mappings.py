import copy
import json
import struct
from pathlib import Path

import pytest

from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.mappings import ValueCatalog, expand_profile
from trace_app.roster import RosterError, validate_roster
from trace_app.trc import merge_trc_with_scope
from test_connections import FakeGame


def test_numeric_vitals_limits_and_original_advanced_fields_stay_read_only():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    for name in ('Bust Percent', 'Boom Percent', 'Play for Winner', 'Financial Security', 'Loyalty'):
        field = profile.fields['vitals', name]
        field.encode(bytearray(profile.stride), 100)
        with pytest.raises(RosterError, match='supported field value'):
            field.encode(bytearray(profile.stride), 101)
    for name in ('Min Potential', 'Max Potential'):
        with pytest.raises(RosterError, match='supported field value'):
            profile.fields['vitals', name].encode(bytearray(profile.stride), 100)
    for name in ('MINIMUMPOTENTIAL', 'MAXIMUMPOTENTIAL', 'BUSTPERCENTAGE', 'BOOMPERCENTAGE',
                 'PLAYFORWINNER', 'FINANCIALSECURITY', 'LOYALTY'):
        assert not profile.fields['advanced', name].writable


def test_forced_nonstarter_uses_observed_on_value_and_reserved_states_are_not_editable():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    field = profile.fields['vitals', 'Forced Non-Starter']
    record = bytearray(profile.stride)
    field.encode(record, 2)
    assert record[0x357] == 8
    for value in (1, 3):
        with pytest.raises(RosterError, match='supported field value'):
            field.encode(record, value)
    dunk = profile.fields['vitals', 'Dominant Dunk Hand']
    dunk.encode(record, 2)
    assert dunk.decode(record) == 2
    with pytest.raises(RosterError, match='supported field value'):
        dunk.encode(record, 3)


def test_location_and_playtype_names_preserve_unnamed_existing_ids():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    record = bytearray(profile.stride)
    for category, name, value in [('vitals', 'FIBA Team', 12345), ('vitals', 'Play Type 1', 9)]:
        field = profile.fields[category, name]
        field.encode(record, value)
        assert profile.decode(record, '6AD2E48C:36532000')[category][name] == value
        assert field.allowed_values is None
    catalog = ValueCatalog(Path('config/field_values.json'))
    for field in ('High School', 'Birthplace'):
        assert catalog.resolve('6AD2E48C:36532000', 'vitals', field, 'Phoenix') == 87
        assert catalog.resolve('6AD2E48C:36532000', 'vitals', field, 'Pittsburgh') == 88
        assert 'Athens' not in catalog.values('6AD2E48C:36532000', 'vitals', field)


def test_injury_days_convert_observed_minutes_without_rounding_partial_days():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    for name, observed in [('Injury 1 Duration Days', [(7, 10080), (8, 11520)]),
                           ('Injury 2 Duration Days', [(10, 14400), (11, 15840)])]:
        field = profile.fields['vitals', name]
        for days, minutes in observed:
            record = bytearray([0xA5] * profile.stride)
            original = bytes(record)
            field.encode(record, days)
            assert field.decode(record) == days
            assert int.from_bytes(record[field.offset:field.offset+3], 'little') & 0xFFFFF == minutes
            mask = ((1 << field.bits) - 1) << (field.offset * 8)
            assert not ((int.from_bytes(original, 'little') ^ int.from_bytes(record, 'little')) & ~mask)
        with pytest.raises(RosterError):
            field.encode(record, 729)
        record[field.offset:field.offset+3] = (10081).to_bytes(3, 'little')
        assert field.decode(record) is None


def test_miscellaneous_durability_keeps_legacy_spelling_compatible(tmp_path):
    game = FakeGame(tmp_path)
    field = game.profile.fields['attributes', 'Miscellaneous Durability']
    document = {'players': [{'player_id': 'p', 'name': 'Test Player',
                             'attributes': {'Miscanellous Durability': 80}}], 'teams': []}
    canonical = game.profile.canonical_document(document)
    assert canonical['players'][0]['attributes'] == {'Miscellaneous Durability': 80}
    after, changes, warnings = game.profile.patch(bytes(game.profile.stride), canonical['players'][0])
    assert field.decode(after) == 80
    assert changes[0]['field'] == 'Miscellaneous Durability'
    document['players'][0]['attributes']['Miscellaneous Durability'] = 81
    with pytest.raises(RosterError, match='conflicting values'):
        game.profile.canonical_document(document)


def test_pass_vision_alias_uses_exact_build_raw_field_byte(tmp_path):
    game = FakeGame(tmp_path)
    field = game.profile.fields['attributes', 'Passing Vision']
    assert field.offset == 0x46E
    assert field.verified_build == '6AD2E48C:36532000'
    assert field.offset == game.profile.fields['advanced', 'PASSVISION'].offset + 2
    before = bytearray(game.profile.stride)
    field.encode(before, 86)
    before[0x46F] = 210
    source = {'players': [{'player_id': 'trc-1', 'name': 'Test Player',
                           'attributes': {'Pass Vision': 75}}], 'teams': []}
    canonical = game.profile.canonical_document(source)
    assert canonical['players'][0]['attributes'] == {'Passing Vision': 75}
    target = {'players': [{'player_id': 'game-1', 'name': 'Test Player',
                           'attributes': {'Passing Vision': 25}}], 'teams': []}
    merged, scope, merge_warnings = merge_trc_with_scope(canonical, target)
    assert merge_warnings == []
    assert merged['players'][0]['attributes'] == {'Passing Vision': 75}
    assert scope['players'][0]['attributes'] == {'Passing Vision': 75}
    after, changes, warnings = game.profile.patch(bytes(before), canonical['players'][0], build='6AD2E48C:36532000')
    assert warnings == []
    assert changes == [{'field': 'Passing Vision', 'category': 'attributes', 'old': 86, 'value': 75}]
    assert after[0x46E] == (75 - 25) * 3
    assert after[0x46F] == before[0x46F]
    assert after[:0x46E] == before[:0x46E]
    assert after[0x470:] == before[0x470:]
    game_request = copy.deepcopy(canonical)
    game_request['players'][0]['player_id'] = 'game-0'
    preview = game.preview(game_request)
    assert preview['changes'] == []
    assert any('Passing Vision: no enabled memory mapping' in warning for warning in preview['warnings'])
    assert not game.memory.writes
    source['players'][0]['attributes']['Passing Vision'] = 76
    with pytest.raises(RosterError, match='conflicting values'):
        game.profile.canonical_document(source)


def test_bundled_shoe_catalog_is_build_and_field_scoped():
    catalog = ValueCatalog(Path('config/field_values.json'))
    build = '6AD2E48C:36532000'
    values = catalog.values(build, 'gear', 'Shoe Home Style')
    assert len(values) >= 559
    assert catalog.resolve(build, 'gear', 'Shoe Home Style', 'Air Jordan III') == 5002
    assert catalog.resolve(build, 'gear', 'Shoe Home Style', 'Air Jordan 2010') == 5024
    assert all(type(entry['value']) is int and 0 <= entry['value'] < 8192 for entry in values.values())
    for name in ('PG 2.5', 'UA Flow Future X', 'Puma MB.04', 'New Balance 1906R'):
        with pytest.raises(RosterError, match='no verified game ID'):
            catalog.resolve(build, 'gear', 'Shoe Home Style', name)
    assert not catalog.values(build, 'gear', 'Shoe Away Style')
    with pytest.raises(RosterError, match='no verified game ID'):
        catalog.resolve('OTHER:BUILD', 'gear', 'Shoe Home Style', 'Air Jordan III')


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
    assert len(profile.document['Hotzones']) == 14
    assert profile.fields['hotzones', 'Under Basket'].verified_build == '6AD2E48C:36532000'


def test_under_basket_hotzone_states_preserve_other_bits_and_require_matching_build():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    field = profile.fields['hotzones', 'Under Basket']
    # Three independently observed byte states: Hot=22, Cold=20, Neutral=21.
    for value, expected in [(0, 20), (1, 21), (2, 22)]:
        record = bytearray(profile.stride)
        record[0x1CC] = 22
        field.encode(record, value)
        assert record[0x1CC] == expected
        assert profile.decode(record, '6AD2E48C:36532000')['hotzones']['Under Basket'] == value
        assert profile.decode(record, 'OTHER:BUILD')['hotzones'] == {}
    with pytest.raises(RosterError, match='supported field value'):
        field.encode(bytearray(profile.stride), 3)
    record[0x1CC] = 23
    assert 'Under Basket' not in profile.decode(record, '6AD2E48C:36532000')['hotzones']
    player = {'hotzones': {'Under Basket': 2}}
    after, changes, warnings = profile.patch(bytes(profile.stride), player, build='OTHER:BUILD')
    assert after == bytes(profile.stride) and not changes and warnings


def test_under_basket_live_write_refuses_other_build(tmp_path):
    game = FakeGame(tmp_path, writes=True)
    game.set_live(True)
    with pytest.raises(RosterError, match='not mapped for the running game build'):
        game.edit({'player_id': 'game-0', 'category': 'hotzones', 'field': 'Under Basket', 'value': 2})
    assert not game.memory.writes


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
    original_profile = copy.deepcopy(game.profile.document)
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
    assert game.profile.document == original_profile
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
