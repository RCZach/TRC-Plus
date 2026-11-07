import copy
import json
import struct
from dataclasses import replace
from threading import Thread
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from trace_app.app import DEFAULT_PROFILE, create_server
from trace_app.fields import Field, RecordProfile
from trace_app.game import (GameConnection, COMMUNITY_ROOT_RVA,
                            COMMUNITY_ROSTER_POINTER_OFFSET,
                            COMMUNITY_PLAYER_COUNT_OFFSET, COMMUNITY_PLAYER_TABLE_OFFSET,
                            OBSERVED_PLAYER_POINTERS)
from trace_app.roster import RosterError, demo_roster
from trace_app.trc import (BADGES_2K25_TO_2K27, convert_2k25_roster_badges,
                           import_document, merge_trc, merge_trc_with_scope)


SOURCE = {'Marcus Bennett': {'Attributes': {'Driving Layup': 95},
                            'Badges': {'Boxout Beast': 3},
                            'Tendencies': {'Driving Layup Tendency': 80},
                            'Signatures': {'Release 1': 'Oscar Robertson'},
                            'Hotzones': {'Close Left': 'Hot'}, 'Gear': {}, 'Accessories': {}}}


def test_trc_import_preserves_names_extra_sections_and_stable_ids():
    roster = import_document(SOURCE)
    player = roster['players'][0]
    assert player['attributes']['Driving Layup'] == 95
    assert player['badges']['Boxout Beast'] == 3
    assert player['signatures']['Release 1'] == 'Oscar Robertson'
    assert player['hotzones']['Close Left'] == 'Hot'
    assert import_document(SOURCE) == roster
    assert 'player_id' not in SOURCE['Marcus Bennett']


def test_merge_keeps_game_ids_and_teams_and_rejects_ambiguous_names():
    target = demo_roster()
    merged, warnings = merge_trc(SOURCE, target)
    player = merged['players'][0]
    assert player['player_id'] == target['players'][0]['player_id']
    assert player['team_id'] == target['players'][0]['team_id']
    assert player['attributes']['Speed'] == target['players'][0]['attributes']['Speed']
    assert player['attributes']['Driving Layup'] == 95
    assert not warnings
    duplicate = copy.deepcopy(target['players'][0])
    duplicate['player_id'] = 'another-id'
    target['players'].append(duplicate)
    merged, warnings = merge_trc(SOURCE, target)
    assert merged == target
    assert 'ambiguous' in warnings[0]
    _, warnings = merge_trc({'Unknown Player': SOURCE['Marcus Bennett']}, target)
    assert 'not found' in warnings[0]


def test_multiword_last_names_and_suffix_periods_merge_only_unique_players():
    target = demo_roster()
    template = copy.deepcopy(target['players'][0])
    target['players'] = []
    for index, name in enumerate(('Zachary James Jr.', 'Colton Fishscale Barkberg',
                                  'Peligro Danger II')):
        player = copy.deepcopy(template)
        player['player_id'], player['name'] = f'game-{index}', name
        target['players'].append(player)
    source = {name: {'Attributes': {'Driving Layup': 80 + index}}
              for index, name in enumerate(('Zachary James Jr', 'Colton Fishscale Barkberg',
                                            'Peligro Danger Ii'))}
    merged, warnings = merge_trc(source, target)
    assert not warnings
    assert [player['attributes']['Driving Layup'] for player in merged['players']] == [80, 81, 82]
    duplicate = copy.deepcopy(target['players'][0])
    duplicate['player_id'], duplicate['name'] = 'game-3', 'Zachary James Jr'
    target['players'].append(duplicate)
    merged, warnings = merge_trc(source, target)
    assert any('Zachary James Jr: ambiguous name' in warning for warning in warnings)
    assert merged['players'][0]['attributes'] == target['players'][0]['attributes']


def test_trc_sync_scope_contains_only_supplied_fields_and_matched_players():
    target = demo_roster()
    target['teams'][0]['coaching'] = {'values': {'Tempo': 85}}
    target['players'][0]['attributes']['Speed'] = 90
    target['players'][0]['vitals']['Weight'] = 220
    source = {'Marcus Bennett': {'Attributes': {'Driving Layup': 95},
                                 'Badges': {'Float Game': 2}}}
    merged, scope, warnings = merge_trc_with_scope(source, target)
    assert not warnings
    assert merged['players'][0]['attributes']['Speed'] == 90
    assert merged['players'][0]['vitals']['Weight'] == 220
    assert scope['players'][0]['player_id'] == target['players'][0]['player_id']
    assert scope['players'][0]['attributes'] == {'Driving Layup': 95}
    assert scope['players'][0]['badges'] == {'Float Game': 2}
    assert scope['players'][0]['vitals'] == {}
    assert scope['players'][1]['attributes'] == {}
    assert 'coaching' not in scope['teams'][0]


