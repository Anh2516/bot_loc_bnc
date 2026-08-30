"""
Gui canh bao Telegram theo dung dinh dang tin nhan cua bot goc (anh mau).

Dieu kien day tin: coin co it nhat config.TELEGRAM_MIN_PASSED_FILTERS (= 2)
tieu chi PASS trong F1-F6. Coin FAIL F1 hoac F6 -> nhan WAIT (theo PDF).

Dinh dang tin nhan (theo anh):
    MMisMyEx                                    Admin
    🔍 CHILLGUYUSDT · RSI 15m 70.0 4h 78.3 1D 67.8
    💲 0.01464  24h: +17.00%  1h: -0.28%  Vol: 0.6x
    L/S 68.5%  FR +0.005%  OI 2.6M
    ---------------------------------------------
    ❌ C · WAIT
    F1: PASS - ...; F2: PASS - ...; ...
    📌 <ket luan>
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests

import config
import indicators
from scoring import CoinScore

log = logging.getLogger("telegram")


# ---------------------------------------------------------------- cooldown
class SentTracker:
    """Ghi nho thoi diem gui gan nhat cua tung coin de tranh spam lai."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or config.TELEGRAM_STATE_FILE)
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._data = {}

    def _save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self._data, indent=1), encoding="utf-8"
            )
        except OSError as exc:
            log.debug("Khong luu duoc %s: %s", self.path, exc)

    def in_cooldown(self, symbol: str, minutes: int | None = None) -> bool:
        mins = config.TELEGRAM_COOLDOWN_MINUTES if minutes is None else minutes
        if mins <= 0:
            return False
        raw = self._data.get(symbol)
        if not raw:
            return False
        try:
            last = datetime.fromisoformat(raw)
        except ValueError:
            return False
        return datetime.now(timezone.utc) - last < timedelta(minutes=mins)

    def mark(self, symbol: str) -> None:
        self._data[symbol] = datetime.now(timezone.utc).isoformat()
        self._save()


