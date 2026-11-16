"""Сбор заявок на покупку недвижимости в Алании из Telegram-чатов.

Запуск:  python parser.py            (берёт настройки из config.ini)
         python parser.py --days 7   (за последние 7 дней)
"""
import argparse
import asyncio
import configparser
from datetime import datetime, timedelta, timezone

from filters import is_buy_request, parse_lead
from storage import load_output


def read_config(path):
    cfg = configparser.ConfigParser()
    if not cfg.read(path, encoding="utf-8"):
        raise SystemExit(f"Не найден {path}. Скопируйте config.example.ini в config.ini и заполните.")
    return cfg


def message_link(chat, msg_id):
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{msg_id}"
    return f"https://t.me/c/{chat.id}/{msg_id}"


def make_lead(*, date, source, chat, author, author_profile, text, link, uid):
    p = parse_lead(text)
    return {
        "date": date, "source": source, "chat": chat, "author": author,
        "author_profile": author_profile, "budget": p["budget"], "currency": p["currency"],
        "budget_raw": p["budget_raw"], "property_type": p["property_type"],
        "districts": p["districts"], "contacts": p["contacts_in_text"], "text": text,
        "link": link, "id": uid,
    }


async def collect(cfg, days):
    from telethon import TelegramClient

    tg = cfg["telegram"]
    chats = [c.strip() for c in cfg["sources"]["chats"].splitlines() if c.strip()]
    since = datetime.now(timezone.utc) - timedelta(days=days)
    store = load_output(cfg)
    async with TelegramClient("alanya_session", int(tg["api_id"]), tg["api_hash"]) as client:
        for chat_ref in chats:
            try:
                chat = await client.get_entity(chat_ref)
            except Exception as e:
                print(f"[!] Не удалось открыть {chat_ref}: {e}")
                continue
            title = getattr(chat, "title", None) or chat_ref
            n = 0
            async for msg in client.iter_messages(chat):
                if msg.date < since:
                    break
                text = msg.message or ""
                if not is_buy_request(text):
                    continue
                sender = await msg.get_sender()
                name = " ".join(filter(None, [getattr(sender, "first_name", None),
                                              getattr(sender, "last_name", None)])) \
                    or getattr(sender, "title", "") or ""
                lead = make_lead(
                    date=msg.date.astimezone().strftime("%Y-%m-%d %H:%M"), source="telegram",
                    chat=title, author=name,
                    author_profile=f"@{sender.username}" if getattr(sender, "username", None) else "",
                    text=text, link=message_link(chat, msg.id), uid=f"tg:{chat.id}:{msg.id}",
                )
                n += store.add(lead)
            print(f"[+] {title}: новых заявок {n}")
    store.save()
    print(f"Готово. Добавлено {store.added} заявок.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, help="за сколько дней собирать")
    ap.add_argument("--config", default="config.ini")
    args = ap.parse_args()
    cfg = read_config(args.config)
    asyncio.run(collect(cfg, args.days or cfg.getint("sources", "days", fallback=3)))


if __name__ == "__main__":
    main()
