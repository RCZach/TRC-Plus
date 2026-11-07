"""Import the name-keyed TRC export without losing unmapped source fields."""

import copy
import hashlib
import unicodedata

from .roster import RosterError, validate_roster

CATEGORIES = {'Attributes': 'attributes', 'Tendencies': 'tendencies',
              'Badges': 'badges', 'Vitals': 'vitals', 'Signatures': 'signatures',
              'Advanced Fields': 'advanced', 'Gear': 'gear', 'Accessories': 'accessories',
              'Hotzones': 'hotzones', 'Appearance': 'appearance'}

# TRC stores NBA 2K25 badges. These are the user's selected single targets in
# NBA 2K27; the other halves of the split badges remain untouched.
BADGES_2K25_TO_2K27 = {
    'Boxout Beast': 'Boxout Boss',
    'On-Ball Menace': 'Seatbelt',
    'Post-Up Poet': 'Post Spin Catalyst',
    'Rebound Chaser': 'Possession Closer',
    'Set Shot Specialist': 'Set and Fire',
    'Shifty Shooter': 'Arc Cadence',
}


def convert_2k25_badges(badges: dict, existing: dict | None = None) -> dict:
    """Translate old badge names without reducing existing 2K27 tiers."""
    converted = copy.deepcopy(badges)
    existing = existing or {}
    for old, new in BADGES_2K25_TO_2K27.items():
        if old not in converted:
            continue
        tier = converted.pop(old)
        if new in converted or tier == 0:
            continue  # An explicit 2K27 value wins; zero does not clear a badge.
        converted[new] = max(tier, existing.get(new, 0))
    return converted


def convert_2k25_roster_badges(document: dict) -> dict:
    """Convert an imported TRC document without a game roster to merge into."""
    result = validate_roster(document)
    for player in result['players']:
        player['badges'] = convert_2k25_badges(player['badges'])
    return result


def normalized_name(name: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', name).casefold().split())


def matching_name(name: str) -> str:
    """Compare complete names while tolerating optional periods after words."""
    return ' '.join(part.rstrip('.') for part in normalized_name(name).split())


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


def merge_trc_with_scope(source: dict, target: dict) -> tuple[dict, dict, list[str]]:
    """Merge supplied values and build a preview limited to those values."""
    source, result = import_document(source), validate_roster(target)
    scope = copy.deepcopy(result)
    for player in scope['players']:
        for category in CATEGORIES.values():
            player[category] = {}
    for team in scope['teams']:
        team.pop('coaching', None)
    source_names, target_names = {}, {}
    scope_players = {player['player_id']: player for player in scope['players']}
    for record in source['players']:
        source_names.setdefault(matching_name(record['name']), []).append(record)
    for record in result['players']:
        target_names.setdefault(matching_name(record['name']), []).append(record)
    warnings = []
    for name, records in source_names.items():
        matches = target_names.get(name, [])
        if len(records) != 1 or len(matches) != 1:
            warnings.append(f"{records[0]['name']}: {'ambiguous name' if len(records) > 1 or len(matches) > 1 else 'not found in workspace'}; skipped.")
            continue
        source_player, player = records[0], matches[0]
        for category in CATEGORIES.values():
            values = (convert_2k25_badges(source_player[category], player[category])
                      if category == 'badges' else copy.deepcopy(source_player[category]))
            if category == 'badges':
                for old in BADGES_2K25_TO_2K27:
                    player[category].pop(old, None)
            player[category].update(values)
            scope_players[player['player_id']][category] = copy.deepcopy(values)
        player['metadata'].update(copy.deepcopy(source_player['metadata']))
    return validate_roster(result), validate_roster(scope), warnings


def merge_trc(source: dict, target: dict) -> tuple[dict, list[str]]:
    """Keep target IDs/team assignments; refuse ambiguous name matching."""
    merged, _, warnings = merge_trc_with_scope(source, target)
    return merged, warnings
