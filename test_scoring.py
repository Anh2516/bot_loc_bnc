"""
Kiem chung logic F1-F6 bang 2 vi du mau trong PDF (KGENUSDT va TSTUSDT).
Chay: python test_scoring.py
"""
from __future__ import annotations

import config
import indicators
import telegram_notifier
from scoring import score_coin

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [OK]   {name} {extra}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} {extra}")


def test_kgen_full_pass() -> None:
    """KGENUSDT trong PDF: F1-F6 deu PASS -> A+ SHORT."""
    print("\n[1] KGENUSDT (F1-F6 deu PASS theo PDF)")
    metrics = {
        "price": 0.2334,
        "rsi_15m": 92.0,     # >= 90
        "rsi_4h": 84.0,      # >= 80
        "rsi_1d": 70.0,      # >= 65
        "long_ratio": 68.0,  # >= 65
        "spike": 8.5,        # >= 7
        "oi_change": 9.1,    # >= 8 (dung so trong PDF)
        "upper_wick": 0.45,  # >= 0.30
        "funding": 0.01,     # >= -0.15
    }
    cs = score_coin("KGENUSDT", metrics)
    check("tat ca F1-F6 PASS", cs.passed_all, f"grade={cs.grade}")
    check("diem = 100", abs(cs.total_score - 100.0) < 0.01, f"score={cs.total_score}")
    check("action = SHORT", cs.action == "SHORT")
    check("grade = A+", cs.grade == "A+")
    check("khong FAIL bo loc bat buoc", cs.failed_mandatory == [])


def test_levels_formula() -> None:
    """
    Entry/SL/TP phai khop du lieu that theo preset dang dung:
      * LEVELS_PRESET="PDF"        -> KGENUSDT: SL 0.23643, TP 0.22523/0.21053/0.19839
      * LEVELS_PRESET="SCREENSHOT" -> anh that: Entry 0.013297 -> SL 0.0135,
                                      TP 0.0128 / 0.0123 / 0.0118
    """
    print(f"\n[2] Cong thuc Entry/SL/TP (preset {config.LEVELS_PRESET})")

    if config.LEVELS_PRESET == "PDF":
        lv = indicators.compute_entry_sl_tp(0.2334)
        expected = {"sl": 0.23643, "tp1": 0.22523, "tp2": 0.21053, "tp3": 0.19839}
        for key, want in expected.items():
            got = lv[key]
            check(
                f"KGEN {key.upper():<4} ~ {want}",
                abs(got - want) <= 0.00001,
                f"= {got:.5f}",
            )
        return

    # SCREENSHOT: doi chieu voi anh tin hieu that (Entry 0.013297)
    lv = indicators.compute_entry_sl_tp(0.013297)
    expected_rounded = {"sl": 0.0135, "tp1": 0.0128, "tp2": 0.0123, "tp3": 0.0118}
    for key, want in expected_rounded.items():
        got = round(lv[key], 4)
        check(f"anh {key.upper():<4} = {want}", got == want, f"= {got}")

    # % lai/lo cua vi the SHORT
    e = 0.013297
    check(
        "SL = -1.5% (PnL short)",
        abs((1 - lv["sl"] / e) * 100 + 1.5) < 0.05,
        f"= {(1 - lv['sl'] / e) * 100:.2f}%",
    )
    for i, key in enumerate(("tp1", "tp2", "tp3")):
        want_pct = config.TP_PCTS[i]
        got_pct = (1 - lv[key] / e) * 100
        check(
            f"{key.upper()} = +{want_pct}% (PnL short)",
            abs(got_pct - want_pct) < 0.05,
            f"= {got_pct:.2f}%",
        )

    # TP phai dung boi so R cua rui ro
    if config.TP_R_MULTIPLES:
        for i, r in enumerate(config.TP_R_MULTIPLES):
            check(
                f"TP{i + 1} = {r:g}R",
                abs(config.TP_PCTS[i] / config.SL_PCT - r) < 0.01,
                f"= {config.TP_PCTS[i] / config.SL_PCT:.2f}R",
            )


