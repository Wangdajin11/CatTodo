import json
import logging
from pathlib import Path

import webview

from typing_hook import start_typing_tracker

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
logging.basicConfig(
    filename=BASE_DIR / "client.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class Api:
    def __init__(self, cfg, tracker):
        self.cfg = cfg
        self.tracker = tracker

    def get_threshold(self):
        return int(self.cfg.get("threshold", 300))

    def set_threshold(self, n):
        n = max(50, min(2000, int(n)))
        self.cfg["threshold"] = n
        save_config(self.cfg)
        self.tracker.threshold = n
        logging.info("threshold set to %s", n)
        return n


def main():
    cfg = load_config()
    total = {"keys": 0}

    def on_threshold(count):
        total["keys"] = count
        for w in webview.windows:
            try:
                w.evaluate_js(f"window.__catPopup && __catPopup({total['keys']})")
            except Exception:
                pass

    logging.info("client starting, user_id=%s", cfg["user_id"])
    token = str(cfg.get("token", "")).strip()
    tracker = start_typing_tracker(
        cfg["server_url"], cfg["user_id"],
        threshold=int(cfg.get("threshold", 300)),
        token=token,
        on_threshold=on_threshold,
    )
    api = Api(cfg, tracker)
    qs = f"user={cfg['user_id']}"
    if token:
        qs += f"&token={token}"
    webview.create_window(
        "CatTodo · 猫猫待办",
        cfg["server_url"] + f"?{qs}",
        width=1280,
        height=820,
        js_api=api,
    )
    webview.start()


if __name__ == "__main__":
    main()
