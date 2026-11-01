import json
import struct
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from trace_app.player_body import (BODY_BUILD, BODY_SIZE, body_span, decode_body,
                                  encode_body, read_body_model, snapshot_body)
from trace_app.roster import RosterError
from test_connections import FakeGame, FakeMemory


@pytest.fixture
def model():
    result = json.loads((Path(__file__).parent / 'fixtures' / 'body_model.json').read_text())
    result['fingerprint'] = 'verified-test-model'
    return result


def raw_body(height=18796, span=19752, scales=(1, 1, 1, 1), flags=0):
    return struct.pack('<2H6f', height | flags, span | flags, *scales, 1, 1)


@pytest.mark.parametrize('before,changes,expected', [
    (raw_body(), {'Height': 75}, raw_body(19050, 20019)),
    (raw_body(19050, 20019), {'Wingspan': 51}, raw_body(19050, 20059, (1, 1, 1.002, 1))),
    (raw_body(19050, 20059, (1, 1, 1.002, 1)),
     {'Shoulder Width': 52, 'Neck Length': 53, 'Trunk Length': 54},
     raw_body(19050, 20073, (1.016, 1.004, 1.002, 1.012))),
    (raw_body(19050, 20073, (1.016, 1.004, 1.002, 1.012)),
     {'Shoulder Width': 54, 'Neck Length': 52, 'Trunk Length': 53},
     raw_body(19050, 20087, (1.012, 1.008, 1.002, 1.008))),
    (raw_body(19050, 20073, (1.016, 1.004, 1.002, 1.012)),
     {'Height': 74, 'Wingspan': 50, 'Shoulder Width': 50, 'Neck Length': 50, 'Trunk Length': 50},
     raw_body()),
])
def test_encode_reproduces_complete_native_body_captures(model, before, changes, expected):
    assert encode_body(before, changes, model) == expected


@pytest.mark.parametrize('changes', [{'Height': 0}, {'Height': 130}, {'Height': 74.5},
                                    {'Wingspan': -1}, {'Neck Length': 101}, {'Trunk Length': True},
                                    {'Shoulder Width': float('nan')}, {'Wingspan': '51'}])
def test_invalid_values_never_produce_body_bytes(model, changes):
    with pytest.raises(RosterError):
        encode_body(raw_body(), changes, model)


def test_body_preserves_both_packed_flag_bits(model):
    result = encode_body(raw_body(flags=0x8000), {'Height': 75, 'Wingspan': 51}, model)
    assert result == raw_body(19050, 20059, (1, 1, 1.002, 1), flags=0x8000)
    assert decode_body(result)['Height'] == 75


class BodyMemory(FakeMemory):
    def __init__(self, profile):
        super().__init__(profile)
        self.build = BODY_BUILD
        self.child = 0x800000
        self.body = bytearray(raw_body(flags=0x8000))
        self.model_identity = 'verified-test-model'
        self.move_after_write = False
        struct.pack_into('<Q', self.data, 0x78, self.child)

    def read(self, address, size):
        if self.child <= address and address+size <= self.child+len(self.body):
            offset = address-self.child
            return bytes(self.body[offset:offset+size])
        return super().read(address, size)

    def write(self, address, data):
        if not self.child <= address < self.child+len(self.body):
            return super().write(address, data)
        self.writes.append((address, data))
        offset = address-self.child
        if self.fail_write == len(self.writes):
            if self.partial_failure:
                self.body[offset:offset+1] = data[:1]
            raise RosterError('Simulated Body write failure')
        self.body[offset:offset+len(data)] = data
        if self.move_after_write:
            struct.pack_into('<Q', self.data, 0x78, self.child+0x10000)


