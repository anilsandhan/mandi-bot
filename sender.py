import os
import requests
from db import load_env

ENV       = load_env()
BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = ENV.get("TELEGRAM_CHAT_ID", "")


def send_message(text):
    return send_to(CHAT_ID, text)


def send_to(chat_id, text):
    url     = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print(f"[SENDER] Sent to {chat_id}")
        return True
    except Exception as e:
        print(f"[SENDER ERROR] {e}")
        return False


if __name__ == "__main__":
    send_message("Bot test -- Supabase pipeline working")