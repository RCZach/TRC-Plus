import hashlib
import json
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import pytest

from trace_app import signature_catalog
from trace_app.app import DEFAULT_PROFILE
from trace_app.fields import RecordProfile
from trace_app.mappings import SIGNATURE_ALIASES
from trace_app.roster import RosterError
from trace_app.trc import import_document, merge_trc_with_scope
from test_connections import FakeGame


BUILD = '6AD2E48C:36532000'


def test_bundled_enum_proofs_bind_exact_profile_layouts():
    catalog = json.loads((DEFAULT_PROFILE.parent / 'signature_values_2k27.json').read_text())
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    assert len(catalog['fields']) == 71 and len(catalog['enums']) == 53
    for enum, proof in catalog['enums'].items():
        table = b''.join(struct.pack('<III', zlib.crc32(symbol.encode()), value, 0)
                         for symbol, value in proof['values'].items())
        assert hashlib.sha256(table).hexdigest() == proof['table_sha256']
        names = enum.encode() + b'\0' + b''.join(symbol.encode() + b'\0' for symbol in proof['values'])
        assert hashlib.sha256(names).hexdigest() == proof['names_sha256']
        crc, flags, padding, count, size = struct.unpack('<5I', bytes.fromhex(proof['header_hex']))
        assert (crc, count, size) == (zlib.crc32(enum.encode()), len(proof['values']), 4)
        code = bytes.fromhex(proof['registration_hex'])
        args = [proof['registration_rva'] + 7 * i + 7 + struct.unpack_from('<i', code, 7 * i + 3)[0]
                for i in range(4)]
        assert args == [proof[k] for k in ('descriptor_rva', 'header_rva', 'table_rva', 'names_rva')]
    for name, binding in catalog['fields'].items():
        field = profile.fields['signatures', name]
        assert binding['layout'] == [field.offset, field.bits, field.shift]
        assert len(binding['properties']) >= 2
        for prop in binding['properties']:
            name_crc, type_crc, offset, size, flags, padding, descriptor = struct.unpack(
                '<IIIIQQQ', bytes.fromhex(prop['property_hex']))
            assert name_crc == prop['name_crc']
            assert type_crc == zlib.crc32(binding['enum'].encode())
            assert size == 4 and padding == 0
            assert offset * 8 + ((flags >> 16) & 255) == field.offset * 8 + field.shift
            assert (flags >> 8) & 255 == field.bits
            assert descriptor == 0x140000000 + catalog['enums'][binding['enum']]['descriptor_rva']


def test_native_names_are_build_field_and_layout_scoped():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    base = profile.fields['signatures', 'Jumpshot Base']
    assert signature_catalog.resolve(BUILD, base, 'Goran Dragic') == 197
    assert signature_catalog.resolve(BUILD, base, 'Kris Dunn') == 203
    assert signature_catalog.resolve(BUILD, base, 'Stephen Curry') == 172
    assert signature_catalog.resolve(BUILD, base, 'Shai Gilgeous-Alexander') >= 0
    for field, build in [(base, '6AA2013D:36558000'), (replace(base, offset=base.offset + 1), BUILD),
                         (replace(base, category='gear'), BUILD)]:
        with pytest.raises(RosterError, match='no unique native'):
            signature_catalog.resolve(build, field, 'Stephen Curry')
    with pytest.raises(RosterError):
        signature_catalog.resolve(BUILD, profile.fields['signatures', 'Signature Size-Up'], 'Steve Francis')
    # Default and None are distinct explicit dunk entries on this build.
    dunk = profile.fields['signatures', 'Dunk Package 2']
    assert signature_catalog.resolve(BUILD, dunk, 'None') == 166
    assert signature_catalog.resolve(BUILD, dunk, 'Default') == 0


