import json
import logging
import threading
import time
import urllib.request

from pynput import keyboard

logger = logging.getLogger("cattodo")


class TypingTracker:
    def __init__(self, server_url, user_id, threshold=300, flush_interval=5,
                 on_threshold=None):
        self.server_url = server_url
        self.user_id = user_id
        self.threshold = threshold
        self.flush_interval = flush_interval
        self.on_threshold = on_threshold
        self.keys = 0
        self.total = 0
        self.session_start = time.time()

    def _flush(self):
        if self.keys <= 0:
            return False
        count = self.keys
        minutes = max(1, int((time.time() - self.session_start) / 60))
        payload = json.dumps(
            {"user_id": self.user_id, "keys": count, "minutes": minutes}
        ).encode("utf-8")
        try:
            req = urllib.request.Request(
                self.server_url + "/api/typing",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            logger.info("flushed %s keys", count)
        except Exception as e:
            logger.warning("flush failed: %s", e)
            return False
        self.keys = 0
        self.session_start = time.time()
        return True

    def _on_press(self, key):
        self.keys += 1
        self.total += 1
        if self.total % self.threshold == 0:
            if self.on_threshold:
                self.on_threshold(self.total)

    def run(self):
        listener = keyboard.Listener(on_press=self._on_press)
        listener.start()
        logger.info("keyboard listener started")
        while listener.is_alive():
            time.sleep(self.flush_interval)
            self._flush()


def start_typing_tracker(server_url, user_id, on_threshold=None):
    tracker = TypingTracker(server_url, user_id, on_threshold=on_threshold)
    thread = threading.Thread(target=tracker.run, daemon=True)
    thread.start()
    return tracker