@pytest.fixture
def game(tmp_path, monkeypatch, model):
    def read_model(process):
        if process.build != BODY_BUILD:
            raise RosterError('Unsupported build')
        return {**model, 'fingerprint': process.model_identity}
    monkeypatch.setattr('trace_app.game.read_body_model', read_model)
    result = FakeGame(tmp_path)
    result.memory = BodyMemory(result.profile)
    result.records = {'game-0': bytes(result.memory.data[:result.profile.stride])}
    result.body_snapshots = {'game-0': {'pointer': result.memory.child, 'data': bytes(result.memory.body)}}
    result.body_values = {'game-0': decode_body(result.memory.body)}
    result.identity = result.status()
    result.set_live(True)
    return result


def edit(game, field='Height', value=75):
    return game.edit({'player_id': 'game-0', 'category': 'vitals', 'field': field, 'value': value})


def test_body_live_write_journal_and_exact_undo_redo(game, model):
    original = bytes(game.memory.body)
    main = bytes(game.memory.data)
    edit(game)
    edited = bytes(game.memory.body)
    assert decode_body(edited)['Height'] == 75
    assert body_span(edited, model) == (int.from_bytes(edited[2:4], 'little') & 0x7FFF)
    assert bytes(game.memory.data) == main
    game.undo()
    assert bytes(game.memory.body) == original
    game.undo(redo=True)
    assert bytes(game.memory.body) == edited
    logs = [json.loads(line) for line in game.audit_path.read_text().splitlines()]
    assert all(any(p.get('region') == 'body' for p in log['patches']) for log in logs)
    assert [log['outcome'] for log in logs] == ['started', 'applied']*3


def test_mixed_bulk_body_and_record_transaction_has_one_undo(game):
    original = bytes(game.memory.body), bytes(game.memory.data)
    document = {'players': [{'player_id': 'game-0', 'name': 'Example',
                            'vitals': {'Height': 75, 'Wingspan': 51, 'Shoulder Width': 54,
                                       'Neck Length': 52, 'Trunk Length': 53},
                            'attributes': {'Driving Layup': 50}}], 'teams': []}
    preview = game.preview(document)
    assert len(preview['changes']) == 6
    assert game.apply(preview['plan_id'])['applied'] == 6
    assert decode_body(game.memory.body)['Wingspan'] == 51
    game.undo()
    assert (bytes(game.memory.body), bytes(game.memory.data)) == original


@pytest.mark.parametrize('failure', ['stale', 'pointer', 'shared', 'model', 'build', 'measurement'])
def test_body_preflight_rejects_uncertain_data_without_writing(game, failure):
    if failure == 'stale':
        struct.pack_into('<f', game.memory.body, 0x10, 1.004)
    elif failure == 'pointer':
        struct.pack_into('<Q', game.memory.data, 0x78, game.memory.child+0x10000)
    elif failure == 'shared':
        offset = game.profile.stride
        struct.pack_into('<Q', game.memory.data, offset+0x78, game.memory.child)
        game.records['game-1'] = bytes(game.memory.data[offset:offset+game.profile.stride])
    elif failure == 'model':
        game.memory.model_identity = 'changed'
    elif failure == 'build':
        game.memory.build = 'OTHER'
    else:
        game.memory.body[2] ^= 1
        game.body_snapshots['game-0']['data'] = bytes(game.memory.body)
    with pytest.raises(RosterError):
        edit(game)
    assert not game.memory.writes


@pytest.mark.parametrize('partial', [False, True])
def test_body_failure_rolls_back_all_attempted_ranges(game, partial):
    original = bytes(game.memory.body)
    game.memory.fail_write = 1
    game.memory.partial_failure = partial
    with pytest.raises(RosterError, match='rolled-back'):
        edit(game)
    assert bytes(game.memory.body) == original
    assert not game.records and not game.body_snapshots


def test_body_pointer_movement_refuses_rollback_into_old_allocation(game):
    game.memory.move_after_write = True
    with pytest.raises(RosterError, match='rollback-failed'):
        edit(game)
    assert len(game.memory.writes) == 1
    assert not game.body_snapshots


