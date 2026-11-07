import json
from email.message import Message
from io import BytesIO
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from unittest.mock import Mock, patch

import pytest

from trace_app.app import DEFAULT_PROFILE, create_server
from trace_app.fields import RecordProfile
from trace_app.mappings import ValueCatalog
from trace_app.roster import RosterError
from trace_app.website import EXPORT_URL, NoRedirects, fetch_export


def response(document, content_type='application/json'):
    result = BytesIO(json.dumps(document).encode())
    result.headers = Message()
    result.headers['Content-Type'] = content_type
    return result


def test_fetches_full_roster_and_handles_empty_roster():
    with patch('trace_app.website.build_opener') as factory:
        factory.return_value.open.return_value = response({'name': 'TRC full roster', 'players': [
            {'player_id': '42', 'name': 'Custom Player', 'attributes': {'Speed': 80}},
        ], 'teams': []})
        roster = fetch_export(['Custom Player'])
        assert roster['players'][0]['attributes']['Speed'] == 80
        assert roster['players'][0]['player_id'] == '42'
        request = factory.return_value.open.call_args.args[0]
        assert request.full_url == EXPORT_URL
        assert request.get_method() == 'POST'
        assert json.loads(request.data) == {'names': ['Custom Player']}
        assert request.get_header('Authorization') is None
        factory.return_value.open.return_value = response({'players': [], 'teams': []})
        assert fetch_export(['Nobody Here'])['players'] == []


def test_empty_loaded_roster_does_not_fetch():
    with patch('trace_app.website.build_opener') as factory:
        assert fetch_export([])['players'] == []
        factory.assert_not_called()


def test_rejects_unrequested_players():
    with patch('trace_app.website.build_opener') as factory:
        factory.return_value.open.return_value = response({'players': [
            {'player_id': '42', 'name': 'Different Player'},
        ], 'teams': []})
        with pytest.raises(RosterError, match='outside the loaded roster'):
            fetch_export(['Custom Player'])


def test_large_loaded_roster_is_fetched_in_one_filtered_request():
    names = [f'Player {number}' for number in range(90)]
    with patch('trace_app.website.build_opener') as factory:
        factory.return_value.open.return_value = response({'players': [
            {'player_id': '89', 'name': 'Player 89'},
        ], 'teams': []})
        roster = fetch_export(names)
        request = factory.return_value.open.call_args.args[0]
        factory.return_value.open.assert_called_once()
    assert json.loads(request.data)['names'] == names
    assert [player['name'] for player in roster['players']] == ['Player 89']


@pytest.mark.parametrize('document,content_type', [('<html>Login</html>', 'text/html'),
                                                 ([], 'application/json'),
                                                 ({'Player': {'Attributes': {'Speed': 999}}}, 'application/json')])
def test_invalid_website_response_is_rejected(document, content_type):
    with patch('trace_app.website.build_opener') as factory:
        factory.return_value.open.return_value = response(document, content_type)
        with pytest.raises(RosterError):
            fetch_export(['Custom Player'])


def test_network_failures_size_limit_and_redirects_are_reported():
    with patch('trace_app.website.build_opener') as factory:
        factory.return_value.open.side_effect = URLError('offline')
        with pytest.raises(RosterError, match='Could not reach'):
            fetch_export(['Custom Player'])
        factory.return_value.open.side_effect = HTTPError(EXPORT_URL, 403, 'Denied', {}, None)
        with pytest.raises(RosterError, match='HTTP 403'):
            fetch_export(['Custom Player'])
        factory.return_value.open.side_effect = None
        factory.return_value.open.return_value = response({'Player': {}})
        with patch('trace_app.website.MAX_EXPORT_BYTES', 5):
            with pytest.raises(RosterError, match='128 MB'):
                fetch_export(['Custom Player'])
    with pytest.raises(RosterError, match='redirected'):
        NoRedirects().redirect_request(None, None, 302, '', {}, 'http://elsewhere/')


def test_website_api_requires_session_and_does_not_save_or_write(tmp_path):
    data = tmp_path / 'roster.json'
    game = Mock()
    game.profile.canonical_document = lambda roster: roster
    server = create_server(0, data, game=game)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/session') as stream:
            session = json.load(stream)
        with patch('trace_app.app.fetch_export', return_value={'players': [], 'teams': []}) as fetch:
            for token, expected_status in [('wrong', 403), (session['token'], 200)]:
                request = Request(base + '/api/trc/export', data=b'{"names":["Custom Player"]}', headers={'X-Editor-Token': token})
                if expected_status == 403:
                    with pytest.raises(HTTPError) as denied:
                        urlopen(request)
                    assert denied.value.code == 403
                    fetch.assert_not_called()
                else:
                    with urlopen(request) as stream:
                        assert json.load(stream)['roster']['players'] == []
            fetch.assert_called_once_with(['Custom Player'])
        assert not data.exists()
        assert not game.mock_calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_trc_shoe_alias_overwrites_game_value_before_canonicalization(tmp_path):
    game = Mock()
    game.profile = RecordProfile(json.loads(DEFAULT_PROFILE.read_text(encoding='utf-8')))
    server = create_server(0, tmp_path / 'roster.json', game=game)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/session') as stream:
            token = json.load(stream)['token']
        document = {
            'merge': True,
            'document': {'players': [{'player_id': 'trc-1', 'name': 'Adrian Higgins',
                                      'gear': {'Shoe Away': 'Kobe XI All Star'}}], 'teams': []},
            'target': {'players': [{'player_id': 'game-1', 'name': 'Adrian Higgins',
                                   'gear': {'Shoe Away Style': 123, 'Shoe Home Style': 456}}], 'teams': []},
        }
        request = Request(base + '/api/import', data=json.dumps(document).encode(),
                          headers={'Content-Type': 'application/json', 'X-Editor-Token': token})
        with urlopen(request) as stream:
            result = json.load(stream)
        assert result['warnings'] == []
        assert result['roster']['players'][0]['gear'] == {
            'Shoe Away Style': 'Kobe XI All Star', 'Shoe Home Style': 456}
        assert result['sync_roster']['players'][0]['gear'] == {
            'Shoe Away Style': 'Kobe XI All Star'}
        catalog = ValueCatalog(DEFAULT_PROFILE.parent / 'field_values.json')
        _, changes, skipped = game.profile.patch(
            bytes(game.profile.stride), result['sync_roster']['players'][0],
            lambda category, name, value: catalog.resolve('6AD2E48C:36532000', category, name, value),
            '6AD2E48C:36532000',
        )
        assert changes == []
        assert any('Shoe Away Style' in warning and 'no verified game ID' in warning for warning in skipped)
        assert not game.mock_calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
