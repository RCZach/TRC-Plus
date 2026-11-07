"""Exact-build, read-only team rotation, staff and coach-default readouts.

All references are resolved from validated team membership at load time.
No team/staff write support is implied by displaying these values.
"""

import hashlib
import struct
import zlib
from collections import defaultdict

from .roster import RosterError

TEAM_BUILD = '6ad2e48c:36532000'
TEAM_STAFF_OFFSET = 0xF70
STAFF_SIZE = 0x1A0
COACH_FIELDS = {'Help Defense': 357, 'Run Plays Frequency': 346, 'Zone Usage Frequency': 348, 'Tempo': 356, 'Off-ball Defense Aggressiveness': 340, 'On-ball Defense Aggressiveness': 341, 'Fastbreak': 342, 'Crash Boards': 343, 'Double Team Frequency': 347, 'Inside Shot Tendency': 349, 'Close Shot Tendency': 350, 'Mid-range Shot Tendency': 351, 'Three-point Shot Tendency': 352, 'Drive Tendency': 353, 'Post Up Tendency': 354, 'Alley-oop Tendency': 355}
CODE_PROOFS = {'TEAMDATA::SetLineupPlayerByIndex': (49386816, 1424, 'd0edb11ead13e2fde4e5c1ccadcfceba852ce5664f367619560953ea2340987d'), 'TEAMDATA::SetStaff_Internal': (49855904, 905, 'bfa49f588e871bc9b78fd2f66b53aaab389a4765299e20bd6e7d83514b6eb4cc'), 'STAFFDATA::SetCoachAttribute': (49808800, 584, '2428944047ae15a530df46485d138893b5c57a239a0fefadda3a34736a92822f'), 'PLAYERDATA::SetPlayingTime': (37055168, 211, '8c6571c5d7848e7ee9b434800b72241ede72305c2e890487c6053cdf989fa96f')}
PROPERTY_PROOFS = {'FirstName': (144900608, 'f52363a1a85ee84b50000000020000000010001601000100'), 'LastName': (144900648, 'de786068a85ee84b78000000020000000010001601000100'), 'Job': (144905888, '18a695c35d5ad41182010000010000000005000701000000'), 'HelpDefense': (144904488, 'c576b1af11c0ab8e65010000010000000008000401000000'), 'RunPlayTendency': (144904048, '8f28931011c0ab8e5a010000010000000008000401000000'), 'ZoneUsage': (144904128, '6942065c11c0ab8e5c010000010000000008000401000000'), 'Tempo': (144904448, '6bc474b511c0ab8e64010000010000000008000401000000'), 'STAFFDATA_JOB': (144899776, '7caf0dc80000000000000000d4433ce001000000000000003af650fa020000000000000010f68cf60300000000000000095eddcd0400000000000000cc24343805000000000000001f88e3e60600000000000000351d73aa0700000000000000887c3ead080000000000000008b84db009000000000000006c7d576a0a00000000000000eac966560b00000000000000f3244c3a0c000000000000005fd1bec70d0000000000000089b96c970e0000000000000033e8650e0f00000000000000a5d862791000000000000000064d06e71100000000000000629cb7fe1200000000000000d8cdbe671300000000000000a64524fd1400000000000000d97a0c031500000000000000cdacf2591600000000000000fe08374e170000000000000050c2e8ca1800000000000000de1b0a861900000000000000102dd37b1a00000000000000aa7cdae21b000000000000003c4cdd951c000000000000009fd9b90b1d0000000000000009e9be7c1e00000000000000b3b8b7e51f00000000000000'), 'OffBallDefAggressiveness': (144903808, '9b169fd811c0ab8e54010000010000000008000401000000'), 'OnBallDefAggressiveness': (144903848, 'e98a5bec11c0ab8e55010000010000000008000401000000'), 'Fastbreak': (144903888, 'a0ecadd011c0ab8e56010000010000000008000401000000'), 'Crashboard': (144903928, '780440f311c0ab8e57010000010000000008000401000000'), 'DoubleTeamTendency': (144904088, '4e82cb6b11c0ab8e5b010000010000000008000401000000'), 'ShotInsideTendency': (144904168, '8c07946511c0ab8e5d010000010000000008000401000000'), 'ShotCloseTendency': (144904208, '048beae511c0ab8e5e010000010000000008000401000000'), 'ShotMediumTendency': (144904248, '897bc59011c0ab8e5f010000010000000008000401000000'), 'ShotThreeTendency': (144904288, '9a684a6011c0ab8e60010000010000000008000401000000'), 'DriveTendency': (144904328, '630a1d0311c0ab8e61010000010000000008000401000000'), 'PostUpTendency': (144904368, 'a370941211c0ab8e62010000010000000008000401000000'), 'AlleyOopTendency': (144904408, '2a4c988d11c0ab8e63010000010000000008000401000000')}
STAFF_ROLES = ['COACH', 'SCOUT', 'TRAINER', 'GM', 'CFO', 'OWNER', 'HEAD_ASSISTANT', 'ASSISTANT_GM', 'SHOTDOCTOR', 'GUARDGURU', 'WINGWHISPERER', 'BIGMANCOACH', 'POSTDMASTER', 'PERIMETERDMASTER', 'DOMESTICSCOUT1', 'DOMESTICSCOUT2', 'DOMESTICSCOUT3', 'DOMESTICSCOUT4', 'FOREIGNSCOUT1', 'FOREIGNSCOUT2', 'STRENGTHTRAINER', 'STAMINATRAINER', 'SPORTSPSYCH', 'SPORTSSCIENCE', 'PHYSIO', 'SLEEPDOCTOR', 'FRONTOFFICEASSIST1', 'FRONTOFFICEASSIST2', 'FRONTOFFICEASSIST3', 'FRONTOFFICEASSIST4', 'FRONTOFFICEASSIST5', 'FRONTOFFICEASSIST6']



