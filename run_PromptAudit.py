"""PromptAudit GUI launcher."""

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