class SubscriberStore:
    """
    Luu danh sach chat_id da gui /start cho bot.
    Nho vay khong can tim chat_id thu cong: ai muon nhan thong bao chi can /start.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or config.TELEGRAM_SUBSCRIBERS_FILE)
        self._ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._ids = {str(x) for x in data.get("chat_ids", [])}
        except (OSError, ValueError):
            self._ids = set()

    def _save(self) -> None:
        try:
            self.path.write_text(
                json.dumps({"chat_ids": sorted(self._ids)}, indent=1),
                encoding="utf-8",
            )
        except OSError as exc:
            log.debug("Khong luu duoc %s: %s", self.path, exc)

    def add(self, chat_id: str | int) -> bool:
        """Tra ve True neu la subscriber moi."""
        cid = str(chat_id)
        if cid in self._ids:
            return False
        self._ids.add(cid)
        self._save()
        log.info("Subscriber moi: %s (tong %d)", cid, len(self._ids))
        return True

    def remove(self, chat_id: str | int) -> bool:
        cid = str(chat_id)
        if cid not in self._ids:
            return False
        self._ids.discard(cid)
        self._save()
        return True

    def all(self) -> list[str]:
        """Danh sach chat_id nhan thong bao (gom ca TELEGRAM_CHAT_ID neu co)."""
        ids = set(self._ids)
        if config.TELEGRAM_CHAT_ID:
            ids.add(str(config.TELEGRAM_CHAT_ID))
        return sorted(ids)

    def __len__(self) -> int:
        return len(self.all())


# ----------------------------------------------------------------- helpers
def _signed(value: float | None, nd: int = 2, suffix: str = "%") -> str:
    """Format so co dau +/- (giong '24h: +17.00%', 'FR +0.005%')."""
    if value is None:
        return "n/a"
    return f"{value:+.{nd}f}{suffix}"


def _conclusion(coin: CoinScore) -> str:
    """
    Cau ket luan cuoi tin nhan (dong bat dau bang 📌 trong anh mau).
    Vi du anh: "OI did not increase sufficiently, failing F4, hence setup is
    not strong enough for a short."
    """
    if coin.action == "SHORT":
        return (
            f"Du {coin.passed_count}/6 tieu chi va PASS ca F1+F6"
            f" - setup SHORT dat chuan (Score {coin.total_score:.0f}/100,"
            f" Trap Risk {coin.trap_risk}/10)."
        )

    fails = coin.failed_codes
    lead = {
        "F1": "RSI chua qua mua dong thoi tren cac khung",
        "F2": "Long/Short ratio chua nghieng Long du manh",
        "F3": "Chua co spike nen 15m du manh",
        "F4": "OI did not increase sufficiently",
        "F5": "Chua thay rau nen tren / luc ban tu choi gia",
        "F6": "Funding am qua sau, thi truong da qua dong Short",
    }
    # Uu tien nhac bo loc bat buoc (F1/F6) neu chinh no FAIL
    order = [c for c in ("F1", "F6") if c in fails] or fails
    first = order[0] if order else ""
    reason = lead.get(first, "Chua du dieu kien")
    return (
        f"{reason}, failing {', '.join(fails)}, hence setup is not strong"
        f" enough for a short. ({coin.passed_count}/6 PASS,"
        f" Score {coin.total_score:.0f}/100)"
    )


def build_message(coin: CoinScore, header_name: str | None = None) -> str:
    """Dung noi dung HTML cho 1 coin theo dung layout anh mau."""
    m = coin.metrics
    name = header_name or config.TELEGRAM_HEADER_NAME
    p = m.get("rsi_periods") or config.RSI_PERIODS

    # Icon theo do manh cua setup (giong anh: 🔥 A+ SHORT)
    if coin.action == "SHORT":
        mark = "\U0001f525"          # 🔥 setup dat chuan
    elif coin.passed_count >= 5:
        mark = "\u26a0\ufe0f"        # ⚠️ sat chuan, thieu 1 tieu chi
    else:
        mark = "\u274c"              # ❌ chua du
    vol_ratio = m.get("volume_ratio")
    vol_txt = "n/a" if vol_ratio is None else f"{vol_ratio:.1f}x"
    oi_txt = indicators.format_compact(m.get("oi_value_to"))
    lr = m.get("long_ratio")
    lr_txt = "n/a" if lr is None else f"{lr:.1f}%"

    # Dong dau: ten hien thi + so thu tu uu tien trong vong quet
    header = f"<b>{escape(name)}</b>"
    if config.TELEGRAM_SHOW_RANK and coin.rank:
        header += (
            f"   <i>TOP #{coin.rank}"
            + (f"/{coin.rank_total}" if coin.rank_total else "")
            + "</i>"
        )
    if config.TELEGRAM_SHOW_SCAN_SUMMARY and coin.scanned_total:
        header += (
            f"\n<i>Da quet {coin.scanned_total} coin"
            f" \u00b7 {coin.rank_total} coin dat"
            f" &gt;= {config.TELEGRAM_MIN_PASSED_FILTERS}/6 tieu chi</i>"
        )

    # Khoi thong tin dau tin nhan
    lines = [
        header,
        (
            f"\U0001f50d <b>{escape(coin.symbol)}</b> \u00b7 RSI"
            f" 15m <b>{m.get('rsi_15m', 0):.1f}</b>"
            f" 4h <b>{m.get('rsi_4h', 0):.1f}</b>"
            f" 1D <b>{m.get('rsi_1d', 0):.1f}</b>"
            f"  <i>(RSI{p['15m']}/{p['4h']}/{p['1d']})</i>"
        ),
        (
            f"\U0001f4b2 <b>{indicators.format_price(m.get('price'))}</b>"
            f"  24h: <b>{_signed(m.get('price_change_pct_24h'))}</b>"
            f"  1h: <b>{_signed(m.get('price_change_pct_1h'))}</b>"
            f"  Vol: <b>{vol_txt}</b>"
        ),
        (
            f"L/S <b>{lr_txt}</b>"
            f"  FR <b>{_signed(m.get('funding'), 3)}</b>"
            f"  OI <b>{oi_txt}</b>"
        ),
        "",
        "\u2014" * 18,
        "",
        f"{mark} <b>{coin.grade}</b> \u00b7 <b>{coin.action}</b>",
        "",
    ]

    # --- Khoi Entry / SL / TP kem % lai-lo cua vi the SHORT (giong anh mau) ---
    if coin.levels:
        lines += _levels_block(coin)
        lines.append("")

    # Score /10 + Trap risk (giong "Score: 8/10 | Trap risk: 7/10" trong anh)
    score_txt = (
        f"<b>{coin.score_10}/10</b>"
        if config.TELEGRAM_SHOW_SCORE_10
        else f"<b>{coin.total_score:.0f}/100</b>"
    )
    lines.append(
        f"Score: {score_txt}  |  Trap risk: <b>{coin.trap_risk}/10</b>"
        f"  |  PASS <b>{coin.passed_count}/6</b>"
    )
    lines.append("")

    # Chi tiet F1-F6 (gop thanh 1 doan, phan cach bang ';' giong anh mau)
    parts = [
        f"<b>{f.code}: {'PASS' if f.passed else 'FAIL'}</b> \u2014 {escape(f.reason)}"
        for f in coin.filters
    ]
    lines.append("; ".join(parts))
    lines.append("")
    lines.append(f"\U0001f4cc {escape(_conclusion(coin))}")

    return "\n".join(lines)


def _levels_block(coin: CoinScore) -> list[str]:
    """
    Khoi Entry/SL/TP theo dung layout anh tin hieu goc:
        📍 Entry: 0.013297
        🔴 SL:    0.0135  (-1.5%)
        🎯 TP1:   0.0128  (+3.7%)
    % la lai-lo cua vi the SHORT: SL am, TP duong.
    """
    lv = coin.levels
    entry = lv.get("entry") or 0.0
    out = [f"\U0001f4cd Entry: <b>{lv.get('entry')}</b>"]

    def pnl(price: float | None) -> str:
        """% lai/lo cua vi the short khi gia chay tu entry ve price."""
        if not price or not entry:
            return ""
        return f"  <i>({(1 - price / entry) * 100:+.1f}%)</i>"

    out.append(f"\U0001f534 SL:  <b>{lv.get('sl')}</b>{pnl(lv.get('sl'))}")
    for i, key in enumerate(("tp1", "tp2", "tp3"), start=1):
        rr = ""
        if config.TP_R_MULTIPLES and i <= len(config.TP_R_MULTIPLES):
            rr = f" <i>{config.TP_R_MULTIPLES[i - 1]:g}R</i>"
        out.append(
            f"\U0001f3af TP{i}: <b>{lv.get(key)}</b>{pnl(lv.get(key))}{rr}"
        )
    return out


# ---------------------------------------------------------------- notifier
class TelegramNotifier:
    """Gui tin nhan Telegram, co cooldown va gioi han so tin moi vong quet."""

    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token if token is not None else config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id if chat_id is not None else config.TELEGRAM_CHAT_ID
        self.tracker = SentTracker()
        self.subscribers = SubscriberStore()
        self.session = requests.Session()

    @property
    def enabled(self) -> bool:
        """Co token la bat duoc; nguoi nhan lay tu /start hoac TELEGRAM_CHAT_ID."""
        return bool(self.token)

    @property
    def has_recipient(self) -> bool:
        return bool(self._recipients())

    def _recipients(self) -> list[str]:
        if self.chat_id:
            ids = set(self.subscribers.all()) | {str(self.chat_id)}
            return sorted(ids)
        return self.subscribers.all()

    def _send_to(
        self, chat_id: str, text: str, reply_to: int | None = None
    ) -> bool:
        """
        Gui 1 tin nhan den 1 chat_id, tu retry khi bi 429.
        reply_to: message_id can reply (dung trong nhom de biet tra loi ai).
        """
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_to:
            payload["reply_to_message_id"] = reply_to
            # Neu tin goc da bi xoa thi van gui binh thuong, khong bao loi
            payload["allow_sending_without_reply"] = True
        for attempt in (1, 2):
            try:
                resp = self.session.post(
                    url, json=payload, timeout=config.REQUEST_TIMEOUT
                )
                if resp.status_code == 429 and attempt == 1:
                    wait = resp.json().get("parameters", {}).get("retry_after", 5)
                    log.warning("Telegram 429, cho %ss", wait)
                    time.sleep(float(wait) + 1)
                    continue
                if resp.status_code in (400, 403):
                    # bot bi block / bi kick khoi nhom / chat khong ton tai
                    desc = ""
                    try:
                        desc = resp.json().get("description", "")
                    except ValueError:
                        pass

                    # Loi tam thoi (vd nhom vua doi sang supergroup) -> giu lai
                    if "upgraded to a supergroup" in desc:
                        log.warning("Chat %s da doi thanh supergroup: %s", chat_id, desc)
                        return False

                    log.warning(
                        "Chat %s tra ve %s (%s) -> bo khoi danh sach nhan tin",
                        chat_id, resp.status_code, desc or "?",
                    )
                    self.subscribers.remove(chat_id)
                    return False
                resp.raise_for_status()
                return True
            except Exception as exc:  # noqa: BLE001 - khong de bot chet vi Telegram
                log.warning("Gui Telegram cho %s that bai: %s", chat_id, exc)
                return False
        return False

    def _post(self, text: str) -> bool:
        """Gui tin nhan den TAT CA nguoi nhan. True neu it nhat 1 nguoi nhan duoc."""
        recipients = self._recipients()
        if not recipients:
            log.info(
                "Chua co nguoi nhan (chua ai /start va TELEGRAM_CHAT_ID trong)"
            )
            return False
        ok = False
        for cid in recipients:
            if self._send_to(cid, text):
                ok = True
        return ok

    def notify(self, coins: list[CoinScore], ignore_cooldown: bool = False) -> int:
        """
        Gui canh bao cho danh sach coin da duoc loc (>= N tieu chi PASS).
        Tra ve so tin nhan gui thanh cong.
        """
        if not self.enabled:
            log.info(
                "Chua cau hinh TELEGRAM_BOT_TOKEN -> bo qua Telegram"
                " (%d coin du dieu kien)", len(coins),
            )
            return 0
        if not self.has_recipient:
            log.warning(
                "Chua ai /start bot -> khong co nguoi nhan (%d coin du dieu kien)."
                " Hay mo Telegram, tim bot va gui /start.", len(coins),
            )
            return 0
        if not coins:
            return 0

        sent = 0
        limit = config.TELEGRAM_MAX_MESSAGES_PER_SCAN
        for coin in coins:
            if sent >= limit:
                log.info("Da dat gioi han %d tin nhan moi vong quet", limit)
                break
            if not ignore_cooldown and self.tracker.in_cooldown(coin.symbol):
                log.debug("%s dang trong cooldown, bo qua", coin.symbol)
                continue
            if self._post(build_message(coin)):
                self.tracker.mark(coin.symbol)
                sent += 1
                if config.TELEGRAM_SEND_DELAY:
                    time.sleep(config.TELEGRAM_SEND_DELAY)

        if sent:
            log.info("Da gui %d tin nhan Telegram", sent)
        return sent

    def send_text(self, text: str) -> bool:
        """Gui 1 tin nhan tu do (dung cho test ket noi)."""
        return self._post(text) if self.enabled else False

    def send_to_chat(
        self, chat_id: str | int, text: str, reply_to: int | None = None
    ) -> bool:
        """
        Gui tin nhan cho dung 1 chat (tra loi lenh /search, /top ...).
        reply_to: message_id de reply (dung trong nhom).
        """
        if not self.enabled:
            return False
        return self._send_to(str(chat_id), text, reply_to)


# ------------------------------------------------------- tin nhan /search
def _score_bar(score: float, max_score: float, width: int = 10) -> str:
    """Thanh tien do dang [#####-----] cho diem tung tieu chi."""
    if max_score <= 0:
        return ""
    filled = int(round(width * max(0.0, min(1.0, score / max_score))))
    return "\u2588" * filled + "\u2591" * (width - filled)


def build_search_message(coin: CoinScore) -> str:
    """
    Tin nhan tra loi lenh /search <coin>: chi tiet TUNG tieu chi F1-F6,
    diem tung phan / diem toi da, tong diem va Entry/SL/TP.
    """
    m = coin.metrics
    p = m.get("rsi_periods") or config.RSI_PERIODS
    vol_ratio = m.get("volume_ratio")
    lr = m.get("long_ratio")

    if coin.action == "SHORT":
        mark = "\U0001f525"          # 🔥
    elif coin.passed_count >= 5:
        mark = "\u26a0\ufe0f"        # ⚠️
    else:
        mark = "\u274c"              # ❌
    rank_txt = (
        f"  <i>(#{coin.rank} vong quet gan nhat)</i>"
        if config.TELEGRAM_SHOW_RANK and coin.rank else ""
    )
    lines = [
        f"\U0001f50d <b>{escape(coin.symbol)}</b> \u2014 CHI TIET F1-F6{rank_txt}",
        "",
        (
            f"\U0001f4b2 Gia <b>{indicators.format_price(m.get('price'))}</b>"
            f"  |  24h <b>{_signed(m.get('price_change_pct_24h'))}</b>"
            f"  |  1h <b>{_signed(m.get('price_change_pct_1h'))}</b>"
        ),
        (
            f"\U0001f4ca Vol 15m <b>"
            f"{'n/a' if vol_ratio is None else f'{vol_ratio:.1f}x'}</b>"
            f"  |  Vol 24h <b>"
            f"{indicators.format_compact(m.get('quote_volume_24h'))}</b>"
            f"  |  OI <b>{indicators.format_compact(m.get('oi_value_to'))}</b>"
        ),
        (
            f"\U0001f4c8 RSI{p['15m']}(15m) <b>{m.get('rsi_15m', 0):.2f}</b>"
            f"  RSI{p['4h']}(4h) <b>{m.get('rsi_4h', 0):.2f}</b>"
            f"  RSI{p['1d']}(1D) <b>{m.get('rsi_1d', 0):.2f}</b>"
        ),
        (
            f"\u2696\ufe0f L/S <b>{'n/a' if lr is None else f'{lr:.1f}%'}</b>"
            f"  |  Funding <b>{_signed(m.get('funding'), 4)}</b>"
        ),
        "",
        f"{mark} <b>KET QUA: {coin.total_score:.1f}/100</b>"
        + (f" <i>({coin.score_10}/10)</i>" if config.TELEGRAM_SHOW_SCORE_10 else "")
        + f"  \u00b7  Hang <b>{coin.grade}</b>"
        f"  \u00b7  <b>{coin.action}</b>",
        f"\u2705 PASS <b>{coin.passed_count}/6</b> tieu chi"
        f"  |  \U0001f3af Trap Risk <b>{coin.trap_risk}/10</b>",
        "",
        "\u2014" * 18,
        "",
    ]

    # Chi tiet tung bo loc, moi bo loc 1 khoi
    for f in coin.filters:
        icon = "\u2705" if f.passed else "\u274c"
        lines.append(
            f"{icon} <b>{f.code} \u00b7 {escape(f.name)}</b>"
            f"  <i>({escape(f.importance)})</i>"
        )
        lines.append(
            f"   {_score_bar(f.score, f.max_score)}"
            f"  <b>{f.score:.1f}/{f.max_score:.0f}</b> diem"
        )
        lines.append(f"   \u2192 {escape(f.reason)}")
        lines.append("")

    lines.append("\u2014" * 18)
    lines.append("")

    # Entry/SL/TP (% la lai-lo cua vi the SHORT)
    if coin.levels:
        if coin.action == "SHORT":
            lines.append("\U0001f525 <b>SETUP SHORT (du 6/6 tieu chi)</b>")
        else:
            lines.append(
                "\U0001f4d0 <b>Muc gia tham khao</b>"
                " <i>(chua du tieu chi - chi de theo doi)</i>"
            )
        lines += _levels_block(coin)
        lines.append("")

    lines.append(f"\U0001f4cc {escape(_conclusion(coin))}")
    return "\n".join(lines)
