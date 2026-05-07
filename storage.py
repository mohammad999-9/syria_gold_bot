import json
import os
from datetime import datetime, timedelta

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "rates_history.json")
MAX_DAYS = 30


def load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def save_rates(data: dict):
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    history[today] = {
        "currencies": {c["name"]: {"buy": c["buy"], "sell": c["sell"]} for c in data.get("currencies", [])},
        "gold": {g["unit"]: {"buy": g["buy"], "sell": g["sell"]} for g in data.get("gold", [])},
        "silver": {s["unit"]: {"buy": s["buy"], "sell": s["sell"]} for s in data.get("silver", [])},
        "last_update": data.get("last_update", ""),
        "fetched_at": data.get("fetched_at", ""),
    }
    # Keep only last MAX_DAYS
    sorted_keys = sorted(history.keys(), reverse=True)
    for old_key in sorted_keys[MAX_DAYS:]:
        del history[old_key]
    save_history(history)


def get_yesterday_rates() -> dict | None:
    history = load_history()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return history.get(yesterday)


def get_rates_for_date(date_str: str) -> dict | None:
    history = load_history()
    return history.get(date_str)


def get_available_dates() -> list[str]:
    history = load_history()
    return sorted(history.keys(), reverse=True)


def parse_number(value: str) -> float | None:
    try:
        return float(value.replace(",", "").replace(" ", ""))
    except Exception:
        return None


def calc_change(current: str, previous: str) -> tuple[float | None, str]:
    cur = parse_number(current)
    prev = parse_number(previous)
    if cur is None or prev is None or prev == 0:
        return None, ""
    diff = cur - prev
    pct = (diff / prev) * 100
    if diff > 0:
        arrow = f"🔺 +{diff:,.0f} ({pct:+.2f}%)"
    elif diff < 0:
        arrow = f"🔻 {diff:,.0f} ({pct:.2f}%)"
    else:
        arrow = "➡️ لا تغيير"
    return diff, arrow
