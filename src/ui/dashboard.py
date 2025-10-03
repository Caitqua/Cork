import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from datetime import *
from src.ui.widgets import CounterCard
from src.ui.widgets import KanbanCard

class Dashboard(ttk.Frame):
    def __init__(self, parent, controller):
        ttk.Frame.__init__(self, parent)
        # Case viewer side bar:
        sidebar = ttk.Treeview(self)

        main_wrapper = ttk.Frame(self)
        # Header:
        header = ttk.Frame(main_wrapper)
        # Top: Case Counters (Active/Archived/Solved)
        ctr_tray = ttk.Frame(header)
            # This should configure the grid rows/cols.
        ctr_tray.columnconfigure(0,weight=1)
        ctr_tray.columnconfigure(1,weight=1)
        ctr_tray.columnconfigure(2,weight=1)
        ctr_tray.rowconfigure(0,weight=1)

        ctr_act = CounterCard(ctr_tray, "Active Cases", 0)
        ctr_arc = CounterCard(ctr_tray, "Archived Cases", 0)
        ctr_sol = CounterCard(ctr_tray, "Solved Cases", 0)

            # grid(column, row, sticky, padx, pady)
        ctr_act.grid(row=0,column=0,sticky='n')
        ctr_arc.grid(row=0,column=1,sticky='n')
        ctr_sol.grid(row=0,column=2,sticky='n')

        # Bottom: Kanban Board
        kb_board = ttk.Frame(header)
        kb_tlbar = ttk.Frame(kb_board)
            # Initializing kanban toolbar buttons
        
            # Initializing the kanban cards
        # kb_todo = KanbanCard(kb_board, "To Do")
        # kb_prog = KanbanCard(kb_board, "In Progress")
        # kb_comp = KanbanCard(kb_board, "Completed")
            # 
        # Packing the header components together.
        sidebar.pack(side='left')
        main_wrapper.pack(side='right')
        ctr_tray.pack(side='top')
        kb_board.pack(side='bottom')
        header.pack(side='top')
    # Body:
        # Search Bar
        # Case Viewer (Active Cases/Archived Cases/Solved Cases)
    # Footer: Updates
        # Left Side: Latest Relevant News (Filtered by caseboard subjects)
        # Right Side: Latest Leads (Top 5)
