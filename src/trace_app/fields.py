"""Profile-driven little-endian record decoding and packed-field encoding."""

import math
import struct
from dataclasses import dataclass

from .roster import RosterError
from .trc import CATEGORIES
from .mappings import expand_profile
from .mappings import label_key


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


@dataclass(frozen=True)
class Field:
    category: str
    name: str
    offset: int
    bits: int
    shift: int
    kind: str = 'bits'
    writable: bool = True
    verified_build: str | None = None
    allowed_values: tuple | None = None

    @property
    def size(self):
        return (self.shift + self.bits + 7) // 8

    def decode(self, record):
        raw = record[self.offset:self.offset + self.size]
        if len(raw) != self.size:
            raise RosterError(f'{self.name}: truncated record.')
        if self.kind == 'float':
            value = struct.unpack('<f', raw)[0]
            return value if math.isfinite(value) else None
        if self.kind == 'utf16':
            end = next((i for i in range(0, len(raw), 2) if raw[i:i+2] == b'\0\0'), len(raw))
            return raw[:end].decode('utf-16-le')
        value = (int.from_bytes(raw, 'little') >> self.shift) & ((1 << self.bits) - 1)
        if self.kind == 'injury_days':
            return value // 1440 if value % 1440 == 0 else None
        return value // 3 + 25 if self.category == 'attributes' else value

    def encode(self, record, value):
        if not self.writable:
            raise RosterError(f'{self.name}: this field is read only.')
        if self.kind == 'utf16':
            if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
                raise RosterError(f'{self.name}: enter a non-empty name without control characters.')
            raw = value.encode('utf-16-le') + b'\0\0'
            if len(raw) > self.size:
                raise RosterError(f'{self.name}: name must fit in 19 UTF-16 code units.')
            record[self.offset:self.offset + len(raw)] = raw
            return
        if self.kind == 'float':
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise RosterError(f'{self.name}: enter a positive finite number in game units.')
            try:
                record[self.offset:self.offset + self.size] = struct.pack('<f', value)
            except (OverflowError, struct.error) as error:
                raise RosterError(f'{self.name}: value cannot be represented as a game float.') from error
            return
        if type(value) is not int:
            raise RosterError(f'{self.name}: requires a numeric game ID or integer value.')
        if self.kind == 'college_reference' and (not 0x10000 <= value <= 0x7FFFFFFFFFFF or value % 8):
            raise RosterError('College / From: invalid internal catalog reference.')
        if self.allowed_values is not None and value not in self.allowed_values:
            raise RosterError(f'{self.name}: choose a supported field value.')
        minimum, maximum = (25, 99) if self.category == 'attributes' else (0, (1 << self.bits) - 1)
        if self.kind == 'injury_days':
            maximum = ((1 << self.bits) - 1) // 1440
        if self.category == 'tendencies':
            maximum = 100
        if self.category == 'badges':
            maximum = 5
        if not minimum <= value <= maximum:
            raise RosterError(f'{self.name}: game value must be from {minimum} to {maximum}.')
        encoded = value * 1440 if self.kind == 'injury_days' else (value - 25) * 3 if self.category == 'attributes' else value
        raw = int.from_bytes(record[self.offset:self.offset + self.size], 'little')
        mask = ((1 << self.bits) - 1) << self.shift
        record[self.offset:self.offset + self.size] = ((raw & ~mask) | (encoded << self.shift)).to_bytes(self.size, 'little')