def test_glossary_labels_resolve_through_current_native_symbols_only():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    layup = profile.fields['signatures', 'Layup Package']
    dunk = profile.fields['signatures', 'Dunk Package 3']
    assert signature_catalog.resolve(BUILD, layup, 'Kobe Bryant') == 15
    assert signature_catalog.resolve(BUILD, layup, 'Michael Jordan') == 52
    assert signature_catalog.resolve(BUILD, dunk, 'Elite Contact Dunks Off Two') == 156
    assert signature_catalog.resolve(BUILD, dunk, 'Back Scratching Rim Hangs') == 45
    assert signature_catalog.choices(BUILD, layup)['Kobe Bryant'] == 15
    assert 'Lup K Bryant' not in signature_catalog.choices(BUILD, layup)
    # Booker has a specific user-confirmed review. Initials are not expanded
    # generally, so unrelated unresolved labels remain blocked.
    assert signature_catalog.resolve(BUILD, layup, 'Devin Booker') == 11
    with pytest.raises(RosterError):
        signature_catalog.resolve(BUILD, layup, 'Jaylen Brown')


def test_accented_names_match_exports_and_conflicting_observations_stay_blocked(tmp_path, monkeypatch):
    game = configured_game(tmp_path)
    field = game.profile.fields['signatures', 'Layup Package']
    for spelling in ('Nikola Jokic', 'Nikola Jokić', 'Nikola Jokic\u0301'):
        assert signature_catalog.resolve(BUILD, field, spelling) == 51
    game.catalog.learn(BUILD, 'signatures', field.name, 'Nikola Jokić', 99, 'game-0')
    with pytest.raises(RosterError, match='disagree'):
        game.normalize_value('signatures', field.name, 'Nikola Jokic')
    assert not game.memory.writes
    document = json.loads(json.dumps(signature_catalog._document()))
    document['enums']['SIG_LAYUP']['labels']['Nikola Jokic'] = ['LUP_K_BRYANT']
    monkeypatch.setattr(signature_catalog, '_document', lambda: document)
    with pytest.raises(RosterError):
        signature_catalog.resolve(BUILD, field, 'Nikola Jokić')
    assert 'Nikola Jokić' not in signature_catalog.choices(BUILD, field)


def test_reviewed_harry_giles_spelling_is_field_scoped():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    assert signature_catalog.resolve(BUILD, profile.fields['signatures', 'Jumpshot Base'], 'Harry Giles') == 262
    assert signature_catalog.resolve(BUILD, profile.fields['signatures', 'Jumpshot Base'], 'Harry Giles III') == 262
    with pytest.raises(RosterError):
        signature_catalog.resolve(BUILD, profile.fields['signatures', 'Release 1'], 'Harry Giles')


def test_chew_gum_uses_native_boolean_property_and_preserves_neighbors(tmp_path):
    catalog = signature_catalog._document()
    primitive = catalog['primitives']['Chew Gum']
    assert primitive['layout'] == [0x10C, 1, 30] and primitive['type'] == 'bool32'
    assert len(primitive['properties']) == 2
    for prop in primitive['properties']:
        name_crc, type_crc, offset, size, packed, padding, descriptor = struct.unpack(
            '<IIIIQQQ', bytes.fromhex(prop['property_hex']))
        assert (name_crc, type_crc) == (zlib.crc32(b'GumChewer'), zlib.crc32(b'bool32'))
        assert (offset, size, (packed >> 8) & 255, (packed >> 16) & 255) == (0x10C, 4, 1, 30)
        assert padding == descriptor == 0
    game = configured_game(tmp_path)
    field = game.profile.fields['signatures', 'Chew Gum']
    assert signature_catalog.choices(BUILD, field) == {'Off': 0, 'On': 1}
    game.memory.data[0x10C:0x110] = b'\xff' * 4
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    before = bytes(game.memory.data)
    game.set_live(True)
    game.edit({'player_id': 'game-0', 'category': 'signatures', 'field': 'Chew Gum', 'value': 'Off'})
    assert game.memory.data[0x10F] == 0xBF
    game.undo()
    assert bytes(game.memory.data) == before
    with pytest.raises(RosterError):
        signature_catalog.resolve('OTHER:BUILD', field, 'Off')


def test_conflicting_glossary_labels_and_native_symbols_fail_closed(monkeypatch):
    document = json.loads(json.dumps(signature_catalog._document()))
    table = document['enums']['SIG_SHOT_JUMPER']
    table['labels']['Stephen Curry'] = ['STEPHEN_CURRY', 'LEBRON_JAMES']
    monkeypatch.setattr(signature_catalog, '_document', lambda: document)
    field = RecordProfile(json.loads(DEFAULT_PROFILE.read_text())).fields['signatures', 'Jumpshot Base']
    assert 'Stephen Curry' not in signature_catalog.choices(BUILD, field)
    with pytest.raises(RosterError):
        signature_catalog.resolve(BUILD, field, 'Stephen Curry')


