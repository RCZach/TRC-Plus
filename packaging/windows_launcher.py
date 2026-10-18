"""Entry point for the Windows executable."""

import sys
import traceback
import ctypes


if __name__ == '__main__':
    try:
        from trc_plus.paths import user_root
        log = user_root() / 'desktop.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w', encoding='utf-8', buffering=1) as output:
            sys.stdout = sys.stderr = output
            from trc_plus.app import main
            main()
    except Exception:
        details = traceback.format_exc()
        try:
            with log.open('a', encoding='utf-8') as output:
                output.write(details)
        except (OSError, NameError):
            pass
        ctypes.windll.user32.MessageBoxW(None,
            'TRC+ could not start.\n\n' + details.splitlines()[-1] +
            '\n\nDetails are in %LOCALAPPDATA%\\TRC+\\desktop.log.\n'
            'The desktop interface requires Microsoft Edge WebView2 Runtime and .NET Framework 4.6.2 or newer.',
            'TRC+ startup error', 0x10)
        sys.exit(1)