def test_tst_wait() -> None:
    """TSTUSDT: F1 FAIL (RSI1D=63.2) va F6 FAIL (funding=-0.252) -> WAIT."""
    print("\n[3] TSTUSDT (F1 + F6 FAIL theo PDF)")
    metrics = {
        "price": 1.0,
        "rsi_15m": 91.0,
        "rsi_4h": 82.0,
        "rsi_1d": 63.2,      # < 65  -> F1 FAIL
        "long_ratio": 66.0,
        "spike": 7.5,
        "oi_change": 9.0,
        "upper_wick": 0.35,
        "funding": -0.252,   # < -0.15 -> F6 FAIL
    }
    cs = score_coin("TSTUSDT", metrics)
    fmap = {f.code: f for f in cs.filters}
    check("F1 FAIL", not fmap["F1"].passed, fmap["F1"].detail)
    check("F6 FAIL", not fmap["F6"].passed, fmap["F6"].detail)
    check("F2-F5 PASS", all(fmap[k].passed for k in ("F2", "F3", "F4", "F5")))
    check("action = WAIT", cs.action == "WAIT", f"score={cs.total_score}")
    check("bao dung bo loc bat buoc FAIL", set(cs.failed_mandatory) == {"F1", "F6"})


def test_partial_credit() -> None:
    """
    Coin dat dung diem giua moi ramp phai duoc ~50/100 (partial credit).
    Lay gia tri tu config.RAMPS de test khong phu thuoc preset dang dung.
    """
    print("\n[4] Cham diem tung phan (partial credit)")
    mid = {k: (lo + hi) / 2 for k, (lo, hi) in config.RAMPS.items()}
    metrics = {
        "price": 1.0,
        "rsi_15m": mid["rsi_15m"],
        "rsi_4h": mid["rsi_4h"],
        "rsi_1d": mid["rsi_1d"],
        "long_ratio": mid["long_ratio"],
        "spike": mid["spike"],
        "oi_change": mid["oi"],
        "upper_wick": mid["upper_wick"],
        "funding": mid["funding"],
    }
    cs = score_coin("MIDUSDT", metrics)
    check("diem ~ 50/100", abs(cs.total_score - 50.0) < 0.5, f"score={cs.total_score}")
    check("khong bo loc nao PASS", not any(f.passed for f in cs.filters))
    check("action = WAIT", cs.action == "WAIT")
    check("passed_count = 0", cs.passed_count == 0)


def _chillguy_metrics() -> dict:
    """So lieu CHILLGUYUSDT lay tu anh tin hieu that cua bot goc."""
    return {
        "price": 0.01464,
        "price_change_pct_24h": 17.00,
        "price_change_pct_1h": -0.28,
        "volume_ratio": 0.6,
        "rsi_15m": 70.05,
        "rsi_4h": 78.3,
        "rsi_1d": 67.81,
        "rsi_periods": config.RSI_PERIODS,
        "long_ratio": 68.5,
        "spike": 6.1,
        "spike_time": "10:30",
        "oi_change": 4.0,          # anh: khong tang du 5% -> F4 FAIL
        "oi_value_from": 2_500_000.0,
        "oi_value_to": 2_600_000.0,
        "oi_periods": 3,
        "upper_wick": 0.42,
        "upper_wick_time": "10:45",
        "funding": 0.005,
    }


def test_chillguy_screenshot() -> None:
    """
    Doi chieu voi anh tin hieu that CHILLGUYUSDT:
      F1 PASS, F2 PASS, F3 PASS, F4 FAIL, F5 PASS, F6 PASS -> "C - WAIT".
    """
    print("\n[8] CHILLGUYUSDT (anh tin hieu that: 5/6 PASS -> C WAIT)")
    if config.FILTER_PRESET != "SCREENSHOT":
        print("  (bo qua: dang dung preset PDF)")
        return
    cs = score_coin("CHILLGUYUSDT", _chillguy_metrics())
    fmap = {f.code: f for f in cs.filters}
    check("F1 PASS", fmap["F1"].passed, fmap["F1"].reason)
    check("F2 PASS", fmap["F2"].passed, fmap["F2"].reason)
    check("F3 PASS (spike 6.1%)", fmap["F3"].passed, fmap["F3"].reason)
    check("F4 FAIL (OI 4% < 5%)", not fmap["F4"].passed, fmap["F4"].reason)
    check("F5 PASS", fmap["F5"].passed, fmap["F5"].reason)
    check("F6 PASS", fmap["F6"].passed, fmap["F6"].reason)
    check("passed_count = 5/6", cs.passed_count == 5, f"= {cs.passed_count}")
    check("action = WAIT (thieu F4)", cs.action == "WAIT")
    check("grade = C giong anh", cs.grade == "C", f"= {cs.grade}")
    check("failed_codes = ['F4']", cs.failed_codes == ["F4"], f"= {cs.failed_codes}")


