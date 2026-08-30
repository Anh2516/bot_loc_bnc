"""
Kiem chung luong xu ly lenh Telegram (/start, /search, /top, /status, /help)
bang cach gia lap update tu Telegram - KHONG gui tin nhan that.

Chay: python test_commands.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import config
import telegram_bot
import telegram_notifier
from scoring import score_coin

PASSED = 0
FAILED = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  [OK]   {name} {extra}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} {extra}")


class FakeNotifier:
    """Notifier gia: khong goi API, chi luu lai tin nhan da 'gui'."""

    def __init__(self, subs_path: str) -> None:
        self.token = "fake-token"
        # (chat_id, text, reply_to_message_id)
        self.sent: list[tuple[str, str, int | None]] = []
        self.subscribers = telegram_notifier.SubscriberStore(subs_path)
        self.session = None

    def send_to_chat(  # noqa: ANN001
        self, chat_id, text: str, reply_to: int | None = None
    ) -> bool:
        self.sent.append((str(chat_id), text, reply_to))
        return True

    def last(self) -> str:
        return self.sent[-1][1] if self.sent else ""

    def last_reply_to(self) -> int | None:
        return self.sent[-1][2] if self.sent else None


DEMO_METRICS = {
    "price": 0.01464,
    "price_change_pct_24h": 17.0,
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
    "oi_change": 4.0,
    "oi_value_from": 2_500_000.0,
    "oi_value_to": 2_600_000.0,
    "oi_periods": 3,
    "upper_wick": 0.42,
    "upper_wick_time": "10:45",
    "funding": 0.005,
}

FAKE_SYMBOLS = {
    "BTCUSDT": {"pricePrecision": 2, "tickSize": 0.1},
    "CHILLGUYUSDT": {"pricePrecision": 5, "tickSize": 0.00001},
    "KGENUSDT": {"pricePrecision": 4, "tickSize": 0.0001},
}


class FakeScanner:
    """Scanner gia: khong goi Binance."""

    def _load_symbol_info(self) -> dict:
        return FAKE_SYMBOLS


def make_bot(tmp: Path) -> tuple[telegram_bot.TelegramCommandBot, FakeNotifier]:
    notifier = FakeNotifier(str(tmp))
    bot = telegram_bot.TelegramCommandBot(
        notifier,  # type: ignore[arg-type]
        FakeScanner(),  # type: ignore[arg-type]
        telegram_bot.ScanCache(),
    )

    def fake_score(symbol: str):
        if symbol not in FAKE_SYMBOLS:
            return None
        coin = score_coin(symbol, dict(DEMO_METRICS))
        coin.levels = {
            "entry": 0.01464, "sl": 0.01483,
            "tp1": 0.01413, "tp2": 0.01321, "tp3": 0.01244,
        }
        return coin

    bot._score_symbol = fake_score  # type: ignore[assignment]
    bot.bot_username = "Test_bot"
    # Tat cooldown de test go nhieu lenh lien tuc
    bot._check_user_cooldown = lambda uid: True  # type: ignore[assignment]
    # Gia lap admin check (mac dinh KHONG phai admin)
    bot._is_group_admin = lambda cid, uid: bool(  # type: ignore[assignment]
        uid and uid in ADMIN_IDS
    )
    return bot, notifier


ADMIN_IDS: set[int] = set()


def upd(
    text: str,
    chat_id: int = 999,
    is_group: bool = False,
    user_id: int = 111,
    msg_id: int = 42,
) -> dict:
    """Tao 1 update Telegram gia lap (chat rieng hoac nhom)."""
    chat = (
        {"id": chat_id, "title": "Nhom Test", "type": "supergroup"}
        if is_group
        else {"id": chat_id, "first_name": "Tester", "type": "private"}
    )
    return {
        "update_id": 1,
        "message": {
            "message_id": msg_id,
            "chat": chat,
            "from": {"id": user_id, "first_name": "Tester", "username": "tester"},
            "text": text,
        },
    }


def upd_added_to_group(chat_id: int = -1001, status: str = "member") -> dict:
    """Gia lap update khi bot duoc add vao nhom / bi kick."""
    return {
        "update_id": 2,
        "my_chat_member": {
            "chat": {"id": chat_id, "title": "Nhom Test", "type": "supergroup"},
            "new_chat_member": {"status": status},
        },
    }


def test_start_stop(tmp: Path) -> None:
    print("\n[1] /start va /stop")
    bot, n = make_bot(tmp)

    bot._handle_update(upd("/start"))
    check("da tra loi /start", len(n.sent) == 1)
    # Voi TELEGRAM_AUTO_SUBSCRIBE=True, chat_id duoc them ngay khi nhan lenh
    # nen /start dau tien co the bao "da dang ky truoc do" - ca 2 deu hop le.
    check(
        "bao da dang ky (moi hoac da co)",
        "Da dang ky thanh cong" in n.last() or "da dang ky truoc do" in n.last(),
    )
    check("chat_id duoc luu", "999" in n.subscribers.all())
    check("co huong dan trong tin nhan", "/search" in n.last())

    bot._handle_update(upd("/start"))
    check("/start lan 2 -> bao da dang ky", "da dang ky truoc do" in n.last())

    bot._handle_update(upd("/stop"))
    check("bao da huy", "da huy nhan canh bao" in n.last())
    check("chat_id da bi xoa", "999" not in n.subscribers.all())


def test_auto_subscribe(tmp: Path) -> None:
    """TELEGRAM_AUTO_SUBSCRIBE: go lenh nao cung duoc dang ky, tru /stop."""
    print("\n[6] Tu dong dang ky khi go lenh (TELEGRAM_AUTO_SUBSCRIBE)")
    if not config.TELEGRAM_AUTO_SUBSCRIBE:
        print("  (bo qua: TELEGRAM_AUTO_SUBSCRIBE = False)")
        return

    bot, n = make_bot(tmp)
    bot._handle_update(upd("/help", chat_id=555))
    check("/help -> tu dong dang ky", "555" in n.subscribers.all())

    bot, n = make_bot(tmp)
    bot._handle_update(upd("/search btc", chat_id=666))
    check("/search -> tu dong dang ky", "666" in n.subscribers.all())

    # /stop KHONG duoc tu dong dang ky lai
    bot, n = make_bot(tmp)
    n.subscribers.add(777)
    bot._handle_update(upd("/stop", chat_id=777))
    check("/stop -> khong dang ky lai", "777" not in n.subscribers.all())


def test_search(tmp: Path) -> None:
    print("\n[2] /search <coin>")
    bot, n = make_bot(tmp)

    bot._handle_update(upd("/search chillguy"))
    check("gui 2 tin (dang lay + ket qua)", len(n.sent) == 2, f"= {len(n.sent)}")
    check("tin dau bao dang lay du lieu", "Dang lay du lieu" in n.sent[0][1])
    msg = n.last()
    check("co tieu de chi tiet", "CHI TIET F1-F6" in msg)
    check("ten coin da chuan hoa", "CHILLGUYUSDT" in msg)
    check("co tong diem /100", "/100" in msg)
    check("co so tieu chi PASS", "5/6" in msg)
    for code in ("F1", "F2", "F3", "F4", "F5", "F6"):
        check(f"co khoi {code}", f"{code} \u00b7" in msg)
    check("co diem tung tieu chi", "diem" in msg)
    check("co Entry/SL/TP", "Entry" in msg and "TP3" in msg)
    check("co ly do FAIL cua F4", "OI did not increase" in msg)


def test_search_variants(tmp: Path) -> None:
    print("\n[3] /search voi cac cach go khac nhau")
    for raw in ("/search btc", "/search BTC-USDT", "/s btcusdt", "btc"):
        bot, n = make_bot(tmp)
        bot._handle_update(upd(raw))
        check(f"{raw!r} -> BTCUSDT", "BTCUSDT" in n.last(), f"({len(n.sent)} tin)")

    bot, n = make_bot(tmp)
    bot._handle_update(upd("/search"))
    check("/search khong tham so -> bao thieu ten", "Thieu ten coin" in n.last())

    bot, n = make_bot(tmp)
    bot._handle_update(upd("/search zzzz"))
    check("coin khong ton tai -> bao khong tim thay", "Khong tim thay" in n.last())

    # Lenh ghi kem dung @ten_bot cua minh -> van chay
    bot, n = make_bot(tmp)
    bot._handle_update(upd("/search@Test_bot btc"))
    check("lenh co @ten_bot cua minh van chay", "BTCUSDT" in n.last())

    # Lenh ghi @ten_bot cua bot KHAC -> phai bo qua
    bot, n = make_bot(tmp)
    bot._handle_update(upd("/search@bot_nao_khac btc"))
    check("lenh cua bot khac -> bo qua", len(n.sent) == 0, f"= {len(n.sent)}")


def test_top_and_status(tmp: Path) -> None:
    print("\n[4] /top va /status")
    bot, n = make_bot(tmp)

    bot._handle_update(upd("/top"))
    check("chua quet -> bao chua co ket qua", "Chua co ket qua" in n.last())

    a = score_coin("AAAUSDT", dict(DEMO_METRICS))
    b = score_coin("BBBUSDT", {"price": 1.0, "funding": 0.01, "upper_wick": 0.9})
    bot.cache.update([a, b], [a, b], "12:00:00 29/08")

    bot._handle_update(upd("/top"))
    msg = n.last()
    check("co tieu de TOP", "TOP" in msg)
    check("liet ke AAAUSDT", "AAAUSDT" in msg)
    check("liet ke BBBUSDT", "BBBUSDT" in msg)
    check("co goi y /search", "/search AAAUSDT" in msg)
    check("co thoi diem quet", "12:00:00" in msg)

    bot._handle_update(upd("/status"))
    msg = n.last()
    check("co TRANG THAI BOT", "TRANG THAI BOT" in msg)
    check("co chu ky quet", "Chu ky quet" in msg)
    check("co preset dang dung", config.FILTER_PRESET in msg)
    check("co nguong F1", "F1 RSI" in msg)
    check("co nguong F6", "F6 Funding" in msg)
    check("co so coin da cham diem", "Coin da cham diem" in msg)


def test_help_and_unknown(tmp: Path) -> None:
    print("\n[5] /help va lenh la")
    bot, n = make_bot(tmp)

    bot._handle_update(upd("/help"))
    check("co HUONG DAN", "HUONG DAN" in n.last())
    check("liet ke /search", "/search" in n.last())
    check("liet ke /top", "/top" in n.last())

    bot._handle_update(upd("/abcxyz"))
    check("lenh la -> bao khong hieu", "Khong hieu lenh" in n.last())
    check("kem huong dan", "HUONG DAN" in n.last())

    before = len(n.sent)
    bot._handle_update({"update_id": 2, "message": {"chat": {"id": 1}}})
    check("update khong co text -> bo qua", len(n.sent) == before)


def test_group_added(tmp: Path) -> None:
    """Bot duoc add vao nhom -> tu dang ky + gui tin chao."""
    print("\n[7] Bot duoc add vao nhom / bi kick")
    bot, n = make_bot(tmp)

    bot._handle_update(upd_added_to_group(-1001, "member"))
    check("tu dang ky nhom", "-1001" in n.subscribers.all())
    check("gui tin chao nhom", "Xin chao nhom" in n.last())
    check("tin chao co ten nhom", "Nhom Test" in n.last())
    check("tin chao co huong dan", "/search" in n.last())
    check("tin chao co @ten_bot", "@Test_bot" in n.last())

    bot._handle_update(upd_added_to_group(-1001, "kicked"))
    check("bi kick -> xoa khoi danh sach", "-1001" not in n.subscribers.all())


def test_group_commands(tmp: Path) -> None:
    """Lenh trong nhom: reply vao tin goc + tag nguoi hoi."""
    print("\n[8] Lenh trong nhom (reply + tag nguoi hoi)")
    bot, n = make_bot(tmp)

    bot._handle_update(upd("/search btc", chat_id=-1002, is_group=True, msg_id=77))
    check("gui dung 1 tin (khong co 'dang lay')", len(n.sent) == 1, f"= {len(n.sent)}")
    check("reply vao tin goc (msg_id=77)", n.last_reply_to() == 77, f"= {n.last_reply_to()}")
    check("tag nguoi hoi", 'tg://user?id=111' in n.last())
    check("co ket qua BTCUSDT", "BTCUSDT" in n.last())
    check("nhom duoc tu dang ky", "-1002" in n.subscribers.all())

    bot, n = make_bot(tmp)
    bot._handle_update(upd("/top", chat_id=-1002, is_group=True, msg_id=88))
    check("/top trong nhom co reply", n.last_reply_to() == 88)

    bot, n = make_bot(tmp)
    bot._handle_update(upd("/help", chat_id=-1002, is_group=True))
    msg = n.last()
    check("/help nhom ghi kem @ten_bot", "/search@Test_bot" in msg)
    check("/help nhom noi ve nhieu thanh vien", "moi thanh vien" in msg)
    check("/help nhom noi khong doc chat thuong", "khong doc" in msg)


def test_group_plain_text_ignored(tmp: Path) -> None:
    """Trong nhom, tin nhan chat thuong KHONG bi coi la /search (chong spam)."""
    print("\n[9] Nhom: bo qua tin nhan chat thuong")
    bot, n = make_bot(tmp)

    bot._handle_update(upd("hom nay btc the nao moi nguoi", chat_id=-1003, is_group=True))
    check("khong tra loi chat thuong trong nhom", len(n.sent) == 0, f"= {len(n.sent)}")

    bot._handle_update(upd("chao ca nha", chat_id=-1003, is_group=True))
    check("khong tra loi loi chao", len(n.sent) == 0, f"= {len(n.sent)}")

    # Chat rieng thi van coi la ten coin
    bot, n = make_bot(tmp)
    bot._handle_update(upd("btc", chat_id=999, is_group=False))
    check("chat rieng: 'btc' -> /search", "BTCUSDT" in n.last())


def test_group_bot_mention(tmp: Path) -> None:
    """Lenh ghi @ten_bot khac thi bot bo qua (nhom co nhieu bot)."""
    print("\n[10] Nhom: phan biet @ten_bot")
    bot, n = make_bot(tmp)

    bot._handle_update(upd("/search@Test_bot btc", chat_id=-1004, is_group=True))
    check("lenh ghi dung @ten_bot -> xu ly", "BTCUSDT" in n.last())

    bot, n = make_bot(tmp)
    bot._handle_update(upd("/search@bot_khac btc", chat_id=-1004, is_group=True))
    check("lenh cua bot khac -> bo qua", len(n.sent) == 0, f"= {len(n.sent)}")


def test_group_admin_only_stop(tmp: Path) -> None:
    """Trong nhom, chi admin duoc /stop."""
    print("\n[11] Nhom: /stop chi danh cho admin")
    if not config.TELEGRAM_GROUP_ADMIN_ONLY_STOP:
        print("  (bo qua: TELEGRAM_GROUP_ADMIN_ONLY_STOP = False)")
        return

    # Nguoi thuong (khong phai admin)
    ADMIN_IDS.clear()
    bot, n = make_bot(tmp)
    n.subscribers.add(-1005)
    bot._handle_update(upd("/stop", chat_id=-1005, is_group=True, user_id=222))
    check("nguoi thuong bi tu choi", "Chi <b>admin cua nhom</b>" in n.last())
    check("nhom VAN nhan canh bao", "-1005" in n.subscribers.all())

    # Admin
    ADMIN_IDS.add(333)
    bot, n = make_bot(tmp)
    n.subscribers.add(-1005)
    bot._handle_update(upd("/stop", chat_id=-1005, is_group=True, user_id=333))
    check("admin huy duoc", "da huy nhan canh bao" in n.last())
    check("nhom bi xoa khoi danh sach", "-1005" not in n.subscribers.all())
    ADMIN_IDS.clear()

    # Chat rieng: ai cung /stop duoc
    bot, n = make_bot(tmp)
    n.subscribers.add(999)
    bot._handle_update(upd("/stop", chat_id=999, is_group=False))
    check("chat rieng: /stop khong can admin", "da huy nhan canh bao" in n.last())


def test_user_cooldown(tmp: Path) -> None:
    """Cooldown chan nguoi dung go lenh qua nhanh."""
    print("\n[12] Chong spam: cooldown moi nguoi")
    if config.TELEGRAM_USER_COOLDOWN_SECONDS <= 0:
        print("  (bo qua: TELEGRAM_USER_COOLDOWN_SECONDS = 0)")
        return

    notifier = FakeNotifier(str(tmp))
    bot = telegram_bot.TelegramCommandBot(
        notifier, FakeScanner(), telegram_bot.ScanCache()  # type: ignore[arg-type]
    )
    check("lan dau -> duoc phep", bot._check_user_cooldown(111) is True)
    check("go lai ngay -> bi chan", bot._check_user_cooldown(111) is False)
    check("nguoi khac -> duoc phep", bot._check_user_cooldown(222) is True)
    check("user_id None -> duoc phep", bot._check_user_cooldown(None) is True)


def main() -> int:
    print("=" * 70)
    print(" KIEM CHUNG LENH TELEGRAM - CHAT RIENG + NHOM")
    print(" (/start /search /top /status /help /stop + hoat dong trong group)")
    print("=" * 70)
    tmp = Path(tempfile.gettempdir()) / "f1f6_cmd_test_subs.json"
    try:
        for fn in (
            test_start_stop, test_search, test_search_variants,
            test_top_and_status, test_help_and_unknown, test_auto_subscribe,
            test_group_added, test_group_commands, test_group_plain_text_ignored,
            test_group_bot_mention, test_group_admin_only_stop, test_user_cooldown,
        ):
            tmp.unlink(missing_ok=True)
            fn(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    print("\n" + "=" * 70)
    print(f" KET QUA: {PASSED} OK / {FAILED} FAIL")
    print("=" * 70)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
