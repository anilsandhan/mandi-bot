import os
import re
import random
import requests
from datetime import datetime


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
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "DATABASE_URL"]:
        if key not in env and os.environ.get(key):
            env[key] = os.environ.get(key)
    return env


ENV           = load_env()
ANTHROPIC_KEY = ENV.get("ANTHROPIC_API_KEY", "")

HARYANVI_QUOTES = [
    "जै बाबा रामदेव! खेती में खुशहाली रहे।",
    "मेहनत का फल मीठा होता है — बढ़ते रहो।",
    "हरियाणा का किसान देश की शान है।",
    "फसल अच्छी हो, दाम अच्छे हों — यही दुआ है।",
    "जमीन से जुड़े रहो, तरक्की होगी।",
    "किसान खुश तो हरियाणा खुश।",
    "मेहनत कर, फल पाएगा — यही खेती का धर्म है।",
]


def get_quote():
    return random.choice(HARYANVI_QUOTES)


def format_date(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        months = {
            1: "जनवरी", 2: "फरवरी", 3: "मार्च",
            4: "अप्रैल", 5: "मई", 6: "जून",
            7: "जुलाई", 8: "अगस्त", 9: "सितंबर",
            10: "अक्टूबर", 11: "नवंबर", 12: "दिसंबर"
        }
        return f"{d.day} {months[d.month]} {d.year}"
    except Exception:
        return date_str


def build_personalised_prompt(summary):
    district       = summary.get("district", "हरियाणा")
    today_mandis   = summary.get("today_mandis", [])
    fallback_mandi = summary.get("fallback_mandis", {})
    missing_mandis = summary.get("missing_mandis", [])
    date_str       = format_date(summary["date"])
    quote          = get_quote()

    # build crop lines for prompt
    crops_text = ""
    for c in summary["crops"]:
        if c["msp_diff"] is not None:
            diff_dir = "ऊपर" if c["msp_diff"] > 0 else "नीचे"
            msp_line = f"MSP से ₹{abs(c['msp_diff'])} {diff_dir}"
            sig      = "✅ बेचें" if c["msp_diff"] > 0 else "⏳ रुकें"
        else:
            msp_line = "MSP लागू नहीं"
            sig      = "ℹ️"

        if c["week_change"] is not None:
            trend = f"4 दिन से {c['week_change']:+.1f}%"
        elif c.get("avg_4day"):
            trend = f"औसत ₹{c['avg_4day']}"
        else:
            trend = "पहला दिन"

        best = ""
        if c.get("best_market"):
            best = f"बेस्ट: {c['best_market']} ₹{c['best_price']}"

        crops_text += (
            f"\n• {c['commodity']}: ₹{c['avg_modal']}/क्विंटल"
            f" | {msp_line} | {trend}"
            f" | {best} | {sig}"
        )

    # build mandi status section
    mandi_lines = []
    if today_mandis:
        mandi_lines.append(
            f"आज का data: {', '.join(today_mandis)}"
        )
    for mandi, info in fallback_mandi.items():
        mandi_lines.append(
            f"{mandi}: {info['status']}"
        )
    if missing_mandis:
        mandi_lines.append(
            f"data नहीं मिला (4 दिन में): "
            f"{', '.join(missing_mandis)}"
        )
    mandi_section = "\n".join(mandi_lines)

    return f"""हरियाणा किसान मंडी भाव message लिखो।

जिला: {district}
तारीख: {date_str}

फसल data:
{crops_text}

मंडी की स्थिति:
{mandi_section}

नियम — सख्ती से follow करो:
1. पहली लाइन: "राम राम किसान भाइयों! 🙏"
2. दूसरी लाइन: "{date_str} | {district} | मंडी भाव"
3. खाली लाइन
4. हर फसल — emoji, नाम, भाव, MSP तुलना, signal (SELL वाली पहले)
5. खाली लाइन
6. मंडी स्थिति — किस मंडी का आज data है, किसका कल का, किसका नहीं मिला
7. खाली लाइन
8. एक सलाह की लाइन
9. आखिरी लाइन exactly: "{quote}"
10. कोई ** bold ** नहीं — plain text only
11. "WhatsApp Message" या "Character count" बिल्कुल नहीं
12. --- या extra symbols नहीं
13. अधिकतम 550 अक्षर

Message:"""


def clean_message(text):
    text = text.replace("**", "")
    text = re.sub(r'\*?Character count.*', '', text)
    text = re.sub(r'WhatsApp Message:?\*?\*?', '', text)
    text = re.sub(r'-{3,}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def generate_hindi_message(summary, prompt_override=None):
    if not ANTHROPIC_KEY:
        print("[NARRATOR] No API key -- using fallback")
        return build_fallback_message(summary)

    prompt = prompt_override or build_personalised_prompt(summary)

    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    body = {
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 700,
        "messages":   [{"role": "user", "content": prompt}],
    }

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=25,
        )
        r.raise_for_status()
        message = r.json()["content"][0]["text"].strip()
        message = clean_message(message)
        print(f"[NARRATOR] Generated {len(message)} chars")
        return message
    except Exception as e:
        print(f"[NARRATOR ERROR] {e} -- fallback")
        return build_fallback_message(summary)


def build_fallback_message(summary):
    district       = summary.get("district", "हरियाणा")
    date_str       = format_date(summary["date"])
    today_mandis   = summary.get("today_mandis", [])
    fallback_mandi = summary.get("fallback_mandis", {})
    missing_mandis = summary.get("missing_mandis", [])

    lines = [
        "राम राम किसान भाइयों! 🙏",
        f"{date_str} | {district} | मंडी भाव",
        "",
    ]

    for c in summary["crops"][:6]:
        msp_str = ""
        if c["msp_diff"] is not None:
            d = "ऊपर" if c["msp_diff"] > 0 else "नीचे"
            msp_str = f" | MSP से ₹{abs(c['msp_diff'])} {d}"
        sig = " ✅ बेचें" if c["signal"] == "SELL" else \
              " ⏳ रुकें" if c["signal"] == "WAIT" else ""
        lines.append(
            f"• {c['commodity']}: ₹{c['avg_modal']}/क्विंटल"
            f"{msp_str}{sig}"
        )

    lines.append("")

    # mandi status
    if today_mandis:
        lines.append(f"✅ आज का data: {', '.join(today_mandis)}")
    for mandi, info in fallback_mandi.items():
        lines.append(f"⚠️ {mandi}: {info['status']} use हुआ")
    if missing_mandis:
        lines.append(
            f"❌ data नहीं मिला: {', '.join(missing_mandis)}"
        )

    lines.append("")
    lines.append(get_quote())
    return "\n".join(lines)


if __name__ == "__main__":
    from analyser import analyse
    summary = analyse()
    if summary:
        msg = generate_hindi_message(summary)
        print(msg)