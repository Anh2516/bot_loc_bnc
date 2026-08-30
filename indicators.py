"""
Cac chi bao ky thuat dung cho bo loc F1-F6.

- RSI: Wilder smoothing (giong TradingView / bot mau).
- Spike 15m: % tang cua nen 15m.
- Upper wick: ty le rau tren so voi bien do nen.
"""
from __future__ import annotations

from typing import Any

import config


def klines_to_ohlc(klines: list[list[Any]]) -> dict[str, list[float]]:
    """
    Doi mang kline tho cua Binance thanh dict cac list.
    Them "open_time" (ms) de bao cao gio xuat hien spike / upper wick.
    """
    out: dict[str, list[float]] = {
        "open": [], "high": [], "low": [], "close": [], "volume": [],
        "open_time": [],
    }
    for k in klines:
        try:
            out["open_time"].append(float(k[0]))
            out["open"].append(float(k[1]))
            out["high"].append(float(k[2]))
            out["low"].append(float(k[3]))
            out["close"].append(float(k[4]))
            out["volume"].append(float(k[5]))
        except (IndexError, ValueError, TypeError):
            continue
    return out


def utc_hhmm(open_time_ms: float | None) -> str | None:
    """Doi open_time (ms) thanh chuoi 'HH:MM' theo UTC (giong anh mau bot goc)."""
    if not open_time_ms:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc).strftime("%H:%M")