def test_ambiguous_symbols_are_not_choices_or_resolvable(monkeypatch):
    document = json.loads(json.dumps(signature_catalog._document()))
    document['enums']['SIG_SHOT_JUMPER']['values']['STEPHEN-CURRY'] = 999
    monkeypatch.setattr(signature_catalog, '_document', lambda: document)
    field = RecordProfile(json.loads(DEFAULT_PROFILE.read_text())).fields['signatures', 'Jumpshot Base']
    assert 'Stephen Curry' not in signature_catalog.choices(BUILD, field)
    with pytest.raises(RosterError):
        signature_catalog.resolve(BUILD, field, 'Stephen Curry')


def configured_game(tmp_path):
    game = FakeGame(tmp_path, writes=True)
    game.memory.build = game.expected_build = BUILD
    game.identity = game.status()
    return game


def test_native_import_preview_apply_preserves_bits_and_exact_undo_redo(tmp_path):
    game = configured_game(tmp_path)
    fields = {name: game.profile.fields['signatures', name]
              for name in ('Jumpshot Base', 'Release 1', 'Release 2', 'Free Throw')}
    # Nonzero neighbors detect an accidental whole-word write.
    game.memory.data[0x408:0x420] = b'\xA5' * 24
    for field in fields.values():
        field.encode(game.memory.data, 0)
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    before = bytes(game.memory.data)
    player = {'player_id': 'game-0', 'name': 'Player', 'signatures': {
        'Jumpshot Base': 'Stephen Curry', 'Release 1': 'Oscar Robertson',
        'Release 2': 'Stephen Curry', 'Free Throw': 'Free Throw 25'}}
    preview = game.preview({'players': [player], 'teams': []})
    assert not game.memory.writes
    assert len(preview['changes']) == 4
    assert not any('no verified game ID' in warning for warning in preview['warnings'])
    expected = bytearray(before)
    for change in preview['changes']:
        fields[change['field']].encode(expected, change['value'])
    game.apply(preview['plan_id'])
    assert bytes(game.memory.data) == bytes(expected)
    game.undo()
    assert bytes(game.memory.data) == before
    game.undo(redo=True)
    assert bytes(game.memory.data) == bytes(expected)


def test_native_catalog_reaches_existing_users_and_conflicts_fail_closed(tmp_path):
    game = configured_game(tmp_path)
    assert game.field_values()['signatures']['Jumpshot Base']['Stephen Curry'] == 172
    assert game.normalize_value('signatures', 'Release Timing', 'Very Quick') == 4
    game.catalog.learn(BUILD, 'signatures', 'Jumpshot Base', 'Stephen Curry', 999, 'game-0')
    with pytest.raises(RosterError, match='disagree'):
        game.normalize_value('signatures', 'Jumpshot Base', 'Stephen Curry')
    assert not game.memory.writes


def test_screenshot_field_names_canonicalize_without_inventing_new_layouts():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    original = dict(profile.fields)
    for alias, name in SIGNATURE_ALIASES.items():
        assert ('signatures', name) in profile.fields
        assert profile.canonical_name('signatures', alias) == name
    for name in ('Aggressive Breakdown Combos', 'Escape Moves', 'Post Spin Shot', 'Dunk Emotion'):
        assert profile.canonical_name('signatures', name) == name
        assert ('signatures', name) not in profile.fields
    document = import_document({'Player': {'Signatures': {
        'Go-To Dunk Package': 'LeBron James', 'Crossover Combos': 'Stephen Curry',
        'Regular Breakdown Combos': 'Stephen Curry'}}})
    player = profile.canonical_document(document)['players'][0]
    assert player['signatures'] == {'Dunk Package 1': 'LeBron James', 'Iso Cross Combo': 'Stephen Curry',
                                    'Breakdown Combos': 'Stephen Curry'}
    assert profile.fields == original
    document['players'][0]['signatures']['Dunk Package 1'] = 'Michael Jordan'
    with pytest.raises(RosterError, match='conflicting values'):
        profile.canonical_document(document)


