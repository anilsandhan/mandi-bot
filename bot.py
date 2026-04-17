import os
import threading
import time
from datetime import date
from flask import Flask, request
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_conn, init_db, load_env
from subscribers import (get_subscriber, add_subscriber,
                          deactivate_subscriber,
                          get_active_subscribers)

app = Flask(__name__)

ENV       = load_env()
BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
BASE_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}"
ADMIN_ID  = "1756491671"

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

# District name aliases -- accept text input
DISTRICT_ALIASES = {
    "karnal": "1", "kernal": "1",
    "kurukshetra": "2", "kurukshetar": "2",
    "ambala": "3",
    "panipat": "4",
    "sirsa": "5",
    "rohtak": "6",
    "hisar": "7", "hissar": "7",
    "sonepat": "8", "sonipat": "8",
    "fatehabad": "9",
    "jind": "10",
    "kaithal": "11",
    "yamunanagar": "12", "jagadhri": "12",
}

# Category aliases -- accept text input
CATEGORY_ALIASES = {
    "anaj": "1", "grain": "1", "grains": "1",
    "gehun": "1", "wheat": "1", "sarson": "1",
    "sabzi": "2", "sabziyan": "2", "vegetable": "2",
    "vegetables": "2", "pyaaz": "2", "onion": "2",
    "phal": "3", "fruit": "3", "fruits": "3",
    "seb": "3", "apple": "3",
    "anya": "4", "other": "4", "others": "4",
    "chara": "4", "fodder": "4",
}

# Category = ALL crops in that category (no individual selection)
CROP_CATEGORIES = {
    "1": ("Anaj (Grains)",
          ["Wheat", "Mustard", "Barley", "Paddy",
           "Maize", "Bajra", "Sunflower"]),
    "2": ("Sabziyan (Vegetables)",
          ["Onion", "Potato", "Tomato", "Cucumbar(Kheera)",
           "Garlic", "Ginger", "Bottle Gourd", "Brinjal"]),
    "3": ("Phal (Fruits)",
          ["Apple", "Banana", "Chikoos(Sapota)",
           "Mango", "Guava"]),
    "4": ("Anya (Others)",
          ["Dry Fodder", "Green Fodder", "Cotton", "Sugarcane"]),
}

DISTRICT_LIST_TEXT = "\n".join(
    f"{k}. {v[0]}" for k, v in DISTRICTS.items()
)

CATEGORY_LIST_TEXT = (
    "1. Anaj / अनाज\n"
    "   (Gehun, Sarson, Jau, Paddy, Makka, Bajra)\n\n"
    "2. Sabziyan / सब्जियां\n"
    "   (Pyaaz, Aloo, Tamatar, Kheera, Lahsun)\n\n"
    "3. Phal / फल\n"
    "   (Seb, Kela, Chikoo, Aam, Amrood)\n\n"
    "4. Anya / अन्य\n"
    "   (Chara, Cotton, Ganna)\n\n"
    "Number ya naam bhejein: 1 ya Anaj\n"
    "Ek se zyada: 1,2 ya Anaj,Phal"
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
    "aaj ka mandi bhav", "bhav dikhao", "mera bhav",
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
    "awaiting_name", "awaiting_district",
    "awaiting_category", "awaiting_more_categories",
]

ADMIN_COMMANDS = [
    "/admin", "/stats", "/users", "/today", "/bhav"
]


def resolve_district(text):
    """Accept '1', '1. Karnal', 'karnal' etc"""
    t = text.strip().lower()
    t = t.lstrip("0123456789. ").strip()
    if t in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[t]
    # try number
    num = text.strip().split(".")[0].strip()
    if num in DISTRICTS:
        return num
    return None


def resolve_categories(text):
    """Accept '1', '1,2', 'anaj', 'anaj,phal' etc"""
    parts = [p.strip().lower().lstrip("0123456789. ").strip()
             for p in text.replace(" ", "").split(",")]
    result = []
    for part in parts:
        # try alias
        if part in CATEGORY_ALIASES:
            result.append(CATEGORY_ALIASES[part])
        # try stripping to number
        num = part.lstrip("abcdefghijklmnopqrstuvwxyz").strip()
        if not num:
            # try as pure number from original
            num = part
        if num in CROP_CATEGORIES:
            result.append(num)
    # also try original text as numbers
    for part in text.replace(" ", "").split(","):
        p = part.strip()
        if p in CROP_CATEGORIES and p not in result:
            result.append(p)
    return list(dict.fromkeys(result))


