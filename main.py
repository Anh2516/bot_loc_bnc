"""
BOT LOC COIN SHORT theo bo tieu chi F1-F6 (Binance USDT-M Futures).

Chuc nang: cu 5 phut quet 1 lan, in ra TAT CA coin co diem >= 50/100.

Cach dung:
    python main.py                 # chay lien tuc, quet moi 5 phut
    python main.py --once          # quet 1 lan roi thoat
    python main.py --min-score 60  # doi nguong diem
    python main.py --interval 300  # doi chu ky quet (giay)
    python main.py --symbol KGENUSDT --once   # kiem tra 1 coin cu the

Nguon tieu chi: Cach_thuc_Bot_SHORT_F1_F6_Entry_SL_TP-3_1.pdf
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

import config
import indicators
import reporter
import telegram_notifier
from scanner import Scanner
from scoring import score_coin
from telegram_bot import ScanCache, TelegramCommandBot
from telegram_notifier import TelegramNotifier


def setup_logging(verbose: bool = False) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bot loc coin SHORT theo tieu chi F1-F6 (Binance Futures)"
    )
    p.add_argument("--once", action="store_true", help="chi quet 1 lan roi thoat")
    p.add_argument(
        "--min-score", type=float, default=config.MIN_SCORE,
        help=f"nguong diem toi thieu (mac dinh {config.MIN_SCORE:.0f})",
    )
    p.add_argument(
        "--interval", type=int, default=config.SCAN_INTERVAL_SECONDS,
        help=f"chu ky quet, giay (mac dinh {config.SCAN_INTERVAL_SECONDS})",
    )
    p.add_argument("--symbol", help="chi kiem tra 1 coin, vd KGENUSDT (bo qua prefilter)")
    p.add_argument("--no-csv", action="store_true", help="khong ghi file CSV")
    p.add_argument(
        "--min-pass", type=int, default=config.TELEGRAM_MIN_PASSED_FILTERS,
        help=(
            "so tieu chi PASS toi thieu trong F1-F6 de day Telegram"
            f" (mac dinh {config.TELEGRAM_MIN_PASSED_FILTERS})"
        ),
    )
    p.add_argument(
        "--no-telegram", action="store_true", help="khong gui Telegram trong lan chay nay"
    )
    p.add_argument(
        "--ignore-cooldown", action="store_true",
        help="bo qua cooldown, gui lai ca coin vua gui gan day",
    )
    p.add_argument(
        "--test-telegram", action="store_true",
        help="gui 1 tin nhan mau (CHILLGUYUSDT trong anh) de kiem tra ket noi",
    )
    p.add_argument(
        "--preview", action="store_true",
        help="in ra noi dung tin nhan Telegram thay vi gui di",
    )
    p.add_argument(
        "--tele-min-score", type=float, default=config.TELEGRAM_MIN_SCORE_FLOOR,
        help="diem toi thieu de day Telegram (0 = khong ap dung)",
    )
    p.add_argument(
        "--quality", action="store_true",
        help=(
            "chong spam: chi day coin PASS it nhat 1 trong F1/F2/F3/F4"
            " (bo coin chi PASS F5+F6)"
        ),
    )
    p.add_argument("-v", "--verbose", action="store_true", help="log chi tiet")
    args = p.parse_args()
    # Ap dung tuy chon CLI vao config
    config.TELEGRAM_MIN_PASSED_FILTERS = args.min_pass
    config.TELEGRAM_MIN_SCORE_FLOOR = args.tele_min_score
    if args.quality:
        config.TELEGRAM_REQUIRE_ANY_OF = ("F1", "F2", "F3", "F4")
    return args


def scan_single_symbol(
    scanner: Scanner, symbol: str, args: argparse.Namespace,
    notifier: TelegramNotifier | None = None,
) -> None:
    """Cham diem 1 coin cu the (dung de kiem tra / doi chieu voi vi du trong PDF)."""
    symbol = symbol.upper()
    tickers = scanner.client.get_all_tickers_24h()
    fundings = scanner.client.get_all_funding_rates()
    if symbol not in tickers:
        print(f"Khong tim thay {symbol} tren Binance USDT-M Futures.")
        return

    metrics = scanner.fetch_metrics(symbol, tickers[symbol], fundings.get(symbol))
    if not metrics:
        print(f"Khong lay du du lieu cho {symbol}.")
        return

    cs = score_coin(symbol, metrics)
    info = scanner._load_symbol_info().get(symbol, {})
    levels = indicators.compute_entry_sl_tp(cs.price)
    cs.levels = {
        k: indicators.round_to_tick(v, info.get("tickSize"), info.get("pricePrecision", 6))
        for k, v in levels.items()
    }
    # nguong 0 vi day la che do soi 1 coin, luon in ket qua du diem thap
    reporter.print_report([cs], reporter.now_local(), 0.0, min_score=0.0)

    # Xem truoc / gui thu tin nhan Telegram cua chinh coin nay
    print(" NOI DUNG TIN NHAN TELEGRAM:")
    print("-" * 118)
    print(telegram_notifier.build_message(cs))
    print("-" * 118)
    print(
        f" So tieu chi PASS: {cs.passed_count}/6"
        f"  -> {'DU' if cs.passed_count >= config.TELEGRAM_MIN_PASSED_FILTERS else 'CHUA DU'}"
        f" dieu kien day Telegram (can >= {config.TELEGRAM_MIN_PASSED_FILTERS})\n"
    )
    if notifier and not args.no_telegram and not args.preview:
        if cs.passed_count >= config.TELEGRAM_MIN_PASSED_FILTERS:
            notifier.notify([cs], ignore_cooldown=True)


def run_one_scan(
    scanner: Scanner,
    args: argparse.Namespace,
    notifier: TelegramNotifier | None = None,
    cache: ScanCache | None = None,
) -> None:
    """
    1 vong quet -> 2 nhanh loc:
      * console + CSV : coin co diem >= --min-score
      * Telegram      : coin co >= --min-pass tieu chi PASS trong F1-F6
    """
    log = logging.getLogger("main")
    scan_time = reporter.now_local()
    t0 = time.time()
    try:
        all_results = scanner.scan_all()
    except Exception as exc:  # noqa: BLE001 - khong de bot chet giua dem
        log.error("Vong quet loi: %s", exc)
        return

    elapsed = time.time() - t0

    # Nhanh 1: bao cao console + CSV theo diem
    scored = [
        c for c in all_results
        if c.total_score >= args.min_score
        and not (config.REQUIRE_MANDATORY_PASS and c.failed_mandatory)
    ]
    reporter.print_report(scored, scan_time, elapsed, args.min_score)
    if scored and not args.no_csv:
        reporter.save_csv(scored, scan_time)

    # Nhanh 2: Telegram theo so tieu chi PASS
    tele_coins = scanner.telegram_candidates(all_results)
    reporter.print_telegram_summary(tele_coins)

    # Luu ket qua cho cac lenh /top, /status tra loi ngay
    if cache is not None:
        cache.update(
            all_results, tele_coins, scan_time.strftime("%H:%M:%S %d/%m")
        )

    if args.preview:
        # Xem truoc noi dung tin nhan ma khong gui di
        for c in tele_coins[: config.TELEGRAM_MAX_MESSAGES_PER_SCAN]:
            print("-" * 118)
            print(telegram_notifier.build_message(c))
        print("-" * 118 + "\n")
        return

    if notifier and not args.no_telegram:
        notifier.notify(tele_coins, ignore_cooldown=args.ignore_cooldown)


def test_telegram(notifier: TelegramNotifier) -> int:
    """Gui tin nhan mau (dung so lieu CHILLGUYUSDT trong anh) de kiem tra ket noi."""
    demo = reporter.build_demo_coin()
    text = telegram_notifier.build_message(demo)
    print("\n NOI DUNG TIN NHAN MAU:")
    print("-" * 118)
    print(text)
    print("-" * 118)
    if not notifier.enabled:
        print(
            "\n Chua cau hinh TELEGRAM_BOT_TOKEN trong config.py -> khong gui duoc.\n"
        )
        return 1
    if not notifier.has_recipient:
        print(
            "\n Chua co nguoi nhan! Hay mo Telegram, tim bot cua ban, bam Start"
            " (hoac go /start), roi chay lai lenh nay.\n"
        )
        return 1
    ok = notifier.send_text(text)
    print(
        f"\n Gui Telegram cho {len(notifier.subscribers)} nguoi/nhom:"
        f" {'THANH CONG' if ok else 'THAT BAI'}\n"
    )
    return 0 if ok else 1


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    log = logging.getLogger("main")

    notifier = TelegramNotifier()

    if args.test_telegram:
        return test_telegram(notifier)

    scanner = Scanner()
    cache = ScanCache()

    if args.symbol:
        scan_single_symbol(scanner, args.symbol, args, notifier)
        return 0

    log.info(
        "Bat dau bot: score >= %.0f/100 (console/CSV), Telegram khi >= %d/6 tieu chi"
        " PASS, chu ky %d giay (%.1f phut). Ctrl+C de dung.",
        args.min_score, args.min_pass, args.interval, args.interval / 60,
    )

    # Thread lang nghe lenh /search, /top, /status, /start ...
    cmd_bot: TelegramCommandBot | None = None
    if (
        notifier.enabled
        and config.TELEGRAM_ENABLE_COMMANDS
        and not args.no_telegram
        and not args.preview
    ):
        cmd_bot = TelegramCommandBot(notifier, scanner, cache)
        cmd_bot.start()
        if not notifier.has_recipient:
            log.warning(
                "Chua ai dang ky nhan tin. Mo Telegram, tim bot va gui /start"
                " de bat dau nhan canh bao tu dong."
            )
        else:
            log.info(
                "Dang gui canh bao cho %d nguoi/nhom",
                len(notifier.subscribers),
            )
    elif not notifier.enabled:
        log.warning(
            "Chua dien TELEGRAM_BOT_TOKEN trong config.py"
            " -> chi in ra console, khong gui Telegram."
        )

    try:
        while True:
            run_one_scan(scanner, args, notifier, cache)
            if args.once:
                # Che do --once: cho them chut de tra loi lenh dang cho (neu co)
                return 0
            log.info("Cho %d giay cho vong quet tiep theo...", args.interval)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log.info("Da dung bot theo yeu cau nguoi dung.")
        return 0
    finally:
        if cmd_bot:
            cmd_bot.stop()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nDa dung bot.")
        sys.exit(0)
