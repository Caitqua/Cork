import tkinter as tk
from tkinter import ttk

class Dashboard(ttk.Notebook):
	def __init__(self,parent,controller):
		super().__init__()
