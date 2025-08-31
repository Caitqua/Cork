from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser  # match cbai2 style

from src.cases.service import find_case
from src.board.service import add_node, add_link, list_nodes, list_links, remove_node, remove_link
from src.board.service import add_node_from_evidence
from src.evidence.service import find_evidence


class BoardCanvas(ttk.Frame):
    NODE_W = 140
    NODE_H = 50

    def __init__(self, master, get_state, set_state, get_current_case_id, open_evidence=None):
        super().__init__(master)
        self.get_state = get_state
        self.set_state = set_state
        self.get_current_case_id = get_current_case_id
        self._open_evidence_cb = open_evidence

        # UI
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X)
        # Search first
        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=(6, 2), pady=6)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=24)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<Return>", lambda _e: self._apply_search())
        ttk.Button(toolbar, text="Search", command=self._search_btn).pack(side=tk.LEFT, padx=6)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        # Pinning and notes
        ttk.Button(toolbar, text="Pin Evidence", command=self._pin_evidence).pack(side=tk.LEFT, padx=6)
        ttk.Button(toolbar, text="Add Note", command=self._add_note).pack(side=tk.LEFT, padx=6)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        # Zoom controls with label
        ttk.Label(toolbar, text="Zoom:").pack(side=tk.LEFT)
        ttk.Button(toolbar, text="-", width=3, command=lambda: self._set_zoom(self._zoom * 0.9)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="100%", width=5, command=lambda: self._set_zoom(1.0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="+", width=3, command=lambda: self._set_zoom(self._zoom * 1.1)).pack(side=tk.LEFT)

        self.canvas = tk.Canvas(self, bg="#fbfbfb")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # state
        self._drag = {"active": False, "dx": 0, "dy": 0, "node_id": None}
        self._selected_node_id = None
        self._selected_node_ids: set[str] = set()
        self._pending_link_source = None
        self._img_cache: dict[str, tk.PhotoImage] = {}
        # zoom + initial center
        self._zoom: float = 1.0
        self._did_initial_center: bool = False
        # marquee selection
        self._marquee = None
        self._marquee_start: tuple[int, int] | None = None
        # panning
        self._panning = False
        self._right_dragged: bool = False
        self._rp_x: int | None = None
        self._rp_y: int | None = None
        # edges map for context menu
        self._edge_items: dict[int, str] = {}
        self._ctx_menu: tk.Menu | None = None
        # search state
        self._search_active = False
        self._search_query = ""

        # events
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        # Right-click panning + context
        self.canvas.bind("<Button-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)

    def refresh(self):
        self._redraw()
        # Center once when tab first draws
        if not getattr(self, "_did_initial_center", False):
            try:
                self._center_on_evidence()
            finally:
                self._did_initial_center = True

    # drawing
    def _redraw(self):
        from src.common.theme import palette

        self.canvas.delete("all")
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        pal = palette(getattr(self.get_state(), "dark_mode", False))
        try:
            self.canvas.configure(bg=pal["board_bg"])
        except Exception:
            pass
        nodes = list_nodes(case)
        self._edge_items.clear()

        # map node.id -> (x,y) and evidence_id -> (x,y)
        centers = {}
        evid_centers = {}
        for n in nodes:
            centers[n.id] = (n.x, n.y)
            if n.evidence_id:
                evid_centers[n.evidence_id] = (n.x, n.y)
        # Draw edges from evidence links
        for ev in case.evidence:
            src_center = evid_centers.get(ev.id)
            if not src_center:
                continue  # only draw links from evidence that has a node on the board
            for ln in getattr(ev, 'links', []) or []:
                if not getattr(ln, 'visible', True):
                    continue
                if ln.target_type == 'node':
                    dst_center = centers.get(ln.target_id)
                else:
                    dst_center = evid_centers.get(ln.target_id)
                if not dst_center:
                    continue
                x1, y1 = src_center
                x2, y2 = dst_center
                line_id = self.canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill=pal["edge"], width=max(1, int(self._zoom)))
                # map to evidence link identity for context actions
                self._edge_items[line_id] = (ev.id, ln.id)
                if getattr(ln, 'show_label', False) and (ln.label or ""):
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    lab_id = self.canvas.create_text(mx, my - max(6, int(10 * self._zoom / 1.8)), text=ln.label, font=("Segoe UI", max(1, int(9 * self._zoom))), fill=pal["subtext"], anchor="s")
                    self._edge_items[lab_id] = (ev.id, ln.id)

        for n in nodes:
            self._draw_node(n)
        # update scrollregion to include all nodes with padding
        if nodes:
            xs = [n.x for n in nodes]
            ys = [n.y for n in nodes]
            pad = int(200 * max(self._zoom, 1.0))
            try:
                self.canvas.configure(scrollregion=(min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad))
            except Exception:
                pass

    def _draw_node(self, n):
        x, y = n.x, n.y
        from src.common.theme import palette

        pal = palette(getattr(self.get_state(), "dark_mode", False))
        is_selected = (n.id == self._selected_node_id) or (n.id in self._selected_node_ids)
        # search fading
        dim = False
        if self._search_active and self._search_query:
            q = self._search_query.lower()
            hay = f"{n.title} {n.description}".lower()
            dim = q not in hay
        fill = pal["node_fill_active"] if is_selected else (pal["panel_header_bg"] if dim else pal["node_fill"]) 

        # Measure title wrapped to a max width (scaled)
        scale = max(self._zoom, 0.25)
        MAX_W = int(220 * scale)
        PAD = int(10 * scale)
        GAP = int(6 * scale)
        text_color = pal["subtext"] if dim else pal["text"]
        title_id = self.canvas.create_text(0, 0, text=n.title or "Node", font=("Segoe UI", max(1, int(10 * scale)), "bold"), fill=text_color, anchor="nw", width=MAX_W)
        bx1, by1, bx2, by2 = self.canvas.bbox(title_id)
        title_w = (bx2 - bx1) if bx1 is not None else 80
        title_h = (by2 - by1) if by1 is not None else 20

        # Optional icon or image
        img_w = img_h = 0
        image_id = None
        icon_id = None
        if n.image_path:
            try:
                if n.image_path not in self._img_cache:
                    self._img_cache[n.image_path] = tk.PhotoImage(file=n.image_path)
                img = self._img_cache[n.image_path]
                img_w, img_h = img.width(), img.height()
                image_id = self.canvas.create_image(0, 0, image=img, anchor="n")
            except Exception:
                pass
        elif n.icon:
            # Render emoji icon as text
            icon_id = self.canvas.create_text(0, 0, text=n.icon, font=("Segoe UI Emoji", max(1, int(18 * scale))), fill=text_color, anchor="n")
            ix1, iy1, ix2, iy2 = self.canvas.bbox(icon_id)
            img_w = (ix2 - ix1) if ix1 is not None else 24
            img_h = (iy2 - iy1) if iy1 is not None else 24

        # Compute box size based on content
        content_w = max(title_w, img_w)
        w = max(min(content_w + 2 * PAD, MAX_W + 2 * PAD), 140)
        h = (img_h if (image_id or icon_id) else 0) + (GAP if (image_id or icon_id) else 0) + title_h + 2 * PAD

        rect = self.canvas.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2, fill=fill, outline=pal["node_border"], width=max(1, int(1 * scale)))
        # Position icon/image and title relative to rect
        top = y - h / 2
        if image_id:
            self.canvas.coords(image_id, x, top + PAD)
        if icon_id:
            self.canvas.coords(icon_id, x, top + PAD)
        # Center title
        self.canvas.coords(title_id, x - title_w / 2, top + PAD + (img_h if (image_id or icon_id) else 0) + (GAP if (image_id or icon_id) else 0))

        # Ensure rect is behind content
        try:
            self.canvas.tag_lower(rect, title_id)
        except Exception:
            pass

        self.canvas.addtag_withtag(f"node:{n.id}", rect)
        self.canvas.addtag_withtag(f"node:{n.id}", title_id)
        if image_id:
            self.canvas.addtag_withtag(f"node:{n.id}", image_id)
        if icon_id:
            self.canvas.addtag_withtag(f"node:{n.id}", icon_id)

    # interactions
    def _find_node_at(self, x, y):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return None
        for n in list_nodes(case):
            w, h = self._node_size(n)
            if abs(x - n.x) <= w / 2 and abs(y - n.y) <= h / 2:
                return n
        return None

    def _node_size(self, n):
        # Approximate node size using the same layout as _draw_node (title width + optional icon)
        scale = max(self._zoom, 0.25)
        MAX_W = int(220 * scale)
        PAD = int(10 * scale)
        GAP = int(6 * scale)
        tmp_id = self.canvas.create_text(0, 0, text=n.title or "Node", font=("Segoe UI", max(1, int(10 * scale)), "bold"), anchor="nw", width=MAX_W)
        bx1, by1, bx2, by2 = self.canvas.bbox(tmp_id)
        self.canvas.delete(tmp_id)
        title_w = (bx2 - bx1) if bx1 is not None else 80
        title_h = (by2 - by1) if by1 is not None else 20
        img_w = img_h = 0
        if n.image_path and n.image_path in self._img_cache:
            img = self._img_cache[n.image_path]
            img_w, img_h = img.width(), img.height()
        elif n.icon:
            icon_id = self.canvas.create_text(0, 0, text=n.icon, font=("Segoe UI Emoji", max(1, int(18 * scale))), anchor="n")
            ix1, iy1, ix2, iy2 = self.canvas.bbox(icon_id)
            self.canvas.delete(icon_id)
            img_w = (ix2 - ix1) if ix1 is not None else 24
            img_h = (iy2 - iy1) if iy1 is not None else 24
        content_w = max(title_w, img_w)
        w = max(min(content_w + 2 * PAD, MAX_W + 2 * PAD), 140)
        h = (img_h if img_h else 0) + (GAP if img_h else 0) + title_h + 2 * PAD
        return w, h

    def _on_click(self, event):
        # hide any open context menu
        try:
            if self._ctx_menu is not None:
                self._ctx_menu.unpost()
                self._ctx_menu = None
        except Exception:
            self._ctx_menu = None
        # Clicking anywhere clears active search highlights
        self._search_active = False
        self._search_query = ""
        # translate to canvas coordinates
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        # proceed with selection/linking logic
        n = self._find_node_at(cx, cy)
        if n:
            if self._pending_link_source and self._pending_link_source != n.id:
                # complete link using Evidence links
                case = find_case(self.get_state().cases, self.get_current_case_id() or "")
                src = next((x for x in case.board_nodes if x.id == self._pending_link_source), None)
                if src:
                    from src.evidence.service import add_evidence_link
                    # ensure source has evidence backing
                    if not src.evidence_id:
                        if messagebox.askyesno("Convert", "Source node is not evidence. Convert to evidence?"):
                            from src.evidence.service import create_evidence
                            e = create_evidence(case, type="node", title=src.title, notes=src.description or "")
                            src.evidence_id = e.id
                        else:
                            self._pending_link_source = None
                            return
                    add_evidence_link(
                        next((ev for ev in case.evidence if ev.id == src.evidence_id), None),
                        target_type="node",
                        target_id=n.id,
                    )
                self._pending_link_source = None
                try:
                    self.canvas.configure(cursor="arrow")
                except Exception:
                    pass
                self.set_state(self.get_state())
                self._selected_node_id = n.id
                self._selected_node_ids = {n.id}
                self._redraw()
                return
            # If node already part of multi-select, drag group
            if n.id in self._selected_node_ids:
                self._selected_node_id = n.id
                self._drag.update({"active": True, "dx": cx - n.x, "dy": cy - n.y, "node_id": n.id, "group": True, "gx": cx, "gy": cy})
            else:
                self._selected_node_id = n.id
                self._selected_node_ids = {n.id}
                self._drag.update({"active": True, "dx": cx - n.x, "dy": cy - n.y, "node_id": n.id, "group": False})
            self._redraw()
        else:
            # start marquee selection
            self._selected_node_id = None
            self._drag.update({"active": False, "node_id": None})
            # if we were in link mode and user clicked empty space, exit link mode
            if self._pending_link_source:
                self._pending_link_source = None
                try:
                    self.canvas.configure(cursor="arrow")
                except Exception:
                    pass
            self._marquee_start = (cx, cy)
            if self._marquee:
                try: self.canvas.delete(self._marquee)
                except Exception: pass
            self._marquee = self.canvas.create_rectangle(
                cx, cy, cx, cy,
                outline="#60a5fa", dash=(3, 2), fill="#60a5fa", stipple="gray25"
            )
            # do not redraw immediately; preserve marquee box while dragging

    def _on_drag(self, event):
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        # marquee update
        if self._marquee_start is not None and self._marquee is not None and not self._drag.get("active", False):
            x0, y0 = self._marquee_start
            self.canvas.coords(self._marquee, x0, y0, cx, cy)
            return
        # node drag
        if not self._drag.get("active", False) or not self._drag.get("node_id"):
            return
        if self._drag.get("group"):
            # move all selected by delta of cursor
            dx = cx - self._drag.get("gx", cx)
            dy = cy - self._drag.get("gy", cy)
            for n in case.board_nodes:
                if n.id in self._selected_node_ids:
                    n.x += int(dx)
                    n.y += int(dy)
            self._drag["gx"], self._drag["gy"] = cx, cy
        else:
            n = next((x for x in case.board_nodes if x.id == self._drag["node_id"]), None)
            if n:
                n.x = int(cx - self._drag["dx"])
                n.y = int(cy - self._drag["dy"])
        self._redraw()
        try:
            self.canvas.update_idletasks()
        except Exception:
            pass

    def _on_release(self, _evt):
        cx, cy = self.canvas.canvasx(_evt.x), self.canvas.canvasy(_evt.y)
        # finalize marquee selection
        if self._marquee_start is not None and self._marquee is not None:
            try:
                x0, y0 = self._marquee_start
                x1, y1 = cx, cy
                xmin, xmax = sorted([x0, x1])
                ymin, ymax = sorted([y0, y1])
                case = find_case(self.get_state().cases, self.get_current_case_id() or "")
                self._selected_node_ids = set()
                if case:
                    for n in list_nodes(case):
                        w, h = self._node_size(n)
                        if (xmin <= n.x - w/2 <= xmax and ymin <= n.y - h/2 <= ymax) or (xmin <= n.x + w/2 <= xmax and ymin <= n.y + h/2 <= ymax) or (xmin <= n.x <= xmax and ymin <= n.y <= ymax):
                            self._selected_node_ids.add(n.id)
                self._selected_node_id = next(iter(self._selected_node_ids), None)
            except Exception:
                pass
            finally:
                try:
                    self.canvas.delete(self._marquee)
                except Exception:
                    pass
                self._marquee = None
                self._marquee_start = None
                self._redraw()
                return
        self._drag.update({"active": False, "node_id": None, "group": False})
        self.set_state(self.get_state())  # persist position change

    # commands
    # _add_node removed in favor of pinning evidence

    def _add_note(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        win = tk.Toplevel(self)
        win.title("Add Sticky Note")
        row = ttk.Frame(win); row.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(row, text="Title", width=12).pack(side=tk.LEFT)
        title_var = tk.StringVar(value="Sticky Note")
        ttk.Entry(row, textvariable=title_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row2 = ttk.Frame(win); row2.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        ttk.Label(row2, text="Description", width=12).pack(side=tk.LEFT, anchor="n")
        desc_text = tk.Text(row2, height=4, width=40); desc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        row3 = ttk.Frame(win); row3.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(row3, text="Icon", width=12).pack(side=tk.LEFT)
        icon_var = tk.StringVar(value="📝")
        icon_choices = ["", "📝", "📌", "⚠️", "⭐", "📍"]
        ttk.Combobox(row3, textvariable=icon_var, values=icon_choices, width=8, state="readonly").pack(side=tk.LEFT)

        row4 = ttk.Frame(win); row4.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(row4, text="Image", width=12).pack(side=tk.LEFT)
        img_var = tk.StringVar(value="")
        img_entry = ttk.Entry(row4, textvariable=img_var, width=40); img_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        def _browse():
            p = filedialog.askopenfilename(title="Select Image", filetypes=[("Images", "*.png *.gif *.ppm *.pgm"), ("All", "*.*")])
            if p:
                img_var.set(p)
        ttk.Button(row4, text="Browse", command=_browse).pack(side=tk.LEFT, padx=6)

        btns = ttk.Frame(win); btns.pack(fill=tk.X, padx=10, pady=8)
        def _save():
            title = title_var.get().strip() or "Sticky Note"
            desc = desc_text.get("1.0", tk.END).strip()
            node = add_node(case, title=title, description=desc, icon=(icon_var.get().strip() or None), image_path=(img_var.get().strip() or None))
            # mark as sticky note for potential future styling/logic
            try:
                node.details["sticky"] = "1"
            except Exception:
                pass
            self.set_state(self.get_state())
            self._redraw()
            win.destroy()
        ttk.Button(btns, text="Add", command=_save).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=6)

    def _remove_selected(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        # Determine targets: multi-select or single
        target_ids = set(self._selected_node_ids) if self._selected_node_ids else ({self._selected_node_id} if self._selected_node_id else set())
        if not target_ids:
            return
        # Confirm once
        if not messagebox.askyesno(
            "Confirm",
            f"Delete {len(target_ids)} selected node(s)? Evidence-backed nodes will also delete their evidence.",
        ):
            return
        from src.evidence.service import delete_evidence
        # Collect evid ids to avoid duplicate deletes
        evid_to_delete = set()
        for nid in list(target_ids):
            n = next((x for x in case.board_nodes if x.id == nid), None)
            if not n:
                continue
            if n.evidence_id:
                evid_to_delete.add(n.evidence_id)
        # Delete evidence first (removes attached nodes too)
        for evid in evid_to_delete:
            try:
                delete_evidence(case, evid)
            except Exception:
                pass
        # Remove any remaining nodes in target_ids (notes/unpinned)
        for nid in list(target_ids):
            n = next((x for x in case.board_nodes if x.id == nid), None)
            if n and not n.evidence_id:
                remove_node(case, nid)
        # Clear selection and refresh
        self._selected_node_id = None
        self._selected_node_ids = set()
        self.set_state(self.get_state())
        self._redraw()

    def _link_mode(self):
        # clicking a first node sets pending source; clicking next node creates link
        if not self._selected_node_id:
            messagebox.showinfo("Link", "Select a node first to start a link.")
            return
        self._pending_link_source = self._selected_node_id
        # Indicate link mode by changing cursor
        try:
            self.canvas.configure(cursor="crosshair")
        except Exception:
            pass

    def _edit_selected(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case or not self._selected_node_id:
            messagebox.showinfo("Edit Node", "Select a node to edit.")
            return
        n = next((x for x in case.board_nodes if x.id == self._selected_node_id), None)
        if not n:
            return
        self._edit_node(n)

    def _edit_node(self, n):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case or not n:
            return
        # If this is a sticky note (non-evidence), open a note editor; else open evidence editor
        if not n.evidence_id:
            self._open_note_editor(n)
            return
        try:
            temp = CaseFileCanvas(self, self.get_state, self.set_state, self.get_current_case_id)
            temp._open_evidence_editor(n.evidence_id)
        except Exception:
            pass

    def _open_note_editor(self, n):
        win = tk.Toplevel(self)
        win.title("Edit Note")
        row = ttk.Frame(win); row.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(row, text="Title", width=12).pack(side=tk.LEFT)
        title_var = tk.StringVar(value=n.title or "")
        ttk.Entry(row, textvariable=title_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        row2 = ttk.Frame(win); row2.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        ttk.Label(row2, text="Description", width=12).pack(side=tk.LEFT, anchor="n")
        desc_text = tk.Text(row2, height=6, width=40); desc_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        if n.description:
            desc_text.insert(tk.END, n.description)
        row3 = ttk.Frame(win); row3.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(row3, text="Icon", width=12).pack(side=tk.LEFT)
        icon_var = tk.StringVar(value=n.icon or "")
        icon_choices = ["", "📝", "📌", "⚠️", "⭐", "📍"]
        ttk.Combobox(row3, textvariable=icon_var, values=icon_choices, width=8, state="readonly").pack(side=tk.LEFT)
        row4 = ttk.Frame(win); row4.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(row4, text="Image", width=12).pack(side=tk.LEFT)
        img_var = tk.StringVar(value=n.image_path or "")
        img_entry = ttk.Entry(row4, textvariable=img_var, width=40); img_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        def _browse():
            p = filedialog.askopenfilename(title="Select Image", filetypes=[("Images", "*.png *.gif *.ppm *.pgm"), ("All", "*.*")])
            if p:
                img_var.set(p)
        ttk.Button(row4, text="Browse", command=_browse).pack(side=tk.LEFT, padx=6)
        btns = ttk.Frame(win); btns.pack(fill=tk.X, padx=10, pady=8)
        def _save():
            n.title = title_var.get().strip() or "Note"
            n.description = desc_text.get("1.0", tk.END).strip()
            n.icon = icon_var.get().strip() or None
            n.image_path = img_var.get().strip() or None
            self.set_state(self.get_state())
            win.destroy()
        ttk.Button(btns, text="Save", command=_save).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=6)

    def _pin_evidence(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        win = tk.Toplevel(self)
        win.title("Pin Evidence")
        row = ttk.Frame(win); row.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(row, text="Filter", width=10).pack(side=tk.LEFT)
        filter_var = tk.StringVar()
        ttk.Entry(row, textvariable=filter_var, width=24).pack(side=tk.LEFT)
        row2 = ttk.Frame(win); row2.pack(fill=tk.X, padx=10, pady=(0,8))
        ttk.Label(row2, text="Select", width=10).pack(side=tk.LEFT)
        ev_var = tk.StringVar()
        ev_cb = ttk.Combobox(row2, textvariable=ev_var, width=60)
        all_vals = [f"{e.id} — [{e.type}] {e.title}" for e in case.evidence]
        def _refresh_vals():
            q = (filter_var.get() or "").lower()
            if q:
                vals = [v for v in all_vals if q in v.lower()]
            else:
                vals = all_vals
            ev_cb["values"] = vals
        _refresh_vals()
        ev_cb.pack(side=tk.LEFT)
        filter_var.trace_add("write", lambda *_: _refresh_vals())
        btns = ttk.Frame(win); btns.pack(fill=tk.X, padx=10, pady=8)
        def _id_from_val(val: str) -> str:
            return val.split(" — ", 1)[0] if " — " in val else val
        def _pin():
            evid = _id_from_val(ev_var.get().strip())
            if not evid:
                return
            eobj = next((x for x in case.evidence if x.id == evid), None)
            if not eobj:
                return
            if any(n.evidence_id == evid for n in case.board_nodes):
                messagebox.showinfo("Pin", "This evidence is already pinned.")
            else:
                add_node_from_evidence(case, eobj)
                self.set_state(self.get_state())
                self._redraw()
            win.destroy()
        ttk.Button(btns, text="Pin", command=_pin).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=6)

    def _remove_selected_evidence(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case or not self._selected_node_id:
            messagebox.showinfo("Remove Evidence", "Select a node with evidence to remove.")
            return
        n = next((x for x in case.board_nodes if x.id == self._selected_node_id), None)
        if not n or not n.evidence_id:
            messagebox.showinfo("Remove Evidence", "Selected node is not evidence.")
            return
        if not messagebox.askyesno("Confirm", "Delete this evidence item?"):
            return
        from src.evidence.service import delete_evidence
        evid = n.evidence_id
        if delete_evidence(case, evid):
            for nn in case.board_nodes:
                if nn.evidence_id == evid:
                    nn.evidence_id = None
            self.set_state(self.get_state())
            self._redraw()

    # Right-click: panning and context menu
    def _on_right_press(self, event):
        # hide any open context menu
        try:
            if self._ctx_menu is not None:
                self._ctx_menu.unpost()
                self._ctx_menu = None
        except Exception:
            self._ctx_menu = None
        self._panning = True
        self._right_dragged = False
        self._rp_x, self._rp_y = event.x, event.y
        try:
            self.canvas.scan_mark(event.x, event.y)
        except Exception:
            pass
        self._ctx_pos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _on_right_drag(self, event):
        if self._panning:
            self._right_dragged = True
            try:
                self.canvas.scan_dragto(event.x, event.y, gain=1)
            except Exception:
                pass

    def _on_right_release(self, event):
        # If there wasn't much movement, treat as context click
        was_drag = self._right_dragged
        self._panning = False
        self._right_dragged = False
        # simple movement threshold
        try:
            dx = abs((self._rp_x or event.x) - event.x)
            dy = abs((self._rp_y or event.y) - event.y)
        except Exception:
            dx = dy = 0
        self._rp_x = None; self._rp_y = None
        if was_drag or dx > 4 or dy > 4:
            # do not open context menu after a drag/pan
            return
        self._show_context_menu(event.x_root, event.y_root, self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))

    def _on_double_click(self, event):
        n = self._find_node_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if not n:
            return
        self._open_view_node(n)

    def _open_view_node(self, n):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        win = tk.Toplevel(self)
        win.title("Node — View")
        nb = ttk.Notebook(win); nb.pack(fill=tk.BOTH, expand=True)
        # Overview
        ov = ttk.Frame(nb); nb.add(ov, text="Overview")
        top = ttk.Frame(ov); top.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(top, text=n.icon or "").pack(side=tk.LEFT)
        ttk.Label(top, text=n.title, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=8)
        body = ttk.Frame(ov); body.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        if n.image_path:
            try:
                if n.image_path not in self._img_cache:
                    self._img_cache[n.image_path] = tk.PhotoImage(file=n.image_path)
                img = self._img_cache[n.image_path]
                tk.Label(body, image=img).pack(anchor="w", pady=(0,8))
            except Exception:
                pass
        ttk.Label(body, text=(n.description or ""), wraplength=520, justify=tk.LEFT).pack(anchor="w")
        # Links (view/edit)
        lk = ttk.Frame(nb); nb.add(lk, text="Links")
        links_controls = ttk.Frame(lk); links_controls.pack(fill=tk.X, padx=10, pady=(8,4))
        edit_links = tk.BooleanVar(value=False)
        ttk.Button(links_controls, text="Edit Links", command=lambda: (edit_links.set(True), _render_links())).pack(side=tk.LEFT)
        listf = ttk.Frame(lk); listf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4,10))
        def _render_links():
            for w in list(listf.winfo_children()):
                w.destroy()
            links = [e for e in list_links(case) if e.source == n.id or e.target == n.id]
            if not links:
                ttk.Label(listf, text="No links.").pack(anchor="w")
                return
            hdr = ttk.Frame(listf); hdr.pack(fill=tk.X, pady=(0,2))
            ttk.Label(hdr, text="Dir", width=6).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Peer", width=36).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Label", width=24).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Visible", width=8).pack(side=tk.LEFT)
            ttk.Label(hdr, text="Show Label", width=10).pack(side=tk.LEFT)
            for e in links:
                row = ttk.Frame(listf); row.pack(fill=tk.X, pady=2)
                ttk.Label(row, text=("→" if e.source == n.id else "←"), width=6).pack(side=tk.LEFT)
                peer_id = e.target if e.source == n.id else e.source
                peer = next((x for x in case.board_nodes if x.id == peer_id), None)
                ttk.Label(row, text=(peer.title if peer else peer_id), width=36).pack(side=tk.LEFT)
                if edit_links.get():
                    lab_var = tk.StringVar(value=e.label or "")
                    ttk.Entry(row, textvariable=lab_var, width=24).pack(side=tk.LEFT, padx=2)
                    vis_var = tk.BooleanVar(value=getattr(e, 'visible', True))
                    ttk.Checkbutton(row, variable=vis_var).pack(side=tk.LEFT, padx=6)
                    shlbl_var = tk.BooleanVar(value=getattr(e, 'show_label', False))
                    ttk.Checkbutton(row, variable=shlbl_var).pack(side=tk.LEFT, padx=6)
                    def _save(e=e, lab_var=lab_var, vis_var=vis_var, shlbl_var=shlbl_var):
                        e.label = lab_var.get().strip() or None
                        e.visible = bool(vis_var.get())
                        e.show_label = bool(shlbl_var.get())
                        self.set_state(self.get_state())
                        self._redraw()
                    ttk.Button(row, text="Save", command=_save).pack(side=tk.LEFT, padx=6)
                else:
                    ttk.Label(row, text=(e.label or ""), width=24).pack(side=tk.LEFT)
                    ttk.Label(row, text=("Yes" if getattr(e, 'visible', True) else "No"), width=8).pack(side=tk.LEFT)
                    ttk.Label(row, text=("Yes" if getattr(e, 'show_label', False) else "No"), width=10).pack(side=tk.LEFT)
        _render_links()
        # Details (view/edit)
        dt = ttk.Frame(nb); nb.add(dt, text="Details")
        details_controls = ttk.Frame(dt); details_controls.pack(fill=tk.X, padx=10, pady=(8,4))
        edit_details = tk.BooleanVar(value=False)
        ttk.Button(details_controls, text="Edit Details", command=lambda: (edit_details.set(True), _render_details())).pack(side=tk.LEFT)
        details_list = ttk.Frame(dt); details_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4,10))
        def _render_details():
            for w in list(details_list.winfo_children()):
                w.destroy()
            if not (n.details or edit_details.get()):
                ttk.Label(details_list, text="No details.").pack(anchor="w")
                return
            if not edit_details.get():
                for k, v in (n.details or {}).items():
                    r = ttk.Frame(details_list); r.pack(fill=tk.X, pady=2)
                    ttk.Label(r, text=f"{k}:", width=18).pack(side=tk.LEFT)
                    ttk.Label(r, text=v).pack(side=tk.LEFT)
                return
            # edit mode
            rows: list[tuple[tk.StringVar, tk.StringVar, ttk.Frame]] = []
            for k, v in (n.details or {}).items():
                r = ttk.Frame(details_list); r.pack(fill=tk.X, pady=2)
                kv = tk.StringVar(value=k); vv = tk.StringVar(value=v)
                ttk.Entry(r, textvariable=kv, width=18).pack(side=tk.LEFT)
                ttk.Entry(r, textvariable=vv).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
                def _remove(rr=r, kvv=kv, vvv=vv):
                    try:
                        rr.destroy()
                        rows.remove((kvv, vvv, rr))
                    except Exception:
                        pass
                ttk.Button(r, text="Remove", command=_remove).pack(side=tk.LEFT, padx=4)
                rows.append((kv, vv, r))
            # add new
            ttk.Button(details_list, text="Add field", command=lambda: rows.append(_add_row())).pack(anchor="w", pady=6)
            def _add_row():
                r = ttk.Frame(details_list); r.pack(fill=tk.X, pady=2)
                kv = tk.StringVar(value=""); vv = tk.StringVar(value="")
                ttk.Entry(r, textvariable=kv, width=18).pack(side=tk.LEFT)
                ttk.Entry(r, textvariable=vv).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
                ttk.Button(r, text="Remove", command=lambda rr=r: (rr.destroy(), rows.remove((kv, vv, r)) if (kv, vv, r) in rows else None)).pack(side=tk.LEFT, padx=4)
                return (kv, vv, r)
            # save
            def _save_details():
                n.details = {kv.get().strip(): vv.get().strip() for (kv, vv, _r) in rows if kv.get().strip()}
                self.set_state(self.get_state())
                edit_details.set(False)
                _render_details()
            ttk.Button(details_list, text="Save", command=_save_details).pack(anchor="w", pady=6)
        _render_details()

    def _show_context_menu(self, rx, ry, x, y):
        menu = tk.Menu(self, tearoff=0)
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        target_node = self._find_node_at(x, y)
        # Detect if an edge exists under cursor
        edge_key = None
        try:
            items = self.canvas.find_overlapping(x-1, y-1, x+1, y+1)
            for it in items:
                if it in self._edge_items:
                    edge_key = self._edge_items[it]
                    break
        except Exception:
            pass

        if edge_key:
            menu.add_command(label="Remove Link", command=lambda ek=edge_key: self._remove_ev_link(ek))
        elif target_node:
            # Open Node (same as double click -> view node)
            menu.add_command(label="Open Node", command=lambda n=target_node: self._open_view_node(n))
            menu.add_separator()
            menu.add_command(label="Edit Node", command=lambda n=target_node: self._edit_node(n))
            menu.add_command(label="Remove Node", command=self._remove_selected)
            menu.add_separator()
            menu.add_command(label="Link Node", command=lambda: self._start_link_from(target_node.id))
        else:
            menu.add_command(label="Add Node Here", command=lambda: self._add_node_at(x, y))
        try:
            # keep a reference so we can close it when clicking elsewhere
            self._ctx_menu = menu
            menu.tk_popup(rx, ry)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _start_link_from(self, node_id: str):
        self._selected_node_id = node_id
        self._selected_node_ids = {node_id}
        self._pending_link_source = node_id
        # Indicate link mode by changing cursor
        try:
            self.canvas.configure(cursor="crosshair")
        except Exception:
            pass

    def _set_zoom(self, value: float):
        try:
            self._zoom = max(0.3, min(3.0, float(value)))
        except Exception:
            self._zoom = 1.0
        self._redraw()

    def _center_on_evidence(self):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        nodes = [n for n in list_nodes(case) if n.evidence_id] or list_nodes(case)
        if not nodes:
            return
        # center to average position of considered nodes
        cx = sum(n.x for n in nodes) / len(nodes)
        cy = sum(n.y for n in nodes) / len(nodes)
        try:
            # compute scroll fractions
            bbox = self.canvas.bbox("all")
            if not bbox:
                return
            x1, y1, x2, y2 = bbox
            vw = max(1, self.canvas.winfo_width())
            vh = max(1, self.canvas.winfo_height())
            total_w = max(1, x2 - x1)
            total_h = max(1, y2 - y1)
            fx = (cx - x1 - vw / 2) / max(1, total_w - vw)
            fy = (cy - y1 - vh / 2) / max(1, total_h - vh)
            fx = min(max(fx, 0.0), 1.0)
            fy = min(max(fy, 0.0), 1.0)
            self.canvas.xview_moveto(fx)
            self.canvas.yview_moveto(fy)
        except Exception:
            pass

    def _add_node_at(self, x, y):
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        add_node(case, title="Node", x=int(x), y=int(y))
        self.set_state(self.get_state())
        self._redraw()

    def _remove_ev_link(self, edge_key):
        # edge_key is (evidence_id, link_id)
        try:
            evid_id, link_id = edge_key
        except Exception:
            return
        case = find_case(self.get_state().cases, self.get_current_case_id() or "")
        if not case:
            return
        ev = next((x for x in case.evidence if x.id == evid_id), None)
        if not ev:
            return
        from src.evidence.service import remove_evidence_link
        if remove_evidence_link(ev, link_id):
            self.set_state(self.get_state())
            self._redraw()

    # Search
    def _apply_search(self):
        q = (self.search_var.get() or "").strip()
        if q:
            self._search_active = True
            self._search_query = q
        self._redraw()

    def _search_btn(self):
        # Apply then clear field; keep highlights until background click
        self._apply_search()
        self.search_var.set("")