def rsi(closes: list[float], period: int | None = None) -> float | None:
    """RSI Wilder tren gia dong cua. Tra ve gia tri RSI cua nen cuoi cung."""
    p = period or config.RSI_PERIOD
    if not closes or len(closes) < p + 1:
        return None

    gains = 0.0
    losses = 0.0
    for i in range(1, p + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / p
    avg_loss = losses / p

    # Wilder smoothing cho phan con lai
    for i in range(p + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (p - 1) + gain) / p
        avg_loss = (avg_loss * (p - 1) + loss) / p

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def spike_pct(ohlc: dict[str, list[float]], bars: int = 1) -> float | None:
    """
    % tang nong cua `bars` nen 15m gan nhat:
    (high cao nhat trong cua so / open dau cua so - 1) x 100.
    Dung high thay vi close de bat dung cu pump du sau do co rau tren.
    """
    opens, highs = ohlc.get("open", []), ohlc.get("high", [])
    if len(opens) < bars or len(highs) < bars:
        return None
    open_ref = opens[-bars]
    high_max = max(highs[-bars:])
    if open_ref <= 0:
        return None
    return (high_max / open_ref - 1.0) * 100.0


def upper_wick_ratio(ohlc: dict[str, list[float]], lookback: int | None = None) -> float | None:
    """
    Ty le rau tren lon nhat trong `lookback` nen gan nhat.
    ratio = (high - max(open, close)) / (high - low)
    """
    n = lookback or config.F5_WICK_LOOKBACK_BARS
    highs, lows = ohlc.get("high", []), ohlc.get("low", [])
    opens, closes = ohlc.get("open", []), ohlc.get("close", [])
    if min(len(highs), len(lows), len(opens), len(closes)) < n:
        return None

    best = 0.0
    for i in range(-n, 0):
        high, low, op, cl = highs[i], lows[i], opens[i], closes[i]
        rng = high - low
        if rng <= 0:
            continue
        wick = high - max(op, cl)
        best = max(best, wick / rng)
    return best


def spike_with_time(
    ohlc: dict[str, list[float]], bars: int = 1
) -> tuple[float | None, str | None]:
    """
    Tim nen 15m co % tang (high/open) lon nhat trong `bars` nen gan nhat.
    Tra ve (% tang, gio UTC 'HH:MM' cua nen do) - giong "Spike with 15m candle at 10:30 UTC".
    """
    opens, highs = ohlc.get("open", []), ohlc.get("high", [])
    times = ohlc.get("open_time", [])
    n = min(bars, len(opens), len(highs))
    if n <= 0:
        return None, None

    best_pct: float | None = None
    best_time: str | None = None
    for i in range(-n, 0):
        if opens[i] <= 0:
            continue
        pct = (highs[i] / opens[i] - 1.0) * 100.0
        if best_pct is None or pct > best_pct:
            best_pct = pct
            best_time = utc_hhmm(times[i]) if len(times) >= abs(i) else None
    return best_pct, best_time


def upper_wick_with_time(
    ohlc: dict[str, list[float]], lookback: int | None = None
) -> tuple[float | None, str | None]:
    """
    Rau tren lon nhat trong `lookback` nen gan nhat kem gio UTC cua nen do.
    Giong "F5: PASS - Upper wick seen at 10:45 UTC".
    """
    n = lookback or config.F5_WICK_LOOKBACK_BARS
    highs, lows = ohlc.get("high", []), ohlc.get("low", [])
    opens, closes = ohlc.get("open", []), ohlc.get("close", [])
    times = ohlc.get("open_time", [])
    if min(len(highs), len(lows), len(opens), len(closes)) < n:
        return None, None

    best = 0.0
    best_time: str | None = None
    for i in range(-n, 0):
        rng = highs[i] - lows[i]
        if rng <= 0:
            continue
        ratio = (highs[i] - max(opens[i], closes[i])) / rng
        if ratio > best:
            best = ratio
            best_time = utc_hhmm(times[i]) if len(times) >= abs(i) else None
    return best, best_time


def price_change_pct(ohlc: dict[str, list[float]], bars: int) -> float | None:
    """
    % thay doi gia qua `bars` nen gan nhat (close cuoi / open cua nen dau).
    Dung cho truong "1h: -0.28%" trong anh mau (4 nen 15m).
    """
    opens, closes = ohlc.get("open", []), ohlc.get("close", [])
    if len(opens) < bars or not closes:
        return None
    open_ref = opens[-bars]
    if open_ref <= 0:
        return None
    return (closes[-1] / open_ref - 1.0) * 100.0


def volume_ratio(ohlc: dict[str, list[float]], lookback: int = 20) -> float | None:
    """
    Volume nen 15m hien tai / volume trung binh `lookback` nen truoc do.
    Dung cho truong "Vol: 0.6x" trong anh mau.
    """
    vols = ohlc.get("volume", [])
    if len(vols) < lookback + 1:
        return None
    ref = vols[-(lookback + 1):-1]
    avg = sum(ref) / len(ref)
    if avg <= 0:
        return None
    return vols[-1] / avg


def format_compact(value: float | None) -> str:
    """Format so lon thanh dang gon: 2.6M, 512K, 1.4B (giong 'OI 2.6M' trong anh)."""
    if value is None:
        return "n/a"
    abs_v = abs(value)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs_v >= div:
            return f"{value / div:.1f}{suffix}"
    return f"{value:.0f}"


def format_price(price: float | None) -> str:
    """Format gia coin bo bot so 0 vo nghia (vd 0.01464, 77639.0)."""
    if price is None:
        return "n/a"
    if price >= 1000:
        return f"{price:,.1f}"
    if price >= 1:
        return f"{price:.4f}".rstrip("0").rstrip(".")
    return f"{price:.8f}".rstrip("0").rstrip(".")


def compute_entry_sl_tp(entry: float) -> dict[str, float]:
    """Entry / SL / TP1-TP3 theo cong thuc muc 4-6 cua PDF."""
    tp1, tp2, tp3 = config.TP_MULTIPLIERS
    return {
        "entry": entry,
        "sl": entry * config.SL_MULTIPLIER,
        "tp1": entry * tp1,
        "tp2": entry * tp2,
        "tp3": entry * tp3,
    }


def round_to_tick(price: float, tick_size: float | None, precision: int = 6) -> float:
    """Lam tron gia theo tick size cua tung coin (PDF muc 5 co nhac)."""
    if not tick_size or tick_size <= 0:
        return round(price, precision)
    steps = round(price / tick_size)
    decimals = max(0, len(f"{tick_size:.10f}".rstrip("0").split(".")[-1]))
    return round(steps * tick_size, decimals)