def test_all_six_2k25_badges_map_to_selected_2k27_targets():
    source = {'Marcus Bennett': {'Badges': dict.fromkeys(BADGES_2K25_TO_2K27, 3)}}
    target = demo_roster()
    target['players'][0]['badges'].update({'Ghost Stepper': 2, 'Crasher': 1,
                                          'Static Middy': 4, 'Smooth Operator': 2})
    merged, scope, warnings = merge_trc_with_scope(source, target)
    assert not warnings
    expected = dict.fromkeys(BADGES_2K25_TO_2K27.values(), 3)
    assert scope['players'][0]['badges'] == expected
    assert merged['players'][0]['badges'] == {**target['players'][0]['badges'], **expected}
    assert not set(BADGES_2K25_TO_2K27) & merged['players'][0]['badges'].keys()
    assert scope['players'][1]['badges'] == {}


def test_converted_badges_preserve_higher_existing_tiers_and_ignore_old_zero():
    target = demo_roster()
    target['players'][0]['badges'].update({'Boxout Boss': 4, 'Seatbelt': 2,
                                          'Post Spin Catalyst': 3, 'Possession Closer': 1,
                                          'Set and Fire': 5, 'Arc Cadence': 2})
    source = {'Marcus Bennett': {'Badges': {
        'Boxout Beast': 3, 'On-Ball Menace': 0, 'Post-Up Poet': 2,
        'Rebound Chaser': 4, 'Set Shot Specialist': 1, 'Shifty Shooter': 3}}}
    merged, scope, _ = merge_trc_with_scope(source, target)
    assert merged['players'][0]['badges'] == {**target['players'][0]['badges'],
                                              'Possession Closer': 4, 'Arc Cadence': 3}
    assert scope['players'][0]['badges'] == {
        'Boxout Boss': 4, 'Post Spin Catalyst': 3, 'Possession Closer': 4,
        'Set and Fire': 5, 'Arc Cadence': 3}
    assert convert_2k25_roster_badges(import_document(source))['players'][0]['badges'] == {
        'Boxout Boss': 3, 'Post Spin Catalyst': 2, 'Possession Closer': 4,
        'Set and Fire': 1, 'Arc Cadence': 3}


def test_explicit_2k27_badge_value_wins_when_source_contains_both_names():
    source = {'Marcus Bennett': {'Badges': {'Boxout Beast': 4, 'Boxout Boss': 1}}}
    merged, scope, _ = merge_trc_with_scope(source, demo_roster())
    assert scope['players'][0]['badges'] == {'Boxout Boss': 1}
    assert merged['players'][0]['badges']['Boxout Boss'] == 1


def test_verified_hotzone_names_use_profile_options_without_learning_game_ids():
    game = GameConnection.__new__(GameConnection)
    game.profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8')))
    game.identity = {'build': '6AD2E48C:36532000'}
    game.catalog = type('NoCatalog', (), {'resolve': lambda *args: pytest.fail('hotzones must not use learned IDs')})()
    before = bytes(game.profile.stride)
    fields = [item['name'] for item in game.profile.document['Hotzones']]
    after, changes, warnings = game.profile.patch(
        before, {'hotzones': {name: ' Neutral ' for name in fields}},
        game.normalize_value, game.identity['build'])
    assert warnings == []
    assert len(changes) == 14
    assert all(change['value'] == 1 for change in changes)
    assert all(game.profile.fields['hotzones', name].decode(after) == 1 for name in fields)
    assert game.normalize_value('hotzones', 'Under Basket', 'Cold') == 0
    assert game.normalize_value('hotzones', 'Under Basket', 'Hot') == 2
    with pytest.raises(RosterError, match='choose a verified hot-zone value'):
        game.normalize_value('hotzones', 'Under Basket', 'Unknown')
    game.identity = {'build': 'another-build'}
    with pytest.raises(RosterError, match='not verified for this game build'):
        game.normalize_value('hotzones', 'Under Basket', 'Hot')


def test_rating_and_cross_byte_badge_encoding_preserve_neighbor_bits():
    rating = Field('attributes', 'Driving Layup', 0, 8, 0)
    for value in (25, 80, 99):
        record = bytearray(1)
        rating.encode(record, value)
        assert record[0] == (value - 25) * 3
        assert rating.decode(record) == value
    for value in (0, 24, 100, True, '99'):
        with pytest.raises(RosterError):
            rating.encode(bytearray(1), value)
    badge = Field('badges', 'Cross byte', 0, 3, 7)
    original = bytes([0x55, 0xAA, 0x81])
    record = bytearray(original)
    badge.encode(record, 5)
    assert badge.decode(record) == 5
    mask = 7 << 7
    assert int.from_bytes(record, 'little') & ~mask == int.from_bytes(original, 'little') & ~mask


