import ctypes
from pathlib import Path
import sys
import traceback

from trace_app.update_installer import main


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except Exception:
        details = traceback.format_exc()
        try:
            Path(sys.argv[1]).parent.joinpath('error.log').write_text(details, encoding='utf-8')
        except Exception:
            pass
        ctypes.windll.user32.MessageBoxW(None, 'Trace could not finish the update.\n\n' + details.splitlines()[-1] +
                                       '\n\nYour saved workspace and settings are kept in your app data folder.',
                                       'Trace update', 0x10)
        sys.exit(1)