def test_telegram_condition() -> None:
    """Dieu kien day Telegram: >= 2 tieu chi PASS trong F1-F6."""
    min_pass = config.TELEGRAM_MIN_PASSED_FILTERS
    print(f"\n[9] Dieu kien day Telegram (>= {min_pass} PASS)")
    check("nguong hop le (2-6)", 2 <= min_pass <= 6, f"= {min_pass}")

    # Coin 5/6 PASS -> luon du dieu kien
    good = score_coin("CHILLGUYUSDT", _chillguy_metrics())
    check("coin 5/6 PASS -> day", good.passed_count >= min_pass, f"= {good.passed_count}")

    # Coin chi PASS F5 + F6 (2 tieu chi de nhat)
    two = score_coin("TWOUSDT", {
        "price": 1.0, "rsi_15m": 10.0, "rsi_4h": 10.0, "rsi_1d": 10.0,
        "long_ratio": 10.0, "spike": 0.0, "oi_change": -5.0,
        "upper_wick": 0.9, "funding": 0.01,
    })
    check("dem dung 2 PASS (F5,F6)", two.passed_count == 2, f"= {two.passed_count}")
    check(
        f"coin 2/6 {'duoc day' if min_pass <= 2 else 'BI LOAI'}",
        (two.passed_count >= min_pass) == (min_pass <= 2),
    )
    check("action = WAIT", two.action == "WAIT")

    # Coin chi PASS 1 tieu chi -> chac chan khong day
    one = score_coin("ONEUSDT", {
        "price": 1.0, "rsi_15m": 10.0, "rsi_4h": 10.0, "rsi_1d": 10.0,
        "long_ratio": 10.0, "spike": 0.0, "oi_change": -5.0,
        "upper_wick": 0.0, "funding": 0.01,
    })
    check("coin PASS 1 (F6) -> khong day", one.passed_count < min_pass,
          f"= {one.passed_count}")


def test_telegram_message_format() -> None:
    """Tin nhan Telegram phai chua dung cac truong nhu anh mau."""
    print("\n[10] Dinh dang tin nhan Telegram")
    cs = score_coin("CHILLGUYUSDT", _chillguy_metrics())
    msg = telegram_notifier.build_message(cs)

    must_have = [
        "CHILLGUYUSDT",
        "RSI",
        "0.01464",
        "+17.00%",       # 24h
        "-0.28%",        # 1h
        "0.6x",          # Vol
        "68.5%",         # L/S
        "+0.005%",       # FR
        "2.6M",          # OI
        "WAIT",
        "F1: PASS",
        "F4: FAIL",
        "OI did not increase by 5% over the last 3 periods (2.5M to 2.6M)",
        "at 10:30 UTC",  # spike time
        "at 10:45 UTC",  # upper wick time
        "\U0001f4cc",    # 📌 dong ket luan
    ]
    for token in must_have:
        check(f"tin nhan chua {token!r}", token in msg)
    check("khong hien Entry/SL khi WAIT", "Entry" not in msg)


def test_weights_sum_100() -> None:
    print("\n[5] Tong trong so = 100 va xu ly thieu du lieu")
    total = sum(config.WEIGHTS.values())
    check("sum(WEIGHTS) == 100", abs(total - 100.0) < 1e-9, f"= {total}")
    cs = score_coin("X", {})
    max_score = sum(f.max_score for f in cs.filters)
    check("tong max_score = 100", abs(max_score - 100.0) < 1e-9, f"= {max_score}")
    check("thieu du lieu -> 0 diem", cs.total_score == 0.0, f"score={cs.total_score}")
    check("thieu du lieu -> WAIT", cs.action == "WAIT")