def test_full_profile_patching_and_named_signature_skip():
    profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text()))
    assert ('advanced', 'POINTS') in profile.ambiguous
    assert ('advanced', 'POINTS') not in profile.fields
    before = bytes(profile.stride)
    player = import_document(SOURCE)['players'][0]
    after, changes, warnings = profile.patch(before, player)
    assert profile.fields['attributes', 'Driving Layup'].decode(after) == 95
    assert profile.fields['tendencies', 'Driving Layup Tendency'].decode(after) == 80
    assert len(changes) == 2
    assert any('Boxout Beast' in warning for warning in warnings)
    assert any('numeric game ID' in warning for warning in warnings)
    field = profile.fields['signatures', 'Release 1']
    assert field.decode(after) == field.decode(before)


class FakeMemory:
    def __init__(self, profile):
        self.path = Path('NBA2K27.exe')
        self.pid, self.created, self.module_base, self.build = 1, 100, 0x100000, '123:456'
        self.base = 0x200000
        self.profile = profile
        self.data = bytearray(profile.stride * 3)
        self.writes = []
        self.fail_write = None
        self.partial_failure = False
        self.running = True
        self.write_requests = []

    def open(self, writable=False):
        self.write_requests.append(writable)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def alive(self):
        return self.running

    def read(self, address, size):
        if address == self.module_base + self.profile.pointer_offset:
            return struct.pack('<Q', self.base)
        offset = address - self.base
        if offset < 0 or offset + size > len(self.data):
            raise RosterError('Unreadable fake memory.')
        return bytes(self.data[offset:offset + size])

    def write(self, address, data):
        self.writes.append((address, data))
        if self.fail_write == len(self.writes):
            if self.partial_failure:
                offset = address - self.base
                self.data[offset:offset + 1] = data[:1]
            raise RosterError('Simulated write failure.')
        offset = address - self.base
        self.data[offset:offset + len(data)] = data


class FakeGame(GameConnection):
    def __init__(self, tmp_path, writes=False):
        super().__init__(json.loads(DEFAULT_PROFILE.read_text()), enable_writes=writes,
                         expected_build='123:456', audit_path=tmp_path / 'audit.jsonl', values_path=tmp_path / 'values.json')
        self.memory = FakeMemory(self.profile)
        self.identity = self.status()
        self.records = {'game-0': bytes(self.profile.stride)}


def game_document():
    source = import_document(SOURCE)
    source['players'][0]['player_id'] = 'game-0'
    return source


@pytest.mark.parametrize('root', [0, 0xFFFF, 0x5F54534F4F425F48])
def test_diagnostics_stops_at_invalid_root_without_dereferencing(tmp_path, root):
    game = FakeGame(tmp_path)
    memory = game.memory
    reads = []
    slots = {
        memory.module_base + game.profile.pointer_offset: struct.pack('<Q', 0),
        memory.module_base + COMMUNITY_ROOT_RVA: struct.pack('<Q', root),
    }

    def read(address, size):
        reads.append((address, size))
        assert address in slots, 'Diagnostics followed an invalid pointer'
        return slots[address]

    memory.read = read
    report = game.diagnostics()
    assert report['read_only'] is True
    assert report['probes']['profile_pointer_slot']['valid_pointer'] is False
    assert report['probes']['community_root_pointer']['valid_pointer'] is False
    assert 'lookup stops here' in report['probes']['community_root_pointer']['reason']
    assert 'community_roster_pointer' not in report['probes']
    assert len(reads) == 2
    assert game.status()['base'] == 0
    assert not any(memory.write_requests)
    assert not memory.writes


def test_diagnostics_keeps_valid_fallback_path_read_only(tmp_path):
    game = FakeGame(tmp_path)
    memory = game.memory
    root, roster, table = 0x300000, 0x400000, 0x500000
    slots = {
        memory.module_base + game.profile.pointer_offset: struct.pack('<Q', 0),
        memory.module_base + COMMUNITY_ROOT_RVA: struct.pack('<Q', root),
        root + COMMUNITY_ROSTER_POINTER_OFFSET: struct.pack('<Q', roster),
        roster + COMMUNITY_PLAYER_COUNT_OFFSET: struct.pack('<I', 100),
        roster + COMMUNITY_PLAYER_TABLE_OFFSET: struct.pack('<Q', table),
    }

    def read(address, size):
        if address == table:
            return bytes(size)  # Readable bytes alone do not prove a roster.
        return slots[address]

    memory.read = read
    report = game.diagnostics()
    assert report['probes']['community_root_pointer']['valid_pointer'] is True
    assert report['probes']['community_player_table']['validated'] is False
    assert 'sample_players' not in report
    assert not any(memory.write_requests)
    assert not memory.writes


