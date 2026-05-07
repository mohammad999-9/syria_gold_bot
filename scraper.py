import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

ARABIC_MONTHS = {
    1: "كانون-الثاني",
    2: "شباط",
    3: "آذار",
    4: "نيسان",
    5: "أيار",
    6: "حزيران",
    7: "تموز",
    8: "آب",
    9: "أيلول",
    10: "تشرين-الأول",
    11: "تشرين-الثاني",
    12: "كانون-الأول",
}


def build_shaam_url(date: datetime) -> str:
    day = date.day
    month = ARABIC_MONTHS[date.month]
    year = date.year
    slug = f"تقرير-شام-الاقتصادي-أو-{day}-{month}-{year}"
    return f"https://shaam.org/business/{slug}"


def clean_num(s: str) -> str:
    return re.sub(r"[,،\s]", "", str(s))


def _find_nums(snippet: str) -> list[str]:
    """Extract all clean numeric strings (3+ digits) from a snippet."""
    raw = re.findall(r"\d[\d,،]*\d|\d{3,}", snippet)
    result = []
    for n in raw:
        c = clean_num(n)
        if c.isdigit() and len(c) >= 3:
            result.append(c)
    return result


def extract_pair_after(text: str, keyword: str, search_window: int = 400):
    """
    After finding `keyword` in text, look for buy/sell pair.
    Returns (buy, sell) strings or (None, None).
    Handles both:
      - "keyword: NUMBER" (keyword then number)
      - "NUMBER keyword" (number then keyword)
    """
    idx = text.find(keyword)
    if idx == -1:
        return None, None
    snippet = text[idx: idx + search_window]

    # Pattern A: "NUMBER then شراء/للشراء" and "NUMBER then مبيع/للمبيع"
    rev_buy = re.search(r"([\d,،]+)\s+(?:للشراء|شراء)", snippet)
    rev_sell = re.search(r"([\d,،]+)\s+(?:للمبيع|المبيع|مبيع)", snippet)
    if rev_buy and rev_sell:
        return clean_num(rev_buy.group(1)), clean_num(rev_sell.group(1))

    # Pattern B: "شراء: NUMBER" and "مبيع: NUMBER"
    fwd_buy = re.search(r"(?:شراء|للشراء)\s*[: ]\s*([\d,،]+)", snippet)
    fwd_sell = re.search(r"(?:مبيع|للمبيع|البيع|بيع)\s*[: ]\s*([\d,،]+)", snippet)
    if fwd_buy and fwd_sell:
        return clean_num(fwd_buy.group(1)), clean_num(fwd_sell.group(1))

    # Pattern C: gold/silver "X ليرة للمبيع وY ليرة للشراء" (sell first, buy second)
    gold_pat = re.search(
        r"([\d,،]+)\s*ليرة.*?(?:للمبيع|المبيع).*?([\d,،]+)\s*ليرة.*?(?:للشراء|الشراء)",
        snippet,
        re.DOTALL,
    )
    if gold_pat:
        return clean_num(gold_pat.group(2)), clean_num(gold_pat.group(1))  # buy, sell

    # Fallback: first two numeric sequences of 3+ digits
    nums = _find_nums(snippet)
    if len(nums) >= 2:
        return nums[0], nums[1]

    return None, None


