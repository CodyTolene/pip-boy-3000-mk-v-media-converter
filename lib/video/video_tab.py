import os
import threading
import queue
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog

from lib.common.ffmpeg_tools import FFmpegProcess
from lib.common.os_utils import open_folder

VIDEO_EXTENSIONS = (
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
    ".wmv",
    ".flv",
    ".mts",
    ".m2ts",
    ".ts",
    ".3gp",
)
VIDEO_EXT_SET = set(VIDEO_EXTENSIONS)

VIDEO_FILETYPES = [
    ("Video files", tuple(f"*{ext}" for ext in VIDEO_EXTENSIONS)),
    ("All files", "*.*"),
]

# 480x320 = Full Screen
# 408x248 = Map Size
# 340x210 = PipTube Video Player Size

TARGET_W = 340
TARGET_H = 210
TARGET_FPS = 12

# Audio
TARGET_A_RATE = "16000"  # 16 kHz
TARGET_A_CHANNELS = "1"  # mono


class VideoTab(ttk.Frame):
    on_running_changed = None

    def __init__(self, master, *, log_q: queue.Queue, ffmpeg_cmd: str):
        super().__init__(master)
        self.log_q, self.ff = log_q, FFmpegProcess(ffmpeg_cmd, log_q)
        self.is_running = False
        self.files: list[Path] = []
        self._known_paths: set[str] = set()
        self._last_dir = str(Path.home())
        self._refreshing = False

        # Preview
        self._preview_tmp: Path | None = None
        self._preview_after_id: str | None = None
        self._preview_target: Path | None = None
        self._preview_img = None  # keep reference so Tk does not GC it

        # Custom size state
        self.custom_w_var = tk.StringVar(value=str(TARGET_W))
        self.custom_h_var = tk.StringVar(value=str(TARGET_H))

        # Layout
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=0)

        self.rowconfigure(0, weight=1, minsize=TARGET_H + 28)
        for r in (1, 2, 3):
            self.rowconfigure(r, weight=0)
        self.rowconfigure(4, weight=1)

        # Preview window
        self.preview_frame = ttk.Frame(self)
        self.preview_frame.grid(row=0, column=0, sticky="nw", padx=(10, 10), pady=10)
        self.preview_canvas = tk.Canvas(
            self.preview_frame,
            width=TARGET_W,
            height=TARGET_H,
            highlightthickness=1,
            highlightbackground="#a0a0a0",
        )
        self.preview_canvas.pack(side="top")

        # Dynamic size note under the preview
        self.preview_size_var = tk.StringVar(value=f"{TARGET_W} x {TARGET_H}")
        self.preview_note = ttk.Label(self.preview_frame, textvariable=self.preview_size_var)
        self.preview_note.pack(side="top", pady=(6, 12))

        self._preview_show_text("No preview")

        # File list
        list_wrap = ttk.Frame(self)
        list_wrap.grid(row=0, column=1, sticky="nsew", padx=(0, 6), pady=(10, 6))
        list_wrap.grid_rowconfigure(0, weight=1)
        list_wrap.grid_columnconfigure(0, weight=1)

        self.file_list = tk.Listbox(
            list_wrap, selectmode=tk.EXTENDED, height=18, exportselection=False
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(
            list_wrap, orient="vertical", command=self.file_list.yview
        )
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.config(yscrollcommand=list_scroll.set)
        self.file_list.bind("<<ListboxSelect>>", self._on_list_select)

        self.empty_hint = ttk.Label(
            self, text="No files selected.", foreground="#000", background="#fff"
        )
        self._toggle_empty_hint()

        # File list buttons
        btns = ttk.Frame(self)
        btns.grid(row=0, column=2, sticky="n", padx=10, pady=(10, 6))
        ttk.Button(btns, text="Add files", command=self.add_files).pack(
            pady=(0, 10), fill="x"
        )
        self.btn_up = ttk.Button(
            btns, text="Up", width=12, command=lambda: self.move_selected(-1)
        )
        self.btn_up.pack(pady=2, fill="x")
        self.btn_down = ttk.Button(
            btns, text="Down", width=12, command=lambda: self.move_selected(+1)
        )
        self.btn_down.pack(pady=2, fill="x")
        self.btn_remove = ttk.Button(
            btns, text="Remove", width=12, command=self.remove_selected
        )
        self.btn_remove.pack(pady=2, fill="x")
        self.btn_clear = ttk.Button(
            btns, text="Clear", width=12, command=self.clear_list
        )
        self.btn_clear.pack(pady=2, fill="x")

        # Output row
        out_row = ttk.Frame(self)
        out_row.grid(row=1, column=0, columnspan=3, sticky="we", padx=10, pady=(0, 6))
        out_row.columnconfigure(1, weight=1)
        ttk.Button(out_row, text="Output folder", command=self.pick_folder).grid(
            row=0, column=0, sticky="w"
        )
        self.output_dir_var = tk.StringVar()
        self.output_dir_var.trace_add("write", lambda *_: self.update_controls())
        self.output_entry = ttk.Entry(out_row, textvariable=self.output_dir_var)
        self.output_entry.grid(row=0, column=1, sticky="we", padx=(8, 0))
        self.open_dir_btn = ttk.Button(
            out_row, text="Open", command=self._open_output_dir, state="disabled"
        )
        self.open_dir_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))

        # Options row
        options = ttk.Frame(self)
        options.grid(row=2, column=0, columnspan=3, sticky="we", padx=10, pady=(0, 6))
        ttk.Label(options, text="Scaling:").pack(side="left")
        self.scale_mode = tk.StringVar(value="contain")

        def _on_mode_change():
            is_custom = self.scale_mode.get() == "custom"
            if is_custom:
                self._hide_preview()
            else:
                self._show_preview()
                self._schedule_preview_update(debounce=True)
            self._toggle_custom_inputs()
            self._update_preview_note()

        for label, val in [
            ("Contain / Letterbox", "contain"),
            ("Cover / Zoom", "cover"),
            ("Fill / Stretch", "stretch"),
            ("Custom", "custom"),
        ]:
            ttk.Radiobutton(
                options,
                text=label,
                variable=self.scale_mode,
                value=val,
                command=_on_mode_change,
            ).pack(side="left", padx=(8, 0))

        # Custom size inputs (hidden unless Custom is selected)
        self.custom_box = ttk.Frame(options)
        self.custom_box.pack(side="left", padx=(16, 0))
        ttk.Label(self.custom_box, text="W:").pack(side="left")
        self.custom_w_entry = ttk.Entry(
            self.custom_box, textvariable=self.custom_w_var, width=6, justify="right"
        )
        self.custom_w_entry.pack(side="left", padx=(2, 8))
        ttk.Label(self.custom_box, text="H:").pack(side="left")
        self.custom_h_entry = ttk.Entry(
            self.custom_box, textvariable=self.custom_h_var, width=6, justify="right"
        )
        self.custom_h_entry.pack(side="left", padx=(2, 0))

        # Progress bar
        bottom = ttk.Frame(self)
        bottom.grid(row=3, column=0, columnspan=3, sticky="we", padx=10, pady=(0, 6))
        bottom.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="we", padx=(0, 8))
        self.convert_btn = ttk.Button(
            bottom, text="Convert", command=self.start_convert_all
        )
        self.convert_btn.grid(row=0, column=1, sticky="e")

        # Log
        self.log_text = tk.Text(self, height=8, wrap="word", state="disabled")
        self.log_text.grid(
            row=4, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 8)
        )

        for var in (self.custom_w_var, self.custom_h_var):
            var.trace_add("write", lambda *_: self.update_controls())

        self.after(75, self._drain_log)
        self.update_controls()

        # Initialize visibility and size note
        self._toggle_custom_inputs()
        self._update_preview_note()

    def _append_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.configure(state="disabled")

    def _drain_log(self):
        pushed = False
        try:
            while True:
                line = self.log_q.get_nowait()
                self._append_log(line)
                pushed = True
        except queue.Empty:
            pass
        if pushed:
            self.log_text.see("end")
        self.after(100, self._drain_log)

    def _show_preview(self):
        self.preview_frame.grid(row=0, column=0, sticky="nw", padx=(10, 10), pady=10)

    def _hide_preview(self):
        self.preview_frame.grid_remove()

    def _preview_show_text(self, msg: str):
        try:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(TARGET_W // 2, TARGET_H // 2, text=msg)
        except Exception:
            pass

    def _schedule_preview_update(self, debounce: bool = False):
        if self.scale_mode.get() == "custom":
            return  # No preview in custom
        sel = self.file_list.curselection()
        if not sel:
            self._preview_show_text("No preview")
            return
        idx = sel[0]
        if not (0 <= idx < len(self.files)):
            self._preview_show_text("No preview")
            return

        target = self.files[idx]
        self._preview_target = target

        delay_ms = 250 if debounce else 0
        if self._preview_after_id is not None:
            try:
                self.after_cancel(self._preview_after_id)
            except Exception:
                pass
            self._preview_after_id = None

        def go():
            threading.Thread(
                target=self._build_preview, args=(target,), daemon=True
            ).start()
            self._preview_after_id = None

        self._preview_after_id = self.after(delay_ms, go)

    def _build_preview(self, src: Path):
        if self.scale_mode.get() == "custom":
            return
        if not src or not src.exists():
            self.after(0, lambda: self._preview_show_text("No preview"))
            return

        vf = self._vf_preview()

        try:
            if self._preview_tmp is None:
                self._preview_tmp = (
                    Path(tempfile.gettempdir()) / f"pipboy_preview_{os.getpid()}.png"
                )
            else:
                try:
                    self._preview_tmp.unlink(missing_ok=True)
                except Exception as e:
                    self.log_q.put(f"[ERROR] Failed to delete preview tmp file: {e!r}")

            cmd = [
                self.ff.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                "1.0",
                "-i",
                str(src),
                "-vframes",
                "1",
                "-vf",
                vf,
                str(self._preview_tmp),
            ]
            code = self.ff.run(cmd)
            if code != 0 or not self._preview_tmp.exists():
                self.after(0, lambda: self._preview_show_text("(Preview unavailable)"))
                return

            if self._preview_target != src:
                return

            def apply():
                try:
                    self._preview_img = tk.PhotoImage(file=str(self._preview_tmp))
                    self.preview_canvas.delete("all")
                    self.preview_canvas.create_image(
                        TARGET_W // 2, TARGET_H // 2, image=self._preview_img
                    )
                except Exception:
                    self._preview_show_text("(Preview unsupported)")

            self.after(0, apply)

        except Exception as e:
            self.log_q.put(f"[ERROR] Preview failed: {e!r}")
            self.after(0, lambda: self._preview_show_text("(Preview error)"))

    def _toggle_custom_inputs(self):
        is_custom = self.scale_mode.get() == "custom"
        if is_custom:
            self.custom_box.pack(side="left", padx=(16, 0))
        else:
            self.custom_box.pack_forget()

    def _toggle_empty_hint(self):
        if len(self.files) == 0:
            self.empty_hint.grid(row=0, column=1, sticky="n", padx=0, pady=(12, 0))
        else:
            try:
                self.empty_hint.grid_forget()
            except Exception:
                pass

    def _on_list_select(self, _e=None):
        if self._refreshing:
            return
        self.update_controls()
        self._schedule_preview_update(debounce=True)

    def update_controls(self):
        count = len(self.files)
        selected = list(self.file_list.curselection())
        out_dir_str = self.output_dir_var.get().strip()

        move_ok = count > 1 and selected and not self.is_running
        self.btn_up.config(state=("normal" if move_ok else "disabled"))
        self.btn_down.config(state=("normal" if move_ok else "disabled"))
        self.btn_remove.config(
            state=("normal" if selected and not self.is_running else "disabled")
        )
        self.btn_clear.config(
            state=("normal" if count >= 1 and not self.is_running else "disabled")
        )
        self.convert_btn.config(
            state=(
                "normal"
                if (count >= 1 and out_dir_str and not self.is_running)
                else "disabled"
            )
        )

        open_ok = False
        if out_dir_str:
            p = Path(out_dir_str)
            try:
                open_ok = p.exists() and p.is_dir() and any(p.iterdir())
            except Exception:
                open_ok = False
        self.open_dir_btn.config(state=("normal" if open_ok else "disabled"))

        self._toggle_empty_hint()
        self._update_preview_note()

    def add_files(self):
        try:
            paths = filedialog.askopenfilenames(
                parent=self.winfo_toplevel(),
                title="Select video files",
                filetypes=VIDEO_FILETYPES,
                initialdir=self._last_dir,
            )
        except Exception as e:
            self.log_q.put(f"[ERROR] Open dialog failed: {e}")
            return
        if not paths:
            return

        self._last_dir = str(Path(paths[0]).parent)

        for raw in paths:
            p = Path(raw)
            if p.suffix.lower() not in VIDEO_EXT_SET:
                continue
            key = os.path.normcase(os.path.abspath(str(p)))
            if key in self._known_paths:
                continue
            self._known_paths.add(key)
            self.files.append(p)

        self._refresh_list()

    def remove_selected(self):
        sel = list(self.file_list.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            try:
                self._known_paths.discard(
                    os.path.normcase(os.path.abspath(str(self.files[idx])))
                )
            except Exception:
                pass
            self.files.pop(idx)
        self._refresh_list()

    def clear_list(self):
        self.files.clear()
        self._known_paths.clear()
        self._refresh_list()

    def move_selected(self, delta: int):
        sel = list(self.file_list.curselection())
        if not sel:
            return
        iterate = sel if delta < 0 else list(reversed(sel))
        for i in iterate:
            j = i + delta
            if 0 <= j < len(self.files):
                self.files[i], self.files[j] = self.files[j], self.files[i]
        self._refresh_list()
        for i in [min(max(0, i + delta), len(self.files) - 1) for i in sel]:
            self.file_list.selection_set(i)

    def _refresh_list(self):
        self._refreshing = True
        try:
            self.file_list.delete(0, tk.END)
            for p in self.files:
                self.file_list.insert(tk.END, p.name)
            if self.files and not self.file_list.curselection():
                self.file_list.selection_set(0)
        finally:
            self._refreshing = False
        self.update_controls()
        self._schedule_preview_update(debounce=True)

    def pick_folder(self):
        folder = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title="Choose output folder",
            initialdir=self._last_dir,
        )
        if folder:
            self.output_dir_var.set(folder)
            self._last_dir = folder

    def _open_output_dir(self):
        path = self.output_dir_var.get().strip()
        if not path:
            return
        open_folder(Path(path))

    def _vf_core(self) -> str:
        mode = (self.scale_mode.get() or "").lower()
        w, h = TARGET_W, TARGET_H

        if mode == "custom":
            w, h = self._get_custom_size()
            core = f"scale={w}:{h}:flags=lanczos,setsar=1"
        elif "stretch" in mode:
            core = f"scale={w}:{h}:flags=lanczos,setsar=1"
        elif "cover" in mode or "fill" in mode:
            s = f"max({w}/iw\\,{h}/ih)"
            we = f"trunc(iw*{s}/2)*2"
            he = f"trunc(ih*{s}/2)*2"
            core = f"scale={we}:{he}:flags=lanczos,setsar=1,crop={w}:{h}"
        else:
            s = f"min({w}/iw\\,{h}/ih)"
            we = f"trunc(iw*{s}/2)*2"
            he = f"trunc(ih*{s}/2)*2"
            core = (
                f"scale={we}:{he}:flags=lanczos,setsar=1,"
                + f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
            )
        return core

    def _vf_convert(self) -> str:
        return f"{self._vf_core()},fps={TARGET_FPS},format=pal8"

    def _vf_preview(self) -> str:
        return f"{self._vf_core()},format=rgb24"

    def _get_custom_size(self) -> tuple[int, int]:
        def _parse(v: str, fallback: int) -> int:
            try:
                n = int(v.strip())
                if n <= 0:
                    raise ValueError
                # keep even for pal8/yuv-style alignments
                if n % 2 == 1:
                    n -= 1
                if n <= 0:
                    n = fallback
                return n
            except Exception:
                return fallback

        w = _parse(self.custom_w_var.get(), TARGET_W)
        h = _parse(self.custom_h_var.get(), TARGET_H)
        self.custom_w_var.set(str(w))
        self.custom_h_var.set(str(h))
        return w, h

    def _peek_custom_size(self) -> tuple[int, int]:
        """Parse custom W and H without mutating StringVars."""
        def _parse(v: str, fallback: int) -> int:
            try:
                n = int(v.strip())
                if n <= 0:
                    return fallback
                if n % 2 == 1:
                    n -= 1
                return n if n > 0 else fallback
            except Exception:
                return fallback

        return _parse(self.custom_w_var.get(), TARGET_W), _parse(self.custom_h_var.get(), TARGET_H)

    def _current_target_size(self) -> tuple[int, int]:
        """Report intended output dimensions based on mode."""
        if (self.scale_mode.get() or "").lower() == "custom":
            return self._peek_custom_size()
        return TARGET_W, TARGET_H

    def _update_preview_note(self):
        """Refresh the label text under the preview to show W x H."""
        w, h = self._current_target_size()
        self.preview_size_var.set(f"{w} x {h}")

    def start_convert_all(self):
        if self.is_running:
            return
        if not self.files:
            self.log_q.put("[ERROR] Add at least one video file.")
            return
        out_dir = self.output_dir_var.get().strip()
        if not out_dir:
            self.log_q.put("[ERROR] Please choose an output folder.")
            return
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        self.is_running = True
        self.progress["mode"] = "determinate"
        self.progress["maximum"] = len(self.files)
        self.progress["value"] = 0
        if callable(self.on_running_changed):
            self.on_running_changed(True)

        def worker():
            ok = True
            for idx, src in enumerate(self.files, start=1):
                dst = Path(out_dir) / f"{src.name}.avi"
                self.log_q.put(f"[*] Converting {src.name} -> {dst.name}")

                vf = self._vf_convert()

                cmd = [
                    self.ff.ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-stats",
                    "-y",
                    "-i",
                    str(src),
                    "-vf",
                    vf,
                    "-vsync",
                    "cfr",
                    "-r",
                    str(TARGET_FPS),
                    "-c:v",
                    "msrle",
                    "-pix_fmt",
                    "pal8",
                    "-ac",
                    TARGET_A_CHANNELS,
                    "-ar",
                    TARGET_A_RATE,
                    "-c:a",
                    "pcm_s16le",
                    "-max_interleave_delta",
                    "0",
                    "-use_odml",
                    "0",
                    "-f",
                    "avi",
                    str(dst),
                ]

                code = self.ff.run(cmd)
                self.after(0, self.progress.configure, {"value": idx})
                if code != 0:
                    self.log_q.put(f"[ERROR] Conversion failed: {src}")
                    ok = False
                    break

            def end(ok_):
                if ok_:
                    self.log_q.put("[OK] Convert complete.")
                self.is_running = False
                if callable(self.on_running_changed):
                    self.on_running_changed(False)
                self.update_controls()

            self.after(0, end, ok)

        threading.Thread(target=worker, daemon=True).start()
