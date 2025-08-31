#!/usr/bin/env python3
"""
Case Board — upgraded

Additions:
- Thread colors (double‑click a thread to edit label + color)
- Images on cards (optional, small thumbnail)
- Keyboard shortcuts: A(Add), C(Connect toggle), E(Edit selected), F(Add field), Del(Delete)
- Sidebar: list of all clues (with search), selected clue details, custom fields (add/remove)
- Generic clue icons (emoji set: location, business, apartment, home, person, vehicle, phone, email, document)
- Save/Load includes new fields; robust to older JSON
- Export PNG (needs Pillow), EPS without Pillow

Run:
    python3 case_board.py
"""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
from datetime import datetime
from collections import defaultdict

# External dependencies
import requests

# Optional PNG export + thumbnail images
PIL_AVAILABLE = False
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    pass

# Cache for thumbnails to avoid repeated disk I/O and resizes
THUMB_CACHE = {}

# Default sizing constants for clues.  A clue can dynamically grow taller
# based on its content, but these define the minimum sizes.  Width remains
# fixed for now; height may be recalculated when drawing.
NODE_WIDTH = 240
NODE_MIN_WIDTH = 180
NODE_HEIGHT = 130
NODE_MIN_HEIGHT = 60

# Default padding around text and elements inside a clue.  These values
# are preserved for backward compatibility but are superseded by more
# granular padding constants defined below.
TEXT_PAD_X = 8
TEXT_PAD_Y = 4

# ---------------------------------------------------------------------------
# LLM configuration and UI padding knobs
#
# LLM_MODEL and OLLAMA_URL define which Ollama model to use and where to
# connect.  Adjust these to point to your Ollama instance and desired model.
#
# The following padding constants control the horizontal and vertical
# spacing of various elements within a clue.  Changing these values at
# runtime will adjust how icons, titles, descriptions and fields are laid
# out.  See Node.draw() for usage.

# Name of the Ollama model to use for lead generation.
LLM_MODEL = "kibble"
# Base URL of the Ollama server.  Include protocol and port (e.g. http://localhost:11434).
OLLAMA_URL = "http://localhost:11434"

# Path to a log file where completed tasks are appended.  Each time a
# task is marked as done, the task text is written to this file with a
# timestamp.  You can adjust this constant to suit your logging
# preferences or set it to ``None`` to disable logging entirely.
COMPLETED_TASKS_LOG = "completed_tasks.log"

# Horizontal and vertical padding for the clue's icon (emoji) when expanded.
ICON_PAD_X = 8
ICON_PAD_Y = 4

# Horizontal and vertical padding for the clue's title text.
TITLE_PAD_X = 8
TITLE_PAD_Y = 4

# Additional vertical padding above the description text (below the title/icon row).
DESC_PAD_Y = 4

# Vertical padding between each field in the details section.
DETAILS_PAD_Y = 4

# Size of the optional thumbnail image inside a clue (width and height in pixels).
THUMBNAIL_SIZE = 44
# Horizontal and vertical margin between the clue border and the thumbnail image.
THUMBNAIL_PAD_X = 10
THUMBNAIL_PAD_Y = 10

# Default colours and styling for clues and edges.  A clue’s background
# colour (bg_color) can be changed per instance via the context menu.
NODE_BG = "#fffef8"
NODE_BORDER = "#444"
NODE_SELECTED = "#2563eb"
EDGE_COLOR_DEFAULT = "#666"
EDGE_SELECTED = "#2563eb"
CANVAS_BG = "#f5f7fb"

# ---------------------------------------------------------------------------
# Additional configuration parameters
#
# These constants make it easy to tune certain behaviours of the case board
# without hunting through the code.  Adjust the values below to suit your
# preferences.  See the accompanying comments for guidance on what each
# parameter controls.

# Size of the square resize handle drawn in the bottom–right corner of each
# clue when it is expanded.  Increasing this value makes it easier to
# click and drag the handle for resizing.
RESIZE_HANDLE_SIZE = 16

# Number of investigative leads to request from the LLM when generating
# suggestions for a clue.  This affects the NodeEditor LLM tab, the
# context menu action on a clue, and any other lead generation routines.
NUM_LEADS = 3

# Number of actionable tasks to request from the LLM when generating
# to‑do list suggestions.  This affects the To‑Do tab’s "Generate" button.
NUM_TASK_LEADS = 3

# Width of the right-hand sidebar.  This constant is used when
# constructing the sidebar tabs and can be tweaked for usability.
SIDEBAR_WIDTH = 340

ICON_CHOICES = [
    ("None", ""),
    ("Location", "📍"),
    ("Business", "🏢"),
    ("Apartment", "🏬"),
    ("Home", "🏠"),
    ("Person", "👤"),
    ("Vehicle", "🚗"),
    ("Phone", "☎️"),
    ("Email", "✉️"),
    ("Document", "📄"),
]

# ---------------------------------------------------------------------------
# Utility functions
#
# The following helper makes it possible to convert human‑readable addresses
# into geographic coordinates.  It uses the Nominatim service provided by
# OpenStreetMap.  Should the lookup fail (for example because there is no
# network connectivity or the service cannot be reached) the function
# gracefully returns ``None``.  See ``CaseBoardApp.add_map_pin_dialog`` for
# usage.

