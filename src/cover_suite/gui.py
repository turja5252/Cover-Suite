# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import ImageTk

from cover_suite import APP_DISPLAY_NAME, APP_RELEASE_DATE, __version__
from cover_suite.cover import (
    COVER_FONT_CASTELLAR,
    COVER_FONT_HELVETICA,
    CoverInfo,
    compose_cover_preview,
    compose_full_cover_preview,
    cover_pdf_name,
    cover_source_page_count,
    is_cover_pdf,
    normalize_cover_font,
    normalize_photo_page,
    normalize_photo_rotation,
    write_cover_pdf,
)
from cover_suite.handoff import write_cover_handoff
from cover_suite.paths import cover_asset, default_settings_path
from cover_suite.project_inputs import (
    fields_from_env,
    load_cover_fields,
    load_cover_inputs,
    overlay_nonempty,
    save_cover_inputs,
)
from cover_suite.suite_folders import last_engine_suite_output, picker_start_dir
from cover_suite.ui_scale import install_ui_scaling, pack_font_size_toggle
from cover_suite.widgets import styled_button

BACKGROUND = "#100e08"
PANEL = "#1b1810"
TEXT = "#f5ead0"
MUTED = "#a8946a"
ACCENT = "#c9a227"
ACCENT_DIM = "#3d2f14"
ENTRY = "#0c0a06"
BORDER = "#4a3c20"
LCD_BG = "#161208"
LCD_FG = "#f0c674"
LCD_DIM = "#8a7038"
LIVE_BG = "#3d2f14"

FIELD_ORDER = (
    ("client", "Client"),
    ("description", "Tank / description"),
    ("location", "Location"),
    ("tag", "Tag"),
    ("job_number", "Job / package #"),
    ("revision", "Revision"),
)


