"""Shared Plotly chart helpers — consistent theming across all KoNotes views."""
from __future__ import annotations

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Color palette — vibrant, high-contrast Garmin-inspired colors
# ---------------------------------------------------------------------------
BLUE = "#3b82f6"
BLUE_LIGHT = "#60a5fa"
BLUE_DARK = "#2563eb"
GREEN = "#22c55e"
GREEN_DARK = "#16a34a"
AMBER = "#f59e0b"
AMBER_LIGHT = "#fbbf24"
PURPLE = "#a855f7"
PURPLE_DARK = "#7c3aed"
ROSE = "#f43f5e"
ROSE_LIGHT = "#fb7185"
CYAN = "#06b6d4"
TEAL = "#14b8a6"
GRAY = "#64748b"
GRAY_LIGHT = "#94a3b8"
WHITE = "#e2e8f0"

PALETTE = [BLUE, GREEN, AMBER, PURPLE, ROSE, CYAN, TEAL, ROSE_LIGHT, BLUE_LIGHT, AMBER_LIGHT]

# Gradients for bar charts
BLUE_GRADIENT = [[0, "rgba(59,130,246,0.2)"], [1, BLUE]]
GREEN_GRADIENT = [[0, "rgba(34,197,94,0.2)"], [1, GREEN]]
AMBER_GRADIENT = [[0, "rgba(245,158,11,0.2)"], [1, AMBER]]
PURPLE_GRADIENT = [[0, "rgba(168,85,247,0.2)"], [1, PURPLE]]

# ---------------------------------------------------------------------------
# Chart layout defaults
# ---------------------------------------------------------------------------
_FONT = dict(family="system-ui, -apple-system, sans-serif", color="#94a3b8")

_COMMON_LAYOUT = dict(
    font=_FONT,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=30, b=0),
    hoverlabel=dict(
        bgcolor="#1e293b",
        font_size=13,
        font_family="system-ui, -apple-system, sans-serif",
        font_color="#e2e8f0",
        bordercolor="rgba(0,0,0,0)",
    ),
    showlegend=False,
)


def base_layout(**overrides) -> dict:
    """Return a copy of the common layout dict with optional overrides."""
    layout = {**_COMMON_LAYOUT}
    layout.update(overrides)
    return layout


def styled_axis(
    show_grid: bool = True,
    show_line: bool = False,
    **kwargs,
) -> dict:
    """Return an axis config dict for the KoNotes theme."""
    axis = dict(
        showgrid=show_grid,
        gridcolor="rgba(148,163,184,0.08)",
        gridwidth=1,
        zeroline=False,
        showline=show_line,
        linecolor="rgba(148,163,184,0.15)",
        tickfont=dict(size=11, color="#94a3b8"),
    )
    axis.update(kwargs)
    return axis


def figure(
    data: list,
    title: str = "",
    height: int = 300,
    xaxis: dict | None = None,
    yaxis: dict | None = None,
    **layout_kw,
) -> go.Figure:
    """Build a consistently styled Plotly Figure."""
    extra: dict = {}
    if title:
        extra["title"] = dict(
            text=title, font=dict(size=14, color="#cbd5e1"), x=0, xanchor="left"
        )
    layout = base_layout(
        height=height,
        xaxis=xaxis or styled_axis(),
        yaxis=yaxis or styled_axis(),
        **extra,
        **layout_kw,
    )
    return go.Figure(data=data, layout=layout)
