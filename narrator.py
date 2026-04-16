import os
import requests
from datetime import date


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


ENV           = load_env()
ANTHROPIC_KEY = ENV.get("ANTHROPIC_API_KEY", "")


def build_prompt(summary):
    crops_text = ""
    for c in summary["crops"][:8]:
        if c["msp_diff"] is not None:
            msp_line = (
                f"MSP se Rs.{abs(c['msp_diff'])} "
                f"{'upar' if c['msp_diff'] > 0 else 'neeche'}"
            )
        else:
            msp_line = "MSP laagu nahi"
        trend = (
            f"{c['week_change']:+.1f}% (4-din avg se)"
            if c["week_change"] is not None
            else "naya data"
        )
        crops_text += (
            f"\n- {c['commodity']}: Rs.{c['avg_modal']}/quintal"
            f" | {msp_line} | {trend}"
            f" | best: {c['best_market']} Rs.{c['best_price']}"
            f" | {c['signal']}"
        )

    return f"""You are an agricultural advisor for Haryana farmers.
Write a WhatsApp message in Hindi (Devanagari script).

Date: {summary['date']}
Data:{crops_text}

Rules:
1. Hindi Devanagari script
2. First line: date + Haryana + Mandi Bhav
3. One line per crop: price, MSP comparison, trend, signal
4. SELL crops first
5. Last line: short advice
6. Max 600 characters
7. Simple farmer language

Write the message:"""


def build_personalised_prompt(summary):
    district      = summary.get("district", "Haryana")
    present       = summary.get("present_mandis", [])
    missing       = summary.get("missing_mandis", [])
    fallback_used = summary.get("fallback_used", False)

    if missing and fallback_used:
        data_note = (
            f"Aaj ki report nahi aayi: {', '.join(missing)}. "
            f"Kal ka data use kiya gaya."
        )
    elif missing:
        data_note = (
            f"Aaj report aayi: {', '.join(present)}. "
            f"Nahi aayi: {', '.join(missing)}."
        )
    else:
        data_note = f"Aaj ki taaza report: {', '.join(present)}."

    crops_text = ""
    for c in summary["crops"]:
        if c["msp_diff"] is not None:
            msp_line = (
                f"MSP se Rs.{abs(c['msp_diff'])} "
                f"{'upar' if c['msp_diff'] > 0 else 'neeche'}"
            )
        else:
            msp_line = "MSP laagu nahi"

        if c["week_change"] is not None:
            trend = f"{c['week_change']:+.1f}% (4-din se)"
        elif c.get("avg_4day"):
            trend = f"4-din avg: Rs.{c['avg_4day']}"
        else:
            trend = "pehla din"

        crops_text += (
            f"\n- {c['commodity']}: Rs.{c['avg_modal']}/quintal"
            f" | {msp_line} | {trend}"
            f" | best: {c['best_market']} Rs.{c['best_price']}"
            f" | {c['signal']}"
        )

    return f"""You are an agricultural advisor for Haryana farmers.
Write a WhatsApp message in Hindi (Devanagari script).

Farmer district: {district}
Date: {summary['date']}
Mandi status: {data_note}

Crops:{crops_text}

Rules:
1. Hindi Devanagari script only
2. First line: date + {district} + Mandi Bhav
3. One line per crop: price, MSP diff, best mandi, signal
4. SELL crops first
5. If mandis missing -- add ONE short warning line
6. Last line: short actionable advice
7. Max 550 characters
8. Simple language a farmer understands

Write the message:"""


def generate_hindi_message(summary, prompt_override=None):
    if not ANTHROPIC_KEY or ANTHROPIC_KEY == "your_key_here":
        print("[NARRATOR] No key -- using fallback")
        return build_fallback_message(summary)

    prompt = prompt_override if prompt_override else build_prompt(summary)

    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    body = {
        "model":    "claude-haiku-4-5-20251001",
        "max_tokens": 800,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=20,
        )
        r.raise_for_status()
        data    = r.json()
        message = data["content"][0]["text"].strip()
        print(f"[NARRATOR] Generated {len(message)} chars")
        return message
    except Exception as e:
        print(f"[NARRATOR ERROR] {e} -- using fallback")
        return build_fallback_message(summary)


def build_fallback_message(summary):
    district = summary.get("district", "Haryana")
    today    = summary["date"]
    missing  = summary.get("missing_mandis", [])
    present  = summary.get("present_mandis", [])

    lines = [f"Mandi Bhav -- {district} -- {today}\n"]

    for c in summary["crops"][:6]:
        msp_str = ""
        if c["msp_diff"] is not None:
            d = "upar" if c["msp_diff"] > 0 else "neeche"
            msp_str = f" (MSP se Rs.{abs(c['msp_diff'])} {d})"
        trend_str = ""
        if c["week_change"] is not None:
            trend_str = f" | {c['week_change']:+.1f}%"
        sig = " -- Bechen" if c["signal"] == "SELL" else ""
        lines.append(
            f"- {c['commodity']}: Rs.{c['avg_modal']}/q"
            f"{msp_str}{trend_str}{sig}"
        )

    if summary["crops"]:
        lines.append(
            f"\nBest mandi: {summary['crops'][0]['best_market']}"
        )
    if missing:
        lines.append(f"Aaj report nahi aayi: {', '.join(missing)}")
    if present:
        lines.append(f"Data: {', '.join(present)}")
    if summary.get("fallback_used"):
        lines.append("(Kuch data kal ka hai)")

    return "\n".join(lines)


def run(summary, prompt_override=None):
    message = generate_hindi_message(summary, prompt_override)
    print("\n" + "=" * 50)
    print("MESSAGE PREVIEW:")
    print("=" * 50)
    print(message)
    print("=" * 50)
    return message


if __name__ == "__main__":
    from analyser import analyse
    summary = analyse()
    if summary:
        run(summary)