def test_rsi_math() -> None:
    """RSI Wilder: gia tang lien tuc -> 100; giam lien tuc -> gan 0."""
    print("\n[6] Cong thuc RSI (Wilder)")
    up = [100.0 + i for i in range(60)]
    down = [200.0 - i for i in range(60)]
    r_up = indicators.rsi(up)
    r_down = indicators.rsi(down)
    check("RSI chuoi tang = 100", r_up is not None and r_up > 99.9, f"= {r_up}")
    check("RSI chuoi giam < 1", r_down is not None and r_down < 1.0, f"= {r_down}")
    check("thieu nen -> None", indicators.rsi([1.0, 2.0]) is None)


def test_indicator_helpers() -> None:
    print("\n[7] Spike / Upper wick / round_to_tick")
    ohlc = {
        "open": [100.0, 100.0],
        "high": [101.0, 110.0],
        "low": [99.0, 100.0],
        "close": [100.0, 104.0],
    }
    sp = indicators.spike_pct(ohlc, bars=1)
    check("spike 1 nen = 10%", sp is not None and abs(sp - 10.0) < 1e-9, f"= {sp}")
    # nen cuoi: high=110, low=100, max(open,close)=104 -> wick = 6/10 = 0.6
    wick = indicators.upper_wick_ratio(ohlc, lookback=1)
    check("wick ratio = 0.6", wick is not None and abs(wick - 0.6) < 1e-9, f"= {wick}")
    check(
        "round_to_tick 0.23643 -> 0.2364",
        indicators.round_to_tick(0.23643, 0.0001) == 0.2364,
    )
    check(
        "round_to_tick khong co tick",
        indicators.round_to_tick(1.23456789, None, 4) == 1.2346,
    )


def test_new_indicators() -> None:
    """Cac chi bao moi phuc vu tin nhan Telegram."""
    print("\n[11] Chi bao moi: 1h change / vol ratio / format / timestamp")
    ohlc = {
        "open_time": [1732500000000.0, 1732500900000.0],
        "open": [100.0, 100.0],
        "high": [101.0, 110.0],
        "low": [99.0, 100.0],
        "close": [100.0, 104.0],
        "volume": [50.0, 30.0],
    }
    chg = indicators.price_change_pct(ohlc, bars=2)
    check("price_change 2 nen = +4%", chg is not None and abs(chg - 4.0) < 1e-9, f"= {chg}")

    sp, t = indicators.spike_with_time(ohlc, bars=2)
    check("spike_with_time = 10%", sp is not None and abs(sp - 10.0) < 1e-9, f"= {sp}")
    check("spike co timestamp UTC HH:MM", bool(t and ":" in t), f"= {t}")

    wick, wt = indicators.upper_wick_with_time(ohlc, lookback=1)
    check("wick_with_time = 0.6", wick is not None and abs(wick - 0.6) < 1e-9, f"= {wick}")
    check("wick co timestamp", bool(wt and ":" in wt), f"= {wt}")

    vols = {"volume": [10.0] * 20 + [6.0]}
    vr = indicators.volume_ratio(vols, lookback=20)
    check("volume_ratio = 0.6x", vr is not None and abs(vr - 0.6) < 1e-9, f"= {vr}")

    check("format_compact 2600000 -> 2.6M", indicators.format_compact(2_600_000) == "2.6M")
    check("format_compact 512000 -> 512.0K", indicators.format_compact(512_000) == "512.0K")
    check("format_compact None -> n/a", indicators.format_compact(None) == "n/a")
    check("format_price 0.01464", indicators.format_price(0.01464) == "0.01464")
    check("utc_hhmm None -> None", indicators.utc_hhmm(None) is None)