class RecordProfile:
    def __init__(self, document):
        document = expand_profile(document)
        self.document = document
        self.base = document['Base']
        self.stride = number(self.base['Player Offset Length'])
        self.pointer_offset = number(self.base['Player Base Address'])
        self.fields = {}
        self.ambiguous = set()
        for section, category in CATEGORIES.items():
            for item in document.get(section, []):
                field = Field(category, item.get('id', item.get('name')), number(item['offset']),
                              number(item.get('bits', item.get('length'))),
                              number(item.get('shift', item.get('startBit', 0))), item.get('kind', 'bits'), item.get('writable', True),
                              item.get('verified_build'), (None if item.get('allow_numeric_ids') else
                              tuple(item['options'].values()) if item.get('options') else
                              tuple(range(item.get('minimum', 0), item['maximum'] + 1)) if 'maximum' in item else None))
                if field.bits <= 0 or field.shift < 0 or field.offset < 0 or field.offset + field.size > self.stride:
                    raise RosterError(f'{field.name}: field is outside the player record.')
                key = (category, field.name)
                if key in self.fields or key in self.ambiguous:
                    self.ambiguous.add(key)
                    self.fields.pop(key, None)
                else:
                    self.fields[key] = field
        self.aliases = {}
        for (category, name), field in self.fields.items():
            if field.writable:
                self.aliases[category, label_key(name)] = name
                if category in ('gear', 'accessories'):
                    self.aliases[category, label_key(name.replace(' Item ', ' ').replace(' Items ', ' '))] = name
        gear_aliases = {'Shoe Home': 'Shoe Home Style', 'Shoe Away': 'Shoe Away Style',
                        'Sock Length Home': 'Socks Item Home', 'Sock Length Away': 'Socks Item Away',
                        'Shorts': 'Shorts Items', 'Shorts Preferred Type': 'Preferred Shorts Type',
                        'Shorts Frequency': 'Shorts Item Frequency', 'Undershirt': 'Shirts Items',
                        'Undershirt Home Color': 'Shirts Items Home Color',
                        'Undershirt Away Color': 'Shirts Items Away Color'}
        for alias, name in gear_aliases.items():
            if ('gear', name) in self.fields:
                self.aliases['gear', label_key(alias)] = name
        self.aliases['accessories', label_key('Headband Logo')] = 'Headband Logo Position'
        if ('attributes', 'Miscellaneous Durability') in self.fields:
            self.aliases['attributes', label_key('Miscanellous Durability')] = 'Miscellaneous Durability'

    def canonical_name(self, category, name):
        return self.aliases.get((category, label_key(name)), name)

    def canonical_document(self, document):
        from .roster import validate_roster
        result = validate_roster(document)
        for player in result['players']:
            for category in CATEGORIES.values():
                normalized = {}
                for name, value in player[category].items():
                    key = self.canonical_name(category, name)
                    if key in normalized and normalized[key] != value:
                        raise RosterError(f'{player["name"]}: conflicting values for {key}.')
                    normalized[key] = value
                player[category] = normalized
        return result

    def decode(self, record, build=None):
        values = {category: {} for category in CATEGORIES.values()}
        for field in self.fields.values():
            if field.kind == 'college_reference':
                continue  # References are resolved to portable labels by GameConnection.
            if field.verified_build and (build or '').casefold() != field.verified_build.casefold():
                continue
            value = field.decode(record)
            if field.allowed_values is not None and value not in field.allowed_values:
                continue
            # Reserved bit patterns are not valid roster values.
            maximum = {'attributes': 99, 'tendencies': 100, 'badges': 5}.get(field.category)
            if value is not None and (maximum is None or value <= maximum):
                values[field.category][field.name] = value
        return values

    def patch(self, before, player, normalize=None, build=None):
        after, changes, warnings = bytearray(before), [], []
        for category in CATEGORIES.values():
            for name, value in player.get(category, {}).items():
                field = self.fields.get((category, name))
                # Advanced definitions include caches, IDs and overlapping fields.
                if (not field or not field.writable or
                        (field.verified_build and (build or '').casefold() != field.verified_build.casefold())):
                    if category != 'advanced' or value != (field.decode(before) if field else None):
                        warnings.append(f'{name}: no enabled memory mapping; skipped.')
                    continue
                if value == field.decode(before):
                    continue
                try:
                    if field.kind == 'college_reference' and normalize is None:
                        raise RosterError('College / From requires a validated live catalog.')
                    if normalize:
                        value = normalize(category, name, value)
                    if value == field.decode(before):
                        continue
                    field.encode(after, value)
                except RosterError as error:
                    warnings.append(str(error))
                    continue
                changes.append({'field': name, 'category': category, 'old': field.decode(before), 'value': field.decode(after)})
        return bytes(after), changes, warnings