def get_crops_for_categories(cat_keys):
    """Returns all crops for selected categories"""
    all_crops = []
    for key in cat_keys:
        if key in CROP_CATEGORIES:
            all_crops.extend(CROP_CATEGORIES[key][1])
    return list(dict.fromkeys(all_crops))


def get_session(telegram_id):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT telegram_id, step, name, district, mandis,
                   selected_category, crops, updated
            FROM sessions WHERE telegram_id = %s
        """, (str(telegram_id),))
        cols = [d[0] for d in cur.description]
        row  = cur.fetchone()
        cur.close()
        conn.close()
        return dict(zip(cols, row)) if row else None
    except Exception as e:
        print(f"[SESSION ERROR] get: {e}")
        return None


def set_session(telegram_id, **kwargs):
    try:
        conn     = get_conn()
        cur      = conn.cursor()
        existing = get_session(telegram_id)
        kwargs["updated"] = str(date.today())
        if existing:
            fields = ", ".join(f"{k} = %s" for k in kwargs)
            values = list(kwargs.values()) + [str(telegram_id)]
            cur.execute(
                f"UPDATE sessions SET {fields} "
                f"WHERE telegram_id = %s", values
            )
        else:
            kwargs["telegram_id"] = str(telegram_id)
            cols = ", ".join(kwargs.keys())
            ph   = ", ".join(["%s"] * len(kwargs))
            cur.execute(
                f"INSERT INTO sessions ({cols}) VALUES ({ph})",
                list(kwargs.values())
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[SESSION ERROR] set: {e}")


def clear_session(telegram_id):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "DELETE FROM sessions WHERE telegram_id = %s",
            (str(telegram_id),)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[SESSION ERROR] clear: {e}")


def send(chat_id, text):
    payload = {"chat_id": chat_id, "text": text}
    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json=payload, timeout=10
        )
        print(f"[SEND] to={chat_id} status={r.status_code}")
        if r.status_code != 200:
            print(f"[SEND FAIL] {r.text[:200]}")
    except Exception as e:
        print(f"[SEND ERROR] {e}")


def is_greeting(text):
    return text.lower().strip() in GREETINGS


def is_valid_name(text):
    t = text.strip()
    if len(t) < 2:
        return False
    if t.lower() in GREETINGS:
        return False
    if t.startswith("/"):
        return False
    if t.isdigit():
        return False
    words = t.lower().split()
    if all(w in GREETINGS for w in words):
        return False
    return True


def get_bhav_for_subscriber(subscriber):
    """Fetch and send bhav for a subscriber"""
    try:
        from analyser import analyse_for_subscriber
        from narrator import (generate_hindi_message,
                               build_personalised_prompt)
        summary = analyse_for_subscriber(subscriber)
        if summary:
            prompt  = build_personalised_prompt(summary)
            message = generate_hindi_message(
                summary, prompt_override=prompt
            )
            return message
        return None
    except Exception as e:
        print(f"[BHAV ERROR] {e}")
        return None


def run_daily_pipeline():
    """Runs at 6:30 AM IST -- called by APScheduler"""
    print("[SCHEDULER] Running daily pipeline...")
    try:
        from fetcher import run as fetch_run
        prices = fetch_run()
        if not prices:
            print("[SCHEDULER] No prices today")
            return

        subscribers = get_active_subscribers()
        print(f"[SCHEDULER] Sending to {len(subscribers)} subscribers")

        for sub in subscribers:
            try:
                message = get_bhav_for_subscriber(sub)
                if message:
                    send(sub["telegram_id"], message)
                    print(f"[SCHEDULER] Sent to {sub['name']}")
                else:
                    send(sub["telegram_id"],
                        "Aaj aapke jile ka mandi data nahi aaya.\n"
                        "Kal subah phir milega.")
            except Exception as e:
                print(f"[SCHEDULER] Error for {sub['name']}: {e}")

        print("[SCHEDULER] Daily pipeline complete")
    except Exception as e:
        print(f"[SCHEDULER ERROR] {e}")
        import traceback
        traceback.print_exc()


def handle_admin(chat_id, text_lower):
    if str(chat_id) != ADMIN_ID:
        return False
    if text_lower not in ADMIN_COMMANDS:
        return False

    today_str = str(date.today())

    if text_lower in ["/admin", "/stats"]:
        try:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM subscribers WHERE active=1"
            )
            active = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM subscribers WHERE active=0"
            )
            inactive = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM subscribers")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sessions")
            sessions = cur.fetchone()[0]
            cur.execute("""
                SELECT COUNT(DISTINCT market) FROM prices
                WHERE fetch_date = %s
            """, (today_str,))
            mandis_today = cur.fetchone()[0]
            cur.execute("""
                SELECT COUNT(*) FROM prices
                WHERE fetch_date = %s AND is_fallback = 0
            """, (today_str,))
            fresh = cur.fetchone()[0]
            cur.execute("""
                SELECT COUNT(*) FROM prices
                WHERE fetch_date = %s AND is_fallback = 1
            """, (today_str,))
            fallback = cur.fetchone()[0]
            cur.execute("""
                SELECT district, COUNT(*) as cnt
                FROM subscribers WHERE active = 1
                GROUP BY district ORDER BY cnt DESC
            """)
            districts = cur.fetchall()
            cur.close()
            conn.close()

            dist_text = "\n".join(
                f"  {r[0]}: {r[1]}" for r in districts
            ) or "  Koi nahi"

            send(chat_id,
                f"ADMIN STATS\n"
                f"{'='*28}\n\n"
                f"SUBSCRIBERS\n"
                f"Active: {active}\n"
                f"Unsubscribed: {inactive}\n"
                f"Total ever: {total}\n"
                f"Mid-registration: {sessions}\n\n"
                f"TODAY ({today_str})\n"
                f"Mandis: {mandis_today}\n"
                f"Fresh records: {fresh}\n"
                f"Fallback records: {fallback}\n\n"
                f"BY DISTRICT\n{dist_text}"
            )
        except Exception as e:
            send(chat_id, f"Stats error: {e}")
        return True

    if text_lower == "/users":
        try:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("""
                SELECT DISTINCT ON (telegram_id)
                    name, telegram_id, district,
                    crops, added_date, active
                FROM subscribers
                ORDER BY telegram_id, id DESC
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                send(chat_id, "Abhi koi subscriber nahi hai.")
                return True

            lines = [f"SUBSCRIBERS ({len(rows)} total)\n"]
            for r in rows:
                name, tid, dist, crops, joined, active = r
                status = "Active" if active == 1 else "Inactive"
                lines.append(
                    f"{name or '?'} [{status}]\n"
                    f"  ID: {tid}\n"
                    f"  Jila: {dist or '?'}\n"
                    f"  Fasalein: {crops or '?'}\n"
                    f"  Joined: {joined or '?'}\n"
                )
            msg = "\n".join(lines)
            send(chat_id, msg[:4000])
        except Exception as e:
            send(chat_id, f"Users error: {e}")
        return True

    if text_lower == "/today":
        try:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("""
                SELECT market, COUNT(*) as cnt
                FROM prices
                WHERE fetch_date = %s
                AND is_fallback = 0
                GROUP BY market ORDER BY market
            """, (today_str,))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                send(chat_id,
                    f"Aaj ({today_str}) ka fresh data nahi aaya.\n"
                    f"main.py run karein."
                )
                return True

            lines = [f"TODAY ({today_str})\n{len(rows)} mandis\n"]
            for r in rows:
                lines.append(f"  {r[0]}: {r[1]} crops")
            send(chat_id, "\n".join(lines)[:4000])
        except Exception as e:
            send(chat_id, f"Today error: {e}")
        return True

    if text_lower == "/bhav":
        send(chat_id,
            "Sabhi subscribers ko abhi bhav bhej raha hoon...\n"
            "Ek minute ruko."
        )
        threading.Thread(target=run_daily_pipeline).start()
        return True

    return False


