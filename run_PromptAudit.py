def new_func():
    # ui/run_PromptAudit.py — Launcher for Code v2.0 Dashboard
# Author: 
# ---------------------------------------------------------------------
# This file is the entry point for launching the "Code v2.0" dashboard.
# Its only job is to create the main application window (the dashboard)
# and start the GUI event loop.
    import ttkbootstrap as tb              # Themed Tkinter wrapper for modern-looking GUIs
    from ui.dashboard import Code2Dashboard  # Our custom main window class for the dashboard

    def main():
        """Launch the Prompt Audit Dashboard."""
    # Create an instance of the main dashboard window.
    # Code2Dashboard is a subclass of ttkbootstrap.Window (or similar),
    # which defines the entire GUI layout and behavior.
        dashboard = Code2Dashboard()

    # Position the window in the center of the screen so the user
    # doesn’t have to drag it into place manually.
        dashboard.place_window_center()

    # Start the GUI event loop.
    # This call keeps the window open and responsive to user actions
    # (button clicks, menu selections, etc.) until the user closes it.
        dashboard.mainloop()

# This conditional ensures that `main()` is only executed when this file
# is run directly (e.g., `python run_gui.py`) and NOT when it is imported
# as a module by another script.
    if __name__ == "__main__":
        main()

new_func()