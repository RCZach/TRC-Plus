"""Import the name-keyed TRC export without losing unmapped source fields."""

import copy
import hashlib
import unicodedata

from .roster import RosterError, validate_roster

CATEGORIES = {'Attributes': 'attributes', 'Tendencies': 'tendencies',
              'Badges': 'badges', 'Vitals': 'vitals', 'Signatures': 'signatures',
              'Advanced Fields': 'advanced', 'Gear': 'gear', 'Accessories': 'accessories',
              'Hotzones': 'hotzones', 'Appearance': 'appearance'}


def normalized_name(name: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', name).casefold().split())


def import_document(document: object) -> dict:
    if isinstance(document, dict) and ('players' in document or 'teams' in document):
        return validate_roster(document)
    if not isinstance(document, dict) or not document:
        raise RosterError('Expected a roster document or a TRC export keyed by player name.')
    players = []
    for name, values in document.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(values, dict):
            raise RosterError('TRC export entries must contain a player name and an object.')
        if not any(key in values for key in CATEGORIES):
            raise RosterError(f'{name}: no recognized TRC categories.')
        identity = hashlib.sha256(normalized_name(name).encode()).hexdigest()[:20]
        player = {'player_id': f'trc-{identity}', 'name': name,
                  'metadata': {'source': 'TRC', 'trc_extra': {
                      key: copy.deepcopy(value) for key, value in values.items() if key not in CATEGORIES}}}
        for source, target in CATEGORIES.items():
            if source in values:
                player[target] = copy.deepcopy(values[source])
        players.append(player)
    return validate_roster({'name': 'TRC export', 'players': players, 'teams': []})


def merge_trc(source: dict, target: dict) -> tuple[dict, list[str]]:
    """Keep target IDs/team assignments; refuse ambiguous name matching."""
    source, result = import_document(source), validate_roster(target)
    source_names, target_names = {}, {}
    for record in source['players']:
        source_names.setdefault(normalized_name(record['name']), []).append(record)
    for record in result['players']:
        target_names.setdefault(normalized_name(record['name']), []).append(record)
    warnings = []
    for name, records in source_names.items():
        matches = target_names.get(name, [])
        if len(records) != 1 or len(matches) != 1:
            warnings.append(f"{records[0]['name']}: {'ambiguous name' if len(records) > 1 or len(matches) > 1 else 'not found in workspace'}; skipped.")
            continue
        source_player, player = records[0], matches[0]
        for category in CATEGORIES.values():
            player[category].update(copy.deepcopy(source_player[category]))
        player['metadata'].update(copy.deepcopy(source_player['metadata']))
    return validate_roster(result), warnings
