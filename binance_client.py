"""
Client goi cac public REST endpoint cua Binance USDT-M Futures (fapi).
Khong can API key vi chi doc du lieu thi truong.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests

import config

log = logging.getLogger("binance")


class WeightLimiter:
    """
    Theo doi weight da dung trong 1 phut (doc tu header x-mbx-used-weight-1m).
    Khi sap cham tran, cac luong se cho den dau phut tiep theo.
    Nho vay quet duoc toan bo 524 coin ma khong bi Binance ban IP (418).
    """

    def __init__(self, max_per_minute: int | None = None) -> None:
        self.max_per_minute = max_per_minute or config.MAX_WEIGHT_PER_MINUTE
        self._used = 0
        self._window_start = time.time()
        self._lock = threading.Lock()

    def acquire(self, cost: int = 1) -> None:
        """Cho neu vuot han muc weight cua phut hien tai."""
        while True:
            with self._lock:
                now = time.time()
                if now - self._window_start >= 60:
                    self._window_start = now
                    self._used = 0
                if self._used + cost <= self.max_per_minute:
                    self._used += cost
                    return
                wait = 60 - (now - self._window_start) + 0.5
            log.warning(
                "Sap cham tran weight (%d/%d), cho %.1fs sang phut moi",
                self._used, self.max_per_minute, wait,
            )
            time.sleep(max(0.1, wait))

    def sync(self, used_weight: str | None) -> None:
        """Dong bo voi so weight that ma Binance bao ve trong header."""
        if not used_weight:
            return
        try:
            real = int(used_weight)
        except (TypeError, ValueError):
            return
        with self._lock:
            # Binance la nguon dung nhat -> lay so lon hon
            if real > self._used:
                self._used = real

    @property
    def used(self) -> int:
        with self._lock:
            return self._used


class BinanceFuturesClient:
    """Wrapper co retry / backoff cho fapi.binance.com."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or config.FAPI_BASE).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "F1F6-ShortScanner/1.0"})
        # Dung chung 1 bo dem weight cho moi luong
        self.limiter = WeightLimiter()

    # ------------------------------------------------------------------ core
    def _get(
        self, path: str, params: dict[str, Any] | None = None, weight: int = 1
    ) -> Any:
        url = f"{self.base_url}{path}"
        last_err: Exception | None = None

        # /futures/data/* nam o pool rate limit rieng, khong tinh vao 2400/phut
        counted = not path.startswith("/futures/data/")

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                if counted:
                    self.limiter.acquire(weight)
                resp = self.session.get(
                    url, params=params, timeout=config.REQUEST_TIMEOUT
                )
                if counted:
                    self.limiter.sync(resp.headers.get("x-mbx-used-weight-1m"))
                # 429/418: bi rate limit -> cho lau hon roi thu lai
                if resp.status_code in (429, 418):
                    wait = config.RETRY_BACKOFF ** attempt * 5
                    log.warning(
                        "Rate limit %s tren %s, cho %.1fs", resp.status_code, path, wait
                    )
                    time.sleep(wait)
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    continue
                resp.raise_for_status()
                if config.THROTTLE_SECONDS:
                    time.sleep(config.THROTTLE_SECONDS)
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - gom moi loi mang
                last_err = exc
                if attempt < config.MAX_RETRIES:
                    time.sleep(config.RETRY_BACKOFF ** attempt)

        raise RuntimeError(
            f"GET {path} that bai sau {config.MAX_RETRIES} lan: {last_err}"
        )

    # ------------------------------------------------------------- batch call
    def get_perpetual_usdt_symbols(self) -> dict[str, dict[str, Any]]:
        """{symbol: {pricePrecision, tickSize}} cho hop dong PERPETUAL USDT dang TRADING."""
        data = self._get("/fapi/v1/exchangeInfo", weight=1)
        out: dict[str, dict[str, Any]] = {}
        for s in data.get("symbols", []):
            if (
                s.get("contractType") != "PERPETUAL"
                or s.get("quoteAsset") != "USDT"
                or s.get("status") != "TRADING"
            ):
                continue
            symbol = s["symbol"]
            if any(k in symbol for k in config.EXCLUDE_SYMBOL_KEYWORDS):
                continue
            if config.EXCLUDE_NON_ASCII_SYMBOLS and not symbol.isascii():
                continue  # vd "龙虾USDT" - hop dong meme ten non-ASCII
            tick = None
            for f in s.get("filters", []):
                if f.get("filterType") == "PRICE_FILTER":
                    tick = float(f["tickSize"])
                    break
            out[symbol] = {
                "pricePrecision": int(s.get("pricePrecision", 4)),
                "tickSize": tick,
            }
        return out

    def get_all_tickers_24h(self) -> dict[str, dict[str, float]]:
        """1 request cho ca san: %thay doi 24h, gia hien tai, volume quote 24h."""
        # Khong truyen symbol -> weight 40
        data = self._get("/fapi/v1/ticker/24hr", weight=40)
        out: dict[str, dict[str, float]] = {}
        for t in data:
            try:
                out[t["symbol"]] = {
                    "price_change_pct_24h": float(t["priceChangePercent"]),
                    "last_price": float(t["lastPrice"]),
                    "quote_volume_24h": float(t["quoteVolume"]),
                    "high_24h": float(t["highPrice"]),
                }
            except (KeyError, ValueError, TypeError):
                continue
        return out

    def get_all_funding_rates(self) -> dict[str, float]:
        """1 request cho ca san: funding rate hien tai, doi ra % (vd -0.15)."""
        # Khong truyen symbol -> weight 10
        data = self._get("/fapi/v1/premiumIndex", weight=10)
        out: dict[str, float] = {}
        for item in data:
            try:
                out[item["symbol"]] = float(item["lastFundingRate"]) * 100.0
            except (KeyError, ValueError, TypeError):
                continue
        return out

    # ------------------------------------------------------- per-symbol call
    def get_klines(
        self, symbol: str, interval: str, limit: int | None = None
    ) -> list[list[Any]]:
        """
        Lay nen. Weight phu thuoc limit:
          limit <= 100 -> 1 | 101-500 -> 2 | 501-1000 -> 5 | >1000 -> 10
        Mac dinh dung config.KLINES_LIMIT = 100 de weight chi la 1.
        """
        n = limit or config.KLINES_LIMIT
        if n <= 100:
            w = 1
        elif n <= 500:
            w = 2
        elif n <= 1000:
            w = 5
        else:
            w = 10
        return self._get(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": n},
            weight=w,
        )

    def get_long_short_account_ratio(
        self, symbol: str, period: str = "15m", limit: int = 1
    ) -> float | None:
        """% tai khoan dang Long tren toan san (vd 65.0)."""
        try:
            data = self._get(
                "/futures/data/globalLongShortAccountRatio",
                {"symbol": symbol, "period": period, "limit": limit},
            )
        except RuntimeError:
            return None
        if not data:
            return None
        try:
            return float(data[-1]["longAccount"]) * 100.0
        except (KeyError, ValueError, TypeError):
            return None

    def get_open_interest_stats(
        self, symbol: str, period: str = "15m", lookback_bars: int | None = None
    ) -> dict[str, float] | None:
        """
        Thong ke Open Interest qua `lookback_bars` chu ky.
        Tra ve {change_pct, value_from, value_to, periods} trong do value_* la
        gia tri OI quy doi USD (sumOpenInterestValue) - dung cho "2.5M to 2.6M".
        """
        bars = (
            lookback_bars
            if lookback_bars is not None
            else config.F4_OI_LOOKBACK_15M_BARS
        )
        try:
            data = self._get(
                "/futures/data/openInterestHist",
                {"symbol": symbol, "period": period, "limit": bars + 1},
            )
        except RuntimeError:
            return None
        if not data or len(data) < 2:
            return None
        try:
            first = float(data[0]["sumOpenInterest"])
            last = float(data[-1]["sumOpenInterest"])
            val_first = float(data[0].get("sumOpenInterestValue") or 0.0)
            val_last = float(data[-1].get("sumOpenInterestValue") or 0.0)
        except (KeyError, ValueError, TypeError):
            return None
        if first <= 0:
            return None
        return {
            "change_pct": (last / first - 1.0) * 100.0,
            "value_from": val_first,
            "value_to": val_last,
            "periods": float(len(data) - 1),
        }

    def get_open_interest_change_pct(
        self, symbol: str, period: str = "15m", lookback_bars: int | None = None
    ) -> float | None:
        """% thay doi Open Interest (giu lai cho tuong thich nguoc)."""
        stats = self.get_open_interest_stats(symbol, period, lookback_bars)
        return None if stats is None else stats["change_pct"]
