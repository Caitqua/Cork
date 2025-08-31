from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from tkinter import filedialog, messagebox, simpledialog, colorchooser  # keep parity with cbai2

from src.common.storage import load_state, save_state, DEFAULT_DATA_PATH
from src.dashboard.view import DashboardCanvas
from src.board.view import BoardCanvas
from src.cases.file_view import CaseFileCanvas
from src.cases.service import create_case
from src.common.theme import palette


class App(tk.Tk):
    def __init__(self, data_path: str | None = None):
        super().__init__()
        self.title("Case Toolkit — MVP")
        self.geometry("1100x720")

        self.data_path = data_path or DEFAULT_DATA_PATH
        self.state_obj = load_state(self.data_path)
        if not self.state_obj.cases:
            self.state_obj.cases.append(create_case("First Case"))
        self.current_case_id = self.state_obj.cases[0].id

        self._build_toolbar()
        self._build_tabs()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # plumbing
    def get_state(self):
        return self.state_obj

    def set_state(self, new_state):
        self.state_obj = new_state
        save_state(self.state_obj, self.data_path)
        self._sync_case_combo()
        self.refresh_all()

    def _sync_case_combo(self):
        # Display only case names (deduplicated), keep a mapping to ids
        self._case_display_to_id = {}
        self._case_id_to_display = {}
        name_counts = {}
        for c in self.state_obj.cases:
            name_counts[c.name] = name_counts.get(c.name, 0) + 1
        values: list[str] = []
        for c in self.state_obj.cases:
            disp = c.name
            if name_counts.get(c.name, 0) > 1:
                # disambiguate duplicates by appending short id
                disp = f"{c.name} ({c.id.split('_')[-1]})"
            self._case_display_to_id[disp] = c.id
            self._case_id_to_display[c.id] = disp
            values.append(disp)
        self.case_combo["values"] = values
        # set current selection
        cur_disp = self._case_id_to_display.get(self.current_case_id)
        if cur_disp:
            self.case_combo.set(cur_disp)

    # UI
    def _build_toolbar(self):
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Case:").pack(side=tk.LEFT, padx=(8, 4), pady=6)
        self.case_combo = ttk.Combobox(bar, state="readonly", width=50)
        self.case_combo.pack(side=tk.LEFT)
        self.case_combo.bind("<<ComboboxSelected>>", self._on_case_combo)
        ttk.Button(bar, text="New Case", command=self._new_case).pack(side=tk.LEFT, padx=8)
        ttk.Button(bar, text="Save", command=lambda: save_state(self.state_obj, self.data_path)).pack(side=tk.LEFT)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        self.dark_btn = ttk.Button(bar, text=self._dark_label(), command=self._toggle_dark)
        self.dark_btn.pack(side=tk.LEFT, padx=(0, 8))

    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True)

        self.tab_dashboard = DashboardCanvas(
            self.nb,
            self.get_state,
            on_select_case=self._open_case_file,
            on_new_case=self._new_case,
            on_edit_case=self._open_case_editor,
            on_archive_case=self._archive_case,
            on_delete_case=self._delete_case,
            on_unarchive_case=self._unarchive_case,
        )
        self.nb.add(self.tab_dashboard, text="Dashboard")

        self.tab_casefile = CaseFileCanvas(self.nb, self.get_state, self.set_state, self._get_case)
        self.nb.add(self.tab_casefile, text="Case File")

        self.tab_board = BoardCanvas(
            self.nb,
            self.get_state,
            self.set_state,
            self._get_case,
            open_evidence=self._open_evidence
        )
        self.nb.add(self.tab_board, text="Cork Board")

    def _on_case_combo(self, _evt=None):
        text = self.case_combo.get()
        if hasattr(self, "_case_display_to_id"):
            cid = self._case_display_to_id.get(text)
            if cid:
                self.current_case_id = cid
                self.refresh_all()
                return
        # fallback: attempt to parse legacy format
        if " — " in text:
            self.current_case_id = text.split(" — ", 1)[0]
            self.refresh_all()

    def _set_case(self, case_id: str):
        self.current_case_id = case_id
        self._sync_case_combo()
        self.refresh_all()

    def _open_case_file(self, case_id: str):
        # Set case and switch to Case File tab when navigated from dashboard links
        self._set_case(case_id)
        try:
            self.nb.select(self.tab_casefile)
        except Exception:
            pass

    def _open_case_editor(self, case_id: str):
        # Open case file tab and toggle edit mode
        self._open_case_file(case_id)
        try:
            if getattr(self.tab_casefile, "mode", "view") != "edit":
                self.tab_casefile._toggle_edit()  # type: ignore[attr-defined]
        except Exception:
            pass

    def _archive_case(self, case_id: str):
        from src.cases.service import find_case

        c = find_case(self.state_obj.cases, case_id)
        if not c:
            return
        c.archived = True
        self.set_state(self.state_obj)

    def _unarchive_case(self, case_id: str):
        from src.cases.service import find_case

        c = find_case(self.state_obj.cases, case_id)
        if not c:
            return
        c.archived = False
        self.set_state(self.state_obj)

    def _delete_case(self, case_id: str):
        from tkinter import messagebox
        from src.cases.service import find_case

        c = find_case(self.state_obj.cases, case_id)
        if not c:
            return
        if not messagebox.askyesno("Delete Case", f"Delete case '{c.name}'? This cannot be undone."):
            return
        self.state_obj.cases = [x for x in self.state_obj.cases if x.id != case_id]
        # adjust current case
        if self.current_case_id == case_id:
            self.current_case_id = self.state_obj.cases[0].id if self.state_obj.cases else ""
        self.set_state(self.state_obj)

    def _open_evidence(self, case_id: str, evidence_id: str | None = None):
        # Switch to case and open the standard evidence editor on the Case File tab
        self._open_case_file(case_id)
        try:
            self.tab_casefile._open_evidence_editor(evidence_id)
        except Exception:
            pass

    def _get_case(self):
        return self.current_case_id

    def _new_case(self):
        from src.cases.service import create_case

        c = create_case("New Case")
        self.state_obj.cases.append(c)
        self.current_case_id = c.id
        self.set_state(self.state_obj)

    def refresh_all(self):
        self._sync_case_combo()
        # best-effort: update background based on theme
        pal = palette(self.state_obj.dark_mode)
        try:
            self.configure(bg=pal["bg"])  # window bg
        except Exception:
            pass
        self.dark_btn.configure(text=self._dark_label())
        self.tab_dashboard.refresh()
        self.tab_casefile.refresh()
        self.tab_board.refresh()

    def _on_close(self):
        save_state(self.state_obj, self.data_path)
        self.destroy()

    # dark mode
    def _toggle_dark(self):
        self.state_obj.dark_mode = not getattr(self.state_obj, "dark_mode", False)
        save_state(self.state_obj, self.data_path)
        self.refresh_all()

    def _dark_label(self) -> str:
        return "Dark: On" if getattr(self.state_obj, "dark_mode", False) else "Dark: Off"


def main():
    path = os.getenv("APP_DATA_PATH", DEFAULT_DATA_PATH)
    app = App(data_path=path)
    app.mainloop()


if __name__ == "__main__":
    main()
