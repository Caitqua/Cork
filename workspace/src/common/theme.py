from __future__ import annotations

from typing import Dict


def palette(dark: bool) -> Dict[str, str]:
    if not dark:
        return {
            # general
            "bg": "#ffffff",
            "canvas_bg": "#ffffff",
            "text": "#0F172A",
            "subtext": "#334155",
            # panels
            "panel_bg": "#FFFFFF",
            "panel_header_bg": "#F1F5F9",
            "panel_border": "#CBD5E1",
            "muted_box_bg": "#F8FAFC",
            "muted_box_border": "#E2E8F0",
            # dashboard cards
            "card1": "#E0F7FA",
            "card2": "#FFF3E0",
            # board
            "board_bg": "#fbfbfb",
            "node_fill": "#F1F5F9",
            "node_fill_active": "#E3F2FD",
            "node_border": "#94A3B8",
            "edge": "#9CA3AF",
        }
    # dark
    return {
        "bg": "#0B1220",
        "canvas_bg": "#0B1220",
        "text": "#E5E7EB",
        "subtext": "#CBD5E1",
        "panel_bg": "#111827",
        "panel_header_bg": "#1F2937",
        "panel_border": "#374151",
        "muted_box_bg": "#0F172A",
        "muted_box_border": "#374151",
        "card1": "#0E7490",
        "card2": "#92400E",
        "board_bg": "#0B1220",
        "node_fill": "#111827",
        "node_fill_active": "#0E7490",
        "node_border": "#374151",
        "edge": "#6B7280",
    }

