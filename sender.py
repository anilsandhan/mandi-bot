import os
import requests


def load_env():
    env = {}
    env_path = r"C:\mandi_bot\.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ["DATA_GOV_API_KEY", "ANTHROPIC_API_KEY",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        if key not in env and os.environ.get(key):
            env[key] = os.environ.get(key)
    return env


ENV       = load_env()
BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = ENV.get("TELEGRAM_CHAT_ID", "")


def send_message(text):
    return send_to(CHAT_ID, text)


def send_to(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
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
    send_message("Bot test -- pipeline working")