import json
from pathlib import Path

from scanner.telegram import send_telegram


WATCHLIST = Path("data/watchlist.json")


def load_watchlist():
    with open(WATCHLIST, "r", encoding="utf-8") as file:
        return json.load(file)


def main():
    watchlist = load_watchlist()

    print(f"Loaded {len(watchlist)} companies")

    message = f"""🧬 PHARMA RADAR — ENGINE V1

🟢 Scanner started
🟢 Telegram connected
🟢 Watchlist loaded: {len(watchlist)} companies

🔎 Sources: INITIALIZING
📡 Clinical trials: INITIALIZING
📄 SEC: INITIALIZING
🏛️ FDA: INITIALIZING

Status: READY
"""

    send_telegram(message)


if __name__ == "__main__":
    main()