class CoverGui:
    def __init__(
        self,
        output_dir: str | None = None,
        job_number: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> None:
        self.root = tk.Tk()
        install_ui_scaling(self.root)
        self.root.title(f"{APP_DISPLAY_NAME} {__version__}")
        self.root.configure(bg=BACKGROUND)
        self._apply_startup_geometry()

        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Fill the cover lines, pick a photo, then Generate Cover.")
        self.photo_var = tk.StringVar()
        self.field_vars = {name: tk.StringVar() for name, _label in FIELD_ORDER}
        self.text_mode_var = tk.StringVar(value="standard")
        self.book_font_var = tk.StringVar(value=COVER_FONT_CASTELLAR)
        self._busy = False
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._action_buttons: list[tk.Button] = []
        self._photo_preview: ImageTk.PhotoImage | None = None
        self._photo_zoom = 1.0
        self._photo_pan_x = 0.0
        self._photo_pan_y = 0.0
        self._photo_rotation = 0
        self._photo_page = 1
        self._photo_drag: tuple[float, float, float, float] | None = None
        self._preview_after: str | None = None
        self.preview_mode_var = tk.StringVar(value="photo")
        env_out = os.environ.get("ELITE_COVER_OUTPUT", "").strip()
        env_job = os.environ.get("ELITE_COVER_JOB", "").strip()
        self._locked_output = (str(output_dir).strip() if output_dir else "") or env_out
        self._locked_job = (str(job_number).strip() if job_number else "") or env_job
        self._tab_title = str((fields or {}).get("tab_title") or os.environ.get("ELITE_COVER_TAB", "")).strip()
        self._settings_output = ""

        self._build_layout()
        self._load_settings()
        if self._locked_output:
            self.output_var.set(self._locked_output)
        self._apply_project_inputs(fields)
        if not self.photo_var.get().strip():
            self.photo_var.set(str(cover_asset("elite_cover_photo.jpg")))
        self._sync_pdf_page_chrome()
        self._apply_text_mode(persist=False)
        self._refresh_photo_preview()
        self.root.after(50, self._drain_ui_queue)
        self._log("Welcome. Use standard fields or custom text, swap the photo if needed, then Generate Cover.")
        if self._locked_output:
            self._log(f"Output folder is the Databook folder:\n{self._locked_output}")
        if self.field_vars["job_number"].get().strip():
            self._log(f"Job number is the Databook job: {self.field_vars['job_number'].get().strip()}")

    def _apply_startup_geometry(self) -> None:
        self.root.update_idletasks()
        self.root.minsize(880, 640)
        leftover = {"n": 4}

        def run() -> None:
            if leftover["n"] <= 0:
                return
            leftover["n"] -= 1
            try:
                self.root.update_idletasks()
                self.root.state("zoomed")
            except tk.TclError:
                leftover["n"] = 0
                return
            if leftover["n"] > 0:
                self.root.after(80, run)

        def on_map(event: tk.Event) -> None:  # type: ignore[type-arg]
            if event.widget is not self.root:
                return
            bind_id = getattr(self.root, "_open_max_map", None)
            if bind_id:
                try:
                    self.root.unbind("<Map>", bind_id)
                except tk.TclError:
                    pass
                try:
                    delattr(self.root, "_open_max_map")
                except AttributeError:
                    pass
            run()

        try:
            setattr(self.root, "_open_max_map", self.root.bind("<Map>", on_map, add="+"))
        except tk.TclError:
            pass
        self.root.after_idle(run)
        self.root.after(80, run)

    def _inset_panel(
        self,
        parent: tk.Widget,
        *,
        fill: str = "x",
        expand: bool = False,
        padx: int = 0,
        pady: int = 0,
        face: str = LCD_BG,
        autoplace: bool = True,
    ) -> tuple[tk.Frame, tk.Frame]:
        shell = tk.Frame(parent, bg=BORDER, highlightthickness=0)
        if autoplace:
            shell.pack(fill=fill, expand=expand, padx=padx, pady=pady)
        face_frame = tk.Frame(shell, bg=face, highlightthickness=0)
        face_frame.pack(fill="both", expand=True, padx=1, pady=1)
        return shell, face_frame

    def _entry(self, parent: tk.Widget, variable: tk.StringVar, **pack) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=ENTRY,
            fg=TEXT,
            insertbackground=LCD_FG,
            relief="flat",
            font=("Georgia", 11),
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            justify="center",
        )
        entry.pack(**pack)
        return entry

    def _secondary_button(self, parent: tk.Widget, text: str, command: Callable[[], None]) -> tk.Button:
        return styled_button(parent, text, command, tone="normal", font=("Segoe UI", 9), padx=10, pady=6)

    def _build_layout(self) -> None:
        rail = tk.Frame(self.root, bg=ACCENT, height=3)
        rail.pack(side="top", fill="x")
        rail.pack_propagate(False)

        footer = tk.Frame(self.root, bg=BACKGROUND)
        footer.pack(side="bottom", fill="x")

        cta = tk.Frame(footer, bg=BACKGROUND)
        cta.pack(fill="x", padx=28, pady=(8, 6))
        generate = styled_button(
            cta,
            "▶  Generate Cover",
            self._generate,
            tone="accent",
            font=("Segoe UI Semibold", 11),
            padx=16,
            pady=9,
        )
        generate.pack(side="left")
        self._action_buttons.append(generate)
        reset = self._secondary_button(cta, "Default photo", self._use_default_photo)
        reset.pack(side="left", padx=(8, 0))
        self._action_buttons.append(reset)
        reset_view = self._secondary_button(cta, "Reset view", self._reset_photo_view)
        reset_view.pack(side="left", padx=(8, 0))
        self._action_buttons.append(reset_view)

        log_header = tk.Frame(footer, bg=BACKGROUND)
        log_header.pack(fill="x", padx=28, pady=(2, 0))
        tk.Label(log_header, text="Activity", font=("Segoe UI Semibold", 10), fg=TEXT, bg=BACKGROUND, anchor="w").pack(
            side="left"
        )
        live_chip = tk.Frame(log_header, bg=LIVE_BG, highlightbackground=LCD_DIM, highlightthickness=1)
        live_chip.pack(side="left", padx=(10, 0), pady=(1, 0))
        tk.Label(live_chip, text="LIVE", font=("Consolas", 8, "bold"), fg=LCD_FG, bg=LIVE_BG).pack(padx=7, pady=1)

        _console_shell, console = self._inset_panel(footer, fill="x", padx=28, pady=(4, 14), face=LCD_BG)
        self.log_text = tk.Text(
            console,
            bg=LCD_BG,
            fg=LCD_FG,
            insertbackground=LCD_FG,
            font=("Consolas", 9),
            relief="flat",
            height=5,
            padx=12,
            pady=8,
            highlightthickness=0,
            borderwidth=0,
        )
        self.log_text.pack(fill="x")
        self.log_text.configure(state="disabled")

        main = tk.Frame(self.root, bg=BACKGROUND)
        main.pack(side="top", fill="both", expand=True)

        hero = tk.Frame(main, bg=BACKGROUND)
        hero.pack(fill="x", padx=28, pady=(12, 6))
        title_row = tk.Frame(hero, bg=BACKGROUND)
        title_row.pack(fill="x")
        tk.Label(
            title_row,
            text=APP_DISPLAY_NAME,
            font=("Segoe UI Semibold", 22),
            fg=TEXT,
            bg=BACKGROUND,
            anchor="w",
        ).pack(side="left")
        version_shell, version_pill = self._inset_panel(title_row, face=LCD_BG, autoplace=False)
        version_shell.pack(side="right", pady=(4, 0))
        tk.Label(version_pill, text=f"v{__version__}", font=("Consolas", 9, "bold"), fg=LCD_FG, bg=LCD_BG).pack(
            side="left", padx=(10, 4), pady=4
        )
        tk.Label(version_pill, text=APP_RELEASE_DATE, font=("Consolas", 8), fg=LCD_DIM, bg=LCD_BG).pack(
            side="left", padx=(0, 10), pady=4
        )
        pack_font_size_toggle(
            title_row,
            bg=BACKGROUND,
            fg=TEXT,
            muted=MUTED,
            selectcolor=ENTRY,
            on_change=lambda mode: self._log(
                "Large text on." if mode == "large" else "Normal text size."
            ),
        )
        tk.Label(
            hero,
            text="Draw the Elite cover in-engine, then import it to Databook as [COVER].",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=BACKGROUND,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        _status_outer, status_shell = self._inset_panel(main, fill="x", padx=28, pady=(2, 8), face=LCD_BG)
        status_bar = tk.Frame(status_shell, bg=LCD_BG)
        status_bar.pack(fill="x", padx=4, pady=2)
        tk.Label(status_bar, text="STATUS", font=("Consolas", 8, "bold"), fg=LCD_DIM, bg=LCD_BG).pack(
            side="left", padx=(8, 10), pady=7
        )
        tk.Label(
            status_bar,
            textvariable=self.status_var,
            font=("Consolas", 10),
            fg=LCD_FG,
            bg=LCD_BG,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, pady=7)

        body = tk.Frame(main, bg=BACKGROUND)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 8))
        split_pane = tk.PanedWindow(
            body,
            orient=tk.HORIZONTAL,
            bg=BACKGROUND,
            sashwidth=6,
            sashrelief="flat",
            bd=0,
            opaqueresize=True,
        )
        split_pane.pack(fill="both", expand=True)
        self._split_pane = split_pane

        left_shell = tk.Frame(split_pane, bg=ACCENT_DIM, highlightthickness=0)
        left = tk.Frame(left_shell, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        left.pack(fill="both", expand=True, padx=(3, 0))
        self._build_fields_panel(left)

        right_shell = tk.Frame(split_pane, bg=ACCENT_DIM, highlightthickness=0)
        right = tk.Frame(right_shell, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        right.pack(fill="both", expand=True, padx=(3, 0))
        self._build_photo_panel(right)

        split_pane.add(left_shell, minsize=280, stretch="never")
        split_pane.add(right_shell, minsize=320, stretch="always")
        self.root.after(400, self._place_preview_sash)

    def _place_preview_sash(self) -> None:
        try:
            pane = self._split_pane
            pane.update_idletasks()
            width = pane.winfo_width()
            if width > 400:
                pane.sash_place(0, max(280, int(width * 0.38)), 1)
        except (tk.TclError, AttributeError):
            pass

    def _build_fields_panel(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Cover text",
            font=("Segoe UI Semibold", 12),
            fg=TEXT,
            bg=PANEL,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 0))
        font_row = tk.Frame(parent, bg=PANEL)
        font_row.pack(fill="x", padx=10, pady=(6, 0))
        tk.Label(
            font_row, text="Font", font=("Segoe UI Semibold", 9), fg=MUTED, bg=PANEL
        ).pack(side="left", padx=(4, 8))
        for value, label in (
            (COVER_FONT_CASTELLAR, "Castellar (classic)"),
            (COVER_FONT_HELVETICA, "Helvetica (modern)"),
        ):
            tk.Radiobutton(
                font_row,
                text=label,
                variable=self.book_font_var,
                value=value,
                command=self._on_font_changed,
                bg=PANEL,
                fg=TEXT,
                selectcolor=ENTRY,
                activebackground=PANEL,
                activeforeground=TEXT,
                font=("Segoe UI Semibold", 9),
                highlightthickness=0,
                bd=0,
            ).pack(side="left", padx=(0, 10))
        mode_row = tk.Frame(parent, bg=PANEL)
        mode_row.pack(fill="x", padx=10, pady=(6, 0))
        for value, label in (("standard", "Standard fields"), ("custom", "Custom text")):
            tk.Radiobutton(
                mode_row,
                text=label,
                variable=self.text_mode_var,
                value=value,
                command=self._apply_text_mode,
                bg=PANEL,
                fg=TEXT,
                selectcolor=ENTRY,
                activebackground=PANEL,
                activeforeground=TEXT,
                font=("Segoe UI Semibold", 9),
                highlightthickness=0,
                bd=0,
            ).pack(side="left", padx=(4, 10))
        self.fields_hint = tk.Label(
            parent,
            text="Same fields as Databook Info. Empty fields leave a blank line. Revision is omitted if blank. Turnover Package is always printed.",
            font=("Segoe UI", 8),
            fg=MUTED,
            bg=PANEL,
            anchor="w",
            wraplength=420,
            justify="left",
        )
        self.fields_hint.pack(fill="x", padx=14, pady=(2, 8))
        self._path_row(
            parent,
            "Output folder (Databook)" if self._locked_output else "Output folder",
            self.output_var,
            self._browse_output,
            side="bottom",
        )
        self.text_body = tk.Frame(parent, bg=PANEL)
        self.text_body.pack(fill="both", expand=True)
        self.fields_block = tk.Frame(self.text_body, bg=PANEL)
        for name, label in FIELD_ORDER:
            frame = tk.Frame(self.fields_block, bg=PANEL)
            frame.pack(fill="x", padx=14, pady=(0, 8))
            tk.Label(frame, text=label, font=("Segoe UI Semibold", 9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x")
            entry = self._entry(frame, self.field_vars[name], fill="x", ipady=5)
            entry.bind("<FocusOut>", lambda _e: self._save_settings())
        for var in self.field_vars.values():
            var.trace_add("write", lambda *_args: self._schedule_photo_preview())
        self.custom_block = tk.Frame(self.text_body, bg=PANEL)
        custom_bar = tk.Frame(self.custom_block, bg=PANEL)
        custom_bar.pack(fill="x", padx=14, pady=(0, 6))
        fill_btn = self._secondary_button(custom_bar, "Fill from fields", self._fill_custom_from_fields)
        fill_btn.pack(side="left")
        self._action_buttons.append(fill_btn)
        tk.Label(
            custom_bar,
            text="Job # still names the PDF.",
            font=("Segoe UI", 8),
            fg=MUTED,
            bg=PANEL,
        ).pack(side="left", padx=(10, 0))
        _custom_shell, custom_face = self._inset_panel(
            self.custom_block, fill="both", expand=True, padx=14, pady=(0, 8), face=ENTRY
        )
        self.custom_text = tk.Text(
            custom_face,
            bg=ENTRY,
            fg=TEXT,
            insertbackground=LCD_FG,
            font=("Georgia", 11),
            relief="flat",
            wrap="word",
            height=9,
            padx=8,
            pady=8,
            highlightthickness=0,
            borderwidth=0,
        )
        self.custom_text.pack(fill="both", expand=True)
        self.custom_text.bind("<FocusOut>", lambda _e: self._save_settings())
        self.custom_text.bind("<KeyRelease>", lambda _e: self._schedule_photo_preview())
        job_row = tk.Frame(self.custom_block, bg=PANEL)
        job_row.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(
            job_row,
            text="Job / package # (PDF file name)",
            font=("Segoe UI Semibold", 9),
            fg=MUTED,
            bg=PANEL,
            anchor="w",
        ).pack(fill="x")
        job_entry = self._entry(job_row, self.field_vars["job_number"], fill="x", ipady=5)
        job_entry.bind("<FocusOut>", lambda _e: self._save_settings())
        self.fields_block.pack(fill="x")

    def _build_photo_panel(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=PANEL)
        header.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(
            header,
            text="Cover preview",
            font=("Segoe UI Semibold", 12),
            fg=TEXT,
            bg=PANEL,
            anchor="w",
        ).pack(side="left", padx=(4, 12))
        for value, label in (("photo", "Photo crop"), ("page", "Full page")):
            tk.Radiobutton(
                header,
                text=label,
                variable=self.preview_mode_var,
                value=value,
                command=self._on_preview_mode_changed,
                bg=PANEL,
                fg=TEXT,
                selectcolor=ENTRY,
                activebackground=PANEL,
                activeforeground=TEXT,
                font=("Segoe UI Semibold", 9),
                highlightthickness=0,
                bd=0,
            ).pack(side="left", padx=(0, 8))
        self._path_row(
            parent,
            "Photo or PDF",
            self.photo_var,
            self._browse_photo,
            side="bottom",
            padx=10,
            pady=(4, 8),
            inline=True,
        )
        tools = tk.Frame(parent, bg=PANEL)
        tools.pack(side="bottom", fill="x", padx=10, pady=(0, 4))
        self._secondary_button(tools, "Rotate 90°", self._rotate_photo).pack(side="left")
        self.rotation_label = tk.Label(
            tools, text="0°", font=("Consolas", 9), fg=LCD_FG, bg=PANEL, width=4, anchor="w"
        )
        self.rotation_label.pack(side="left", padx=(6, 8))
        self.pdf_page_row = tk.Frame(tools, bg=PANEL)
        self._secondary_button(self.pdf_page_row, "◀", self._pdf_page_prev).pack(side="left")
        self.pdf_page_label = tk.Label(
            self.pdf_page_row, text="Page 1 / 1", font=("Consolas", 9), fg=LCD_FG, bg=PANEL, anchor="w"
        )
        self.pdf_page_label.pack(side="left", padx=6)
        self._secondary_button(self.pdf_page_row, "▶", self._pdf_page_next).pack(side="left")
        self.zoom_label = tk.Label(
            tools, text="100%", font=("Consolas", 9), fg=LCD_FG, bg=PANEL, width=5, anchor="e"
        )
        self.zoom_label.pack(side="right")
        tk.Label(tools, text="Zoom", font=("Segoe UI Semibold", 9), fg=MUTED, bg=PANEL).pack(side="left")
        self.zoom_var = tk.DoubleVar(value=100.0)
        zoom_shell, zoom_face = self._inset_panel(tools, fill="x", expand=True, autoplace=False, face=ENTRY)
        zoom_shell.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.zoom_scale = tk.Scale(
            zoom_face,
            from_=100,
            to=400,
            orient="horizontal",
            resolution=5,
            showvalue=False,
            variable=self.zoom_var,
            command=self._on_zoom_scale,
            bg=ACCENT,
            fg="#1a1408",
            troughcolor=ACCENT_DIM,
            highlightthickness=0,
            bd=0,
            sliderrelief="raised",
            activebackground=ACCENT,
            length=160,
        )
        self.zoom_scale.pack(fill="x", expand=True, padx=2, pady=1)
        self.zoom_scale.bind("<ButtonRelease-1>", lambda _e: self._save_settings())
        _preview_shell, preview_face = self._inset_panel(
            parent, fill="both", expand=True, padx=10, pady=(0, 4), face="#050403"
        )
        self.photo_canvas = tk.Canvas(
            preview_face, bg="#050403", highlightthickness=0, width=360, height=280, cursor="fleur"
        )
        self.photo_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.photo_canvas.bind("<Configure>", lambda _e: self._schedule_photo_preview())
        self.photo_canvas.bind("<Enter>", lambda _e: self.photo_canvas.focus_set())
        self.photo_canvas.bind("<ButtonPress-1>", self._on_photo_press)
        self.photo_canvas.bind("<B1-Motion>", self._on_photo_drag)
        self.photo_canvas.bind("<ButtonRelease-1>", self._on_photo_release)
        self.photo_canvas.bind("<MouseWheel>", self._on_photo_wheel)
        self.photo_canvas.bind("<Button-4>", self._on_photo_wheel)
        self.photo_canvas.bind("<Button-5>", self._on_photo_wheel)
        self.photo_var.trace_add("write", lambda *_args: self._on_photo_path_changed())

    def _path_row(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        browse: Callable[[], None],
        *,
        inline: bool = False,
        **pack,
    ) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        opts: dict[str, object] = {"fill": "x", "padx": 14, "pady": (8, 12)}
        opts.update(pack)
        frame.pack(**opts)
        caption = tk.Label(frame, text=label, font=("Segoe UI Semibold", 9), fg=MUTED, bg=PANEL, anchor="w")
        line = tk.Frame(frame, bg=PANEL)
        if inline:
            caption.pack(side="left", padx=(0, 8))
            line.pack(side="left", fill="x", expand=True)
        else:
            caption.pack(fill="x")
            line.pack(fill="x", pady=(4, 0))
        entry = tk.Entry(
            line,
            textvariable=variable,
            bg=ENTRY,
            fg=TEXT,
            insertbackground=LCD_FG,
            relief="flat",
            font=("Consolas", 9),
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=4 if inline else 6)
        btn = self._secondary_button(line, "Browse", browse)
        btn.pack(side="left", padx=(8, 0))

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            callback()
        self.root.after(50, self._drain_ui_queue)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in self._action_buttons:
            button.configure(state=state)
        if hasattr(self, "custom_text"):
            self.custom_text.configure(state=state)

    def _custom_text_value(self) -> str:
        if not hasattr(self, "custom_text"):
            return ""
        return self.custom_text.get("1.0", "end-1c").replace("\r\n", "\n").replace("\r", "\n")

    def _fill_custom_from_fields(self, *, log: bool = True) -> None:
        info = CoverInfo(
            client=self.field_vars["client"].get(),
            description=self.field_vars["description"].get(),
            location=self.field_vars["location"].get(),
            tag=self.field_vars["tag"].get(),
            job_number=self.field_vars["job_number"].get(),
            revision=self.field_vars["revision"].get(),
        )
        self.custom_text.delete("1.0", "end")
        self.custom_text.insert("1.0", "\n".join(info.lines()))
        self._save_settings()
        self._schedule_photo_preview()
        if log:
            self._log("Copied the standard field lines into custom text.")

    def _apply_text_mode(self, *, persist: bool = True) -> None:
        custom = self.text_mode_var.get() == "custom"
        if custom:
            self.fields_block.pack_forget()
            if not self._custom_text_value().strip():
                self._fill_custom_from_fields(log=False)
            self.custom_block.pack(fill="both", expand=True)
            self.fields_hint.configure(
                text="Type the cover exactly as it should print. Each Enter is a new line. Long lines wrap in the box."
            )
        else:
            self.custom_block.pack_forget()
            self.fields_block.pack(fill="x")
            self.fields_hint.configure(
                text="Same fields as Databook Info. Empty fields leave a blank line. Revision is omitted if blank. Turnover Package is always printed."
            )
        if persist:
            self._save_settings()
        self._schedule_photo_preview()

    def _apply_project_inputs(self, fields: dict[str, str] | None) -> None:
        output_text = self.output_var.get().strip()
        output = Path(output_text) if output_text else None
        stored = load_cover_inputs(output)
        incoming = overlay_nonempty(load_cover_fields(output), fields_from_env(), fields or {})
        if self._locked_job:
            incoming["job_number"] = self._locked_job
        same_folder = bool(
            output_text
            and self._settings_output
            and Path(output_text).resolve() == Path(self._settings_output).resolve()
        )
        for name, var in self.field_vars.items():
            if incoming.get(name):
                var.set(incoming[name])
            elif output_text and not same_folder:
                var.set("")
        font = incoming.get("font", "").strip()
        if font:
            self.book_font_var.set(normalize_cover_font(font))
        tab = incoming.get("tab_title", "").strip()
        if tab:
            self._tab_title = tab
        photo = stored.get("photo", "").strip()
        if photo:
            self.photo_var.set(photo)
        elif output_text and not same_folder:
            self.photo_var.set("")
        if stored.get("text_mode") == "custom":
            self.text_mode_var.set("custom")
        custom_text = stored.get("custom_text", "")
        if custom_text and hasattr(self, "custom_text"):
            self.custom_text.delete("1.0", "end")
            self.custom_text.insert("1.0", custom_text)
        try:
            if stored.get("photo_zoom"):
                self._photo_zoom = max(1.0, min(4.0, float(stored["photo_zoom"])))
            if stored.get("photo_pan_x"):
                self._photo_pan_x = max(-1.0, min(1.0, float(stored["photo_pan_x"])))
            if stored.get("photo_pan_y"):
                self._photo_pan_y = max(-1.0, min(1.0, float(stored["photo_pan_y"])))
            if stored.get("photo_rotation"):
                self._photo_rotation = normalize_photo_rotation(stored.get("photo_rotation"))
            if stored.get("photo_page"):
                self._photo_page = max(1, int(float(stored["photo_page"])))
        except (TypeError, ValueError):
            pass
        if hasattr(self, "zoom_var"):
            self.zoom_var.set(self._photo_zoom * 100)
            self.zoom_label.configure(text=f"{int(self._photo_zoom * 100)}%")
        if hasattr(self, "rotation_label"):
            self.rotation_label.configure(text=f"{self._photo_rotation}°")
        if stored.get("preview_mode") == "page":
            self.preview_mode_var.set("page")

    def _load_settings(self) -> None:
        path = default_settings_path()
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if data.get("output"):
            self.output_var.set(str(data["output"]))
            self._settings_output = str(data["output"]).strip()
        if data.get("photo"):
            self.photo_var.set(str(data["photo"]))
        try:
            self._photo_zoom = max(1.0, min(4.0, float(data.get("photo_zoom") or 1.0)))
            self._photo_pan_x = max(-1.0, min(1.0, float(data.get("photo_pan_x") or 0.0)))
            self._photo_pan_y = max(-1.0, min(1.0, float(data.get("photo_pan_y") or 0.0)))
            self._photo_rotation = normalize_photo_rotation(data.get("photo_rotation"))
            self._photo_page = max(1, int(data.get("photo_page") or 1))
        except (TypeError, ValueError):
            self._photo_zoom, self._photo_pan_x, self._photo_pan_y, self._photo_rotation, self._photo_page = (
                1.0,
                0.0,
                0.0,
                0,
                1,
            )
        if hasattr(self, "zoom_var"):
            self.zoom_var.set(self._photo_zoom * 100)
            self.zoom_label.configure(text=f"{int(self._photo_zoom * 100)}%")
        if hasattr(self, "rotation_label"):
            self.rotation_label.configure(text=f"{self._photo_rotation}°")
        if data.get("text_mode") == "custom":
            self.text_mode_var.set("custom")
        custom_text = str(data.get("custom_text") or "")
        if custom_text and hasattr(self, "custom_text"):
            self.custom_text.delete("1.0", "end")
            self.custom_text.insert("1.0", custom_text)
        if data.get("font"):
            self.book_font_var.set(normalize_cover_font(data.get("font")))
        for name, var in self.field_vars.items():
            if data.get(name):
                var.set(str(data[name]).strip())
        if data.get("tab_title"):
            self._tab_title = str(data["tab_title"]).strip()
        if data.get("preview_mode") == "page":
            self.preview_mode_var.set("page")
        self._sync_pdf_page_chrome()
        self._apply_preview_mode_chrome()
        if not self._locked_output:
            engine_out = last_engine_suite_output("Cover")
            if engine_out is not None:
                self.output_var.set(str(engine_out))

    def _save_settings(self) -> None:
        path = default_settings_path()
        photo = self.photo_var.get().strip()
        if Path(photo).name.casefold() == "elite_cover_photo.jpg":
            photo = ""
        payload = {
            "output": self.output_var.get().strip(),
            "photo": photo,
            "photo_zoom": self._photo_zoom,
            "photo_pan_x": self._photo_pan_x,
            "photo_pan_y": self._photo_pan_y,
            "photo_rotation": self._photo_rotation,
            "photo_page": self._photo_page,
            "text_mode": self.text_mode_var.get().strip() or "standard",
            "custom_text": self._custom_text_value(),
            "font": normalize_cover_font(self.book_font_var.get()),
            "preview_mode": self.preview_mode_var.get().strip() or "photo",
            "tab_title": self._tab_title,
        }
        for name, var in self.field_vars.items():
            payload[name] = var.get().strip()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        save_cover_inputs(Path(self.output_var.get().strip()) if self.output_var.get().strip() else None, payload)

    def _on_font_changed(self) -> None:
        self._save_settings()
        self._schedule_photo_preview()

    def _preview_is_photo(self) -> bool:
        return self.preview_mode_var.get() != "page"

    def _apply_preview_mode_chrome(self) -> None:
        canvas = getattr(self, "photo_canvas", None)
        if canvas is not None:
            canvas.configure(cursor="fleur" if self._preview_is_photo() else "")

    def _on_preview_mode_changed(self) -> None:
        self._apply_preview_mode_chrome()
        self._refresh_photo_preview()
        self._save_settings()

    def _browse_output(self) -> None:
        if self._locked_output:
            messagebox.showinfo(
                APP_DISPLAY_NAME,
                "Output is the Databook Output Folder.\nChange it on Databook Home, then launch Cover Suite again.",
            )
            return
        path = filedialog.askdirectory(
            title="Select output folder",
            initialdir=picker_start_dir(self.output_var.get().strip()),
        )
        if path:
            self.output_var.set(path)
            self._save_settings()

    def _browse_photo(self) -> None:
        photo = self.photo_var.get().strip()
        if photo and Path(photo).name.casefold() == "elite_cover_photo.jpg":
            photo = ""
        selected = filedialog.askopenfilename(
            title="Choose the circle photo or PDF",
            filetypes=[
                ("Photos and PDFs", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp *.pdf"),
                ("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp"),
                ("PDF", "*.pdf"),
                ("All files", "*.*"),
            ],
            initialdir=picker_start_dir(photo, self.output_var.get().strip()),
        )
        if selected:
            self._photo_page = 1
            self.photo_var.set(selected)
            self._reset_photo_view(log=False)
            self._save_settings()

    def _use_default_photo(self) -> None:
        self.photo_var.set(str(cover_asset("elite_cover_photo.jpg")))
        self._photo_page = 1
        self._reset_photo_view(log=False)
        self._log("Restored the bundled Elite building photo.")

    def _on_photo_path_changed(self) -> None:
        self._sync_pdf_page_chrome()
        self._schedule_photo_preview()

    def _current_photo_path(self) -> Path:
        photo_text = self.photo_var.get().strip()
        source = Path(photo_text) if photo_text else cover_asset("elite_cover_photo.jpg")
        if not source.is_file():
            return cover_asset("elite_cover_photo.jpg")
        return source

    def _sync_pdf_page_chrome(self) -> None:
        row = getattr(self, "pdf_page_row", None)
        if row is None:
            return
        source = self._current_photo_path()
        if not is_cover_pdf(source):
            self._photo_page = 1
            row.pack_forget()
            return
        count = cover_source_page_count(source)
        self._photo_page = normalize_photo_page(self._photo_page, count)
        if not row.winfo_ismapped():
            row.pack(side="left", padx=(12, 0), after=self.rotation_label)
        if hasattr(self, "pdf_page_label"):
            self.pdf_page_label.configure(text=f"Page {self._photo_page} / {count}")

    def _pdf_page_prev(self) -> None:
        self._set_pdf_page(self._photo_page - 1)

    def _pdf_page_next(self) -> None:
        self._set_pdf_page(self._photo_page + 1)

    def _set_pdf_page(self, page: int) -> None:
        source = self._current_photo_path()
        count = cover_source_page_count(source)
        next_page = normalize_photo_page(page, count)
        if next_page == self._photo_page:
            return
        self._photo_page = next_page
        self._sync_pdf_page_chrome()
        self._refresh_photo_preview()
        self._save_settings()
        self._log(f"Cover PDF page {self._photo_page} of {count}.")

    def _reset_photo_view(self, *, log: bool = True) -> None:
        self._photo_zoom = 1.0
        self._photo_pan_x = 0.0
        self._photo_pan_y = 0.0
        self._photo_rotation = 0
        if hasattr(self, "zoom_var"):
            self.zoom_var.set(100)
            self.zoom_label.configure(text="100%")
        if hasattr(self, "rotation_label"):
            self.rotation_label.configure(text="0°")
        self._refresh_photo_preview()
        self._save_settings()
        if log:
            self._log("Reset photo pan, zoom, and rotation.")

    def _rotate_photo(self) -> None:
        self._photo_rotation = normalize_photo_rotation(self._photo_rotation + 90)
        if hasattr(self, "rotation_label"):
            self.rotation_label.configure(text=f"{self._photo_rotation}°")
        self._refresh_photo_preview()
        self._save_settings()
        self._log(f"Photo rotated to {self._photo_rotation}°.")

    def _set_zoom(self, zoom: float, *, from_scale: bool = False) -> None:
        self._photo_zoom = max(1.0, min(4.0, zoom))
        if hasattr(self, "zoom_label"):
            self.zoom_label.configure(text=f"{int(self._photo_zoom * 100)}%")
        if not from_scale and hasattr(self, "zoom_var"):
            self.zoom_var.set(self._photo_zoom * 100)
        self._schedule_photo_preview()

    def _on_zoom_scale(self, value: str) -> None:
        try:
            self._set_zoom(float(value) / 100.0, from_scale=True)
        except ValueError:
            return

    def _on_photo_press(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not self._preview_is_photo():
            return
        self._photo_drag = (event.x, event.y, self._photo_pan_x, self._photo_pan_y)

    def _on_photo_drag(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self._photo_drag is None or not self._preview_is_photo():
            return
        start_x, start_y, pan_x, pan_y = self._photo_drag
        canvas = self.photo_canvas
        span = max(80.0, min(canvas.winfo_width(), canvas.winfo_height()) / 2)
        self._photo_pan_x = max(-1.0, min(1.0, pan_x + (event.x - start_x) / span))
        self._photo_pan_y = max(-1.0, min(1.0, pan_y + (event.y - start_y) / span))
        self._schedule_photo_preview()

    def _on_photo_release(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._photo_drag = None
        self._save_settings()

    def _on_photo_wheel(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not self._preview_is_photo():
            return
        if getattr(event, "num", None) == 4 or (getattr(event, "delta", 0) or 0) > 0:
            steps = 1
        elif getattr(event, "num", None) == 5 or (getattr(event, "delta", 0) or 0) < 0:
            steps = -1
        else:
            return
        self._set_zoom(self._photo_zoom * (1.12 ** steps))
        self._save_settings()

    def _schedule_photo_preview(self) -> None:
        if self._preview_after is not None:
            try:
                self.root.after_cancel(self._preview_after)
            except tk.TclError:
                pass
        delay = 90 if not self._preview_is_photo() else 20
        self._preview_after = self.root.after(delay, self._refresh_photo_preview)

    def _refresh_photo_preview(self) -> None:
        self._preview_after = None
        canvas = getattr(self, "photo_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(int(canvas.winfo_width()), 120)
        height = max(int(canvas.winfo_height()), 120)
        if not self._preview_is_photo():
            composed = compose_full_cover_preview(self._current_info(), width=width, height=height)
        else:
            photo_text = self.photo_var.get().strip()
            source = Path(photo_text) if photo_text else cover_asset("elite_cover_photo.jpg")
            if not source.is_file():
                source = cover_asset("elite_cover_photo.jpg")
            composed = compose_cover_preview(
                source,
                zoom=self._photo_zoom,
                pan_x=self._photo_pan_x,
                pan_y=self._photo_pan_y,
                rotation=self._photo_rotation,
                page=self._photo_page,
                width=width,
                height=height,
            )
        if composed is None:
            canvas.create_text(width / 2, height / 2, text="Could not build preview", fill=MUTED, font=("Segoe UI", 9))
            return
        preview = ImageTk.PhotoImage(composed)
        self._photo_preview = preview
        canvas.create_image(width / 2, height / 2, image=preview)

    def _current_info(self) -> CoverInfo:
        return CoverInfo(
            client=self.field_vars["client"].get(),
            description=self.field_vars["description"].get(),
            location=self.field_vars["location"].get(),
            tag=self.field_vars["tag"].get(),
            job_number=self.field_vars["job_number"].get(),
            revision=self.field_vars["revision"].get(),
            photo_path=self.photo_var.get().strip(),
            photo_zoom=self._photo_zoom,
            photo_pan_x=self._photo_pan_x,
            photo_pan_y=self._photo_pan_y,
            photo_rotation=self._photo_rotation,
            photo_page=self._photo_page,
            use_custom_text=self.text_mode_var.get() == "custom",
            custom_text=self._custom_text_value(),
            font=normalize_cover_font(self.book_font_var.get()),
        )

    def _generate(self) -> None:
        if self._busy:
            return
        output_text = self.output_var.get().strip()
        if not output_text:
            messagebox.showinfo(
                APP_DISPLAY_NAME,
                "Set the output folder first.\nWhen launched from Databook, this is the Databook Output Folder.",
            )
            return
        output_dir = Path(output_text)
        info = self._current_info()
        dest = output_dir / cover_pdf_name(info.job_number)
        self._set_busy(True)
        self.status_var.set("Drawing cover…")
        self._log(f"Generating {dest.name}…")

        def worker() -> None:
            try:
                pdf_path = write_cover_pdf(info, dest)
                handoff_path = write_cover_handoff(
                    output_dir,
                    cover_pdf=pdf_path,
                    tab_title=self._tab_title,
                )
                self._save_settings()

                def done() -> None:
                    self._set_busy(False)
                    self.status_var.set(f"Done - {pdf_path.name}")
                    self._log(f"Cover PDF → {pdf_path}")
                    self._log(f"Databook handoff → {handoff_path}")
                    messagebox.showinfo(
                        APP_DISPLAY_NAME,
                        f"Saved in:\n{output_dir.resolve()}\n\n"
                        f"Created:\n{pdf_path.name}\n{handoff_path.name}\n\n"
                        "Databook will import this as [COVER]. You can also click Import Cover in the Chapter Editor.",
                    )

                self._ui_queue.put(done)
            except Exception as exc:  # noqa: BLE001
                def fail() -> None:
                    self._set_busy(False)
                    self.status_var.set("Generate Cover failed")
                    self._log(f"ERROR: {exc}")
                    messagebox.showerror(APP_DISPLAY_NAME, f"Generate Cover failed:\n{exc}")

                self._ui_queue.put(fail)

        threading.Thread(target=worker, name="cover-generate", daemon=True).start()

    def run(self) -> None:
        self.root.mainloop()


def main(
    output_dir: str | None = None,
    job_number: str | None = None,
    fields: dict[str, str] | None = None,
) -> None:
    CoverGui(output_dir=output_dir, job_number=job_number, fields=fields).run()


if __name__ == "__main__":
    main()
