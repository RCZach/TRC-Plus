"""Read TRC values for players in the loaded roster without modifying data."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .roster import RosterError, validate_roster
from .trc import import_document, normalized_name

EXPORT_URL = 'https://russellcup.xyz/logs/roster/download/'
MAX_EXPORT_BYTES = 128_000_000


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RosterError('TRC redirected the export request. Download and import the export manually.')


def fetch_export(names):
    if not isinstance(names, list) or len(names) > 6000 or any(
        not isinstance(name, str) or not name.strip() or len(name) > 80 for name in names
    ):
        raise RosterError('TRC sync needs a list of loaded player names.')
    unique = list({normalized_name(name): name.strip() for name in names}.values())
    if not unique:
        return validate_roster({'name': 'TRC matched players', 'players': [], 'teams': []})
    request = Request(EXPORT_URL, data=json.dumps({'names': unique}).encode('utf-8'),
                      headers={'Accept': 'application/json', 'Content-Type': 'application/json',
                               'User-Agent': 'TRACE/0.1'})
    try:
        with build_opener(NoRedirects()).open(request, timeout=30) as response:
            if response.headers.get_content_type() != 'application/json':
                raise RosterError('TRC did not return a JSON export. Download and import the export manually.')
            payload = response.read(MAX_EXPORT_BYTES + 1)
        if len(payload) > MAX_EXPORT_BYTES:
            raise RosterError('The TRC export must be smaller than 128 MB.')
        imported = import_document(json.loads(payload.decode('utf-8-sig')))
        requested = {normalized_name(name) for name in unique}
        if any(normalized_name(player['name']) not in requested for player in imported['players']):
            raise RosterError('TRC returned players outside the loaded roster request.')
        return imported
    except RosterError:
        raise
    except HTTPError as error:
        raise RosterError(f'TRC export request failed (HTTP {error.code}). Try again or import a downloaded export.') from error
    except (URLError, OSError) as error:
        raise RosterError('Could not reach TRC. Check your connection and try again, or import a downloaded export.') from error
    except (ValueError, UnicodeError) as error:
        raise RosterError('TRC returned an invalid export. Try again or import a downloaded export.') from error
