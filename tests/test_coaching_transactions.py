import copy
import json
import struct
from pathlib import Path

import pytest

from test_connections import FakeGame, FakeMemory
from trace_app.roster import RosterError
from trace_app.team_sections import COACH_FIELDS, CODE_PROOFS, PROPERTY_PROOFS


class CoachMemory(FakeMemory):
    def __init__(self, profile, shared=False, unnamed=False):
        super().__init__(profile)
        self.build = '6AD2E48C:36532000'
        self.coach = 0x80000000
        self.root = 0x400000
        self.peer_root = 0x600000
        self.on_write = None
        self.blocks = {}
        proof = json.loads((Path(__file__).parent / 'fixtures' / 'team_layout_2k27.json').read_text())
        for rva, raw in proof['code'].items():
            self.blocks[self.module_base + int(rva, 16)] = bytearray.fromhex(raw)
        for item in proof['properties']:
            self.blocks[self.module_base + item['rva']] = bytearray.fromhex(item['hex'])
        for index in range(2):
            start = index * profile.stride
            for offset, text in ((0, 'Example'), (40, f'Person{index}')):
                encoded = text.encode('utf-16-le')
                self.data[start+offset:start+offset+len(encoded)] = encoded
            pointer = self.peer_root if index == 1 and (shared or unnamed) else self.root
            struct.pack_into('<Q', self.data, start + 0x60, pointer)
        for root, addresses in ((self.root, [self.base]), (self.peer_root, [self.base+profile.stride])):
            header = bytearray(0x1400)
            if not (shared or unnamed) and root == self.root:
                addresses.append(self.base + profile.stride)
            for index, address in enumerate(addresses):
                struct.pack_into('<Q', header, index*8, address)
            for offset, text in ((0x2FA, 'Example'), (0x32C, 'City'), (0x350, 'EX')):
                encoded = text.encode('utf-16-le')
                header[offset:offset+len(encoded)] = encoded
            if root == self.peer_root and unnamed:
                header[0x2FA:0x32C] = bytes(50)
            struct.pack_into('<Q', header, 0xF70, self.coach)
            self.blocks[root] = header
        raw = bytearray(0x1A0)
        for offset, text in ((0x50, 'Morgan'), (0x78, 'Coach')):
            encoded = text.encode('utf-16-le')
            raw[offset:offset+len(encoded)] = encoded
        for name, offset in COACH_FIELDS.items():
            raw[offset] = 50
        self.blocks[self.coach] = raw

    def read(self, address, size):
        for start, raw in self.blocks.items():
            if start <= address and address + size <= start + len(raw):
                return bytes(raw[address-start:address-start+size])
        return super().read(address, size)

    def store(self, address, raw):
        if self.base <= address and address + len(raw) <= self.base + len(self.data):
            self.data[address-self.base:address-self.base+len(raw)] = raw
            return
        for start, block in self.blocks.items():
            if start <= address and address + len(raw) <= start + len(block):
                block[address-start:address-start+len(raw)] = raw
                return
        raise RosterError('Unmapped fixture write')

    def write(self, address, raw):
        self.writes.append((address, raw))
        if self.fail_write == len(self.writes):
            if self.partial_failure:
                self.store(address, raw[:1])
            raise RosterError('Simulated failure')
        self.store(address, raw)
        if self.on_write:
            self.on_write(self)


def coach_game(tmp_path, shared=False, unnamed=False, mutate=None):
    game = FakeGame(tmp_path)
    game.memory = CoachMemory(game.profile, shared=shared, unnamed=unnamed)
    if mutate:
        mutate(game.memory)
    game.expected_build = game.memory.build
    game.enable_writes = False
    loaded = game.load()
    return game, loaded


def test_coaching_live_undo_redo_all_fields_and_exact_neighbors(tmp_path):
    game, loaded = coach_game(tmp_path)
    assert len(COACH_FIELDS) == 16
    team = loaded['roster']['teams'][0]
    assert not team['coaching']['read_only']
    assert set(team['coaching']['writable_fields']) == set(COACH_FIELDS)
    assert not game.memory.writes and not loaded['status']['writes_enabled']
    game.set_live(True)
    before = bytes(game.memory.blocks[game.memory.coach])
    for name, offset in COACH_FIELDS.items():
        result = game.edit({'team_id': team['team_id'], 'category': 'coaching', 'field': name, 'expected': 50, 'value': 51})
        expected = bytearray(before)
        expected[offset] = 51
        assert game.memory.blocks[game.memory.coach] == expected
        assert result['changes'][0]['team_id'] == team['team_id']
        game.undo()
        assert game.memory.blocks[game.memory.coach] == before
        game.undo(redo=True)
        assert game.memory.blocks[game.memory.coach] == expected
        game.undo()
    journal = [json.loads(line) for line in game.audit_path.read_text().splitlines()]
    assert journal[-1]['outcome'] == 'applied'
    assert journal[0]['patches'][0]['region'] == 'coach'


