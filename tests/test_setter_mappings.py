"""Code-pinned setters use the existing reversible packed-field transactions."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from test_connections import FakeGame
from trace_app.roster import RosterError
from trace_app.setter_mappings import SETTER_BUILD, SETTER_FIELDS, verified_setter_fields


def setter_game(tmp_path):
    game = FakeGame(tmp_path, writes=True)
    game.memory.build = SETTER_BUILD.upper()
    game.expected_build = game.memory.build
    fixtures = json.loads((Path(__file__).parent / 'fixtures' / 'packed_setter_code_2k27.json').read_text())
    code = {game.memory.module_base + int(rva, 16): bytes.fromhex(item['code_hex'])
            for rva, item in fixtures['routines'].items()}
    original_read = game.memory.read

    def read(address, size):
        if address in code:
            return code[address][:size]
        return original_read(address, size)

    game.memory.read = read
    game.identity = game.status()
    return game, code


def test_all_proofs_match_code_and_profile_and_fail_closed(tmp_path):
    game, code = setter_game(tmp_path)
    assert len(SETTER_FIELDS) == 55
    assert verified_setter_fields(game.memory, game.profile) == set(SETTER_FIELDS)
    key = ('gear', 'Shorts Length')
    field = game.profile.fields[key]
    for replacement in (replace(field, offset=field.offset + 1),
                        replace(field, allowed_values=None),
                        replace(field, verified_build='OTHER'), replace(field, writable=False)):
        game.profile.fields[key] = replacement
        assert key not in verified_setter_fields(game.memory, game.profile)
    game.profile.fields[key] = field
    _, _, rva, _, _ = SETTER_FIELDS[key]
    address = game.memory.module_base + rva
    original = code[address]
    code[address] = bytes([original[0] ^ 1]) + original[1:]
    assert key not in verified_setter_fields(game.memory, game.profile)
    code.pop(address)
    assert key not in verified_setter_fields(game.memory, game.profile)
    game.memory.build = 'OTHER'
    assert not verified_setter_fields(game.memory, game.profile)


@pytest.mark.parametrize('key', list(SETTER_FIELDS))
def test_each_setter_range_preserves_adjacent_bits_and_rejects_reserved_values(tmp_path, key):
    game, _ = setter_game(tmp_path)
    field = game.profile.fields[key]
    layout, maximum, _, _, _ = SETTER_FIELDS[key]
    assert (field.offset, field.bits, field.shift, field.kind) == layout
    assert field.verified_build.casefold() == SETTER_BUILD
    mask = ((1 << field.bits) - 1) << (field.offset * 8 + field.shift)
    for value in range(maximum + 1):
        row = bytearray([0xA5] * game.profile.stride)
        before = bytes(row)
        field.encode(row, value)
        assert field.decode(row) == value
        assert not ((int.from_bytes(row, 'little') ^ int.from_bytes(before, 'little')) & ~mask)
    with pytest.raises(RosterError):
        field.encode(bytearray(game.profile.stride), maximum + 1)
    assert field.name not in game.profile.decode(bytes(game.profile.stride), 'OTHER')[field.category]


def test_setter_live_bulk_undo_redo_and_primary_path_code_guard(tmp_path):
    game, code = setter_game(tmp_path)
    game.set_live(True)
    before = bytes(game.memory.data)
    for (category, name), (_, maximum, _, _, _) in SETTER_FIELDS.items():
        game.edit({'player_id': 'game-0', 'category': category, 'field': name, 'value': maximum})
        assert game.profile.fields[category, name].decode(game.memory.data) == maximum
        game.undo()
        assert bytes(game.memory.data) == before
        game.undo(redo=True)
        game.undo()
        assert bytes(game.memory.data) == before
    changes = [{'player_id': 'game-0', 'category': category, 'field': name, 'old': 0, 'value': proof[1]}
               for (category, name), proof in SETTER_FIELDS.items()]
    game._write_changes(changes, 'bulk')
    game.undo_stack.append(changes)
    for change in changes:
        assert game.profile.fields[change['category'], change['field']].decode(game.memory.data) == change['value']
    game.undo()
    assert bytes(game.memory.data) == before
    # The ordinary profile-pointer path has no writable_fields allowlist;
    # the transaction must still reject a changed setter before writing.
    key = ('gear', 'Shorts Length')
    _, _, rva, _, _ = SETTER_FIELDS[key]
    code[game.memory.module_base + rva] = b'\0' * len(code[game.memory.module_base + rva])
    writes = len(game.memory.writes)
    with pytest.raises(RosterError, match='Named setter code'):
        game.edit({'player_id': 'game-0', 'category': key[0], 'field': key[1], 'value': 1})
    assert len(game.memory.writes) == writes
    assert bytes(game.memory.data) == before