def test_cooldown() -> None:
    """SentTracker phai chan gui lai cung 1 coin trong thoi gian cooldown."""
    print("\n[12] Cooldown chong spam Telegram")
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.gettempdir()) / "f1f6_test_cooldown.json"
    tmp.unlink(missing_ok=True)
    tracker = telegram_notifier.SentTracker(str(tmp))

    check("coin moi -> khong bi chan", not tracker.in_cooldown("AAAUSDT"))
    tracker.mark("AAAUSDT")
    check("sau khi gui -> bi chan", tracker.in_cooldown("AAAUSDT"))
    check("coin khac -> khong bi chan", not tracker.in_cooldown("BBBUSDT"))
    check("cooldown = 0 phut -> khong chan", not tracker.in_cooldown("AAAUSDT", minutes=0))

    # State phai doc lai duoc sau khi restart
    tracker2 = telegram_notifier.SentTracker(str(tmp))
    check("state luu ra file va doc lai duoc", tracker2.in_cooldown("AAAUSDT"))
    tmp.unlink(missing_ok=True)


def test_short_label_all_pass() -> None:
    """Coin PASS ca 6 tieu chi moi duoc gan nhan SHORT + hien Entry/SL/TP."""
    print("\n[13] Nhan SHORT chi khi PASS het F1-F6")
    m = _chillguy_metrics()
    m["oi_change"] = 12.0          # sua F4 thanh PASS -> du 6/6
    cs = score_coin("CHILLGUYUSDT", m)
    cs.levels = indicators.compute_entry_sl_tp(cs.price)
    check("passed_count = 6/6", cs.passed_count == 6, f"= {cs.passed_count}")
    check("action = SHORT", cs.action == "SHORT")
    check("grade = A+ hoac A", cs.grade in ("A+", "A"), f"= {cs.grade}")
    msg = telegram_notifier.build_message(cs)
    check("tin nhan co Entry/SL/TP", "Entry" in msg and "TP1" in msg)
    check("tin nhan ghi SHORT", "SHORT" in msg)


def test_normalize_symbol() -> None:
    """Chuan hoa tu khoa nguoi dung go trong /search."""
    print("\n[14] Chuan hoa ten coin cho /search")
    import telegram_bot

    cases = {
        "btc": "BTCUSDT",
        "BTC": "BTCUSDT",
        "btcusdt": "BTCUSDT",
        "BTC-USDT": "BTCUSDT",
        "btc/usdt": "BTCUSDT",
        " kgen ": "KGENUSDT",
        "$doge": "DOGEUSDT",
        "chillguy": "CHILLGUYUSDT",
    }
    for raw, want in cases.items():
        got = telegram_bot.normalize_symbol(raw)
        check(f"{raw!r} -> {want}", got == want, f"= {got}")
    check("chuoi rong -> rong", telegram_bot.normalize_symbol("  ") == "")


def test_search_message() -> None:
    """Tin nhan /search phai co diem tung tieu chi va tong diem."""
    print("\n[15] Tin nhan /search (chi tiet tung tieu chi + diem)")
    cs = score_coin("CHILLGUYUSDT", _chillguy_metrics())
    cs.levels = {
        k: round(v, 5)
        for k, v in indicators.compute_entry_sl_tp(cs.price).items()
    }
    msg = telegram_notifier.build_search_message(cs)

    check("co tieu de CHI TIET F1-F6", "CHI TIET F1-F6" in msg)
    check("co tong diem /100", f"{cs.total_score:.1f}/100" in msg, f"{cs.total_score}")
    check("co so tieu chi PASS", f"{cs.passed_count}/6" in msg)
    check("co hang (grade)", f"Hang <b>{cs.grade}</b>" in msg)
    check("co Trap Risk", "Trap Risk" in msg)
    for code in ("F1", "F2", "F3", "F4", "F5", "F6"):
        check(f"co khoi {code}", f"<b>{code} \u00b7" in msg)
    # F4 FAIL nhung van co diem tung phan (OI 4% nam giua ramp) -> phai hien x.x/20
    f4 = next(f for f in cs.filters if f.code == "F4")
    check(
        "F4 FAIL nhung co diem tung phan",
        not f4.passed and 0 < f4.score < f4.max_score,
        f"= {f4.score:.1f}/{f4.max_score:.0f}",
    )
    check(f"tin nhan hien {f4.score:.1f}/20", f"{f4.score:.1f}/20</b> diem" in msg)
    check("co diem full F6 (12/12)", "12.0/12</b> diem" in msg)
    check("co thanh tien do", "\u2588" in msg or "\u2591" in msg)
    check("co muc gia tham khao", "Entry" in msg and "TP1" in msg)
    check("co muc do quan trong", "Rat quan trong" in msg)
    check("do dai tin nhan <= 4096", len(msg) <= 4096, f"= {len(msg)} ky tu")


