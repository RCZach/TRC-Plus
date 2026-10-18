"""Read the existing TRC export; never acknowledge or complete upgrades."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .roster import RosterError, validate_roster
from .trc import import_document

EXPORT_URL = 'https://russellcup.xyz/logs/upgrades/download/'
MAX_EXPORT_BYTES = 128_000_000


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RosterError('TRC redirected the export request. Download and import the export manually.')


def fetch_export():
    request = Request(EXPORT_URL, headers={'Accept': 'application/json', 'User-Agent': 'TRC+/0.1'})
    try:
        with build_opener(NoRedirects()).open(request, timeout=20) as response:
            if response.headers.get_content_type() != 'application/json':
                raise RosterError('TRC did not return a JSON export. Download and import the export manually.')
            payload = response.read(MAX_EXPORT_BYTES + 1)
        if len(payload) > MAX_EXPORT_BYTES:
            raise RosterError('The TRC export must be smaller than 128 MB.')
        document = json.loads(payload.decode('utf-8-sig'))
        if document == {}:
            return validate_roster({'name': 'TRC pending upgrades', 'players': [], 'teams': []})
        return import_document(document)
    except RosterError:
        raise
    except HTTPError as error:
        raise RosterError(f'TRC export request failed (HTTP {error.code}). Try again or import a downloaded export.') from error
    except (URLError, OSError) as error:
        raise RosterError('Could not reach TRC. Check your connection and try again, or import a downloaded export.') from error
    except (ValueError, UnicodeError) as error:
        raise RosterError('TRC returned an invalid export. Try again or import a downloaded export.') from error
