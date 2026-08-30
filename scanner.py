"""
Scanner: quet toan bo coin PERPETUAL USDT tren Binance Futures,
tinh chi bao F1-F6 va cham diem tren thang 100.

Chien luoc tiet kiem rate limit:
  Buoc 1 (2 request cho ca san): /ticker/24hr + /premiumIndex -> prefilter
  Buoc 2 (song song, ~5 request/coin): klines 15m/4H/1D + longShortRatio + OI
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import config
import indicators
from binance_client import BinanceFuturesClient
from scoring import CoinScore, score_coin

log = logging.getLogger("scanner")


class Scanner:
    def __init__(self, client: BinanceFuturesClient | None = None) -> None:
        self.client = client or BinanceFuturesClient()
        self._symbol_info: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------- prefilter
    def _load_symbol_info(self) -> dict[str, dict[str, Any]]:
        if not self._symbol_info:
            self._symbol_info = self.client.get_perpetual_usdt_symbols()
            log.info("Nap %d hop dong PERPETUAL USDT", len(self._symbol_info))
        return self._symbol_info

    def prefilter(
        self,
    ) -> tuple[list[str], dict[str, dict[str, float]], dict[str, float]]:
        """
        Loc so bo bang du lieu batch: chi giu coin du thanh khoan va dang tang gia.
        Tra ve (danh sach symbol, ticker_map, funding_map).
        """
        info = self._load_symbol_info()
        tickers = self.client.get_all_tickers_24h()
        fundings = self.client.get_all_funding_rates()

        # --- Che do quet TOAN BO coin (mac dinh) ---
        if config.SCAN_ALL_SYMBOLS:
            symbols = [s for s in info if s in tickers][
                : config.MAX_SYMBOLS_PER_SCAN
            ]
            est_weight = len(symbols) * 3 + 51
            log.info(
                "Quet TOAN BO %d/%d coin PERPETUAL USDT"
                " (uoc tinh ~%d weight, tran %d/phut)",
                len(symbols), len(info), est_weight, config.MAX_WEIGHT_PER_MINUTE,
            )
            return symbols, tickers, fundings

        # --- Che do loc so bo (tiet kiem request) ---
        candidates: list[tuple[str, float]] = []
        for symbol in info:
            t = tickers.get(symbol)
            if not t:
                continue
            if t["quote_volume_24h"] < config.MIN_QUOTE_VOLUME_24H:
                continue
            if t["price_change_pct_24h"] < config.MIN_PRICE_CHANGE_24H:
                continue
            candidates.append((symbol, t["price_change_pct_24h"]))

        # uu tien coin tang nong nhat neu vuot tran MAX_SYMBOLS_PER_SCAN
        candidates.sort(key=lambda x: x[1], reverse=True)
        symbols = [s for s, _ in candidates[: config.MAX_SYMBOLS_PER_SCAN]]

        log.info(
            "Prefilter: %d/%d coin (vol>=%s USDT, 24h>=%.1f%%)",
            len(symbols),
            len(info),
            f"{config.MIN_QUOTE_VOLUME_24H:,.0f}",
            config.MIN_PRICE_CHANGE_24H,
        )
        return symbols, tickers, fundings

    # ------------------------------------------------------------ per symbol
    def fetch_metrics(
        self, symbol: str, ticker: dict[str, float], funding: float | None
    ) -> dict[str, Any] | None:
        """Lay day du chi bao cho 1 coin. None neu thieu du lieu quan trong."""
        # limit=100 -> weight 1/request (limit>100 se ton gap 4 lan).
        # 100 nen van du xa cho RSI 6/12/24 + volume trung binh 20 nen.
        n = config.KLINES_LIMIT
        try:
            kl_15m = self.client.get_klines(symbol, "15m", limit=n)
            kl_4h = self.client.get_klines(symbol, "4h", limit=n)
            kl_1d = self.client.get_klines(symbol, "1d", limit=n)
        except RuntimeError as exc:
            log.debug("%s: khong lay duoc klines (%s)", symbol, exc)
            return None

        ohlc_15m = indicators.klines_to_ohlc(kl_15m)
        ohlc_4h = indicators.klines_to_ohlc(kl_4h)
        ohlc_1d = indicators.klines_to_ohlc(kl_1d)

        # Chu ky RSI theo preset (SCREENSHOT: 6/12/24, PDF: 14/14/14)
        p = config.RSI_PERIODS
        rsi_15m = indicators.rsi(ohlc_15m["close"], p["15m"])
        rsi_4h = indicators.rsi(ohlc_4h["close"], p["4h"])
        rsi_1d = indicators.rsi(ohlc_1d["close"], p["1d"])
        if rsi_15m is None or rsi_4h is None or rsi_1d is None:
            return None  # coin moi list, chua du nen

        long_ratio = self.client.get_long_short_account_ratio(symbol, "15m", 1)
        oi_stats = self.client.get_open_interest_stats(symbol, "15m")

        spike, spike_time = indicators.spike_with_time(ohlc_15m, bars=1)
        wick, wick_time = indicators.upper_wick_with_time(ohlc_15m)

        return {
            "symbol": symbol,
            "price": ticker.get("last_price"),
            "price_change_pct_24h": ticker.get("price_change_pct_24h"),
            "price_change_pct_1h": indicators.price_change_pct(ohlc_15m, bars=4),
            "quote_volume_24h": ticker.get("quote_volume_24h"),
            "volume_ratio": indicators.volume_ratio(ohlc_15m, lookback=20),
            "rsi_15m": rsi_15m,
            "rsi_4h": rsi_4h,
            "rsi_1d": rsi_1d,
            "rsi_periods": p,
            "long_ratio": long_ratio,
            "spike": spike,
            "spike_time": spike_time,
            "spike_2bar": indicators.spike_pct(ohlc_15m, bars=2),
            "oi_change": None if oi_stats is None else oi_stats["change_pct"],
            "oi_value_from": None if oi_stats is None else oi_stats["value_from"],
            "oi_value_to": None if oi_stats is None else oi_stats["value_to"],
            "oi_periods": (
                config.F4_OI_LOOKBACK_15M_BARS
                if oi_stats is None
                else int(oi_stats["periods"])
            ),
            "upper_wick": wick,
            "upper_wick_time": wick_time,
            "funding": funding,
        }

    # ----------------------------------------------------------------- scan
    def scan_all(self) -> list[CoinScore]:
        """
        Chay 1 vong quet va cham diem TAT CA coin ung vien (khong loc theo diem).
        Nho vay caller co the loc theo nhieu tieu chi khac nhau:
          - console/CSV: theo diem >= MIN_SCORE
          - Telegram   : theo so tieu chi PASS >= TELEGRAM_MIN_PASSED_FILTERS
        """
        symbols, tickers, fundings = self.prefilter()
        if not symbols:
            return []

        results: list[CoinScore] = []
        info = self._load_symbol_info()
        total = len(symbols)
        done = failed = 0
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
            futures = {
                pool.submit(
                    self.fetch_metrics, s, tickers.get(s, {}), fundings.get(s)
                ): s
                for s in symbols
            }
            for fut in as_completed(futures):
                symbol = futures[fut]
                done += 1
                # Bao tien do moi 100 coin (quet 524 coin mat ~30-60s)
                if total > 100 and done % 100 == 0:
                    log.info(
                        "  ... %d/%d coin (%.0fs, weight %d/%d)",
                        done, total, time.time() - t0,
                        self.client.limiter.used, config.MAX_WEIGHT_PER_MINUTE,
                    )
                try:
                    metrics = fut.result()
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    log.debug("%s: loi khi fetch (%s)", symbol, exc)
                    continue
                if not metrics:
                    failed += 1
                    continue

                cs = score_coin(symbol, metrics)

                # Entry/SL/TP theo cong thuc PDF, lam tron theo tick size
                meta = info.get(symbol, {})
                tick = meta.get("tickSize")
                precision = meta.get("pricePrecision", 6)
                levels = indicators.compute_entry_sl_tp(cs.price)
                cs.levels = {
                    k: indicators.round_to_tick(v, tick, precision)
                    for k, v in levels.items()
                }
                results.append(cs)

        results.sort(key=lambda c: c.total_score, reverse=True)
        log.info(
            "Cham diem xong %d/%d coin trong %.0fs (weight da dung %d/%d)%s",
            len(results), total, time.time() - t0,
            self.client.limiter.used, config.MAX_WEIGHT_PER_MINUTE,
            f", {failed} coin thieu du lieu" if failed else "",
        )
        return results

    def scan(self, min_score: float | None = None) -> list[CoinScore]:
        """Quet va chi tra ve coin co diem >= min_score (giu tuong thich nguoc)."""
        threshold = config.MIN_SCORE if min_score is None else min_score
        all_results = self.scan_all()
        results = [
            c for c in all_results
            if c.total_score >= threshold
            and not (config.REQUIRE_MANDATORY_PASS and c.failed_mandatory)
        ]
        log.info("Co %d coin dat >= %.0f diem", len(results), threshold)
        return results

    def telegram_candidates(self, all_results: list[CoinScore]) -> list[CoinScore]:
        """
        Loc coin du dieu kien day Telegram: it nhat N tieu chi PASS trong F1-F6.
        Sap xep uu tien: nhieu PASS truoc, roi den diem cao.
        """
        min_pass = config.TELEGRAM_MIN_PASSED_FILTERS
        require_any = set(config.TELEGRAM_REQUIRE_ANY_OF or ())

        picked: list[CoinScore] = []
        for c in all_results:
            if c.passed_count < min_pass:
                continue
            if (
                config.TELEGRAM_ALSO_REQUIRE_MIN_SCORE
                and c.total_score < config.MIN_SCORE
            ):
                continue
            if c.total_score < config.TELEGRAM_MIN_SCORE_FLOOR:
                continue
            if require_any:
                passed_codes = {f.code for f in c.filters if f.passed}
                if not (passed_codes & require_any):
                    continue
            picked.append(c)

        # --- Sap xep uu tien: coin manh nhat len dau ---
        mode = config.TELEGRAM_SORT_MODE
        if mode == "SCORE":
            key = lambda c: c.total_score  # noqa: E731
        elif mode == "SCORE_THEN_PASS":
            key = lambda c: (c.total_score, c.passed_count)  # noqa: E731
        else:  # PASS_THEN_SCORE (mac dinh)
            # Uu tien setup dat chuan SHORT (PASS het 6) len tren cung, sau do
            # nhieu tieu chi PASS, roi den diem cao, cuoi cung trap risk thap.
            key = lambda c: (  # noqa: E731
                c.passed_count,
                c.total_score,
                -c.trap_risk,
            )
        picked.sort(key=key, reverse=True)

        # Gan so thu tu de tin nhan biet coin nao manh nhat vong quet
        for i, c in enumerate(picked, start=1):
            c.rank = i
            c.rank_total = len(picked)
            c.scanned_total = len(all_results)

        log.info(
            "Telegram: %d/%d coin du dieu kien (>= %d tieu chi PASS%s%s), sap xep %s",
            len(picked), len(all_results), min_pass,
            f", score >= {config.TELEGRAM_MIN_SCORE_FLOOR:.0f}"
            if config.TELEGRAM_MIN_SCORE_FLOOR > 0 else "",
            f", phai PASS 1 trong {'/'.join(sorted(require_any))}"
            if require_any else "",
            mode,
        )
        if picked:
            top = picked[0]
            log.info(
                "  Manh nhat: %s (%d/6 PASS, %.1f/100, %s %s)",
                top.symbol, top.passed_count, top.total_score,
                top.grade, top.action,
            )
        return picked
