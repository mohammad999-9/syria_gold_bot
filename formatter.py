from storage import calc_change

CURRENCY_EMOJIS = {
    "الدولار الأمريكي": "🇺🇸",
    "اليورو": "🇪🇺",
    "الجنيه الاسترليني": "🇬🇧",
    "الليرة التركية": "🇹🇷",
    "الجنيه المصري": "🇪🇬",
    "الريال السعودي": "🇸🇦",
    "الدرهم الإماراتي": "🇦🇪",
    "الريال القطري": "🇶🇦",
    "الدينار الكويتي": "🇰🇼",
    "الدينار البحريني": "🇧🇭",
    "الدينار الاردني": "🇯🇴",
    "الدينار الأردني": "🇯🇴",
    "الليرة اللبنانية": "🇱🇧",
    "الدينار الليبي": "🇱🇾",
}

MAIN_CURRENCIES = [
    "الدولار الأمريكي",
    "اليورو",
    "الدرهم الإماراتي",
    "الريال السعودي",
    "الليرة التركية",
    "الجنيه المصري",
    "الدينار الاردني",
]

MAIN_GOLD = [
    "غرام 24K",
    "غرام 21K",
    "غرام 18K",
    # Legacy names from old liratoday.net scraper
    "جرام 24K",
    "جرام 21K",
    "جرام 18K",
]


def format_message(data: dict, yesterday: dict | None = None) -> str:
    lines = []

    lines.append("🔔 *أسعار الصرف والذهب في سوريا*")
    lines.append("📍 _السوق الموازية (السوق السوداء) — دمشق_")
    lines.append(f"🕐 {data.get('fetched_at', data.get('last_update', ''))}")
    if yesterday:
        lines.append("📈 _التغيير مقارنة بالأمس مُدرج أسفل كل سعر_")
    lines.append("━" * 30)

    # ------------------------------------------------------------------
    # Currencies
    # ------------------------------------------------------------------
    lines.append("\n💱 *أسعار العملات مقابل الليرة السورية*")

    currency_map = {c["name"]: c for c in data.get("currencies", [])}
    prev_currencies = yesterday.get("currencies", {}) if yesterday else {}

    shown = 0
    for name in MAIN_CURRENCIES:
        if name in currency_map:
            c = currency_map[name]
            emoji = CURRENCY_EMOJIS.get(name, "💵")
            lines.append(f"\n{emoji} *{name}*")
            lines.append(f"  شراء: `{c['buy']}` | بيع: `{c['sell']}`")
            if name in prev_currencies:
                _, change = calc_change(c["buy"], prev_currencies[name]["buy"])
                if change:
                    lines.append(f"  {change}")
            shown += 1

    # Also show any extra currencies not in MAIN_CURRENCIES list
    for c in data.get("currencies", []):
        if c["name"] not in MAIN_CURRENCIES:
            emoji = CURRENCY_EMOJIS.get(c["name"], "💵")
            lines.append(f"\n{emoji} *{c['name']}*")
            lines.append(f"  شراء: `{c['buy']}` | بيع: `{c['sell']}`")

    lines.append("\n" + "━" * 30)

    # ------------------------------------------------------------------
    # Gold
    # ------------------------------------------------------------------
    lines.append("\n🥇 *أسعار الذهب في سوريا* (ليرة/غرام)")

    gold_map = {g["unit"]: g for g in data.get("gold", [])}
    prev_gold = yesterday.get("gold", {}) if yesterday else {}

    for unit in MAIN_GOLD:
        if unit in gold_map:
            g = gold_map[unit]
            # Normalise display name to always show "غرام"
            display = unit.replace("جرام", "غرام")
            lines.append(f"\n🔸 *{display}*")
            lines.append(f"  شراء: `{g['buy']}` | بيع: `{g['sell']}`")
            prev_unit = prev_gold.get(unit) or prev_gold.get(unit.replace("غرام", "جرام"))
            if prev_unit:
                _, change = calc_change(g["buy"], prev_unit["buy"])
                if change:
                    lines.append(f"  {change}")

    lines.append("\n" + "━" * 30)

    # ------------------------------------------------------------------
    # Silver / Platinum
    # ------------------------------------------------------------------
    silver = data.get("silver", [])
    prev_silver = yesterday.get("silver", {}) if yesterday else {}
    if silver:
        lines.append("\n🥈 *معادن أخرى* (ليرة/غرام)")
        for s in silver:
            icon = "⚪" if "فضة" in s["unit"] else "🔘"
            lines.append(f"\n{icon} *{s['unit']}*")
            lines.append(f"  شراء: `{s['buy']}` | بيع: `{s['sell']}`")
            if s["unit"] in prev_silver:
                _, change = calc_change(s["buy"], prev_silver[s["unit"]]["buy"])
                if change:
                    lines.append(f"  {change}")
        lines.append("\n" + "━" * 30)

    return "\n".join(lines)


def format_history_summary(history_data: dict, dates: list[str]) -> str:
    if len(dates) < 2:
        return "⚠️ لا يوجد سجل كافٍ للمقارنة بعد. يحتاج البوت يوماً واحداً على الأقل من البيانات."

    lines = []
    lines.append("📅 *سجل أسعار الدولار والذهب عيار 21*")
    lines.append("━" * 30)
    lines.append(f"{'التاريخ':<14} {'الدولار':>12} {'ذهب 21K':>14}")
    lines.append("─" * 42)

    for date in dates[:10]:
        day_data = history_data.get(date, {})
        currencies = day_data.get("currencies", {})
        gold = day_data.get("gold", {})

        usd = currencies.get("الدولار الأمريكي", {}).get("buy", "—")
        # Support both old (جرام) and new (غرام) naming
        gold21 = (
            gold.get("غرام 21K", {}).get("buy")
            or gold.get("جرام 21K", {}).get("buy")
            or "—"
        )

        lines.append(f"{date:<14} {usd:>12} {gold21:>14}")

    return "\n".join(lines)
