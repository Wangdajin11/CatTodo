import json
import logging
from pathlib import Path

import webview

from typing_hook import start_typing_tracker

BASE_DIR = Path(__file__).resolve().parent
logging.basicConfig(
    filename=BASE_DIR / "client.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)


def load_config():
    path = BASE_DIR / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


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
    start_typing_tracker(cfg["server_url"], cfg["user_id"], on_threshold=on_threshold)
    webview.create_window(
        "CatTodo · 猫猫待办",
        cfg["server_url"] + f"?user={cfg['user_id']}",
        width=1280,
        height=820,
    )
    webview.start()


if __name__ == "__main__":
    main()
