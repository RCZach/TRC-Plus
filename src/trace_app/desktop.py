"""Host the existing editor in its own Windows WebView2 window."""

import logging
from threading import Event, Thread, Timer
import sys

from .paths import user_root


def protect_unsaved_changes(window):
    """Check on a worker so evaluating JavaScript cannot block the UI thread."""
    approved, checking = Event(), Event()

    def review_close():
        try:
            dirty = window.evaluate_js('Boolean(window.trcHasUnsavedChanges?.())')
            if dirty and not window.create_confirmation_dialog(
                'Unsaved workspace', 'Close Trace without saving your workspace changes?'
            ):
                return
            approved.set()
            window.destroy()
        except Exception:
            logging.exception('Could not check unsaved changes before closing')
            if window.create_confirmation_dialog('Close Trace', 'Could not check for unsaved changes. Close anyway?'):
                approved.set()
                window.destroy()
        finally:
            checking.clear()

    def closing():
        if approved.is_set() or not window.events.loaded.is_set():
            return True
        if not checking.is_set():
            checking.set()
            Thread(target=review_close, daemon=True).start()
        return False

    window.events.closing += closing

    def close_after_update():
        approved.set()
        window.destroy()

    return close_after_update


def run_desktop(server, url):
    worker = Thread(target=server.serve_forever, name='Trace local backend', daemon=True)
    try:
        import webview

        webview.settings['ALLOW_DOWNLOADS'] = True
        window = webview.create_window('Trace', url, width=1440, height=900,
                                       min_size=(1000, 680), background_color='#10151e')
        missing_runtime = Event()

        def initialized(renderer):
            if renderer != 'edgechromium':
                missing_runtime.set()
                return False
            return True

        window.events.initialized += initialized
        close_after_update = protect_unsaved_changes(window)
        if getattr(sys, 'frozen', False):
            def check_update_ready():
                if window.evaluate_js('Boolean(window.trcHasUnsavedChanges?.())'):
                    raise ValueError('Save your workspace and finish pending edits before updating.')

            server.check_update_ready = check_update_ready
            server.finish_update = lambda: Timer(0.5, close_after_update).start()
        worker.start()
        print(f'Trace: {url}', flush=True)
        webview.start(gui='edgechromium', storage_path=str(user_root() / 'webview'), private_mode=False)
        if missing_runtime.is_set():
            raise RuntimeError('Install Microsoft Edge WebView2 Runtime to use the Trace desktop interface.')
    finally:
        if worker.ident is not None:
            server.shutdown()
            worker.join(timeout=5)
        server.server_close()
