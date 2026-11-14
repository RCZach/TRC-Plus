"""Exact-build animation enums bound to existing packed roster fields.

Names come from native symbols, not an older game's list positions. Formatting
and punctuation may differ; only unique normalized symbol matches are accepted.
"""

import json
import unicodedata
from functools import lru_cache

from .mappings import label_key as _label_key
from .paths import resource_root
from .roster import RosterError


def label_key(label):
    """Treat accented display names as their unaccented spellings."""
    return _label_key(unicodedata.normalize('NFKD', label))


@lru_cache(maxsize=1)
def _document():
    return json.loads((resource_root() / 'config' / 'signature_values_2k27.json').read_text(encoding='utf-8'))


def _table(build, field):
    document = _document()
    if (not build or build.upper() != document['build'] or
            field.category != 'signatures' or field.kind != 'bits'):
        return {}
    binding = document['fields'].get(field.name) or document.get('primitives', {}).get(field.name)
    if not binding or binding['layout'] != [field.offset, field.bits, field.shift]:
        return {}
    table = document['enums'][binding['enum']] if 'enum' in binding else binding
    values = table['values']
    # A malformed catalog cannot turn an unsupported ID into a valid choice.
    if any(type(value) is not int or not 0 <= value < 2 ** field.bits for value in values.values()):
        return {}
    return table


def _entries(build, field):
    return _table(build, field).get('values', {})


def _label_symbols(table):
    values = table.get('values', {})
    groups = {}
    for symbol in values:
        groups.setdefault(label_key(symbol), set()).add(symbol)
    for label, symbols in table.get('labels', {}).items():
        if not isinstance(symbols, list) or any(symbol not in values for symbol in symbols):
            continue
        groups.setdefault(label_key(label), set()).update(symbols)
    return groups


def choices(build, field):
    table = _table(build, field)
    values = table.get('values', {})
    groups = _label_symbols(table)
    labels = table.get('labels', {})
    named = {symbol for symbols in labels.values() if isinstance(symbols, list) for symbol in symbols}
    candidates = [*labels, *(symbol.replace('_', ' ').title() for symbol in values if symbol not in named)]
    return {label: values[next(iter(groups[label_key(label)]))] for label in candidates
            if len(groups.get(label_key(label), ())) == 1}


def resolve(build, field, label):
    table = _table(build, field)
    matches = _label_symbols(table).get(label_key(label), set())
    if len(matches) != 1:
        raise RosterError(f'{field.name}: "{label}" has no unique native animation ID for this build; skipped.')
    return table['values'][next(iter(matches))]