@pytest.mark.parametrize('shared,unnamed', [(True, False), (False, True)])
def test_shared_coach_including_unnamed_team_is_never_writable(tmp_path, shared, unnamed):
    game, loaded = coach_game(tmp_path, shared, unnamed)
    team = loaded['roster']['teams'][0]
    assert team['coaching']['read_only']
    game.set_live(True)
    with pytest.raises(RosterError, match='read only'):
        game.edit({'team_id': team['team_id'], 'category': 'coaching', 'field': 'Help Defense', 'value': 51})
    assert not game.memory.writes


@pytest.mark.parametrize('failure', ['slot', 'peer_slot', 'name', 'job', 'membership', 'roster_link',
                                   'new_record', 'code', 'metadata', 'old_value'])
def test_changed_coach_ownership_identity_code_or_value_blocks_before_write(tmp_path, failure):
    game, loaded = coach_game(tmp_path)
    game.set_live(True)
    memory = game.memory
    if failure == 'slot':
        struct.pack_into('<Q', memory.blocks[memory.root], 0xF70, memory.coach+0x1000)
    if failure == 'peer_slot':
        struct.pack_into('<Q', memory.blocks[memory.root], 0xF78, memory.coach)
    if failure == 'name':
        memory.blocks[memory.coach][0x50] ^= 1
    if failure == 'job':
        memory.blocks[memory.coach][0x182] = 1
    if failure == 'membership':
        struct.pack_into('<Q', memory.blocks[memory.root], 0, memory.base + 8)
    if failure == 'roster_link':
        struct.pack_into('<Q', memory.data, 0x60, memory.peer_root)
    if failure == 'new_record':
        memory.data[2*game.profile.stride] = 1
    if failure == 'code':
        memory.blocks[memory.module_base + CODE_PROOFS['STAFFDATA::SetCoachAttribute'][0]][0] ^= 1
    if failure == 'metadata':
        memory.blocks[memory.module_base + PROPERTY_PROOFS['HelpDefense'][0]][8] ^= 1
    if failure == 'old_value':
        memory.blocks[memory.coach][COACH_FIELDS['Help Defense']] = 55
    with pytest.raises(RosterError):
        game.edit({'team_id': loaded['roster']['teams'][0]['team_id'], 'category': 'coaching',
                   'field': 'Help Defense', 'expected': 50, 'value': 51})
    assert not memory.writes


@pytest.mark.parametrize('value', [-1, 101, True, 1.5, '51', None])
def test_coaching_requires_integer_in_native_domain(tmp_path, value):
    game, loaded = coach_game(tmp_path)
    game.set_live(True)
    with pytest.raises(RosterError):
        game.edit({'team_id': loaded['roster']['teams'][0]['team_id'], 'category': 'coaching',
                   'field': 'Help Defense', 'value': value})
    assert not game.memory.writes


def test_mixed_player_coach_bulk_is_read_only_until_apply_and_undo_is_exact(tmp_path):
    game, loaded = coach_game(tmp_path)
    game.set_live(True)
    before_player = bytes(game.memory.data)
    before_coach = bytes(game.memory.blocks[game.memory.coach])
    document = copy.deepcopy(loaded['roster'])
    document['players'][0]['attributes']['Driving Layup'] = 26
    document['teams'][0]['coaching']['values']['Help Defense'] = 51
    document['teams'][0]['coaching']['values']['Run Plays Frequency'] = 52
    preview = game.preview(document)
    assert len(preview['changes']) == 3 and not game.memory.writes
    result = game.apply(preview['plan_id'])
    assert result['applied'] == 3
    assert game.memory.blocks[game.memory.coach][COACH_FIELDS['Help Defense']] == 51
    assert game.profile.fields['attributes', 'Driving Layup'].decode(game.memory.data) == 26
    game.undo()
    assert game.memory.data == before_player and game.memory.blocks[game.memory.coach] == before_coach
    game.undo(redo=True)
    game.undo()
    assert game.memory.data == before_player and game.memory.blocks[game.memory.coach] == before_coach


