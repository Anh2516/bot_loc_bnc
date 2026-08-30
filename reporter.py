"""
Xuat ket qua quet: bang tren console, luu CSV va gui Telegram (tuy chon).
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

import config
from scoring import CoinScore

log = logging.getLogger("reporter")

CSV_HEADER = [
    "scan_time", "symbol", "score", "passed_count", "grade", "action", "trap_risk",
    "price", "chg_24h", "chg_1h", "vol_24h", "vol_ratio",
    "rsi_15m", "rsi_4h", "rsi_1d", "long_ratio", "spike_15m",
    "oi_change_1h", "upper_wick", "funding",
    "F1", "F2", "F3", "F4", "F5", "F6",
    "entry", "sl", "tp1", "tp2", "tp3",
]


def _n(value: float | None, nd: int = 2) -> str:
    return "" if value is None else f"{value:.{nd}f}"


def _pf(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def now_local() -> datetime:
    """Thoi gian hien tai theo mui gio cau hinh (fallback ve local time)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(config.TIMEZONE))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc).astimezone()


# --------------------------------------------------------------------- console
def print_report(
    results: list[CoinScore],
    scan_time: datetime,
    elapsed: float,
    min_score: float | None = None,
) -> None:
    threshold = config.MIN_SCORE if min_score is None else min_score
    ts = scan_time.strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "=" * 118)
    print(
        f" BOT LOC SHORT F1-F6  |  {ts}  |  nguong >= {threshold:.0f}/100"
        f"  |  {len(results)} coin  |  {elapsed:.1f}s"
    )
    print("=" * 118)

    if not results:
        print(" Khong co coin nao dat nguong diem trong vong quet nay.")
        print("=" * 118 + "\n")
        return

    print(
        f"{'#':>3} {'SYMBOL':<14}{'SCORE':>7} {'GR':<3}{'ACT':<6}"
        f"{'RSI15m':>7}{'RSI4H':>7}{'RSI1D':>7}{'LONG%':>7}"
        f"{'SPIKE':>7}{'OI-1h':>8}{'WICK':>6}{'FUND%':>9}{'TRAP':>6}  F1-F6"
    )
    print("-" * 118)

    for i, c in enumerate(results, start=1):
        m = c.metrics
        # vd "++-+-+" theo thu tu F1..F6
        flags = "".join("+" if f.passed else "-" for f in c.filters)
        print(
            f"{i:>3} {c.symbol:<14}{c.total_score:>7.1f} {c.grade:<3}{c.action:<6}"
            f"{_n(m.get('rsi_15m'), 1):>7}{_n(m.get('rsi_4h'), 1):>7}"
            f"{_n(m.get('rsi_1d'), 1):>7}{_n(m.get('long_ratio'), 1):>7}"
            f"{_n(m.get('spike'), 2):>7}{_n(m.get('oi_change'), 2):>8}"
            f"{_n(m.get('upper_wick'), 2):>6}{_n(m.get('funding'), 4):>9}"
            f"{c.trap_risk:>6.1f}  {flags}"
        )

    print("-" * 118)
    print(
        " CHI TIET (Entry/SL/TP theo PDF: SL +1.3% | TP -3.5% / -9.8% / -15%)"
    )
    print("-" * 118)
    for c in results[: min(10, len(results))]:
        lv = c.levels
        note = "" if not c.failed_mandatory else (
            f"  << WAIT: {', '.join(c.failed_mandatory)} FAIL (bat buoc)"
        )
        print(
            f" {c.symbol:<14} {c.total_score:>5.1f}/100  {c.grade:<3} {c.action:<5}"
            f" Trap {c.trap_risk:>4.1f}/10{note}"
        )
        print(
            f"   Entry={lv.get('entry')}  SL={lv.get('sl')}"
            f"  TP1={lv.get('tp1')}  TP2={lv.get('tp2')}  TP3={lv.get('tp3')}"
        )
        for f in c.filters:
            print(
                f"   {f.code} {_pf(f.passed):<4} {f.score:>5.1f}/{f.max_score:<4.0f}"
                f" {f.name:<18} {f.detail}"
            )
        print()
    print("=" * 118 + "\n")


