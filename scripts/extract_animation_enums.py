"""Extract explicit animation enums from an on-disk executable, without process access.

Outputs evidence for review; does not access a process or install the catalog.
Usage: python scripts/extract_animation_enums.py NBA2K27.exe output.json
"""

import argparse
import hashlib
import json
import mmap
import re
import struct
import zlib
from pathlib import Path


def extract(data):
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    if data[:2] != b'MZ' or data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Expected a PE executable.')
    build = f'{struct.unpack_from("<I", data, pe + 8)[0]:08X}:{struct.unpack_from("<I", data, pe + 0x50)[0]:X}'
    results = []
    for match in re.finditer(rb'\x00(SIG_[A-Z0-9_]+|PLAYERDATA_DUNK_PACKAGE)\x00', data):
        position, names = match.end(), []
        while len(names) < 2000:
            end = data.find(b'\0', position, position + 180)
            if end < 0:
                break
            name, position = data[position:end], end + 1
            if not name:
                continue
            if name.startswith((b'SIG_', b'PLAYERDATA_')) or not re.fullmatch(rb'[A-Za-z0-9_]+', name):
                break
            names.append(name)
        if len(names) < 2:
            continue
        tables, position = [], 0
        needle = struct.pack('<I', zlib.crc32(names[0]))
        while True:
            position = data.find(needle, position)
            if position < 0:
                break
            size = 12 * len(names)
            if position + size <= len(data):
                entries = [struct.unpack_from('<III', data, position + i * 12) for i in range(len(names))]
                if all(crc == zlib.crc32(name) and padding == 0
                       for name, (crc, value, padding) in zip(names, entries)):
                    tables.append({'file_offset': position,
                                   'sha256': hashlib.sha256(data[position:position + size]).hexdigest(),
                                   'values': [value for crc, value, padding in entries]})
            position += 4
        consistent = bool(tables) and all(t['values'] == tables[0]['values'] for t in tables)
        results.append({'enum': match.group(1).decode(), 'name_block_file_offset': match.start() + 1,
                        'name_count': len(names), 'consistent_explicit_tables': consistent,
                        'tables': tables,
                        'entries': [{'symbol': name.decode(), 'value': value}
                                    for name, value in zip(names, tables[0]['values'])] if consistent else []})
    return {'build': build, 'source': 'on-disk PE; no running-process access',
            'write_authorized': False, 'enums': results}


