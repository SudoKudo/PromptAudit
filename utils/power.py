"""Windows sleep-management helpers for long-running PromptAudit runs."""

import os


class SleepInhibitor:
    """Prevent the host system from sleeping while an experiment is active."""

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002

    def __init__(self, enabled: bool = True, keep_display_awake: bool = False):
        self.enabled = bool(enabled)
        self.keep_display_awake = bool(keep_display_awake)
        self.active = False
        self.supported = os.name == "nt"
        self._kernel32 = None

        if self.supported:
            try:
                import ctypes

                self._kernel32 = ctypes.windll.kernel32
            except Exception:
                self.supported = False
                self._kernel32 = None

    def acquire(self) -> bool:
        """Request that the OS keep the machine awake for the current thread."""
        if not self.enabled or self.active:
            return False
        if not self.supported or self._kernel32 is None:
            return False

        # SetThreadExecutionState is thread-scoped on Windows, so acquire/release
        # must happen on the same worker thread that owns the long-running run loop.
        flags = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
        if self.keep_display_awake:
            flags |= self.ES_DISPLAY_REQUIRED

        result = self._kernel32.SetThreadExecutionState(flags)
        if result == 0:
            return False

        self.active = True
        return True

    def release(self) -> bool:
        """Clear any active keep-awake request for the current thread."""
        if not self.enabled or not self.active:
            return False
        if not self.supported or self._kernel32 is None:
            self.active = False
            return False

        result = self._kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
        self.active = False
        return result != 0