# ------------------------------------------------------------------------- csv
def save_csv(results: list[CoinScore], scan_time: datetime) -> Path | None:
    """Ghi ket qua vao signals/signals_YYYYMMDD.csv (append) de backtest sau."""
    if not results:
        return None
    Path(config.CSV_DIR).mkdir(parents=True, exist_ok=True)
    path = Path(config.CSV_DIR) / f"signals_{scan_time:%Y%m%d}.csv"
    exists = path.exists()

    with path.open("a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        if not exists:
            writer.writerow(CSV_HEADER)
        for c in results:
            m, lv = c.metrics, c.levels
            fmap = {f.code: f for f in c.filters}
            writer.writerow([
                scan_time.strftime("%Y-%m-%d %H:%M:%S"), c.symbol,
                f"{c.total_score:.2f}", c.passed_count, c.grade, c.action,
                c.trap_risk,
                m.get("price"), _n(m.get("price_change_pct_24h")),
                _n(m.get("price_change_pct_1h")),
                _n(m.get("quote_volume_24h"), 0), _n(m.get("volume_ratio")),
                _n(m.get("rsi_15m")), _n(m.get("rsi_4h")), _n(m.get("rsi_1d")),
                _n(m.get("long_ratio")), _n(m.get("spike")),
                _n(m.get("oi_change")), _n(m.get("upper_wick"), 3),
                _n(m.get("funding"), 4),
                *[_pf(fmap[k].passed) for k in ("F1", "F2", "F3", "F4", "F5", "F6")],
                lv.get("entry"), lv.get("sl"),
                lv.get("tp1"), lv.get("tp2"), lv.get("tp3"),
            ])
    log.info("Luu %d dong vao %s", len(results), path)
    return path


# -------------------------------------------------------------------- telegram
def print_telegram_summary(coins: list[CoinScore]) -> None:
    """In danh sach coin du dieu kien day Telegram (>= N tieu chi PASS)."""
    min_pass = config.TELEGRAM_MIN_PASSED_FILTERS
    print("-" * 118)
    print(
        f" TELEGRAM: {len(coins)} coin co >= {min_pass}/6 tieu chi PASS"
        " (day duoi dang WAIT/SHORT)"
    )
    print("-" * 118)
    if not coins:
        print(" (khong co coin nao du dieu kien)\n")
        return
    for c in coins:
        flags = "".join("+" if f.passed else "-" for f in c.filters)
        passed = ",".join(f.code for f in c.filters if f.passed)
        print(
            f" {c.symbol:<14} {c.passed_count}/6 PASS [{flags}]"
            f"  {c.total_score:>5.1f}/100  {c.grade:<3} {c.action:<5}"
            f"  PASS: {passed}"
        )
    print()


def build_demo_coin() -> CoinScore:
    """
    Tao CoinScore mau dung so lieu CHILLGUYUSDT trong anh tin hieu goc,
    dung cho --test-telegram (kiem tra dinh dang + ket noi ma khong can quet).
    """
    from scoring import score_coin

    metrics = {
        "symbol": "CHILLGUYUSDT",
        "price": 0.01464,
        "price_change_pct_24h": 17.00,
        "price_change_pct_1h": -0.28,
        "quote_volume_24h": 12_000_000.0,
        "volume_ratio": 0.6,
        "rsi_15m": 70.05,
        "rsi_4h": 78.3,
        "rsi_1d": 67.81,
        "rsi_periods": config.RSI_PERIODS,
        "long_ratio": 68.5,
        "spike": 6.1,
        "spike_time": "10:30",
        "oi_change": 4.0,          # < 5% -> F4 FAIL giong anh
        "oi_value_from": 2_500_000.0,
        "oi_value_to": 2_600_000.0,
        "oi_periods": 3,
        "upper_wick": 0.42,
        "upper_wick_time": "10:45",
        "funding": 0.005,
    }
    cs = score_coin("CHILLGUYUSDT", metrics)
    import indicators as _ind

    cs.levels = {
        k: _ind.round_to_tick(v, 0.00001, 5)
        for k, v in _ind.compute_entry_sl_tp(0.01464).items()
    }
    return cs