def test_subscriber_store() -> None:
    """SubscriberStore luu/xoa chat_id va song sot qua restart."""
    print("\n[16] Quan ly subscriber (/start, /stop)")
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.gettempdir()) / "f1f6_test_subs.json"
    tmp.unlink(missing_ok=True)
    store = telegram_notifier.SubscriberStore(str(tmp))

    check("ban dau rong", store.all() == [], f"= {store.all()}")
    check("them moi -> True", store.add(12345) is True)
    check("them lai -> False", store.add(12345) is False)
    check("co trong danh sach", "12345" in store.all())
    check("them nguoi thu 2", store.add(-100999) is True)
    check("len = 2", len(store) == 2, f"= {len(store)}")

    store2 = telegram_notifier.SubscriberStore(str(tmp))
    check("doc lai sau restart", set(store2.all()) == {"12345", "-100999"})
    check("xoa -> True", store2.remove(12345) is True)
    check("xoa lai -> False", store2.remove(12345) is False)
    check("con 1 nguoi", len(store2) == 1, f"= {len(store2)}")
    tmp.unlink(missing_ok=True)


def test_scan_cache() -> None:
    """ScanCache luu ket qua vong quet cho lenh /top va /status."""
    print("\n[17] ScanCache cho /top va /status")
    from telegram_bot import ScanCache

    cache = ScanCache()
    results, cands, ts, n = cache.snapshot()
    check("ban dau rong", results == [] and cands == [] and n == 0)
    check("scan_time mac dinh", ts == "chua quet", f"= {ts}")

    a = score_coin("AAAUSDT", _chillguy_metrics())
    b = score_coin("BBBUSDT", {"price": 1.0, "funding": 0.01, "upper_wick": 0.9})
    cache.update([a, b], [a], "12:34:56 29/08")
    results, cands, ts, n = cache.snapshot()
    check("luu 2 ket qua", n == 2, f"= {n}")
    check("luu 1 candidate", len(cands) == 1 and cands[0].symbol == "AAAUSDT")
    check("luu scan_time", ts == "12:34:56 29/08", f"= {ts}")


def test_telegram_threshold_4() -> None:
    """Nguong day Telegram phai la >= 4/6 tieu chi PASS."""
    print("\n[18] Nguong day Telegram = 4/6 tieu chi")
    check(
        "TELEGRAM_MIN_PASSED_FILTERS = 4",
        config.TELEGRAM_MIN_PASSED_FILTERS == 4,
        f"= {config.TELEGRAM_MIN_PASSED_FILTERS}",
    )

    m = _chillguy_metrics()          # 5/6 PASS
    cs5 = score_coin("FIVEUSDT", m)
    check("coin 5/6 PASS -> duoc day", cs5.passed_count >= 4, f"= {cs5.passed_count}")

    # Coin 4/6: bo them F3 (spike thap)
    m4 = dict(m)
    m4["spike"] = 0.5
    cs4 = score_coin("FOURUSDT", m4)
    check("coin 4/6 PASS -> duoc day", cs4.passed_count == 4, f"= {cs4.passed_count}")

    # Coin 3/6: bo them F2
    m3 = dict(m4)
    m3["long_ratio"] = 40.0
    cs3 = score_coin("THREEUSDT", m3)
    check(
        "coin 3/6 PASS -> KHONG day",
        cs3.passed_count < config.TELEGRAM_MIN_PASSED_FILTERS,
        f"= {cs3.passed_count}",
    )