COACH_PROPERTY_NAMES = ('HelpDefense', 'RunPlayTendency', 'ZoneUsage', 'Tempo', 'OffBallDefAggressiveness', 'OnBallDefAggressiveness', 'Fastbreak', 'Crashboard', 'DoubleTeamTendency', 'ShotInsideTendency', 'ShotCloseTendency', 'ShotMediumTendency', 'ShotThreeTendency', 'DriveTendency', 'PostUpTendency', 'AlleyOopTendency')

# Each addition is named by its own reflection descriptor and written by the
# pinned native scalar setter; ratings are displayed under Staff.
COACH_RATING_FIELDS = ('Coach Offense', 'Coach Defense', 'Coach Business', 'Coach Training', 'Coach Charisma', 'Coach Analytics', 'Coach Potential')
COACH_FIELDS.update({'Lineup Form Factor': 345, 'Coach Offense': 362, 'Coach Defense': 363, 'Coach Business': 364, 'Coach Training': 365, 'Coach Charisma': 366, 'Coach Analytics': 367, 'Coach Potential': 305})
COACH_PROPERTY_NAMES += ('LineupFormFactor', 'Offense', 'Defense', 'Business', 'Training', 'Charisma', 'Analytics', 'GrowthPotential')
PROPERTY_PROOFS.update({
    'LineupFormFactor': (144904008, 'd7e1c60811c0ab8e59010000010000000008000401000000'),
    'Offense': (144904688, 'bdea8b9011c0ab8e6a010000010000000008000401000000'),
    'Defense': (144904728, 'e9cc181411c0ab8e6b010000010000000008000401000000'),
    'Business': (144904768, '6e0ca5f111c0ab8e6c010000010000000008000401000000'),
    'Training': (144904808, 'd9e8642c11c0ab8e6d010000010000000008000401000000'),
    'Charisma': (144904848, '115dacc011c0ab8e6e010000010000000008000401000000'),
    'Analytics': (144904888, '2b64336811c0ab8e6f010000010000000008000401000000'),
    'GrowthPotential': (144901328, 'e0e28efe81f32a0e30010000040000000008082401000000'),
})
CODE_PROOFS["STAFFDATA::SetAttribute"] = (49807680, 247, '1bd6fb20d665b1163e53cb6c70e561e8d1aabb7b037f2a48ae41f627a3395a1b')
DISPATCH_PROOFS = {
    'STAFFDATA::SetAttribute:0': (124993668, 28, 'de22b1c3a421a79348eb974c8b11a1aa60163b6ec9f7ebafc0def7914a0858ab'),
    'STAFFDATA::SetCoachAttribute:0': (124993820, 96, 'fd600301513d3dc693bb581c2809b4b2c4b829af20027220b4ac033abd4c7a19'),
    'STAFFDATA::SetCoachAttribute:1': (124993916, 28, '59f0844fedb712d956dc3eb9e2d54ba34e3b1931e67d3b27c50fcf411b8b3dc3'),
}

