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

CROP_CATEGORIES = {
    "1": ("अनाज (Grains)",
          ["Wheat", "Mustard", "Barley", "Paddy",
           "Maize", "Bajra", "Sunflower"]),
    "2": ("सब्जियां (Vegetables)",
          ["Onion", "Potato", "Tomato", "Cucumbar(Kheera)",
           "Garlic", "Ginger", "Bottle Gourd", "Brinjal"]),
    "3": ("फल (Fruits)",
          ["Apple", "Banana", "Chikoos(Sapota)",
           "Mango", "Guava"]),
    "4": ("अन्य (Others)",
          ["Dry Fodder", "Green Fodder", "Cotton", "Sugarcane"]),
}

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

DISTRICT_LIST_TEXT = "\n".join(
    f"{k}. {v[0]}" for k, v in DISTRICTS.items()
)

CATEGORY_LIST_TEXT = (
    "1. अनाज\n"
    "   (गेहूं, सरसों, जौ, धान, मक्का, बाजरा)\n\n"
    "2. सब्जियां\n"
    "   (प्याज, आलू, टमाटर, खीरा, लहसुन)\n\n"
    "3. फल\n"
    "   (सेब, केला, चीकू, आम, अमरूद)\n\n"
    "4. अन्य\n"
    "   (चारा, कपास, गन्ना)\n\n"
    "Number bhejein: 1, 2, 3, ya 4\n"
    "Ek se zyada: 1,2"
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
    "/admin", "/stats", "/users", "/today",
    "/bhav", "/health"
]


def resolve_district(text):
    t = text.strip().lower()
    # strip leading numbers and dots like "1." or "1. "
    import re
    t_clean = re.sub(r'^\d+[\.\)]\s*', '', t).strip()
    if t_clean in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[t_clean]
    # try pure number
    num = text.strip().split(".")[0].strip()
    if num in DISTRICTS:
        return num
    # try original lowered
    if t in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[t]
    return None


def resolve_categories(text):
    import re
    parts = [p.strip() for p in text.split(",")]
    result = []
    for part in parts:
        p = part.strip().lower()
        p_clean = re.sub(r'^\d+[\.\)]\s*', '', p).strip()
        if p_clean in CATEGORY_ALIASES:
            result.append(CATEGORY_ALIASES[p_clean])
            continue
        if p in CATEGORY_ALIASES:
            result.append(CATEGORY_ALIASES[p])
            continue
        num = p.split(".")[0].strip()
        if num in CROP_CATEGORIES:
            result.append(num)
            continue
        if p in CROP_CATEGORIES:
            result.append(p)
    return list(dict.fromkeys(result))


def get_crops_for_categories(cat_keys):
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
    payload = {"chat_id": str(chat_id), "text": text}
    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json=payload, timeout=10
        )
        print(f"[SEND] to={chat_id} status={r.status_code}")
        if r.status_code != 200:
            print(f"[SEND FAIL] {r.text[:300]}")
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


