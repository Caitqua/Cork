import tkinter as tk
from tkinter import ttk

class Card(ttk.Frame):
    def __init__(self, parent, label = str, tracker = int):
        ttk.Frame.__init__(self, parent)
        # Top Part: Label
        lbl_top = ttk.Label(self, text=label)
        lbl_bot = ttk.Label(self, text=tracker)
        lbl_top.pack(padx=10,pady=10)
        lbl_bot.pack(padx=10,pady=10)
