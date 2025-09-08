import os
import sys
import subprocess
from pathlib import Path
from typing import Dict


def _no_console_kwargs() -> Dict:
    try:
        if sys.platform.startswith("win"):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return {"startupinfo": si, "creationflags": subprocess.CREATE_NO_WINDOW}
    except Exception:
        pass
    return {}


def open_folder(path: Path) -> None:
    if not path or not path.exists() or not path.is_dir():
        return
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], **_no_console_kwargs())
        else:
            subprocess.Popen(["xdg-open", str(path)], **_no_console_kwargs())
    except Exception:
        pass
