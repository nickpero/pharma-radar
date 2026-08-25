import os
import requests


TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"


def send_telegram(message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    url = TELEGRAM_API.format(token)

    # Telegram permette massimo 4096 caratteri
    # per singolo messaggio.
    max_length = 4000

    chunks = []

    while len(message) > max_length:
        split_at = message.rfind(
            "\n",
            0,
            max_length
        )

        if split_at == -1:
            split_at = max_length

        chunks.append(
            message[:split_at]
        )

        message = message[split_at:].lstrip()

    if message:
        chunks.append(message)

    for chunk in chunks:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": chunk
            },
            timeout=30
        )

        response.raise_for_status()