# The system setter stores an unsigned byte without additional receiver updates.
# TRACE intentionally accepts only 0–100, a subset of the native byte domain.
COACH_SYSTEM_FIELDS = ('Balanced Proficiency', 'Grit and Grind Proficiency', 'Pace and Space Proficiency', 'Perimeter Proficiency', 'Post Proficiency', 'Triangle Proficiency', 'Seven Seconds Proficiency', 'Defense First Proficiency')
COACH_RATING_FIELDS += COACH_SYSTEM_FIELDS
COACH_FIELDS.update({'Balanced Proficiency': 368, 'Grit and Grind Proficiency': 369, 'Pace and Space Proficiency': 370, 'Perimeter Proficiency': 371, 'Post Proficiency': 372, 'Triangle Proficiency': 373, 'Seven Seconds Proficiency': 374, 'Defense First Proficiency': 375})
COACH_PROPERTY_NAMES += ('SystemBalanced', 'SystemGritAndGrind', 'SystemPaceAndSpace', 'SystemPerimeter', 'SystemPost', 'SystemTriangle', 'SystemSevenSeconds', 'SystemDefenseFirst')
PROPERTY_PROOFS.update({
    'SystemBalanced': (144904928, 'a8e65d6e11c0ab8e70010000010000000008000401000000'),
    'SystemGritAndGrind': (144904968, '99d80f3511c0ab8e71010000010000000008000401000000'),
    'SystemPaceAndSpace': (144905008, '715ed12511c0ab8e72010000010000000008000401000000'),
    'SystemPerimeter': (144905048, '5855900f11c0ab8e73010000010000000008000401000000'),
    'SystemPost': (144905088, '4273363511c0ab8e74010000010000000008000401000000'),
    'SystemTriangle': (144905128, 'e7eabe7311c0ab8e75010000010000000008000401000000'),
    'SystemSevenSeconds': (144905168, '86493d1811c0ab8e76010000010000000008000401000000'),
    'SystemDefenseFirst': (144905208, '08413f2a11c0ab8e77010000010000000008000401000000'),
})
CODE_PROOFS["STAFFDATA::SetSystemAbilityByIndex"] = (49809696, 258, '8931d2da371500a7f1195718eda8651adf8ec86675731b3b86d28042c4d3d39f')
DISPATCH_PROOFS["STAFFDATA::SetSystemAbilityByIndex:0"] = (124993976, 32, '2a8ffba3a888c64440ef390d4e81c4bb9fa3e36e08b53e55082b6522c862d62f')


def verified_team_sections(process, profile):
    if process.build.casefold() != TEAM_BUILD or profile.stride != 0x4F8:
        return set()
    code_ok, property_ok = {}, {}
    for name, (rva, size, digest) in CODE_PROOFS.items():
        try:
            raw = process.read(process.module_base + rva, size)
            code_ok[name] = len(raw) == size and hashlib.sha256(raw).hexdigest() == digest
        except (RosterError, OSError):
            code_ok[name] = False
    for name, (rva, encoded) in PROPERTY_PROOFS.items():
        expected = bytes.fromhex(encoded)
        try:
            raw = process.read(process.module_base + rva, len(expected))
            if name in COACH_PROPERTY_NAMES:
                # Startup resolves uint8_t/uint32_t aliases to canonical u8/u32.
                property_ok[name] = (len(raw) == 24 and raw[:4] == expected[:4] and raw[8:] == expected[8:] and
                                     int.from_bytes(raw[4:8], 'little') in
                                     ((zlib.crc32(b'uint32_t'), zlib.crc32(b'u32')) if name == 'GrowthPotential' else
                                      (zlib.crc32(b'uint8_t'), zlib.crc32(b'u8'))))
            else:
                property_ok[name] = raw == expected
        except (RosterError, OSError):
            property_ok[name] = False
    dispatch_ok = True
    for rva, size, digest in DISPATCH_PROOFS.values():
        try:
            dispatch_ok = dispatch_ok and hashlib.sha256(process.read(process.module_base + rva, size)).hexdigest() == digest
        except (RosterError, OSError):
            dispatch_ok = False
    enabled = set()
    field = profile.fields.get(('advanced', 'PLAYINGTIME'))
    if (code_ok['TEAMDATA::SetLineupPlayerByIndex'] and code_ok['PLAYERDATA::SetPlayingTime'] and field and
            (field.offset, field.bits, field.shift, field.kind) == (0x12C, 7, 15, 'bits')):
        enabled.add('rotation')
    if (code_ok['TEAMDATA::SetStaff_Internal'] and
            all(property_ok.get(k) for k in ('FirstName', 'LastName', 'Job', 'STAFFDATA_JOB'))):
        enabled.add('staff')
        if (code_ok['STAFFDATA::SetCoachAttribute'] and code_ok['STAFFDATA::SetAttribute'] and
                code_ok['STAFFDATA::SetSystemAbilityByIndex'] and dispatch_ok and
                all(property_ok.get(k) for k in COACH_PROPERTY_NAMES)):
            enabled.add('coaching')
    return enabled


