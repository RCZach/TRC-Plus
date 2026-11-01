import copy
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from trace_app.app import create_server
from trace_app.roster import RosterError, demo_roster, save_roster, validate_roster


def test_round_trip_preserves_custom_fields(tmp_path):
    roster = demo_roster()
    roster['players'][0]['advanced'] = {'CUSTOM_ID': 1234}
    path = tmp_path / 'roster.json'
    assert save_roster(path, roster) == json.loads(path.read_text(encoding='utf-8'))
    assert roster['players'][0]['advanced']['CUSTOM_ID'] == 1234


@pytest.mark.parametrize('value', [True, 100, -1, '85', 85.5])
def test_invalid_ratings_do_not_replace_saved_roster(tmp_path, value):
    path = tmp_path / 'roster.json'
    roster = demo_roster()
    save_roster(path, roster)
    before = path.read_bytes()
    roster['players'][0]['attributes']['Speed'] = value
    with pytest.raises(RosterError):
        save_roster(path, roster)
    assert path.read_bytes() == before


def test_duplicate_identity_and_unknown_team_are_rejected():
    roster = demo_roster()
    roster['players'].append(copy.deepcopy(roster['players'][0]))
    with pytest.raises(RosterError, match='Duplicate'):
        validate_roster(roster)
    roster = demo_roster()
    roster['players'][0]['team_id'] = 'missing'
    with pytest.raises(RosterError, match='unknown team_id'):
        validate_roster(roster)


def test_editor_api_save_reload_validation_and_session_guard(tmp_path):
    path = tmp_path / 'roster.json'
    server = create_server(0, path)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urlopen(base + '/api/session') as response:
            session = json.load(response)
        assert session['api_version'] == 6
        roster = session['roster']
        roster['players'][0]['attributes']['Speed'] = 95
        def post(document, token):
            return urlopen(Request(base + '/api/roster', data=json.dumps(document).encode(), headers={'X-Editor-Token': token, 'Content-Type': 'application/json'}))
        with pytest.raises(HTTPError) as denied:
            post(roster, 'wrong')
        assert denied.value.code == 403
        with post(roster, session['token']) as response:
            assert json.load(response)['roster']['players'][0]['attributes']['Speed'] == 95
        roster['players'][0]['attributes']['Speed'] = 999
        with pytest.raises(HTTPError) as invalid:
            post(roster, session['token'])
        assert invalid.value.code == 400
        with urlopen(base + '/api/session') as response:
            assert json.load(response)['roster']['players'][0]['attributes']['Speed'] == 95
        with urlopen(base + '/') as response:
            assert b'TRACE' in response.read()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    restarted = create_server(0, path)
    restarted.server_close()
    assert json.loads(path.read_text())['players'][0]['attributes']['Speed'] == 95


def test_editor_port_cannot_be_shared_with_another_instance(tmp_path):
    first = create_server(0, tmp_path / 'first.json')
    try:
        with pytest.raises(OSError):
            create_server(first.server_port, tmp_path / 'second.json')
    finally:
        first.server_close()
