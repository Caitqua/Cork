# GUI Imports
import tkinter as tk
# Used for styling the GUI
from tkinter import ttk


# Import to help add an icon to the application.
from PIL import Image, ImageTk

# Imports from the project.


class App(tk.Tk):
    # This is the method that initializes the class, creating a method that runs itself when the class forms an object.
    def __init__(self):
        tk.Tk.__init__(self)
        # Adds a title to the window:
        self.wm_title("Cork")

        # This creates a frame and assigns it to a container
        container = tk.Frame(self, height=400, width=400)
        # Specifying the region where the frame is packed in root
        container.pack(side="top", fill="both", expand=True)

        # Configuring the location of the container using a grid:
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # This creates a dictionary of frames:
        self.frames = {}

        # This loop should add components to the dictionary:
        for frame_cls in (Dashboard, SidePage, CompletionScreen):
            frame = frame_cls(container, self)

            # The windows class acts as the root window for the frames.
            self.frames[frame_cls] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.build_menubar()
        # Using a method to switch frames:
        self.show_frame(Dashboard)


    def build_menubar(self):
        menubar = tk.Menu(self)
        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Create New Workspace...",command=self.create_workspace)
        file_menu.add_command(label="Open Workspace...",command=self.open_workspace)

        file_menu.add_separator()
        file_menu.add_command(label="Preferences...",command=self.open_preferences)
        # file_menu.add_command(label="Open Recent Dashboard:",command=self.open_recent_dashboard) TODO: Stub
        # Edit
        edit_menu = tk.Menu(menubar, tearoff=0)

            # List Items
        edit_menu.add_command(label="Undo", command=self.undo)
        edit_menu.add_command(label="Redo",command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Add Todo...",command=self.add_todo)
        edit_menu.add_command(label="Add Evidence...", command=self.add_evidence)

        # View
        view_menu = tk.Menu(menubar, tearoff=0)

            # List Items
        view_menu.add_command(label="View Archived Cases...",command=self.view_archived)

         # Case View
        casefile_menu = tk.Menu(menubar,tearoff=0)

            # List Items
        casefile_menu.add_command(label="Open Case...", command=self.open_case)
        casefile_menu.add_command(label="Save Case...",command=self.save_case)
        casefile_menu.add_command(label="New Case...",command=self.new_case)
        casefile_menu.add_separator()
        casefile_menu.add_command(label="Solve Case...",command=self.solve_case)
        casefile_menu.add_command(label="Archive Case...",command=self.archive_case)

        # Corkboard
        cork_menu = tk.Menu(menubar,tearoff=0)
        cork_create_menu = tk.Menu(cork_menu,tearoff=0)
            # List Items
        cork_create_menu.add_command(label='Node',command=self.add_node)
        cork_create_menu.add_command(label='Connection',command=self.add_connection)
        cork_menu.add_cascade(label='Create New...', menu=cork_create_menu)

        # Media
        media_menu = tk.Menu(menubar,tearoff=0)

            # News List Items
        media_menu.add_command(label="View News RSS Feeds...",command=self.view_news)
            # Social Media List Items
        media_menu.add_command(label="View Social Media Feeds", command=self.view_socials)
        # Actually building the menu here:
        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Edit",menu=edit_menu)
        menubar.add_cascade(label="View",menu=view_menu)
        menubar.add_cascade(label="Case File", menu=casefile_menu)
        menubar.add_cascade(label="Corkboard", menu=cork_menu)
        menubar.add_cascade(label="Media", menu=media_menu)

        self.config(menu=menubar)
    def show_frame(self, cont):
        frame = self.frames[cont]
        # Raises the current frame to the top:
        frame.tkraise()
    def new_case(self):
        print('Making a new case...')
	#TODO: Stub
    def save_case(self):
        print('Saving a case...')
	#TODO: Stub
    def open_case(self):
        print('Opening a case...')
	#TODO: Stub
    def close_case(self):
        print('Closing a case...')
        #TODO: Stub
    def solve_case(self):
        print('Solving a case...')
        #TODO: Stub
    def archive_case(self):
        print('Archiving a case...')
        #TODO: Stub
    def view_archived(self):
        print('Viewing archived cases...')
	#TODO: Stub
    def view_news(self):
        print("Viewing recent news RSS feeds...")
	#TODO: Stub
    def create_workspace(self):
        print('Creating new workspace...')
	#TODO: Stub
    def open_workspace(self):
        print('Opening workspace...')
        #TODO: Stub
    # def open_recent_dashboards():
    #     print('Displaying recent dashboards...')
        #TODO: Stub
    def open_preferences(self):
        print('Opening preferences...')
        #TODO: Stub
    def undo(self):
        print('Undoing the previous action...')
        #TODO: Stub
    def redo(self):
        print('Redoing the previously undone action...')
        #TODO: Stub
    def add_todo(self):
        print('Adding a todo item...')
        #TODO: Stub
    def add_evidence(self):
        print('Adding an evidence item...')
        #TODO: Stub
    def view_socials(self):
        print('Viewing social media feeds...')
        #TODO: Stub
    def add_node(self):
        print('Creating a corkboard node...')
        #TODO: Stub
    def add_connection(self):
        print('Creating a connection between two nodes...')
class Dashboard(ttk.Frame):
    def __init__(self, parent, controller):
        ttk.Frame.__init__(self, parent)
        label = tk.Label(self, text="Main Page")
        label.pack(padx=10, pady=10)

        btn_page_switch = tk.Button(
            self,
            text="Go to the Side Page",
            command=lambda: controller.show_frame(SidePage),
        )
        btn_page_switch.pack(side="bottom", fill=tk.X)

## Placeholder until I get something better to do.
class SidePage(tk.Frame):
    def __init__(self, parent, controller):
        ttk.Frame.__init__(self, parent)
        label = tk.Label(self, text="This is the Side Page")
        label.pack(padx=10, pady=10)

        btn_page_switch = tk.Button(
            self,
            text="Go to the Completion Screen",
            command=lambda: controller.show_frame(CompletionScreen),
        )
        btn_page_switch.pack(side="bottom", fill=tk.X)


class CompletionScreen(tk.Frame):
    def __init__(self, parent, controller):
        ttk.Frame.__init__(self, parent)
        label = tk.Label(self, text="Completion screen, we did it!")
        label.pack(padx=10, pady=10)
        btn_page_switch = ttk.Button(
            self,
            text="Return to menu",
            command=lambda: controller.show_frame(Dashboard),
        )
        btn_page_switch.pack(side="bottom", fill=tk.X)


def main():
    root = App()
    icon = Image.open("./src/icons/cork.png")
    photo = ImageTk.PhotoImage(icon)
    # root.wm_iconphoto(False, photo)

    root.mainloop()


if __name__ == "__main__":
    main()
