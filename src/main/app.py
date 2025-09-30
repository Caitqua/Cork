# GUI Imports
import tkinter as tk
# Used for styling the GUI
from tkinter import ttk


# Import to help add an icon to the application.
from PIL import Image, ImageTk

# Imports from the project.
from src.ui.dashboard import Dashboard

class App(tk.Tk):
	# This is the method that initializes the class, creating a method that runs itself when the class forms an object.
	def __init__(self):
		tk.Tk.__init__(self)
		# Adds a title to the window:
		self.wm_title("Test Application")
		
		# This creates a frame and assigns it to a container
		container = tk.Frame(self, height=400, width=400)
		# Specifying the region where the frame is packed in root
		container.pack(side="top",fill="both",expand=True)

		# Configuring the location of the container using a grid:
		container.grid_rowconfigure(0, weight=1)
		container.grid_columnconfigure(0, weight=1)

		# This creates a dictionary of frames:
		self.frames = {}

		# This loop should add components to the dictionary:
		for F in (Dashboard, SidePage, CompletionScreen):
			frame = F(container, self)

			# The windows class acts as the root window for the frames.
			self.frames[F] = frame
			frame.grid(row = 0, column = 0, sticky = "nsew")
		# Using a method to switch frames:
		self.show_frame(Dashboard)
	def show_frame(self, cont):
		frame = self.frames[cont]
		# Raises the current frame to the top:
		frame.tkraise()

class Dashboard(tk.Frame):
	def __init__(self, parent, controller):
		tk.Frame.__init__(self,parent)
		label = tk.Label(self, text="Main Page")
		label.pack(padx=10,pady=10)

		btn_page_switch = tk.Button(
			self,
			text = "Go to the Side Page",
			command=lambda: controller.show_frame(SidePage)
		)
		btn_page_switch.pack(side="bottom",fill=tk.X)
class SidePage(tk.Frame):
	def __init__(self, parent, controller):
		tk.Frame.__init__(self,parent)
		label = tk.Label(self, text="This is the Side Page")
		label.pack(padx=10,pady=10)

		btn_page_switch = tk.Button(
			self,
			text = "Go to the Completion Screen",
			command = lambda: controller.show_frame(CompletionScreen)
		)
		btn_page_switch.pack(side="bottom",fill=tk.X)
class CompletionScreen(tk.Frame):
	def __init__(self, parent, controller):
		tk.Frame.__init__(self, parent)
		label = tk.Label(self, text="Completion screen, we did it!")
		label.pack(padx=10, pady=10)
		btn_page_switch = ttk.Button(
			self,
			text = "Return to menu",
			command = lambda: controller.show_frame(Dashboard)
		)
		btn_page_switch.pack(side="bottom", fill=tk.X)

def main():
	root = App()
	icon = Image.open("./src/icons/cork.png")
	photo = ImageTk.PhotoImage(icon)
	root.wm_iconphoto(False, photo)

	root.mainloop()

if __name__ == "__main__":
	main()
