import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from datetime import *
from src.ui.widgets import Card

class Dashboard(ttk.Frame):
    def __init__( self, parent, controller ):
        ttk.Frame.__init__(self, parent)
        # Header:
        header = ttk.Frame.__init__(self,parent)
        # Top: Case Counters (Active/Archived/Solved)
        counter_tray = ttk.Frame.__init__(header,parent)
        card1 = Card.__init__(self, parent, "Active Cases", 0)
        card2 = Card.__init__(self, parent, "Archived Cases", 0)
        card3 = Card.__init__(self, parent, "Solved Cases", 0)
    
        # Packing cards together to make it work... Hopefully.
        card1.pack(side='right')
        card2.pack(side='right')
        card3.pack(side='right')

        # Bottom: Kanban Board
        kanban_board = ttk.Frame.__init__(header,parent)

        # Packing the header components together.
        counter_tray.pack()
        kanban_board.pack()
    # Body:
        # Search Bar
        # Case Viewer (Active Cases/Archived Cases/Solved Cases)
    # Footer: Updates
        # Left Side: Latest Relevant News (Filtered by caseboard subjects)
        # Right Side: Latest Leads (Top 5)

