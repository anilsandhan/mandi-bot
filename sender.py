import requests

def load_env():
    env = {}
    with open(r"C:\mandi_bot\.env", "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
BOT_TOKEN = ENV["TELEGRAM_BOT_TOKEN"]
CHAT_ID = ENV["TELEGRAM_CHAT_ID"]

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print(f"[SENDER] Message sent successfully")
        return True
    except Exception as e:
        print(f"[SENDER ERROR] {e}")
        return False

def send_to(chat_id, text):
    """Send to a specific chat ID — for personalised delivery"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[SENDER ERROR] {e}")
        return False

if __name__ == "__main__":
    send_message("✅ Mandi Bot test message\nयह एक परीक्षण संदेश है।")