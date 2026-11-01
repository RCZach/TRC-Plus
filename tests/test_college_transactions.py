import json

import pytest

from test_connections import FakeGame
from trace_app.player_college import build_college_catalog, validate_college_catalog
from trace_app.roster import RosterError


def college_game(tmp_path, labels=('Argentina', 'Arizona', 'Oregon', 'Yale')):
    game = FakeGame(tmp_path, writes=True)
    memory = game.memory
    memory.build = '6AD2E48C:36532000'
    game.expected_build = memory.build
    memory.data = bytearray(game.profile.stride * 5)
    for index in range(4):
        offset = index * game.profile.stride
        memory.data[offset:offset+4] = 'AA'.encode('utf-16-le')
        first = f'Test{index}'.encode('utf-16-le')
        memory.data[offset+0x28:offset+0x28+len(first)] = first
        memory.data[offset+0xB0:offset+0xB8] = (0x700000 + index * 72).to_bytes(8, 'little')
    catalog = bytearray(4 * 72)
    for index, name in enumerate(labels):
        raw = name.encode()
        catalog[index*72:index*72+len(raw)] = raw
    old_read = memory.read

    def read(address, size):
        if 0x700000 <= address and address + size <= 0x700000 + len(catalog):
            return bytes(catalog[address-0x700000:address-0x700000+size])
        return old_read(address, size)

    memory.read = read
    loaded = game.load()
    return game, catalog, loaded


def test_college_load_and_preview_are_named_and_read_only(tmp_path):
    game, _, loaded = college_game(tmp_path)
    assert loaded['status']['college_writable']
    assert loaded['roster']['players'][1]['vitals']['College / From'] == 'Arizona'
    assert game.field_values()['vitals']['College / From'] == {n: n for n in ('Argentina', 'Arizona', 'Oregon', 'Yale')}
    loaded['roster']['players'][1]['vitals']['College / From'] = 'Argentina'
    preview = game.preview(loaded['roster'])
    assert preview['changes'] == [{'name': 'Test1 AA', 'player_id': 'game-1', 'category': 'vitals',
                                  'field': 'College / From', 'old': 'Arizona', 'value': 'Argentina'}]
    assert not game.memory.writes
    assert str(0x700000) not in json.dumps(preview)
    for value in (0x700000, 'Missing college'):
        with pytest.raises(RosterError):
            game.normalize_value('vitals', 'College / From', value)


def test_college_live_bulk_undo_redo_preserve_other_bytes(tmp_path):
    game, _, loaded = college_game(tmp_path)
    game.set_live(True)
    before = bytes(game.memory.data)
    result = game.edit({'player_id': 'game-1', 'category': 'vitals', 'field': 'College / From',
                        'expected': 'Arizona', 'value': 'Argentina'})
    assert result['changes'][0]['old'] == 'Arizona'
    assert result['changes'][0]['value'] == 'Argentina'
    expected = bytearray(before)
    offset = game.profile.stride + 0xB0
    expected[offset:offset+8] = (0x700000).to_bytes(8, 'little')
    assert game.memory.data == expected
    assert game.undo()['changes'][0]['value'] == 'Arizona'
    assert game.memory.data == before
    game.undo(redo=True)
    assert game.memory.data == expected
    game.undo()
    assert game.memory.data == before
    for player in loaded['roster']['players']:
        player['vitals']['College / From'] = 'Oregon'
    preview = game.preview(loaded['roster'])
    assert len(preview['changes']) == 3
    result = game.apply(preview['plan_id'])
    assert all(c['value'] == 'Oregon' for c in result['changes'])
    assert validate_college_catalog(game.memory, game.profile, game.college_catalog, game.memory.base)
    game.undo()
    assert game.memory.data == before


@pytest.mark.parametrize('duplicate', ['Arizona', 'arizona'])
def test_college_catalog_changes_and_ambiguous_names_fail_closed(tmp_path, duplicate):
    game, catalog, loaded = college_game(tmp_path, ('Arizona', duplicate, 'Oregon', 'Yale'))
    preview = game.preview(loaded['roster'])
    assert not any('College / From' in w for w in preview['warnings'])
    assert not preview['changes']
    assert 'Arizona' not in game.college_catalog['choices']
    with pytest.raises(RosterError, match='ambiguous'):
        game.normalize_value('vitals', 'College / From', 'Arizona')
    game.set_live(True)
    before = bytes(game.memory.data)
    catalog[0] ^= 1
    with pytest.raises(RosterError):
        game.edit({'player_id': 'game-2', 'category': 'vitals', 'field': 'College / From', 'value': 'Yale'})
    assert not game.memory.writes and game.memory.data == before
    assert not game.status()['college_writable']


def test_failed_college_write_rolls_back_exactly(tmp_path):
    game, _, _ = college_game(tmp_path)
    game.set_live(True)
    before = bytes(game.memory.data)
    game.memory.fail_write = 1
    game.memory.partial_failure = True
    with pytest.raises(RosterError, match='rolled-back'):
        game.edit({'player_id': 'game-1', 'category': 'vitals', 'field': 'College / From', 'value': 'Argentina'})
    assert game.memory.data == before
    assert game.identity is None


def test_renaming_catalog_source_players_keeps_college_transactions_valid(tmp_path):
    game, _, _ = college_game(tmp_path)
    game.set_live(True)
    before = bytes(game.memory.data)
    changes = [{'player_id': f'game-{i}', 'category': 'vitals', 'field': 'First Name',
                'old': f'Test{i}', 'value': f'Renamed{i}'} for i in range(4)]
    game._write_changes(changes, 'bulk')
    game.undo_stack.append(changes)
    assert game.status()['college_writable']
    game.undo()
    assert game.memory.data == before
    assert game.status()['college_writable']


def test_college_catalog_requires_observed_spacing_and_multiple_sources(tmp_path):
    game, _, _ = college_game(tmp_path)
    assert build_college_catalog(game.memory, game.profile, {'game-0': game.records['game-0']}, game.memory.base) is None
    bad = dict(game.records)
    row = bytearray(bad['game-1'])
    row[0xB0:0xB8] = (0x700008).to_bytes(8, 'little')
    bad['game-1'] = bytes(row)
    assert build_college_catalog(game.memory, game.profile, bad, game.memory.base) is None
