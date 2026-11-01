"""Entry point for the Windows executable."""

import sys
import traceback
import ctypes
import os
from pathlib import Path


def clear_download_marks():
    """Allow bundled .NET assemblies after Explorer extracts a downloaded ZIP."""
    if not getattr(sys, 'frozen', False):
        return
    internal = Path(sys.executable).resolve().parent / '_internal'
    for package in ('pythonnet', 'clr_loader', 'webview'):
        folder = internal / package
        if not folder.is_dir():
            continue
        for assembly in folder.rglob('*.dll'):
            try:
                os.remove(f'{assembly}:Zone.Identifier')
            except FileNotFoundError:
                pass
            except OSError as error:
                raise RuntimeError(
                    'Windows blocked TRACE\'s bundled .NET files. Right-click the downloaded ZIP, '
                    'open Properties, select Unblock, then extract it again.'
                ) from error


if __name__ == '__main__':
    try:
        from trace_app.paths import user_root
        log = user_root() / 'desktop.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w', encoding='utf-8', buffering=1) as output:
            sys.stdout = sys.stderr = output
            clear_download_marks()
            from trace_app.app import main
            main()
    except Exception:
        details = traceback.format_exc()
        try:
            with log.open('a', encoding='utf-8') as output:
                output.write(details)
        except (OSError, NameError):
            pass
        ctypes.windll.user32.MessageBoxW(None,
            'TRACE could not start.\n\n' + details.splitlines()[-1] +
            '\n\nDetails are in %LOCALAPPDATA%\\TRACE\\desktop.log.\n'
            'The desktop interface requires Microsoft Edge WebView2 Runtime and .NET Framework 4.6.2 or newer.',
            'TRACE startup error', 0x10)
        sys.exit(1)
