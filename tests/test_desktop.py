from threading import Event
from types import SimpleNamespace
import sys

import pytest

from trc_plus.app import create_server
from trc_plus.desktop import protect_unsaved_changes, run_desktop


class ClosingEvent:
    def __iadd__(self, callback):
        self.callback = callback
        return self


@pytest.mark.parametrize('dirty,confirmed,should_close', [(False, False, True), (True, False, False), (True, True, True)])
def test_native_close_respects_unsaved_changes(dirty, confirmed, should_close):
    finished = Event()
    events = SimpleNamespace(loaded=Event(), closing=ClosingEvent())
    events.loaded.set()
    prompts, closed = [], []

    def confirm(*args):
        prompts.append(args)
        if not confirmed:
            finished.set()
        return confirmed

    def destroy():
        closed.append(True)
        assert events.closing.callback() is True
        finished.set()

    window = SimpleNamespace(events=events, evaluate_js=lambda _: dirty,
                             create_confirmation_dialog=confirm, destroy=destroy)
    protect_unsaved_changes(window)
    assert events.closing.callback() is False
    assert finished.wait(3)
    assert bool(closed) is should_close
    assert bool(prompts) is dirty


@pytest.mark.parametrize('fail', [False, True, 'old-renderer'])
def test_desktop_releases_local_server_when_window_exits(tmp_path, monkeypatch, fail):
    server = create_server(0, tmp_path / 'roster.json', settings_path=tmp_path / 'settings.json')
    settings = {}
    window = SimpleNamespace(events=SimpleNamespace(loaded=Event(), closing=ClosingEvent(), initialized=ClosingEvent()))

    def start(**kwargs):
        assert kwargs['gui'] == 'edgechromium'
        if fail is True:
            raise RuntimeError('Runtime unavailable')
        assert window.events.initialized.callback('mshtml' if fail == 'old-renderer' else 'edgechromium') is (fail != 'old-renderer')

    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(
        settings=settings, create_window=lambda *args, **kwargs: window, start=start))
    if fail:
        with pytest.raises(RuntimeError, match='Runtime unavailable|WebView2 Runtime'):
            run_desktop(server, 'http://127.0.0.1:1234')
    else:
        run_desktop(server, 'http://127.0.0.1:1234')
    assert settings['ALLOW_DOWNLOADS'] is True
    assert server.socket.fileno() == -1
