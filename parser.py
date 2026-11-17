"""Сбор заявок на покупку недвижимости в Алании из Telegram-чатов.

Запуск:  python parser.py             (берёт настройки из config.ini)
         python parser.py --days 7    (за последние 7 дней)
         python parser.py --hours 3   (за последние 3 часа, так работает облачный запуск)

Любую настройку можно задать переменной окружения (так делает GitHub Actions):
TG_API_ID, TG_API_HASH, TG_SESSION (строка сессии из login.py), WEBHOOK_URL, WEBHOOK_SECRET.
"""
import argparse
import asyncio
import configparser
import os
import sys
from datetime import datetime, timedelta, timezone

from filters import is_buy_request, parse_lead
from storage import load_output

ALANYA_TZ = timezone(timedelta(hours=3))  # время Турции, в облаке часы идут по UTC


ENV = {
    "TG_API_ID": ("telegram", "api_id"),
    "TG_API_HASH": ("telegram", "api_hash"),
    "TG_SESSION": ("telegram", "session"),
    "WEBHOOK_URL": ("output", "webhook_url"),
    "WEBHOOK_SECRET": ("output", "webhook_secret"),
}


def read_config(path):
    # Без интерполяции: в паролях бывает «%», обычный ConfigParser на нём падает
    cfg = configparser.ConfigParser(interpolation=None)
    found = cfg.read(path, encoding="utf-8")
    for sec in ("telegram", "sources", "output"):
        if not cfg.has_section(sec):
            cfg.add_section(sec)
    for var, (sec, key) in ENV.items():
        if os.environ.get(var, "").strip():
            cfg.set(sec, key, os.environ[var].strip())
    if not found and not cfg.get("telegram", "api_id", fallback=""):
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


def make_client(tg):
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    session = tg.get("session", "").strip()
    return TelegramClient(StringSession(session) if session else "alanya_session",
                          int(tg["api_id"]), tg["api_hash"]), bool(session)


async def collect(cfg, since):
    tg = cfg["telegram"]
    chats = [c.strip() for c in cfg.get("sources", "chats", fallback="").splitlines() if c.strip()]
    if not chats:
        raise SystemExit("В config.ini не указаны чаты ([sources] chats).")
    store = load_output(cfg)
    client, from_string = make_client(tg)
    if from_string or not sys.stdin.isatty():
        await client.connect()
        if not await client.is_user_authorized():
            raise SystemExit("Telegram не авторизован: строка сессии неверна или устарела. "
                             "Получите новую: python login.py")
    async with client:
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
                    date=msg.date.astimezone(ALANYA_TZ).strftime("%Y-%m-%d %H:%M"), source="telegram",
                    chat=title, author=name,
                    author_profile=f"@{sender.username}" if getattr(sender, "username", None) else "",
                    text=text, link=message_link(chat, msg.id), uid=f"tg:{chat.id}:{msg.id}",
                )
                n += store.add(lead)
            print(f"[+] {title}: новых заявок {n}")
    failed = store.save()
    print(f"Готово. Новых заявок: {store.added}.")
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, help="за сколько дней собирать")
    ap.add_argument("--hours", type=int, help="за сколько часов собирать")
    ap.add_argument("--config", default="config.ini")
    args = ap.parse_args()
    cfg = read_config(args.config)
    span = timedelta(hours=args.hours) if args.hours else \
        timedelta(days=args.days or cfg.getint("sources", "days", fallback=3))
    failed = asyncio.run(collect(cfg, datetime.now(timezone.utc) - span))
    if failed:
        sys.exit(1)  # чтобы в GitHub Actions запуск стал красным и было видно, что кабинет не принял заявки


if __name__ == "__main__":
    main()
