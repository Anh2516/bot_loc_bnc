"""
Thread lang nghe lenh nguoi dung tren Telegram (long polling getUpdates).

Cac lenh ho tro:
  /start            - dang ky nhan thong bao tu dong moi 5 phut
  /stop             - huy dang ky
  /search <coin>    - soi chi tiet 1 coin: tung tieu chi F1-F6 + diem /100
  /top              - top coin nhieu tieu chi PASS nhat tu vong quet gan nhat
  /status           - trang thai bot va cau hinh dang dung
  /help             - huong dan
"""
from __future__ import annotations

import logging
import threading
import time
from html import escape

import config
import indicators
import telegram_notifier
from scanner import Scanner
from scoring import CoinScore, score_coin
from telegram_notifier import TelegramNotifier

log = logging.getLogger("tgbot")


class ScanCache:
    """Luu ket qua vong quet gan nhat de lenh /top, /status tra loi ngay."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.results: list[CoinScore] = []
        self.candidates: list[CoinScore] = []
        self.scan_time: str = "chua quet"
        self.scanned_count: int = 0

    def update(
        self,
        results: list[CoinScore],
        candidates: list[CoinScore],
        scan_time: str,
    ) -> None:
        with self._lock:
            self.results = list(results)
            self.candidates = list(candidates)
            self.scan_time = scan_time
            self.scanned_count = len(results)

    def snapshot(self) -> tuple[list[CoinScore], list[CoinScore], str, int]:
        with self._lock:
            return (
                list(self.results),
                list(self.candidates),
                self.scan_time,
                self.scanned_count,
            )


def normalize_symbol(raw: str) -> str:
    """
    Chuan hoa tu khoa nguoi dung thanh symbol Binance:
      btc / BTC / btcusdt / BTC-USDT / btc/usdt  ->  BTCUSDT
    """
    s = raw.strip().upper()
    for ch in (" ", "-", "/", "_", "$", "#"):
        s = s.replace(ch, "")
    if not s:
        return ""
    if not s.endswith("USDT"):
        s += "USDT"
    return s


class TelegramCommandBot:
    """Long polling getUpdates trong 1 thread rieng, xu ly lenh nguoi dung."""

    def __init__(
        self,
        notifier: TelegramNotifier,
        scanner: Scanner,
        cache: ScanCache,
    ) -> None:
        self.notifier = notifier
        self.scanner = scanner
        self.cache = cache
        self.session = notifier.session
        self.token = notifier.token
        self._offset: int | None = None
        self._stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.bot_username: str | None = None
        # Chong spam: thoi diem go lenh gan nhat cua tung user
        self._user_last_cmd: dict[int, float] = {}
        self._cooldown_lock = threading.Lock()

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if not self.token:
            log.warning("Chua co TELEGRAM_BOT_TOKEN -> khong lang nghe lenh")
            return
        self._load_bot_info()
        self._register_commands()
        self.thread = threading.Thread(
            target=self._loop, name="tg-commands", daemon=True
        )
        self.thread.start()
        log.info("Da bat thread lang nghe lenh Telegram (/search, /top, /status)")

    def stop(self) -> None:
        self._stop.set()

    def _load_bot_info(self) -> None:
        """Lay username cua bot + canh bao ve Privacy Mode khi dung trong nhom."""
        try:
            resp = self.session.get(
                f"https://api.telegram.org/bot{self.token}/getMe",
                timeout=config.REQUEST_TIMEOUT,
            )
            data = resp.json()
            if not data.get("ok"):
                return
            me = data["result"]
            self.bot_username = me.get("username")
            log.info(
                "Bot @%s | vao nhom: %s | doc moi tin nhan trong nhom: %s",
                self.bot_username,
                "CO" if me.get("can_join_groups") else "KHONG",
                "CO" if me.get("can_read_all_group_messages") else "KHONG (privacy ON)",
            )
            if not me.get("can_join_groups"):
                log.warning(
                    "Bot dang BI CHAN vao nhom! Vao @BotFather -> /mybots ->"
                    " chon bot -> Bot Settings -> Allow Groups -> Turn on."
                )
        except Exception as exc:  # noqa: BLE001
            log.debug("getMe loi: %s", exc)

    def _register_commands(self) -> None:
        """Dang ky menu lenh de Telegram goi y khi nguoi dung go '/'."""
        commands = [
            {"command": "start", "description": "Dang ky nhan canh bao moi 5 phut"},
            {"command": "search", "description": "Soi chi tiet 1 coin, vd /search btc"},
            {"command": "top", "description": "Top coin nhieu tieu chi PASS nhat"},
            {"command": "status", "description": "Trang thai va cau hinh bot"},
            {"command": "help", "description": "Huong dan su dung"},
            {"command": "stop", "description": "Huy nhan canh bao"},
        ]
        # Dang ky cho ca chat rieng va nhom de menu '/' hien ra o moi noi
        scopes = [
            {"type": "default"},
            {"type": "all_private_chats"},
            {"type": "all_group_chats"},
        ]
        for scope in scopes:
            try:
                self.session.post(
                    f"https://api.telegram.org/bot{self.token}/setMyCommands",
                    json={"commands": commands, "scope": scope},
                    timeout=config.REQUEST_TIMEOUT,
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("setMyCommands (%s) that bai: %s", scope["type"], exc)

    # ----------------------------------------------------------------- polling
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                updates = self._get_updates()
            except Exception as exc:  # noqa: BLE001 - loi mang thi thu lai
                log.debug("getUpdates loi: %s", exc)
                time.sleep(5)
                continue
            for upd in updates:
                try:
                    self._handle_update(upd)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Xu ly update loi: %s", exc)

    def _get_updates(self) -> list[dict]:
        params: dict[str, object] = {
            "timeout": config.TELEGRAM_POLL_TIMEOUT,
            # my_chat_member: biet khi bot duoc add / bi kick khoi nhom
            "allowed_updates": '["message","my_chat_member"]',
        }
        if self._offset is not None:
            params["offset"] = self._offset
        resp = self.session.get(
            f"https://api.telegram.org/bot{self.token}/getUpdates",
            params=params,
            timeout=config.TELEGRAM_POLL_TIMEOUT + 15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            return []
        updates = data.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    # ---------------------------------------------------------------- handlers
    def _handle_update(self, upd: dict) -> None:
        # Bot vua duoc add vao nhom / bi kick khoi nhom
        if "my_chat_member" in upd:
            self._handle_membership(upd["my_chat_member"])
            return

        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        text = (msg.get("text") or "").strip()
        if not chat_id or not text:
            return

        is_group = chat.get("type") in ("group", "supergroup")
        msg_id = msg.get("message_id")
        from_user = msg.get("from") or {}
        user_id = from_user.get("id")

        # Bo phan @ten_bot trong lenh khi dung trong group: /search@my_bot btc
        parts = text.split()
        cmd = parts[0].lower()
        mentioned: str | None = None
        if "@" in cmd:
            cmd, mentioned = cmd.split("@", 1)
        args = parts[1:]

        # Nhom co nhieu bot: lenh ghi ro @ten_bot khac thi khong phai cua minh
        if mentioned and self.bot_username and mentioned != self.bot_username.lower():
            return

        who = from_user.get("first_name") or from_user.get("username") or "?"
        where = f'nhom "{chat.get("title")}"' if is_group else "chat rieng"
        log.info("Lenh tu %s (%s) trong %s: %s", who, user_id, where, text[:60])

        # Tin nhan thuong (khong bat dau bang '/')
        if not cmd.startswith("/"):
            # Trong nhom KHONG coi tin nhan thuong la ten coin, neu khong bot se
            # tra loi moi cau chat cua moi nguoi -> spam.
            if is_group and config.TELEGRAM_PLAIN_TEXT_PRIVATE_ONLY:
                return
            if not self._check_user_cooldown(user_id):
                return
            self._auto_subscribe(chat_id, is_group, cmd)
            self._cmd_search(chat_id, parts, msg_id, is_group, from_user)
            return

        if not self._check_user_cooldown(user_id):
            return

        # Ai tuong tac voi bot thi tu dong nhan canh bao (tru khi go /stop)
        self._auto_subscribe(chat_id, is_group, cmd)

        if cmd in ("/start", "/dangky"):
            self._cmd_start(chat_id, msg_id, is_group, from_user)
        elif cmd in ("/stop", "/huy"):
            self._cmd_stop(chat_id, msg_id, is_group, from_user)
        elif cmd in ("/search", "/s", "/coin"):
            self._cmd_search(chat_id, args, msg_id, is_group, from_user)
        elif cmd in ("/top", "/list"):
            self._cmd_top(chat_id, msg_id, is_group, from_user)
        elif cmd in ("/status", "/info"):
            self._cmd_status(chat_id, msg_id, is_group, from_user)
        elif cmd in ("/help", "/huongdan"):
            self._reply(chat_id, self._help_text(is_group), msg_id, is_group, from_user)
        else:
            self._reply(
                chat_id,
                f"Khong hieu lenh <code>{escape(cmd)}</code>.\n\n"
                + self._help_text(is_group),
                msg_id, is_group, from_user,
            )

    def _send(self, chat_id: int | str, text: str) -> None:
        self.notifier.send_to_chat(chat_id, text)

    def _reply(
        self,
        chat_id: int | str,
        text: str,
        msg_id: int | None = None,
        is_group: bool = False,
        from_user: dict | None = None,
    ) -> None:
        """
        Tra loi 1 lenh. Trong nhom se reply vao tin goc + tag nguoi hoi
        de moi nguoi biet bot dang tra loi ai.
        """
        reply_to = None
        if is_group:
            prefix = self._mention(from_user)
            if prefix:
                text = f"{prefix}\n{text}"
            if config.TELEGRAM_REPLY_IN_GROUP:
                reply_to = msg_id
        self.notifier.send_to_chat(chat_id, text, reply_to)

    # ------------------------------------------------------------- group utils
    def _handle_membership(self, member: dict) -> None:
        """Xu ly khi bot duoc add vao nhom hoac bi kick ra."""
        chat = member.get("chat") or {}
        chat_id = chat.get("id")
        status = (member.get("new_chat_member") or {}).get("status")
        title = chat.get("title") or chat.get("first_name") or "?"
        if not chat_id:
            return

        if status in ("member", "administrator"):
            log.info('Bot duoc add vao "%s" (%s) voi quyen %s', title, chat_id, status)
            if config.TELEGRAM_AUTO_SUBSCRIBE_GROUP:
                self.notifier.subscribers.add(chat_id)
            is_group = chat.get("type") in ("group", "supergroup")
            if is_group:
                self._send(chat_id, self._welcome_group_text(title))
        elif status in ("left", "kicked"):
            log.info('Bot bi go khoi "%s" (%s)', title, chat_id)
            self.notifier.subscribers.remove(chat_id)

    def _auto_subscribe(self, chat_id: int, is_group: bool, cmd: str) -> None:
        """Tu dong dang ky chat/nhom vao danh sach nhan canh bao."""
        if cmd in ("/stop", "/huy"):
            return
        if is_group and not config.TELEGRAM_AUTO_SUBSCRIBE_GROUP:
            return
        if not is_group and not config.TELEGRAM_AUTO_SUBSCRIBE:
            return
        if self.notifier.subscribers.add(chat_id):
            log.info("Tu dong dang ky %s vao danh sach nhan canh bao", chat_id)

    def _check_user_cooldown(self, user_id: int | None) -> bool:
        """True neu duoc xu ly lenh; False neu nguoi dung go qua nhanh (chong spam)."""
        secs = config.TELEGRAM_USER_COOLDOWN_SECONDS
        if secs <= 0 or user_id is None:
            return True
        now = time.time()
        with self._cooldown_lock:
            if now - self._user_last_cmd.get(user_id, 0.0) < secs:
                log.debug("User %s go lenh qua nhanh -> bo qua", user_id)
                return False
            self._user_last_cmd[user_id] = now
            if len(self._user_last_cmd) > 500:  # don cache
                cutoff = now - max(secs * 10, 60)
                self._user_last_cmd = {
                    k: v for k, v in self._user_last_cmd.items() if v > cutoff
                }
        return True

    def _is_group_admin(self, chat_id: int, user_id: int | None) -> bool:
        """Kiem tra user co phai admin/owner cua nhom."""
        if user_id is None:
            return False
        try:
            resp = self.session.get(
                f"https://api.telegram.org/bot{self.token}/getChatMember",
                params={"chat_id": chat_id, "user_id": user_id},
                timeout=config.REQUEST_TIMEOUT,
            )
            data = resp.json()
            if not data.get("ok"):
                return False
            return data["result"].get("status") in ("creator", "administrator")
        except Exception as exc:  # noqa: BLE001
            log.debug("getChatMember loi: %s", exc)
            return False

    @staticmethod
    def _mention(from_user: dict | None) -> str:
        """Tag nguoi go lenh (hoat dong ca khi ho khong co username)."""
        if not from_user or not config.TELEGRAM_MENTION_USER_IN_GROUP:
            return ""
        uid = from_user.get("id")
        name = from_user.get("first_name") or from_user.get("username") or "ban"
        if not uid:
            return ""
        return f'<a href="tg://user?id={uid}">{escape(str(name))}</a>'

    def _welcome_group_text(self, title: str) -> str:
        """Tin nhan chao khi bot vua duoc add vao nhom."""
        at = f"@{self.bot_username}" if self.bot_username else ""
        return (
            f"\U0001f44b <b>Xin chao nhom {escape(str(title))}!</b>\n\n"
            f"Bot quet Binance Futures moi"
            f" <b>{config.SCAN_INTERVAL_SECONDS // 60} phut</b> va gui canh bao"
            f" cho moi coin co <b>&gt;= {config.TELEGRAM_MIN_PASSED_FILTERS}/6"
            f" tieu chi F1-F6 PASS</b>.\n\n"
            f"\u2705 Nhom nay da duoc dang ky nhan canh bao tu dong.\n\n"
            + self._help_text(is_group=True)
            + (
                f"\n\n\u26a0\ufe0f <b>Luu y:</b> trong nhom hay go lenh kem"
                f" <code>{at}</code> (vd <code>/search{at} btc</code>)"
                f" neu bot khong phan hoi."
                if at else ""
            )
        )

    # ------------------------------------------------------------ /start /stop
    def _cmd_start(
        self,
        chat_id: int,
        msg_id: int | None = None,
        is_group: bool = False,
        from_user: dict | None = None,
    ) -> None:
        is_new = self.notifier.subscribers.add(chat_id)
        target = "Nhom nay" if is_group else "Ban"
        head = (
            f"\U0001f7e2 <b>{target} da dang ky thanh cong!</b>"
            if is_new
            else f"\u2139\ufe0f <b>{target} da dang ky truoc do.</b>"
        )
        self._reply(
            chat_id,
            f"{head}\n\n"
            f"Bot quet Binance Futures moi"
            f" <b>{config.SCAN_INTERVAL_SECONDS // 60} phut</b> va gui canh bao"
            f" cho moi coin co <b>&gt;= {config.TELEGRAM_MIN_PASSED_FILTERS}/6"
            f" tieu chi F1-F6 PASS</b>.\n\n"
            + self._help_text(is_group),
            msg_id, is_group, from_user,
        )

    def _cmd_stop(
        self,
        chat_id: int,
        msg_id: int | None = None,
        is_group: bool = False,
        from_user: dict | None = None,
    ) -> None:
        # Trong nhom: chi admin duoc tat canh bao cua ca nhom
        if is_group and config.TELEGRAM_GROUP_ADMIN_ONLY_STOP:
            uid = (from_user or {}).get("id")
            if not self._is_group_admin(chat_id, uid):
                self._reply(
                    chat_id,
                    "\U0001f512 Chi <b>admin cua nhom</b> moi duoc dung"
                    " <code>/stop</code> (vi no tat canh bao cho ca nhom).\n\n"
                    "\U0001f4a1 Muon tu tat rieng minh: chat rieng voi bot"
                    " va go <code>/stop</code> o do.",
                    msg_id, is_group, from_user,
                )
                return

        removed = self.notifier.subscribers.remove(chat_id)
        target = "Nhom nay" if is_group else "Ban"
        self._reply(
            chat_id,
            f"\U0001f534 <b>{target} da huy nhan canh bao tu dong.</b>\n"
            "Gui /start de dang ky lai.\n\n"
            "\u2139\ufe0f Cac lenh <code>/search</code>, <code>/top</code>,"
            " <code>/status</code> <b>van dung binh thuong</b>."
            if removed
            else f"{target} chua dang ky nhan canh bao. Gui /start de dang ky.",
            msg_id, is_group, from_user,
        )

    # ------------------------------------------------------------- /search
    def _cmd_search(
        self,
        chat_id: int,
        args: list[str],
        msg_id: int | None = None,
        is_group: bool = False,
        from_user: dict | None = None,
    ) -> None:
        at = f"@{self.bot_username}" if (is_group and self.bot_username) else ""
        if not args:
            self._reply(
                chat_id,
                "\u2753 Thieu ten coin.\n\n"
                f"Cach dung: <code>/search{at} btc</code>,"
                f" <code>/search{at} kgen</code>,"
                f" <code>/search{at} chillguyusdt</code>",
                msg_id, is_group, from_user,
            )
            return

        symbol = normalize_symbol(args[0])

        # Trong nhom khong gui tin "dang lay du lieu" de bot khong lam nhieu chat
        if not is_group or config.TELEGRAM_GROUP_SHOW_LOADING:
            self._reply(
                chat_id,
                f"\u23f3 Dang lay du lieu <b>{escape(symbol)}</b>...",
                msg_id, is_group, from_user,
            )

        try:
            coin = self._score_symbol(symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning("/search %s loi: %s", symbol, exc)
            self._reply(
                chat_id,
                f"\u26a0\ufe0f Loi khi lay du lieu <b>{escape(symbol)}</b>: "
                f"<code>{escape(str(exc)[:200])}</code>",
                msg_id, is_group, from_user,
            )
            return

        if coin is None:
            self._reply(
                chat_id, self._not_found_text(symbol, at), msg_id, is_group, from_user
            )
            return

        self._reply(
            chat_id,
            telegram_notifier.build_search_message(coin),
            msg_id, is_group, from_user,
        )

    def _score_symbol(self, symbol: str) -> CoinScore | None:
        """Lay du lieu + cham diem 1 coin theo yeu cau (khong qua prefilter)."""
        info = self.scanner._load_symbol_info()
        if symbol not in info:
            return None

        tickers = self.scanner.client.get_all_tickers_24h()
        if symbol not in tickers:
            return None
        fundings = self.scanner.client.get_all_funding_rates()

        metrics = self.scanner.fetch_metrics(
            symbol, tickers[symbol], fundings.get(symbol)
        )
        if not metrics:
            return None

        coin = score_coin(symbol, metrics)
        meta = info.get(symbol, {})
        coin.levels = {
            k: indicators.round_to_tick(
                v, meta.get("tickSize"), meta.get("pricePrecision", 6)
            )
            for k, v in indicators.compute_entry_sl_tp(coin.price).items()
        }
        return coin

    def _not_found_text(self, symbol: str, at: str = "") -> str:
        """Bao khong tim thay + goi y cac symbol gan giong."""
        info = self.scanner._load_symbol_info()
        base = symbol.replace("USDT", "")
        suggestions = [s for s in info if base and base in s][:8]
        if not suggestions and len(base) >= 2:
            suggestions = [s for s in info if s.startswith(base[:2])][:8]

        text = (
            f"\u274c Khong tim thay <b>{escape(symbol)}</b> trong danh sach"
            f" hop dong PERPETUAL USDT tren Binance Futures."
        )
        if suggestions:
            text += "\n\n\U0001f4a1 Co phai ban tim:\n" + "\n".join(
                f"\u2022 <code>/search{at} {escape(s)}</code>" for s in suggestions
            )
        return text

    # ---------------------------------------------------------------- /top
    def _cmd_top(
        self,
        chat_id: int,
        msg_id: int | None = None,
        is_group: bool = False,
        from_user: dict | None = None,
    ) -> None:
        at = f"@{self.bot_username}" if (is_group and self.bot_username) else ""
        _, candidates, scan_time, scanned = self.cache.snapshot()
        if not candidates:
            self._reply(
                chat_id,
                "\u23f3 Chua co ket qua quet nao (hoac vong quet gan nhat khong"
                " co coin nao du dieu kien). Thu lai sau vai phut.",
                msg_id, is_group, from_user,
            )
            return

        limit = config.TELEGRAM_SEARCH_TOP_LIMIT
        lines = [
            f"\U0001f3c6 <b>TOP {min(limit, len(candidates))} COIN</b>"
            f" (&gt;= {config.TELEGRAM_MIN_PASSED_FILTERS}/6 tieu chi PASS)",
            f"<i>Vong quet {escape(scan_time)} \u00b7 {scanned} coin da cham diem</i>",
            "",
        ]
        for i, c in enumerate(candidates[:limit], start=1):
            passed = ",".join(f.code for f in c.filters if f.passed)
            icon = "\U0001f534" if c.action == "SHORT" else "\u274c"
            lines.append(
                f"{i}. {icon} <b>{escape(c.symbol)}</b>"
                f" \u00b7 <b>{c.passed_count}/6</b> PASS"
                f" \u00b7 <b>{c.total_score:.0f}</b>/100 ({c.grade})"
            )
            lines.append(
                f"    PASS: {passed or '-'}"
                f"  |  <code>/search{at} {escape(c.symbol)}</code>"
            )
        lines.append("")
        lines.append(
            f"\U0001f4a1 Go <code>/search{at} &lt;ten coin&gt;</code> de xem"
            " chi tiet tung tieu chi."
        )
        self._reply(chat_id, "\n".join(lines), msg_id, is_group, from_user)

    # -------------------------------------------------------------- /status
    def _cmd_status(
        self,
        chat_id: int,
        msg_id: int | None = None,
        is_group: bool = False,
        from_user: dict | None = None,
    ) -> None:
        _, candidates, scan_time, scanned = self.cache.snapshot()
        p = config.RSI_PERIODS
        require_any = config.TELEGRAM_REQUIRE_ANY_OF or ()
        subscribed = str(chat_id) in self.notifier.subscribers.all()
        lines = [
            "\u2699\ufe0f <b>TRANG THAI BOT</b>",
            "",
            f"\U0001f4cd Chat nay: <b>"
            f"{'DANG nhan canh bao' if subscribed else 'KHONG nhan canh bao'}</b>"
            f" ({'nhom' if is_group else 'chat rieng'})",
            f"\U0001f501 Chu ky quet: <b>{config.SCAN_INTERVAL_SECONDS // 60}"
            f" phut</b>",
            f"\U0001f552 Vong quet gan nhat: <b>{escape(scan_time)}</b>",
            f"\U0001f4ca Coin da cham diem: <b>{scanned}</b>",
            f"\U0001f514 Coin du dieu kien canh bao: <b>{len(candidates)}</b>",
            f"\U0001f465 Nguoi dang nhan tin: <b>"
            f"{len(self.notifier.subscribers)}</b>",
            "",
            "<b>Cau hinh tieu chi</b>",
            f"\u2022 Preset: <b>{config.FILTER_PRESET}</b>"
            f" (RSI {p['15m']}/{p['4h']}/{p['1d']})",
            f"\u2022 F1 RSI &gt;= <b>{config.F1_RSI_15M_PASS:.0f}"
            f"/{config.F1_RSI_4H_PASS:.0f}/{config.F1_RSI_1D_PASS:.0f}</b>",
            f"\u2022 F2 Long ratio &gt;= <b>{config.F2_LONG_RATIO_PASS:.0f}%</b>",
            f"\u2022 F3 Spike 15m &gt;= <b>{config.F3_SPIKE_15M_PASS:.0f}%</b>",
            f"\u2022 F4 OI &gt;= <b>{config.F4_OI_CHANGE_PASS:.0f}%</b>"
            f" qua {config.F4_OI_LOOKBACK_15M_BARS} chu ky",
            f"\u2022 F5 Upper wick &gt;= <b>"
            f"{config.F5_UPPER_WICK_RATIO_PASS:.2f}</b>",
            f"\u2022 F6 Funding &gt;= <b>{config.F6_FUNDING_MIN}%</b>",
            "",
            "<b>Dieu kien gui canh bao</b>",
            f"\u2022 PASS toi thieu: <b>"
            f"{config.TELEGRAM_MIN_PASSED_FILTERS}/6</b>",
            f"\u2022 Diem san: <b>{config.TELEGRAM_MIN_SCORE_FLOOR:.0f}/100</b>",
            f"\u2022 Bat buoc PASS 1 trong: <b>"
            f"{'/'.join(require_any) if require_any else 'khong'}</b>",
            f"\u2022 Cooldown moi coin: <b>{config.TELEGRAM_COOLDOWN_MINUTES}"
            f" phut</b>",
        ]
        self._reply(chat_id, "\n".join(lines), msg_id, is_group, from_user)

    # ---------------------------------------------------------------- /help
    def _help_text(self, is_group: bool = False) -> str:
        """Huong dan su dung. Trong nhom se ghi kem @ten_bot cho tung lenh."""
        at = f"@{self.bot_username}" if (is_group and self.bot_username) else ""
        text = (
            "\U0001f4d6 <b>HUONG DAN</b>\n\n"
            f"<code>/search{at} btc</code> \u2014 soi chi tiet 1 coin:"
            " tung tieu chi F1-F6 PASS/FAIL, diem tung phan va tong diem /100\n"
            f"<code>/top{at}</code> \u2014 top coin nhieu tieu chi PASS nhat\n"
            f"<code>/status{at}</code> \u2014 trang thai + nguong cac tieu chi\n"
            f"<code>/start{at}</code> \u2014 dang ky nhan canh bao tu dong\n"
            f"<code>/stop{at}</code> \u2014 huy nhan canh bao"
        )
        if is_group:
            text += (
                "\n\n\U0001f465 <b>Trong nhom:</b> moi thanh vien deu dung duoc"
                " cac lenh tren, bot se reply truc tiep vao tin cua ban.\n"
                f"\u2022 Neu bot khong phan hoi, hay go kem <code>{at}</code>"
                " (vd <code>/search" + at + " btc</code>).\n"
                "\u2022 Bot <b>khong doc</b> tin nhan chat thuong cua moi nguoi,"
                " chi phan hoi tin bat dau bang <code>/</code>."
            )
            if config.TELEGRAM_GROUP_ADMIN_ONLY_STOP:
                text += (
                    "\n\u2022 <code>/stop</code> chi <b>admin nhom</b> dung duoc."
                )
        else:
            text += (
                "\n\n\U0001f4a1 Co the go thang ten coin (vd <code>btc</code>)"
                " thay cho <code>/search btc</code>."
            )
        if config.TELEGRAM_USER_COOLDOWN_SECONDS > 0:
            text += (
                f"\n\n\u23f1\ufe0f Moi nguoi cho"
                f" <b>{config.TELEGRAM_USER_COOLDOWN_SECONDS}s</b> giua 2 lenh."
            )
        return text