def test_mixed_body_and_record_partial_failure_rolls_back_both(game):
    original = bytes(game.memory.body), bytes(game.memory.data)
    document = {'players': [{'player_id': 'game-0', 'name': 'Example',
                            'vitals': {'Height': 75}, 'attributes': {'Driving Layup': 50}}], 'teams': []}
    preview = game.preview(document)
    game.memory.fail_write = 2
    game.memory.partial_failure = True
    with pytest.raises(RosterError, match='rolled-back'):
        game.apply(preview['plan_id'])
    assert (bytes(game.memory.body), bytes(game.memory.data)) == original


def test_body_undo_refuses_to_overwrite_an_external_body_edit(game):
    edit(game)
    struct.pack_into('<f', game.memory.body, 0x10, 1.004)
    count = len(game.memory.writes)
    with pytest.raises(RosterError):
        game.undo()
    assert len(game.memory.writes) == count


def test_height_undo_preserves_original_fractional_inch_measurement(game, model):
    struct.pack_into('<H', game.memory.body, 0, 19000 | 0x8000)
    struct.pack_into('<H', game.memory.body, 2, body_span(game.memory.body, model) | 0x8000)
    original = bytes(game.memory.body)
    game.body_snapshots['game-0']['data'] = original
    game.body_values['game-0'] = decode_body(original)
    assert not decode_body(original)['Height'].is_integer()
    edit(game, value=76)
    game.undo()
    assert bytes(game.memory.body) == original


def test_native_model_reader_fails_closed_without_verified_code(game):
    with pytest.raises(RosterError):
        read_body_model(game.memory)


@pytest.mark.parametrize('failure', [None, 'code', 'constant', 'topology', 'scale_group', 'nonfinite', 'unstable'])
def test_model_resolution_requires_verified_code_and_stable_supported_geometry(model, monkeypatch, failure):
    from trace_app import player_body
    base, pointer = 0x100000, 0x600000
    code = b'verified test routine'
    monkeypatch.setattr(player_body, 'MODEL_CODE_HASHES', {0x1000: (len(code), hashlib.sha256(code).hexdigest())})
    header = bytearray(0x60)
    for offset, address in ((8, 0x601000), (0x10, 0x602000), (0x28, 0x603000), (0x38, 0x604000)):
        struct.pack_into('<Q', header, offset, address)
    struct.pack_into('<I', header, 0x4C, 22)
    struct.pack_into('<2f', header, 0x54, model['height'], model['span'])
    landmarks = [0]*14
    landmarks[10], landmarks[13] = 10, 13
    regions = {base+0x1000: code, base+player_body.BODY_MODEL_RVA: struct.pack('<Q', pointer),
               pointer: bytes(header), 0x601000: struct.pack('<22i', *model['parents']),
               0x602000: struct.pack('<88f', *(v for position in model['positions'] for v in position)),
               0x603000: struct.pack('<14i', *landmarks), 0x604000: struct.pack('<22i', *model['groups'])}
    regions.update({base+rva: bytes.fromhex(value) for rva, value in player_body.MODEL_CONSTANTS.items()})
    if failure == 'code':
        regions[base+0x1000] = bytes(len(code))
    elif failure == 'constant':
        regions[base+next(iter(player_body.MODEL_CONSTANTS))] = bytes(4)
    elif failure == 'topology':
        regions[0x601000] = bytes(88)
    elif failure == 'scale_group':
        regions[0x604000] = struct.pack('<22i', *([7]*22))
    elif failure == 'nonfinite':
        broken = bytearray(regions[0x602000])
        struct.pack_into('<f', broken, 0, float('nan'))
        regions[0x602000] = bytes(broken)
    reads = {}
    def read(address, size):
        reads[address] = reads.get(address, 0)+1
        raw = regions[address]
        assert len(raw) == size
        if failure == 'unstable' and address == pointer and reads[address] > 1:
            return bytes(size)
        return raw
    process = SimpleNamespace(build=BODY_BUILD, module_base=base, read=read)
    if failure:
        with pytest.raises(RosterError):
            read_body_model(process)
    else:
        actual = read_body_model(process)
        assert actual['height'] == model['height']
        assert actual['span'] == model['span']
        assert actual['fingerprint']
        assert body_span(raw_body(), actual) == 19752
