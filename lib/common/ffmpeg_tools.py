import shutil
import subprocess
from pathlib import Path
from typing import List

from .os_utils import _no_console_kwargs


def _app_base_dir() -> Path:
    # Works for both PyInstaller bundles and source-tree runs
    try:
        import sys

        if getattr(sys, "frozen", False):
            return Path(getattr(sys, "_MEIPASS", Path.cwd()))
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd()


def _bin_candidate(exe_name: str) -> Path:
    # exe_name should include extension on Windows (e.g., "ffmpeg.exe")
    return _app_base_dir() / "bin" / exe_name


def resolve_tool(preferred_name_with_ext: str, path_name_no_ext: str) -> str:
    """
    Search for a tool in app-local bin/ first, then PATH.
    """
    local_path = _bin_candidate(preferred_name_with_ext)
    if local_path.exists():
        return str(local_path)

    found = shutil.which(path_name_no_ext)
    if found:
        return found

    # Last resort: return the bin path we expected
    return str(local_path)


def resolve_ffmpeg_path() -> str:
    # Windows build ships ffmpeg.exe; PATH fallback is "ffmpeg"
    return resolve_tool("ffmpeg.exe", "ffmpeg")


def resolve_ffprobe_path() -> str:
    return resolve_tool("ffprobe.exe", "ffprobe")


class Probe:
    def __init__(self, ffmpeg_cmd: str):
        # Try to locate ffprobe next to ffmpeg, otherwise fall back to PATH
        self.ffprobe = self._guess_ffprobe(ffmpeg_cmd)

    @staticmethod
    def _guess_ffprobe(ffmpeg_cmd: str) -> str:
        try:
            p = Path(ffmpeg_cmd)
            name = p.name.lower()
            if name.startswith("ffmpeg"):
                candidate = p.with_name(name.replace("ffmpeg", "ffprobe"))
                if candidate.exists():
                    return str(candidate)
        except Exception:
            pass
        return "ffprobe"

    def duration(self, src: Path) -> float | None:
        try:
            cmd: List[str] = [
                self.ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(src),
            ]
            out = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            val = out.stdout.strip()
            return float(val) if val else None
        except Exception:
            return None


class FFmpegProcess:
    def __init__(self, ffmpeg_cmd: str, log_q):
        self.ffmpeg = ffmpeg_cmd
        self.log_q = log_q

    def run(self, args: list[str]) -> int:
        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                **_no_console_kwargs(),
            )
            for line in proc.stderr:
                self.log_q.put(line.strip())
            return proc.wait()
        except Exception as e:
            try:
                self.log_q.put(f"[ERROR] {e}")
            except Exception:
                pass
            return 1

    @staticmethod
    def guess_ffplay(ffmpeg_cmd: str) -> str:
        try:
            p = Path(ffmpeg_cmd)
            name = p.name
            if name.lower().startswith("ffmpeg"):
                candidate = p.with_name(name.replace("ffmpeg", "ffplay"))
                if candidate.exists():
                    return str(candidate)
        except Exception:
            pass
        return "ffplay"
