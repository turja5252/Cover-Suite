# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Hover-glow buttons: lit border on mouse-over, launch chips stay distinct."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

TONES: dict[str, dict[str, object]] = {
    "normal": {
        "edge": "#4a3c20",
        "fill": "#2c2410",
        "text": "#f5ead0",
        "hover_fill": "#433618",
        "hover_edge": "#f0c674",
        "stripe": None,
    },
    "accent": {
        "edge": "#f0c674",
        "fill": "#c9a227",
        "text": "#1a1408",
        "hover_fill": "#e0b84a",
        "hover_edge": "#ffe08a",
        "stripe": None,
    },
    "launch": {
        "edge": "#f0c674",
        "fill": "#2c2410",
        "text": "#ffe8a3",
        "hover_fill": "#433618",
        "hover_edge": "#ffe08a",
        "stripe": "#f0c674",
    },
    "assign": {
        "edge": "#f0c674",
        "fill": "#2c2410",
        "text": "#ffe8a3",
        "hover_fill": "#433618",
        "hover_edge": "#ffe08a",
        "stripe": "#f0c674",
    },
    "danger": {
        "edge": "#6e2220",
        "fill": "#3c1a1a",
        "text": "#f85149",
        "hover_fill": "#6e2220",
        "hover_edge": "#ff7b72",
        "stripe": None,
    },
}


def _inside(shell: tk.Misc, widget: tk.Misc | None) -> bool:
    current = widget
    while current is not None:
        if current == shell:
            return True
        current = getattr(current, "master", None)
    return False


def styled_button(
    parent: tk.Widget,
    text: str,
    command: object,
    *,
    tone: str = "normal",
    font: tuple[str, int] | tuple[str, int, str] = ("Segoe UI", 10),
    padx: int = 10,
    pady: int = 6,
    stripe: bool | None = None,
    fill: str | None = None,
    text_color: str | None = None,
    hover_fill: str | None = None,
    hover_edge: str | None = None,
    edge: str | None = None,
    width: int | None = None,
) -> tk.Button:
    """Button with a glow border. Pack/grid/place the returned button (shell follows).

    ``launch`` and ``assign`` keep a colored stripe so app-launch actions stand out.
    """
    pal = dict(TONES.get(tone, TONES["normal"]))
    if fill:
        pal["fill"] = fill
    if text_color:
        pal["text"] = text_color
    if hover_fill:
        pal["hover_fill"] = hover_fill
    if hover_edge:
        pal["hover_edge"] = hover_edge
    if edge:
        pal["edge"] = edge
    use_stripe = pal.get("stripe") if stripe is None else (pal.get("stripe") if stripe else None)

    shell = tk.Frame(parent, bg=str(pal["edge"]), highlightthickness=0)
    inner = tk.Frame(shell, bg=str(pal["fill"]))
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    stripe_bar = None
    if use_stripe:
        stripe_bar = tk.Frame(inner, bg=str(use_stripe), width=4)
        stripe_bar.pack(side="left", fill="y")
        stripe_bar.pack_propagate(False)
    button = tk.Button(
        inner,
        text=text,
        command=command,
        font=font,
        bg=str(pal["fill"]),
        fg=str(pal["text"]),
        activebackground=str(pal["hover_fill"]),
        activeforeground="#ffffff",
        relief="flat",
        bd=0,
        padx=padx,
        pady=pady,
        cursor="hand2",
        highlightthickness=0,
        width=width or 0,
    )
    button.pack(side="left", fill="both", expand=True)

    idle_edge = str(pal["edge"])
    idle_fill = str(pal["fill"])
    lit_edge = str(pal["hover_edge"])
    lit_fill = str(pal["hover_fill"])
    original_configure = button.configure

    def _idle() -> None:
        shell.configure(bg=idle_edge)
        inner.configure(bg=idle_fill)
        original_configure(bg=idle_fill)

    def enter(_event: object | None = None) -> None:
        if str(button.cget("state")) == "disabled":
            return
        shell.configure(bg=lit_edge)
        inner.configure(bg=lit_fill)
        original_configure(bg=lit_fill)

    def leave(event: tk.Event) -> None:  # type: ignore[type-arg]
        try:
            dest = event.widget.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            dest = None
        if _inside(shell, dest):
            return
        _idle()

    targets: list[tk.Misc] = [shell, inner, button]
    if stripe_bar is not None:
        targets.append(stripe_bar)
    for widget in targets:
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def pack(**kwargs: object) -> None:
        shell.pack(**kwargs)

    def grid(**kwargs: object) -> None:
        shell.grid(**kwargs)

    def place(**kwargs: object) -> None:
        shell.place(**kwargs)

    def configure(*args: object, **kwargs: object) -> object:
        result = original_configure(*args, **kwargs)
        state = kwargs.get("state")
        if state == "disabled":
            _idle()
        return result

    button.pack = pack  # type: ignore[method-assign]
    button.grid = grid  # type: ignore[method-assign]
    button.place = place  # type: ignore[method-assign]
    button.pack_forget = shell.pack_forget  # type: ignore[method-assign]
    button.grid_forget = shell.grid_forget  # type: ignore[method-assign]
    button.configure = configure  # type: ignore[method-assign]
    button.config = configure  # type: ignore[method-assign]
    return button


def make_flare_button(
    parent: tk.Widget,
    text: str,
    command: Callable[[], None],
    *,
    tone: str = "fwm",
    padx: int = 12,
    pady: int = 6,
    font: tuple[str, int] | tuple[str, int, str] = ("Segoe UI Semibold", 10),
) -> tk.Button:
    mapped = {"fwm": "launch", "assign": "assign"}.get(tone, tone)
    return styled_button(parent, text, command, tone=mapped, padx=padx, pady=pady, font=font)
