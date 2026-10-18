import json
from email.message import Message
from io import BytesIO
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from unittest.mock import Mock, patch

import pytest

from trc_plus.app import create_server
from trc_plus.roster import RosterError
from trc_plus.website import EXPORT_URL, NoRedirects, fetch_export


def response(document, content_type='application/json'):
    result = BytesIO(json.dumps(document).encode())
    result.headers = Message()
    result.headers['Content-Type'] = content_type
    return result


def test_fetch_matches_manual_export_and_handles_no_pending_players():
    with patch('trc_plus.website.build_opener') as factory:
        factory.return_value.open.return_value = response({'Custom Player': {'Attributes': {'Speed': 80}}})
        roster = fetch_export()
        assert roster['players'][0]['attributes']['Speed'] == 80
        request = factory.return_value.open.call_args.args[0]
        assert request.full_url == EXPORT_URL
        assert request.get_method() == 'GET'
        factory.return_value.open.return_value = response({})
        assert fetch_export()['players'] == []


@pytest.mark.parametrize('document,content_type', [('<html>Login</html>', 'text/html'),
                                                 ([], 'application/json'),
                                                 ({'Player': {'Attributes': {'Speed': 999}}}, 'application/json')])
def test_invalid_website_response_is_rejected(document, content_type):
    with patch('trc_plus.website.build_opener') as factory:
        factory.return_value.open.return_value = response(document, content_type)
        with pytest.raises(RosterError):
            fetch_export()


def test_network_failures_size_limit_and_redirects_are_reported():
    with patch('trc_plus.website.build_opener') as factory:
        factory.return_value.open.side_effect = URLError('offline')
        with pytest.raises(RosterError, match='Could not reach'):
            fetch_export()
        factory.return_value.open.side_effect = HTTPError(EXPORT_URL, 403, 'Denied', {}, None)
        with pytest.raises(RosterError, match='HTTP 403'):
            fetch_export()
        factory.return_value.open.side_effect = None
        factory.return_value.open.return_value = response({'Player': {}})
        with patch('trc_plus.website.MAX_EXPORT_BYTES', 5):
            with pytest.raises(RosterError, match='128 MB'):
                fetch_export()
    with pytest.raises(RosterError, match='redirected'):
        NoRedirects().redirect_request(None, None, 302, '', {}, 'http://elsewhere/')


def test_website_api_requires_session_and_does_not_save_or_write(tmp_path):
    data = tmp_path / 'roster.json'
    game = Mock()
    server = create_server(0, data, game=game)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/session') as stream:
            session = json.load(stream)
        with patch('trc_plus.app.fetch_export', return_value={'players': [], 'teams': []}) as fetch:
            for token, expected_status in [('wrong', 403), (session['token'], 200)]:
                request = Request(base + '/api/trc/export', data=b'{}', headers={'X-Editor-Token': token})
                if expected_status == 403:
                    with pytest.raises(HTTPError) as denied:
                        urlopen(request)
                    assert denied.value.code == 403
                    fetch.assert_not_called()
                else:
                    with urlopen(request) as stream:
                        assert json.load(stream)['roster']['players'] == []
            fetch.assert_called_once()
        assert not data.exists()
        assert not game.mock_calls
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
