import json
from pathlib import Path

import webview

from typing_hook import start_typing_tracker


def load_config():
    path = Path(__file__).resolve().parent / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    cfg = load_config()
    total = {"keys": 0}

    def on_threshold(count):
        total["keys"] += count
        for w in webview.windows:
            try:
                w.evaluate_js(f"window.__catPopup && __catPopup({total['keys']})")
            except Exception:
                pass

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