def test_alias_import_overwrites_target_slot_and_preserves_separate_dunk_slots(tmp_path):
    game = configured_game(tmp_path)
    first, second = (game.profile.fields['signatures', f'Dunk Package {n}'] for n in (1, 2))
    game.memory.data[first.offset:first.offset + 4] = b'\xA5' * 4
    first.encode(game.memory.data, 166)
    second.encode(game.memory.data, 78)
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    before = bytes(game.memory.data)
    target = {'players': [{'player_id': 'game-0', 'name': 'Player', 'signatures': {
        'Dunk Package 1': 166, 'Dunk Package 2': 78}}], 'teams': []}
    # This matches the existing API order: canonicalize the source before merge.
    source = game.profile.canonical_document(import_document({'Player': {'Signatures': {
        'Go-To Dunk Package': 'LeBron James', 'Crossover Combos': 'Stephen Curry',
        'Regular Breakdown Combos': 'Stephen Curry', 'Escape Moves': 'Paul George'}}}))
    merged, scope, warnings = merge_trc_with_scope(source, target)
    assert not warnings and merged['players'][0]['signatures']['Dunk Package 1'] == 'LeBron James'
    preview = game.preview(scope)
    assert {r['field'] for r in preview['changes']} == {'Dunk Package 1', 'Iso Cross Combo', 'Breakdown Combos'}
    assert any('Escape Moves: no enabled memory mapping' in warning for warning in preview['warnings'])
    assert not game.memory.writes
    game.apply(preview['plan_id'])
    assert first.decode(game.memory.data) == 102
    assert second.decode(game.memory.data) == 78
    assert game.profile.fields['signatures', 'Iso Cross Combo'].decode(game.memory.data) == 7
    game.undo()
    assert bytes(game.memory.data) == before


def test_conflicting_trc_source_skips_only_ambiguous_field_and_keeps_strict_preview(tmp_path):
    game = configured_game(tmp_path)
    first, second = (game.profile.fields['signatures', f'Dunk Package {n}'] for n in (1, 2))
    first.encode(game.memory.data, 166)
    second.encode(game.memory.data, 166)
    game.records['game-0'] = bytes(game.memory.data[:game.profile.stride])
    document = import_document({'Player': {'Signatures': {
        'Dunk Package 1': 'Elite Contact Dunks Off Two',
        'Go-To Dunk Package': 'Elite Contact Dunks Off One',
        'DunkPackage1': 'Elite Contact Dunks Off Two',
        'Dunk Package 2': 'Pro Contact Dunks Off Two'}}})
    original = json.dumps(document, sort_keys=True)
    with pytest.raises(RosterError, match='conflicting values'):
        game.profile.canonical_document(document)
    warnings = []
    source = game.profile.canonical_document(document, conflict_warnings=warnings)
    assert source['players'][0]['signatures'] == {'Dunk Package 2': 'Pro Contact Dunks Off Two'}
    assert len(warnings) == 1
    assert 'Elite Contact Dunks Off Two' in warnings[0] and 'Elite Contact Dunks Off One' in warnings[0]
    assert json.dumps(document, sort_keys=True) == original
    target = {'players': [{'player_id': 'game-0', 'name': 'Player', 'signatures': {
        'Dunk Package 1': 166, 'Dunk Package 2': 166}}], 'teams': []}
    merged, scope, _ = merge_trc_with_scope(source, target)
    assert merged['players'][0]['signatures']['Dunk Package 1'] == 166
    assert 'Dunk Package 1' not in scope['players'][0]['signatures']
    preview = game.preview(scope)
    assert not game.memory.writes
    assert [row['field'] for row in preview['changes']] == ['Dunk Package 2']
    game.apply(preview['plan_id'])
    assert first.decode(game.memory.data) == 166 and second.decode(game.memory.data) == 154


def test_equal_import_aliases_do_not_warn_or_skip():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    document = import_document({'Player': {'Signatures': {
        'Dunk Package 1': 'LeBron James', 'Go-To Dunk Package': 'LeBron James'}}})
    warnings = []
    result = profile.canonical_document(document, conflict_warnings=warnings)
    assert not warnings
    assert result['players'][0]['signatures'] == {'Dunk Package 1': 'LeBron James'}