@pytest.mark.parametrize('failure', [None, 'build', 'disagreement', 'null', 'unreadable', 'names', 'layout', 'field_layout', 'injury_inactive', 'name_layout'])
def test_observed_build_lookup_and_verified_field_write_guards(tmp_path, failure):
    game = FakeGame(tmp_path, writes=True)
    memory = game.memory
    memory.build = '6AD2E48C:36532000'
    game.expected_build = memory.build
    game.enable_writes = False
    offsets = OBSERVED_PLAYER_POINTERS[memory.build.casefold()]
    memory.data = bytearray(game.profile.stride * 129)
    for index in range(128):
        start = index * game.profile.stride
        memory.data[start + 0x108:start + 0x10C] = struct.pack('<f', 190.0)
        for offset, value in ((0, f'Player{index}'), (0x28, 'Test')):
            raw = value.encode('utf-16-le')
            memory.data[start + offset:start + offset + len(raw)] = raw
    for key, value in [(('vitals', 'Number'), 10),
                       (('vitals', 'Birth Month'), 5),
                       (('vitals', 'Secondary Position'), 5),
                       (('vitals', 'FIBA Team'), 65535),
                       (('vitals', 'High School'), 87),
                       (('vitals', 'Birthplace'), 86),
                       (('vitals', 'Min Potential'), 81),
                       (('vitals', 'Max Potential'), 93),
                       (('gear', 'Shoe Home Style'), 5024),
                       (('gear', 'Shoe Away Style'), 123),
                       (('accessories', 'Headband'), 1)]:
        game.profile.fields[key].encode(memory.data, value)
    for key, value in [(('advanced', 'INJURY1TYPE'), 1), (('advanced', 'INJURY1STATUS'), 4),
                       (('advanced', 'INJURY2TYPE'), 3), (('advanced', 'INJURY2STATUS'), 1),
                       (('vitals', 'Injury 1 Duration Days'), 8), (('vitals', 'Injury 2 Duration Days'), 11)]:
        replace(game.profile.fields[key], writable=True).encode(memory.data, value)
    if failure == 'injury_inactive':
        replace(game.profile.fields['advanced', 'INJURY1TYPE'], writable=True).encode(memory.data, 0)
    original_read = memory.read

    def read(address, size):
        if address == memory.module_base + 0xAC7B9A0:
            raise AssertionError('Roster-specific editor reference must not be used')
        if address == memory.module_base + game.profile.pointer_offset:
            return struct.pack('<Q', 0)
        if address == memory.module_base + COMMUNITY_ROOT_RVA:
            return struct.pack('<Q', 0)
        if address in {memory.module_base + offset for offset in offsets}:
            if address == memory.module_base + offsets[-1]:
                if failure == 'unreadable':
                    raise RosterError('Unreadable observation')
                if failure == 'disagreement':
                    return struct.pack('<Q', memory.base + game.profile.stride)
                if failure == 'null':
                    return bytes(8)
            return struct.pack('<Q', memory.base)
        return original_read(address, size)

    memory.read = read
    if failure == 'build':
        memory.build = 'OTHER:BUILD'
    if failure == 'names':
        memory.data[:] = bytes(len(memory.data))
    if failure == 'layout':
        game.profile.stride += 8
    if failure == 'field_layout':
        game.profile.fields['attributes', 'Driving Layup'] = Field('attributes', 'Driving Layup', 0x43D, 8, 0)
    if failure == 'name_layout':
        original = game.profile.fields['advanced', 'FIRSTLASTNAMESID']
        game.profile.fields['advanced', 'FIRSTLASTNAMESID'] = replace(original, offset=original.offset+1)
    status = game.status()
    assert status['writes_enabled'] is False
    if failure is None:
        assert status['base'] == memory.base
        assert status['array_count'] is None
        assert status['array_source'] == 'validated build references'
        loaded = game.load()
        assert len(loaded['roster']['players']) == 128
        assert game.diagnostics()['observed_build_lookup']['validated'] is True
        document = copy.deepcopy(loaded['roster'])
        document['players'][0]['attributes'].update({'Driving Layup': 26, 'Speed': 50, 'Strength': 50})
        document['players'][0]['vitals']['Face Type'] = 1
        preview = game.preview(document)
        assert {change['field'] for change in preview['changes']} == {'Driving Layup', 'Speed', 'Strength'}
        assert any('Face Type: read only' in warning for warning in preview['warnings'])
        expected_fields = {(f.category, f.name) for f in game.profile.fields.values()
                           if f.writable and (f.category in {'attributes', 'tendencies', 'badges', 'signatures', 'hotzones'}
                                              or (f.category, f.name) in {('vitals', 'Weight'), ('vitals', 'Number'),
                                                                         ('vitals', 'First Name'), ('vitals', 'Last Name'),
                                                                         ('vitals', 'Birth Day'), ('vitals', 'Birth Year'),
                                                                         ('vitals', 'Years Pro'), ('vitals', 'Peak Age'),
                                                                         ('vitals', 'Peak End Age'),
                                                                         ('vitals', 'Min Potential'), ('vitals', 'Max Potential'),
                                                                         ('vitals', 'Bust Percent'), ('vitals', 'AVG Percent'), ('vitals', 'Boom Percent'),
                                                                         ('vitals', 'Play for Winner'), ('vitals', 'Financial Security'),
                                                                         ('vitals', 'Loyalty'),
                                                                         ('vitals', 'Birth Month'), ('vitals', 'Dominant Hand'),
                                                                         ('vitals', 'Position'), ('vitals', 'Secondary Position'),
                                                                         ('vitals', 'Dominant Dunk Hand'), ('vitals', 'Forced Non-Starter'),
                                                                         ('vitals', 'Play Initiator'),
                                                                         ('vitals', 'FIBA Team'), ('vitals', 'High School'),
                                                                         ('vitals', 'Birthplace'), ('vitals', 'Play Type 1'),
                                                                         ('vitals', 'Play Type 2'), ('vitals', 'Play Type 3'),
                                                                         ('vitals', 'Play Type 4'),
                                                                         ('vitals', 'Injury 1 Duration Days'),
                                                                         ('vitals', 'Injury 2 Duration Days'),
                                                                         ('gear', 'Shoe Home Style'),
                                                                         ('accessories', 'Headband'),
                                                                         ('hotzones', 'Under Basket')})}
        assert {tuple(key) for key in status['writable_fields']} == expected_fields
        assert not any(memory.write_requests)
        assert not memory.writes
        assert game.set_live(True)['status']['writes_enabled'] is True
        initial = bytes(memory.data)
        game.edit({'player_id': 'game-0', 'category': 'attributes', 'field': 'Driving Layup', 'value': 26})
        assert game.profile.fields['attributes', 'Driving Layup'].decode(memory.data) == 26
        game.undo()
        assert bytes(memory.data) == initial
        for category, name, value in [('attributes', 'Speed', 78),
                                       ('attributes', 'Strength', 50),
                                       ('tendencies', 'Driving Layup Tendency', 71),
                                       ('badges', 'Rise Up', 1),
                                       ('signatures', 'Jumpshot Base', 203),
                                       ('vitals', 'Weight', 191.0),
                                       ('vitals', 'Number', 90),
                                       ('vitals', 'Birth Day', 14),
                                       ('vitals', 'Birth Month', 6),
                                       ('vitals', 'Position', 1),
                                       ('vitals', 'Secondary Position', 2),
                                       ('vitals', 'Dominant Hand', 1),
                                       ('vitals', 'Dominant Dunk Hand', 1),
                                       ('vitals', 'Dominant Dunk Hand', 2),
                                       ('vitals', 'Forced Non-Starter', 2),
                                       ('vitals', 'Play Initiator', 1),
                                       ('vitals', 'FIBA Team', 69),
                                       ('vitals', 'High School', 88),
                                       ('vitals', 'Birthplace', 87),
                                       ('vitals', 'Play Type 1', 2),
                                       ('vitals', 'Play Type 2', 14),
                                       ('vitals', 'Play Type 3', 15),
                                       ('vitals', 'Play Type 4', 5),
                                       ('vitals', 'Injury 1 Duration Days', 9),
                                       ('vitals', 'Injury 2 Duration Days', 12),
                                       ('vitals', 'Birth Year', 1979),
                                       ('vitals', 'Years Pro', 13),
                                       ('vitals', 'Peak Age', 26),
                                       ('vitals', 'Peak End Age', 29),
                                       ('vitals', 'Min Potential', 82),
                                       ('vitals', 'Max Potential', 94),
                                       ('vitals', 'Bust Percent', 2),
                                       ('vitals', 'AVG Percent', 91),
                                       ('vitals', 'Boom Percent', 8),
                                       ('vitals', 'Play for Winner', 75),
                                       ('vitals', 'Financial Security', 54),
                                       ('vitals', 'Loyalty', 83),
                                       ('gear', 'Shoe Home Style', 5002),
                                       ('accessories', 'Headband', 0),
                                       ('hotzones', 'Under Basket', 2)] + [('hotzones', item['name'], 2) for item in game.profile.document['Hotzones'][1:]]:
            game.edit({'player_id': 'game-0', 'category': category, 'field': name, 'value': value})
            field = game.profile.fields[category, name]
            assert field.decode(memory.data) == value
            # The transaction may change only this field's verified bits.
            bit_mask = ((1 << field.bits) - 1) << (field.offset * 8 + field.shift)
            assert ((int.from_bytes(initial, 'little') ^ int.from_bytes(memory.data, 'little')) & ~bit_mask) == 0
            game.undo()
            assert bytes(memory.data) == initial
        for name, value in [('First Name', 'Tester'), ('Last Name', 'Example')]:
            game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': name, 'value': value})
            assert game.identity == game.status()
            flag = 'FIRSTNAMEVETTED' if name == 'First Name' else 'LASTNAMEVETTED'
            assert game.profile.fields['advanced', flag].decode(memory.data) == 1
            assert game.profile.fields['advanced', 'FIRSTLASTNAMESID'].decode(memory.data) == 65535
            game.undo()
            assert bytes(memory.data) == initial
            assert game.identity == game.status()
            game.undo(redo=True)
            assert game.identity == game.status()
            game.undo()
            assert bytes(memory.data) == initial
        named = copy.deepcopy(loaded['roster'])
        named['players'][0]['vitals'].update({'First Name': 'Batch', 'Last Name': 'Renamed'})
        game.apply(game.preview(named)['plan_id'])
        assert game.identity == game.status()
        game.undo()
        assert bytes(memory.data) == initial
        # A partial name write must roll back its characters and companions.
        memory.fail_write = len(memory.writes) + 2
        memory.partial_failure = True
        with pytest.raises(RosterError, match='rolled-back'):
            game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'First Name', 'value': 'Failure'})
        assert bytes(memory.data) == initial
        memory.fail_write = None
        memory.partial_failure = False
        game.load()
        game.set_live(True)
        write_count = len(memory.writes)
        for name in ('Injury 1 Duration Days', 'Injury 2 Duration Days'):
            with pytest.raises(RosterError, match='Create or clear injuries'):
                game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': name, 'value': 0})
        assert len(memory.writes) == write_count
        with pytest.raises(RosterError, match='not been verified'):
            game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'Face Type', 'value': 1})
        assert len(memory.writes) == write_count
        # The game can overwrite the roster in place without moving its array.
        memory.data[:2] = 'X'.encode('utf-16-le')
        with pytest.raises(RosterError, match='connection changed'):
            game.edit({'player_id': 'game-1', 'category': 'attributes', 'field': 'Driving Layup', 'value': 26})
        assert len(memory.writes) == write_count
        game.load()
        game.set_live(True)
        original_write = memory.write
        def external_roster_change(address, data):
            original_write(address, data)
            memory.data[game.profile.stride:game.profile.stride+2] = 'Y'.encode('utf-16-le')
        memory.write = external_roster_change
        with pytest.raises(RosterError, match='rollback-failed'):
            game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'First Name', 'value': 'External'})
        assert game.identity is None
    elif failure == 'name_layout':
        assert status['base'] == memory.base
        assert ['vitals', 'First Name'] not in status['writable_fields']
        assert ['vitals', 'Last Name'] not in status['writable_fields']
        game.load()
        game.set_live(True)
        with pytest.raises(RosterError, match='not been verified'):
            game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'First Name', 'value': 'Blocked'})
        assert not memory.writes
    elif failure == 'injury_inactive':
        assert status['base'] == memory.base
        game.load()
        game.set_live(True)
        with pytest.raises(RosterError, match='Create or clear injuries'):
            game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': 'Injury 1 Duration Days', 'value': 9})
        assert not memory.writes
    elif failure == 'field_layout':
        assert status['base'] == memory.base
        assert ['attributes', 'Driving Layup'] not in status['writable_fields']
        assert ['attributes', 'Strength'] not in status['writable_fields']
        assert ['attributes', 'Speed'] in status['writable_fields']
        game.load()
        game.set_live(True)
        with pytest.raises(RosterError, match='not been verified'):
            game.edit({'player_id': 'game-0', 'category': 'attributes', 'field': 'Driving Layup', 'value': 26})
        assert not memory.writes
    else:
        assert status['base'] == 0
        assert not any(memory.write_requests)
        assert not memory.writes


