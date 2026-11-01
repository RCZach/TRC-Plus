"""Validated, portable roster documents; independent of process memory access."""

import copy
import json
from pathlib import Path


class RosterError(ValueError):
    pass


def validate_roster(document: object) -> dict:
    if not isinstance(document, dict):
        raise RosterError('Expected a JSON object with players and teams arrays.')
    result = copy.deepcopy(document)
    result['version'] = 1
    for kind, id_key in [('players', 'player_id'), ('teams', 'team_id')]:
        records = result.setdefault(kind, [])
        if not isinstance(records, list):
            raise RosterError(f'{kind} must be an array.')
        seen = set()
        for record in records:
            if not isinstance(record, dict):
                raise RosterError(f'Each {kind} entry must be an object.')
            identity = record.get(id_key)
            if not isinstance(identity, str) or not identity.strip():
                raise RosterError(f'Each {kind} entry needs a non-empty {id_key} string.')
            if identity in seen:
                raise RosterError(f'Duplicate {id_key}: {identity}')
            seen.add(identity)
            if not isinstance(record.get('name'), str) or not record['name'].strip():
                raise RosterError(f'{identity}: name is required.')
            metadata = record.get('metadata')
            extra = metadata.get('trc_extra', {}) if isinstance(metadata, dict) else {}
            if isinstance(extra, dict):
                for source, target in [('Gear', 'gear'), ('Accessories', 'accessories'), ('Hotzones', 'hotzones')]:
                    if target not in record and isinstance(extra.get(source), dict):
                        record[target] = copy.deepcopy(extra[source])
            for key in ['attributes', 'tendencies', 'badges', 'vitals', 'signatures', 'advanced', 'metadata', 'gear', 'accessories', 'hotzones', 'appearance']:
                values = record.setdefault(key, {})
                if not isinstance(values, dict):
                    raise RosterError(f'{identity}: {key} must be an object.')
                for field, value in values.items():
                    if key in ('attributes', 'tendencies', 'badges'):
                        maximum = {'attributes': 99, 'tendencies': 100, 'badges': 5}[key]
                        if type(value) is not int or not 0 <= value <= maximum:
                            raise RosterError(f'{identity}: {field} must be an integer from 0 to {maximum}.')
            team_id = record.get('team_id')
            if team_id is not None and not isinstance(team_id, str):
                raise RosterError(f'{identity}: team_id must be a string or null.')
    teams = {t['team_id'] for t in result['teams']}
    for player in result['players']:
        if player.get('team_id') is not None and player['team_id'] not in teams:
            raise RosterError(f"{player['name']}: unknown team_id {player['team_id']}.")
    return result


def save_roster(path: Path, document: object) -> dict:
    roster = validate_roster(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(roster, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)
    return roster


def demo_roster() -> dict:
    """Fictional records so example values cannot be mistaken for game data."""
    teams = [
        {'team_id': 'demo-tor', 'name': 'Toronto North', 'metadata': {'abbreviation': 'TOR', 'city': 'Toronto', 'conference': 'East'}},
        {'team_id': 'demo-la', 'name': 'Los Angeles Gold', 'metadata': {'abbreviation': 'LAG', 'city': 'Los Angeles', 'conference': 'West'}},
        {'team_id': 'demo-ny', 'name': 'New York Empire', 'metadata': {'abbreviation': 'NYE', 'city': 'New York', 'conference': 'East'}},
    ]
    names = [('Marcus Bennett', 'PG', 'demo-tor'), ('Isaiah Brooks', 'SG', 'demo-tor'), ('Julian Carter', 'SF', 'demo-tor'), ('Andre Mitchell', 'PF', 'demo-la'), ('Elijah Hayes', 'C', 'demo-la'), ('Darius Cole', 'PG', 'demo-ny'), ('Noah Williams', 'SF', 'demo-ny'), ('Cameron Davis', 'C', None)]
    fields = ['Driving Layup', 'Close Shot', 'Midrange Shot', '3pt Shot', 'Free Throw', 'Ball Control', 'Pass Accuracy', 'Driving Dunk', 'Speed', 'Strength']
    players = []
    for i, (name, position, team) in enumerate(names):
        players.append({'player_id': f'demo-{i + 1:03}', 'name': name, 'team_id': team,
                        'metadata': {'position': position, 'number': str(i * 3 + 1)},
                        'attributes': {f: 65 + (i * 7 + j * 3) % 32 for j, f in enumerate(fields)},
                        'tendencies': {'Shoot': 75, 'Driving Layup Tendency': 65},
                        'badges': {'Float Game': 2, 'Posterizer': 1}})
    return validate_roster({'version': 1, 'name': 'Demo roster', 'players': players, 'teams': teams})