def extract_registered(data, fields):
    """Use native registration bounds and packed reflection, not string boundaries.

    fields contains (display name, byte offset, bit width, bit shift) tuples.
    The exact four-LEA registration form is intentionally conservative; unknown
    code forms are omitted. No process access or game execution is performed.
    """
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Expected a PE executable.')
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Expected a PE executable.')
    optional = struct.unpack_from('<H', data, pe + 20)[0]
    image = struct.unpack_from('<Q', data, pe + 48)[0]
    build = f'{struct.unpack_from("<I", data, pe + 8)[0]:08X}:{struct.unpack_from("<I", data, pe + 0x50)[0]:X}'
    sections = []
    for index in range(struct.unpack_from('<H', data, pe + 6)[0]):
        offset = pe + 24 + optional + index * 40
        virtual_size, rva, size, pointer = struct.unpack_from('<4I', data, offset + 8)
        flags = struct.unpack_from('<I', data, offset + 36)[0]
        if pointer + size > len(data):
            raise ValueError('Truncated PE section.')
        sections.append((rva, pointer, size, flags))

    def read(rva, size):
        for start, pointer, length, flags in sections:
            if start <= rva and rva + size <= start + length:
                offset = pointer + rva - start
                return data[offset:offset + size]
        raise ValueError('Unbacked PE RVA.')

    def string(rva):
        value = bytearray()
        for index in range(180):
            byte = read(rva + index, 1)
            if byte == b'\0':
                return bytes(value)
            value.extend(byte)
        raise ValueError('Unterminated native symbol.')

    result = {'version': 1, 'build': build,
              'source': 'Native on-disk enum registrations and packed reflection; no process access',
              'enums': {}, 'fields': {}}
    registrations, duplicate_enums = {}, set()
    pattern = rb'\x48\x8d\x0d....\x48\x8d\x15....\x4c\x8d\x05....\x4c\x8d\x0d....\xe9....'
    for start, pointer, length, flags in sections:
        if not flags & 0x20000000:
            continue
        for hit in re.finditer(pattern, data[pointer:pointer + length], re.DOTALL):
            registration = start + hit.start()
            code = hit.group()
            args = [registration + 7 * index + 7 + struct.unpack_from('<i', code, 7 * index + 3)[0]
                    for index in range(4)]
            try:
                enum_bytes = string(args[3])
                enum = enum_bytes.decode('ascii')
                if (not enum.startswith(('SIG_', 'PLAYERDATA_DUNK_PACKAGE')) or
                        enum.endswith('_WITH_NO_CHANGE')):
                    continue
                header = read(args[1], 20)
                crc, type_flags, padding, count, size = struct.unpack('<5I', header)
                if (crc != zlib.crc32(enum_bytes) or size != 4 or
                        not 0 < count < 2000 or not 0 <= args[1] - args[2] - count * 12 <= 7):
                    continue
                table = read(args[2], count * 12)
                position = args[3] + len(enum_bytes) + 1
                names = bytearray(enum_bytes + b'\0')
                values = {}
                for index in range(count):
                    symbol = string(position)
                    position += len(symbol) + 1
                    names.extend(symbol + b'\0')
                    name_crc, value, reserved = struct.unpack_from('<III', table, index * 12)
                    if name_crc != zlib.crc32(symbol) or reserved or symbol.decode() in values:
                        raise ValueError('Enum symbols do not match the explicit table.')
                    values[symbol.decode('ascii')] = value
                if enum in registrations or enum in duplicate_enums:
                    registrations.pop(enum, None)
                    duplicate_enums.add(enum)
                    continue
                registrations[enum] = {
                    'values': values, 'registration_rva': registration, 'registration_hex': code.hex(),
                    'descriptor_rva': args[0], 'header_rva': args[1], 'header_hex': header.hex(),
                    'table_rva': args[2], 'table_sha256': hashlib.sha256(table).hexdigest(),
                    'names_rva': args[3], 'names_sha256': hashlib.sha256(names).hexdigest()}
            except (ValueError, UnicodeError, struct.error):
                continue
    for enum, entry in registrations.items():
        needle = struct.pack('<Q', image + entry['descriptor_rva'])
        for start, pointer, length, flags in sections:
            if flags & 0x20000000:
                continue
            position = pointer
            while True:
                position = data.find(needle, position, pointer + length)
                if position < 0:
                    break
                property_offset = position - 32
                position += 8
                if property_offset < pointer:
                    continue
                encoded = data[property_offset:property_offset + 40]
                name_crc, type_crc, offset, size, packed, padding, descriptor = struct.unpack('<IIIIQQQ', encoded)
                bits, shift = (packed >> 8) & 255, (packed >> 16) & 255
                if type_crc != zlib.crc32(enum.encode()) or size != 4 or padding:
                    continue
                for name, field_offset, field_bits, field_shift in fields:
                    if bits != field_bits or offset * 8 + shift != field_offset * 8 + field_shift:
                        continue
                    if any(value >= 2 ** bits for value in entry['values'].values()):
                        continue
                    binding = result['fields'].setdefault(name, {
                        'enum': enum, 'layout': [field_offset, field_bits, field_shift], 'properties': []})
                    if binding['enum'] != enum:
                        raise ValueError(f'Ambiguous enum binding for {name}.')
                    binding['properties'].append({'property_rva': start + property_offset - pointer,
                                                 'property_hex': encoded.hex(), 'name_crc': name_crc})
                    result['enums'][enum] = entry
    # This existing field has a native bool32 property rather than an enum.
    # Off/On are the ordinary false/true labels; no animation IDs are inferred.
    for name, field_offset, field_bits, field_shift in fields:
        if name != 'Chew Gum' or field_bits != 1:
            continue
        needle = struct.pack('<II', zlib.crc32(b'GumChewer'), zlib.crc32(b'bool32'))
        properties = []
        for start, pointer, length, flags in sections:
            if flags & 0x20000000:
                continue
            position = pointer
            while True:
                position = data.find(needle, position, pointer + length)
                if position < 0:
                    break
                encoded = data[position:position + 40]
                if len(encoded) < 40:
                    break
                name_crc, type_crc, offset, size, packed, padding, descriptor = struct.unpack('<IIIIQQQ', encoded)
                if (size == 4 and not padding and not descriptor and (packed >> 8) & 255 == 1 and
                        offset * 8 + ((packed >> 16) & 255) == field_offset * 8 + field_shift):
                    properties.append({'property_rva': start + position - pointer, 'property_hex': encoded.hex()})
                position += 4
        if properties:
            result.setdefault('primitives', {})[name] = {
                'layout': [field_offset, field_bits, field_shift], 'type': 'bool32',
                'values': {'FALSE': 0, 'TRUE': 1}, 'labels': {'Off': ['FALSE'], 'On': ['TRUE']},
                'properties': properties}
    return result