def test_preview_is_read_only_and_reviewed_apply_does_not_enable_live_editing(tmp_path):
    game = FakeGame(tmp_path)
    preview = game.preview(game_document())
    assert len(preview['changes']) == 2
    assert preview['can_apply'] and not preview['writes_enabled']
    assert not game.memory.writes
    assert not any(game.memory.write_requests)
    assert game.apply(preview['plan_id'])['applied'] == 2
    assert game.memory.writes
    assert not game.live_enabled and not game.enable_writes
    assert not game.identity['writes_enabled'] and not game.status()['writes_enabled']
    with pytest.raises(RosterError, match='Start live editing'):
        game.edit({'player_id': 'game-0', 'category': 'attributes', 'field': 'Driving Layup', 'value': 96})
    game = FakeGame(tmp_path, writes=True)
    preview = game.preview(game_document())
    assert game.apply(preview['plan_id'])['applied'] == 2
    assert game.memory.writes
    assert game.profile.fields['attributes', 'Driving Layup'].decode(game.memory.data) == 95
    assert game.profile.fields['tendencies', 'Driving Layup Tendency'].decode(game.memory.data) == 80
    assert json.loads(game.audit_path.read_text().splitlines()[0])['outcome'] == 'started'
    with pytest.raises(RosterError, match='expired'):
        game.apply(preview['plan_id'])
    assert not game.preview(game_document())['changes']


