import os
from pathlib import Path


def fmt_bytes(n: int | None) -> str:
    if n is None or n < 0:
        return "N/A"
    mb = n / (1024 * 1024)
    return f"{mb:.2f} MB"


def fmt_hms(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "N/A"
    total = int(round(seconds))
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"


class PathTools:
    @staticmethod
    def normalize(p: Path) -> str:
        try:
            abs_path = os.path.abspath(str(p))
        except Exception:
            abs_path = str(p)
        return os.path.normcase(abs_path)
