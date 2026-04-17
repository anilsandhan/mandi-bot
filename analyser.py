from datetime import date, timedelta
from fetcher import get_prices_for_date, get_todays_prices

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
    modals = [p["modal_price"] for p in price_list
              if p["modal_price"] > 0]
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


def get_historical_avg(commodity, wanted_mandis, days=4):
    """Get average price from last N days for trend"""
    today  = date.today()
    prices = []
    for i in range(1, days + 1):
        day_prices = get_prices_for_date(today - timedelta(days=i))
        for p in day_prices:
            if commodity in p["commodity"].lower():
                if any(m.lower() in p["market"].lower()
                       for m in wanted_mandis):
                    if p["modal_price"] > 0:
                        prices.append(p["modal_price"])
    return round(sum(prices) / len(prices)) if prices else None


def get_mandi_status(subscriber):
    """
    For each mandi in subscriber's list, check:
    - Does it have today's fresh data?
    - If not, how many days back do we have to go?
    Returns dict: {mandi_name: {"status": "today"/"1 day ago"/etc, "date": date}}
    """
    wanted_mandis = [m.strip() for m in subscriber["mandis"].split(",")]
    today         = date.today()
    status        = {}

    for mandi in wanted_mandis:
        found = False
        for days_back in range(0, 5):
            check_date = today - timedelta(days=days_back)
            day_prices = get_prices_for_date(check_date)
            for p in day_prices:
                if mandi.lower() in p["market"].lower():
                    if days_back == 0:
                        label = "आज का data"
                    elif days_back == 1:
                        label = "कल का data"
                    elif days_back == 2:
                        label = "2 दिन पुराना data"
                    elif days_back == 3:
                        label = "3 दिन पुराना data"
                    else:
                        label = "4 दिन पुराना data"
                    status[mandi] = {
                        "status":    label,
                        "days_back": days_back,
                        "date":      str(check_date),
                        "found":     True,
                    }
                    found = True
                    break
            if found:
                break

        if not found:
            status[mandi] = {
                "status":    "data उपलब्ध नहीं",
                "days_back": 99,
                "date":      None,
                "found":     False,
            }

    return status


def build_crop_entry(commodity, price_list, wanted_mandis=None):
    avg_today = avg_modal(price_list)
    if avg_today == 0:
        return None

    msp          = get_msp(commodity)
    market_name, best_price = best_market(price_list)
    msp_diff     = avg_today - msp if msp else None
    msp_diff_pct = round((msp_diff / msp) * 100, 1) if msp else None

    wanted_list = [m.strip() for m in wanted_mandis] \
        if wanted_mandis else []
    avg_4day   = get_historical_avg(commodity, wanted_list, days=4)
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


def analyse_for_subscriber(subscriber):
    """
    Main function — analyses prices for a specific subscriber.
    Checks today first, falls back up to 4 days for each mandi.
    Returns per-mandi status so narrator can show exactly
    which mandi has today's data and which is using old data.
    """
    wanted_mandis = [m.strip() for m in
                     subscriber["mandis"].split(",")]
    wanted_crops  = [c.strip().lower() for c in
                     subscriber["crops"].split(",")]

    print(f"[ANALYSE] {subscriber['name']} | "
          f"mandis={wanted_mandis} | crops={wanted_crops[:3]}...")

    # get per-mandi status (today/1 day ago/not found)
    mandi_status = get_mandi_status(subscriber)

    # collect all available prices across up to 4 days
    today      = date.today()
    all_prices = []
    seen_keys  = set()

    for days_back in range(0, 5):
        check_date = today - timedelta(days=days_back)
        day_prices = get_prices_for_date(check_date)

        for p in day_prices:
            # check if this mandi is in subscriber's list
            mandi_match = any(
                m.lower() in p["market"].lower()
                for m in wanted_mandis
            )
            # check if this crop is in subscriber's list
            crop_match = any(
                c in p["commodity"].lower()
                for c in wanted_crops
            )
            if mandi_match and crop_match:
                # deduplicate by market+commodity
                key = (p["market"], p["commodity"])
                if key not in seen_keys:
                    p["days_back"] = days_back
                    all_prices.append(p)
                    seen_keys.add(key)

    if not all_prices:
        print(f"[ANALYSE] No prices found for {subscriber['name']}")
        return None

    # group by commodity and build summary
    grouped = group_by_commodity(all_prices)

    # build mandi report for narrator
    today_mandis    = [m for m, s in mandi_status.items()
                       if s["days_back"] == 0]
    fallback_mandis = {m: s for m, s in mandi_status.items()
                       if 0 < s["days_back"] < 99}
    missing_mandis  = [m for m, s in mandi_status.items()
                       if not s["found"]]

    summary = {
        "date":            str(today),
        "subscriber_name": subscriber["name"],
        "district":        subscriber["district"],
        "total_records":   len(all_prices),
        "mandi_status":    mandi_status,
        "today_mandis":    today_mandis,
        "fallback_mandis": fallback_mandis,
        "missing_mandis":  missing_mandis,
        "crops":           [],
    }

    for commodity, price_list in grouped.items():
        entry = build_crop_entry(
            commodity, price_list, wanted_mandis
        )
        if entry:
            summary["crops"].append(entry)

    signal_order = {"SELL": 0, "NEUTRAL": 1, "WAIT": 2}
    summary["crops"].sort(
        key=lambda x: signal_order.get(x["signal"], 9)
    )

    print(f"[ANALYSE] {subscriber['name']}: "
          f"{len(summary['crops'])} crops | "
          f"today: {today_mandis} | "
          f"fallback: {list(fallback_mandis.keys())} | "
          f"missing: {missing_mandis}")

    return summary


def analyse():
    """Analyse all prices for today — used for testing"""
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
    return summary


if __name__ == "__main__":
    analyse()