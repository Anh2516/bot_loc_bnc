"""
Kiem tra moi truong truoc khi chay bot - dung khi chuyen sang may moi.

Chay: python check_env.py
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

OK = "[OK]  "
BAD = "[LOI] "
WARN = "[!]   "

problems: list[str] = []


def check_python() -> None:
    v = sys.version_info
    print(f"\n1. Phien ban Python: {v.major}.{v.minor}.{v.micro}")
    if (v.major, v.minor) >= (3, 10):
        print(f"   {OK}Du yeu cau (can >= 3.10)")
    else:
        print(f"   {BAD}Qua cu! Can Python 3.10 tro len.")
        problems.append("Nang cap Python len 3.10+")


def check_packages() -> None:
    print("\n2. Thu vien ngoai:")
    required = {
        "requests": "BAT BUOC - goi API Binance va Telegram",
        "pypdf": "tuy chon - chi de doc file PDF tieu chi",
    }
    for name, note in required.items():
        try:
            mod = importlib.import_module(name)
            ver = getattr(mod, "__version__", "?")
            print(f"   {OK}{name:<10} {ver:<10} ({note})")
        except ImportError:
            if name == "requests":
                print(f"   {BAD}{name:<10} CHUA CAI    ({note})")
                problems.append("pip install -r requirements.txt")
            else:
                print(f"   {WARN}{name:<10} chua cai    ({note})")


def check_stdlib() -> None:
    print("\n3. Thu vien chuan (co san trong Python):")
    mods = [
        "logging", "json", "csv", "time", "datetime", "pathlib",
        "threading", "argparse", "html", "typing", "tempfile",
        "zoneinfo", "concurrent.futures",
    ]
    missing = []
    for m in mods:
        try:
            importlib.import_module(m)
        except ImportError:
            missing.append(m)
    if missing:
        print(f"   {BAD}Thieu: {', '.join(missing)}")
        problems.append("Cai lai Python day du")
    else:
        print(f"   {OK}Day du {len(mods)} module")


def check_project_files() -> None:
    print("\n4. File cua project:")
    needed = [
        "config.py", "binance_client.py", "indicators.py", "scoring.py",
        "scanner.py", "reporter.py", "telegram_notifier.py",
        "telegram_bot.py", "main.py",
    ]
    here = Path(__file__).parent
    missing = [f for f in needed if not (here / f).exists()]
    if missing:
        print(f"   {BAD}Thieu file: {', '.join(missing)}")
        problems.append("Copy day du file project")
    else:
        print(f"   {OK}Day du {len(needed)} file code")


def check_config() -> None:
    print("\n5. Cau hinh:")
    try:
        import config
    except Exception as exc:  # noqa: BLE001
        print(f"   {BAD}Khong doc duoc config.py: {exc}")
        problems.append("Sua loi trong config.py")
        return

    if config.TELEGRAM_BOT_TOKEN:
        token = config.TELEGRAM_BOT_TOKEN
        print(f"   {OK}TELEGRAM_BOT_TOKEN da co ({token[:10]}...)")
    else:
        print(f"   {WARN}TELEGRAM_BOT_TOKEN con trong")
        print("         -> bot van quet duoc nhung KHONG gui Telegram")
        print("         -> lay token tu @BotFather roi dien vao config.py")

    print(f"   {OK}Chu ky quet: {config.SCAN_INTERVAL_SECONDS // 60} phut")
    print(f"   {OK}Telegram khi >= {config.TELEGRAM_MIN_PASSED_FILTERS}/6 tieu chi PASS")
    print(f"   {OK}Preset tieu chi: {config.FILTER_PRESET}")

    subs = Path(config.TELEGRAM_SUBSCRIBERS_FILE)
    if subs.exists():
        import json

        try:
            ids = json.loads(subs.read_text(encoding="utf-8")).get("chat_ids", [])
            print(f"   {OK}So nguoi nhan canh bao: {len(ids)}")
        except ValueError:
            print(f"   {WARN}{subs.name} bi loi dinh dang")
    else:
        print(f"   {WARN}Chua ai dang ky nhan tin")
        print("         -> mo Telegram, tim bot cua ban, bam Start")


def check_network() -> None:
    print("\n6. Ket noi mang:")
    try:
        import requests
    except ImportError:
        print(f"   {BAD}Chua cai requests, khong kiem tra duoc")
        return

    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/ping", timeout=15)
        r.raise_for_status()
        print(f"   {OK}Ket noi Binance Futures API thanh cong")
    except Exception as exc:  # noqa: BLE001
        print(f"   {BAD}Khong ket noi duoc Binance: {str(exc)[:120]}")
        problems.append("Kiem tra mang / VPN (mot so ISP chan Binance)")

    try:
        import config

        if config.TELEGRAM_BOT_TOKEN:
            r = requests.get(
                f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe",
                timeout=15,
            )
            data = r.json()
            if data.get("ok"):
                bot = data["result"]
                print(
                    f"   {OK}Token Telegram hop le:"
                    f" @{bot.get('username')} ({bot.get('first_name')})"
                )
            else:
                print(f"   {BAD}Token Telegram khong hop le: {data.get('description')}")
                problems.append("Lay token moi tu @BotFather")
    except Exception as exc:  # noqa: BLE001
        print(f"   {WARN}Khong kiem tra duoc Telegram: {str(exc)[:120]}")


def main() -> int:
    print("=" * 62)
    print(" KIEM TRA MOI TRUONG - BOT LOC COIN SHORT F1-F6")
    print("=" * 62)

    check_python()
    check_packages()
    check_stdlib()
    check_project_files()
    check_config()
    check_network()

    print("\n" + "=" * 62)
    if problems:
        print(" CAN XU LY:")
        for i, p in enumerate(dict.fromkeys(problems), start=1):
            print(f"   {i}. {p}")
        print("=" * 62)
        return 1

    print(" SAN SANG! Chay bot bang lenh:")
    print("   python main.py --quality        (hoac double-click run_bot.bat)")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
