import queue
import shutil
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from lib.music.music_tab import MusicTab
from lib.video.video_tab import VideoTab

APP_TITLE = "Pip-Boy 3000 Mk V - Media Conversion Tool"
APP_VERSION = "1.0.0"


def _app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Running from bundled EXE (PyInstaller)
        return Path(getattr(sys, "_MEIPASS", Path.cwd()))
    return Path(__file__).resolve().parent


def _bin_candidate(exe_name: str) -> Path:
    # exe_name should include extension on Windows (e.g., "ffmpeg.exe")
    return _app_base_dir() / "bin" / exe_name


def _no_console_kwargs() -> dict:
    try:
        if sys.platform.startswith("win"):
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return {"startupinfo": si, "creationflags": subprocess.CREATE_NO_WINDOW}
    except Exception:
        pass
    return {}


def resolve_tool(preferred_name_with_ext: str, path_name_no_ext: str) -> str:
    # Prefer local bin copy
    local_path = _bin_candidate(preferred_name_with_ext)
    if local_path.exists():
        return str(local_path)

    # Fall back to system PATH
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


FFMPEG_CMD = resolve_ffmpeg_path()
FFPROBE_CMD = resolve_ffprobe_path()


class PipMediaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} (v{APP_VERSION})")
        self.geometry("980x640")

        # Per-tab queues so logs don't "eat" each other
        self.music_log_q: queue.Queue[str] = queue.Queue()
        self.video_log_q: queue.Queue[str] = queue.Queue()

        self._build_layout()
        self._wire_tabs()

        # Send initial app notes to both logs
        for q in (self.music_log_q, self.video_log_q):
            q.put(f"ffmpeg path resolved to: {FFMPEG_CMD}")
            q.put(f"{APP_TITLE} ready!")

        self.after(0, self._validate_tools)

    def _build_layout(self):
        self.columnconfigure(0, weight=1)

        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=0, column=0, sticky="nsew")

        # Footer links
        link_frame = ttk.Frame(self)
        link_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 10))

        for i in range(4):
            link_frame.columnconfigure(i, weight=1)

        # Author link
        author_frame = ttk.Frame(link_frame)
        author_frame.grid(row=0, column=0, sticky="w")
        tk.Label(author_frame, text="Author: ").pack(side="left")
        self.link1 = tk.Label(
            author_frame, text="Cody Tolene", fg="blue", cursor="hand2"
        )
        self.link1.pack(side="left")
        self.link1.bind(
            "<Button-1>", lambda e: self._open_link("https://github.com/CodyTolene")
        )

        # TWC link
        tinytv_frame = ttk.Frame(link_frame)
        tinytv_frame.grid(row=0, column=1)
        tk.Label(tinytv_frame, text="Purchase Pip-Boy 3000 Mk V: ").pack(side="left")
        self.link2 = tk.Label(
            tinytv_frame, text="The Wand Company", fg="blue", cursor="hand2"
        )
        self.link2.pack(side="left")
        self.link2.bind(
            "<Button-1>", lambda e: self._open_link("https://www.thewandcompany.com/")
        )

        # FFmpeg link
        ffmpeg_frame = ttk.Frame(link_frame)
        ffmpeg_frame.grid(row=0, column=2)
        tk.Label(ffmpeg_frame, text="Powered by ").pack(side="left")
        self.link4 = tk.Label(ffmpeg_frame, text="FFmpeg", fg="blue", cursor="hand2")
        self.link4.pack(side="left")
        self.link4.bind("<Button-1>", lambda e: self._open_link("https://ffmpeg.org/"))
        tk.Label(ffmpeg_frame, text=" (LGPLv2.1)").pack(side="left")

        # Donation link
        donate_frame = ttk.Frame(link_frame)
        donate_frame.grid(row=0, column=3, sticky="e")
        tk.Label(donate_frame, text="Any ").pack(side="left")
        self.link3 = tk.Label(donate_frame, text="donation", fg="blue", cursor="hand2")
        self.link3.pack(side="left")
        self.link3.bind(
            "<Button-1>",
            lambda e: self._open_link("https://github.com/sponsors/CodyTolene"),
        )
        tk.Label(donate_frame, text=" appreciated!").pack(side="left")

    def _wire_tabs(self):
        # Each tab builds its own UI, including progress, buttons, and log
        self.music_tab = MusicTab(
            self.nb,
            log_q=self.music_log_q,
            ffmpeg_cmd=FFMPEG_CMD,
        )
        self.nb.add(self.music_tab, text="Music")

        self.video_tab = VideoTab(
            self.nb,
            log_q=self.video_log_q,
            ffmpeg_cmd=FFMPEG_CMD,
        )
        self.nb.add(self.video_tab, text="Video")

    def _open_link(self, url: str):
        import webbrowser

        webbrowser.open_new(url)

    def _validate_tools(self):
        def _works(cmd: str) -> bool:
            try:
                subprocess.run(
                    [cmd, "-version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    **_no_console_kwargs(),
                )
                return True
            except Exception as e:
                for q in (self.music_log_q, self.video_log_q):
                    q.put(f"[DEBUG] ffmpeg check failed for '{cmd}': {e!r}")
                return False

        if not _works(FFMPEG_CMD):
            for q in (self.music_log_q, self.video_log_q):
                q.put(
                    "[ERROR] ffmpeg not found. Install ffmpeg globally (and add to "
                    "PATH) or place ffmpeg.exe in the app's bin/ folder."
                )


if __name__ == "__main__":
    PipMediaApp().mainloop()