def handle_registration_step(chat_id, text_clean, session,
                              user_first_name):
    step       = session.get("step")
    text_lower = text_clean.lower().strip()

    if text_lower in BAND_TRIGGERS + HELP_TRIGGERS:
        return False

    # step 1 -- naam
    if step == "awaiting_name":
        if not is_valid_name(text_clean):
            send(chat_id,
                "Apna naam batayein ji.\n"
                "Jaise: Suresh Kumar\n\n"
                "Sirf apna naam likhein:"
            )
            return True
        set_session(chat_id, step="awaiting_district",
                    name=text_clean)
        send(chat_id,
            f"Shukriya {text_clean} ji!\n\n"
            f"Ab apna Jila (District) chunein.\n"
            f"Number ya naam -- dono chalega:\n\n"
            f"{DISTRICT_LIST_TEXT}"
        )
        return True

    # step 2 -- jila
    if step == "awaiting_district":
        resolved = resolve_district(text_clean)
        if not resolved:
            send(chat_id,
                f"Samajh nahi aaya ji.\n\n"
                f"Number ya naam bhejein:\n"
                f"Jaise: 1 ya Karnal\n\n"
                f"{DISTRICT_LIST_TEXT}"
            )
            return True
        district_name, mandis = DISTRICTS[resolved]
        set_session(chat_id,
            step="awaiting_category",
            district=district_name,
            mandis=mandis,
            crops=""
        )
        send(chat_id,
            f"Jila: {district_name}\n\n"
            f"Ab fasal ki category (Category) chunein.\n"
            f"Number ya naam -- dono chalega:\n\n"
            f"{CATEGORY_LIST_TEXT}"
        )
        return True

    # step 3 -- category (select = get ALL crops in that category)
    if step == "awaiting_category":
        resolved_cats = resolve_categories(text_clean)
        if not resolved_cats:
            send(chat_id,
                f"Samajh nahi aaya ji.\n\n"
                f"Number ya naam bhejein:\n"
                f"Jaise: 1 ya Anaj\n\n"
                f"{CATEGORY_LIST_TEXT}"
            )
            return True

        all_crops = get_crops_for_categories(resolved_cats)
        existing  = session.get("crops") or ""
        exist_list = [c for c in existing.split(",") if c]
        combined  = list(dict.fromkeys(exist_list + all_crops))
        crops_str = ",".join(combined)

        cat_names = " + ".join(
            CROP_CATEGORIES[k][0]
            for k in resolved_cats if k in CROP_CATEGORIES
        )

        set_session(chat_id,
            step="awaiting_more_categories",
            selected_category=",".join(resolved_cats),
            crops=crops_str
        )

        send(chat_id,
            f"Category add ki gayi: {cat_names}\n\n"
            f"Kya aur category chahiye?\n\n"
            f"1. Haan -- aur category add karo\n"
            f"2. Nahi -- registration complete karo"
        )
        return True

    # step 4 -- aur category ya complete
    if step == "awaiting_more_categories":
        want_more = text_clean == "1" or text_lower in [
            "haan", "ha", "yes", "aur", "haan ji", "haa",
            "haan chahiye", "aur chahiye"
        ]
        if want_more:
            set_session(chat_id, step="awaiting_category")
            send(chat_id,
                f"Aur category chunein:\n\n{CATEGORY_LIST_TEXT}"
            )
            return True

        name     = session.get("name", user_first_name)
        district = session.get("district")
        mandis   = session.get("mandis")
        crops    = session.get("crops", "")

        if not crops:
            set_session(chat_id, step="awaiting_category")
            send(chat_id,
                f"Koi category nahi chuni ji.\n\n"
                f"Category chunein:\n\n{CATEGORY_LIST_TEXT}"
            )
            return True

        if not is_valid_name(name):
            name = user_first_name or "Kisan"

        add_subscriber(chat_id, name, district, mandis, crops)
        clear_session(chat_id)

        crop_count = len([c for c in crops.split(",") if c])
        send(chat_id,
            f"Bahut badhiya {name} ji!\n\n"
            f"Aapka profile (Profile) taiyaar ho gaya:\n"
            f"Naam: {name}\n"
            f"Jila: {district}\n"
            f"Fasalein: {crop_count} fasalein selected\n\n"
            f"Rozana subah 6:30 baje\n"
            f"aapki fasal ka mandi bhav (Mandi Rate)\n"
            f"automatically aayega.\n\n"
            f"Abhi ka bhav (Rate): /mera_bhav\n"
            f"Profile dekhein: /profile\n"
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

    # priority 0 -- admin
    if handle_admin(chat_id, text_lower):
        return

    # priority 1 -- registration flow
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
                f"/update -- Profile badlo\n"
                f"/band -- Alerts band karo\n"
                f"/help -- Madad"
            )
            return
        clear_session(chat_id)
        set_session(chat_id, step="awaiting_name")
        send(chat_id,
            "Ram Ram! Haryana Mandi Bhav Bot mein\n"
            "aapka swagat hai!\n\n"
            "Yeh bot kya karta hai:\n"
            "- Rozana subah 6:30 baje mandi bhav\n"
            "- MSP se tulna -- bechein ya ruken\n"
            "- Sirf aapki fasal ka data\n"
            "- Bilkul muft (Free)\n\n"
            "Pehle apna naam (Name) batayein:\n"
            "Jaise: Suresh Kumar"
        )
        return

    # priority 3 -- /profile
    if text_clean == "/profile":
        sub = get_subscriber(chat_id)
        if sub:
            crop_list = sub['crops'].replace(",", ", ")
            send(chat_id,
                f"Aapka Profile\n\n"
                f"Naam (Name): {sub['name']}\n"
                f"Jila (District): {sub['district']}\n"
                f"Fasalein (Crops): {crop_list}\n"
                f"Status: Active\n"
                f"Joined: {sub['added_date']}\n\n"
                f"/update se profile badlein"
            )
        else:
            send(chat_id,
                "Aap registered nahi hain.\n"
                "Register karne ke liye 'Hi' bhejein."
            )
        return

    # priority 4 -- bhav
    if text_lower in BHAV_TRIGGERS:
        sub = get_subscriber(str(chat_id))
        if not sub:
            send(chat_id,
                "Aap abhi registered nahi hain.\n\n"
                "Register karne ke liye\n"
                "'Hi' ya 'Ram Ram' bhejein."
            )
            return
        send(chat_id,
            "Aapka bhav (Rate) nikal raha hai...\n"
            "Thoda intezaar karein."
        )
        threading.Thread(
            target=send_instant_bhav,
            args=(chat_id, sub)
        ).start()
        return

    # priority 5 -- /band
    if text_lower in BAND_TRIGGERS:
        deactivate_subscriber(chat_id)
        clear_session(chat_id)
        send(chat_id,
            "Aapke alerts band (Stop) kar diye gaye hain.\n\n"
            "Dobara shuru karne ke liye 'Hi' bhejein.\n"
            "Aapka data save hai."
        )
        return

    # priority 6 -- /update
    if text_lower in UPDATE_TRIGGERS:
        clear_session(chat_id)
        set_session(chat_id, step="awaiting_name")
        send(chat_id,
            "Profile update karte hain.\n\n"
            "Apna naam (Name) batayein:\n"
            "(Same rakhna ho to wahi dobara likhein)"
        )
        return

    # priority 7 -- /help
    if text_lower in HELP_TRIGGERS:
        send(chat_id,
            "Haryana Mandi Bhav Bot -- Madad\n\n"
            "Yeh bhejein:\n"
            "Hi / Ram Ram -- Register ya profile dekhein\n"
            "/mera_bhav -- Abhi ka bhav (Rate)\n"
            "/profile -- Apna profile\n"
            "/update -- Profile badlein\n"
            "/band -- Alerts band karein\n"
            "/help -- Yeh message\n\n"
            "Rozana subah 6:30 baje automatically\n"
            "aapki fasal ka mandi bhav milega."
        )
        return

    # fallback
    send(chat_id,
        "Samajh nahi aaya ji.\n\n"
        "Bhav ke liye: /mera_bhav\n"
        "Madad ke liye: /help\n"
        "Register ke liye: Hi"
    )


