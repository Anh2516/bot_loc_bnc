"""
Quan ly danh sach nguoi / nhom nhan canh bao tu dong.

Cach dung:
    python add_subscriber.py                    # xem danh sach hien tai
    python add_subscriber.py 8048946417         # them 1 chat_id
    python add_subscriber.py -1001234567890     # them 1 nhom (id am)
    python add_subscriber.py --remove 8048946417  # xoa 1 chat_id
    python add_subscriber.py --clear            # xoa tat ca

Ghi chu: chat_id cua NHOM luon la so AM (vd -1001234567890).
Binh thuong khong can dung script nay: chi can /start hoac add bot vao nhom.
"""
from __future__ import annotations

import sys

import config
import telegram_notifier


def describe(chat_id: str) -> str:
    """Goi ten chat_id + lay ten thuc te tu Telegram neu duoc."""
    kind = "nhom" if chat_id.startswith("-") else "ca nhan"
    if not config.TELEGRAM_BOT_TOKEN:
        return kind
    try:
        import requests

        r = requests.get(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getChat",
            params={"chat_id": chat_id},
            timeout=15,
        )
        data = r.json()
        if data.get("ok"):
            c = data["result"]
            name = c.get("title") or c.get("first_name") or c.get("username") or "?"
            return f"{kind} - {name}"
        return f"{kind} - (khong lay duoc ten: {data.get('description', '?')})"
    except Exception as exc:  # noqa: BLE001
        return f"{kind} - (loi: {str(exc)[:60]})"


def show(store: telegram_notifier.SubscriberStore) -> None:
    ids = store.all()
    print(f"\nDanh sach nhan canh bao ({len(ids)}):")
    if not ids:
        print("  (trong) -> hay /start voi bot hoac add bot vao nhom")
        return
    for cid in ids:
        print(f"  {cid:<16} {describe(cid)}")


def main() -> int:
    store = telegram_notifier.SubscriberStore()
    args = sys.argv[1:]

    if args and args[0] in ("--clear", "-c"):
        for cid in list(store.all()):
            store.remove(cid)
        print("Da xoa tat ca.")
        show(store)
        return 0

    if args and args[0] in ("--remove", "-r"):
        targets = args[1:]
        if not targets:
            print("Thieu chat_id. Vd: python add_subscriber.py --remove 8048946417")
            return 1
        for raw in targets:
            print(f"{raw}: {'da xoa' if store.remove(raw) else 'khong co trong danh sach'}")
        show(store)
        return 0

    for raw in args:
        print(f"{raw}: {'da them' if store.add(raw) else 'da co san'}")

    show(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
