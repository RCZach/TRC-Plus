"""Persistent game connection settings, independent of roster documents."""

import json
import re

from .roster import RosterError

DEFAULT_GAME_PATH = r'D:\Program Files (x86)\Steam\steamapps\common\NBA 2K27'


def validate_settings(document):
    if not isinstance(document, dict):
        raise RosterError('Game connection settings must be an object.')
    path = document.get('game_path', DEFAULT_GAME_PATH)
    build = document.get('verified_build', '')
    writes = document.get('enable_writes', False)
    if not isinstance(path, str) or not path.strip():
        raise RosterError('Enter the game folder or executable path.')
    if not isinstance(build, str) or (build.strip() and not re.fullmatch(r'[0-9a-fA-F]+:[0-9a-fA-F]+', build.strip())):
        raise RosterError('Verified build must use the displayed hexadecimal TIMESTAMP:SIZE format.')
    if type(writes) is not bool:
        raise RosterError('Enable writes must be true or false.')
    if writes and not build.strip():
        raise RosterError('Enter the verified build fingerprint before enabling writes.')
    return {'game_path': path.strip(), 'verified_build': build.strip().upper(), 'enable_writes': writes}


def load_settings(path):
    return validate_settings(json.loads(path.read_text(encoding='utf-8')) if path.exists() else {})


def save_settings(path, document):
    settings = validate_settings(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(settings, indent=2), encoding='utf-8')
    temporary.replace(path)
    return settings
