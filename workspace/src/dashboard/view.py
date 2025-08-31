from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser  # keep cbai2.py style imports

from src.common.models import AppState
from src.dashboard.service import overview


class DashboardCanvas(ttk.Frame):
    def __init__(self, master, get_state, on_select_case=None, on_new_case=None, on_edit_case=None, on_archive_case=None, on_delete_case=None, on_unarchive_case=None):
        super().__init__(master)
        self.get_state = get_state
        self.on_select_case = on_select_case
        self.on_new_case = on_new_case
        self.on_edit_case = on_edit_case
        self.on_archive_case = on_archive_case
        self.on_delete_case = on_delete_case
        self.on_unarchive_case = on_unarchive_case
        self.canvas = tk.Canvas(self, bg="#ffffff")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.refresh())
        self._latest_item_bounds = []  # list of (bbox, case_id)
        self._case_item_bounds = []    # list of (bbox, action, case_id)
        self._arch_item_bounds = []    # archived list actions
        self._selected_case_id: str | None = None
        self._show_archived: bool = False

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

    def _card(self, x, y, w, h, title, value, fill="#F1F5F9"):
        r = 12
        self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill, outline="#CBD5E1", width=1)
        self.canvas.create_text(x + 12, y + 14, text=title, anchor="w", font=("Segoe UI", 10, "bold"))
        self.canvas.create_text(x + 12, y + h / 2 + 6, text=str(value), anchor="w", font=("Segoe UI", 28, "bold"))

    def refresh(self):
        from src.common.theme import palette

        self.canvas.delete("all")
        state: AppState = self.get_state()
        pal = palette(getattr(state, "dark_mode", False))
        try:
            self.canvas.configure(bg=pal["canvas_bg"])
        except Exception:
            pass
        data = overview(state)
        w = self.canvas.winfo_width() or 800
        padding = 16
        card_w, card_h = (w - padding * 3) / 2, 120
        self._card(padding, padding, card_w, card_h, "Active Cases", data["active_cases"], fill=pal["card1"])
        self._card(padding * 2 + card_w, padding, card_w, card_h, "Archived Cases", data["archived_cases"], fill=pal["card2"])

        # Active cases list area, styled like Latest Evidence
        y0 = padding * 2 + card_h
        self._case_item_bounds = []
        # Draw header with bg bar sized to text (like Latest Evidence)
        header_text_id = self.canvas.create_text(padding, y0, text="Active Cases", anchor="nw", font=("Segoe UI", 12, "bold"), fill=pal["text"]) 
        tx1, ty1, tx2, ty2 = self.canvas.bbox(header_text_id)
        text_h = (ty2 - ty1) if (tx1 is not None) else 20
        header_pad = 8
        header_bottom = y0 + text_h + header_pad
        header_bg_id = self.canvas.create_rectangle(padding - 2, y0 - 2, w - padding + 2, header_bottom, fill=pal["panel_header_bg"], outline="")
        try:
            self.canvas.tag_lower(header_bg_id, header_text_id)
        except Exception:
            pass
        # New Case button aligned within header row area
        # Increase padding/size for header buttons
        btn_w, btn_h = 130, 30
        new_x2 = w - padding
        new_x1 = new_x2 - btn_w
        new_y1 = y0
        new_y2 = y0 + btn_h
        # add Archived button to the left of New
        arch_x2 = new_x1 - 8
        arch_x1 = arch_x2 - btn_w
        arch_y1 = new_y1
        arch_y2 = new_y2
        # themed button colors
        dark = (pal["bg"].startswith("#0") or pal["bg"].lower() != "#ffffff")
        def btn_fill(kind: str) -> str:
            if not dark:
                return {"new": "#DCFCE7", "arch": "#DBEAFE", "edit": "#DBEAFE", "archive": "#FEF9C3", "delete": "#FEE2E2"}.get(kind, pal["panel_header_bg"])
            return {"new": "#166534", "arch": "#1D4ED8", "edit": "#1D4ED8", "archive": "#854D0E", "delete": "#7F1D1D"}.get(kind, pal["panel_header_bg"])

        self.canvas.create_rectangle(new_x1, new_y1, new_x2, new_y2, fill=btn_fill("new"), outline=pal["panel_border"]) 
        self.canvas.create_text((new_x1 + new_x2)//2, new_y1 + btn_h//2, text="New Case", font=("Segoe UI", 11, "bold"))
        self._case_item_bounds.append(((new_x1, new_y1, new_x2, new_y2), "new", None))

        self.canvas.create_rectangle(arch_x1, arch_y1, arch_x2, arch_y2, fill=btn_fill("arch"), outline=pal["panel_border"]) 
        self.canvas.create_text((arch_x1 + arch_x2)//2, arch_y1 + btn_h//2, text="Archived", font=("Segoe UI", 11, "bold"))
        self._case_item_bounds.append(((arch_x1, arch_y1, arch_x2, arch_y2), "toggle_archived", None))

        row_y = header_bottom + 6
        row_h = 28
        active_cases = [c for c in state.cases if not c.archived]
        for c in active_cases:
            bbox = (padding, row_y, w - padding, row_y + row_h)
            fill = pal["muted_box_bg"] if c.id != self._selected_case_id else pal["card2"]
            self.canvas.create_rectangle(*bbox, fill=fill, outline=pal["muted_box_border"]) 
            self.canvas.create_text(padding + 8, row_y + row_h/2, text=c.name, anchor="w", fill=pal["text"], font=("Segoe UI", 10, "bold"))
            # action buttons on right
            actions = [("Edit", "edit"), ("Archive", "archive"), ("Delete", "delete")]
            ax = w - padding - 8
            for label, action in reversed(actions):
                # Wider buttons for more internal padding
                if action == "edit":
                    tw = 70
                elif action == "archive":
                    tw = 110
                else:
                    tw = 110
                ax1 = ax - tw
                # Slightly taller buttons (more vertical padding)
                ay1 = row_y + 1
                ax2 = ax
                ay2 = row_y + row_h - 1
                self.canvas.create_rectangle(ax1, ay1, ax2, ay2, fill=btn_fill(action), outline=pal["panel_border"]) 
                self.canvas.create_text((ax1+ax2)//2, (ay1+ay2)//2, text=label, font=("Segoe UI", 9))
                self._case_item_bounds.append(((ax1, ay1, ax2, ay2), action, c.id))
                # Increase gap between adjacent buttons
                ax = ax1 - 12
            # make row clickable to open case
            self._case_item_bounds.append((bbox, "open", c.id))
            row_y += row_h + 4

        # Archived list toggle
        arch_row_start = row_y
        self._arch_item_bounds = []
        if self._show_archived:
            # header
            ay0 = row_y + 4
            arch_text_id = self.canvas.create_text(padding, ay0, text="Archived Cases", anchor="nw", font=("Segoe UI", 12, "bold"), fill=pal["text"]) 
            atx1, aty1, atx2, aty2 = self.canvas.bbox(arch_text_id)
            atext_h = (aty2 - aty1) if (atx1 is not None) else 20
            abottom = ay0 + atext_h + 8
            arch_bg_id = self.canvas.create_rectangle(padding - 2, ay0 - 2, w - padding + 2, abottom, fill=pal["panel_header_bg"], outline="")
            try:
                self.canvas.tag_lower(arch_bg_id, arch_text_id)
            except Exception:
                pass
            row_y = abottom + 6
            for c in [c for c in state.cases if c.archived]:
                bbox = (padding, row_y, w - padding, row_y + row_h)
                fill = pal["muted_box_bg"] if c.id != self._selected_case_id else pal["card2"]
                self.canvas.create_rectangle(*bbox, fill=fill, outline=pal["muted_box_border"]) 
                self.canvas.create_text(padding + 8, row_y + row_h/2, text=c.name, anchor="w", fill=pal["text"], font=("Segoe UI", 10, "bold"))
                # actions: View | Unarchive
                actions = [("View", "open"), ("Unarchive", "unarchive")]
                ax = w - padding - 8
                for label, action in reversed(actions):
                    tw = 120 if action == "unarchive" else 80
                    ax1 = ax - tw
                    ay1 = row_y + 2
                    ax2 = ax
                    ay2 = row_y + row_h - 2
                    self.canvas.create_rectangle(ax1, ay1, ax2, ay2, fill=btn_fill("arch"), outline=pal["panel_border"]) 
                    self.canvas.create_text((ax1+ax2)//2, (ay1+ay2)//2, text=label, font=("Segoe UI", 10))
                    self._arch_item_bounds.append(((ax1, ay1, ax2, ay2), action, c.id))
                    ax = ax1 - 12
                self._arch_item_bounds.append((bbox, "open", c.id))
                row_y += row_h + 4

        # Latest evidence list area with padding below header
        y0 = row_y + padding
        # Draw header text first to measure actual height, then draw bg and lower it
        header_text_id = self.canvas.create_text(
            padding, y0, text="Latest Evidence", anchor="nw", font=("Segoe UI", 12, "bold"), fill=pal["text"]
        )
        tx1, ty1, tx2, ty2 = self.canvas.bbox(header_text_id)
        text_h = (ty2 - ty1) if (tx1 is not None) else 20
        header_pad = 8  # vertical padding to better match font height
        header_bottom = y0 + text_h + header_pad
        header_bg_id = self.canvas.create_rectangle(
            padding - 2, y0 - 2, w - padding + 2, header_bottom, fill=pal["panel_header_bg"], outline=""
        )
        # Ensure background sits behind the header text
        try:
            self.canvas.tag_lower(header_bg_id, header_text_id)
        except Exception:
            pass

        # Leave comfortable space before first row
        row_y = header_bottom + 6
        row_h = 28
        self._latest_item_bounds = []
        for item in data["latest_evidence"]:
            text = f"[{item['type']}] {item['title']} — {item['case_name']}"
            bbox = (padding, row_y, w - padding, row_y + row_h)
            self.canvas.create_rectangle(*bbox, fill=pal["muted_box_bg"], outline=pal["muted_box_border"])
            self.canvas.create_text(padding + 8, row_y + row_h / 2, text=text, anchor="w", fill=pal["subtext"]) 
            self._latest_item_bounds.append((bbox, item["case_id"]))
            row_y += row_h + 4

        # Small bottom margin after the list block
        self.canvas.create_rectangle(padding, row_y, w - padding, row_y + 4, fill=pal["canvas_bg"], outline="")

    def _on_click(self, event):
        x, y = event.x, event.y
        # case actions: prioritize buttons (non-open) before row open areas
        for (x1, y1, x2, y2), action, cid in self._case_item_bounds:
            if action == "open":
                continue
            if x1 <= x <= x2 and y1 <= y <= y2:
                if action == "new" and self.on_new_case:
                    self.on_new_case()
                    return
                if action == "toggle_archived":
                    self._show_archived = not self._show_archived
                    self.refresh()
                    return
                if action == "edit" and self.on_edit_case and cid:
                    self.on_edit_case(cid)
                    return
                if action == "archive" and self.on_archive_case and cid:
                    self.on_archive_case(cid)
                    return
                if action == "delete" and self.on_delete_case and cid:
                    self.on_delete_case(cid)
                    return
        # row open areas (after buttons)
        for (x1, y1, x2, y2), action, cid in self._case_item_bounds:
            if action != "open":
                continue
            if x1 <= x <= x2 and y1 <= y <= y2:
                if self.on_select_case and cid:
                    # single click selects, double click will open
                    self._selected_case_id = cid
                    self.refresh()
                    return
        # archived actions
        for (x1, y1, x2, y2), action, cid in self._arch_item_bounds:
            if x1 <= x <= x2 and y1 <= y <= y2:
                if action == "unarchive" and self.on_unarchive_case and cid:
                    self.on_unarchive_case(cid)
                    return
                if action == "open" and self.on_select_case and cid:
                    # single click selects, double click opens
                    self._selected_case_id = cid
                    self.refresh()
                    return
        # evidence rows -> open case
        if not self.on_select_case:
            return
        for (x1, y1, x2, y2), case_id in self._latest_item_bounds:
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.on_select_case(case_id)
                break

    def _on_double_click(self, event):
        x, y = event.x, event.y
        # double click on active case row opens
        for (x1, y1, x2, y2), action, cid in self._case_item_bounds:
            if action == "open" and x1 <= x <= x2 and y1 <= y <= y2:
                if self.on_select_case and cid:
                    self.on_select_case(cid)
                return
        # double click on archived case row opens
        for (x1, y1, x2, y2), action, cid in self._arch_item_bounds:
            if action == "open" and x1 <= x <= x2 and y1 <= y <= y2:
                if self.on_select_case and cid:
                    self.on_select_case(cid)
                return
