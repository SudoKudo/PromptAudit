<<<<<<< Updated upstream
def new_func():
    # ui/run_PromptAudit.py — Launcher for Code v2.0 Dashboard
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# This file is the entry point for launching the "Code v2.0" dashboard.
# Its only job is to create the main application window (the dashboard)
# and start the GUI event loop.
    import ttkbootstrap as tb              # Themed Tkinter wrapper for modern-looking GUIs
    from ui.dashboard import Code2Dashboard  # Our custom main window class for the dashboard
=======
"""PromptAudit GUI launcher."""
>>>>>>> Stashed changes

from ui.dashboard import Code2Dashboard


def main():
    """Launch the PromptAudit dashboard."""
    app = Code2Dashboard()
    try:
        app.place_window_center()
    except Exception:
        # Some Tk backends do not expose the centering helper.
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
