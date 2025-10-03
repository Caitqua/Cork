import tkinter as tk
from tkinter import ttk

class CounterCard(ttk.Frame):
    def __init__(self, parent, label = str, tracker = int):
        ttk.Frame.__init__(self, parent)
        self.columnconfigure(0,weight=1)
        self.rowconfigure(0,weight=1)
        self.rowconfigure(1,weight=1)
        # Top Part: Label
        lbl_top = ttk.Label(self, text=label)
        # Bottom Part: Number of cases following X/Y/Z condition.
        lbl_bot = ttk.Label(self, text=tracker)
        
        # Adding padding
        # lbl_top.pack(padx=10,pady=10)
        # lbl_bot.pack(padx=10,pady=10)
        # Trying the .grid() method instead
        lbl_top.grid(row=0,column=0,sticky='n')
        lbl_bot.grid(row=1,column=0,sticky='s')

class KanbanCard(ttk.Frame):
    def __init__(self, parent, controller):
        #TODO: Stub; populate with widgets to make kanban board functional
        super().__init__(parent)
        self.controller = controller
        
        placeholder = ttk.Label(self, text='Kanban Card Stub')
        placeholder.pack()
