"""Offline discovery must use explicit values rather than name-list positions."""

import runpy
import struct
import zlib
from pathlib import Path


extract = runpy.run_path(str(Path(__file__).parents[1] / 'scripts' / 'extract_animation_enums.py'))['extract']
extract_registered = runpy.run_path(str(Path(__file__).parents[1] / 'scripts' / 'extract_animation_enums.py'))['extract_registered']
add_glossary_labels = runpy.run_path(str(Path(__file__).parents[1] / 'scripts' / 'extract_animation_enums.py'))['add_glossary_labels']


def executable(tables):
    data = bytearray(256)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3C, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<I', data, 72, 0x12345678)
    struct.pack_into('<I', data, 144, 0x1000)
    data.extend(b'\0SIG_SHOT_JUMPER\0ALPHA\0BETA\0end.of.block\0')
    for values in tables:
        data.extend(b'\xff' * 16)
        for name, value in zip((b'ALPHA', b'BETA'), values):
            data.extend(struct.pack('<III', zlib.crc32(name), value, 0))
    return data


def test_extracts_explicit_nonsequential_values_and_matching_duplicates():
    result = extract(executable([(197, 203), (197, 203)]))
    assert result['build'] == '12345678:1000'
    assert not result['write_authorized']
    enum = result['enums'][0]
    assert enum['consistent_explicit_tables']
    assert len(enum['tables']) == 2
    assert enum['entries'] == [{'symbol': 'ALPHA', 'value': 197}, {'symbol': 'BETA', 'value': 203}]


def test_conflicting_tables_are_not_resolved():
    enum = extract(executable([(197, 203), (197, 204)]))['enums'][0]
    assert not enum['consistent_explicit_tables']
    assert enum['entries'] == []


def test_name_block_without_explicit_table_remains_unresolved():
    enum = extract(executable([]))['enums'][0]
    assert enum['name_count'] == 2
    assert enum['entries'] == []


def registered_executable():
    data = bytearray(1280)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3C, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<H', data, 70, 2)
    struct.pack_into('<I', data, 72, 0x12345678)
    struct.pack_into('<H', data, 84, 240)
    struct.pack_into('<Q', data, 112, 0x140000000)
    struct.pack_into('<I', data, 144, 0x4000)
    for index, (rva, pointer, size, flags) in enumerate([(0x1000, 512, 256, 0x20000000), (0x2000, 768, 512, 0)]):
        offset = 328 + index * 40
        struct.pack_into('<4I', data, offset + 8, size, rva, size, pointer)
        struct.pack_into('<I', data, offset + 36, flags)
    code = bytearray()
    for index, (opcode, target) in enumerate([(b'\x48\x8d\x0d', 0x2500), (b'\x48\x8d\x15', 0x209C),
                                             (b'\x4c\x8d\x05', 0x2080), (b'\x4c\x8d\x0d', 0x2000)]):
        code.extend(opcode + struct.pack('<i', target - (0x1000 + index * 7 + 7)))
    code.extend(b'\xe9' + struct.pack('<i', 0x3000 - 0x1021))
    data[512:545] = code
    names = b'SIG_SHOT_JUMPER\0ALPHA\0BETA\0UNRELATED_TRAILER\0'
    data[768:768 + len(names)] = names
    for index, (symbol, value) in enumerate([(b'ALPHA', 197), (b'BETA', 203)]):
        struct.pack_into('<III', data, 896 + index * 12, zlib.crc32(symbol), value, 0)
    struct.pack_into('<5I', data, 924, zlib.crc32(b'SIG_SHOT_JUMPER'), 0x64207, 0, 2, 4)
    struct.pack_into('<IIIIQQQ', data, 960, zlib.crc32(b'ShotJumper'), zlib.crc32(b'SIG_SHOT_JUMPER'),
                     0x408, 4, 0x127000A00, 0, 0x140002500)
    return data


def test_registration_bounds_ignore_unrelated_strings_and_bind_packed_field():
    result = extract_registered(registered_executable(), [('Jumpshot Base', 0x408, 10, 0)])
    assert result['enums']['SIG_SHOT_JUMPER']['values'] == {'ALPHA': 197, 'BETA': 203}
    assert result['fields']['Jumpshot Base']['layout'] == [0x408, 10, 0]


def test_wrong_type_crc_layout_or_table_does_not_produce_catalog():
    original = registered_executable()
    for offset in (896, 924, 964):
        changed = bytearray(original)
        changed[offset] ^= 1
        result = extract_registered(changed, [('Jumpshot Base', 0x408, 10, 0)])
        assert not result['fields'] and not result['enums']
    result = extract_registered(original, [('Jumpshot Base', 0x408, 9, 0)])
    assert not result['fields']


def test_duplicate_registrations_require_investigation():
    data = registered_executable()
    second = bytearray(data[512:545])
    for index in range(4):
        displacement = struct.unpack_from('<i', second, index * 7 + 3)[0]
        struct.pack_into('<i', second, index * 7 + 3, displacement - 64)
    data[576:609] = second
    result = extract_registered(data, [('Jumpshot Base', 0x408, 10, 0)])
    assert not result['fields'] and not result['enums']


def test_glossary_joins_exact_symbols_without_importing_numeric_ids():
    catalog = {'enums': {'SIG_LAYUP': {'values': {'LUP_K_BRYANT': 15, 'LUP_M_JORDAN': 52}}}}
    glossary = {'Anim Glossary Tabs': [{'Anims': [
        {'Anim ID': 'SIG_LAYUP_LUP_K_BRYANT', 'Anim Name': {'EN': 'Kobe Bryant'}, 'value': 999},
        {'Anim ID': 'SIG_FREE_THROW_LUP_K_BRYANT', 'Anim Name': {'EN': 'Wrong Field'}},
        {'Anim ID': 'SIG_LAYUP_UNKNOWN', 'Anim Name': {'EN': 'Unknown Symbol'}},
        {'Anim ID': 'SIG_LAYUP_LUP_K_BRYANT', 'Anim Name': {'EN': 'Conflicting Label'}},
        {'Anim ID': 'SIG_LAYUP_LUP_M_JORDAN', 'Anim Name': {'EN': 'Conflicting Label'}},
    ]}]}
    result = add_glossary_labels(catalog, glossary, {'url': 'test-fixture'})
    table = result['enums']['SIG_LAYUP']
    assert table['values']['LUP_K_BRYANT'] == 15
    assert table['labels']['Kobe Bryant'] == ['LUP_K_BRYANT']
    assert table['labels']['Conflicting Label'] == ['LUP_K_BRYANT', 'LUP_M_JORDAN']
    assert 'Wrong Field' not in table['labels'] and 'Unknown Symbol' not in table['labels']


def test_glossary_refresh_preserves_reviewed_spellings_and_retains_conflicts():
    catalog = {'enums': {'SIG_SHOT_JUMPER': {
        'values': {'HARRY_GILES_III': 262, 'OTHER_PLAYER': 500},
        'label_reviews': {'Harry Giles': {'symbol': 'HARRY_GILES_III', 'source': 'test-fixture'},
                          'Removed': {'symbol': 'MISSING', 'source': 'test-fixture'}}}}}
    glossary = [{'Anim ID': 'SIG_SHOT_JUMPER_OTHER_PLAYER', 'Anim Name': {'EN': 'Harry Giles'}}]
    result = add_glossary_labels(catalog, glossary, {'url': 'test-fixture'})
    labels = result['enums']['SIG_SHOT_JUMPER']['labels']
    assert labels['Harry Giles'] == ['HARRY_GILES_III', 'OTHER_PLAYER']
    assert 'Removed' not in labels