def test_reviewed_apply_rejects_changed_game_before_authorizing_writes(tmp_path):
    game = FakeGame(tmp_path)
    preview = game.preview(game_document())
    game.memory.build = 'DIFFERENT:BUILD'
    with pytest.raises(RosterError, match='Game connection changed'):
        game.apply(preview['plan_id'])
    assert not game.enable_writes and not game.live_enabled
    assert not game.memory.writes


def test_failed_reviewed_apply_does_not_leave_writes_authorized(tmp_path):
    game = FakeGame(tmp_path)
    original = bytes(game.memory.data)
    preview = game.preview(game_document())
    game.memory.fail_write = 1
    with pytest.raises(RosterError, match='rolled-back'):
        game.apply(preview['plan_id'])
    assert not game.enable_writes and not game.live_enabled
    assert game.identity is None
    assert bytes(game.memory.data) == original


@pytest.mark.parametrize('identity', ['pid', 'created', 'base', 'build'])
def test_game_identity_change_blocks_writes(tmp_path, identity):
    game = FakeGame(tmp_path, writes=True)
    preview = game.preview(game_document())
    current = getattr(game.memory, identity)
    setattr(game.memory, identity, current + 1 if isinstance(current, int) else '999:999')
    with pytest.raises(RosterError):
        game.apply(preview['plan_id'])
    assert not game.memory.writes