def parse_shaam_article(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    article = soup.find("article") or soup.find("main") or soup
    text = article.get_text()

    # ------------------------------------------------------------------
    # Currencies
    # ------------------------------------------------------------------
    currencies = []

    # USD – the article typically says one of:
    #   "بين سعر 13330 ليرة سورية للشراء وسعر 13400 للمبيع"
    #   "سعر للشراء 13,320، وسعر 13,380 للمبيع"
    #   "شراء 13330 للشراء، و 13400 للمبيع"
    usd_buy, usd_sell = None, None
    # Pattern 1: "بين سعر X...للشراء وسعر Y للمبيع"
    m = re.search(r"بين سعر ([\d,،]+).*?وسعر ([\d,،]+)", text[:1200])
    if m:
        usd_buy, usd_sell = clean_num(m.group(1)), clean_num(m.group(2))
    # Pattern 2: "للشراء X ، وسعر Y للمبيع" or "للشراء X، وسعر Y"
    if not usd_buy:
        m = re.search(r"سعر للشراء\s+([\d,،]+).*?(?:وسعر|سعر)\s+([\d,،]+)\s+للمبيع", text[:1200])
        if m:
            usd_buy, usd_sell = clean_num(m.group(1)), clean_num(m.group(2))
    # Pattern 3: look near "الدولار" for any X/Y pair in 1[23],XXX range
    if not usd_buy:
        idx = text.find("الدولار")
        if idx != -1:
            snip = text[idx: idx + 300]
            candidates = [c for c in _find_nums(snip) if 10000 <= int(c) <= 20000]
            if len(candidates) >= 2:
                usd_buy, usd_sell = candidates[0], candidates[1]
    if usd_buy:
        currencies.append({"name": "الدولار الأمريكي", "buy": usd_buy, "sell": usd_sell or usd_buy})

    # EUR – look for يورو
    eur_buy, eur_sell = extract_pair_after(text, "اليورو")
    if not eur_buy:
        m = re.search(r"اليورو.*?([\d,،]+).*?([\d,،]+)", text[:1000])
        if m:
            eur_buy, eur_sell = clean_num(m.group(1)), clean_num(m.group(2))
    if eur_buy:
        currencies.append({"name": "اليورو", "buy": eur_buy, "sell": eur_sell or eur_buy})

    # AED
    aed_buy, aed_sell = extract_pair_after(text, "الدرهم الإماراتي")
    if aed_buy:
        currencies.append({"name": "الدرهم الإماراتي", "buy": aed_buy, "sell": aed_sell or aed_buy})

    # SAR
    sar_buy, sar_sell = extract_pair_after(text, "الريال السعودي")
    if sar_buy:
        currencies.append({"name": "الريال السعودي", "buy": sar_buy, "sell": sar_sell or sar_buy})

    # TRY
    try_buy, try_sell = extract_pair_after(text, "الليرة التركية")
    if try_buy:
        currencies.append({"name": "الليرة التركية", "buy": try_buy, "sell": try_sell or try_buy})

    # JOD
    jod_buy, jod_sell = extract_pair_after(text, "الدينار الاردني")
    if not jod_buy:
        jod_buy, jod_sell = extract_pair_after(text, "الدينار الأردني")
    if jod_buy:
        currencies.append({"name": "الدينار الاردني", "buy": jod_buy, "sell": jod_sell or jod_buy})

    # EGP
    egp_buy, egp_sell = extract_pair_after(text, "الجنيه المصري")
    if egp_buy:
        currencies.append({"name": "الجنيه المصري", "buy": egp_buy, "sell": egp_sell or egp_buy})

    # ------------------------------------------------------------------
    # Gold
    # ------------------------------------------------------------------
    gold = []

    for karat, keyword in [
        ("24", "عيار 24"),
        ("21", "عيار 21"),
        ("18", "عيار 18"),
    ]:
        buy, sell = extract_pair_after(text, keyword, search_window=300)
        if buy:
            gold.append({"unit": f"غرام {karat}K", "buy": buy, "sell": sell or buy})

    # ------------------------------------------------------------------
    # Silver & Platinum (treat platinum as extra metal)
    # ------------------------------------------------------------------
    silver = []

    silver_buy, silver_sell = extract_pair_after(text, "الفضة", search_window=300)
    if silver_buy:
        silver.append({"unit": "غرام فضة", "buy": silver_buy, "sell": silver_sell or silver_buy})

    platinum_buy, platinum_sell = extract_pair_after(text, "البلاتين", search_window=300)
    if platinum_buy:
        silver.append({"unit": "غرام بلاتين", "buy": platinum_buy, "sell": platinum_sell or platinum_buy})

    if not currencies and not gold:
        return None

    return {
        "currencies": currencies,
        "gold": gold,
        "silver": silver,
        "source": "shaam.org",
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_update": datetime.now().strftime("%Y-%m-%d"),
    }


def fetch_shaam(date: datetime) -> dict | None:
    url = build_shaam_url(date)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.text) > 5000:
            data = parse_shaam_article(resp.text)
            if data and data.get("currencies"):
                return data
    except Exception as e:
        print(f"Error fetching shaam ({url}): {e}")
    return None


def scrape_all() -> dict | None:
    now = datetime.now()

    # Try today first
    data = fetch_shaam(now)
    if data:
        print(f"✅ Scraped from shaam.org for {now.strftime('%Y-%m-%d')}")
        return data

    # Try yesterday (article may not be published yet early morning, or weekend)
    yesterday = now - timedelta(days=1)
    data = fetch_shaam(yesterday)
    if data:
        print(f"✅ Scraped from shaam.org for {yesterday.strftime('%Y-%m-%d')} (yesterday)")
        return data

    # Try two days ago
    day_before = now - timedelta(days=2)
    data = fetch_shaam(day_before)
    if data:
        print(f"✅ Scraped from shaam.org for {day_before.strftime('%Y-%m-%d')} (2 days ago)")
        return data

    print("❌ Could not fetch data from shaam.org")
    return None


if __name__ == "__main__":
    data = scrape_all()
    if data:
        print(f"\nالمصدر: {data.get('source')} | {data.get('fetched_at')}")
        print("\n=== العملات (السوق الموازية) ===")
        for c in data["currencies"]:
            print(f"{c['name']}: شراء {c['buy']} - بيع {c['sell']}")
        print("\n=== الذهب ===")
        for g in data["gold"]:
            print(f"{g['unit']}: شراء {g['buy']} - بيع {g['sell']}")
        print("\n=== معادن أخرى ===")
        for s in data["silver"]:
            print(f"{s['unit']}: شراء {s['buy']} - بيع {s['sell']}")
    else:
        print("فشل جلب البيانات")
