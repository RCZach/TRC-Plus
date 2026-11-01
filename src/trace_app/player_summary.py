"""Build-specific, read-only player list information observed in game memory."""

import math
import struct
from collections import defaultdict

from .roster import RosterError


SUMMARY_BUILD = '6ad2e48c:36532000'
# Confirmed against the user's displayed primary and secondary positions.
POSITIONS = {0: 'PG', 1: 'SG', 2: 'SF', 3: 'PF', 4: 'C', 5: None}


def player_summary(profile, record, build):
    metadata = {'team_status': 'unknown'}
    if build.casefold() != SUMMARY_BUILD:
        return metadata

    def observed(category, name, layout):
        field = profile.fields.get((category, name))
        if field and (field.offset, field.bits, field.shift, field.kind) == layout:
            return field.decode(record)
        return None

    primary = observed('vitals', 'Position', (0x12D, 3, 0, 'bits'))
    secondary = observed('vitals', 'Secondary Position', (0x12D, 3, 3, 'bits'))
    metadata['primary_position'] = POSITIONS.get(primary)
    metadata['secondary_position'] = POSITIONS.get(secondary)
    if metadata['primary_position']:
        labels = [metadata['primary_position']]
        if metadata['secondary_position'] and metadata['secondary_position'] != labels[0]:
            labels.append(metadata['secondary_position'])
        metadata['position'] = ' / '.join(labels)
    valid = observed('advanced', 'ARECACHEDRATINGSVALID', (0x370, 1, 6, 'bits'))
    overall = observed('advanced', 'CACHEDOVERALLRATINGNEVERCALL', (0x1AC, 32, 0, 'float'))
    if valid == 1 and overall is not None and math.isfinite(overall):
        rounded = math.floor(overall + 0.5)
        if 25 <= rounded <= 99:
            metadata.update(overall=rounded, overall_source='game')
    return metadata


def read_teams(process, profile, base, players, records):
    """Read observed team names only when the membership list validates.

    Player +0x60 points to the team's list of up to 20 player pointers. The
    same observed object contains UTF-16 nickname/city/abbreviation fields.
    No team address, enum ID, or NBA name is inferred from player identity.
    """
    if process.build.casefold() != SUMMARY_BUILD or profile.stride != 0x4F8:
        return []
    groups = defaultdict(list)
    addresses = {}
    for player in players:
        identity = player['player_id']
        address = base + player['metadata']['game_index'] * profile.stride
        addresses[address] = player
        pointer = struct.unpack_from('<Q', records[identity], 0x60)[0]
        groups[pointer].append((address, player))
    teams = []
    for pointer, group in groups.items():
        if not 0x10000 <= pointer <= 0x7FFFFFFFFFFF:
            continue  # A null/unknown link does not establish free agency.
        try:
            raw = process.read(pointer, 0x358)
            members = [value for value in struct.unpack_from('<20Q', raw) if value]
            if (not members or len(set(members)) != len(members) or
                    set(members) != {address for address, _ in group} or
                    any(member not in addresses for member in members)):
                continue

            def text(start, end, optional=False):
                value = raw[start:end].decode('utf-16-le')
                if '\0' not in value:
                    raise ValueError('Unterminated team name')
                value = value.split('\0', 1)[0].strip()
                if optional and not value:
                    return ''
                if not value or not all(char.isprintable() for char in value) or not any(char.isalpha() for char in value):
                    raise ValueError('Invalid team name')
                return value

            nickname = text(0x2FA, 0x32C)
            city = text(0x32C, 0x350, optional=True)
            abbreviation = text(0x350, 0x358)
        except (RosterError, OSError, UnicodeError, ValueError, struct.error):
            continue
        team_id = f'game-team-{len(teams)}'
        teams.append({'team_id': team_id, 'name': f'{city} {nickname}'.strip(),
                      'metadata': {'city': city, 'abbreviation': abbreviation, 'source': 'game'}})
        for _, player in group:
            player['team_id'] = team_id
            player['metadata']['team_status'] = 'assigned'
    return teams
