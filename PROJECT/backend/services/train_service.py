"""Live train data via eRail.in (PROMPT_5 §5).

eRail.in endpoint returns live running trains across Karnataka station codes.
Rules:
- Trains appear ONLY when eRail returns real data.
- 7 known city-pair fallbacks exist but are FLAGGED `source: "fallback"` and
  used only when eRail is unreachable — never presented as live.
- No fabricated trains: if a corridor has no eRail match, no train leg.
"""
import json
import logging
import time

import requests

from .. import config

logger = logging.getLogger(__name__)

_ERAIL = "https://erail.in/rail/getTrains.aspx"
_TIMEOUT = 6.0
_TTL_S = 15 * 60
_RND = 4

# Real station codes for the 48 mapped Karnataka stations (used to query eRail)
STATION_CODES = {
    "KSR Bengaluru City Junction": "SBC",
    "Yesvantpur Junction": "YPR",
    "Bengaluru Cantonment": "BNC",
    "Krishnarajapuram": "KJM",
    "Yelahanka Junction": "YNK",
    "Whitefield": "WFD",
    "Kengeri": "KGI",
    "Mysuru City Junction": "MYS",
    "Hubballi Junction": "UBL",
    "Mangaluru Junction": "MAJN",
    "Mangaluru Central": "MAQ",
    "Belagavi": "BGM",
    "Ballari Junction": "BAY",
    "Davangere": "DVG",
    "Dharwad": "DWR",
    "Kalaburagi Junction": "KLBG",
    "Raichur Junction": "RC",
    "Vijayapura": "BJP",
    "Bangarapet Junction": "BWT",
    "Tumakuru": "TK",
    "Arsikere Junction": "ASK",
    "Hassan Junction": "HAS",
    "Mandya": "MYA",
    "Hosapete Junction": "HPT",
    "Gadag Junction": "GDG",
    "Shivamogga Town": "SMET",
    "Harihar": "HRR",
    "Wadi Junction": "WADI",
    "Birur Junction": "RRB",
    "Londa Junction": "LD",
    "Yadgir": "YG",
    "Bidar": "BIDR",
    "Udupi": "UD",
    "Karwar": "KAWR",
    "Haveri": "HVR",
    "Ranibennur": "RNR",
    "Tiptur": "TTR",
    "Kadur Junction": "DRU",
    "Kundapura": "KUDA",
    "Koppal": "KBL",
    "Bagalkot": "BGK",
    "Shrirangapattana": "S",
    "Ramanagaram": "RMGM",
    "Channapatna": "CPT",
    "Nanjangud Town": "NTW",
    "Chamarajanagar": "CMNR",
    "Bhadravati": "BDVT",
    "Bhatkal": "BTJL",
}

# Fallback city-pair schedules (7). ONLY used when eRail is unreachable and
# always flagged source: "fallback" — never presented as live.
_FALLBACK_PAIRS: dict[tuple[str, str], list[dict]] = {
    ("SBC", "MYS"): [
        {"train": "12007", "name": "Shatabdi", "dep": "06:00", "arr": "07:30", "dur_min": 90},
        {"train": "12613", "name": "Intercity Express", "dep": "17:00", "arr": "18:30", "dur_min": 90},
    ],
    ("SBC", "TUMKUR"): [
        {"train": "12613", "name": "Intercity Express", "dep": "17:00", "arr": "18:10", "dur_min": 70},
    ],
    ("SBC", "BWT"): [
        {"train": "12607", "name": "Lalbagh Express", "dep": "07:00", "arr": "08:30", "dur_min": 90},
    ],
    ("SBC", "HAS"): [
        {"train": "12027", "name": "Shatabdi", "dep": "06:00", "arr": "08:40", "dur_min": 160},
    ],
    ("SBC", "YPR"): [
        {"train": "16527", "name": "Malnad Express", "dep": "06:30", "arr": "06:50", "dur_min": 20},
    ],
    ("MYS", "BWT"): [
        {"train": "12610", "name": "Cauvery Express", "dep": "07:00", "arr": "09:40", "dur_min": 160},
    ],
    ("YPR", "UBL"): [
        {"train": "16545", "name": "Karnataka Express", "dep": "23:00", "arr": "05:00", "dur_min": 360},
    ],
}


class TrainService:
    def __init__(self, timeout_s: float = _TIMEOUT):
        self._timeout = timeout_s
        self._cache: dict[str, tuple[float, dict | None]] = {}

    def code_for(self, station_name: str) -> str | None:
        """Resolve a station name OR code to its eRail code.

        Accepts full names ("KSR Bengaluru City Junction"), partial names
        ("Mysuru") and already-resolved codes ("SBC", "YPR") so both the tests
        and the live-trains API route (which passes codes) work.
        """
        name = station_name.strip().lower()
        if not name:
            return None
        upper = station_name.strip().upper()
        if upper in {c for c in STATION_CODES.values()}:  # already a code
            return upper
        if name in {k.lower() for k in STATION_CODES}:
            return STATION_CODES[next(k for k in STATION_CODES if k.lower() == name)]
        for k, code in STATION_CODES.items():
            if name in k.lower() or k.lower() in name:
                return code
        return None

    def trains_between(self, from_code: str, to_code: str) -> dict:
        """Live trains from eRail. {trains: [...], source: "live"|"fallback"}.

        Empty trains [] when the corridor has no data — never fabricated.
        """
        key = f"{from_code}:{to_code}"
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < _TTL_S:
            return hit[1]
        out = {"trains": [], "source": "fallback", "note": "eRail unreachable"}
        try:
            resp = requests.get(_ERAIL, params={
                "Station1": from_code, "Station2": to_code,
                "SameStation": 0, "TrainName": "", "StateCode": "",
                "getTrains.aspx": "",
            }, timeout=self._timeout, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()
            trains = []
            for row in data:
                if isinstance(row, dict):
                    trains.append({
                        "train": row.get("TrainNo"),
                        "name": row.get("TrainName"),
                        "dep": row.get("DepartureTime"),
                        "arr": row.get("ArrivalTime"),
                        "dur_min": row.get("Duration"),
                        "source": "live",
                    })
                elif isinstance(row, (list, tuple)) and len(row) >= 3:
                    trains.append({
                        "train": row[0], "name": row[1],
                        "dep": row[2], "arr": None, "dur_min": None,
                        "source": "live",
                    })
            if trains:
                out = {"trains": trains, "source": "live", "note": "eRail.in"}
            else:
                # eRail reachable but no trains -> genuinely empty, no fallback
                out = {"trains": [], "source": "live", "note": "eRail.in (no services)"}
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[train] eRail %s->%s failed: %s", from_code, to_code, exc)
            fb = _FALLBACK_PAIRS.get((from_code, to_code))
            if fb:
                out = {"trains": fb, "source": "fallback",
                       "note": "eRail unreachable — city-pair schedule (NOT live)"}
        self._cache[key] = (time.time(), out)
        return out
