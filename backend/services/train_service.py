import logging
import httpx
import re

logger = logging.getLogger(__name__)

_STATION_CODES = {
    "sbc": "sbc", "ksr bengaluru": "sbc", "bengaluru city": "sbc", "bangalore city": "sbc",
    "ksr bangalore": "sbc", "bengaluru": "sbc",
    "bnc": "bnc", "bengaluru cant": "bnc", "bengaluru cantonment": "bnc", "bangalore cant": "bnc",
    "ypr": "ypr", "yesvantpur": "ypr", "yasvantpur": "ypr", "yashwantpura": "ypr",
    "ypr junction": "ypr", "yesvantpur junction": "ypr",
    "kjm": "kjm", "krishnarajapuram": "kjm",
    "mys": "mys", "mysuru": "mys", "mysore": "mys", "mysuru junction": "mys", "mysore junction": "mys",
    "ubl": "ubl", "hubballi": "ubl", "hubli": "ubl", "hubballi junction": "ubl", "hubli junction": "ubl",
    "majn": "majn", "mangaluru junction": "majn", "mangalore junction": "majn",
    "maq": "maq", "mangaluru": "maq", "mangalore": "maq", "mangaluru central": "maq",
    "bgm": "bgm", "belagavi": "bgm", "belgaum": "bgm",
    "bay": "bay", "ballari": "bay", "bellary": "bay", "ballari junction": "bay",
    "smet": "smet", "shivamogga": "smet", "shimoga": "smet", "shivamogga town": "smet",
    "dvg": "dvg", "davanagere": "dvg", "davangere": "dvg",
    "has": "has", "hassan": "has",
    "gr": "gr", "kalaburagi": "gr", "gulbarga": "gr", "kalaburagi junction": "gr",
    "bjp": "bjp", "vijayapura": "bjp", "bijapur": "bjp",
    "hpt": "hpt", "hosapete": "hpt", "hospet": "hpt", "hosapete junction": "hpt",
    "ud": "ud", "udupi": "ud", "uduppi": "ud",
    "cta": "cta", "chitradurga": "cta",
    "tk": "tk", "tumakuru": "tk", "tumkur": "tk",
}

_NAME_TO_CITY = {
    "ksr bengaluru": "bengaluru", "bengaluru city": "bengaluru",
    "bengaluru": "bengaluru", "bengaluru cantonment": "bengaluru",
    "bengaluru cant": "bengaluru", "yesvantpur": "bengaluru",
    "yasvantpur": "bengaluru", "yashwantpura": "bengaluru",
    "krishnarajapuram": "bengaluru",
    "mysuru": "mysuru", "mysore": "mysuru",
    "hubballi": "hubballi", "hubli": "hubballi",
    "mangaluru": "mangaluru", "mangalore": "mangaluru",
    "belagavi": "belagavi", "belgaum": "belagavi",
    "ballari": "ballari", "bellary": "ballari",
    "shivamogga": "shivamogga", "shimoga": "shivamogga",
    "davanagere": "davanagere", "davangere": "davanagere",
    "hassan": "hassan",
    "kalaburagi": "kalaburagi", "gulbarga": "kalaburagi",
    "vijayapura": "vijayapura", "bijapur": "vijayapura",
    "hosapete": "hosapete", "hospet": "hosapete",
    "udupi": "udupi",
    "chitradurga": "chitradurga",
    "tumakuru": "tumakuru", "tumkur": "tumakuru",
}

