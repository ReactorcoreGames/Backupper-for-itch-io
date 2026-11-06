import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog
from tkinter import ttk as _tk_ttk

import ttkbootstrap as ttk
from ttkbootstrap.widgets import ToolTip

from core.backup import BackupFailed, BackupOptions, run_backup, summarize
from core.urls import InvalidAuthorError, parse_author
from gui import theme
from gui.theme import PALETTE
from utils.config import load_config, resolve_output_folder, save_config

APP_TITLE = "Backupper for itch.io"
APP_SUBTITLE = "Save an offline copy of any itch.io author's page, projects and devlogs."
LINK_URL = "https://linktr.ee/reactorcore"
ITCH_URL = "https://itch.io/"
MIN_DELAY, MAX_DELAY, DEFAULT_DELAY = 0.5, 60.0, 1.0
POLL_MILLISECONDS = 100


class BackupApp:
    def __init__(self):
        self.config = load_config()
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.last_folder = None

        theme.load_bundled_fonts()
        theme.inject_theme()
        self.root = ttk.Window(themename=theme.THEME_NAME)
        self.root.title(APP_TITLE)
        self.root.geometry("1000x760")
        self.root.minsize(960, 730)

        style = ttk.Style()
        theme.apply_theme(style, root=self.root)

        self._apply_icon(self.root)
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(POLL_MILLISECONDS, self._drain_events)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _apply_icon(self, window):
        icon_paths = [
            theme.assets_folder() / "icon.ico",
            Path(sys.executable).parent / "icon.ico",
            Path.cwd() / "icon.ico",
        ]
        for p in icon_paths:
            if p.exists():
                try:
                    window.iconbitmap(str(p))
                    return
                except Exception:
                    continue

    def _attach_context_menu(self, entry_widget):
        menu = tk.Menu(entry_widget, tearoff=0)
        menu.add_command(label="Cut",        command=lambda: entry_widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy",       command=lambda: entry_widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste",      command=lambda: entry_widget.event_generate("<<Paste>>"))
        menu.add_command(label="Select All", command=lambda: entry_widget.event_generate("<<SelectAll>>"))

        def _show(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        entry_widget.bind("<Button-3>", _show)

    def _log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, message, level=""):
        self.status_var.set(message)
        self.status_label.configure(style=f"Status{level.title()}.TLabel" if level else "Status.TLabel")

    # ------------------------------------------------------------------ #
    #  UI Build                                                            #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self):
        header = ttk.Frame(self.root, padding=(18, 12, 18, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        titles = ttk.Frame(header)
        titles.grid(row=0, column=0, sticky="w")
        ttk.Label(titles, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text=APP_SUBTITLE, style="Subtitle.TLabel").pack(anchor="w")
        self._build_itch_button(header)
        tk.Frame(self.root, height=3, bg=PALETTE["accent_brand"]).grid(row=1, column=0, sticky="ew")

    def _build_itch_button(self, parent):
        try:
            normal = tk.PhotoImage(file=str(theme.assets_folder() / "visit_itch_button.png"))
            hover = tk.PhotoImage(file=str(theme.assets_folder() / "visit_itch_button_hover.png"))
        except tk.TclError:
            return  # A missing image should not stop the program from opening.
        self._itch_button_images = (normal, hover)  # Tk does not keep its own reference.
        button = tk.Button(parent, image=normal, command=lambda: webbrowser.open(ITCH_URL), cursor="hand2",
                           relief="flat", borderwidth=0, highlightthickness=0, takefocus=True,
                           background=PALETTE["bg_base"], activebackground=PALETTE["bg_base"])
        button.grid(row=0, column=1, sticky="e", padx=(12, 0))
        button.bind("<Enter>", lambda e: button.configure(image=hover))
        button.bind("<Leave>", lambda e: button.configure(image=normal))
        ToolTip(button, text="Open itch.io in your web browser.")

    def _build_body(self):
        body = ttk.Frame(self.root, padding=(18, 12))
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(5, weight=1)

        self._build_author_section(body)
        self._build_folder_section(body)
        self._build_options_section(body)
        self._build_action_row(body)
        self._build_progress_section(body)
        self._build_log(body)

    def _build_author_section(self, parent):
        frame = _tk_ttk.LabelFrame(parent, text="Whose page do you want to back up?", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        self.author_var = tk.StringVar(value=self.config["author_url"])
        self.author_var.trace_add("write", self._on_setting_changed)
        self.author_entry = ttk.Entry(frame, textvariable=self.author_var, font=theme.FONT_BODY)
        self.author_entry.grid(row=0, column=0, sticky="ew")
        self._attach_context_menu(self.author_entry)
        ToolTip(self.author_entry, text="Any itch.io author: their page address or just their name.")
        ttk.Label(frame, text="Example: https://example.itch.io/  or just  example",
                  style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_folder_section(self, parent):
        frame = _tk_ttk.LabelFrame(parent, text="Where should the backup be saved?", padding=10)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        self.folder_var = tk.StringVar(value=self._folder_display())
        entry = ttk.Entry(frame, textvariable=self.folder_var, state="readonly", font=theme.FONT_BODY)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._attach_context_menu(entry)
        button = ttk.Button(frame, text="Choose Output Folder", width=22, style="Plain.TButton",
                            command=self._choose_folder)
        button.grid(row=0, column=1, sticky="e")
        ToolTip(button, text="Each author gets their own subfolder inside the folder you pick.")

    def _build_options_section(self, parent):
        frame = _tk_ttk.LabelFrame(parent, text="Options", padding=10)
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        self.subpages_var = tk.BooleanVar(value=self.config["include_subpages"])
        self.full_size_var = tk.BooleanVar(value=self.config["full_size_images"])
        self.delay_var = tk.StringVar(value=f"{self._delay_value():g}")
        for variable in (self.subpages_var, self.full_size_var, self.delay_var):
            variable.trace_add("write", self._on_setting_changed)

        subpages = ttk.Checkbutton(frame, text="Include devlogs and other subpages", variable=self.subpages_var)
        subpages.grid(row=0, column=0, sticky="w", pady=(0, 6))
        ToolTip(subpages, text="Turn this off to save only the main page and the project pages.")
        full_size = ttk.Checkbutton(frame, text="Save full-size screenshots", variable=self.full_size_var)
        full_size.grid(row=1, column=0, sticky="w")
        ToolTip(full_size, text="Turn this off for a smaller backup that only has the sizes shown on the page.")

        delay_row = ttk.Frame(frame, style="Surface.TFrame")
        delay_row.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Label(delay_row, text="Seconds to wait between pages", style="Surface.TLabel").pack(side="left", padx=(0, 8))
        spinbox = ttk.Spinbox(delay_row, textvariable=self.delay_var, from_=MIN_DELAY, to=MAX_DELAY,
                              increment=0.5, width=6, font=theme.FONT_BODY)
        spinbox.pack(side="left")
        self._attach_context_menu(spinbox)
        ToolTip(spinbox, text="Going slower is kinder to itch.io's servers. Minimum 0.5 seconds.")

    def _build_action_row(self, parent):
        row = ttk.Frame(parent)
        row.grid(row=3, column=0, sticky="ew", pady=(2, 8))

        self.start_button = ttk.Button(row, text="Start Backup", width=14, style="Primary.TButton", command=self._start)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button = ttk.Button(row, text="Stop", width=7, style="Plain.TButton", state="disabled", command=self._stop)
        self.stop_button.pack(side="left", padx=(0, 8))
        ToolTip(self.stop_button, text="Stops soon. Running the same backup again picks up where it left off.")

        self.view_button = ttk.Button(row, text="View Backup in Browser", width=21, style="Plain.TButton",
                                      state="disabled", command=self._view_backup)
        self.view_button.pack(side="right")
        self.open_button = ttk.Button(row, text="Open Backup Folder", width=18, style="Plain.TButton",
                                      state="disabled", command=self._open_folder)
        self.open_button.pack(side="right", padx=(0, 8))

    def _build_progress_section(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        frame.columnconfigure(0, weight=1)
        self.progress = _tk_ttk.Progressbar(frame, style="Backup.Horizontal.TProgressbar", mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel", wraplength=900)
        self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_log(self, parent):
        frame = ttk.Frame(parent)
        frame.grid(row=5, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(frame, height=8, wrap="word", state="disabled", font=theme.FONT_MONO,
                                bg=PALETTE["bg_input"], fg=PALETTE["text_primary"],
                                insertbackground=PALETTE["text_primary"], relief="solid", borderwidth=1,
                                highlightthickness=0, padx=8, pady=6)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _build_footer(self):
        ttk.Separator(self.root, orient="horizontal").grid(row=3, column=0, sticky="ew")
        footer = ttk.Frame(self.root, padding=(18, 5))
        footer.grid(row=4, column=0, sticky="ew")
        ttk.Label(footer, text="Made by Reactorcore", style="Footer.TLabel").pack(side="left", padx=(0, 6))
        link = ttk.Label(footer, text=LINK_URL, style="Link.TLabel", cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(LINK_URL))
        ttk.Label(footer, text="Unofficial tool, not affiliated with itch.io", style="Footer.TLabel").pack(side="right")

    # ------------------------------------------------------------------ #
    #  Settings                                                            #
    # ------------------------------------------------------------------ #

    def _delay_value(self):
        try:
            value = float(self.delay_var.get() if hasattr(self, "delay_var") else self.config["page_delay"])
        except (TypeError, ValueError, tk.TclError):
            return DEFAULT_DELAY
        return min(max(value, MIN_DELAY), MAX_DELAY)

    def _folder_display(self):
        value = self.config["output_folder"]
        return str(resolve_output_folder(value)) if value else "(no folder chosen yet)"

    def _on_setting_changed(self, *_):
        self.config["author_url"] = self.author_var.get().strip()
        self.config["include_subpages"] = self.subpages_var.get() if hasattr(self, "subpages_var") else self.config["include_subpages"]
        self.config["full_size_images"] = self.full_size_var.get() if hasattr(self, "full_size_var") else self.config["full_size_images"]
        self.config["page_delay"] = self._delay_value()
        self._save_config()

    def _save_config(self):
        try:
            save_config(self.config)
        except OSError as error:
            self._set_status(f"Could not save your settings: {error}", "warning")

    def _choose_folder(self):
        current = resolve_output_folder(self.config["output_folder"]) if self.config["output_folder"] else None
        folder = filedialog.askdirectory(title="Choose where to save backups",
                                         initialdir=str(current) if current and current.is_dir() else None)
        if folder:
            self.config["output_folder"] = folder
            self.folder_var.set(self._folder_display())
            self._save_config()

    # ------------------------------------------------------------------ #
    #  Backup                                                              #
    # ------------------------------------------------------------------ #

    def _start(self):
        try:
            author = parse_author(self.author_var.get())
        except InvalidAuthorError as error:
            self._set_status(str(error), "danger")
            self.author_entry.focus_set()
            return
        if not self.config["output_folder"]:
            self._set_status("Please choose an output folder first.", "danger")
            return

        options = BackupOptions(
            author=author,
            output_dir=resolve_output_folder(self.config["output_folder"]),
            include_subpages=self.subpages_var.get(),
            full_size_images=self.full_size_var.get(),
            page_delay=self._delay_value(),
        )
        self.stop_event = threading.Event()
        self.last_folder = Path(options.output_dir) / author

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.progress.configure(value=0, maximum=1)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.open_button.configure(state="disabled")
        self.view_button.configure(state="disabled")
        self._set_status(f"Scanning {author}.itch.io for pages...")

        self.worker = threading.Thread(target=self._run_worker, args=(options, self.stop_event), daemon=True)
        self.worker.start()

    def _run_worker(self, options, stop_event):
        """Runs on the worker thread. Talks to the GUI only through the queue."""
        try:
            result = run_backup(
                options,
                log=lambda message: self.events.put(("log", message)),
                progress=lambda phase, done, total: self.events.put(("progress", phase, done, total)),
                stop_event=stop_event,
            )
            self.events.put(("finished", result))
        except BackupFailed as error:
            self.events.put(("failed", str(error)))
        except Exception as error:
            self.events.put(("failed", f"Something unexpected went wrong: {error}"))

    def _stop(self):
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self._set_status("Stopping...")

    def _drain_events(self):
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(POLL_MILLISECONDS, self._drain_events)

    def _handle_event(self, event):
        kind = event[0]
        if kind == "log":
            self._log(event[1])
        elif kind == "progress":
            _, phase, done, total = event
            self.progress.configure(value=done, maximum=max(total, 1))
            if not self.stop_event.is_set():
                verb = "Scanning for pages" if phase == "scan" else "Saving pages"
                self._set_status(f"{verb}: {done} of {total}")
        elif kind == "finished":
            self._finish(event[1])
        elif kind == "failed":
            self._reset_buttons()
            self._log(event[1])
            self._set_status(event[1], "danger")

    def _finish(self, result):
        self._reset_buttons()
        summary = summarize(result)
        self._log("")
        self._log(summary)
        level = "success" if result.clean else "warning"
        self._set_status(summary.replace("\n", " "), level)

    def _reset_buttons(self):
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        exists = self.last_folder is not None and self.last_folder.is_dir()
        self.open_button.configure(state="normal" if exists else "disabled")
        has_index = exists and (self.last_folder / "index.html").exists()
        self.view_button.configure(state="normal" if has_index else "disabled")

    def _open_folder(self):
        if self.last_folder and self.last_folder.is_dir():
            os.startfile(self.last_folder)

    def _view_backup(self):
        if self.last_folder:
            webbrowser.open((self.last_folder / "index.html").as_uri())

    def _on_close(self):
        self.stop_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
