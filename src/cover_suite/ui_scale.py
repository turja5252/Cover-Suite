# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Shared UI text-size preference for Engine, Cover Suite, and WELD Suite.

Large is +2pt on screen fonts only. Cover/TOC/matrix print fonts stay as they are.
Keep this file in sync across the three apps.
"""
from __future__ import annotations

import json
import os
import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk
from collections.abc import Callable
from pathlib import Path

APP_FOLDER = "EliteIntegrity"
FILENAME = "suite-ui.json"
MODE_NORMAL = "normal"
MODE_LARGE = "large"
LARGE_OFFSET = 2
TTK_STYLE_NAMES = (
    "Review.Treeview",
    "Review.Treeview.Heading",
    "Packet.Treeview",
    "Packet.Treeview.Heading",
    "Proc.Treeview",
    "Proc.Treeview.Heading",
)

_creation_offset = 0
_named_applied = 0
_installed = False
_originals: dict[type, dict[str, Callable]] = {}


def ui_prefs_path() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / APP_FOLDER / FILENAME


def normalize_ui_scale(value: object) -> str:
    text = str(value or "").strip().casefold()
    if text in ("normal", "small", "off", "0"):
        return MODE_NORMAL
    return MODE_LARGE


def load_ui_scale() -> str:
    path = ui_prefs_path()
    if not path.is_file():
        return MODE_LARGE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return MODE_LARGE
    if not isinstance(raw, dict):
        return MODE_LARGE
    return normalize_ui_scale(raw.get("font_size") or raw.get("ui_scale"))


def save_ui_scale(mode: str) -> None:
    mode = normalize_ui_scale(mode)
    path = ui_prefs_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"font_size": mode}, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def ui_offset(mode: str | None = None) -> int:
    chosen = normalize_ui_scale(mode) if mode is not None else (
        MODE_LARGE if _creation_offset else load_ui_scale()
    )
    if mode is None and _installed:
        return _creation_offset
    return LARGE_OFFSET if chosen == MODE_LARGE else 0


def scale_font(spec: object, *, offset: int | None = None) -> object:
    """Add points to a Tk font spec. ``offset=None`` uses the live UI setting."""
    off = _creation_offset if offset is None else int(offset)
    if not off or spec is None:
        return spec
    if isinstance(spec, (tuple, list)) and len(spec) >= 2:
        try:
            size = int(spec[1])
        except (TypeError, ValueError):
            return spec
        bumped = list(spec)
        if size < 0:
            bumped[1] = size - off
        else:
            bumped[1] = max(1, size + off)
        return tuple(bumped)
    if isinstance(spec, str) and spec.startswith("Tk"):
        return spec
    try:
        font = spec if isinstance(spec, tkfont.Font) else tkfont.Font(font=spec)
        size = int(font.cget("size"))
        if size < 0:
            size = size - off
        else:
            size = max(1, abs(size) + off)
        weight = str(font.cget("weight") or "normal")
        slant = str(font.cget("slant") or "roman")
        extra: list[str] = []
        if weight.casefold() == "bold":
            extra.append("bold")
        if slant.casefold() == "italic":
            extra.append("italic")
        return (str(font.cget("family")), size, *extra)
    except (tk.TclError, TypeError, ValueError):
        return spec


def ui_font(*parts: object) -> tuple:
    """Designed UI font, with the current size offset applied."""
    scaled = scale_font(parts)
    return tuple(scaled) if isinstance(scaled, tuple) else parts


def ui_rowheight(designed: int, *, offset: int | None = None) -> int:
    off = _creation_offset if offset is None else int(offset)
    return max(16, int(designed) + off * 2)


def _patch_init(cls: type) -> None:
    original_init = cls.__init__
    original_configure = cls.configure

    def __init__(self, *args: object, **kwargs: object) -> None:
        args, kwargs = _scale_font_args(args, kwargs)
        original_init(self, *args, **kwargs)

    def configure(self, *args: object, **kwargs: object) -> object:
        args, kwargs = _scale_font_args(args, kwargs)
        return original_configure(self, *args, **kwargs)

    cls.__init__ = __init__  # type: ignore[method-assign]
    cls.configure = configure  # type: ignore[method-assign]
    cls.config = configure  # type: ignore[method-assign]
    _originals[cls] = {"init": original_init, "configure": original_configure}


def _scale_font_args(args: tuple, kwargs: dict) -> tuple[tuple, dict]:
    kwargs = dict(kwargs)
    if "font" in kwargs:
        kwargs["font"] = scale_font(kwargs["font"])
    if args and isinstance(args[0], dict) and "font" in args[0]:
        payload = dict(args[0])
        payload["font"] = scale_font(payload["font"])
        args = (payload, *args[1:])
    return args, kwargs


def _patch_canvas() -> None:
    original = tk.Canvas.create_text

    def create_text(self, *args: object, **kwargs: object):
        if "font" in kwargs:
            kwargs = dict(kwargs)
            kwargs["font"] = scale_font(kwargs["font"])
        return original(self, *args, **kwargs)

    tk.Canvas.create_text = create_text  # type: ignore[method-assign]
    _originals[tk.Canvas] = {"create_text": original}


def _bump_named_fonts(delta: int) -> None:
    if not delta:
        return
    for name in (
        "TkDefaultFont",
        "TkTextFont",
        "TkFixedFont",
        "TkMenuFont",
        "TkHeadingFont",
        "TkCaptionFont",
        "TkSmallCaptionFont",
        "TkIconFont",
        "TkTooltipFont",
    ):
        try:
            font = tkfont.nametofont(name)
            size = int(font.cget("size") or 0)
            if size < 0:
                font.configure(size=size - delta)
            elif size:
                font.configure(size=max(1, size + delta))
        except tk.TclError:
            continue


def _bump_one_font(widget: tk.Misc, delta: int) -> None:
    originals = _originals.get(type(widget))
    configure = originals["configure"] if originals and "configure" in originals else None
    try:
        current = widget.cget("font")
    except tk.TclError:
        return
    if not current:
        return
    if isinstance(current, str) and current.startswith("Tk"):
        return
    bumped = scale_font(current, offset=delta)
    if bumped is None or bumped == current:
        return
    try:
        if configure is not None:
            configure(widget, font=bumped)
        else:
            widget.configure(font=bumped)
    except tk.TclError:
        pass


def _bump_canvas_text(widget: tk.Canvas, delta: int) -> None:
    original = _originals.get(tk.Canvas, {}).get("create_text")
    try:
        items = widget.find_all()
    except tk.TclError:
        return
    for item in items:
        try:
            if widget.type(item) != "text":
                continue
            current = widget.itemcget(item, "font")
            bumped = scale_font(current, offset=delta)
            if bumped is None or bumped == current:
                continue
            widget.itemconfigure(item, font=bumped)
        except tk.TclError:
            continue
    del original


def _bump_ttk_styles(root: tk.Misc, delta: int) -> None:
    try:
        style = ttk.Style(root)
    except tk.TclError:
        return
    for name in TTK_STYLE_NAMES:
        try:
            current = style.configure(name) or {}
        except tk.TclError:
            continue
        updates: dict[str, object] = {}
        if current.get("font"):
            updates["font"] = scale_font(current.get("font"), offset=delta)
        if current.get("rowheight"):
            try:
                updates["rowheight"] = max(16, int(current.get("rowheight")) + delta * 2)
            except (TypeError, ValueError):
                pass
        if updates:
            try:
                style.configure(name, **updates)
            except tk.TclError:
                continue


def bump_widget_tree(root: tk.Misc, delta: int) -> None:
    if not delta:
        return
    stack = [root]
    while stack:
        widget = stack.pop()
        _bump_one_font(widget, delta)
        if isinstance(widget, tk.Canvas):
            _bump_canvas_text(widget, delta)
        try:
            stack.extend(widget.winfo_children())
        except tk.TclError:
            continue
    _bump_ttk_styles(root, delta)


def install_ui_scaling(root: tk.Misc) -> None:
    """Call once right after Tk() so every later widget picks up the saved size."""
    global _creation_offset, _installed, _named_applied
    _creation_offset = LARGE_OFFSET if load_ui_scale() == MODE_LARGE else 0
    if not _installed:
        for cls in (
            tk.Label,
            tk.Button,
            tk.Entry,
            tk.Text,
            tk.Listbox,
            tk.Radiobutton,
            tk.Checkbutton,
            tk.Message,
            tk.Scale,
            tk.Menubutton,
        ):
            _patch_init(cls)
        _patch_canvas()
        _installed = True
    delta = _creation_offset - _named_applied
    _bump_named_fonts(delta)
    _named_applied = _creation_offset
    try:
        root.tk.call("tk", "scaling")
    except tk.TclError:
        pass


def set_ui_scale(mode: str, root: tk.Misc | None = None) -> str:
    """Save Normal/Large and restyle the open window immediately."""
    global _creation_offset, _named_applied
    mode = normalize_ui_scale(mode)
    target = LARGE_OFFSET if mode == MODE_LARGE else 0
    delta = target - _creation_offset
    save_ui_scale(mode)
    _creation_offset = target
    if delta and root is not None:
        bump_widget_tree(root, delta)
        _bump_named_fonts(delta)
        _named_applied = target
    elif not delta:
        _named_applied = target
    return mode


def pack_font_size_toggle(
    parent: tk.Widget,
    *,
    bg: str,
    fg: str,
    muted: str,
    selectcolor: str,
    on_change: Callable[[str], None] | None = None,
) -> tk.StringVar:
    """Normal / Large radios. Packs into ``parent``."""
    var = tk.StringVar(value=load_ui_scale())
    host = tk.Frame(parent, bg=bg)
    host.pack(side="right", padx=(0, 12), pady=(4, 0))
    tk.Label(host, text="Text", font=("Segoe UI Semibold", 8), fg=muted, bg=bg).pack(
        side="left", padx=(0, 6)
    )
    def apply() -> None:
        mode = set_ui_scale(var.get(), parent.winfo_toplevel())
        if on_change is not None:
            on_change(mode)

    for value, label in ((MODE_NORMAL, "Normal"), (MODE_LARGE, "Large")):
        tk.Radiobutton(
            host,
            text=label,
            value=value,
            variable=var,
            command=apply,
            bg=bg,
            fg=fg,
            selectcolor=selectcolor,
            activebackground=bg,
            activeforeground=fg,
            font=("Segoe UI", 8),
            highlightthickness=0,
            bd=0,
        ).pack(side="left", padx=(0, 4))
    return var