def test_expired_plan_and_stale_record_block_writes(tmp_path):
    game = FakeGame(tmp_path, writes=True)
    preview = game.preview(game_document())
    game.plans[preview['plan_id']]['created'] -= 301
    with pytest.raises(RosterError, match='expired'):
        game.apply(preview['plan_id'])
    assert not game.memory.writes
    preview = game.preview(game_document())
    game.memory.data[0] = 1
    with pytest.raises(RosterError, match='Player record changed'):
        game.apply(preview['plan_id'])
    assert not game.memory.writes


@pytest.mark.parametrize('partial_failure', [False, True])
def test_failed_write_restores_earlier_changes_and_invalidates_snapshot(tmp_path, partial_failure):
    game = FakeGame(tmp_path, writes=True)
    original = bytes(game.memory.data)
    preview = game.preview(game_document())
    game.memory.fail_write = 2
    game.memory.partial_failure = partial_failure
    with pytest.raises(RosterError, match='rolled-back'):
        game.apply(preview['plan_id'])
    assert bytes(game.memory.data) == original
    assert game.identity is None
    assert not game.records
    assert json.loads(game.audit_path.read_text().splitlines()[-1])['outcome'] == 'rolled-back'


def test_game_load_decodes_raw_snapshot_and_clears_old_plans(tmp_path):
    game = FakeGame(tmp_path)
    raw = bytearray(game.profile.stride)
    last = 'Bennett'.encode('utf-16-le')
    raw[0:len(last)] = last
    first = 'Marcus'.encode('utf-16-le')
    raw[0x28:0x28 + len(first)] = first
    game.profile.fields['attributes', 'Driving Layup'].encode(raw, 95)
    game.memory.data[:len(raw)] = raw
    game.plans['obsolete'] = {}
    result = game.load()
    assert result['roster']['players'][0]['name'] == 'Marcus Bennett'
    assert result['roster']['players'][0]['player_id'] == 'game-0'
    assert result['roster']['players'][0]['attributes']['Driving Layup'] == 95
    assert game.records['game-0'] == raw
    assert not game.plans


