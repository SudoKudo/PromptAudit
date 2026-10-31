"""PromptAudit GUI launcher."""

from ui.dashboard import PromptAuditDashboard


def main():
    """Launch the PromptAudit dashboard."""
    app = PromptAuditDashboard()
    try:
        app.place_window_center()
    except Exception:
        # Some Tk backends do not expose the centering helper.
        pass
    app.mainloop()


if __name__ == "__main__":
    main()
