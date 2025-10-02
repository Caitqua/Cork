import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from datetime import *
from src.ui.widgets import Card

class Dashboard(ttk.Frame):
    def __init__(self, parent, controller):
        ttk.Frame.__init__(self, parent)
        # Header:
        header = ttk.Frame(self)
        # Top: Case Counters (Active/Archived/Solved)
        counter_tray = ttk.Frame(header)
        card1 = Card(counter_tray, "Active Cases", 0)
        card2 = Card(counter_tray, "Archived Cases", 0)
        card3 = Card(counter_tray, "Solved Cases", 0)

        # Packing cards together to make it work... Hopefully.
        card1.pack(side='right')
        card2.pack(side='right')
        card3.pack(side='right')

        # Bottom: Kanban Board
        kanban_board = ttk.Frame(header)

        # Packing the header components together.
        counter_tray.pack(side='bottom')
        kanban_board.pack(side='bottom')
        header.pack(side='bottom')
    # Body:
        # Search Bar
        # Case Viewer (Active Cases/Archived Cases/Solved Cases)
    # Footer: Updates
        # Left Side: Latest Relevant News (Filtered by caseboard subjects)
        # Right Side: Latest Leads (Top 5)
