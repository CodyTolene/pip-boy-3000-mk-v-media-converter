import os
import threading
import queue
import subprocess
import signal
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog
import subprocess as _sp

AUDIO_OUT_RATE = "16000"
AUDIO_OUT_CHANNELS = "1"
AUDIO_OUT_CODEC = "pcm_s16le"
AUDIO_OUT_SAMPLE_FMT = "s16"
PREVIEW_SECONDS = 8

AUDIO_EXTENSIONS = (
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".wma",
    ".aif",
    ".aiff",
    ".alac",
    ".ac3",
)
AUDIO_FILETYPES = [
    ("Audio files", [f"*{ext}" for ext in AUDIO_EXTENSIONS]),
    ("All files", "*.*"),
]


def _no_console_kwargs() -> dict:
    try:
        if os.name == "nt":
            si = _sp.STARTUPINFO()
            si.dwFlags |= _sp.STARTF_USESHOWWINDOW
            return {"startupinfo": si, "creationflags": _sp.CREATE_NO_WINDOW}
    except Exception:
        pass
    return {}


def fmt_bytes(n: int | None) -> str:
    if not n or n <= 0:
        return "N/A"
    mb = n / (1024 * 1024)
    return f"{mb:.2f} MB"


def fmt_hms(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "N/A"
    total = int(round(seconds))
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"


def is_audio(path: Path) -> bool:
    return path.suffix.lower() in set(AUDIO_EXTENSIONS)


class PathTools:
    @staticmethod
    def normalize(p: Path) -> str:
        try:
            abs_path = os.path.abspath(str(p))
        except Exception:
            abs_path = str(p)
        return os.path.normcase(abs_path)


class Probe:
    def __init__(self, ffmpeg_cmd: str):
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
            cmd = [
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
    def __init__(self, ffmpeg_cmd: str, log_q: queue.Queue):
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
            self.log_q.put(f"[ERROR] {e}")
            return 1

    @staticmethod
    def guess_ffplay(ffmpeg_cmd: str) -> str:
        """
        Try to derive an ffplay path from the provided ffmpeg path.
        Fallback to 'ffplay' on PATH.
        """
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


class MusicTab(ttk.Frame):
    on_running_changed = None

    def __init__(self, master, *, log_q: queue.Queue, ffmpeg_cmd: str):
        super().__init__(master)
        self.log_q, self.probe = log_q, Probe(ffmpeg_cmd)
        self.ff = FFmpegProcess(ffmpeg_cmd, log_q)
        self.ffplay_cmd = FFmpegProcess.guess_ffplay(ffmpeg_cmd)
        self.is_running, self.convert_finished_once = False, False
        self.files: list[Path] = []
        self._last_dir = str(Path.home())
        self._duration_cache: dict[Path, float] = {}
        self._known_paths: set[str] = set()
        self._preview_proc: subprocess.Popen | None = None

        # Layout
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=1)
        for r in (1, 2, 3, 4, 5):
            self.rowconfigure(r, weight=0)

        # List row
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)

        self.file_list = tk.Listbox(left, selectmode=tk.EXTENDED, height=14)
        self.file_list.grid(row=0, column=0, sticky="nsew")
        self.file_list.bind("<<ListboxSelect>>", self._on_list_select)

        list_scroll = ttk.Scrollbar(
            left, orient="vertical", command=self.file_list.yview
        )
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.config(yscrollcommand=list_scroll.set)

        self.empty_hint = ttk.Label(
            self, text="No files selected.", foreground="#000", background="#fff"
        )
        self._toggle_empty_hint()

        btns = ttk.Frame(self)
        btns.grid(row=0, column=1, sticky="ne", padx=10, pady=(10, 6))

        self.btn_add = ttk.Button(
            btns,
            text="Add files",
            command=lambda: self.add_files(self.file_list, self.files),
        )
        self.btn_add.pack(pady=(0, 10), fill="x")

        self.btn_up = ttk.Button(
            btns,
            text="Up",
            width=12,
            command=lambda: self.move_selected(self.file_list, self.files, -1),
        )
        self.btn_up.pack(pady=2, fill="x")

        self.btn_down = ttk.Button(
            btns,
            text="Down",
            width=12,
            command=lambda: self.move_selected(self.file_list, self.files, +1),
        )
        self.btn_down.pack(pady=2, fill="x")

        self.btn_remove = ttk.Button(
            btns,
            text="Remove",
            width=12,
            command=lambda: self.remove_selected(self.file_list, self.files),
        )
        self.btn_remove.pack(pady=2, fill="x")

        self.btn_clear = ttk.Button(
            btns,
            text="Clear",
            width=12,
            command=lambda: self.clear_list(self.file_list, self.files),
        )
        self.btn_clear.pack(pady=2, fill="x")

        # Output row
        self.output_dir_var = tk.StringVar()
        self.output_dir_var.trace_add("write", lambda *_: self.update_controls())
        out_row = ttk.Frame(self)
        out_row.grid(row=1, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 6))
        ttk.Button(
            out_row,
            text="Output folder",
            command=lambda: self.pick_folder(self.output_dir_var),
        ).pack(side="left")
        self.output_entry = ttk.Entry(out_row, textvariable=self.output_dir_var)
        self.output_entry.pack(side="left", padx=(8, 0), fill="x", expand=True)

        self.open_dir_btn = ttk.Button(
            out_row, text="Open", command=self._open_output_dir, state="disabled"
        )
        self.open_dir_btn.pack(side="right")

        # Volume options row
        options_row = ttk.Frame(self)
        options_row.grid(
            row=2, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 6)
        )
        options_row.grid_columnconfigure(0, weight=1)

        vol_group = ttk.Frame(options_row)
        vol_group.grid(row=0, column=0, sticky="we")
        ttk.Label(vol_group, text="Volume gain (dB):").pack(side="left", padx=(0, 8))
        self.volume_db = tk.DoubleVar(value=0.0)
        self.volume_scale = ttk.Scale(
            vol_group,
            from_=-20.0,
            to=20.0,
            orient="horizontal",
            variable=self.volume_db,
            command=lambda _v: self._on_volume_change(),
        )
        self.volume_scale.pack(side="left", padx=8, fill="x", expand=True)
        self.volume_label = ttk.Label(vol_group, text="0.0 dB")
        self.volume_label.pack(side="left", padx=(8, 0))

        # Preview and file info row
        preview_row = ttk.Frame(self)
        preview_row.grid(
            row=3, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 6)
        )
        self.play_btn = ttk.Button(
            preview_row,
            text=f"▶ Play ~{PREVIEW_SECONDS}s Preview",
            command=self.start_preview,
        )
        self.play_btn.pack(side="left")
        self.stop_btn = ttk.Button(
            preview_row, text="■ Stop", command=self.stop_preview, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.length_label = ttk.Label(preview_row, text="Length: N/A")
        self.length_label.pack(side="left", padx=(16, 8))
        self.orig_size_label = ttk.Label(preview_row, text="File size: N/A")
        self.orig_size_label.pack(side="left")

        # Progress bar
        bottom_bar = ttk.Frame(self)
        bottom_bar.grid(
            row=4, column=0, columnspan=2, sticky="we", padx=10, pady=(0, 6)
        )
        bottom_bar.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(bottom_bar, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="we", padx=(0, 8))
        self.convert_btn = ttk.Button(
            bottom_bar, text="Convert", command=self.start_convert_all
        )
        self.convert_btn.grid(row=0, column=1, sticky="e")

        # Log
        self.log_text = tk.Text(self, height=8, wrap="word", state="disabled")
        self.log_text.grid(
            row=5, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 8)
        )

        # Cleanup on close to ensure preview process is stopped
        self.bind("<<Destroy>>", lambda *_: self.stop_preview())

        self.update_controls()
        self.after(75, self._drain_log)
        self.after(0, self._set_initial_minsize)

    def _set_initial_minsize(self):
        try:
            top = self.winfo_toplevel()
            top.update_idletasks()
            w = top.winfo_width()
            h = top.winfo_height()
            if w > 1 and h > 1:
                top.minsize(w, h)
        except Exception:
            pass

    def _append_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.configure(state="disabled")

    def _drain_log(self):
        pushed_any = False
        try:
            while True:
                line = self.log_q.get_nowait()
                self._append_log(line + "\n")
                pushed_any = True
        except queue.Empty:
            pass
        if pushed_any:
            self.log_text.see("end")
        self.after(100, self._drain_log)

    def _af(self) -> list[str]:
        try:
            db = float(self.volume_db.get())
        except Exception:
            db = 0.0
        if abs(db) < 0.05:
            return []
        return ["-af", f"volume={db:.1f}dB"]

    def on_interaction(self, _event=None):
        if not self.is_running and self.convert_finished_once:
            try:
                self.progress["value"] = 0
            except Exception:
                pass
            self.convert_finished_once = False

    def _dir_has_files(self, folder: Path) -> bool:
        try:
            for p in folder.iterdir():
                if p.is_file():
                    return True
            return False
        except Exception:
            return False

    def update_controls(self):
        count = len(self.files)
        selected = list(self.file_list.curselection())
        out_dir_str = self.output_dir_var.get().strip()
        has_output = bool(out_dir_str)

        move_ok = count > 1 and selected and not self.is_running
        self.btn_up.config(state=("normal" if move_ok else "disabled"))
        self.btn_down.config(state=("normal" if move_ok else "disabled"))
        self.btn_remove.config(
            state=("normal" if (selected and not self.is_running) else "disabled")
        )
        self.btn_clear.config(
            state=("normal" if (count >= 1 and not self.is_running) else "disabled")
        )

        can_convert_all = (count >= 1) and has_output and (not self.is_running)
        self.convert_btn.config(state=("normal" if can_convert_all else "disabled"))

        # Preview button enabled when a file is selected and nothing else is running
        can_preview = (
            (count >= 1)
            and selected
            and (not self.is_running)
            and (self._preview_proc is None)
        )
        self.play_btn.config(state=("normal" if can_preview else "disabled"))
        self.stop_btn.config(
            state=("normal" if self._preview_proc is not None else "disabled")
        )

        # Enable/disable "Open" button
        open_ok = False
        if out_dir_str:
            p = Path(out_dir_str)
            if p.exists() and p.is_dir() and self._dir_has_files(p):
                open_ok = True
        self.open_dir_btn.config(state=("normal" if open_ok else "disabled"))

        if count > 0 and not selected:
            self.file_list.selection_set(0)

        self._toggle_empty_hint()
        self._update_selected_info_labels()

    def _toggle_empty_hint(self):
        if len(self.files) == 0:
            self.empty_hint = getattr(
                self,
                "empty_hint",
                ttk.Label(
                    self,
                    text="No files selected.",
                    foreground="#000",
                    background="#fff",
                ),
            )
            self.empty_hint.grid(
                row=0, column=0, columnspan=2, sticky="n", padx=0, pady=(12, 0)
            )
        else:
            try:
                self.empty_hint.grid_forget()
            except Exception:
                pass

    def _selected_path(self) -> Path | None:
        sel = self.file_list.curselection()
        if not sel:
            return None
        idx = sel[0]
        if 0 <= idx < len(self.files):
            return self.files[idx]
        return None

    def start_preview(self):
        if self._preview_proc is not None:
            return  # already playing
        src = self._selected_path()
        if not src:
            self.log_q.put("[WARN] Select a file to preview.")
            self.update_controls()
            return

        # Build ffplay command
        af = self._af()
        cmd = [
            self.ffplay_cmd,
            "-nodisp",
            "-autoexit",
            "-vn",
            "-t",
            str(PREVIEW_SECONDS),
            "-i",
            str(src),
        ]
        if af:
            cmd.extend(af)

        self.log_q.put(
            f"[*] Previewing {src.name} for ~{PREVIEW_SECONDS}s "
            + f"({' '.join(af) if af else 'no gain'})"
        )
        try:
            self._preview_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_no_console_kwargs(),
            )
        except FileNotFoundError:
            self._preview_proc = None
            self.log_q.put(
                "[ERROR] ffplay not found. Install ffplay or place it next to ffmpeg."
            )
        except Exception as e:
            self._preview_proc = None
            self.log_q.put(f"[ERROR] Preview failed to start: {e}")

        # Re enable controls when finished
        if self._preview_proc is not None:
            self.stop_btn.config(state="normal")
            self.play_btn.config(state="disabled")
            self.after(300, self._poll_preview_done)
        else:
            self.update_controls()

    def _poll_preview_done(self):
        if self._preview_proc is None:
            self.update_controls()
            return
        code = self._preview_proc.poll()
        if code is None:
            # still running
            self.after(300, self._poll_preview_done)
            return
        self._preview_proc = None
        self.update_controls()

    def stop_preview(self):
        proc = self._preview_proc
        if proc is None:
            self.update_controls()
            return
        try:
            if os.name == "nt":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            self._preview_proc = None
            self.update_controls()

    def _open_output_dir(self):
        path = self.output_dir_var.get().strip()
        if not path:
            return
        p = Path(path)
        if not (p.exists() and p.is_dir()):
            return
        try:
            if os.name == "nt":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)], **_no_console_kwargs())
            else:
                subprocess.Popen(["xdg-open", str(p)], **_no_console_kwargs())
        except Exception as e:
            self.log_q.put(f"[ERROR] Could not open folder: {e}")

    def add_files(self, listbox: tk.Listbox, store: list[Path]):
        try:
            paths = filedialog.askopenfilenames(
                parent=self.winfo_toplevel(),
                title="Select audio files",
                filetypes=AUDIO_FILETYPES,
                initialdir=self._last_dir,
            )
        except Exception as e:
            self.log_q.put(f"[ERROR] Open dialog failed: {e}")
            return

        if not paths:
            self.update_controls()
            return

        self._last_dir = str(Path(paths[0]).parent)

        picked: list[Path] = []
        for raw in paths:
            p = Path(raw)
            if not is_audio(p):
                continue
            key = PathTools.normalize(p)
            if key in self._known_paths:
                continue
            self._known_paths.add(key)
            picked.append(p)

        if not picked:
            self.update_controls()
            return

        store.extend(picked)
        self._refresh_list(listbox, store)
        self.update_controls()

        if listbox.size() and not listbox.curselection():
            listbox.selection_set(0)
        self._update_selected_info_labels()

    def remove_selected(self, listbox: tk.Listbox, store: list[Path]):
        sel = list(listbox.curselection())
        if not sel:
            return

        first_idx = sel[0]
        for idx in reversed(sel):
            if 0 <= idx < len(store):
                try:
                    self._known_paths.discard(PathTools.normalize(store[idx]))
                except Exception:
                    pass
                store.pop(idx)

        self._refresh_list(listbox, store)

        if store:
            target = max(0, min(first_idx - 1, len(store) - 1))
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(target)

        self.update_controls()

    def clear_list(self, listbox: tk.Listbox, store: list[Path]):
        store.clear()
        self._known_paths.clear()
        self._refresh_list(listbox, store)
        self.update_controls()

    def move_selected(self, listbox: tk.Listbox, store: list[Path], delta: int):
        sel = list(listbox.curselection())
        if not sel:
            return

        if delta < 0:
            for i in sel:
                j = i + delta
                if j >= 0:
                    store[i], store[j] = store[j], store[i]
        else:
            for i in reversed(sel):
                j = i + delta
                if j < len(store):
                    store[i], store[j] = store[j], store[i]

        self._refresh_list(listbox, store)
        for i in [min(max(0, i + delta), len(store) - 1) for i in sel]:
            listbox.selection_set(i)

        self.update_controls()

    def _refresh_list(self, listbox: tk.Listbox, store: list[Path]):
        listbox.delete(0, tk.END)
        for p in store:
            listbox.insert(tk.END, p.name)
        if store and not listbox.curselection():
            listbox.selection_set(0)
        self._toggle_empty_hint()

    def pick_folder(self, var: tk.StringVar):
        folder = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title="Choose output folder",
            initialdir=self._last_dir,
        )
        if folder:
            var.set(folder)
            self._last_dir = folder
        self.update_controls()

    def _on_list_select(self, _event=None):
        # Stop preview when switching selection
        if self._preview_proc is not None:
            self.stop_preview()
        self.update_controls()

    def _on_volume_change(self):
        try:
            db = float(self.volume_db.get())
        except Exception:
            db = 0.0
        self.volume_label.config(text=f"{db:.1f} dB")
        # If preview is running, restart it with new volume gain
        if self._preview_proc is not None:
            self.stop_preview()
            # Small delay to avoid races
            self.after(100, self.start_preview)

    def _update_selected_info_labels(self):
        sel = self.file_list.curselection()
        if not sel:
            self.length_label.config(text="Length: N/A")
            self.orig_size_label.config(text="File size: N/A")
            return
        idx = sel[0]
        if not (0 <= idx < len(self.files)):
            self.length_label.config(text="Length: N/A")
            self.orig_size_label.config(text="File size: N/A")
            return

        src = self.files[idx]
        duration = self._duration_cache.get(src)
        if duration is None:
            duration = self.probe.duration(src)
            if duration is not None:
                self._duration_cache[src] = duration

        self.length_label.config(text=f"Length: {fmt_hms(duration)}")
        try:
            self.orig_size_label.config(
                text=f"File size: {fmt_bytes(os.path.getsize(src))}"
            )
        except Exception:
            self.orig_size_label.config(text="File size: N/A")

    def _set_progress(self, value: int):
        self.progress["value"] = value

    def _end_convert(self, ok: bool):
        if ok:
            self.log_q.put("[OK] Convert complete.")
        self.is_running = False
        if callable(self.on_running_changed):
            self.on_running_changed(False)
        self.convert_finished_once = True
        self.update_controls()

    def start_convert_all(self):
        if self.is_running:
            return
        if not self.files:
            self.log_q.put("[ERROR] Add at least one audio file.")
            return
        # Stop any preview during conversion
        if self._preview_proc is not None:
            self.stop_preview()
        self._convert_files(list(self.files))

    def _convert_files(self, files: list[Path]):
        if self.is_running:
            return

        out_dir = self.output_dir_var.get().strip()
        if not out_dir:
            self.log_q.put("[ERROR] Please choose an output folder.")
            return
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        self.is_running = True
        if callable(self.on_running_changed):
            self.on_running_changed(True)

        self.convert_finished_once = False
        self.update_controls()
        self.progress["mode"] = "determinate"
        self.progress["maximum"] = len(files)
        self.progress["value"] = 0

        af = self._af()

        def worker():
            ok = True
            for idx, src in enumerate(files, start=1):
                base = src.stem
                dst = Path(out_dir) / f"{base}.wav"
                self.log_q.put(f"[*] Converting {src.name} -> {dst.name}")
                cmd = [
                    self.ff.ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-stats",
                    "-y",
                    "-i",
                    str(src),
                    "-ac",
                    AUDIO_OUT_CHANNELS,
                    "-ar",
                    AUDIO_OUT_RATE,
                    "-sample_fmt",
                    AUDIO_OUT_SAMPLE_FMT,
                    "-c:a",
                    AUDIO_OUT_CODEC,
                    *af,
                    "-f",
                    "wav",
                    str(dst),
                ]
                code = self.ff.run(cmd)
                self.after(0, self._set_progress, idx)
                if code != 0:
                    self.log_q.put(f"[ERROR] Conversion failed: {src}")
                    ok = False
                    break

            self.after(0, self._end_convert, ok)

        threading.Thread(target=worker, daemon=True).start()
