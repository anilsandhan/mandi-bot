import sqlite3
import os
from datetime import date, timedelta
from fetcher import get_prices_for_date, get_todays_prices, get_mandis_in_db

MSP = {
    "wheat":     2425,
    "paddy":     2300,
    "mustard":   5950,
    "barley":    1850,
    "maize":     2225,
    "bajra":     2625,
    "sunflower": 7280,
    "cotton":    7121,
    "sugarcane": 340,
}


def group_by_commodity(prices):
    grouped = {}
    for p in prices:
        key = p["commodity"].lower()
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(p)
    return grouped


def avg_modal(price_list):
    modals = [p["modal_price"] for p in price_list if p["modal_price"] > 0]
    return round(sum(modals) / len(modals)) if modals else 0


def best_market(price_list):
    valid = [p for p in price_list if p["modal_price"] > 0]
    if not valid:
        return None, 0
    best = max(valid, key=lambda p: p["modal_price"])
    return best["market"], best["modal_price"]


def get_msp(commodity_lower):
    for key in MSP:
        if key in commodity_lower:
            return MSP[key]
    return None


def get_4day_avg(commodity, wanted_mandis=None):
    today  = date.today()
    prices = []
    for i in range(1, 5):
        day_prices = get_prices_for_date(today - timedelta(days=i))
        for p in day_prices:
            if commodity in p["commodity"].lower():
                if wanted_mandis:
                    if any(m in p["market"].lower() for m in wanted_mandis):
                        prices.append(p["modal_price"])
                else:
                    prices.append(p["modal_price"])
    if not prices:
        return None
    return round(sum(prices) / len(prices))


def get_mandi_coverage(subscriber):
    wanted_mandis = [
        m.strip().lower()
        for m in subscriber["mandis"].split(",")
    ]
    today_mandis = get_mandis_in_db(date.today())
    present = []
    missing = []
    for m in wanted_mandis:
        if any(m in tm for tm in today_mandis):
            present.append(m.title())
        else:
            missing.append(m.title())
    return present, missing


def build_crop_entry(commodity, price_list, wanted_mandis=None):
    avg_today = avg_modal(price_list)
    if avg_today == 0:
        return None

    msp          = get_msp(commodity)
    market_name, best_price = best_market(price_list)
    msp_diff     = avg_today - msp if msp else None
    msp_diff_pct = round((msp_diff / msp) * 100, 1) if msp else None

    avg_4day   = get_4day_avg(commodity, wanted_mandis)
    change_pct = None
    if avg_4day and avg_4day > 0:
        change_pct = round(
            ((avg_today - avg_4day) / avg_4day) * 100, 1
        )

    if msp_diff is not None and msp_diff > 0:
        signal = "SELL"
    elif msp_diff is not None and msp_diff < -100:
        signal = "WAIT"
    else:
        signal = "NEUTRAL"

    return {
        "commodity":    commodity,
        "avg_modal":    avg_today,
        "best_market":  market_name,
        "best_price":   best_price,
        "msp":          msp,
        "msp_diff":     msp_diff,
        "msp_diff_pct": msp_diff_pct,
        "week_change":  change_pct,
        "avg_4day":     avg_4day,
        "signal":       signal,
        "num_markets":  len(price_list),
    }


def analyse():
    today_prices = get_todays_prices()
    if not today_prices:
        print("[ANALYSE] No prices for today")
        return None

    grouped = group_by_commodity(today_prices)
    summary = {
        "date":          str(date.today()),
        "total_records": len(today_prices),
        "crops":         [],
    }

    for commodity, price_list in grouped.items():
        entry = build_crop_entry(commodity, price_list)
        if entry:
            summary["crops"].append(entry)

    signal_order = {"SELL": 0, "NEUTRAL": 1, "WAIT": 2}
    summary["crops"].sort(
        key=lambda x: signal_order.get(x["signal"], 9)
    )

    print(f"[ANALYSE] {len(summary['crops'])} crops analysed")
    for c in summary["crops"]:
        trend = (f"{c['week_change']:+.1f}% vs 4-day"
                 if c["week_change"] is not None else "no history")
        msp_s = (f"MSP diff Rs.{c['msp_diff']}"
                 if c["msp_diff"] is not None else "no MSP")
        print(f"  {c['commodity']:25} | Rs.{c['avg_modal']:5} | "
              f"{msp_s:22} | {trend} | {c['signal']}")

    return summary


def analyse_for_subscriber(subscriber):
    all_prices = get_todays_prices()
    if not all_prices:
        return None

    wanted_mandis = [
        m.strip().lower()
        for m in subscriber["mandis"].split(",")
    ]
    wanted_crops = [
        c.strip().lower()
        for c in subscriber["crops"].split(",")
    ]

    # primary -- subscriber mandis + crops
    filtered = [
        p for p in all_prices
        if any(m in p["market"].lower() for m in wanted_mandis)
        and any(c in p["commodity"].lower() for c in wanted_crops)
    ]

    # fallback 1 -- any mandi with their crops
    if not filtered:
        print(f"[ANALYSE] No mandi+crop match -- crop-only fallback")
        filtered = [
            p for p in all_prices
            if any(c in p["commodity"].lower() for c in wanted_crops)
        ]

    # fallback 2 -- last 4 days
    if not filtered:
        print(f"[ANALYSE] No today data -- checking last 4 days")
        today = date.today()
        for i in range(1, 5):
            day_prices = get_prices_for_date(today - timedelta(days=i))
            filtered = [
                p for p in day_prices
                if any(m in p["market"].lower() for m in wanted_mandis)
                and any(c in p["commodity"].lower() for c in wanted_crops)
            ]
            if filtered:
                print(f"[ANALYSE] Found data from "
                      f"{today - timedelta(days=i)}")
                break

    if not filtered:
        print(f"[ANALYSE] No data for {subscriber['name']}")
        return None

    present_mandis, missing_mandis = get_mandi_coverage(subscriber)
    grouped = group_by_commodity(filtered)

    summary = {
        "date":            str(date.today()),
        "subscriber_name": subscriber["name"],
        "district":        subscriber["district"],
        "total_records":   len(filtered),
        "fallback_used":   any(p.get("is_fallback", 0) for p in filtered),
        "present_mandis":  present_mandis,
        "missing_mandis":  missing_mandis,
        "crops":           [],
    }

    for commodity, price_list in grouped.items():
        entry = build_crop_entry(commodity, price_list, wanted_mandis)
        if entry:
            summary["crops"].append(entry)

    signal_order = {"SELL": 0, "NEUTRAL": 1, "WAIT": 2}
    summary["crops"].sort(
        key=lambda x: signal_order.get(x["signal"], 9)
    )

    print(f"[ANALYSE] {subscriber['name']}: "
          f"{len(summary['crops'])} crops | "
          f"present: {present_mandis} | "
          f"missing: {missing_mandis}")

    return summary


if __name__ == "__main__":
    analyse()