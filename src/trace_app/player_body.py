"""Exact-build reads and encoding for the separately allocated Body structure.

These are deliberately outside RecordProfile: offsets here are relative to a
validated runtime pointer, never offsets within the main player record.
"""

import math
import struct
import hashlib

from .roster import RosterError


BODY_BUILD = '6ad2e48c:36532000'
BODY_POINTER = 0x78
BODY_SIZE = 0x1C
BODY_MODEL_RVA = 0xBB9BE20
MODEL_CODE_HASHES = {
    0x7BAAD0: (0x1B5, 'fd3dbdf9b9b22e3dca104b0c6bee58d6d2614b1a39c71020123b4139746ece57'),
    0x3D1DB90: (0x37E, 'ae9de2977127ee9a8b6251970d043f707ee440686138b7d3d498350a78ee3d8b'),
    0x2E24B30: (0xD3, '592d0c3635fae15354fa04853ba86aa1cb6f1cd8043c09720fb91a52339c174a'),
}
MODEL_CONSTANTS = {0x5D0E560: '0ad7233c', 0x5D0DAC8: '0000c842',
                   0x5D00440: '0000003f', 0x5D00398: '0000803f', 0x5D00434: 'ffffff7f'}
MODEL_PARENTS = (-1, 0, 1, 2, 3, 4, 3, 6, 7, 8, 3, 10, 11, 12, 0, 14, 15, 16, 0, 18, 19, 20)
# Independently observed at 50 and in two distinct combined edit captures.
BODY_SCALES = {
    'Wingspan': (0x0C, 0.002),
    'Shoulder Width': (0x08, 0.002),
    'Neck Length': (0x10, 0.004),
    'Trunk Length': (0x04, 0.004),
}


def body_schema():
    return [{'name': name, 'kind': 'float' if name == 'Height' else 'bits',
             'bits': 15 if name == 'Height' else 32,
             'writable': True, 'readOnly': False, 'verified_build': BODY_BUILD,
             'linkedBody': True,
             **({'units': 'inches', 'minimum': 1, 'maximum': 129} if name == 'Height' else {'minimum': 0, 'maximum': 100})}
            for name in ('Height', *BODY_SCALES)]


def decode_body(raw):
    if len(raw) < 0x14:
        return {}
    # Height is an unsigned 16-bit count of hundredths of a centimetre.
    height = struct.unpack_from('<H', raw)[0] & 0x7FFF
    if not height:
        return {}
    values = {'Height': round(height / 254, 2)}
    for name, (offset, step) in BODY_SCALES.items():
        scale = struct.unpack_from('<f', raw, offset)[0]
        if not math.isfinite(scale):
            return {}
        slider = 50 + (scale - 1) / step
        # Reject unsupported scale values instead of clamping or inventing IDs.
        if not -0.0001 <= slider <= 100.0001 or abs(slider - round(slider)) > 0.0001:
            return {}
        values[name] = round(slider)
    return values


def read_body(process, profile, record, player_address):
    if (process.build.casefold() != BODY_BUILD or profile.stride != 0x4F8 or
            len(record) != profile.stride):
        return {}
    pointer_bytes = record[BODY_POINTER:BODY_POINTER + 8]
    pointer = int.from_bytes(pointer_bytes, 'little')
    if not 0x10000 <= pointer <= 0x7FFFFFFFFFFF - 0x14 or pointer % 4:
        return {}
    try:
        raw = process.read(pointer, 0x14)
        # Do not publish a readout if the player or its Body allocation changed.
        fresh = process.read(player_address, profile.stride)
        if (fresh[:0x58] != record[:0x58] or
                fresh[BODY_POINTER:BODY_POINTER + 8] != pointer_bytes or
                process.read(pointer, 0x14) != raw):
            return {}
        return decode_body(raw)
    except (RosterError, OSError):
        return {}


def is_body_field(category, name):
    return category == 'vitals' and name in ('Height', *BODY_SCALES)


