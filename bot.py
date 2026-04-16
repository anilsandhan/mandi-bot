import sqlite3
import os
import threading
from datetime import date
from flask import Flask, request
import requests

app = Flask(__name__)


def load_env():
    env = {}
    with open(r"C:\mandi_bot\.env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


ENV = load_env()
BOT_TOKEN = ENV["TELEGRAM_BOT_TOKEN"]
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

SUBSCRIBERS_DB = r"C:\mandi_bot\data\subscribers.db"
SESSIONS_DB    = r"C:\mandi_bot\data\sessions.db"

DISTRICTS = {
    "1":  ("Karnal",      "Gharaunda,Kunjpura,Pipli,Thanesar"),
    "2":  ("Kurukshetra", "Thanesar,Pehowa,Shahabad,Ladwa"),
    "3":  ("Ambala",      "Ambala City APMC,Ambala Cantt. APMC,Naraingarh"),
    "4":  ("Panipat",     "Panipat APMC,Ganaur,Samalkha"),
    "5":  ("Sirsa",       "Sirsa APMC,Ellanabad APMC,Rania"),
    "6":  ("Rohtak",      "Gohana,Sonepat,Jhajjar"),
    "7":  ("Hisar",       "Hissar APMC,Hansi,Barwala"),
    "8":  ("Sonepat",     "Sonepat APMC,Gohana,Ganaur"),
    "9":  ("Fatehabad",   "Fatehabad APMC,Ratia,Tohana"),
    "10": ("Jind",        "Jind APMC,Narwana,Safidon"),
    "11": ("Kaithal",     "Kaithal,Pundri,Guhla"),
    "12": ("Yamunanagar", "Jagadhri APMC,Sadhaura,Shahzadpur"),
}

CROP_CATEGORIES = {
    "1": "Anaj (Grains)",
    "2": "Sabziyan (Vegetables)",
    "3": "Phal (Fruits)",
    "4": "Anya (Others)",
}

CROPS_BY_CATEGORY = {
    "1": {
        "1": "Wheat",
        "2": "Mustard",
        "3": "Barley",
        "4": "Paddy",
        "5": "Maize",
        "6": "Bajra",
        "7": "Sunflower",
    },
    "2": {
        "1": "Onion",
        "2": "Potato",
        "3": "Tomato",
        "4": "Cucumbar(Kheera)",
        "5": "Garlic",
        "6": "Ginger",
        "7": "Bottle Gourd",
        "8": "Brinjal",
    },
    "3": {
        "1": "Apple",
        "2": "Banana",
        "3": "Chikoos(Sapota)",
        "4": "Mango",
        "5": "Guava",
    },
    "4": {
        "1": "Dry Fodder",
        "2": "Green Fodder",
        "3": "Cotton",
        "4": "Sugarcane",
    },
}

DISTRICT_LIST_TEXT = "\n".join(
    f"{k}. {v[0]}" for k, v in DISTRICTS.items()
)

CATEGORY_LIST_TEXT = (
    "1. Anaj (Gehun, Sarson, Jau...)\n"
    "2. Sabziyan (Pyaaz, Aloo, Tamatar...)\n"
    "3. Phal (Seb, Kela, Chikoo...)\n"
    "4. Anya (Chara, Cotton, Ganna...)\n\n"
    "Ek ya zyada chunein jaise: 1 ya 1,2"
)

GREETINGS = [
    "hi", "hii", "hiii", "hiiii", "hello", "helo", "hey",
    "/start", "hy", "namaste", "namaskar", "namasate",
    "nmste", "nmskar", "ram ram", "jai hind", "jai shri ram",
    "sat sri akal", "pranam", "charan sparsh", "jai mata di",
    "ke haal", "kiddan", "kidhar", "kaisa hai", "kya haal",
    "bhai", "bhai sahab", "hello ji", "namaste ji",
    "ram ram ji", "bolo", "haan bhai", "hlw", "hlww",
    "hlo", "nm", "nmsty", "shuru", "start karo",
    "shuru karo", "chalu karo",
]

BHAV_TRIGGERS = [
    "/mera_bhav", "bhav", "bhav batao", "rate", "price",
    "aaj ka bhav", "mandi bhav", "bhav do", "aaj ka rate",
    "mandi rate", "kya bhav hai", "gehun ka bhav",
    "sarson ka bhav", "gehu bhav", "bhav chahiye",
    "aaj ka mandi bhav", "bhav dikhao",
]

BAND_TRIGGERS = [
    "/band", "band karo", "stop", "unsubscribe",
    "band", "rok do", "mat bhejo", "band kar do",
]

UPDATE_TRIGGERS = [
    "/update", "update", "badlo", "change karo",
    "profile badlo", "profile update",
]

HELP_TRIGGERS = [
    "/help", "help", "madad", "commands",
    "kya kare", "kya karna hai",
]

REGISTRATION_STEPS = [
    "awaiting_name",
    "awaiting_district",
    "awaiting_category",
    "awaiting_crops_in_category",
    "awaiting_more_categories",
]


def init_sessions_db():
    os.makedirs(os.path.dirname(SESSIONS_DB), exist_ok=True)
    conn = sqlite3.connect(SESSIONS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            telegram_id        TEXT PRIMARY KEY,
            step               TEXT,
            name               TEXT,
            district           TEXT,
            mandis             TEXT,
            selected_category  TEXT,
            crops              TEXT,
            updated            TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_session(telegram_id):
    conn = sqlite3.connect(SESSIONS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM sessions WHERE telegram_id = ?",
        (str(telegram_id),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_session(telegram_id, **kwargs):
    conn = sqlite3.connect(SESSIONS_DB)
    existing = get_session(telegram_id)
    if existing:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [str(date.today()), str(telegram_id)]
        conn.execute(
            f"UPDATE sessions SET {fields}, updated = ? "
            f"WHERE telegram_id = ?",
            values
        )
    else:
        kwargs["telegram_id"] = str(telegram_id)
        kwargs["updated"] = str(date.today())
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        conn.execute(
            f"INSERT INTO sessions ({cols}) VALUES ({placeholders})",
            list(kwargs.values())
        )
    conn.commit()
    conn.close()


def clear_session(telegram_id):
    conn = sqlite3.connect(SESSIONS_DB)
    conn.execute(
        "DELETE FROM sessions WHERE telegram_id = ?",
        (str(telegram_id),)
    )
    conn.commit()
    conn.close()


def save_subscriber(telegram_id, name, district, mandis, crops):
    os.makedirs(os.path.dirname(SUBSCRIBERS_DB), exist_ok=True)
    conn = sqlite3.connect(SUBSCRIBERS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            telegram_id TEXT UNIQUE,
            district    TEXT,
            mandis      TEXT,
            crops       TEXT,
            active      INTEGER DEFAULT 1,
            added_date  TEXT
        )
    """)
    conn.execute("""
        INSERT OR REPLACE INTO subscribers
        (name, telegram_id, district, mandis, crops, active, added_date)
        VALUES (?,?,?,?,?,1,?)
    """, (
        name, str(telegram_id), district,
        mandis, crops, str(date.today())
    ))
    conn.commit()
    conn.close()


def get_subscriber(telegram_id):
    if not os.path.exists(SUBSCRIBERS_DB):
        return None
    conn = sqlite3.connect(SUBSCRIBERS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM subscribers "
        "WHERE telegram_id = ? AND active = 1",
        (str(telegram_id),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def send(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json=payload,
            timeout=10
        )
        print(f"[SEND] to={chat_id} status={r.status_code}")
        if r.status_code != 200:
            print(f"[SEND FAIL] {r.text[:200]}")
    except Exception as e:
        print(f"[SEND ERROR] {e}")


def is_greeting(text):
    return text.lower().strip() in GREETINGS


def build_combined_crop_list(cat_keys):
    lines = ""
    for cat_key in cat_keys:
        cat_name = CROP_CATEGORIES.get(cat_key, "")
        crops = CROPS_BY_CATEGORY.get(cat_key, {})
        lines += f"{cat_name}:\n"
        lines += "\n".join(f"{k}. {v}" for k, v in crops.items())
        lines += "\n\n"
    return lines.strip()


def get_all_crops_from_categories(cat_keys):
    merged = {}
    for cat_key in cat_keys:
        merged.update(CROPS_BY_CATEGORY.get(cat_key, {}))
    return merged


def handle_registration_step(chat_id, text_clean, session, user_first_name):
    step = session.get("step")
    text_lower = text_clean.lower().strip()

    # allow /band and /help to escape registration
    if text_lower in BAND_TRIGGERS + HELP_TRIGGERS:
        return False

    # step 1 -- name
    if step == "awaiting_name":
        if len(text_clean) < 2 or text_clean.isdigit():
            send(chat_id, "Apna naam batayein ji:")
            return True
        set_session(chat_id,
            step="awaiting_district",
            name=text_clean
        )
        send(chat_id,
            f"Shukriya {text_clean} ji!\n\n"
            f"Apna jila chunein -- sirf number bhejein:\n\n"
            f"{DISTRICT_LIST_TEXT}"
        )
        return True

    # step 2 -- district
    if step == "awaiting_district":
        if text_clean not in DISTRICTS:
            send(chat_id,
                f"Sirf number bhejein ji (1-{len(DISTRICTS)}):\n\n"
                f"{DISTRICT_LIST_TEXT}"
            )
            return True
        district_name, mandis = DISTRICTS[text_clean]
        set_session(chat_id,
            step="awaiting_category",
            district=district_name,
            mandis=mandis,
            crops=""
        )
        send(chat_id,
            f"Jila: {district_name}\n\n"
            f"Ab fasal ki category chunein:\n\n"
            f"{CATEGORY_LIST_TEXT}"
        )
        return True

    # step 3 -- category (one or multiple like 1,2)
    if step == "awaiting_category":
        selected_cats = [
            c.strip()
            for c in text_clean.replace(" ", "").split(",")
        ]
        valid_cats = [c for c in selected_cats if c in CROP_CATEGORIES]
        if not valid_cats:
            send(chat_id,
                f"Sirf number bhejein (1-4):\n\n"
                f"{CATEGORY_LIST_TEXT}"
            )
            return True
        crop_list = build_combined_crop_list(valid_cats)
        set_session(chat_id,
            step="awaiting_crops_in_category",
            selected_category=",".join(valid_cats)
        )
        send(chat_id,
            f"{crop_list}\n\n"
            f"Jo fasalein chahiye un sabke\n"
            f"numbers bhejein jaise: 1,2,3"
        )
        return True

    # step 4 -- crops within selected categories
    if step == "awaiting_crops_in_category":
        cat_keys = session.get("selected_category", "").split(",")
        all_cat_crops = get_all_crops_from_categories(cat_keys)

        selected = [
            c.strip()
            for c in text_clean.replace(" ", "").split(",")
        ]
        valid = [c for c in selected if c in all_cat_crops]

        if not valid:
            crop_list = build_combined_crop_list(cat_keys)
            send(chat_id,
                f"Sahi numbers bhejein ji:\n\n"
                f"{crop_list}"
            )
            return True

        new_crops = ",".join(all_cat_crops[c] for c in valid)
        existing  = session.get("crops") or ""
        all_crops = existing + "," + new_crops if existing else new_crops

        set_session(chat_id,
            step="awaiting_more_categories",
            crops=all_crops
        )
        crop_display = ", ".join(all_cat_crops[c] for c in valid)
        send(chat_id,
            f"Selected: {crop_display}\n\n"
            f"Kya aur category add karni hai?\n\n"
            f"1. Haan -- aur category chunni hai\n"
            f"2. Nahi -- registration complete karo"
        )
        return True

    # step 5 -- more categories or finish
    if step == "awaiting_more_categories":
        want_more = text_clean == "1" or text_lower in [
            "haan", "ha", "yes", "aur", "haan ji", "haa"
        ]

        if want_more:
            set_session(chat_id, step="awaiting_category")
            send(chat_id,
                f"Aur category chunein:\n\n"
                f"{CATEGORY_LIST_TEXT}"
            )
            return True

        # finish registration
        name     = session.get("name", user_first_name)
        district = session.get("district")
        mandis   = session.get("mandis")
        crops    = session.get("crops", "")

        if not crops:
            set_session(chat_id, step="awaiting_category")
            send(chat_id,
                f"Koi fasal nahi chuni ji.\n\n"
                f"Category chunein:\n\n"
                f"{CATEGORY_LIST_TEXT}"
            )
            return True

        save_subscriber(chat_id, name, district, mandis, crops)
        clear_session(chat_id)
        crop_display = crops.replace(",", ", ")

        send(chat_id,
            f"Bahut badhiya {name} ji!\n\n"
            f"Aapka profile taiyaar:\n"
            f"Naam: {name}\n"
            f"Jila: {district}\n"
            f"Fasalein: {crop_display}\n\n"
            f"Rozana subah 6:30 baje\n"
            f"aapki fasal ka mandi bhav milega.\n\n"
            f"Abhi ka bhav: /mera_bhav\n"
            f"Madad: /help\n\n"
            f"Kheti mein khushhaali rahe!"
        )
        return True

    return False


def handle_message(chat_id, text, user_first_name):
    text_clean = text.strip()
    text_lower = text_clean.lower().strip()
    session    = get_session(chat_id)

    print(f"[HANDLE] chat_id={chat_id} "
          f"step={session.get('step') if session else None} "
          f"text='{text_clean}'")

    # priority 1 -- mid registration
    if session and session.get("step") in REGISTRATION_STEPS:
        handled = handle_registration_step(
            chat_id, text_clean, session, user_first_name
        )
        if handled:
            return

    # priority 2 -- greeting / start
    if is_greeting(text_clean) or text_clean == "/start":
        existing = get_subscriber(chat_id)
        if existing:
            send(chat_id,
                f"Ram Ram {existing['name']} ji!\n\n"
                f"Aapka profile:\n"
                f"Jila: {existing['district']}\n"
                f"Fasalein: {existing['crops']}\n\n"
                f"/mera_bhav -- Abhi ka bhav\n"
                f"/profile -- Apna profile\n"
                f"/update -- Profile badlein\n"
                f"/band -- Alerts band karein\n"
                f"/help -- Madad"
            )
            return
        clear_session(chat_id)
        set_session(chat_id, step="awaiting_name")
        send(chat_id,
            "Ram Ram! Haryana Mandi Bhav Bot mein\n"
            "aapka swagat hai.\n\n"
            "Yeh bot kya karta hai:\n"
            "- Rozana subah 6:30 baje fasal ka bhav\n"
            "- MSP se tulna -- bechein ya ruken\n"
            "- Aapke jile ki mandion ka data\n"
            "- Bilkul muft\n\n"
            "Apna naam batayein:"
        )
        return

    # priority 3 -- /profile
    if text_clean == "/profile":
        sub = get_subscriber(chat_id)
        if sub:
            send(chat_id,
                f"Aapka Profile\n\n"
                f"Naam: {sub['name']}\n"
                f"Jila: {sub['district']}\n"
                f"Fasalein: {sub['crops']}\n"
                f"Status: Active\n"
                f"Joined: {sub['added_date']}\n\n"
                f"/update se profile badlein"
            )
        else:
            send(chat_id,
                "Aap registered nahi hain.\n"
                "Register ke liye 'Hi' bhejein."
            )
        return

    # priority 4 -- bhav
    if text_lower in BHAV_TRIGGERS:
        sub = get_subscriber(chat_id)
        if not sub:
            send(chat_id,
                "Pehle register karein ji.\n"
                "'Hi' bhejein register karne ke liye."
            )
            return
        send(chat_id, "Bhav nikal raha hai... thoda ruko.")
        threading.Thread(
            target=send_instant_bhav,
            args=(chat_id, sub)
        ).start()
        return

    # priority 5 -- /band
    if text_lower in BAND_TRIGGERS:
        if os.path.exists(SUBSCRIBERS_DB):
            conn = sqlite3.connect(SUBSCRIBERS_DB)
            conn.execute(
                "UPDATE subscribers SET active = 0 "
                "WHERE telegram_id = ?",
                (str(chat_id),)
            )
            conn.commit()
            conn.close()
        clear_session(chat_id)
        send(chat_id,
            "Aapke alerts band kar diye gaye hain.\n\n"
            "Dobara shuru ke liye 'Hi' bhejein.\n"
            "Aapka data save hai."
        )
        return

    # priority 6 -- /update
    if text_lower in UPDATE_TRIGGERS:
        clear_session(chat_id)
        set_session(chat_id, step="awaiting_name")
        send(chat_id,
            "Profile update karte hain.\n\n"
            "Apna naam batayein\n"
            "(same rakhna ho to wahi likhein):"
        )
        return

    # priority 7 -- /help
    if text_lower in HELP_TRIGGERS:
        send(chat_id,
            "Haryana Mandi Bhav Bot\n\n"
            "Yeh bhejein:\n"
            "Hi / Ram Ram -- Shuru karein\n"
            "/mera_bhav -- Abhi ka bhav\n"
            "/profile -- Apna profile\n"
            "/update -- Profile badlein\n"
            "/band -- Alerts band karein\n"
            "/help -- Yeh message\n\n"
            "Rozana subah 6:30 baje automatically\n"
            "aapki fasal ka bhav milega."
        )
        return

    # priority 8 -- fallback
    send(chat_id,
        "Samajh nahi aaya ji.\n\n"
        "Bhav ke liye: /mera_bhav\n"
        "Madad ke liye: /help"
    )


def send_instant_bhav(chat_id, subscriber):
    try:
        from analyser import analyse_for_subscriber
        from narrator import generate_hindi_message, build_personalised_prompt
        summary = analyse_for_subscriber(subscriber)
        if summary:
            prompt  = build_personalised_prompt(summary)
            message = generate_hindi_message(
                summary, prompt_override=prompt
            )
            send(chat_id, message)
        else:
            send(chat_id,
                "Abhi aapke jile ka data nahi aaya.\n"
                "Kal subah 6:30 baje automatically milega."
            )
    except Exception as e:
        send(chat_id,
            "Data laane mein dikkat aayi.\n"
            "Thodi der mein /mera_bhav try karein."
        )
        print(f"[BOT ERROR] {e}")
        import traceback
        traceback.print_exc()


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return "ok"
    try:
        message    = data.get("message", {})
        chat_id    = message.get("chat", {}).get("id")
        text       = message.get("text", "")
        first_name = message.get("from", {}).get("first_name", "")
        print(f"[WEBHOOK] from={first_name} text='{text}'")
        if chat_id and text:
            try:
                handle_message(chat_id, text, first_name)
            except Exception as e:
                print(f"[HANDLE ERROR] {e}")
                import traceback
                traceback.print_exc()
                send(chat_id,
                    "Kuch gadbad ho gayi ji.\n"
                    "Thodi der mein dobara try karein."
                )
        else:
            print("[WEBHOOK] No text -- skipping")
    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")
    return "ok"


@app.route("/", methods=["GET"])
def index():
    return "Mandi Bot is running."


if __name__ == "__main__":
    init_sessions_db()
    print("[BOT] Starting webhook server on port 5000...")
    app.run(host="0.0.0.0", port=5000)