def add_glossary_labels(catalog, glossary, source):
    """Join English labels through exact full enum+symbol keys; never import IDs.

    The HQ glossary and executable can have different versions. A label is
    usable only when its exact symbolic key exists in the bound native enum.
    Conflicting labels are kept as multiple targets so resolution fails closed.
    """
    records = []

    def walk(node):
        if isinstance(node, dict):
            key, label = node.get('Anim ID'), node.get('Anim Name', {}).get('EN')
            if isinstance(key, str) and isinstance(label, str) and label.strip():
                records.append((key, label))
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(glossary)
    for enum, entry in catalog['enums'].items():
        labels = {}
        # Retain separately documented spelling reviews when refreshing HQ
        # labels. The target must still exist in this exact native enum.
        for label, review in entry.get('label_reviews', {}).items():
            symbol = review.get('symbol')
            if symbol in entry['values']:
                labels.setdefault(label, set()).add(symbol)
        prefix = enum + '_'
        for key, label in records:
            if key.startswith(prefix) and key[len(prefix):] in entry['values']:
                labels.setdefault(label, set()).add(key[len(prefix):])
        entry['labels'] = {label: sorted(symbols) for label, symbols in sorted(labels.items())}
    catalog['label_source'] = source
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--profile', type=Path, default=Path(__file__).parents[1] / 'config' / 'offsets_2k27.json')
    parser.add_argument('--heuristic', action='store_true', help='Use the earlier exploratory string-block scan.')
    parser.add_argument('--glossary', type=Path, help='Optional HQ animation glossary JSON; label-to-symbol joins only.')
    parser.add_argument('--glossary-source', help='Source URL or immutable revision for the optional glossary.')
    args = parser.parse_args()
    with args.executable.open('rb') as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        if args.heuristic:
            result = extract(data)
        else:
            import sys
            sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
            from trace_app.fields import RecordProfile
            profile = RecordProfile(json.loads(args.profile.read_text(encoding='utf-8')))
            fields = [(name, field.offset, field.bits, field.shift)
                      for (category, name), field in profile.fields.items() if category == 'signatures']
            result = extract_registered(data, fields)
            if args.glossary:
                if not args.glossary_source:
                    parser.error('--glossary-source is required with --glossary')
                result = add_glossary_labels(result, json.loads(args.glossary.read_text(encoding='utf-8')),
                                             {'url': args.glossary_source, 'role': 'labels only; IDs from native tables'})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    if args.heuristic:
        for item in result['enums']:
            print(item['enum'], item['name_count'], 'names;', len(item['tables']), 'explicit tables;',
                  'consistent' if item['consistent_explicit_tables'] else 'unresolved')
    else:
        print(result['build'], len(result['fields']), 'bound fields;', len(result['enums']), 'registered enums')


if __name__ == '__main__':
    main()

