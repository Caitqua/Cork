from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser  # match cbai2

from src.cases.service import find_case
from src.common.theme import palette
from src.evidence.service import create_evidence
from src.notebook.service import list_notes, create_note, update_note, delete_note
from src.board.service import add_node_from_evidence


class CaseFileCanvas(ttk.Frame):
    def __init__(self, master, get_state, set_state, get_current_case_id):
        super().__init__(master)
        self.get_state = get_state
        self.set_state = set_state
        self.get_current_case_id = get_current_case_id

        # header: title + edit toggle
        hdr = ttk.Frame(self)
        hdr.pack(fill=tk.X)
        self.title_label = ttk.Label(hdr, text="")
        self.title_label.pack(side=tk.LEFT, padx=8, pady=6)
        self.edit_btn = ttk.Button(hdr, text="Edit", command=self._toggle_edit)
        self.edit_btn.pack(side=tk.LEFT)

        # scrollable body (canvas + frame)
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)
        self.sc = tk.Canvas(body, highlightthickness=0)
        self.sc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vscroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.sc.yview)
        self.vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.sc.configure(yscrollcommand=self.vscroll.set)
        self.content = tk.Frame(self.sc)
        self.sc_window = self.sc.create_window((0, 0), window=self.content, anchor="nw")

        # keep scrollregion updated
        def _on_configure(_evt=None):
            self.sc.configure(scrollregion=self.sc.bbox("all"))
            # keep width synced
            try:
                self.sc.itemconfigure(self.sc_window, width=self.sc.winfo_width())
            except Exception:
                pass

        self.content.bind("<Configure>", _on_configure)
        self.sc.bind("<Configure>", _on_configure)

        # state
        self.mode = "view"
        # journal state
        self._journal_collapsed: dict[str, bool] = {}
        self._journal_edit_id: str | None = None
        self._journal_new: bool = False

    def refresh(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        self.title_label.configure(text=f"Case: {case.name}" if case else "Case: —")
        pal = palette(getattr(self.get_state(), "dark_mode", False))

        # theme the scroll canvas
        try:
            self.sc.configure(bg=pal["canvas_bg"])
            self.content.configure(bg=pal["canvas_bg"])  # best-effort for tk.Frame
        except Exception:
            pass

        # clear content
        for child in list(self.content.winfo_children()):
            child.destroy()

        if not case:
            tk.Label(self.content, text="Select or create a case.").pack(pady=24)
            return

        if self.mode == "edit":
            self._build_edit_form(self.content)
            self._fill_edit_values(case)
            return

        # View mode content
        # Case Details section
        sec = tk.Frame(self.content, bg=pal["panel_bg"], highlightbackground=pal["panel_border"], highlightthickness=1)
        sec.pack(fill=tk.X, padx=12, pady=(12, 8))
        tk.Label(sec, text="Case Details", font=("Segoe UI", 11, "bold"), bg=pal["panel_header_bg"], fg=pal["text"], anchor="w").pack(fill=tk.X)
        inner = tk.Frame(sec, bg=pal["panel_bg"])
        inner.pack(fill=tk.X, padx=12, pady=8)
        rows = [
            ("Name", case.name or "—"),
            ("Type", case.case_type or "—"),
            ("Objectives", ", ".join(case.objectives) or "—"),
        ]
        for lab, val in rows:
            r = tk.Frame(inner, bg=pal["panel_bg"]) ; r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=f"{lab}:", width=14, anchor="w", bg=pal["panel_bg"], fg=pal["text"]).pack(side=tk.LEFT)
            tk.Label(r, text=val, anchor="w", bg=pal["panel_bg"], fg=pal["subtext"]).pack(side=tk.LEFT)

        # Client Info block (key:value per line)
        ci_items = list(case.client_info.items()) if case.client_info else []
        if ci_items:
            r = tk.Frame(inner, bg=pal["panel_bg"]) ; r.pack(fill=tk.X, pady=(8, 2))
            tk.Label(r, text="Client Info:", width=14, anchor="nw", bg=pal["panel_bg"], fg=pal["text"]).pack(side=tk.LEFT)
            ci_frame = tk.Frame(r, bg=pal["panel_bg"]) ; ci_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            for k, v in ci_items:
                row = tk.Frame(ci_frame, bg=pal["panel_bg"]) ; row.pack(fill=tk.X)
                tk.Label(row, text=f"{k}:", width=16, anchor="w", bg=pal["panel_bg"], fg=pal["text"]).pack(side=tk.LEFT)
                tk.Label(row, text=v, anchor="w", bg=pal["panel_bg"], fg=pal["subtext"]).pack(side=tk.LEFT)

        # Notes / Summary block
        if case.summary:
            r = tk.Frame(inner, bg=pal["panel_bg"]) ; r.pack(fill=tk.X, pady=(8, 2))
            tk.Label(r, text="Notes:", width=14, anchor="nw", bg=pal["panel_bg"], fg=pal["text"]).pack(side=tk.LEFT)
            notes_lbl = tk.Label(r, text=case.summary, justify=tk.LEFT, wraplength=800, bg=pal["panel_bg"], fg=pal["subtext"], anchor="w")
            notes_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Case Journal
        self._render_journal(self.content, case, pal)

        # Evidence section
        evid_sec = tk.Frame(self.content, bg=pal["panel_bg"], highlightbackground=pal["panel_border"], highlightthickness=1)
        evid_sec.pack(fill=tk.X, padx=12, pady=(8, 16))
        tk.Label(evid_sec, text="Evidence", font=("Segoe UI", 11, "bold"), bg=pal["panel_header_bg"], fg=pal["text"], anchor="w").pack(fill=tk.X)
        einner = tk.Frame(evid_sec, bg=pal["panel_bg"]) ; einner.pack(fill=tk.X, padx=12, pady=8)
        ttk.Button(einner, text="Add Evidence Item", command=self._add_evidence).pack(anchor="w", pady=(0, 8))

        for e in case.evidence:
            row = tk.Frame(einner, bg=pal["muted_box_bg"], highlightbackground=pal["muted_box_border"], highlightthickness=1)
            row.pack(fill=tk.X, pady=6)
            top = tk.Frame(row, bg=pal["muted_box_bg"]) ; top.pack(fill=tk.X, padx=8, pady=(6, 2))
            tk.Label(top, text=f"[{e.type}] {e.title}", bg=pal["muted_box_bg"], fg=pal["text"], anchor="w").pack(side=tk.LEFT)
            # Actions: Pin to Board, Edit, Delete
            def _pin(eid=e.id):
                case2 = find_case(self.get_state().cases, self.get_current_case_id() or "")
                if not case2:
                    return
                ev2 = next((x for x in case2.evidence if x.id == eid), None)
                if not ev2:
                    return
                node = add_node_from_evidence(case2, ev2)
                if node is None:
                    messagebox.showinfo("Board", "This evidence is already pinned on the board.")
                    return
                self.set_state(self.get_state())
                messagebox.showinfo("Board", "Pinned on the Cork Board.")
            ttk.Button(top, text="Pin to Board", command=_pin).pack(side=tk.RIGHT, padx=(4, 0))
            ttk.Button(top, text="Edit", command=lambda eid=e.id: self._open_evidence_editor(eid)).pack(side=tk.RIGHT)
            def _del_evidence(eid=e.id):
                case3 = find_case(self.get_state().cases, self.get_current_case_id() or "")
                if not case3:
                    return
                if messagebox.askyesno("Delete Evidence", "Delete this evidence item?"):
                    from src.evidence.service import delete_evidence
                    if delete_evidence(case3, eid):
                        self.set_state(self.get_state())
            ttk.Button(top, text="Delete", command=_del_evidence).pack(side=tk.RIGHT, padx=(4, 0))
            sub = ", ".join(filter(None, [e.date or "", e.location or "", e.collector or ""]))
            if sub:
                tk.Label(row, text=sub, bg=pal["muted_box_bg"], fg=pal["subtext"], anchor="w").pack(fill=tk.X, padx=8, pady=(0, 6))

    # Journal rendering and actions
    def _render_journal(self, root, case, pal):
        sec = tk.Frame(root, bg=pal["panel_bg"], highlightbackground=pal["panel_border"], highlightthickness=1)
        sec.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 8))
        hdr = tk.Frame(sec, bg=pal["panel_header_bg"]) ; hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Case Journal", font=("Segoe UI", 11, "bold"), bg=pal["panel_header_bg"], fg=pal["text"], anchor="w").pack(side=tk.LEFT, padx=6, pady=2)
        ttk.Button(hdr, text="New Entry", command=self._journal_new_entry).pack(side=tk.RIGHT, padx=6, pady=4)

        inner = tk.Frame(sec, bg=pal["panel_bg"]) ; inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # new entry editor
        if self._journal_new:
            self._render_journal_editor(inner, None, pal)

        # list entries (newest first)
        items = list_notes(case)
        # sort by created_at desc when possible
        try:
            items = sorted(items, key=lambda n: n.created_at, reverse=True)
        except Exception:
            pass
        for n in items:
            self._render_journal_item(inner, n, pal)

    def _render_journal_item(self, parent, n, pal):
        cont = tk.Frame(parent, bg=pal["muted_box_bg"], highlightbackground=pal["muted_box_border"], highlightthickness=1)
        cont.pack(fill=tk.X, pady=6)
        top = tk.Frame(cont, bg=pal["muted_box_bg"]) ; top.pack(fill=tk.X, padx=8, pady=(6, 4))
        title = f"{n.title or 'Untitled'}"
        meta = f" — {n.created_at.split('T')[0] if n.created_at else ''}"
        tk.Label(top, text=title + meta, bg=pal["muted_box_bg"], fg=pal["text"], anchor="w").pack(side=tk.LEFT)
        btn_text = "Show" if self._journal_collapsed.get(n.id, False) else "Hide"
        ttk.Button(top, text=btn_text, command=lambda nid=n.id: self._toggle_journal_collapse(nid)).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(top, text="Delete", command=lambda nid=n.id: self._delete_journal(nid)).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(top, text="Edit", command=lambda nid=n.id: self._start_edit_journal(nid)).pack(side=tk.RIGHT)

        if self._journal_edit_id == n.id:
            self._render_journal_editor(cont, n, pal)
            return

        if not self._journal_collapsed.get(n.id, False):
            body = tk.Label(cont, text=n.body or "", justify=tk.LEFT, wraplength=800, bg=pal["muted_box_bg"], fg=pal["subtext"], anchor="w")
            body.pack(fill=tk.X, padx=8, pady=(0, 8))

    def _render_journal_editor(self, parent, n, pal):
        editor = tk.Frame(parent, bg=pal["panel_bg"]) ; editor.pack(fill=tk.X, padx=8, pady=6)
        row = tk.Frame(editor, bg=pal["panel_bg"]) ; row.pack(fill=tk.X)
        tk.Label(row, text="Title", width=10, anchor="w", bg=pal["panel_bg"], fg=pal["text"]).pack(side=tk.LEFT)
        title_var = tk.StringVar(value=(n.title if n else ""))
        title_entry = tk.Entry(row, textvariable=title_var)
        self._apply_text_theme(title_entry)
        title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row2 = tk.Frame(editor, bg=pal["panel_bg"]) ; row2.pack(fill=tk.X, pady=(6, 2))
        tk.Label(row2, text="Body", width=10, anchor="nw", bg=pal["panel_bg"], fg=pal["text"]).pack(side=tk.LEFT)
        body_text = tk.Text(row2, height=8)
        self._apply_text_theme(body_text)
        body_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if n and n.body:
            body_text.insert(tk.END, n.body)

        btns = tk.Frame(editor, bg=pal["panel_bg"]) ; btns.pack(fill=tk.X, pady=6)
        def on_save():
            title = title_var.get().strip() or "Note"
            body = body_text.get("1.0", tk.END).strip()
            case = find_case(self.get_state().cases, self.get_current_case_id() or "")
            if not case:
                return
            if n is None:
                create_note(case, title=title, body=body)
                self._journal_new = False
            else:
                update_note(case, n.id, title=title, body=body)
                self._journal_edit_id = None
            self.set_state(self.get_state())

        ttk.Button(btns, text="Save", command=on_save).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=self._cancel_journal_edit).pack(side=tk.LEFT, padx=6)

    def _toggle_journal_collapse(self, note_id: str):
        self._journal_collapsed[note_id] = not self._journal_collapsed.get(note_id, False)
        self.refresh()

    def _start_edit_journal(self, note_id: str):
        self._journal_edit_id = note_id
        self._journal_new = False
        self.refresh()

    def _cancel_journal_edit(self):
        self._journal_edit_id = None
        self._journal_new = False
        self.refresh()

    def _journal_new_entry(self):
        self._journal_new = True
        self._journal_edit_id = None
        self.refresh()

    def _delete_journal(self, note_id: str):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        if messagebox.askyesno("Delete Entry", "Delete this journal entry?"):
            if delete_note(case, note_id):
                self.set_state(self.get_state())

    # edit mode
    def _toggle_edit(self):
        self.mode = "edit" if self.mode == "view" else "view"
        self.edit_btn.configure(text=("Done" if self.mode == "edit" else "Edit"))
        self.refresh()

    def _apply_text_theme(self, widget):
        pal = palette(getattr(self.get_state(), "dark_mode", False))
        try:
            widget.configure(bg=pal["panel_bg"], fg=pal["text"])
        except Exception:
            pass
        # caret color
        try:
            widget.configure(insertbackground=pal["text"])
        except Exception:
            pass
        # border color (best-effort for tk widgets)
        try:
            widget.configure(highlightbackground=pal["panel_border"], highlightcolor=pal["panel_border"])  # type: ignore
        except Exception:
            pass

    def _build_edit_form(self, root):
        # basic fields for case editing
        pal = palette(getattr(self.get_state(), "dark_mode", False))
        self.name_var = tk.StringVar()
        self.type_var = tk.StringVar()
        self.objectives_var = tk.StringVar()
        self.client_var = tk.Text(root, height=5, width=40)
        self.summary_var = tk.Text(root, height=10, width=60)

        row = ttk.Frame(root)
        row.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(row, text="Name", width=16).pack(side=tk.LEFT)
        self.name_entry = tk.Entry(row, textvariable=self.name_var, width=50)
        self._apply_text_theme(self.name_entry)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = ttk.Frame(root)
        row.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(row, text="Type", width=16).pack(side=tk.LEFT)
        self.type_entry = tk.Entry(row, textvariable=self.type_var, width=30)
        self._apply_text_theme(self.type_entry)
        self.type_entry.pack(side=tk.LEFT)

        row = ttk.Frame(root)
        row.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(row, text="Objectives (comma)", width=16).pack(side=tk.LEFT)
        self.objectives_entry = tk.Entry(row, textvariable=self.objectives_var, width=60)
        self._apply_text_theme(self.objectives_entry)
        self.objectives_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = ttk.Frame(root)
        row.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        ttk.Label(row, text="Client info (key=value per line)", width=28).pack(side=tk.LEFT, anchor="n")
        # scrollable client info text
        ci_wrap = tk.Frame(row, bg=palette(getattr(self.get_state(), "dark_mode", False))["panel_bg"]) ; ci_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._apply_text_theme(self.client_var)
        self.client_var.configure(wrap=tk.WORD)
        ysb1 = ttk.Scrollbar(ci_wrap, orient=tk.VERTICAL, command=self.client_var.yview)
        self.client_var.configure(yscrollcommand=ysb1.set)
        self.client_var.pack(in_=ci_wrap, side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb1.pack(in_=ci_wrap, side=tk.RIGHT, fill=tk.Y)

        row = ttk.Frame(root)
        row.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        ttk.Label(row, text="Notes", width=16).pack(side=tk.LEFT, anchor="n")
        # scrollable notes text
        notes_wrap = tk.Frame(row, bg=palette(getattr(self.get_state(), "dark_mode", False))["panel_bg"]) ; notes_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._apply_text_theme(self.summary_var)
        self.summary_var.configure(wrap=tk.WORD)
        ysb2 = ttk.Scrollbar(notes_wrap, orient=tk.VERTICAL, command=self.summary_var.yview)
        self.summary_var.configure(yscrollcommand=ysb2.set)
        self.summary_var.pack(in_=notes_wrap, side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb2.pack(in_=notes_wrap, side=tk.RIGHT, fill=tk.Y)

        row = ttk.Frame(root)
        row.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(row, text="Save", command=self._save_edit).pack(side=tk.LEFT)
        ttk.Button(row, text="Cancel", command=self._toggle_edit).pack(side=tk.LEFT, padx=8)
        ttk.Button(row, text="Archive Case", command=self._archive_case).pack(side=tk.RIGHT)
        ttk.Button(row, text="Delete Case", command=self._delete_case).pack(side=tk.RIGHT, padx=8)

    def _fill_edit_values(self, case):
        if not case:
            return
        self.name_var.set(case.name)
        self.type_var.set(case.case_type or "")
        self.objectives_var.set(", ".join(case.objectives))
        self.client_var.delete("1.0", tk.END)
        for k, v in case.client_info.items():
            self.client_var.insert(tk.END, f"{k}={v}\n")
        self.summary_var.delete("1.0", tk.END)
        self.summary_var.insert(tk.END, case.summary or "")

    def _save_edit(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        case.name = self.name_var.get().strip() or case.name
        case.case_type = self.type_var.get().strip() or None
        # objectives
        objs = [o.strip() for o in self.objectives_var.get().split(",") if o.strip()]
        case.objectives = objs
        # client
        lines = [ln.strip() for ln in self.client_var.get("1.0", tk.END).splitlines() if ln.strip()]
        ci = {}
        for ln in lines:
            if "=" in ln:
                k, v = ln.split("=", 1)
                ci[k.strip()] = v.strip()
        case.client_info = ci
        # summary (notes)
        case.summary = self.summary_var.get("1.0", tk.END).strip()
        self.set_state(self.get_state())
        self._toggle_edit()

    def _delete_case(self):
        case_id = self.get_current_case_id() or ""
        state = self.get_state()
        c = find_case(state.cases, case_id)
        if not c:
            return
        if not messagebox.askyesno("Delete Case", f"Delete case '{c.name}'? This cannot be undone."):
            return
        state.cases = [x for x in state.cases if x.id != case_id]
        self.set_state(state)

    def _archive_case(self):
        case_id = self.get_current_case_id() or ""
        state = self.get_state()
        c = find_case(state.cases, case_id)
        if not c:
            return
        c.archived = True
        self.set_state(state)

    # evidence
    def _add_evidence(self):
        self._open_evidence_editor(None)

    def _open_evidence_editor(self, evidence_id: str | None):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        ev = None
        if evidence_id:
            ev = next((x for x in case.evidence if x.id == evidence_id), None)

        win = tk.Toplevel(self)
        win.title("Edit Evidence" if ev else "Add Evidence")
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True)
        general = ttk.Frame(nb)
        links_tab = ttk.Frame(nb)
        nb.add(general, text="Details")
        nb.add(links_tab, text="Links")

        fields = {}
        entries = []
        def add_field(label, initial=""):
            row = ttk.Frame(general)
            row.pack(fill=tk.X, padx=10, pady=4)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            var = tk.StringVar(value=initial)
            ent = tk.Entry(row, textvariable=var, width=50)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._apply_text_theme(ent)
            fields[label] = var
            entries.append(ent)

        # Title first
        add_field("Title", ev.title if ev else "")

        # Type dropdown with <custom>
        type_row = ttk.Frame(general)
        type_row.pack(fill=tk.X, padx=10, pady=4)
        ttk.Label(type_row, text="Type", width=14).pack(side=tk.LEFT)
        type_choices = [
            "clip", "photo", "video", "audio", "document",
            "transcript", "note", "link", "device", "sample", "person", "other", "<custom>"
        ]
        type_var = tk.StringVar()
        # initial selection
        initial_type = (ev.type if ev else "") if ev else ""
        if initial_type and initial_type in type_choices:
            type_var.set(initial_type)
        elif initial_type:
            type_var.set("<custom>")
        else:
            type_var.set("clip")
        type_combo = ttk.Combobox(type_row, textvariable=type_var, values=type_choices, state="readonly", width=48)
        type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Custom type field (hidden unless <custom>)
        custom_type_row = ttk.Frame(general)
        custom_type_var = tk.StringVar(value=(initial_type if (ev and initial_type not in type_choices) else ""))
        def _render_custom_type_row():
            # show/hide based on type selection
            if type_var.get() == "<custom>":
                custom_type_row.pack(fill=tk.X, padx=10, pady=4)
            else:
                try:
                    custom_type_row.forget()
                except Exception:
                    pass
        ttk.Label(custom_type_row, text="Custom Type", width=14).pack(side=tk.LEFT)
        custom_type_entry = tk.Entry(custom_type_row, textvariable=custom_type_var, width=50)
        custom_type_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._apply_text_theme(custom_type_entry)
        type_combo.bind("<<ComboboxSelected>>", lambda _e: _render_custom_type_row())
        _render_custom_type_row()

        # Details editor
        details_frame = ttk.LabelFrame(general, text="Details")
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        detail_rows: list[tuple[tk.StringVar, tk.StringVar, ttk.Frame]] = []
        detail_type_choices = [
            "id", "url", "address", "phone", "email", "serial", "tag", "category", "source", "confidence"
        ]
        def _add_detail_row(k="", v=""):
            r = ttk.Frame(details_frame); r.pack(fill=tk.X, padx=6, pady=2)
            kv = tk.StringVar(value=k); vv = tk.StringVar(value=v)
            tcb = ttk.Combobox(r, textvariable=kv, values=detail_type_choices, width=16)
            tcb.pack(side=tk.LEFT)
            ttk.Entry(r, textvariable=vv).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            def _remove():
                detail_rows.remove((kv, vv, r))
                r.destroy()
            ttk.Button(r, text="Remove", command=_remove).pack(side=tk.LEFT)
            detail_rows.append((kv, vv, r))
        if ev and getattr(ev, 'details', None):
            for k, v in (ev.details or {}).items():
                _add_detail_row(k, v)
        ttk.Button(details_frame, text="Add field", command=lambda: _add_detail_row()).pack(anchor="w", padx=6, pady=4)

        notes_row = ttk.Frame(general)
        notes_row.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        ttk.Label(notes_row, text="Notes", width=14).pack(side=tk.LEFT, anchor="n")
        notes_text = tk.Text(notes_row, height=6, width=50)
        notes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._apply_text_theme(notes_text)
        if ev and ev.notes:
            notes_text.insert(tk.END, ev.notes)

        # Tags field removed

        # Links tab
        from src.board.service import list_nodes
        from src.evidence.service import add_evidence_link, update_evidence_link, remove_evidence_link
        links_header = ttk.Frame(links_tab); links_header.pack(fill=tk.X, padx=10, pady=(8,4))
        ttk.Label(links_header, text="Add Link").pack(side=tk.LEFT)
        add_row = ttk.Frame(links_tab); add_row.pack(fill=tk.X, padx=10, pady=4)
        ttk.Label(add_row, text="Type", width=8).pack(side=tk.LEFT)
        link_type_var = tk.StringVar(value="node")
        ttk.Combobox(add_row, textvariable=link_type_var, values=["node", "evidence"], width=10, state="readonly").pack(side=tk.LEFT)
        ttk.Label(add_row, text="Target", width=8).pack(side=tk.LEFT)
        link_target_var = tk.StringVar()
        link_target_cb = ttk.Combobox(add_row, textvariable=link_target_var, width=46)
        link_target_cb.pack(side=tk.LEFT, padx=4)
        ttk.Label(add_row, text="Label", width=8).pack(side=tk.LEFT)
        link_label_var = tk.StringVar()
        ttk.Entry(add_row, textvariable=link_label_var, width=20).pack(side=tk.LEFT, padx=4)
        def _refresh_target_values():
            if link_type_var.get() == "node":
                vals = [f"{n.id} — {n.title}" for n in list_nodes(case)]
            else:
                vals = [f"{x.id} — [{x.type}] {x.title}" for x in case.evidence]
            link_target_cb["values"] = vals
        _refresh_target_values()
        link_type_var.trace_add("write", lambda *_: _refresh_target_values())
        def _id_from_val(val: str) -> str:
            return val.split(" — ", 1)[0] if " — " in val else val
        def _add_link():
            if not ev:
                messagebox.showinfo("Save", "Save this evidence before adding links.")
                return
            tgt = _id_from_val(link_target_var.get().strip())
            if not tgt:
                return
            add_evidence_link(ev, target_type=link_type_var.get(), target_id=tgt, label=(link_label_var.get().strip() or None))
            self.set_state(self.get_state())
            link_target_var.set(""); link_label_var.set("")
            _render_links_list()
        ttk.Button(add_row, text="Add", command=_add_link).pack(side=tk.LEFT, padx=4)

        links_list = ttk.Frame(links_tab); links_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4,10))
        def _render_links_list():
            for w in list(links_list.winfo_children()):
                w.destroy()
            if not ev:
                ttk.Label(links_list, text="No links yet. Save to start linking.").pack(anchor="w")
                return
            hdr = ttk.Frame(links_list); hdr.pack(fill=tk.X, pady=(0,2))
            ttk.Label(hdr, text="Type", width=10).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Target", width=36).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Label", width=18).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Visible", width=8).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Show Label", width=10).pack(side=tk.LEFT)
            for ln in getattr(ev, 'links', []) or []:
                row = ttk.Frame(links_list); row.pack(fill=tk.X, pady=2)
                tvar = tk.StringVar(value=ln.target_type)
                tcb = ttk.Combobox(row, textvariable=tvar, values=["node", "evidence"], state="readonly", width=10)
                tcb.pack(side=tk.LEFT)
                svar = tk.StringVar(value=ln.target_id)
                scb = ttk.Combobox(row, textvariable=svar, width=36)
                scb.pack(side=tk.LEFT, padx=4)
                # sync targets for this row
                def _sync_row_targets(cb=scb, tvar=tvar):
                    if tvar.get() == "node":
                        cb["values"] = [f"{n.id} — {n.title}" for n in list_nodes(case)]
                    else:
                        cb["values"] = [f"{x.id} — [{x.type}] {x.title}" for x in case.evidence]
                _sync_row_targets()
                tcb.bind("<<ComboboxSelected>>", lambda _e, cb=scb, tv=tvar: _sync_row_targets(cb, tv))
                lvar = tk.StringVar(value=ln.label or "")
                ttk.Entry(row, textvariable=lvar, width=18).pack(side=tk.LEFT, padx=4)
                vis_var = tk.BooleanVar(value=getattr(ln, 'visible', True))
                ttk.Checkbutton(row, variable=vis_var).pack(side=tk.LEFT, padx=6)
                shlbl_var = tk.BooleanVar(value=getattr(ln, 'show_label', False))
                ttk.Checkbutton(row, variable=shlbl_var).pack(side=tk.LEFT, padx=6)
                def _save_this(ln=ln, tvar=tvar, svar=svar, lvar=lvar, vis_var=vis_var, shlbl_var=shlbl_var):
                    update_evidence_link(ev, ln.id, target_type=tvar.get(), target_id=_id_from_val(svar.get().strip()), label=(lvar.get().strip() or None), visible=bool(vis_var.get()), show_label=bool(shlbl_var.get()))
                    self.set_state(self.get_state())
                def _del_this(ln=ln):
                    remove_evidence_link(ev, ln.id)
                    self.set_state(self.get_state())
                    _render_links_list()
                ttk.Button(row, text="Save", command=_save_this).pack(side=tk.LEFT, padx=4)
                ttk.Button(row, text="Delete", command=_del_this).pack(side=tk.LEFT)
        _render_links_list()

        btns = ttk.Frame(win)
        btns.pack(fill=tk.X, padx=10, pady=8)

        def on_save():
            # resolve type selection with custom
            if type_var.get() == "<custom>":
                dtype = custom_type_var.get().strip() or "unknown"
            else:
                dtype = type_var.get().strip() or "unknown"
            title = fields["Title"].get().strip() or "Untitled"
            notes = notes_text.get("1.0", tk.END).strip()
            details = {kv.get().strip(): vv.get().strip() for (kv, vv, _r) in detail_rows if kv.get().strip()}
            if ev:
                ev.type = dtype
                ev.title = title
                ev.notes = notes
                ev.details = details
            else:
                create_evidence(case, type=dtype, title=title, notes=notes, details=details)
            self.set_state(self.get_state())
            win.destroy()

        ttk.Button(btns, text="Save", command=on_save).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=8)