def test_priority_sort() -> None:
    """Coin manh nhat (nhieu PASS + diem cao) phai duoc xep len dau."""
    print("\n[19] Sap xep uu tien coin manh nhat")
    from scanner import Scanner

    base = _chillguy_metrics()

    # 6/6 PASS - manh nhat
    m6 = dict(base)
    m6["oi_change"] = 20.0
    best = score_coin("BESTUSDT", m6)

    # 5/6 PASS
    good = score_coin("GOODUSDT", dict(base))

    # 4/6 PASS (FAIL F3+F4), diem cao vi OI con duoc diem tung phan
    m4a = dict(base)
    m4a["spike"] = 0.5
    m4a["oi_change"] = 4.5           # sat nguong -> gan full diem partial
    mid_hi = score_coin("MIDHIUSDT", m4a)

    # 4/6 PASS (cung FAIL F3+F4) nhung OI am -> mat het diem F4
    m4b = dict(m4a)
    m4b["oi_change"] = -10.0
    mid_lo = score_coin("MIDLOUSDT", m4b)

    check(
        "2 coin 4/6 co diem khac nhau",
        mid_hi.total_score > mid_lo.total_score,
        f"{mid_hi.total_score} > {mid_lo.total_score}",
    )

    # 2/6 PASS - bi loai boi nguong 4
    weak = score_coin("WEAKUSDT", {
        "price": 1.0, "rsi_15m": 10.0, "rsi_4h": 10.0, "rsi_1d": 10.0,
        "long_ratio": 10.0, "spike": 0.0, "oi_change": -5.0,
        "upper_wick": 0.9, "funding": 0.01,
    })

    scanner = Scanner.__new__(Scanner)  # khong goi __init__ (khong can mang)
    picked = scanner.telegram_candidates([mid_lo, weak, good, best, mid_hi])

    syms = [c.symbol for c in picked]
    check("loai coin 2/6 PASS", "WEAKUSDT" not in syms, f"= {syms}")
    check("con lai 4 coin", len(picked) == 4, f"= {len(picked)}")
    check("#1 = coin 6/6 PASS", syms[0] == "BESTUSDT", f"= {syms[0]}")
    check("#2 = coin 5/6 PASS", syms[1] == "GOODUSDT", f"= {syms[1]}")
    check(
        "trong cung so PASS: diem cao truoc",
        syms[2] == "MIDHIUSDT" and syms[3] == "MIDLOUSDT",
        f"= {syms[2]}, {syms[3]}",
    )
    check("gan rank tu 1", picked[0].rank == 1 and picked[-1].rank == 4)
    check("gan rank_total", all(c.rank_total == 4 for c in picked))
    check("score_10 dung", abs(best.score_10 - best.total_score / 10) < 0.05,
          f"= {best.score_10}")


def test_message_new_format() -> None:
    """Tin nhan phai co Score /10, rank, Entry/SL/TP kem % PnL short."""
    print("\n[20] Dinh dang tin nhan moi (giong anh)")
    m = _chillguy_metrics()
    m["oi_change"] = 20.0            # cho PASS het 6 -> SHORT
    cs = score_coin("MYCOINUSDT", m)
    cs.rank, cs.rank_total = 1, 3
    cs.levels = {
        k: round(v, 6) for k, v in indicators.compute_entry_sl_tp(0.013297).items()
    }
    msg = telegram_notifier.build_message(cs)

    # % hien thi lam tron 1 chu so, tinh tu config de khong phu thuoc preset
    sl_pct = f"(-{config.SL_PCT:.1f}%)"
    tp1_pct = f"(+{config.TP_PCTS[0]:.1f}%)"

    check("co so thu tu #1/3", "#1/3" in msg)
    check("co icon 🔥 cho SHORT", "\U0001f525" in msg)
    check("co Entry:", "Entry:" in msg)
    check(f"co SL: kem % am {sl_pct}", "SL:" in msg and sl_pct in msg)
    check(f"co TP1 kem % duong {tp1_pct}", "TP1:" in msg and tp1_pct in msg)
    if config.TP_R_MULTIPLES:
        check("co boi so R", "2.5R" in msg and "7.5R" in msg)
    check("co Score /10", "Score:" in msg and "/10" in msg)
    check("co Trap risk", "Trap risk:" in msg)
    check("co PASS 6/6", "PASS <b>6/6</b>" in msg)
    check("do dai <= 4096", len(msg) <= 4096, f"= {len(msg)}")


