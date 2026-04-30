import platform
import time


class PostureNotifier:
    def __init__(self, config=None):
        notification_config = ((config or {}).get("posture", {}).get("notifications", {}))
        self.enabled = notification_config.get("enabled", True)
        self.sound_enabled = notification_config.get("sound", True)
        self.cooldown_seconds = float(notification_config.get("cooldown_seconds", 60.0))
        self.last_alert_at = 0.0

    def notify(self, title, message):
        if not self.enabled:
            return False

        now = time.monotonic()
        if now - self.last_alert_at < self.cooldown_seconds:
            return False

        self.last_alert_at = now
        print(f"[POSTURE ALERT] {title}: {message}")
        if self.sound_enabled:
            self._beep()
        self._desktop_alert(title, message)
        return True

    def _beep(self):
        if platform.system() == "Windows":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass

    def _desktop_alert(self, title, message):
        """
        Uses a best-effort Windows toast without adding a runtime dependency.
        Falls back to console + sound when notifications are unavailable.
        """
        if platform.system() != "Windows":
            return
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except Exception:
            return
