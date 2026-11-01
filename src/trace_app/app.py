"""Local-only roster editor. Run with python -m trace_app.app."""

import argparse
import json
import secrets
import socket
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .roster import RosterError, demo_roster, save_roster, validate_roster
from .game import GameConnection
from .settings import load_settings, save_settings, validate_settings
from .trc import import_document, merge_trc
from .mappings import expand_profile
from .website import fetch_export
from .paths import resource_root, user_root
from .updates import UpdateManager
from .version import VERSION

UI = Path(__file__).parent / 'ui'
DEFAULT_PROFILE = resource_root() / 'config' / 'offsets_2k27.json'
DEFAULT_SETTINGS = user_root() / 'config' / 'game_connection.json'
API_VERSION = 6
MAX_DOCUMENT_BYTES = 128_000_000


class EditorServer(HTTPServer):
    # HTTPServer's SO_REUSEADDR permits two Windows processes to share a port.
    # An old backend could then serve freshly changed frontend files.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(port: int, data_path: Path, profile_path: Path = DEFAULT_PROFILE,
                  *, game=None, settings_path=DEFAULT_SETTINGS, game_path=None,
                  game_build=None, enable_game_writes=None) -> HTTPServer:
    token = secrets.token_urlsafe(32)
    updates = UpdateManager()
    profile = expand_profile(json.loads(profile_path.read_text(encoding='utf-8'))) if profile_path.exists() else {}
    roster = validate_roster(json.loads(data_path.read_text(encoding='utf-8'))) if data_path.exists() else demo_roster()
    connection_settings = load_settings(settings_path)
    # Ignore legacy saved write authorization; the UI now enables writes only
    # through the explicit, session-scoped Start live editing action.
    connection_settings['verified_build'] = ''
    connection_settings['enable_writes'] = False
    for key, value in [('game_path', game_path), ('verified_build', game_build), ('enable_writes', enable_game_writes)]:
        if value is not None:
            connection_settings[key] = value
    connection_settings = validate_settings(connection_settings)
    game = game or (GameConnection(profile, expected_build=connection_settings['verified_build'],
                                   enable_writes=connection_settings['enable_writes'],
                                   game_path=connection_settings['game_path'],
                                   audit_path=data_path.parent / 'game_updates.jsonl') if profile else None)
    if game is not None:
        roster = game.profile.canonical_document(roster)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, body, content_type='application/json'):
            payload = json.dumps(body, ensure_ascii=False).encode() if content_type == 'application/json' else body
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {'error': 'Invalid host.'})
            path = urlparse(self.path).path
            if path == '/api/session':
                return self.reply(200, {'token': token, 'roster': roster, 'profile': profile,
                                        'mode': 'offline', 'api_version': API_VERSION, 'game_settings': connection_settings,
                                        'app_version': VERSION, 'desktop_updates': callable(getattr(self.server, 'finish_update', None))})
            if path == '/api/game/status':
                try:
                    if game is None:
                        raise RosterError('No player offset profile loaded.')
                    return self.reply(200, game.status())
                except RosterError as error:
                    return self.reply(200, {'connected': False, 'writes_enabled': False, 'error': str(error)})
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path not in files:
                return self.reply(404, {'error': 'Not found.'})
            file, mime = files[path]
            self.reply(200, (UI / file).read_bytes(), mime)

        def do_POST(self):
            nonlocal roster, connection_settings
            if not self.valid_host() or self.headers.get('X-Editor-Token') != token:
                return self.reply(403, {'error': 'Invalid editor session. Reload the page.'})
            if self.path not in ('/api/updates/check', '/api/updates/download', '/api/updates/install', '/api/trc/export', '/api/roster', '/api/import', '/api/game/settings', '/api/game/load', '/api/game/diagnostics', '/api/game/preview', '/api/game/apply', '/api/game/live', '/api/game/edit', '/api/game/undo', '/api/game/redo', '/api/game/learn-value', '/api/game/capture', '/api/game/compare'):
                return self.reply(404, {'error': 'Not found.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_DOCUMENT_BYTES:
                    raise RosterError('Roster must be smaller than 128 MB.')
                document = json.loads(self.rfile.read(length))
                if self.path == '/api/roster':
                    roster = save_roster(data_path, document)
                    return self.reply(200, {'roster': roster})
                if not isinstance(document, dict):
                    raise RosterError('Request must be a JSON object.')
                if self.path == '/api/updates/check':
                    return self.reply(200, updates.check())
                if self.path in ('/api/updates/download', '/api/updates/install'):
                    if not callable(getattr(self.server, 'finish_update', None)):
                        raise RosterError('Install updates using the packaged desktop app.')
                    self.server.check_update_ready()
                    if self.path.endswith('/download'):
                        return self.reply(200, updates.download())
                    updates.launch_installer()
                    self.reply(200, {'restarting': True})
                    self.server.finish_update()
                    return
                if self.path == '/api/trc/export':
                    return self.reply(200, {'roster': fetch_export()})
                if self.path == '/api/import':
                    if document.get('merge'):
                        imported, warnings = merge_trc(document.get('document'), document.get('target'))
                    else:
                        imported, warnings = import_document(document.get('document')), []
                    if game is not None:
                        imported = game.profile.canonical_document(imported)
                    return self.reply(200, {'roster': imported, 'warnings': warnings})
                if game is None:
                    raise RosterError('No player offset profile loaded.')
                if self.path == '/api/game/settings':
                    connection_settings = save_settings(settings_path, document)
                    game.configure(connection_settings)
                    return self.reply(200, {'game_settings': connection_settings})
                if self.path == '/api/game/load':
                    return self.reply(200, game.load())
                if self.path == '/api/game/diagnostics':
                    return self.reply(200, game.diagnostics())
                if self.path == '/api/game/live':
                    return self.reply(200, game.set_live(document.get('enabled')))
                if self.path == '/api/game/edit':
                    return self.reply(200, game.edit(document))
                if self.path == '/api/game/learn-value':
                    return self.reply(200, game.learn_value(document))
                if self.path == '/api/game/capture':
                    return self.reply(200, game.capture_change(document))
                if self.path == '/api/game/compare':
                    return self.reply(200, game.compare_change(document))
                if self.path in ('/api/game/undo', '/api/game/redo'):
                    return self.reply(200, game.undo(redo=self.path.endswith('/redo')))
                if self.path == '/api/game/preview':
                    return self.reply(200, game.preview(document))
                if not isinstance(document.get('plan_id'), str):
                    raise RosterError('A reviewed plan_id is required.')
                return self.reply(200, game.apply(document['plan_id']))
            except (ValueError, UnicodeError) as error:
                self.reply(400, {'error': str(error)})
            except OSError:
                self.reply(500, {'error': 'Could not save the local file. Check file permissions.'})

    return EditorServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='TRACE — local roster editor')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data', type=Path, default=user_root() / 'data' / 'roster.json')
    parser.add_argument('--profile', type=Path, default=DEFAULT_PROFILE)
    parser.add_argument('--no-browser', action='store_true')
    interface = parser.add_mutually_exclusive_group()
    interface.add_argument('--desktop', action='store_true', help='Open a dedicated app window')
    interface.add_argument('--browser', action='store_true', help='Open in the default browser instead')
    parser.add_argument('--settings', type=Path, default=DEFAULT_SETTINGS, help='Game connection settings JSON')
    parser.add_argument('--game-path', help='NBA 2K27 installation folder or executable path')
    parser.add_argument('--game-build', help='Verified executable PE timestamp:SizeOfImage, in hexadecimal')
    parser.add_argument('--enable-game-writes', action='store_true', default=None, help='Allow reviewed writes for the matching game build')
    args = parser.parse_args()
    try:
        server = create_server(args.port, args.data, args.profile, settings_path=args.settings, game_path=args.game_path,
                               game_build=args.game_build, enable_game_writes=args.enable_game_writes)
    except OSError as error:
        if error.errno not in (48, 98, 10048) and getattr(error, 'winerror', None) not in (10013, 10048):
            raise
        print(f'Port {args.port} is already in use. Opening this editor on a separate port.', flush=True)
        server = create_server(0, args.data, args.profile, settings_path=args.settings, game_path=args.game_path,
                               game_build=args.game_build, enable_game_writes=args.enable_game_writes)
    url = f'http://127.0.0.1:{server.server_port}'
    if not args.no_browser and (args.desktop or (getattr(sys, 'frozen', False) and not args.browser)):
        from .desktop import run_desktop
        return run_desktop(server, url)
    print(f'TRACE: {url}\nKeep this window open while using the editor. Press Ctrl+C or close this window to stop.\n'
          f'Workspace: {args.data.resolve()}\nSettings: {args.settings.resolve()}', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