def staff_readout(raw, role):
    if len(raw) != STAFF_SIZE or raw[0x182] & 31 != role:
        return None
    names = []
    try:
        for start in (0x50, 0x78):
            text = raw[start:start+40].decode('utf-16-le')
            if '\0' not in text:
                return None
            name = text.split('\0', 1)[0].strip()
            if any(not c.isprintable() for c in name):
                return None
            names.append(name)
    except UnicodeError:
        return None
    full = ' '.join(n for n in names if n)
    if not full:
        return None
    return {'role_code': role, 'role': STAFF_ROLES[role], 'name': full}


def populate_team_sections(process, profile, base, players, records, teams, snapshots=None):
    if not teams or not players:
        return
    enabled = verified_team_sections(process, profile)
    if not enabled:
        return
    groups = defaultdict(list)
    for player in players:
        if player.get('team_id'):
            groups[player['team_id']].append(player)
    for team in teams:
        group = groups[team['team_id']]
        if not group:
            continue
        pointer = int.from_bytes(records[group[0]['player_id']][0x60:0x68], 'little')
        if not 0x10000 <= pointer <= 0x7FFFFFFFFFFF - 0x1070 or pointer % 8:
            continue
        try:
            header = process.read(pointer, 0x358)
            expected = {base + p['metadata']['game_index'] * profile.stride for p in group}
            members = [v for v in struct.unpack_from('<20Q', header) if v]
            if len(set(members)) != len(members) or set(members) != expected:
                continue
            by_address = {base + p['metadata']['game_index'] * profile.stride: p['player_id'] for p in group}
            fresh_records = {}
            for address in expected:
                row = process.read(address, profile.stride)
                snapshot = records[by_address[address]]
                if row[:0x58] != snapshot[:0x58] or row[0x60:0x68] != pointer.to_bytes(8, 'little'):
                    break
                fresh_records[address] = row
            if len(fresh_records) != len(expected):
                continue
            sections = {}
            if 'rotation' in enabled:
                field = profile.fields['advanced', 'PLAYINGTIME']
                minutes = {by_address[address]: field.decode(fresh_records[address]) for address in members}
                sections['rotation'] = {'player_ids': [by_address[a] for a in members], 'minutes': minutes,
                                        'total_minutes': sum(minutes.values()), 'read_only': True, 'source': 'game'}
            coach, coach_pointer = None, None
            if 'staff' in enabled:
                try:
                    slots_raw = process.read(pointer + TEAM_STAFF_OFFSET, 32 * 8)
                    staff, coach = [], None
                    for role, child in enumerate(struct.unpack('<32Q', slots_raw)):
                        if not 0x10000 <= child <= 0x7FFFFFFFFFFF - STAFF_SIZE or child % 8:
                            continue
                        try:
                            raw = process.read(child, STAFF_SIZE)
                            entry = staff_readout(raw, role)
                            if not entry or process.read(child, STAFF_SIZE) != raw:
                                continue
                            staff.append(entry)
                            if role == 0:
                                coach = (entry, raw)
                                coach_pointer = child
                        except (RosterError, OSError):
                            continue
                    if process.read(pointer + TEAM_STAFF_OFFSET, len(slots_raw)) == slots_raw:
                        sections['staff'] = {'entries': staff, 'read_only': True, 'source': 'game'}
                        if 'coaching' in enabled and coach:
                            values = {name: coach[1][offset] for name, offset in COACH_FIELDS.items()
                                      if coach[1][offset] <= 100}
                            sections['coaching'] = {'values': values, 'coach': coach[0]['name'],
                                                    'read_only': True, 'source': 'coach_defaults',
                                                    'field_order': list(COACH_FIELDS), 'rating_fields': list(COACH_RATING_FIELDS)}
                except (RosterError, OSError, struct.error):
                    pass
            # Avoid combining a moved team or changed minutes with old members.
            if process.read(pointer, len(header)) != header:
                continue
            stable = True
            for address, before in fresh_records.items():
                after = process.read(address, profile.stride)
                if (after[:0x58] != before[:0x58] or after[0x60:0x68] != before[0x60:0x68] or
                        ('rotation' in enabled and profile.fields['advanced', 'PLAYINGTIME'].decode(after) !=
                         profile.fields['advanced', 'PLAYINGTIME'].decode(before))):
                    stable = False
                    break
            if stable:
                team.update(sections)
                if snapshots is not None and 'coaching' in sections:
                    snapshots[team['team_id']] = {'team_pointer': pointer, 'coach_pointer': coach_pointer,
                        'team_signature': header[:160] + header[0x2FA:0x358], 'data': coach[1],
                        'name': team['name'], 'coach': coach[0]['name']}
        except (RosterError, OSError, ValueError, struct.error):
            continue
    # Invalidate just these derived sections if code/metadata changed mid-load.
    if verified_team_sections(process, profile) != enabled:
        if snapshots is not None:
            snapshots.clear()
        for team in teams:
            for key in ('rotation', 'coaching', 'staff'):
                team.pop(key, None)