def send_instant_bhav(chat_id, subscriber):
    try:
        message = get_bhav_for_subscriber(subscriber)
        if message:
            send(chat_id, message)
        else:
            send(chat_id,
                "Abhi aapke jile ka data nahi aaya.\n"
                "Thodi der mein dobara try karein.\n"
                "Ya kal subah 6:30 baje automatically milega."
            )
    except Exception as e:
        send(chat_id,
            "Data laane mein dikkat aayi.\n"
            "Thodi der mein /mera_bhav try karein."
        )
        print(f"[BOT ERROR] {e}")
        import traceback
        traceback.print_exc()


def keep_alive():
    time.sleep(60)
    while True:
        try:
            requests.get(
                "https://mandi-bot.onrender.com/",
                timeout=10
            )
            print("[KEEPALIVE] Pinged")
        except Exception as e:
            print(f"[KEEPALIVE ERROR] {e}")
        time.sleep(600)


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
    init_db()

    # keep-alive ping
    threading.Thread(target=keep_alive, daemon=True).start()

    # daily scheduler -- 6:30 AM IST = 01:00 UTC
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_daily_pipeline,
        "cron",
        hour=6,
        minute=30,
        id="daily_mandi_bhav"
    )
    scheduler.start()
    print("[SCHEDULER] Daily job set for 6:30 AM IST")

    print("[BOT] Starting webhook server...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)