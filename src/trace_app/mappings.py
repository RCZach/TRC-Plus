"""Promote existing field definitions; keep named ID observations build-specific."""

import copy
import json
import re

from .roster import RosterError
from .player_body import body_schema


def label_key(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


VITAL_IDS = {'WEIGHT', 'NUMBER', 'BIRTHDAY', 'BIRTHMONTH', 'BIRTHYEAR', 'DOMINANTHAND',
             'DOMINANTDUNKHAND', 'PEAKAGE', 'PEAKENDAGE', 'FACETYPE', 'HAIRLENGTH', 'SKINTYPE'}

DISPLAY_NAMES = {
    'GOTOSHOT': 'Go-To Shot', 'DRIBBLEPULLUP': 'Dribble Pull-Up', 'SHOTSPIN': 'Spin Jumper',
    'SHOTSIDEHOP': 'Hop Jumper', 'SHOTSTEPTHRU': 'Step Through Shot', 'GOPOSTTOSHOT': 'Post Go-To Shot',
    'POSTONESTEPPULLUP': 'Post Hop Shot', 'ISOSIZEUPSIG': 'Signature Size-Up',
    'ISOBREAKDOWN': 'Breakdown Combos', 'ISOBREAKDOWNMOVE': 'Moving Breakdown Combos',
    'ISOESCAPEHES': 'Hesitation Escape', 'ISOBEHINDBACK': 'Moving Behind The Back',
    'ISOCROSSOVER': 'Moving Crossover', 'ISOHESITATION': 'Moving Hesitation',
    'ISOSPIN': 'Moving Spin', 'ISOSTEPBACK': 'Moving Stepback',
    'SIGPLAYERINTRO1': 'Pre-Game 1', 'SIGPLAYERINTRO2': 'Pre-Game 2', 'SIGJUMPBALLSTAND': 'Jumpball Ritual',
    'GUMCHEWER': 'Chew Gum',
}

# Display names confirmed in the supplied 2K27 Signature menu screenshots.
# These translate names only; the existing profile and native catalog retain
# their canonical field names, layouts, enum IDs and build restrictions.
SIGNATURE_ALIASES = {
    'Lower/Base': 'Jumpshot Base',
    'Upper Release 1': 'Release 1',
    'Upper Release 2': 'Release 2',
    'Animation Blending': 'Jumpshot Blending',
    'Go-To Dunk Package': 'Dunk Package 1',
    'Crossover Combos': 'Iso Cross Combo',
    'Crossover Escape': 'Iso Escape Cross',
    'Between the Legs Escape': 'Iso Escape Tween',
    'Behind the Back Escape': 'Iso Escape Behind Back',
    'Misdirection Hesitation': 'Iso Mis Direct Hes',
    'Misdirection Crossover': 'Iso Mis Direct Cross',
    'Misdirection Behind Back': 'Iso Mis Direct Behind Back',
    'Hesitation Cross Combo': 'Iso Combo Hesi Cross',
    'Double Cross Combo': 'Iso Combo Double Cross',
    'Moving Behind the Back Launch': 'Iso Behind Back Launch',
    'Moving Cross Spin': 'Iso Cross Spin',
    'In and Out': 'Iso Inandout',
    'Moving Lateral Hesitation': 'Iso Hesitation Lateral',
    'Moving Stepback Cross': 'Iso Step Back Cross',
    'Moving LateralStepback': 'Iso Step Back Lateral',
    'NBA Jumpball Ritual': 'Jumpball Ritual',
    # The export's regular (stationary) category is the displayed Breakdown
    # Combos control. Aggressive Breakdown Combos has no confirmed equivalent;
    # it is deliberately not assigned to Moving Breakdown Combos.
    'Regular Breakdown Combos': 'Breakdown Combos',
}


def expand_profile(document):
    profile = copy.deepcopy(document)
    profile['Body'] = body_schema()
    for section in ('Gear', 'Accessories', 'Appearance', 'Hotzones'):
        profile.setdefault(section, [])
    keys = {section: {label_key(f.get('name', f.get('label', ''))) for f in values}
            for section, values in profile.items() if isinstance(values, list)}
    ids = {}
    for field in profile.get('Advanced Fields', []):
        ids[field['id']] = ids.get(field['id'], 0) + 1
    for field in profile.get('Advanced Fields', []):
        if ids[field['id']] != 1:
            continue
        section = None
        if field['section'] == 'Signature' or field['id'] == 'GUMCHEWER':
            section = 'Signatures'
        elif field['section'] == 'Gear':
            section = 'Gear' if field['group'] == 'Shoes/Gear' else 'Accessories'
        elif field['section'] == 'Vitals' and field['id'] in VITAL_IDS:
            section = 'Vitals'
        elif field['section'] == 'Appearance':
            section = 'Appearance'
        display = DISPLAY_NAMES.get(field['id'], field['label'])
        if section and label_key(display) not in keys[section]:
            item = {**field, 'name': display, 'label': display, 'source_id': field['id'], 'writable': True}
            item.pop('id')  # Category records use labels; Advanced keeps its original IDs.
            profile[section].append(item)
            keys[section].add(label_key(display))
    # Use conservative 20-code-unit name buffers, without clearing trailing bytes.
    for name, offset in [('First Name', profile['Base']['Offset First Name']),
                         ('Last Name', profile['Base']['Offset Last Name'])]:
        if label_key(name) not in keys['Vitals']:
            profile['Vitals'].append({'name': name, 'offset': offset, 'bits': 320, 'shift': 0,
                                      'kind': 'utf16', 'writable': True})
    for section, values in profile.items():
        if isinstance(values, list):
            for field in values:
                field.setdefault('writable', section != 'Advanced Fields')
    return profile


class ValueCatalog:
    def __init__(self, path):
        self.path = path
        self.document = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version': 1, 'builds': {}}

    def values(self, build, category, field):
        return self.document['builds'].get(build.upper(), {}).get(category, {}).get(field, {})

    def resolve(self, build, category, field, label):
        for name, entry in self.values(build, category, field).items():
            if name.strip().casefold() == label.strip().casefold():
                return entry['value']
        raise RosterError(f'{field}: "{label}" has no verified game ID for this build. Use Learn name on the value shown in 2K.')

    def learn(self, build, category, field, label, value, player_id):
        if not isinstance(label, str) or not label.strip() or len(label) > 120:
            raise RosterError('Enter a name of 1–120 characters exactly as displayed in 2K.')
        label = label.strip()
        updated = copy.deepcopy(self.document)
        values = updated['builds'].setdefault(build.upper(), {}).setdefault(category, {}).setdefault(field, {})
        for name, entry in values.items():
            if name.casefold() == label.casefold() and entry['value'] != value:
                raise RosterError('That name was previously observed with a different game ID. No mapping was overwritten.')
        values[label] = {'value': value, 'observed_player_id': player_id}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.path)
        self.document = updated
        return {'label': label, 'value': value, 'build': build}
