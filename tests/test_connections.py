import copy
import json
import struct
from threading import Thread
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from trc_plus.app import DEFAULT_PROFILE, create_server
from trc_plus.fields import Field, RecordProfile
from trc_plus.game import GameConnection
from trc_plus.roster import RosterError, demo_roster
from trc_plus.trc import import_document, merge_trc


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


def test_preview_is_read_only_and_apply_requires_build_and_consumes_plan(tmp_path):
    game = FakeGame(tmp_path)
    preview = game.preview(game_document())
    assert len(preview['changes']) == 2
    assert not game.memory.writes
    with pytest.raises(RosterError, match='Writes require'):
        game.apply(preview['plan_id'])
    assert not any(game.memory.write_requests)
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