def test_import_and_game_api_session_guards_and_no_implicit_save(tmp_path):
    data = tmp_path / 'roster.json'
    game = FakeGame(tmp_path)
    server = create_server(0, data, game=game)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/session') as response:
            session = json.load(response)
        def post(path, body, token=session['token']):
            return urlopen(Request(base + path, data=json.dumps(body).encode(),
                                  headers={'X-Editor-Token': token, 'Content-Type': 'application/json'}))
        with post('/api/import', {'document': SOURCE}) as response:
            assert json.load(response)['roster']['players'][0]['name'] == 'Marcus Bennett'
        with post('/api/import', {'document': SOURCE, 'merge': True, 'target': session['roster']}) as response:
            assert json.load(response)['roster']['players'][0]['player_id'] == 'demo-001'
        with post('/api/game/preview', game_document()) as response:
            assert len(json.load(response)['changes']) == 2
        for path in ('/api/import', '/api/game/load', '/api/game/preview', '/api/game/apply', '/api/game/live', '/api/game/edit', '/api/game/undo', '/api/game/redo', '/api/game/learn-value', '/api/game/capture', '/api/game/compare'):
            with pytest.raises(HTTPError) as denied:
                post(path, {}, 'wrong')
            assert denied.value.code == 403
        assert not data.exists()
        assert not game.memory.writes
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_settings_api_persists_and_invalidates_memory_snapshots(tmp_path):
    data, settings_path = tmp_path / 'roster.json', tmp_path / 'settings.json'
    game = FakeGame(tmp_path)
    server = create_server(0, data, game=game, settings_path=settings_path)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/session') as response:
            session = json.load(response)
        settings = {'game_path': r'D:\Games\NBA 2K27', 'verified_build': 'AB:CD', 'enable_writes': True}
        def post(body, token):
            return urlopen(Request(base + '/api/game/settings', data=json.dumps(body).encode(),
                                  headers={'X-Editor-Token': token, 'Content-Type': 'application/json'}))
        with pytest.raises(HTTPError) as denied:
            post(settings, 'wrong')
        assert denied.value.code == 403
        assert not settings_path.exists()
        with post(settings, session['token']) as response:
            assert json.load(response)['game_settings'] == settings
        assert game.identity is None and not game.records
        assert game.expected_build == 'AB:CD'
        assert json.loads(settings_path.read_text()) == settings
        assert not data.exists()
        with pytest.raises(HTTPError) as invalid:
            post({'enable_writes': True}, session['token'])
        assert invalid.value.code == 400
        assert json.loads(settings_path.read_text()) == settings
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_live_edit_enables_once_and_undo_redo_restore_game_values(tmp_path):
    game = FakeGame(tmp_path)
    original = bytes(game.memory.data)
    assert game.set_live(True)['live_enabled']
    request = {'player_id': 'game-0', 'category': 'attributes', 'field': 'Driving Layup', 'value': 90, 'expected': 25}
    result = game.edit(request)
    assert result['undo_count'] == 1
    field = game.profile.fields['attributes', 'Driving Layup']
    assert field.decode(game.memory.data) == 90
    assert game.undo()['redo_count'] == 1
    assert bytes(game.memory.data) == original
    assert game.undo(redo=True)['undo_count'] == 1
    assert field.decode(game.memory.data) == 90
    game.set_live(False)
    with pytest.raises(RosterError, match='Start live editing'):
        game.edit({**request, 'value': 91, 'expected': 90})
    game.undo()
    assert bytes(game.memory.data) == original


def test_bulk_ignores_unrelated_caches_but_preserves_them(tmp_path):
    game = FakeGame(tmp_path, writes=True)
    preview = game.preview(game_document())
    game.memory.data[0xE8] = 77
    assert game.apply(preview['plan_id'])['applied'] == 2
    assert game.memory.data[0xE8] == 77
    game.undo()
    assert game.memory.data[0xE8] == 77
    assert game.profile.fields['attributes', 'Driving Layup'].decode(game.memory.data) == 25


def test_live_cross_byte_edit_preserves_adjacent_fields_and_rejects_external_change(tmp_path):
    game = FakeGame(tmp_path)
    game.set_live(True)
    field = game.profile.fields['badges', 'Rise Up']
    game.memory.data[field.offset + 1] = 0xF0
    before = bytes(game.memory.data)
    result = game.edit({'player_id': 'game-0', 'category': 'badges', 'field': 'Rise Up', 'value': 5})
    assert field.decode(game.memory.data) == 5
    game.undo()
    assert bytes(game.memory.data) == before
    game.undo(redo=True)
    field.encode(game.memory.data, 4)
    with pytest.raises(RosterError, match='edited field'):
        game.undo()
    assert field.decode(game.memory.data) == 4


def test_live_invalid_values_and_stale_browser_values_never_write(tmp_path):
    game = FakeGame(tmp_path)
    game.set_live(True)
    request = {'player_id': 'game-0', 'category': 'attributes', 'field': 'Driving Layup', 'value': 90}
    for value in (0, 100, True, '90', None):
        with pytest.raises(RosterError):
            game.edit({**request, 'value': value})
    with pytest.raises(RosterError):
        game.edit({**request, 'expected': 50})
    with pytest.raises(RosterError):
        game.edit({**request, 'category': 'advanced', 'field': 'WEIGHT'})
    assert not game.memory.writes


def test_live_api_edit_undo_redo_without_workspace_save(tmp_path):
    path = tmp_path / 'roster.json'
    game = FakeGame(tmp_path)
    server = create_server(0, path, game=game)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/session') as response:
            session = json.load(response)
        def post(endpoint, body):
            request = Request(base + endpoint, data=json.dumps(body).encode(),
                              headers={'X-Editor-Token': session['token'], 'Content-Type': 'application/json'})
            with urlopen(request) as response:
                return json.load(response)
        assert post('/api/game/live', {'enabled': True})['live_enabled']
        edit = {'player_id': 'game-0', 'category': 'attributes', 'field': 'Driving Layup', 'value': 90}
        assert post('/api/game/edit', edit)['undo_count'] == 1
        assert post('/api/game/undo', {})['changes'][0]['value'] == 25
        assert post('/api/game/redo', {})['changes'][0]['value'] == 90
        assert not post('/api/game/live', {'enabled': False})['live_enabled']
        assert not path.exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