def test_full_scan_config() -> None:
    """Cau hinh phai cho phep quet toan bo ~524 coin ma khong vuot rate limit."""
    print("\n[21] Cau hinh quet toan bo coin")
    check("SCAN_ALL_SYMBOLS = True", config.SCAN_ALL_SYMBOLS is True)
    check(
        "MAX_SYMBOLS_PER_SCAN >= 524",
        config.MAX_SYMBOLS_PER_SCAN >= 524,
        f"= {config.MAX_SYMBOLS_PER_SCAN}",
    )
    check(
        "KLINES_LIMIT <= 100 (weight 1)",
        config.KLINES_LIMIT <= 100,
        f"= {config.KLINES_LIMIT}",
    )
    check(
        "KLINES_LIMIT >= 60 (du nen cho RSI 24 + vol 20)",
        config.KLINES_LIMIT >= 60,
        f"= {config.KLINES_LIMIT}",
    )
    check("giu coin non-ASCII", config.EXCLUDE_NON_ASCII_SYMBOLS is False)

    # Uoc tinh weight: 3 klines/coin + batch (ticker 40 + premium 10 + info 1)
    est = 524 * 3 + 51
    check(
        f"weight uoc tinh {est} <= tran {config.MAX_WEIGHT_PER_MINUTE}",
        est <= config.MAX_WEIGHT_PER_MINUTE,
        f"= {est / config.MAX_WEIGHT_PER_MINUTE * 100:.0f}% han muc",
    )
    check(
        "tran weight <= 2400 (gioi han that cua Binance)",
        config.MAX_WEIGHT_PER_MINUTE <= 2400,
        f"= {config.MAX_WEIGHT_PER_MINUTE}",
    )
    check(
        "Telegram chi day 3-4 coin manh nhat",
        3 <= config.TELEGRAM_MAX_MESSAGES_PER_SCAN <= 4,
        f"= {config.TELEGRAM_MAX_MESSAGES_PER_SCAN}",
    )


def test_weight_limiter() -> None:
    """WeightLimiter phai dem dung va dong bo voi header cua Binance."""
    print("\n[22] Rate limiter theo weight")
    from binance_client import WeightLimiter

    lim = WeightLimiter(max_per_minute=100)
    check("ban dau = 0", lim.used == 0, f"= {lim.used}")

    lim.acquire(40)
    check("sau acquire(40) = 40", lim.used == 40, f"= {lim.used}")

    lim.acquire(10)
    check("sau acquire(10) = 50", lim.used == 50, f"= {lim.used}")

    # Binance bao so that cao hon -> phai lay theo Binance
    lim.sync("80")
    check("sync('80') -> 80", lim.used == 80, f"= {lim.used}")

    # Binance bao thap hon -> giu so cua minh (an toan hon)
    lim.sync("10")
    check("sync('10') -> van 80", lim.used == 80, f"= {lim.used}")

    lim.sync(None)
    check("sync(None) khong loi", lim.used == 80)
    lim.sync("khong-phai-so")
    check("sync chuoi la khong loi", lim.used == 80)


def main() -> int:
    print("=" * 70)
    print(" KIEM CHUNG LOGIC F1-F6 (PDF + ANH TIN HIEU THAT)")
    print(f" Preset dang dung: {config.FILTER_PRESET}"
          f" | RSI {config.RSI_PERIODS}"
          f" | Telegram khi >= {config.TELEGRAM_MIN_PASSED_FILTERS} PASS")
    print("=" * 70)
    test_kgen_full_pass()
    test_levels_formula()
    test_tst_wait()
    test_partial_credit()
    test_weights_sum_100()
    test_rsi_math()
    test_indicator_helpers()
    test_chillguy_screenshot()
    test_telegram_condition()
    test_telegram_message_format()
    test_new_indicators()
    test_cooldown()
    test_short_label_all_pass()
    test_normalize_symbol()
    test_search_message()
    test_subscriber_store()
    test_scan_cache()
    test_telegram_threshold_4()
    test_priority_sort()
    test_message_new_format()
    test_full_scan_config()
    test_weight_limiter()
    print("\n" + "=" * 70)
    print(f" KET QUA: {PASSED} OK / {FAILED} FAIL")
    print("=" * 70)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