def get_bhav_message(subscriber):
    try:
        from fetcher import get_todays_prices
        from analyser import analyse_for_subscriber
        from narrator import (generate_hindi_message,
                               build_personalised_prompt)

        # check if today's data exists
        prices = get_todays_prices()
        if not prices:
            print("[BHAV] No prices in DB -- fetching now...")
            from fetcher import run as fetch_run
            fetch_run()

        summary = analyse_for_subscriber(subscriber)
        if not summary or not summary.get("crops"):
            print(f"[BHAV] No summary for {subscriber['name']}")
            return None
        prompt  = build_personalised_prompt(summary)
        message = generate_hindi_message(
            summary, prompt_override=prompt
        )
        return message
    except Exception as e:
        print(f"[BHAV ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None


def run_daily_pipeline():
    print("[PIPELINE] Starting daily pipeline...")
    try:
        from fetcher import run as fetch_run
        prices = fetch_run()
        if not prices:
            print("[PIPELINE] No prices fetched")
            return

        subscribers = get_active_subscribers()
        print(f"[PIPELINE] {len(subscribers)} subscribers")

        for sub in subscribers:
            try:
                msg = get_bhav_message(sub)
                if msg:
                    send(sub["telegram_id"], msg)
                    print(f"[PIPELINE] Sent to {sub['name']}")
                else:
                    send(sub["telegram_id"],
                        "आज आपके जिले का मंडी डेटा नहीं आया।\n"
                        "कल सुबह 6:30 बजे फिर मिलेगा।"
                    )
            except Exception as e:
                print(f"[PIPELINE] Error for {sub['name']}: {e}")

        print("[PIPELINE] Done")
    except Exception as e:
        print(f"[PIPELINE ERROR] {e}")
        import traceback
        traceback.print_exc()


def handle_admin(chat_id, text_lower):
    if str(chat_id) != ADMIN_ID:
        return False
    if text_lower not in ADMIN_COMMANDS:
        return False

    today_str = str(date.today())

    # /stats
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
            mandis = cur.fetchone()[0]
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
                SELECT district, COUNT(*) FROM subscribers
                WHERE active=1 GROUP BY district ORDER BY 2 DESC
            """)
            dists = cur.fetchall()
            cur.close()
            conn.close()

            dist_txt = "\n".join(
                f"  {r[0]}: {r[1]}" for r in dists
            ) or "  Koi nahi"

            send(chat_id,
                f"ADMIN STATS\n{'='*25}\n\n"
                f"Subscribers\n"
                f"Active: {active}\n"
                f"Unsubscribed: {inactive}\n"
                f"Total: {total}\n"
                f"Mid-reg: {sessions}\n\n"
                f"Today ({today_str})\n"
                f"Mandis: {mandis}\n"
                f"Fresh: {fresh}\n"
                f"Fallback: {fallback}\n\n"
                f"By District\n{dist_txt}"
            )
        except Exception as e:
            send(chat_id, f"Stats error: {e}")
        return True

    # /users
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

            lines = [f"Subscribers ({len(rows)} total)\n"]
            for r in rows:
                name, tid, dist, crops, joined, active = r
                status = "Active" if active == 1 else "Inactive"
                crop_count = len([c for c in (crops or "").split(",") if c])
                lines.append(
                    f"{name or '?'} [{status}]\n"
                    f"  ID: {tid}\n"
                    f"  Jila: {dist or '?'}\n"
                    f"  Fasalein: {crop_count} crops\n"
                    f"  Joined: {joined or '?'}\n"
                )
            send(chat_id, "\n".join(lines)[:4000])
        except Exception as e:
            send(chat_id, f"Users error: {e}")
        return True

    # /today
    if text_lower == "/today":
        try:
            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("""
                SELECT market, COUNT(*) FROM prices
                WHERE fetch_date = %s AND is_fallback = 0
                GROUP BY market ORDER BY market
            """, (today_str,))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if not rows:
                send(chat_id,
                    f"Aaj ({today_str}) fresh data nahi aaya.\n"
                    f"/bhav command se fetch karo."
                )
                return True

            lines = [f"Today ({today_str}) -- {len(rows)} mandis\n"]
            for r in rows:
                lines.append(f"  {r[0]}: {r[1]} crops")
            send(chat_id, "\n".join(lines)[:4000])
        except Exception as e:
            send(chat_id, f"Today error: {e}")
        return True

    # /bhav -- fetch + send to all subscribers NOW
    if text_lower == "/bhav":
        send(chat_id,
            "Pipeline shuru ho rahi hai...\n"
            "Data fetch karke sabko bhav bhejunga.\n"
            "2-3 minute lagenge."
        )
        threading.Thread(
            target=run_daily_pipeline, daemon=True
        ).start()
        return True

    # /health -- system health check
    if text_lower == "/health":
        try:
            report = ["SYSTEM HEALTH CHECK\n" + "="*25 + "\n"]

            # 1. DB connection
            try:
                conn = get_conn()
                cur  = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                conn.close()
                report.append("DB: OK (Supabase connected)")
            except Exception as e:
                report.append(f"DB: FAIL -- {e}")

            # 2. subscribers count
            try:
                subs = get_active_subscribers()
                report.append(f"Subscribers: {len(subs)} active")
            except Exception as e:
                report.append(f"Subscribers: FAIL -- {e}")

            # 3. today's price data
            try:
                conn = get_conn()
                cur  = conn.cursor()
                cur.execute("""
                    SELECT COUNT(*), MAX(fetch_date)
                    FROM prices
                """)
                row = cur.fetchone()
                cur.execute("""
                    SELECT COUNT(*) FROM prices
                    WHERE fetch_date = %s
                """, (today_str,))
                today_count = cur.fetchone()[0]
                cur.close()
                conn.close()
                report.append(
                    f"Price DB: {row[0]} total records\n"
                    f"  Latest date: {row[1]}\n"
                    f"  Today ({today_str}): {today_count} records"
                )
            except Exception as e:
                report.append(f"Price DB: FAIL -- {e}")

            # 4. Agmarknet API
            try:
                r = requests.get(
                    "https://data.gov.in/resource/"
                    "9ef84268-d588-465a-a308-a864a43d0070"
                    f"?api-key={ENV.get('DATA_GOV_API_KEY','')}"
                    "&format=json&limit=1",
                    timeout=10
                )
                if r.status_code == 200:
                    report.append("Agmarknet API: OK")
                else:
                    report.append(
                        f"Agmarknet API: HTTP {r.status_code}"
                    )
            except Exception as e:
                report.append(f"Agmarknet API: FAIL -- {e}")

            # 5. Anthropic API
            try:
                r = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ENV.get("ANTHROPIC_API_KEY",""),
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 10,
                        "messages": [{"role": "user",
                                      "content": "say ok"}]
                    },
                    timeout=10
                )
                if r.status_code == 200:
                    report.append("Anthropic API: OK")
                else:
                    report.append(
                        f"Anthropic API: HTTP {r.status_code}"
                    )
            except Exception as e:
                report.append(f"Anthropic API: FAIL -- {e}")

            # 6. Scheduler status
            report.append("Scheduler: 6:30 AM IST daily")

            send(chat_id, "\n".join(report))

        except Exception as e:
            send(chat_id, f"Health check error: {e}")
        return True

    return False


def handle_registration_step(chat_id, text_clean, session,
                              user_first_name):
    step       = session.get("step")
    text_lower = text_clean.lower().strip()

    if text_lower in BAND_TRIGGERS + HELP_TRIGGERS:
        return False

    # naam
    if step == "awaiting_name":
        if not is_valid_name(text_clean):
            send(chat_id,
                "अपना नाम बताएं।\n"
                "Jaise: Suresh Kumar\n\n"
                "Naam likhein:"
            )
            return True
        set_session(chat_id, step="awaiting_district",
                    name=text_clean)
        send(chat_id,
            f"Shukriya {text_clean} ji!\n\n"
            f"अपना जिला चुनें।\n"
            f"Number bhejein:\n\n"
            f"{DISTRICT_LIST_TEXT}"
        )
        return True

    # jila
    if step == "awaiting_district":
        resolved = resolve_district(text_clean)
        if not resolved:
            send(chat_id,
                f"Samajh nahi aaya.\n"
                f"Number bhejein (1-12):\n\n"
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
            f"जिला: {district_name}\n\n"
            f"अब फसल की category चुनें।\n"
            f"Number bhejein:\n\n"
            f"{CATEGORY_LIST_TEXT}"
        )
        return True

    # category -- select gets ALL crops in that category
    if step == "awaiting_category":
        resolved_cats = resolve_categories(text_clean)
        if not resolved_cats:
            send(chat_id,
                f"Samajh nahi aaya.\n"
                f"Number bhejein (1-4):\n\n"
                f"{CATEGORY_LIST_TEXT}"
            )
            return True

        all_crops = get_crops_for_categories(resolved_cats)
        existing  = session.get("crops") or ""
        exist_list = [c for c in existing.split(",") if c]
        combined  = list(dict.fromkeys(exist_list + all_crops))
        crops_str = ",".join(combined)

        cat_names = ", ".join(
            CROP_CATEGORIES[k][0]
            for k in resolved_cats if k in CROP_CATEGORIES
        )

        set_session(chat_id,
            step="awaiting_more_categories",
            selected_category=",".join(resolved_cats),
            crops=crops_str
        )

        send(chat_id,
            f"Category add hui: {cat_names}\n\n"
            f"क्या और category चाहिए?\n\n"
            f"1. हाँ -- aur category add karo\n"
            f"2. नहीं -- registration complete karo"
        )
        return True

    # aur category ya complete
    if step == "awaiting_more_categories":
        want_more = text_clean == "1" or text_lower in [
            "haan", "ha", "yes", "aur", "haan ji", "haa",
            "1", "han", "haa", "chahiye"
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
                f"Koi category nahi chuni.\n\n"
                f"Category chunein:\n\n{CATEGORY_LIST_TEXT}"
            )
            return True

        if not is_valid_name(name):
            name = user_first_name or "Kisan"

        print(f"[REG] Saving: name={name} district={district} "
              f"crops={crops[:50]}")
        add_subscriber(chat_id, name, district, mandis, crops)
        clear_session(chat_id)

        # verify it saved
        saved = get_subscriber(str(chat_id))
        if saved:
            print(f"[REG] Verified saved: {saved['name']}")
        else:
            print(f"[REG] WARNING: subscriber not found after save!")

        crop_count = len([c for c in crops.split(",") if c])
        send(chat_id,
            f"Bahut badhiya {name} ji!\n\n"
            f"Profile taiyaar ho gaya:\n"
            f"नाम: {name}\n"
            f"जिला: {district}\n"
            f"फसलें: {crop_count} fasalein selected\n\n"
            f"Rozana subah 6:30 baje\n"
            f"aapki fasal ka mandi bhav milega.\n\n"
            f"Abhi ka bhav: /mera_bhav\n"
            f"Profile: /profile\n"
            f"Madad: /help\n\n"
            f"खेती में खुशहाली रहे!"
        )
        return True

    return False


def handle_message(chat_id, text, user_first_name):
    text_clean = text.strip()
    text_lower = text_clean.lower().strip()
    session    = get_session(chat_id)

    print(f"[MSG] from={chat_id} ({user_first_name}) "
          f"step={session.get('step') if session else None} "
          f"text='{text_clean}'")

    # priority 0 -- admin
    if handle_admin(chat_id, text_lower):
        return

    # priority 1 -- registration
    if session and session.get("step") in REGISTRATION_STEPS:
        handled = handle_registration_step(
            chat_id, text_clean, session, user_first_name
        )
        if handled:
            return

    # priority 2 -- greeting
    if is_greeting(text_clean) or text_clean == "/start":
        existing = get_subscriber(str(chat_id))
        if existing:
            send(chat_id,
                f"Ram Ram {existing['name']} ji!\n\n"
                f"आपका profile:\n"
                f"जिला: {existing['district']}\n"
                f"फसलें: {existing['crops']}\n\n"
                f"/mera_bhav -- अभी का भाव\n"
                f"/profile -- Profile देखें\n"
                f"/update -- Profile बदलें\n"
                f"/band -- Alerts band करें\n"
                f"/help -- मदद"
            )
            return
        clear_session(chat_id)
        set_session(chat_id, step="awaiting_name")
        send(chat_id,
            "राम राम! Haryana Mandi Bhav Bot में\n"
            "आपका स्वागत है!\n\n"
            "यह bot क्या करता है:\n"
            "- रोज़ सुबह 6:30 बजे मंडी भाव\n"
            "- MSP से तुलना\n"
            "- सिर्फ आपकी फसल का data\n"
            "- बिल्कुल मुफ्त\n\n"
            "अपना नाम बताएं:\n"
            "(Jaise: Suresh Kumar)"
        )
        return

    # priority 3 -- /profile
    if text_clean == "/profile":
        sub = get_subscriber(str(chat_id))
        if sub:
            crops = sub['crops'].replace(",", ", ")
            send(chat_id,
                f"आपका Profile\n\n"
                f"नाम: {sub['name']}\n"
                f"जिला: {sub['district']}\n"
                f"फसलें: {crops}\n"
                f"Status: Active\n"
                f"Joined: {sub['added_date']}\n\n"
                f"/update se profile badlein"
            )
        else:
            send(chat_id,
                "आप registered नहीं हैं।\n"
                "Register करें: 'Hi' भेजें।"
            )
        return

    # priority 4 -- bhav
    if text_lower in BHAV_TRIGGERS:
        sub = get_subscriber(str(chat_id))
        if not sub:
            send(chat_id,
                "आप registered नहीं हैं।\n\n"
                "Register करने के लिए\n"
                "'Hi' या 'Ram Ram' भेजें।"
            )
            return
        send(chat_id,
            "आपका भाव निकाल रहे हैं...\n"
            "थोड़ा इंतज़ार करें।"
        )
        threading.Thread(
            target=_send_bhav_thread,
            args=(chat_id, sub),
            daemon=True
        ).start()
        return

    # priority 5 -- /band
    if text_lower in BAND_TRIGGERS:
        deactivate_subscriber(chat_id)
        clear_session(chat_id)
        send(chat_id,
            "आपके alerts band कर दिए गए हैं।\n\n"
            "दोबारा शुरू करने के लिए 'Hi' भेजें।\n"
            "आपका data save है।"
        )
        return

    # priority 6 -- /update
    if text_lower in UPDATE_TRIGGERS:
        clear_session(chat_id)
        set_session(chat_id, step="awaiting_name")
        send(chat_id,
            "Profile update करते हैं।\n\n"
            "अपना नाम बताएं:\n"
            "(Same रखना हो तो वही लिखें)"
        )
        return

    # priority 7 -- /help
    if text_lower in HELP_TRIGGERS:
        send(chat_id,
            "Haryana Mandi Bhav Bot -- मदद\n\n"
            "यह भेजें:\n"
            "Hi / Ram Ram -- Register या profile\n"
            "/mera_bhav -- अभी का भाव\n"
            "/profile -- Profile देखें\n"
            "/update -- Profile बदलें\n"
            "/band -- Alerts band करें\n"
            "/help -- यह message\n\n"
            "रोज़ सुबह 6:30 बजे automatically\n"
            "आपकी फसल का मंडी भाव मिलेगा।"
        )
        return

    # fallback
    send(chat_id,
        "समझ नहीं आया।\n\n"
        "भाव के लिए: /mera_bhav\n"
        "मदद के लिए: /help\n"
        "Register के लिए: Hi"
    )


def _send_bhav_thread(chat_id, subscriber):
    try:
        msg = get_bhav_message(subscriber)
        if msg:
            send(chat_id, msg)
        else:
            send(chat_id,
                "अभी आपके जिले का data नहीं आया।\n"
                "थोड़ी देर में /mera_bhav try करें।\n"
                "या कल सुबह 6:30 बजे automatically मिलेगा।"
            )
    except Exception as e:
        send(chat_id,
            "Data लाने में दिक्कत आई।\n"
            "थोड़ी देर में /mera_bhav try करें।"
        )
        print(f"[BHAV THREAD ERROR] {e}")
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
            print("[KEEPALIVE] OK")
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
        print(f"[WEBHOOK] from={chat_id} ({first_name}) text='{text}'")
        if chat_id and text:
            try:
                handle_message(chat_id, text, first_name)
            except Exception as e:
                print(f"[HANDLE ERROR] {e}")
                import traceback
                traceback.print_exc()
                send(chat_id,
                    "कुछ गड़बड़ हो गई।\n"
                    "थोड़ी देर में दोबारा try करें।"
                )
    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")
    return "ok"


@app.route("/", methods=["GET"])
def index():
    return "Mandi Bot is running."


if __name__ == "__main__":
    init_db()
    threading.Thread(target=keep_alive, daemon=True).start()

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_daily_pipeline,
        "cron",
        hour=6,
        minute=30,
        id="daily_mandi_bhav"
    )
    scheduler.start()
    print("[SCHEDULER] 6:30 AM IST daily job set")

    print("[BOT] Starting...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)