_FALLBACK_TRAINS = {
    ("bengaluru", "mysuru"): [
        ("12613", "Shatabdi Express", "11:00", "13:00"),
        ("12007", "Shatabdi Express", "14:00", "16:00"),
        ("16535", "Gol Gumbaz Express", "07:45", "10:25"),
        ("16232", "Mysuru Express", "12:30", "15:10"),
    ],
    ("bengaluru", "hubballi"): [
        ("17325", "Vishwamanava Express", "15:00", "22:30"),
        ("16589", "Rani Chennamma Express", "22:00", "06:30"),
    ],
    ("bengaluru", "mangaluru"): [
        ("16511", "KSR Bengaluru - Kannur Express", "23:30", "09:45"),
        ("16585", "Mokashi Express", "22:15", "08:30"),
    ],
    ("bengaluru", "belagavi"): [
        ("17309", "Basava Express", "22:00", "08:30"),
    ],
    ("bengaluru", "ballari"): [
        ("16545", "KSR Bengaluru - Ballari Express", "22:30", "06:30"),
    ],
    ("bengaluru", "shivamogga"): [
        ("16581", "Shivamogga Express", "22:30", "05:30"),
        ("16579", "Shivamogga Intercity", "14:00", "19:00"),
    ],
    ("bengaluru", "davanagere"): [
        ("17325", "Vishwamanava Express", "15:00", "20:30"),
    ],
    ("bengaluru", "hassan"): [
        ("16511", "Kannur Express", "23:30", "03:15"),
    ],
    ("bengaluru", "kalaburagi"): [
        ("16541", "Gol Gumbaz Express", "22:00", "06:00"),
    ],
    ("bengaluru", "vijayapura"): [
        ("16535", "Gol Gumbaz Express", "07:45", "17:30"),
    ],
    ("bengaluru", "udupi"): [
        ("16511", "Kannur Express", "23:30", "06:30"),
    ],
    ("bengaluru", "chitradurga"): [
        ("17325", "Vishwamanava Express", "15:00", "18:15"),
    ],
}


def _resolve_station_code(name: str) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r'\s*(junction|railway\s*station|railway|station|terminal|halt|halt\s*station|road|road\s*station)\s*', '', name.lower().strip())
    words = cleaned.split()
    if cleaned in _STATION_CODES:
        return _STATION_CODES[cleaned]
    for i in range(len(words), 0, -1):
        key = " ".join(words[:i])
        if key in _STATION_CODES:
            return _STATION_CODES[key]
    if words and words[0] in _STATION_CODES:
        return _STATION_CODES[words[0]]
    return None


def _city_key(name: str) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r'\s*(junction|railway\s*station|railway|station)\s*', '', name.lower().strip())
    if cleaned in _NAME_TO_CITY:
        return _NAME_TO_CITY[cleaned]
    words = cleaned.split()
    for i in range(len(words), 0, -1):
        key = " ".join(words[:i])
        if key in _NAME_TO_CITY:
            return _NAME_TO_CITY[key]
    if words and words[0] in _NAME_TO_CITY:
        return _NAME_TO_CITY[words[0]]
    return cleaned


def _parse_erail_response(text: str) -> list:
    trains = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) < 12:
            continue
        tn = parts[0].strip()
        dep = parts[4].strip()
        arr = parts[5].strip()
        from_name = parts[2].strip()
        to_name = parts[3].strip()
        name = parts[1].strip()
        if len(tn) < 3 or len(tn) > 6:
            continue
        trains.append((tn, f"{from_name} → {to_name}", dep, arr))
    return trains


def _scrape_erail(src_code: str, dst_code: str) -> list | None:
    url = f"https://erail.in/rail/getTrains.aspx?from_station={src_code}&to_station={dst_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/plain, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://erail.in/",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200 and resp.text.strip():
                trains = _parse_erail_response(resp.text)
                if trains:
                    return trains
    except Exception as e:
        logger.warning(f"eRail scrape failed for {src_code}→{dst_code}: {e}")
    return None


def _fallback_trains(src_city: str, dst_city: str) -> list:
    key = (src_city, dst_city)
    key_rev = (dst_city, src_city)
    return _FALLBACK_TRAINS.get(key, _FALLBACK_TRAINS.get(key_rev, []))


def get_train_options(src_name: str, dst_name: str) -> list:
    src_code = _resolve_station_code(src_name)
    dst_code = _resolve_station_code(dst_name)
    src_city = _city_key(src_name)
    dst_city = _city_key(dst_name)

    if src_code and dst_code:
        live = _scrape_erail(src_code, dst_code)
        if live:
            return live[:10]

    if src_city and dst_city:
        return _fallback_trains(src_city, dst_city)

    return []
