import json
import threading
import time
import urllib.request

from pynput import keyboard


class TypingTracker:
    def __init__(self, server_url, user_id, threshold=300, on_threshold=None):
        self.server_url = server_url
        self.user_id = user_id
        self.threshold = threshold
        self.on_threshold = on_threshold
        self.keys = 0
        self.session_start = time.time()

    def _flush(self):
        if self.keys <= 0:
            return
        minutes = max(1, int((time.time() - self.session_start) / 60))
        payload = json.dumps(
            {"user_id": self.user_id, "keys": self.keys, "minutes": minutes}
        ).encode("utf-8")
        try:
            req = urllib.request.Request(
                self.server_url + "/api/typing",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
        self.keys = 0
        self.session_start = time.time()

    def _on_press(self, key):
        self.keys += 1
        if self.keys >= self.threshold:
            self._flush()
            if self.on_threshold:
                self.on_threshold(self.threshold)

    def run(self):
        with keyboard.Listener(on_press=self._on_press) as listener:
            listener.join()


def start_typing_tracker(server_url, user_id, on_threshold=None):
    tracker = TypingTracker(server_url, user_id, on_threshold=on_threshold)
    thread = threading.Thread(target=tracker.run, daemon=True)
    thread.start()
    return tracker