def snapshot_body(process, profile, record, player_address):
    if process.build.casefold() != BODY_BUILD or profile.stride != 0x4F8:
        raise RosterError('Body editing is not mapped for this player layout.')
    pointer = int.from_bytes(record[BODY_POINTER:BODY_POINTER+8], 'little')
    if not 0x10000 <= pointer <= 0x7FFFFFFFFFFF-BODY_SIZE or pointer % 4:
        raise RosterError('Invalid Body pointer.')
    raw = process.read(pointer, BODY_SIZE)
    fresh = process.read(player_address, profile.stride)
    if (not decode_body(raw) or fresh[:0x58] != record[:0x58] or
            fresh[BODY_POINTER:BODY_POINTER+8] != record[BODY_POINTER:BODY_POINTER+8] or
            process.read(pointer, BODY_SIZE) != raw):
        raise RosterError('Body values changed or are not recognized. Reload the roster.')
    return {'pointer': pointer, 'data': raw}


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def read_body_model(process):
    """Resolve and validate the model used by the native wingspan calculation."""
    if process.build.casefold() != BODY_BUILD:
        raise RosterError('Body editing is not mapped for this executable build.')
    for rva, (size, digest) in MODEL_CODE_HASHES.items():
        if hashlib.sha256(process.read(process.module_base + rva, size)).hexdigest() != digest:
            raise RosterError('Body calculation code does not match the verified build.')
    for rva, expected in MODEL_CONSTANTS.items():
        if process.read(process.module_base+rva, 4) != bytes.fromhex(expected):
            raise RosterError('Body calculation constants do not match the verified build.')
    reads = []
    def read(address, size):
        if not 0x10000 <= address <= 0x7FFFFFFFFFFF - size:
            raise RosterError('Invalid Body model address.')
        raw = process.read(address, size)
        reads.append((address, raw))
        return raw
    global_address = process.module_base + BODY_MODEL_RVA
    pointer = struct.unpack('<Q', read(global_address, 8))[0]
    header = read(pointer, 0x60)
    count = struct.unpack_from('<I', header, 0x4C)[0]
    if count != len(MODEL_PARENTS):
        raise RosterError('The loaded Body model layout is not supported.')
    def array(offset, fmt, size):
        address = struct.unpack_from('<Q', header, offset)[0]
        return struct.unpack(fmt, read(address, size))
    parents = array(8, '<22i', 88)
    positions = array(0x10, '<88f', 352)
    landmarks = array(0x28, '<14i', 56)
    groups = array(0x38, '<22i', 88)
    height, span = struct.unpack_from('<2f', header, 0x54)
    if (parents != MODEL_PARENTS or landmarks[10] != 10 or landmarks[13] != 13 or
            any(group not in range(7) for group in groups) or
            any(not math.isfinite(v) for v in (*positions, height, span)) or
            height <= 0 or span <= 0):
        raise RosterError('The loaded Body model values are not supported.')
    if any(process.read(address, len(raw)) != raw for address, raw in reads):
        raise RosterError('The Body model changed during the read.')
    fingerprint = hashlib.sha256(b''.join(struct.pack('<Q', address) + raw for address, raw in reads)).hexdigest()
    return {'parents': parents, 'positions': [positions[i:i+4] for i in range(0, 88, 4)],
            'groups': groups, 'height': height, 'span': span, 'fingerprint': fingerprint}


def body_span(raw, model):
    """Reproduce the verified native helper with float32 operation rounding.

    The validated model has one leaf at 13 and its shoulder at 10. The native
    helper uses neutral arm scale while computing the base span, then the
    forward caller multiplies the result by the stored arm scale.
    """
    if len(raw) != BODY_SIZE or not decode_body(raw):
        raise RosterError('Body values are not recognized; reload or validate them in the game.')
    scalars = [struct.unpack_from('<f', raw, o)[0] for o in (0x14, 4, 8)]
    scalars += [1.0] + [struct.unpack_from('<f', raw, o)[0] for o in (0x10, 0x18)]
    if any(not math.isfinite(v) or v <= 0 for v in scalars):
        raise RosterError('Body model scales are invalid.')
    ratio = f32(f32((int.from_bytes(raw[:2], 'little') & 0x7FFF) * f32(0.01)) / model['height'])
    arm = base_arm = 0.0
    bone = 13
    while bone != 10:
        squares = [f32(v*v) for v in model['positions'][bone]]
        length = f32(math.sqrt(f32(f32(squares[0]+squares[1]) + f32(squares[2]+squares[3]))))
        group = model['groups'][bone]
        scale = scalars[group] if group <= 5 else 1.0
        arm = f32(arm + f32(length*scale))
        base_arm = f32(base_arm + length)
        bone = model['parents'][bone]
    x = base_x = 0.0
    while bone != -1:
        group = model['groups'][bone]
        scale = scalars[group] if group <= 5 else 1.0
        x = f32(x + f32(model['positions'][bone][0]*scale))
        base_x = f32(base_x + model['positions'][bone][0])
        bone = model['parents'][bone]
    arm = f32(arm + abs(x))
    base_arm = f32(base_arm + abs(base_x))
    span = f32(f32(ratio+ratio) * f32(arm + f32(f32(model['span']*f32(0.5))-base_arm)))
    span = f32(span * struct.unpack_from('<f', raw, 0x0C)[0])
    encoded = round(f32(span*f32(100)))
    if not 1 <= encoded <= 0x7FFF:
        raise RosterError('Calculated wingspan is outside the supported game range.')
    return encoded


def encode_body(before, values, model):
    if body_span(before, model) != (int.from_bytes(before[2:4], 'little') & 0x7FFF):
        raise RosterError('Body measurements are inconsistent; validate them in the game before editing.')
    raw = bytearray(before)
    for name, value in values.items():
        if type(value) not in (int, float) or not math.isfinite(value) or int(value) != value:
            raise RosterError(f'{name}: enter a whole number.')
        value = int(value)
        if name == 'Height':
            if not 1 <= value <= 129:
                raise RosterError('Height must be from 1 to 129 whole inches.')
            height = (int.from_bytes(before[:2], 'little') & 0x8000) | value*254
            struct.pack_into('<H', raw, 0, height)
        elif name in BODY_SCALES:
            if not 0 <= value <= 100:
                raise RosterError(f'{name}: enter a whole number from 0 to 100.')
            offset, step = BODY_SCALES[name]
            struct.pack_into('<f', raw, offset, f32(1 + (value-50)*step))
        else:
            raise RosterError('Unknown Body field.')
    span = body_span(bytes(raw), model)
    struct.pack_into('<H', raw, 2, (int.from_bytes(before[2:4], 'little') & 0x8000) | span)
    return bytes(raw)
