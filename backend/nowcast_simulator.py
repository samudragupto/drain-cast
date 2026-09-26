"""Rainfall input for the simulation: design storms and a live model forecast.

All series are rainfall intensity in mm/h on a fixed 5-minute step. The
simulation starts WARMUP_MIN before "now" so the network is already carrying
water when the forecast window opens, instead of every road starting dry.
"""

import json
import logging
import math
import time
import urllib.request
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

STEP_MIN = 5
WARMUP_MIN = 30
HORIZON_MIN = 180
IST = timezone(timedelta(hours=5, minutes=30))

PATTERNS = {
    "steady": "Constant intensity for the whole window",
    "building": "Storm builds for two hours, then holds at peak",
    "burst": "Cloudburst: sharp peak about 45 min from now, then a long tail",
    "passing": "Heaviest now, easing off as the cell moves away",
}

_live_cache = {}
LIVE_TTL_S = 600


def n_steps() -> int:
    return (WARMUP_MIN + HORIZON_MIN) // STEP_MIN


def step_times() -> list:
    """Start minute of each step relative to now (negative = already fallen)."""
    return [-WARMUP_MIN + k * STEP_MIN for k in range(n_steps())]


def design_hyetograph(pattern: str, peak: float) -> list:
    """Rainfall intensity (mm/h) for each 5-minute step of the simulation window."""
    if pattern not in PATTERNS:
        raise ValueError(f"unknown pattern '{pattern}'")
    series = []
    for t in step_times():
        mid = t + STEP_MIN / 2
        if pattern == "steady":
            value = peak
        elif pattern == "building":
            value = peak * (0.25 + 0.75 * min(1.0, max(0.0, (mid + WARMUP_MIN) / (120 + WARMUP_MIN))))
        elif pattern == "burst":
            # asymmetric triangle: rises quickly, recedes slowly (Chicago-style shape)
            peak_at, rise, fall = 45.0, 50.0, 90.0
            if mid <= peak_at:
                shape = max(0.0, 1 - (peak_at - mid) / rise)
            else:
                shape = max(0.0, 1 - (mid - peak_at) / fall)
            value = peak * max(0.08, shape)
        else:  # passing
            value = peak * math.exp(-max(0.0, mid) / 70.0)
        series.append(round(value, 2))
    return series


def now_ist() -> datetime:
    now = datetime.now(IST)
    return now.replace(minute=now.minute - now.minute % STEP_MIN, second=0, microsecond=0)


def fetch_live_rainfall(lat: float, lon: float) -> dict:
    """Open-Meteo 15-minute precipitation (model forecast, not radar) mapped onto our steps."""
    key = (round(lat, 3), round(lon, 3))
    cached = _live_cache.get(key)
    if cached and time.time() - cached[0] < LIVE_TTL_S:
        return cached[1]

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&minutely_15=precipitation&past_minutely_15=2&forecast_minutely_15=12"
        "&current=precipitation,rain&timezone=Asia%2FKolkata"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "DrainCast/1.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    block = payload["minutely_15"]
    stamps = [datetime.fromisoformat(t).replace(tzinfo=IST) for t in block["time"]]
    # Open-Meteo reports the precipitation sum of the preceding 15 minutes
    buckets = [(ts - timedelta(minutes=15), ts, (mm or 0.0) * 4.0) for ts, mm in zip(stamps, block["precipitation"])]

    start = now_ist()
    series = []
    for t in step_times():
        mid = start + timedelta(minutes=t + STEP_MIN / 2)
        value = next((rate for lo, hi, rate in buckets if lo <= mid < hi), 0.0)
        series.append(round(value, 2))

    result = {
        "series": series,
        "source": "Open-Meteo forecast (15-min, model-based)",
        "issued": datetime.now(IST).isoformat(timespec="minutes"),
        "current_mm": payload.get("current", {}).get("precipitation"),
    }
    _live_cache[key] = (time.time(), result)
    return result