def geocode_address(address: str):
    """Attempt to geocode an address string using the public Nominatim API.

    Given an address or place name, this function performs a lookup against
    the OpenStreetMap Nominatim API and returns a tuple of ``(latitude,
    longitude)`` floats if successful.  A ``None`` return value indicates
    that no coordinates could be resolved.

    The User‑Agent header is explicitly set to identify this application
    when making the request.  This is considered polite behaviour when
    consuming free services.

    :param address: Free‑form address or place description to geocode
    :returns: ``(lat, lon)`` on success or ``None`` on failure
    """
    if not address:
        return None
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1,
    }
    headers = {
        "User-Agent": "CaseBoardApp/1.0"
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            lat = float(data[0].get("lat"))
            lon = float(data[0].get("lon"))
            return lat, lon
    except Exception:
        # Ignore any exceptions (network errors, JSON decoding issues etc.)
        pass
    return None

def center_window(win, width=420, height=280):
    win.update_idletasks()
    ws = win.winfo_screenwidth()
    hs = win.winfo_screenheight()
    x = (ws // 2) - (width // 2)
    y = (hs // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


class NodeEditor(tk.Toplevel):
    """Multi-tab editor for a clue.

    Allows editing of core properties (title, description, icon, thumbnail),
    custom fields, associated connections, and AI lead generation.  The
    to-do list is managed in the sidebar and not edited here.
    """

    def __init__(self, app: 'CaseBoardApp', node: 'Node' = None):
        """Create a new clue editor.

        When ``node`` is provided, the editor modifies that node in place.
        When ``node`` is ``None``, the editor is used to collect details
        for a new clue; in that case ``self.result`` will be a tuple
        ``(title, description, icon_symbol, image_path)`` when OK is
        pressed.  For editing an existing node, no result tuple is
        returned—the node is updated directly.
        """
        super().__init__(app)
        self.app = app
        self.geometry("500x700")
        # Node may be None when creating a new clue
        self.node = node
        # Initialise result for new clue creation
        self.result = None
        # Determine initial values based on whether editing or creating
        if node is not None:
            init_title = node.title
            init_desc = node.description
            init_icon = node.icon
            init_image = node.image_path or ""
            # Shallow copy of fields for editing
            init_fields = {k: v.copy() for k, v in node.fields.items()}
        else:
            init_title = ""
            init_desc = ""
            init_icon = ""
            init_image = ""
            init_fields = {}
        # Window title reflects editing vs creating
        self.title("Edit Clue" if node is not None else "New Clue")
        self.resizable(True, True)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        # Configure weight so notebook expands
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(4, weight=1)

        # Title entry
        ttk.Label(frm, text="Title").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value=init_title)
        self.title_entry = ttk.Entry(frm, textvariable=self.title_var)
        self.title_entry.grid(row=1, column=0, sticky="we", pady=(0,4))

        # Description text area
        ttk.Label(frm, text="Description").grid(row=2, column=0, sticky="w")
        self.desc_text = tk.Text(frm, height=4, wrap="word")
        self.desc_text.grid(row=3, column=0, sticky="nsew")
        self.desc_text.insert("1.0", init_desc)

        # Icon and Image picker row
        icon_row = ttk.Frame(frm)
        icon_row.grid(row=4, column=0, sticky="we", pady=(4,4))
        icon_row.columnconfigure(1, weight=1)
        ttk.Label(icon_row, text="Icon").grid(row=0, column=0, sticky="w")
        self.icon_var = tk.StringVar(value=init_icon)
        # Display names for combo: include emoji where available
        combo_values = [f"{name} {sym}" if sym else name for name, sym in ICON_CHOICES]
        self.icon_combo = ttk.Combobox(icon_row, state="readonly", values=combo_values)
        # Mapping from combo display to symbol
        self.icon_map = { (f"{name} {sym}" if sym else name): sym for name, sym in ICON_CHOICES }
        # Determine initial selection label based on current icon
        initial_label = None
        for name, sym in ICON_CHOICES:
            label = f"{name} {sym}" if sym else name
            if sym == init_icon:
                initial_label = label
                break
        if initial_label is None:
            initial_label = "None"
        self.icon_combo.set(initial_label)
        self.icon_combo.grid(row=0, column=1, sticky="w", padx=(6,0))
        # Image picker widgets
        ttk.Label(icon_row, text="Image").grid(row=1, column=0, sticky="w")
        self.image_var = tk.StringVar(value=init_image)
        img_entry = ttk.Entry(icon_row, textvariable=self.image_var)
        img_entry.grid(row=1, column=1, sticky="we", padx=(6,0))
        ttk.Button(icon_row, text="Browse…", command=self.pick_image).grid(row=1, column=2, padx=(6,0))

        # Notebook for Details, Connections, LLM
        notebook = ttk.Notebook(frm)
        notebook.grid(row=5, column=0, sticky="nsew", pady=(4,4))

        # ----- Details tab -----
        details_tab = ttk.Frame(notebook)
        notebook.add(details_tab, text="Details")
        details_tab.columnconfigure(0, weight=1)
        details_tab.rowconfigure(1, weight=1)
        ttk.Label(details_tab, text="Fields", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.fields_tree_editor = ttk.Treeview(details_tab, columns=("title", "value", "visible"), show="headings")
        self.fields_tree_editor.heading("title", text="Title")
        self.fields_tree_editor.heading("value", text="Value")
        self.fields_tree_editor.heading("visible", text="Visible")
        self.fields_tree_editor.column("visible", width=60, anchor="center")
        self.fields_tree_editor.grid(row=1, column=0, sticky="nsew")
        # Fields are stored separately so they can be edited for both new and existing nodes.
        # Use a dedicated dict; for existing nodes this is a shallow copy of node.fields.
        self.fields_data = init_fields.copy() if init_fields else {}
        # Populate treeview with fields_data
        for fname, info in self.fields_data.items():
            val = info.get("value", "")
            vis = "Yes" if info.get("visible", True) else "No"
            self.fields_tree_editor.insert("", "end", iid=fname, values=(fname, val, vis))
        # Buttons for fields
        fbtn = ttk.Frame(details_tab)
        fbtn.grid(row=2, column=0, sticky="w", pady=(4,0))
        ttk.Button(fbtn, text="Add", command=self._add_field).pack(side="left")
        ttk.Button(fbtn, text="Edit", command=self._edit_field).pack(side="left", padx=4)
        ttk.Button(fbtn, text="Remove", command=self._remove_field).pack(side="left", padx=(0,4))
        # Toggle visibility of selected field on/off
        ttk.Button(fbtn, text="Show/Hide", command=self._toggle_field_visible).pack(side="left")

        # ----- Connections tab -----
        conn_tab = ttk.Frame(notebook)
        notebook.add(conn_tab, text="Connections")
        conn_tab.columnconfigure(0, weight=1)
        conn_tab.rowconfigure(1, weight=1)
        ttk.Label(conn_tab, text="Connections", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.conns_tree_editor = ttk.Treeview(conn_tab, columns=("label", "visible"), show="headings")
        self.conns_tree_editor.heading("label", text="Label")
        self.conns_tree_editor.heading("visible", text="Visible")
        self.conns_tree_editor.column("visible", width=60, anchor="center")
        self.conns_tree_editor.grid(row=1, column=0, sticky="nsew")
        # Populate with current connections if editing existing node
        if node is not None:
            for eid, edge in app.edges.items():
                if edge.src_id == node.id or edge.dst_id == node.id:
                    vis = "Yes" if not edge.hidden else "No"
                    self.conns_tree_editor.insert("", "end", iid=str(eid), values=(edge.label or "", vis))
        # Buttons for connections
        cbtn = ttk.Frame(conn_tab)
        cbtn.grid(row=2, column=0, sticky="w", pady=(4,0))
        ttk.Button(cbtn, text="Rename", command=self._rename_connection).pack(side="left")
        ttk.Button(cbtn, text="Show/Hide", command=self._toggle_connection_visibility).pack(side="left", padx=4)
        ttk.Button(cbtn, text="Create New", command=self._create_connection).pack(side="left")

        # ----- LLM tab -----
        llm_tab = ttk.Frame(notebook)
        notebook.add(llm_tab, text="LLM")
        llm_tab.columnconfigure(0, weight=1)
        ttk.Label(llm_tab, text="Ask the LLM (Ollama) for leads", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        self.llm_query_var = tk.StringVar()
        query_entry = ttk.Entry(llm_tab, textvariable=self.llm_query_var)
        query_entry.pack(fill="x", pady=(4,4))
        # Button for generating leads.  The label includes the number of
        # leads defined in NUM_LEADS for easy adjustment.
        ttk.Button(llm_tab, text=f"Generate {NUM_LEADS} Leads", command=self._ask_llm).pack(anchor="w")
        self.llm_result = tk.Text(llm_tab, height=5, wrap="word")
        self.llm_result.pack(fill="both", expand=True, pady=(4,0))
        self.llm_result.configure(state="disabled")

        # Action buttons (OK/Cancel)
        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, sticky="e", pady=(8,0))
        ttk.Button(btns, text="OK", command=self.on_ok).pack(side="right", padx=(6,0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")

        # Key bindings
        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.title_entry.focus_set()

        # Position the editor; use larger dimensions to fit content comfortably
        center_window(self, 750, 600)

    # ----- Field editors -----
    def _add_field(self):
        # Ask for field title and value
        title = simpledialog.askstring("Add Field", "Field title:", parent=self)
        if not title:
            return
        value = simpledialog.askstring("Add Field", f"Value for '{title}':", parent=self)
        if value is None:
            return
        # Create structured entry and add to fields_data
        entry = {
            "value": value,
            "visible": True,
            "file_link": None,
            "image_path": None,
        }
        self.fields_data[title] = entry
        # If editing an existing node, update its fields as well
        if self.node is not None:
            self.node.fields[title] = entry.copy()
            # Redraw node to reflect new field
            self.node.refresh_text()
        # Insert into treeview
        self.fields_tree_editor.insert("", "end", iid=title, values=(title, value, "Yes"))

    def _edit_field(self):
        sel = self.fields_tree_editor.selection()
        if not sel:
            return
        fname = sel[0]
        info = self.fields_data.get(fname)
        if not info:
            return
        old_val = info.get("value", "")
        new_val = simpledialog.askstring("Edit Field", f"New value for '{fname}':", initialvalue=old_val, parent=self)
        if new_val is None:
            return
        info["value"] = new_val
        # If editing existing node, update its fields
        if self.node is not None and fname in self.node.fields:
            self.node.fields[fname]["value"] = new_val
            # Redraw node on canvas
            self.node.refresh_text()
        # Update treeview
        vis = "Yes" if info.get("visible", True) else "No"
        self.fields_tree_editor.item(fname, values=(fname, new_val, vis))

    def _remove_field(self):
        sel = self.fields_tree_editor.selection()
        if not sel:
            return
        fname = sel[0]
        if messagebox.askyesno("Remove Field", f"Delete field '{fname}'?", parent=self):
            # Remove from data and UI
            self.fields_data.pop(fname, None)
            if self.node is not None:
                self.node.fields.pop(fname, None)
            self.fields_tree_editor.delete(fname)
            # Redraw node on canvas
            if self.node is not None:
                self.node.refresh_text()

    def _toggle_field_visible(self):
        """Toggle the visibility of the selected field in the details list."""
        sel = self.fields_tree_editor.selection()
        if not sel:
            return
        fname = sel[0]
        # Determine current visibility and flip it in fields_data
        info = self.fields_data.get(fname)
        if not info:
            return
        current_vis = info.get("visible", True)
        info["visible"] = not current_vis
        # If editing existing node, update its fields as well
        if self.node is not None and fname in self.node.fields:
            self.node.fields[fname]["visible"] = info["visible"]
            # Redraw node on canvas to reflect change
            self.node.refresh_text()
        # Update tree display
        new_vis_text = "Yes" if info["visible"] else "No"
        vals = list(self.fields_tree_editor.item(fname, "values"))
        if len(vals) >= 3:
            vals[2] = new_vis_text
            self.fields_tree_editor.item(fname, values=tuple(vals))

    # ----- Connections editors -----
    def _rename_connection(self):
        sel = self.conns_tree_editor.selection()
        if not sel:
            return
        eid = int(sel[0])
        edge = self.app.edges.get(eid)
        if not edge:
            return
        new_label = simpledialog.askstring("Rename Connection", "New label:", initialvalue=edge.label, parent=self)
        if new_label is None:
            return
        edge.label = new_label
        edge.draw()
        # Update tree
        vis = "Yes" if not edge.hidden else "No"
        self.conns_tree_editor.item(str(eid), values=(edge.label, vis))

    def _toggle_connection_visibility(self):
        sel = self.conns_tree_editor.selection()
        if not sel:
            return
        eid = int(sel[0])
        edge = self.app.edges.get(eid)
        if not edge:
            return
        edge.hidden = not edge.hidden
        edge.draw()
        vis = "Yes" if not edge.hidden else "No"
        self.conns_tree_editor.item(str(eid), values=(edge.label, vis))

    def _create_connection(self):
        # Switch the main app into connect mode with this node as the first
        self.app.mode_var.set("connect")
        self.app.update_mode()
        self.app.connect_first = self.node
        self.app.status_message(f"Connect: first is “{self.node.title}”. Now click another clue.")

    # ----- LLM tab -----
    def _ask_llm(self):
        """Query the Ollama chat endpoint to generate three investigative leads.

        The prompt is constructed using the node's title and description
        along with an optional focus string entered by the user.  The
        results are displayed in the text area.  Any errors during the
        request are reported to the user.
        """
        focus = self.llm_query_var.get().strip()
        # Build the prompt
        base_prompt = f"Generate {NUM_LEADS} investigative leads related to the clue titled '{self.node.title}'. "
        if self.node.description:
            base_prompt += f"Description: {self.node.description}. "
        if focus:
            base_prompt += f"Focus on: {focus}. "
        base_prompt += "Provide each lead as a separate line."
        try:
            # Prepare payload for Ollama chat endpoint
            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "user", "content": base_prompt}
                ],
			"stream": False,
                # Temperature or other parameters could be added here
            }
            response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Extract the response content.  Ollama chat API returns a list
            # of messages; use the assistant's content from the last turn.
            content = ""
            if isinstance(data, dict):
                # Data may include 'message' or 'messages'
                if "message" in data and isinstance(data["message"], dict):
                    content = data["message"].get("content", "")
                elif "messages" in data and data["messages"]:
                    content = data["messages"][-1].get("content", "")
                else:
                    content = str(data)
            else:
                content = str(data)
            # Split into lines for leads
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            if not lines:
                lines = [content.strip()] if content.strip() else []
            # Take only the configured number of leads
            leads = lines[:NUM_LEADS]
        except Exception as e:
            leads = [f"Error while contacting LLM: {e}"]
        # Present the leads in a new window with checkboxes and a confirm button
        def _confirm_add_leads():
            for var, text in zip(vars_list, leads):
                if var.get():
                    # Add to board's todo list
                    self.app.todo_list.append({"task": text, "done": False})
            # Refresh the app's todo display
            self.app.refresh_todo_listbox()
            win.destroy()
        # Create window only if there are leads
        win = tk.Toplevel(self)
        win.title("Generated Leads")
        ttk.Label(win, text="Select leads to add to the To‑Do list:").pack(anchor="w", padx=8, pady=8)
        vars_list = []
        for text in leads:
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(win, text=text, variable=var)
            cb.pack(anchor="w", padx=12)
            vars_list.append(var)
        ttk.Button(win, text="Add Selected", command=_confirm_add_leads).pack(pady=(8,8))

    def on_ok(self):
        """Apply changes and close the editor.

        If editing an existing node, update its properties and redraw it.
        If creating a new clue (self.node is None), store a result
        tuple for the caller to use when constructing the node.
        """
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Missing title", "Please enter a title.", parent=self)
            return
        desc = self.desc_text.get("1.0", "end").strip()
        icon_label = self.icon_combo.get()
        icon_sym = self.icon_map.get(icon_label, "")
        image_path = self.image_var.get().strip() or ""

        if self.node is not None:
            # Editing existing node: update in place
            self.node.title = title
            self.node.description = desc
            self.node.icon = icon_sym
            self.node.image_path = image_path
            # Fields and connections have already been modified through the UI
            # Redraw the node and refresh the clue list
            self.node.refresh_text()
            self.node.redraw_thumbnail()
            self.app.refresh_clue_list()
        else:
            # Creating a new node: return the collected values, including fields
            # Copy fields_data to avoid sharing references
            self.result = (title, desc, icon_sym, image_path, {k: v.copy() for k, v in self.fields_data.items()})
        # Close the window
        self.destroy()

    def pick_image(self):
        path = filedialog.askopenfilename(
            title="Choose image…",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")]
        )
        if path:
            self.image_var.set(path)

    # Note: the on_ok implementation below updates the node directly.
    # The duplicate on_ok definition used in older versions has been
    # removed to avoid confusion.


class EdgeEditor(tk.Toplevel):
    def __init__(self, master, label="", color=EDGE_COLOR_DEFAULT):
        super().__init__(master)
        self.title("Edit Thread")
        # Allow edge edit window to be resizable
        self.resizable(True, True)
        self.result = None  # (label, color)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        # Let the entry row expand horizontally within the frame
        frm.columnconfigure(0, weight=1)

        ttk.Label(frm, text="Label").grid(row=0, column=0, sticky="w")
        self.label_var = tk.StringVar(value=label)
        ttk.Entry(frm, textvariable=self.label_var, width=38).grid(row=1, column=0, sticky="we", pady=(0,8))

        color_row = ttk.Frame(frm)
        color_row.grid(row=2, column=0, sticky="we")
        ttk.Label(color_row, text="Color").pack(side="left")
        self.color_var = tk.StringVar(value=color)
        self.color_preview = tk.Canvas(color_row, width=26, height=18, bg=color, highlightthickness=1, highlightbackground="#888")
        self.color_preview.pack(side="left", padx=8)
        ttk.Button(color_row, text="Pick…", command=self.pick_color).pack(side="left")

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, sticky="e", pady=(10,0))
        ttk.Button(btns, text="OK", command=self.on_ok).pack(side="right", padx=(8,0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")

        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        center_window(self, 360, 200)

    def pick_color(self):
        (rgb, hexcolor) = colorchooser.askcolor(color=self.color_var.get(), title="Pick thread color")
        if hexcolor:
            self.color_var.set(hexcolor)
            self.color_preview.configure(bg=hexcolor)

    def on_ok(self):
        self.result = (self.label_var.get().strip(), self.color_var.get())
        self.destroy()


class Node:
    """Represents a clue on the canvas.

    Nodes now carry additional state beyond the original version, such as
    a background colour and a collapsed flag.  Fields are stored as a
    mapping from a field title to a dictionary with keys ``value``,
    ``visible``, ``file_link`` and ``image_path``.  These values will be
    used when rendering the clue on the canvas and inside the sidebar.

    :param app: The parent CaseBoardApp instance
    :param node_id: Unique integer identifier for this node
    :param x: X coordinate of the node’s top‑left corner on the canvas
    :param y: Y coordinate of the node’s top‑left corner on the canvas
    :param title: Title text for the clue
    :param description: Longer description for the clue
    :param icon: Optional emoji to display next to the title
    :param image_path: Optional path to a thumbnail image
    :param bg_color: Background colour for the clue’s rectangle or oval
    :param collapsed: Whether the clue is collapsed into a dot
    :param fields: Mapping of field titles to structured field values
    """

    def __init__(self, app, node_id, x, y, title, description, icon="", image_path="", *, bg_color=NODE_BG, collapsed=False, fields=None):
        self.app = app
        self.id = node_id
        self.x = x
        self.y = y
        self.title = title
        self.description = description
        self.icon = icon or ""
        self.image_path = image_path or ""
        # Use structured field dictionaries.  If legacy ``fields`` is passed in
        # as a mapping of key to value (string), promote it into the new
        # structure with defaults for ``visible``, ``file_link`` and
        # ``image_path``.  Otherwise deep‑copy the provided structure.
        self.fields = {}
        if fields:
            for k, v in fields.items():
                # If v is a dict containing at least "value", treat it as
                # the new structure; otherwise treat the whole v as the
                # value string and wrap it.
                if isinstance(v, dict) and "value" in v:
                    self.fields[k] = {
                        "value": v.get("value", ""),
                        "visible": bool(v.get("visible", True)),
                        "file_link": v.get("file_link"),
                        "image_path": v.get("image_path"),
                    }
                else:
                    self.fields[k] = {
                        "value": v,
                        "visible": True,
                        "file_link": None,
                        "image_path": None,
                    }
        self.bg_color = bg_color or NODE_BG
        self.collapsed = bool(collapsed)
        self.width = NODE_WIDTH
        self.height = NODE_HEIGHT

        self.group_tag = f"node_{self.id}"
        # Canvas item ids for the various parts.  They may be None until
        # created in draw().
        self.rect_id = None
        self.title_id = None
        self.desc_id = None
        self.icon_id = None
        self.image_id = None
        self._img_ref = None  # keep PhotoImage alive

        # Resize handle id.  When non-collapsed, a small square at the
        # bottom-right of the clue allows the user to resize the clue by
        # dragging.  This id is used to bind events for resizing.
        self.resize_id = None

        # Field text ids used when drawing visible fields on the canvas.  They
        # are cleared each time draw() is called so we can remove or update
        # them easily.
        self._field_text_ids = []

        # Draw the node immediately upon creation.
        self.draw()

    def draw(self):
        """Draw the node on the canvas.  Handles both expanded and collapsed
        presentations.  When collapsed, the node is a simple oval; when
        expanded it displays the title, description and optional thumbnail.

        If the node has previously been drawn, remove existing items
        associated with this node before drawing anew.
        """
        c = self.app.canvas
        # Remove any existing visual items for this node
        if c.find_withtag(self.group_tag):
            c.delete(self.group_tag)

        # Collapsed representation: draw a filled oval.  Use a diameter of
        # approximately 60px for readability.  The icon (if present) is
        # centred within the dot.
        if self.collapsed:
            diameter = 60
            self.width = diameter
            self.height = diameter
            x0, y0 = self.x, self.y
            x1, y1 = x0 + diameter, y0 + diameter
            self.rect_id = c.create_oval(
                x0, y0, x1, y1,
                fill=self.bg_color,
                outline=NODE_BORDER,
                width=2,
                tags=(self.group_tag, "node", f"node_rect_{self.id}")
            )
            # Draw icon centred if provided
            if self.icon:
                self.icon_id = c.create_text(
                    x0 + diameter / 2,
                    y0 + diameter / 2,
                    text=self.icon,
                    anchor="center",
                    font=("TkDefaultFont", 16, "bold"),
                    tags=(self.group_tag, "node_icon", f"node_icon_{self.id}")
                )
            else:
                self.icon_id = None
            # Collapsed nodes do not display title, description or thumbnail
            self.title_id = None
            self.desc_id = None
            self.image_id = None
        else:
            # Expanded representation.  Do not override existing width/height
            # unless they are below the minimums.  This allows users to
            # resize clues and preserve custom sizing when redrawn.
            # Ensure minimum dimensions
            if self.width < NODE_MIN_WIDTH:
                self.width = NODE_MIN_WIDTH
            if self.height < NODE_MIN_HEIGHT:
                self.height = NODE_MIN_HEIGHT
            x0, y0 = self.x, self.y
            x1, y1 = x0 + self.width, y0 + self.height
            self.rect_id = c.create_rectangle(
                x0, y0, x1, y1,
                fill=self.bg_color,
                outline=NODE_BORDER,
                width=2,
                tags=(self.group_tag, "node", f"node_rect_{self.id}")
            )
            # Icon (emoji) at top-left if provided
            if self.icon:
                self.icon_id = c.create_text(
                    x0 + ICON_PAD_X,
                    y0 + ICON_PAD_Y,
                    text=self.icon,
                    anchor="nw",
                    font=("TkDefaultFont", 14, "bold"),
                    tags=(self.group_tag, "node_icon", f"node_icon_{self.id}")
                )
                # Adjust title x based on icon width (approximate 26px)
                title_x = x0 + ICON_PAD_X + 26 + TITLE_PAD_X
            else:
                self.icon_id = None
                title_x = x0 + TITLE_PAD_X
            # Title
            self.title_id = c.create_text(
                title_x,
                y0 + TITLE_PAD_Y,
                text=self.title,
                anchor="nw",
                font=("TkDefaultFont", 11, "bold"),
                fill="#111",
                tags=(self.group_tag, "node_title", f"node_title_{self.id}")
            )
            # Description text area.  Leave space for title/icon row (~18px) and padding.
            desc_top = y0 + TITLE_PAD_Y + 18 + DESC_PAD_Y
            # Compute available width for the description.  Leave room for the
            # thumbnail on the right: size plus horizontal padding.
            desc_width = self.width - 2 * ICON_PAD_X - (THUMBNAIL_SIZE + THUMBNAIL_PAD_X)
            if desc_width < 60:
                desc_width = 60
            self.desc_id = c.create_text(
                x0 + ICON_PAD_X,
                desc_top,
                text=self.description,
                anchor="nw",
                width=desc_width,
                font=("TkDefaultFont", 10),
                fill="#2c2c2c",
                tags=(self.group_tag, "node_desc", f"node_desc_{self.id}")
            )
            # Optional image thumbnail at right
            self.redraw_thumbnail()

            # Draw visible fields below the description.  Clear any previous
            # field text items first.
            for fid in getattr(self, "_field_text_ids", []):
                c.delete(fid)
            self._field_text_ids = []
            # Determine where the description ends
            desc_bbox = c.bbox(self.desc_id)
            if desc_bbox:
                current_y = desc_bbox[3] + DETAILS_PAD_Y
            else:
                current_y = desc_top + 20
            # Draw each visible field on its own line
            field_height = 14
            for field_title, info in self.fields.items():
                if not info.get("visible", True):
                    continue
                value = info.get("value", "")
                text = f"{field_title}: {value}"
                fid = c.create_text(
                    x0 + ICON_PAD_X,
                    current_y,
                    text=text,
                    anchor="nw",
                    font=("TkDefaultFont", 9),
                    fill="#2c2c2c",
                    tags=(self.group_tag, "node_field", f"node_field_{self.id}")
                )
                self._field_text_ids.append(fid)
                current_y += field_height
            # Compute new height: bottom of last field + padding
            content_bottom = current_y + DETAILS_PAD_Y
            new_height = max(content_bottom - y0, NODE_MIN_HEIGHT)
            # Expand height automatically if content requires more space;
            # do not shrink below the current height so that manual resizes
            # are preserved unless the user explicitly changes the size.
            if new_height > self.height:
                self.height = new_height
                # update rectangle to new size
                c.coords(self.rect_id, x0, y0, x0 + self.width, y0 + self.height)
                # After resizing, reposition thumbnail
                self.redraw_thumbnail()
            # Create or reposition resize handle
            # Remove old handle if present
            if self.resize_id:
                c.delete(self.resize_id)
                self.resize_id = None
            # Draw a small square handle at the bottom-right for resizing
            # Draw a small square handle at the bottom‑right for resizing.  The
            # size is defined by the global RESIZE_HANDLE_SIZE constant so
            # users can tune how easy it is to grab the handle.  A larger
            # handle improves usability on high‑resolution displays.
            handle_size = RESIZE_HANDLE_SIZE
            hx0 = x0 + self.width - handle_size
            hy0 = y0 + self.height - handle_size
            hx1 = x0 + self.width
            hy1 = y0 + self.height
            self.resize_id = c.create_rectangle(
                hx0, hy0, hx1, hy1,
                fill="#ccc",
                outline="#888",
                tags=(self.group_tag, "resize_handle", f"resize_handle_{self.id}")
            )
            # Bind resize events specifically on the handle
            c.tag_bind(self.resize_id, "<ButtonPress-1>", self.on_resize_press)
            c.tag_bind(self.resize_id, "<B1-Motion>", self.on_resize_drag)
            c.tag_bind(self.resize_id, "<ButtonRelease-1>", self.on_resize_release)
        # Bindings
        c.tag_bind(self.group_tag, "<ButtonPress-1>", self.on_press)
        c.tag_bind(self.group_tag, "<B1-Motion>", self.on_drag)
        c.tag_bind(self.group_tag, "<ButtonRelease-1>", self.on_release)
        c.tag_bind(self.group_tag, "<Double-Button-1>", self.on_double_click)
        # Right‑click context menu
        c.tag_bind(self.group_tag, "<Button-3>", lambda e, n=self: self.app.show_node_menu(n, e))

    def redraw_thumbnail(self):
        c = self.app.canvas
        # Remove old
        if self.image_id:
            c.delete(self.image_id)
            self.image_id = None
            self._img_ref = None
        if not self.image_path:
            return
        # Target area
        x0 = self.x + self.width - (THUMBNAIL_SIZE + THUMBNAIL_PAD_X)
        y0 = self.y + THUMBNAIL_PAD_Y
        w, h = THUMBNAIL_SIZE, THUMBNAIL_SIZE
        try:
            if PIL_AVAILABLE:
                key = ("pil", self.image_path, w, h)
                tkimg = THUMB_CACHE.get(key)
                if tkimg is None:
                    img = Image.open(self.image_path)
                    img.thumbnail((w, h))
                    tkimg = ImageTk.PhotoImage(img)
                    THUMB_CACHE[key] = tkimg
            else:
                # Tk PhotoImage supports GIF/PNG minimally
                tmp = tk.PhotoImage(file=self.image_path)
                iw, ih = tmp.width(), tmp.height()
                factor = max(iw // w, ih // h, 1)
                key = ("tk", self.image_path, factor)
                tkimg = THUMB_CACHE.get(key)
                if tkimg is None:
                    if factor > 1:
                        tkimg = tmp.subsample(factor, factor)
                    else:
                        tkimg = tmp
                    THUMB_CACHE[key] = tkimg
            self.image_id = c.create_image(x0, y0, anchor="nw", image=tkimg, tags=(self.group_tag, "node_thumb"))
            self._img_ref = tkimg
        except Exception as e:
            # Show a tiny 'X' if load fails
            self.image_id = c.create_text(x0+2, y0+2, anchor="nw", text="✖", fill="#a00",
                                          tags=(self.group_tag, "node_thumb"))

    def on_press(self, event):
        """Handle mouse button press on this node.

        If the click occurs on the resize handle the event is ignored
        (resizing is handled separately).  In connect mode the click is
        forwarded to the connection handler.  Otherwise this method
        manages both single and multi‑selection semantics: clicking on a
        node that is already part of a multi‑selection does not clear
        the selection, allowing for group movement.  Clicking on a
        previously unselected node will clear any prior selection and
        select only this node.
        """
        current_tags = self.app.canvas.gettags("current")
        # Ignore clicks on the resize handle
        if current_tags and any(tag.startswith("resize_handle_") for tag in current_tags):
            return "break"
        # Connect mode handling
        if self.app.mode == "connect":
            self.app.handle_connect_click(self)
            return
        # If this node is not in the current multi selection, select it exclusively
        if self not in self.app.selected_nodes:
            self.app.select(self)
        # Record starting point for dragging (for single or group moves)
        self.app.canvas.focus_set()
        # For group drag store start coordinates on the app
        if len(self.app.selected_nodes) > 1:
            # Use a group drag start for consistent movement across all nodes
            self.app._group_drag_start = (event.x, event.y)
            # Reset the event time marker so the upcoming drag is processed
            self.app._last_group_drag_time = None
            # Disable smoothing on all edges connected to the selection for performance
            self.app.begin_drag(self.app.selected_nodes)
        # Regardless of single or multi, store this node's drag start for single drags
        self._drag_start = (event.x, event.y)
        if len(self.app.selected_nodes) <= 1:
            # Single-node drag: also disable smoothing for connected edges
            self.app.begin_drag([self])
        
    def on_drag(self, event):
        """Handle mouse drag events on this node.

        Supports both single and multi‑node dragging.  When multiple
        nodes are selected the drag applies to all of them exactly once
        per motion event.  The ``event.time`` attribute is used to
        suppress duplicate processing when the same motion event is
        delivered to multiple items belonging to the same node.
        """
        # Do not move while resizing
        if getattr(self, "_resizing", False):
            return "break"
        # Multi‑selection drag: move all selected nodes in unison
        if len(self.app.selected_nodes) > 1 and self in self.app.selected_nodes:
            # Skip duplicate handling for the same motion event
            last_time = getattr(self.app, "_last_group_drag_time", None)
            if last_time == event.time:
                return "break"
            # Compute delta relative to the stored group drag start
            start_x, start_y = getattr(self.app, "_group_drag_start", (event.x, event.y))
            dx = event.x - start_x
            dy = event.y - start_y
            if dx == 0 and dy == 0:
                return "break"
            for n in self.app.selected_nodes:
                n.x += dx
                n.y += dy
                self.app.canvas.move(n.group_tag, dx, dy)
            # Update connected edges only once using adjacency sets
            affected = set()
            for n in self.app.selected_nodes:
                adj = self.app.edges_by_node.get(n.id)
                if adj:
                    affected.update(adj)
                else:
                    # Fallback: scan edges if adjacency missing
                    for e in self.app.edges.values():
                        if e.src_id == n.id or e.dst_id == n.id:
                            affected.add(e.id)
            for eid in affected:
                e = self.app.edges.get(eid)
                if e:
                    e.update_positions()
            # Update the starting point for the next motion
            self.app._group_drag_start = (event.x, event.y)
            self.app._last_group_drag_time = event.time
            return "break"
        # Single node dragging
        if getattr(self, "_drag_start", None) is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        if dx == 0 and dy == 0:
            return
        self.move_by(dx, dy)
        self._drag_start = (event.x, event.y)

    def on_release(self, event):
        """Reset drag state upon releasing the mouse button."""
        # Clear individual drag start
        self._drag_start = None
        # End any group drag state
        if len(self.app.selected_nodes) > 1:
            self.app._group_drag_start = None
            self.app._last_group_drag_time = None
        # Restore edge smoothing after drag
        self.app.end_drag()

    def on_double_click(self, event):
        """Open the multi‑tab editor for this node.

        The NodeEditor edits the node in place.  Once the editor closes
        the clue is redrawn automatically and the clue list is refreshed.
        """
        editor = NodeEditor(self.app, self)
        # Wait for the editor window to close.  The editor updates the node
        # directly and triggers a redraw via its on_ok method.  No need
        # to handle result tuples as in earlier versions.
        self.app.wait_window(editor)
        # After editing, refresh the clue list and tasks display.  The
        # NodeEditor already refreshed the canvas; here we update the
        # sidebar (clue list and to‑do list).
        self.app.refresh_clue_list()
        self.app.refresh_sidebar_selection()

    def refresh_text(self):
        """Update the visual text and icon for this node.

        Because the node can be in collapsed or expanded state, and
        properties like the background colour and title can change, the
        simplest way to refresh is to redraw the node entirely.  This
        method therefore delegates to :meth:`draw` after updating the
        internal state.
        """
        # Redraw the node to reflect updated title, description, icon, or
        # background colour.  ``draw`` will remove existing items and create
        # new ones as necessary.
        self.draw()

    # ----- Resizing handlers -----
    def on_resize_press(self, event):
        """Record the starting point and original size when beginning a resize."""
        # Only respond if this node is currently expanded (not collapsed)
        if self.collapsed:
            return
        # Flag that resizing is in progress
        self._resizing = True
        # Convert event coordinates relative to canvas
        self._resize_origin = (event.x, event.y)
        self._orig_size = (self.width, self.height)
        # Prevent event from also triggering move logic
        # Returning "break" stops the event from propagating to the move handler
        return "break"

    def on_resize_drag(self, event):
        """Handle resizing as the mouse moves while holding the handle."""
        if self.collapsed or not hasattr(self, "_resize_origin"):
            return
        sx, sy = self._resize_origin
        ox, oy = sx, sy
        dx = event.x - sx
        dy = event.y - sy
        orig_w, orig_h = self._orig_size
        # Compute new size; enforce minimums
        new_w = max(orig_w + dx, NODE_MIN_WIDTH)
        new_h = max(orig_h + dy, NODE_MIN_HEIGHT)
        # Update internal size and redraw
        self.width = new_w
        self.height = new_h
        self.draw()
        # Update connected edges positions via adjacency index; fallback to scan if missing
        adj = self.app.edges_by_node.get(self.id)
        if adj:
            for eid in adj:
                e = self.app.edges.get(eid)
                if e:
                    e.update_positions()
        else:
            for e in self.app.edges.values():
                if e.src_id == self.id or e.dst_id == self.id:
                    e.update_positions()
        # Prevent event propagation to moving
        return "break"

    def on_resize_release(self, event):
        """Cleanup after resizing finishes."""
        if hasattr(self, "_resize_origin"):
            del self._resize_origin
        if hasattr(self, "_orig_size"):
            del self._orig_size
        # Clear resizing flag
        if hasattr(self, "_resizing"):
            self._resizing = False
        # Prevent event propagation
        return "break"

    def move_by(self, dx, dy):
        self.x += dx
        self.y += dy
        self.app.canvas.move(self.group_tag, dx, dy)
        # Update connected edges via adjacency index; fallback to scan if missing
        adj = self.app.edges_by_node.get(self.id)
        if adj:
            for eid in adj:
                e = self.app.edges.get(eid)
                if e:
                    e.update_positions()
        else:
            for e in self.app.edges.values():
                if e.src_id == self.id or e.dst_id == self.id:
                    e.update_positions()

    def bbox(self):
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def set_selected(self, selected: bool):
        self.app.canvas.itemconfigure(self.rect_id, outline=NODE_SELECTED if selected else NODE_BORDER)

    def serialize(self):
        # When serializing, include additional properties (bg_color,
        # collapsed) and ensure that fields are stored in the new
        # structured format.  Width/height are included for backward
        # compatibility but will be recalculated when loading.
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "image_path": self.image_path,
            "bg_color": self.bg_color,
            "collapsed": self.collapsed,
            "fields": self.fields,
            "width": self.width,
            "height": self.height,
        }


class Edge:
    """Represents a connection between two nodes on the canvas.

    Edges support hiding via the ``hidden`` flag; hidden edges are not
    rendered on the canvas until made visible again.  Colour and label
    can be edited via the context menu.
    """

    def __init__(self, app, edge_id, src_id, dst_id, label="", color=EDGE_COLOR_DEFAULT, *, hidden=False):
        self.app = app
        self.id = edge_id
        self.src_id = src_id
        self.dst_id = dst_id
        self.label = label
        self.color = color or EDGE_COLOR_DEFAULT
        self.hidden = bool(hidden)

        self.group_tag = f"edge_{self.id}"
        self.line_id = None
        self.label_id = None

        self.draw()

    def draw(self):
        """Render the edge on the canvas if not hidden.  Calculates
        anchor points on the source and destination nodes and draws a
        smoothed line with an arrowhead.  A label is drawn above the
        midpoint of the line.  If hidden, no canvas items are created.
        """
        # Remove any existing items first
        c = self.app.canvas
        if c.find_withtag(self.group_tag):
            c.delete(self.group_tag)
        if self.hidden:
            # When hidden, do not draw anything; leave line_id and label_id
            # as None.  Anchor points still rely on node positions but
            # nothing will be rendered.
            self.line_id = None
            self.label_id = None
            return
        x0, y0 = self.anchor_point(self.app.nodes[self.src_id])
        x1, y1 = self.anchor_point(self.app.nodes[self.dst_id])
        self.line_id = c.create_line(
            x0, y0, x1, y1,
            fill=self.color,
            width=2,
            arrow="last",
            smooth=True,
            splinesteps=20,
            tags=(self.group_tag, "edge")
        )
        midx = (x0 + x1) / 2
        midy = (y0 + y1) / 2
        self.label_id = c.create_text(
            midx, midy - 8,
            text=self.label,
            font=("TkDefaultFont", 10, "italic"),
            fill="#000",
            tags=(self.group_tag, "edge_label")
        )
        c.tag_bind(self.group_tag, "<Button-1>", self.on_click)
        c.tag_bind(self.group_tag, "<Double-Button-1>", self.on_double_click)
        # Right‑click context menu for edges
        c.tag_bind(self.group_tag, "<Button-3>", lambda e, ed=self: self.app.show_edge_menu(ed, e))

    def on_click(self, event):
        self.app.select(self)
        self.app.canvas.focus_set()

    def on_double_click(self, event):
        editor = EdgeEditor(self.app, label=self.label, color=self.color)
        self.app.wait_window(editor)
        if editor.result:
            self.label, self.color = editor.result
            self.app.canvas.itemconfigure(self.label_id, text=self.label)
            self.app.canvas.itemconfigure(self.line_id, fill=self.color)

    def update_positions(self):
        """Update the canvas positions of the line and label when nodes move.

        If the edge is hidden, nothing is updated.  Otherwise the line
        endpoints and label midpoint are recalculated.
        """
        if self.hidden or self.line_id is None or self.label_id is None:
            return
        c = self.app.canvas
        x0, y0 = self.anchor_point(self.app.nodes[self.src_id])
        x1, y1 = self.anchor_point(self.app.nodes[self.dst_id])
        c.coords(self.line_id, x0, y0, x1, y1)
        midx = (x0 + x1) / 2
        midy = (y0 + y1) / 2
        c.coords(self.label_id, midx, midy - 8)

    def anchor_point(self, node: Node):
        other = self.app.nodes[self.dst_id] if node.id == self.src_id else self.app.nodes[self.src_id]
        nx = node.x + node.width / 2
        ny = node.y + node.height / 2
        ox = other.x + other.width / 2
        oy = other.y + other.height / 2
        dx = ox - nx
        dy = oy - ny
        if abs(dx) > abs(dy):
            x = node.x + (node.width if dx > 0 else 0)
            y = ny
        else:
            x = nx
            y = node.y + (node.height if dy > 0 else 0)
        return x, y

    def set_selected(self, selected: bool):
        if self.hidden or self.line_id is None:
            return
        self.app.canvas.itemconfigure(self.line_id, fill=EDGE_SELECTED if selected else self.color)

    def serialize(self):
        return {
            "id": self.id,
            "src": self.src_id,
            "dst": self.dst_id,
            "label": self.label,
            "color": self.color,
            "hidden": self.hidden,
        }


class CaseBoardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Case Board")
        self.geometry("1280x760")

        self.nodes = {}
        self.edges = {}
        # Map node_id -> set of edge_ids for fast adjacency lookups
        self.edges_by_node = defaultdict(set)
        self._next_node_id = 1
        self._next_edge_id = 1
        # Primary selection object (Node or Edge).  When multiple nodes
        # are selected via the box‑selection, ``selected`` will be set
        # to ``None`` and the list of nodes will live in ``selected_nodes``.
        self.selected = None
        # Collection of currently selected nodes.  This supports the
        # box‑selection feature allowing multiple clues to be selected and
        # moved together.  When only one clue is selected this list will
        # contain exactly one element; when nothing is selected it will be
        # empty.
        self.selected_nodes = []
        self.mode = "select"  # "select" or "connect"
        self.connect_first = None
        # Per-board to‑do list; list of dicts {"task": str, "done": bool}
        self.todo_list = []
        # Drag state for temporarily unsmoothing edges
        self._drag_active = False
        self._drag_edges = set()
        # Track zoom factor for model<->canvas consistency
        self.zoom = 1.0

        # Remember the most recently saved board data.  This is used as
        # context when chatting with the LLM.  It is set when save_board
        # successfully writes out JSON and remains None until the user
        # performs a save.
        self.last_saved_board_data = None

        self._build_ui()
        self._bind_shortcuts()

    # ---------- UI ----------
    def _build_ui(self):
        # Top toolbar
        toolbar = ttk.Frame(self, padding="6 6 6 6")
        toolbar.pack(side="top", fill="x")

        ttk.Button(toolbar, text="New", command=self.new_board).pack(side="left")
        ttk.Button(toolbar, text="Open…", command=self.load_board).pack(side="left", padx=(6,0))
        ttk.Button(toolbar, text="Save…", command=self.save_board).pack(side="left", padx=(6,0))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Button(toolbar, text="Export PNG", command=self.export_image).pack(side="left")
        ttk.Button(toolbar, text="Export EPS", command=self.export_eps).pack(side="left", padx=(6,0))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        self.mode_var = tk.StringVar(value="select")
        ttk.Radiobutton(toolbar, text="Select/Move", value="select", variable=self.mode_var, command=self.update_mode).pack(side="left")
        ttk.Radiobutton(toolbar, text="Connect", value="connect", variable=self.mode_var, command=self.update_mode).pack(side="left", padx=(6,0))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Button(toolbar, text="Add Clue", command=self.add_node_dialog).pack(side="left")
        # Button for dropping a map pin.  When clicked, prompts the user
        # for an address or area name, attempts to geocode it, and then
        # places a new clue on the board with a pin icon.  See
        # ``add_map_pin_dialog`` for the implementation.
        ttk.Button(toolbar, text="Add Map Pin", command=self.add_map_pin_dialog).pack(side="left", padx=(6,0))
        ttk.Button(toolbar, text="Help", command=self.show_help).pack(side="left", padx=(8,0))

        # Separator before LLM chat button
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        # Chat with the LLM using the last saved board as context
        ttk.Button(toolbar, text="Chat with LLM", command=self.chat_with_llm).pack(side="left")

        # Main area: use a horizontal PanedWindow to allow the sidebar width
        # to be adjusted by the user.  The first pane holds the canvas and
        # scrollbars; the second pane holds the sidebar.
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(side="top", fill="both", expand=True)

        # Canvas with scrollbars contained in its own frame
        canvas_frame = ttk.Frame(paned)
        self.canvas = tk.Canvas(canvas_frame, bg=CANVAS_BG, scrollregion=(0,0,4000,4000))
        hbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="we")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        # Sidebar frame with a fixed initial width; the PanedWindow will manage
        # the geometry so the user can drag to resize it.  We disable
        # propagation so the width remains constant until the user drags.
        self.sidebar = ttk.Frame(paned, width=SIDEBAR_WIDTH, padding=8)
        self.sidebar.pack_propagate(False)
        self._build_sidebar(self.sidebar)

        # Add frames to the paned window; assign weights to control initial
        # proportions.  A higher weight on the canvas gives it more space.
        paned.add(canvas_frame, weight=3)
        paned.add(self.sidebar, weight=1)

        # Canvas bindings
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<ButtonPress-2>", self._start_pan)
        self.canvas.bind("<B2-Motion>", self._do_pan)
        # Allow zooming with the scroll wheel even without holding the
        # Control modifier; bind both variants.  On Windows/Mac the
        # delta value will be positive for up and negative for down.
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom)
        self.canvas.bind("<MouseWheel>", self._on_zoom)
        # Box selection bindings: when the left mouse button is pressed on
        # empty canvas space, begin drawing a selection rectangle.  Drag
        # updates the rectangle and selects all nodes within.  Releasing
        # finalises the selection.
        self.canvas.bind("<ButtonPress-1>", self._start_box_select, add="+")
        self.canvas.bind("<B1-Motion>", self._update_box_select, add="+")
        self.canvas.bind("<ButtonRelease-1>", self._end_box_select, add="+")

    def _build_sidebar(self, parent):
        # All clues list with search.  Only this panel remains in the sidebar; detailed
        # editing now occurs in the Edit Clue window.
        ttk.Label(parent, text="All Clues", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill="x", pady=(2,6))
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side="left", fill="x", expand=True)
        ttk.Button(search_frame, text="Clear", command=lambda: self.search_var.set("")).pack(side="left", padx=(6,0))
        self.search_var.trace_add("write", lambda *args: self.refresh_clue_list())

        self.clue_list = tk.Listbox(parent, height=10)
        self.clue_list.pack(fill="both", expand=True)
        self.clue_list.bind("<<ListboxSelect>>", self._on_clue_pick)

        # Separator between clue list and to‑do section
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(8,4))

        # To‑Do section with tabs for pending and completed tasks
        ttk.Label(parent, text="To‑Do Items", font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        # Notebook for pending/completed
        self.todo_notebook = ttk.Notebook(parent)
        self.todo_notebook.pack(fill="both", expand=False)
        # Pending tab
        pending_tab = ttk.Frame(self.todo_notebook)
        self.todo_notebook.add(pending_tab, text="Pending")
        pending_tab.columnconfigure(0, weight=1)
        pending_tab.rowconfigure(0, weight=1)
        # Listbox for pending tasks
        pending_frame = ttk.Frame(pending_tab)
        pending_frame.grid(row=0, column=0, sticky="nsew")
        self.todo_pending_listbox = tk.Listbox(pending_frame, height=6)
        self.todo_pending_listbox.pack(side="left", fill="both", expand=True)
        pend_scroll = ttk.Scrollbar(pending_frame, orient="vertical", command=self.todo_pending_listbox.yview)
        pend_scroll.pack(side="left", fill="y")
        self.todo_pending_listbox.configure(yscrollcommand=pend_scroll.set)
        # Completed tab
        completed_tab = ttk.Frame(self.todo_notebook)
        self.todo_notebook.add(completed_tab, text="Completed")
        completed_tab.columnconfigure(0, weight=1)
        completed_tab.rowconfigure(0, weight=1)
        completed_frame = ttk.Frame(completed_tab)
        completed_frame.grid(row=0, column=0, sticky="nsew")
        self.todo_completed_listbox = tk.Listbox(completed_frame, height=6)
        self.todo_completed_listbox.pack(side="left", fill="both", expand=True)
        comp_scroll = ttk.Scrollbar(completed_frame, orient="vertical", command=self.todo_completed_listbox.yview)
        comp_scroll.pack(side="left", fill="y")
        self.todo_completed_listbox.configure(yscrollcommand=comp_scroll.set)

        # Buttons for task operations (applies to whichever tab is active)
        tbtn = ttk.Frame(parent)
        tbtn.pack(anchor="w", pady=(4,0))
        ttk.Button(tbtn, text="Add", command=self.add_task).pack(side="left")
        ttk.Button(tbtn, text="Edit", command=self.edit_task).pack(side="left", padx=(4,0))
        ttk.Button(tbtn, text="Remove", command=self.remove_task).pack(side="left", padx=(4,0))
        ttk.Button(tbtn, text="Toggle", command=self.toggle_task_done).pack(side="left", padx=(4,0))

        # LLM query for to‑do leads
        ttk.Label(parent, text="Generate To‑Do Leads", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(6,0))
        llm_frame = ttk.Frame(parent)
        llm_frame.pack(fill="x", pady=(2,0))
        # We no longer ask the user for a free‑form prompt when generating
        # leads; instead, we use the currently selected clue as context.
        # Therefore the text entry is omitted here.  The button label
        # reflects the configurable number of tasks defined in NUM_TASK_LEADS.
        self.todo_llm_query_var = tk.StringVar()  # retained for backward compatibility
        ttk.Button(llm_frame, text=f"Generate {NUM_TASK_LEADS}", command=self.generate_todo_leads).pack(side="left")

        # Manual case conjecture button: placed at bottom of sidebar
        ttk.Button(parent, text="Case Conjecture", command=self.generate_case_conjecture_manual).pack(anchor="e", pady=(6,0))

        # Populate the clue list and to‑do lists initially
        self.refresh_clue_list()
        self.refresh_todo_listbox()

    # ---------- Shortcuts ----------
    def _bind_shortcuts(self):
        self.bind("<Delete>", self.on_delete)
        self.bind("<BackSpace>", self.on_delete)
        self.bind("<Control-s>", lambda e: self.save_board())
        self.bind("<Control-o>", lambda e: self.load_board())
        self.bind("<Control-n>", lambda e: self.new_board())
        self.bind("<Key-a>", lambda e: self.add_node_dialog())
        self.bind("<Key-A>", lambda e: self.add_node_dialog())
        self.bind("<Key-c>", lambda e: self.toggle_connect())
        self.bind("<Key-C>", lambda e: self.toggle_connect())
        self.bind("<Key-e>", lambda e: self.edit_selected_node())
        self.bind("<Key-E>", lambda e: self.edit_selected_node())
        self.bind("<Key-f>", lambda e: self.add_field())
        self.bind("<Key-F>", lambda e: self.add_field())

    # ---------- Sidebar helpers ----------
    def refresh_clue_list(self):
        query = (self.search_var.get() or "").lower().strip()
        self.clue_list.delete(0, "end")
        items = []
        for nid, node in sorted(self.nodes.items(), key=lambda kv: kv[0]):
            label = f"{nid}: {node.title}"
            if not query or query in label.lower():
                items.append((nid, label))
        for _, label in items:
            self.clue_list.insert("end", label)

    def _on_clue_pick(self, event):
        sel = self.clue_list.curselection()
        if not sel: return
        label = self.clue_list.get(sel[0])
        try:
            nid = int(label.split(":")[0])
        except Exception:
            return
        node = self.nodes.get(nid)
        if node:
            self.select(node)

    def refresh_sidebar_selection(self):
        """Refresh the sidebar when the selection changes.

        In the simplified sidebar, we no longer display per‑clue details.
        Instead this method simply refreshes the to‑do list so that any
        changes to tasks are reflected immediately.  Clue selection
        highlighting is handled automatically by the Listbox widget.
        """
        self.refresh_todo_listbox()

    def refresh_todo_listbox(self):
        """Refresh both the pending and completed to‑do listboxes to reflect current tasks."""
        # Skip if not yet built
        if not hasattr(self, "todo_pending_listbox"):
            return
        self.todo_pending_listbox.delete(0, "end")
        self.todo_completed_listbox.delete(0, "end")
        for idx, task in enumerate(self.todo_list):
            done = task.get("done", False)
            text = task.get("task", "")
            prefix = "✓ " if done else "☐ "
            if done:
                self.todo_completed_listbox.insert("end", prefix + text)
            else:
                self.todo_pending_listbox.insert("end", prefix + text)

    # ---------- Node & Edge ops ----------
    def update_mode(self):
        self.mode = self.mode_var.get()
        self.connect_first = None
        self.status_message(f"Mode: {self.mode.title()}")

    def toggle_connect(self):
        self.mode_var.set("connect" if self.mode != "connect" else "select")
        self.update_mode()

    def status_message(self, msg):
        self.title(f"Case Board — {msg}")

    def add_node_dialog(self):
        """Show a dialog for creating a new clue and add it to the board."""
        editor = NodeEditor(self, None)
        self.wait_window(editor)
        if editor.result:
            # Unpack the title, description, icon, image and fields for the new node
            if len(editor.result) == 4:
                title, desc, icon_sym, image_path = editor.result
                fields = {}
            else:
                title, desc, icon_sym, image_path, fields = editor.result
            # Position the new node near the centre of the canvas
            x = self.canvas.canvasx(self.winfo_width() // 2 - NODE_WIDTH // 2 - 160)
            y = self.canvas.canvasy(self.winfo_height() // 2 - NODE_HEIGHT // 2 - 40)
            self.add_node(x, y, title, desc, icon_sym, image_path, fields=fields)

    def add_node(self, x, y, title, description, icon="", image_path="", *, bg_color=NODE_BG, collapsed=False, fields=None):
        """Create a new node on the canvas and register it.

        Additional properties such as ``bg_color`` and ``collapsed`` are
        passed through to the Node constructor.  ``fields`` should be a
        mapping of field titles to either plain strings or structured
        dictionaries; see :class:`Node` for details.
        """
        node_id = self._next_node_id
        self._next_node_id += 1
        node = Node(
            self,
            node_id,
            x,
            y,
            title,
            description,
            icon=icon,
            image_path=image_path,
            bg_color=bg_color,
            collapsed=collapsed,
            fields=fields or {},
        )
        self.nodes[node_id] = node
        self.select(node)
        self.refresh_clue_list()
        return node

    def add_edge(self, src_id, dst_id, label="", color=EDGE_COLOR_DEFAULT, *, hidden=False, edge_id=None):
        """Create a new edge between two nodes.

        If ``hidden`` is True, the edge will be created but not drawn until
        made visible.  Returns the created Edge instance or ``None`` on
        failure.
        """
        if src_id == dst_id:
            messagebox.showinfo("Oops", "Pick two different clues to connect.")
            return None
        if edge_id is None:
            edge_id = self._next_edge_id
            self._next_edge_id += 1
        else:
            # Ensure next id stays ahead of explicit ids
            self._next_edge_id = max(self._next_edge_id, edge_id + 1)
        edge = Edge(self, edge_id, src_id, dst_id, label, color=color, hidden=hidden)
        self.edges[edge_id] = edge
        # Update adjacency index
        self.edges_by_node[src_id].add(edge_id)
        self.edges_by_node[dst_id].add(edge_id)
        self.select(edge)
        return edge

    def handle_connect_click(self, node: 'Node'):
        if self.connect_first is None:
            self.connect_first = node
            self.status_message(f"Connect: first is “{node.title}”. Now click another clue.")
        else:
            second = node
            # Ask label and color
            editor = EdgeEditor(self, label="", color=EDGE_COLOR_DEFAULT)
            self.wait_window(editor)
            if editor.result is None:
                self.connect_first = None
                self.mode_var.set("select")
                self.update_mode()
                return
            label, color = editor.result
            self.add_edge(self.connect_first.id, second.id, label, color=color or EDGE_COLOR_DEFAULT)
            self.connect_first = None
            self.mode_var.set("select")
            self.update_mode()

    def on_canvas_click(self, event):
        if self.mode == "select":
            self.select(None)

    def select(self, obj):
        """Select a single node or edge, clearing prior selections.

        When ``obj`` is a :class:`Node`, this method clears any
        multi‑selection state, deselects previously selected nodes, and
        highlights the chosen node.  For edges, the highlighting logic
        remains unchanged.  Passing ``None`` deselects everything.
        """
        # Deselect previously selected nodes (multi selection)
        if self.selected_nodes:
            for node in self.selected_nodes:
                node.set_selected(False)
            self.selected_nodes = []
        # Deselect previously selected edge (single)
        if isinstance(self.selected, Node):
            self.selected.set_selected(False)
        elif isinstance(self.selected, Edge):
            self.selected.set_selected(False)

        # Assign new selection
        self.selected = obj

        if isinstance(obj, Node):
            # Select only this node
            self.selected_nodes = [obj]
            obj.set_selected(True)
            self.status_message(f"Selected clue: {obj.title}")
        elif isinstance(obj, Edge):
            obj.set_selected(True)
            src = self.nodes[obj.src_id].title
            dst = self.nodes[obj.dst_id].title
            self.status_message(f"Selected thread: {src} → {dst} ({obj.label})")
        else:
            self.status_message("Ready")
        # Refresh sidebar to reflect the new selection
        self.refresh_sidebar_selection()

    def on_delete(self, event=None):
        """Delete the currently selected node(s) or edge.

        When multiple nodes are selected via the box selection this
        method deletes all of them.  Deleting a node also removes any
        connected edges.  After deletion the selection is cleared and
        the clue list is refreshed.
        """
        # Nothing selected
        if not self.selected and not self.selected_nodes:
            return
        # Delete multiple nodes if present
        if self.selected_nodes:
            for node in list(self.selected_nodes):
                self.delete_node(node)
            self.selected_nodes.clear()
            self.selected = None
        elif isinstance(self.selected, Node):
            self.delete_node(self.selected)
            self.selected = None
        elif isinstance(self.selected, Edge):
            self.delete_edge(self.selected)
            self.selected = None
        # Clear any remaining highlights
        self.refresh_clue_list()
        self.select(None)

    def delete_node(self, node: 'Node'):
        to_remove = [e for e in list(self.edges.values()) if e.src_id == node.id or e.dst_id == node.id]
        for e in to_remove:
            self.delete_edge(e)
        self.canvas.delete(node.group_tag)
        self.nodes.pop(node.id, None)

    def delete_edge(self, edge: 'Edge'):
        self.canvas.delete(edge.group_tag)
        self.edges.pop(edge.id, None)
        # Remove from adjacency index
        try:
            self.edges_by_node[edge.src_id].discard(edge.id)
            self.edges_by_node[edge.dst_id].discard(edge.id)
        except Exception:
            pass

    # ---------- Drag smoothing control ----------
    def begin_drag(self, nodes):
        if self._drag_active:
            return
        affected = set()
        for n in nodes:
            affected.update(self.edges_by_node.get(n.id, set()))
        self._drag_edges = affected
        for eid in affected:
            e = self.edges.get(eid)
            if e and e.line_id:
                # Disable smoothing for better performance while dragging
                self.canvas.itemconfigure(e.line_id, smooth=False)
        self._drag_active = True

    def end_drag(self):
        if not self._drag_active:
            return
        for eid in self._drag_edges:
            e = self.edges.get(eid)
            if e and e.line_id:
                # Restore smoothing and ensure positions are up to date
                self.canvas.itemconfigure(e.line_id, smooth=True)
                e.update_positions()
        self._drag_edges = set()
        self._drag_active = False

    # ---------- Sidebar actions ----------
    def add_field(self, event=None):
        """Prompt the user to add a new field to the selected clue.

        This quick‑add dialog allows adding a key/value pair to the
        currently selected node.  The new field will be visible by
        default.  After adding, the clue is redrawn and the clue list
        refreshed.
        """
        # Determine the target node: use the explicitly selected node or
        # fallback to the first entry in selected_nodes.  If more than
        # one node is selected there is no obvious target so bail out.
        target = None
        if isinstance(self.selected, Node):
            target = self.selected
        elif len(self.selected_nodes) == 1:
            target = self.selected_nodes[0]
        else:
            return
        key = simpledialog.askstring("Add Field", "Field title:", parent=self)
        if not key:
            return
        val = simpledialog.askstring("Add Field", f"Value for '{key}':", parent=self)
        if val is None:
            return
        # Create a structured field entry with defaults
        target.fields[key] = {
            "value": val,
            "visible": True,
            "file_link": None,
            "image_path": None,
        }
        # Redraw the node to reflect the new field
        target.refresh_text()
        # Refresh the clue list to update sorting/searching
        self.refresh_clue_list()

    def edit_selected_node(self, event=None):
        """Open the editor for the currently selected clue.

        If exactly one node is selected (either via single selection or
        multi‑selection), open the editor for that node.  When multiple
        nodes are selected this method does nothing since editing
        multiple nodes simultaneously is not supported.
        """
        target = None
        if isinstance(self.selected, Node):
            target = self.selected
        elif len(self.selected_nodes) == 1:
            target = self.selected_nodes[0]
        if not isinstance(target, Node):
            return
        target.on_double_click(None)

    # ---------- File ops ----------
    def save_board(self):
        path = filedialog.asksaveasfilename(
            title="Save board as…",
            defaultextension=".json",
            filetypes=[("Case Board JSON", "*.json")]
        )
        if not path:
            return
        data = {
            "nodes": [n.serialize() for n in self.nodes.values()],
            "edges": [e.serialize() for e in self.edges.values()],
            "todo_list": self.todo_list,
            "next_ids": {"node": self._next_node_id, "edge": self._next_edge_id},
            # Use version 3 to indicate support for bg_color, collapsed and hidden fields
            "version": 3,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.status_message(f"Saved: {os.path.basename(path)}")
            # Remember the last saved board state for LLM chat.  This makes
            # it possible to include the board JSON as context when chatting
            # with the LLM later.
            self.last_saved_board_data = data
            # After saving, generate a conjecture about where the case might lead.
            # Call the LLM with the current board data and display the analysis in a separate window.
            try:
                self.show_case_conjecture_window(data)
            except Exception as e:
                # If LLM call fails, log or show a warning but continue
                print(f"LLM conjecture generation failed: {e}")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def show_case_conjecture_window(self, board_data: dict):
        """Generate a one-paragraph conjecture using the entire board and display it in a new window.

        This method is called after the board is saved.  It sends the
        board's JSON representation to the LLM via the chat API and
        requests a single paragraph conjecture about where the case
        might lead.  The response is displayed in a separate top‑right
        window.

        :param board_data: The board data dictionary as saved to JSON.
        """
        # Convert board data to a JSON string for the prompt
        try:
            board_json = json.dumps(board_data, ensure_ascii=False, indent=2)
        except Exception:
            board_json = str(board_data)
        # Build prompt instructing the LLM to analyze the board and produce a conjecture
        prompt = (
            "You are an investigative assistant. Given the following case board in JSON format, "
            "provide a brief one-paragraph conjecture about possible future directions or hypotheses "
            "that the investigation could explore. Summarize in 3–5 sentences.\n\n"
            f"Board JSON:\n{board_json}"
        )
        # Prepare the chat payload for Ollama
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
		
        }
        conjecture = ""
        try:
            response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            content = ""
            if isinstance(data, dict):
                # Data may include 'message' or 'messages'
                if "message" in data and isinstance(data["message"], dict):
                    content = data["message"].get("content", "")
                elif "messages" in data and data["messages"]:
                    # Use the content of the last assistant message
                    content = data["messages"][-1].get("content", "")
                else:
                    content = str(data)
            else:
                content = str(data)
            conjecture = content.strip()
            if not conjecture:
                conjecture = "LLM returned an empty response."
        except Exception as e:
            conjecture = f"Failed to generate conjecture: {e}"
        # Create a top-level window to display the conjecture
        win = tk.Toplevel(self)
        win.title("Case Conjecture")
        # Text widget to show the paragraph
        text = tk.Text(win, wrap="word", height=8, width=60)
        text.pack(fill="both", expand=True)
        text.insert("1.0", conjecture)
        text.config(state="disabled")
        # Position window at the top-right of the main app window
        try:
            # Make sure geometry is computed
            self.update_idletasks()
            root_x = self.winfo_rootx()
            root_y = self.winfo_rooty()
            root_w = self.winfo_width()
            # Determine window size based on content length (approximate)
            win_w = min(max(400, int(self.winfo_width() * 0.4)), 800)
            win_h = min(max(200, int(self.winfo_height() * 0.3)), 400)
            # Place 20 px away from right and top edges
            pos_x = root_x + root_w - win_w - 20
            pos_y = root_y + 20
            win.geometry(f"{win_w}x{win_h}+{int(pos_x)}+{int(pos_y)}")
        except Exception:
            # Fallback geometry
            win.geometry("600x300")
        # Ensure the window stays on top of the main window but does not grab focus
        win.transient(self)

    def generate_case_conjecture_manual(self):
        """Manually generate a case conjecture without saving the board.

        This method serializes the current board state into a dictionary
        (including nodes, edges, to-do list, and source documents) and
        calls the LLM analysis method to display a conjecture.  It is
        triggered by the "Case Conjecture" button in the sidebar.
        """
        # Compose the board data similar to save_board but without writing to a file
        data = {
            "nodes": [n.serialize() for n in self.nodes.values()],
            "edges": [e.serialize() for e in self.edges.values()],
            "todo_list": self.todo_list,
            # Include source_docs if present on the app; default to []
            "source_docs": getattr(self, "source_docs", []),
            "next_ids": {"node": self._next_node_id, "edge": self._next_edge_id},
            "version": 3,
        }
        try:
            self.show_case_conjecture_window(data)
        except Exception as e:
            messagebox.showerror("LLM Error", str(e), parent=self)

    # ---------- Chat with LLM ----------
    def chat_with_llm(self):
        """Open a chat window to converse with the LLM using the last saved board as context.

        This feature allows investigators to ask follow‑up questions or
        brainstorm ideas with the LLM while keeping the board's state in
        context.  The conversation is initialized with a system message
        containing the JSON representation of the most recently saved
        board.  If the user has not saved the board yet, they are
        prompted to do so.
        """
        # Ensure there is saved board data to use as context
        if not getattr(self, "last_saved_board_data", None):
            messagebox.showinfo(
                "LLM Chat",
                "Please save the board at least once before starting a chat. The chat uses the last saved board as context.",
                parent=self,
            )
            return
        # Serialize the last saved board data
        try:
            board_json = json.dumps(self.last_saved_board_data, ensure_ascii=False, indent=2)
        except Exception:
            board_json = str(self.last_saved_board_data)
        # Construct the system prompt to provide context to the LLM
        system_prompt = (
            "You are an investigative assistant. The user will ask questions about their case board. "
            "Use the following JSON representation of the board as context for your responses. "
            "If the user asks about clues, threads, or tasks, refer to the information in the JSON. "
            "Board JSON:\n"
            f"{board_json}"
        )
        # Create chat window
        win = tk.Toplevel(self)
        win.title("Chat with LLM")
        win.geometry("500x500")
        # Conversation display
        text_display = tk.Text(win, wrap="word", state="disabled")
        text_display.pack(fill="both", expand=True, padx=8, pady=(8,4))
        # Entry and send frame
        entry_frame = ttk.Frame(win)
        entry_frame.pack(fill="x", padx=8, pady=(0,8))
        entry_var = tk.StringVar()
        entry_widget = ttk.Entry(entry_frame, textvariable=entry_var)
        entry_widget.pack(side="left", fill="x", expand=True)
        # Chat state: messages to send to the API.  Start with system message.
        messages = [{"role": "system", "content": system_prompt}]

        def append_message(role: str, content: str):
            """Helper to append a message to the display."""
            text_display.configure(state="normal")
            prefix = "You: " if role == "user" else "LLM: " if role == "assistant" else ""
            text_display.insert("end", f"{prefix}{content.strip()}\n")
            text_display.see("end")
            text_display.configure(state="disabled")

        def send():
            """Handle sending a user message and receiving the LLM's reply."""
            user_text = entry_var.get().strip()
            if not user_text:
                return
            entry_var.set("")
            # Append user message locally and display
            messages.append({"role": "user", "content": user_text})
            append_message("user", user_text)
            # Send conversation to LLM
            try:
                payload = {
                    "model": LLM_MODEL,
                    "messages": messages,
                }
                response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
                response.raise_for_status()
                data = response.json()
                assistant_content = ""
                if isinstance(data, dict):
                    if "message" in data and isinstance(data["message"], dict):
                        assistant_content = data["message"].get("content", "")
                    elif "messages" in data and data["messages"]:
                        assistant_content = data["messages"][-1].get("content", "")
                    else:
                        assistant_content = str(data)
                else:
                    assistant_content = str(data)
            except Exception as e:
                assistant_content = f"Error while contacting LLM: {e}"
            # Append assistant message to state and display
            messages.append({"role": "assistant", "content": assistant_content})
            append_message("assistant", assistant_content)
        # Send on button click
        send_btn = ttk.Button(entry_frame, text="Send", command=send)
        send_btn.pack(side="left", padx=(4,0))
        # Also send when pressing Enter in the entry widget
        def on_enter(event):
            send()
            return "break"
        entry_widget.bind("<Return>", on_enter)
        # Focus on entry
        entry_widget.focus_set()

    def load_board(self):
        path = filedialog.askopenfilename(
            title="Open board…",
            filetypes=[("Case Board JSON", "*.json")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))
            return

        self.clear_board()

        for n in data.get("nodes", []):
            # Read properties with backward compatibility: older data may not
            # include bg_color or collapsed.  Use defaults if missing.
            node = self.add_node(
                n.get("x", 50),
                n.get("y", 50),
                n.get("title", ""),
                n.get("description", ""),
                icon=n.get("icon", ""),
                image_path=n.get("image_path", ""),
                bg_color=n.get("bg_color", NODE_BG),
                collapsed=n.get("collapsed", False),
                fields=n.get("fields", {}),
            )
            node.id = n.get("id", node.id)
            # Ensure id mapping uses loaded id in case of non sequential ids
            self.nodes[node.id] = node

        for e in data.get("edges", []):
            # Accept the hidden flag when present
            edge = self.add_edge(
                e.get("src"),
                e.get("dst"),
                e.get("label", ""),
                color=e.get("color", EDGE_COLOR_DEFAULT),
                hidden=e.get("hidden", False),
                edge_id=e.get("id"),
            )
            if edge:
                # Draw now that properties are set
                edge.draw()

        # Restore todo list
        self.todo_list = data.get("todo_list", [])

        next_ids = data.get("next_ids", {})
        self._next_node_id = max(self._next_node_id, next_ids.get("node", self._next_node_id))
        self._next_edge_id = max(self._next_edge_id, next_ids.get("edge", self._next_edge_id))
        self.status_message(f"Opened: {os.path.basename(path)}")
        self.refresh_clue_list()

    def new_board(self):
        if self.nodes or self.edges:
            if not messagebox.askyesno("New board", "Start a new board and discard the current one?"):
                return
        self.clear_board()
        self.status_message("New board")

    def clear_board(self):
        self.canvas.delete("all")
        self.nodes.clear()
        self.edges.clear()
        self.edges_by_node.clear()
        self._next_node_id = 1
        self._next_edge_id = 1
        self.todo_list = []
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<ButtonPress-2>", self._start_pan)
        self.canvas.bind("<B2-Motion>", self._do_pan)
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom)
        self.refresh_clue_list()
        self.refresh_sidebar_selection()

    # ---------- Export ----------
    def export_image(self):
        if not PIL_AVAILABLE:
            messagebox.showinfo(
                "PNG export needs Pillow",
                "PNG export requires Pillow (PIL). You can still export EPS (vector) via 'Export EPS'.\n\n"
                "Install Pillow:\n    pip install Pillow"
            )
            return
        path = filedialog.asksaveasfilename(
            title="Export as PNG…",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")]
        )
        if not path:
            return
        tmp_eps = path + ".eps"
        try:
            x0 = int(self.canvas.canvasx(0))
            y0 = int(self.canvas.canvasy(0))
            x1 = x0 + int(self.canvas.winfo_width())
            y1 = y0 + int(self.canvas.winfo_height())
            self.canvas.postscript(file=tmp_eps, colormode='color', pagewidth=x1 - x0, pageheight=y1 - y0)
            img = Image.open(tmp_eps)
            img.save(path, "PNG")
            os.remove(tmp_eps)
            self.status_message(f"Exported PNG: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
            try:
                if os.path.exists(tmp_eps):
                    os.remove(tmp_eps)
            except Exception:
                pass

    def export_eps(self):
        path = filedialog.asksaveasfilename(
            title="Export as EPS…",
            defaultextension=".eps",
            filetypes=[("Encapsulated PostScript", "*.eps")]
        )
        if not path:
            return
        try:
            x0 = int(self.canvas.canvasx(0))
            y0 = int(self.canvas.canvasy(0))
            x1 = x0 + int(self.canvas.winfo_width())
            y1 = y0 + int(self.canvas.winfo_height())
            self.canvas.postscript(file=path, colormode='color', pagewidth=x1 - x0, pageheight=y1 - y0)
            self.status_message(f"Exported EPS: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    # ---------- Pan/Zoom ----------
    def _start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        # Scale all canvas items visually
        self.canvas.scale("all", x, y, factor, factor)
        # Sync model coordinates so future computations (edges, redraws) align
        for node in self.nodes.values():
            node.x = x + factor * (node.x - x)
            node.y = y + factor * (node.y - y)
            node.width *= factor
            node.height *= factor
        # Recompute edges from model to avoid drift
        for edge in self.edges.values():
            edge.update_positions()
        self.zoom *= factor

    # ---------- Map pins ----------
    def add_map_pin_dialog(self):
        """Prompt the user to drop a map pin for an address or area.

        This method opens a simple input dialog requesting a human‑readable
        location description (for example, "Eiffel Tower, Paris" or
        "Golden Gate Park").  It attempts to geocode the string using
        :func:`geocode_address` and, if successful, embeds the resulting
        latitude and longitude into the clue's description and custom
        fields.  Should the geocoding fail, the clue is still created
        with the entered address as its title and description.  A map pin
        is represented by the 📍 emoji.
        """
        address = simpledialog.askstring("Add Map Pin", "Enter address or area:", parent=self)
        if not address:
            return
        coords = geocode_address(address)
        desc = ""
        fields = {}
        if coords:
            lat, lon = coords
            # Format coordinates for display; include four decimal places
            desc = f"{lat:.4f}, {lon:.4f}"
            # Store coordinates in separate custom fields so they can be
            # accessed later (for example when exporting or inspecting)
            fields = {
                "Latitude": {"value": str(lat), "visible": True, "file_link": None, "image_path": None},
                "Longitude": {"value": str(lon), "visible": True, "file_link": None, "image_path": None},
            }
        else:
            # If geocoding failed, use the address in the description as
            # well so there is some meaningful text on the clue card.
            desc = address
        # Position the new pin near the centre of the current viewport
        x = self.canvas.canvasx(self.winfo_width() // 2 - NODE_WIDTH // 2)
        y = self.canvas.canvasy(self.winfo_height() // 2 - NODE_HEIGHT // 2)
        node = self.add_node(x, y, address, desc, icon="📍", image_path="", fields=fields)
        # Automatically select the new pin so the user receives feedback
        self.select(node)
        # Update the clue list to include the new entry
        self.refresh_clue_list()

    # ---------- Box selection ----------
    def _start_box_select(self, event):
        """Initiate a rectangular selection on the canvas.

        A selection rectangle is only created when the click occurs on
        empty canvas space in select mode.  Clicking on a clue or edge
        falls through to the usual selection mechanics defined on those
        items.  The selection rectangle is drawn with a dashed outline
        and removed once the selection completes.
        """
        # Only respond in select mode
        if self.mode != "select":
            return
        # Determine if the click was on an existing canvas item
        current = self.canvas.find_withtag("current")
        if current:
            tags = self.canvas.gettags(current)
            # If clicked on a node, edge or resize handle, do not start box selection
            for t in tags:
                if t.startswith("node_") or t.startswith("edge_") or t.startswith("resize_handle_"):
                    return
        # Convert to canvas coordinates in case the canvas is scrolled
        start_x = self.canvas.canvasx(event.x)
        start_y = self.canvas.canvasy(event.y)
        self._box_active = True
        self._box_start = (start_x, start_y)
        # Remove any existing selection rectangle
        if hasattr(self, "_box_rect") and self._box_rect:
            try:
                self.canvas.delete(self._box_rect)
            except Exception:
                pass
        # Clear any existing selection
        self.select(None)
        # Draw the initial rectangle (zero size)
        self._box_rect = self.canvas.create_rectangle(
            start_x, start_y, start_x, start_y,
            outline=NODE_SELECTED,
            dash=(4, 2),
            width=1,
            tags=("selection_rect",)
        )

    def _update_box_select(self, event):
        """Update the selection rectangle as the pointer moves.

        While the user drags the mouse with the left button held down,
        the selection rectangle is resized.  All nodes whose bounding
        boxes intersect the rectangle are marked as selected.  If the
        selection rectangle is not active, this method does nothing.
        """
        if not getattr(self, "_box_active", False):
            return
        # Current pointer location in canvas coordinates
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        x0, y0 = self._box_start
        # Update the rectangle on the canvas
        self.canvas.coords(self._box_rect, x0, y0, cur_x, cur_y)
        # Compute normalised rectangle bounds
        left, right = sorted([x0, cur_x])
        top, bottom = sorted([y0, cur_y])
        # Determine which nodes intersect the selection rectangle
        new_selection = []
        for node in self.nodes.values():
            nx0, ny0, nx1, ny1 = node.bbox()
            # Simple bounding box intersection check
            if not (nx1 < left or nx0 > right or ny1 < top or ny0 > bottom):
                new_selection.append(node)
        # Update highlighting: deselect nodes not in new_selection
        # Note: set difference to avoid unnecessary redraws
        for node in list(self.selected_nodes):
            if node not in new_selection:
                node.set_selected(False)
        # Highlight newly selected nodes
        for node in new_selection:
            if node not in self.selected_nodes:
                node.set_selected(True)
        self.selected_nodes = new_selection
        # When more than one node is selected, clear the single object
        if len(self.selected_nodes) == 1:
            self.selected = self.selected_nodes[0]
            self.status_message(f"Selected clue: {self.selected.title}")
        elif self.selected_nodes:
            self.selected = None
            self.status_message(f"Selected {len(self.selected_nodes)} clues")
        else:
            self.selected = None
            self.status_message("Ready")

    def _end_box_select(self, event):
        """Finalize a box selection by removing the rectangle.

        Once the mouse button is released the dashed selection rectangle
        is deleted.  If no nodes were selected the state will revert
        back to no selection.  This method also resets the internal
        selection rectangle state variables.
        """
        if not getattr(self, "_box_active", False):
            return
        # Remove the rectangle from the canvas
        if hasattr(self, "_box_rect") and self._box_rect:
            try:
                self.canvas.delete(self._box_rect)
            except Exception:
                pass
        # Reset internal state
        self._box_active = False
        self._box_rect = None
        self._box_start = None
        # Update status message if nothing selected
        if not self.selected_nodes:
            self.status_message("Ready")

    def show_help(self):
        messagebox.showinfo(
            "Help",
            "Quick Tips:\n"
            "• A: Add Clue  • C: Toggle Connect  • E: Edit selected  • F: Add Field  • Del: Delete\n"
            "• Connect mode: click a first clue, then a second; edit label & color.\n"
            "• Double‑click a clue to edit; double‑click a thread to edit label/color.\n"
            "• Sidebar shows all clues (searchable) and details for the selection; add custom fields.\n"
            "• Icons: use Set Icon or the editor; choices include 📍 🏢 🏬 🏠 👤 🚗 ☎️ ✉️ 📄.\n"
            "• Save/Open uses JSON (backward‑compatible).\n"
            "• Export PNG needs Pillow; EPS works without it.\n"
            "\nShortcuts:\n"
            "• Ctrl+N New  • Ctrl+O Open  • Ctrl+S Save  • Middle‑drag to pan  • Ctrl+Wheel to zoom"
        )

    # ---------- Context menus ----------
    def show_node_menu(self, node: Node, event):
        """Display a context menu for the given node at the pointer location."""
        menu = tk.Menu(self, tearoff=False)
        # Edit node
        menu.add_command(label="Edit", command=lambda: node.on_double_click(None))
        # Delete node
        menu.add_command(label="Delete", command=lambda: self.delete_node(node))
        # Collapse/Expand
        if node.collapsed:
            menu.add_command(label="Expand", command=lambda: self._toggle_node_collapse(node))
        else:
            menu.add_command(label="Collapse", command=lambda: self._toggle_node_collapse(node))
        # Change background colour
        menu.add_command(label="Change Background Color", command=lambda: self._change_node_color(node))
        # Resize node
        menu.add_command(label="Resize…", command=lambda: self._resize_node_dialog(node))
        # Generate leads.  Use the global NUM_LEADS to determine how many
        # suggestions to request from the LLM.  The label is updated to
        # reflect this configurable value.
        menu.add_command(label=f"Generate {NUM_LEADS} Leads…", command=lambda: self._generate_leads(node))
        # Add Clue option to quickly create a new clue without returning to
        # the toolbar.  This appears in all node context menus.
        menu.add_separator()
        menu.add_command(label="Add Clue", command=self.add_node_dialog)
        # Display menu and ensure it is dismissed when focus is lost.  The
        # FocusOut binding triggers whenever the menu loses focus (e.g.
        # when the user clicks anywhere outside of it).  Without this,
        # certain environments may leave the menu visible until another
        # right‑click occurs.
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            # Bind to close the menu on focus loss
            menu.bind("<FocusOut>", lambda e: menu.unpost())

    def show_edge_menu(self, edge: Edge, event):
        """Display a context menu for the given edge at the pointer location."""
        menu = tk.Menu(self, tearoff=False)
        # Edit edge
        menu.add_command(label="Edit", command=lambda: edge.on_double_click(None))
        # Delete
        menu.add_command(label="Delete", command=lambda: self.delete_edge(edge))
        # Change color
        menu.add_command(label="Change Color", command=lambda: self._change_edge_color(edge))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            # Dismiss when clicking elsewhere
            menu.bind("<FocusOut>", lambda e: menu.unpost())

    # ---------- Context menu helpers ----------
    def _toggle_node_collapse(self, node: Node):
        node.collapsed = not node.collapsed
        node.draw()
        # Redraw connected edges in case anchor points changed
        for e in self.edges.values():
            if e.src_id == node.id or e.dst_id == node.id:
                e.update_positions()

    def _change_node_color(self, node: Node):
        (rgb, hexcolor) = colorchooser.askcolor(color=node.bg_color, title="Pick background color")
        if hexcolor:
            node.bg_color = hexcolor
            node.refresh_text()

    def _change_edge_color(self, edge: Edge):
        (rgb, hexcolor) = colorchooser.askcolor(color=edge.color, title="Pick thread color")
        if hexcolor:
            edge.color = hexcolor
            # Redraw to apply colour
            edge.draw()
            # If selected, maintain selection colour
            if self.selected is edge:
                edge.set_selected(True)

    def _generate_leads(self, node: Node):
        """Generate investigative leads for a clue using the LLM.

        This context menu action queries the Ollama chat endpoint for a
        list of investigative leads related to the selected clue.  The
        prompt is constructed automatically from the clue's title and
        description without asking the user for additional input.  The
        number of leads returned is controlled by the NUM_LEADS constant.

        After the leads are fetched, a dialog presents checkboxes for
        each suggestion; the user can choose which ones to add to the
        board's to‑do list.  Selecting leads does not create new clues
        but rather populates the to‑do panel with tasks.
        """
        if not isinstance(node, Node):
            return
        # Build prompt based on the node's title and description.  No
        # additional user prompt is requested.
        base_prompt = f"Generate {NUM_LEADS} investigative leads related to the clue titled '{node.title}'. "
        if node.description:
            base_prompt += f"Description: {node.description}. "
        base_prompt += "Provide each lead as a separate line."
        try:
            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "user", "content": base_prompt}
                ],
            }
            response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            content = ""
            if isinstance(data, dict):
                if "message" in data and isinstance(data["message"], dict):
                    content = data["message"].get("content", "")
                elif "messages" in data and data["messages"]:
                    content = data["messages"][-1].get("content", "")
                else:
                    content = str(data)
            else:
                content = str(data)
            # Split lines and take only the desired number
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            leads = lines[:NUM_LEADS] if lines else []
            if not leads:
                leads = [content.strip()] if content.strip() else []
        except Exception as e:
            leads = [f"Error while contacting LLM: {e}"]
        # Present the leads in a dialog with checkboxes for adding to the to‑do list
        def _confirm_add_leads():
            for var, text in zip(vars_list, leads):
                if var.get():
                    self.todo_list.append({"task": text, "done": False})
            self.refresh_todo_listbox()
            win.destroy()
        win = tk.Toplevel(self)
        win.title("Generated Leads")
        ttk.Label(win, text="Select leads to add to the To‑Do list:").pack(anchor="w", padx=8, pady=8)
        vars_list = []
        for text in leads:
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(win, text=text, variable=var)
            cb.pack(anchor="w", padx=12)
            vars_list.append(var)
        ttk.Button(win, text="Add Selected", command=_confirm_add_leads).pack(pady=(8,8))

    def _resize_node_dialog(self, node: Node):
        """Prompt the user to set a new width and height for the given clue."""
        # Ask for width and height with minimum constraints
        try:
            new_w = simpledialog.askinteger(
                "Resize Clue",
                "New width:",
                initialvalue=int(node.width),
                minvalue=int(NODE_MIN_WIDTH),
                parent=self
            )
            if new_w is None:
                return
            new_h = simpledialog.askinteger(
                "Resize Clue",
                "New height:",
                initialvalue=int(node.height),
                minvalue=int(NODE_MIN_HEIGHT),
                parent=self
            )
            if new_h is None:
                return
            # Apply new size
            node.width = new_w
            node.height = new_h
            node.draw()
            # Update connected edges positions
            for e in self.edges.values():
                if e.src_id == node.id or e.dst_id == node.id:
                    e.update_positions()
        except Exception:
            pass

    # The connections tab from the previous sidebar design is no longer present.
    # Functions for renaming connections or toggling their visibility from the
    # sidebar have been removed.  Connections can still be managed via the
    # context menu on edges or within the NodeEditor.

    # ---------- To‑Do tab actions ----------
    def add_task(self):
        """Prompt the user to add a new task to the board's to‑do list."""
        task_text = simpledialog.askstring("Add Task", "Task:", parent=self)
        if not task_text:
            return
        self.todo_list.append({"task": task_text, "done": False})
        self.refresh_todo_listbox()

    def edit_task(self):
        """Edit the selected task's text without changing its completion state."""
        if not hasattr(self, "todo_notebook"):
            return
        # Determine which list and get global index
        index_info = self._get_selected_task_index()
        if index_info is None:
            return
        global_idx = index_info
        task = self.todo_list[global_idx]
        new_text = simpledialog.askstring("Edit Task", "New task text:", initialvalue=task.get("task", ""), parent=self)
        if new_text is None:
            return
        task["task"] = new_text
        self.refresh_todo_listbox()

    def remove_task(self):
        """Remove the selected task from the to‑do list."""
        if not hasattr(self, "todo_notebook"):
            return
        index_info = self._get_selected_task_index()
        if index_info is None:
            return
        global_idx = index_info
        if messagebox.askyesno("Remove Task", "Delete the selected task?", parent=self):
            self.todo_list.pop(global_idx)
            self.refresh_todo_listbox()

    def toggle_task_done(self):
        """Toggle the completion state of the selected task."""
        if not hasattr(self, "todo_notebook"):
            return
        index_info = self._get_selected_task_index(return_done_flag=True)
        if index_info is None:
            return
        global_idx, idx_in_listbox, current_done = index_info
        task = self.todo_list[global_idx]
        # Toggle completion state
        new_state = not task.get("done", False)
        task["done"] = new_state
        # If marking as done, append to log
        if new_state:
            try:
                if COMPLETED_TASKS_LOG:
                    with open(COMPLETED_TASKS_LOG, "a", encoding="utf-8") as f:
                        f.write(f"{datetime.now().isoformat()}\t{task.get('task','')}\n")
            except Exception:
                pass
        self.refresh_todo_listbox()

    def generate_todo_leads(self):
        """Generate new to‑do tasks using the LLM via Ollama chat.

        Rather than prompting the user for a free‑form query, this method
        uses the currently selected clue as the basis for generating
        actionable tasks.  If no clue is selected, the user is informed
        accordingly.  The number of tasks generated is controlled by
        NUM_TASK_LEADS.  Each suggested task may be added to the board's
        to‑do list via checkboxes.
        """
        # Determine which clue to use as context.  The selected object may
        # be either a node or edge; we only handle nodes here.
        if not isinstance(self.selected, Node):
            messagebox.showinfo("LLM", "Please select a clue to generate tasks.", parent=self)
            return
        node = self.selected
        # Build prompt for tasks
        prompt = (
            f"Generate {NUM_TASK_LEADS} actionable tasks related to the clue titled '{node.title}'. "
        )
        if node.description:
            prompt += f"Description: {node.description}. "
        prompt += "Provide each task on its own line."
        try:
            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
			"stream": False,
            }
            response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            content = ""
            if isinstance(data, dict):
                if "message" in data and isinstance(data["message"], dict):
                    content = data["message"].get("content", "")
                elif "messages" in data and data["messages"]:
                    content = data["messages"][-1].get("content", "")
                else:
                    content = str(data)
            else:
                content = str(data)
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            leads = lines[:NUM_TASK_LEADS] if lines else []
            if not leads:
                leads = [content.strip()] if content.strip() else []
        except Exception as e:
            leads = [f"Error while contacting LLM: {e}"]
        # Present the leads in a dialog with checkboxes and confirm button
        def _confirm_add():
            for var, text in zip(vars_list, leads):
                if var.get():
                    self.todo_list.append({"task": text, "done": False})
            self.refresh_todo_listbox()
            win.destroy()
        win = tk.Toplevel(self)
        win.title("Generated To‑Do Leads")
        ttk.Label(win, text="Select tasks to add to the To‑Do list:").pack(anchor="w", padx=8, pady=8)
        vars_list = []
        for text in leads:
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(win, text=text, variable=var)
            cb.pack(anchor="w", padx=12)
            vars_list.append(var)
        ttk.Button(win, text="Add Selected", command=_confirm_add).pack(pady=(8,8))

    # ---------- Helper for task operations ----------
    def _get_selected_task_index(self, return_done_flag: bool = False):
        """
        Determine the global index of the selected task based on the current
        tab (pending or completed) and the listbox selection.  If no
        selection is made, returns ``None``.

        :param return_done_flag: When True, return a tuple
            ``(global_index, index_in_tab, done_flag)`` where
            ``done_flag`` is a boolean indicating whether the selected
            item is in the completed tab.  When False, return just
            ``global_index``.
        """
        if not hasattr(self, "todo_notebook"):
            return None
        # Determine which tab is selected: 0 for pending, 1 for completed
        try:
            current_tab = self.todo_notebook.index(self.todo_notebook.select())
        except Exception:
            return None
        listbox = self.todo_pending_listbox if current_tab == 0 else self.todo_completed_listbox
        sel = listbox.curselection()
        if not sel:
            return None
        idx_in_tab = sel[0]
        done_flag = (current_tab == 1)
        count = -1
        for global_idx, task in enumerate(self.todo_list):
            if task.get("done", False) == done_flag:
                count += 1
                if count == idx_in_tab:
                    if return_done_flag:
                        return (global_idx, idx_in_tab, done_flag)
                    return global_idx
        return None


if __name__ == "__main__":
    app = CaseBoardApp()
    app.mainloop()