def test_mixed_batch_failure_rolls_back_coach_and_partial_player_write(tmp_path):
    game, loaded = coach_game(tmp_path)
    game.set_live(True)
    before_player = bytes(game.memory.data)
    before_coach = bytes(game.memory.blocks[game.memory.coach])
    document = loaded['roster']
    document['players'][0]['attributes']['Driving Layup'] = 26
    document['teams'][0]['coaching']['values']['Help Defense'] = 51
    preview = game.preview(document)
    game.memory.fail_write = 2
    game.memory.partial_failure = True
    with pytest.raises(RosterError, match='rolled-back'):
        game.apply(preview['plan_id'])
    assert game.memory.data == before_player and game.memory.blocks[game.memory.coach] == before_coach
    assert game.identity is None


def test_moved_coach_after_write_refuses_rollback_to_old_record(tmp_path):
    game, loaded = coach_game(tmp_path)
    game.set_live(True)
    game.memory.on_write = lambda memory: struct.pack_into('<Q', memory.blocks[memory.root], 0xF70, memory.coach+0x1000)
    with pytest.raises(RosterError, match='rollback-failed'):
        game.edit({'team_id': loaded['roster']['teams'][0]['team_id'], 'category': 'coaching',
                   'field': 'Help Defense', 'value': 51})
    assert len(game.memory.writes) == 1 and game.identity is None


@pytest.mark.parametrize('overlap', ['player', 'module', 'body', 'staff'])
def test_overlapping_records_remain_read_only(tmp_path, overlap):
    def mutate(memory):
        if overlap == 'body':
            struct.pack_into('<Q', memory.data, 0x78, memory.coach-32)
        elif overlap == 'staff':
            struct.pack_into('<Q', memory.blocks[memory.root], 0xF78, memory.coach+8)
        else:
            raw = memory.blocks.pop(memory.coach)
            memory.coach = memory.base+0x200 if overlap == 'player' else memory.module_base+0x7000
            if overlap == 'player':
                memory.data[0x200:0x200+len(raw)] = raw
            else:
                memory.blocks[memory.coach] = raw
            struct.pack_into('<Q', memory.blocks[memory.root], 0xF70, memory.coach)
    game, loaded = coach_game(tmp_path, mutate=mutate)
    assert loaded['roster']['teams'][0]['coaching']['read_only']
    assert not game.memory.writes


def test_preview_rechecks_current_coach_without_opening_write_access(tmp_path):
    game, loaded = coach_game(tmp_path)
    document = loaded['roster']
    document['teams'][0]['coaching']['values']['Help Defense'] = 51
    game.memory.blocks[game.memory.coach][COACH_FIELDS['Help Defense']] = 55
    with pytest.raises(RosterError, match='coaching value changed'):
        game.preview(document)
    assert not game.memory.writes and not any(game.memory.write_requests)


def test_coaching_edits_preserve_unrelated_fresh_staff_bytes(tmp_path):
    game, loaded = coach_game(tmp_path)
    game.set_live(True)
    game.memory.blocks[game.memory.coach][0x170] = 77
    game.edit({'team_id': loaded['roster']['teams'][0]['team_id'], 'category': 'coaching',
               'field': 'Help Defense', 'value': 51})
    game.undo()
    assert game.memory.blocks[game.memory.coach][COACH_FIELDS['Help Defense']] == 50
    assert game.memory.blocks[game.memory.coach][0x170] == 77


def test_mixed_source_player_renames_do_not_invalidate_coach_ownership(tmp_path):
    game, loaded = coach_game(tmp_path)
    game.set_live(True)
    before_player = bytes(game.memory.data)
    before_coach = bytes(game.memory.blocks[game.memory.coach])
    document = loaded['roster']
    for p in document['players']:
        p['vitals']['First Name'] = 'Renamed'
    document['teams'][0]['coaching']['values']['Help Defense'] = 51
    preview = game.preview(document)
    assert len(preview['changes']) == 3
    game.apply(preview['plan_id'])
    game.undo()
    assert game.memory.data == before_player and game.memory.blocks[game.memory.coach] == before_coach
