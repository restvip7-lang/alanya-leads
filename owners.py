"""Квартиры на продажу от собственников из тех же Telegram-чатов. Отдельно от заявок покупателей.

Запуск:  python owners.py --hours 16      (так работает облачный запуск)
         python owners.py --days 7 --dry  (просто показать найденное, никуда не отправлять)

Каждая квартира уходит POST-запросом на [output] listings_url (кабинет, раздел «Квартиры от собственников»)
с тем же паролем webhook_secret. Агентства отсеиваются: по словам в тексте, по имени автора, по тому, что пишет
канал, а не человек, и по числу разных квартир от одного автора (больше 2 за запуск = агент).
"""
import argparse
import asyncio
import hashlib
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from owner_filters import MAX_LISTINGS_PER_AUTHOR, is_owner_listing, parse_listing, text_key
from parser import ALANYA_TZ, make_client, message_link, read_config


def listing_id(sender_id, text):
    # Один автор и один текст = одна квартира, даже если пост разослан по пяти чатам
    return "own:" + hashlib.sha256(f"{sender_id}:{text_key(text)}".encode()).hexdigest()[:24]


async def collect(cfg, since):
    chats = [c.strip() for c in cfg.get("sources", "chats", fallback="").splitlines() if c.strip()]
    client, _ = make_client(cfg["telegram"])
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("Telegram не авторизован: получите строку сессии через python login.py")
    found = {}
    by_author = defaultdict(set)
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
                if len(text) < 20:
                    continue
                sender = await msg.get_sender()
                # Пишет канал или бот, а не человек: это агентство или паблик
                if sender is None or getattr(sender, "bot", False) or not hasattr(sender, "first_name"):
                    continue
                name = " ".join(filter(None, [sender.first_name, getattr(sender, "last_name", None)]))
                if not is_owner_listing(text, name + " " + (sender.username or "")):
                    continue
                uid = listing_id(sender.id, text)
                by_author[sender.id].add(text_key(text))
                if uid in found:
                    continue
                p = parse_listing(text)
                found[uid] = {
                    "id": uid, "source": "telegram", "date": msg.date.astimezone(ALANYA_TZ).strftime("%Y-%m-%d %H:%M"),
                    "chat": title, "author": name, "author_id": str(sender.id),
                    "author_profile": f"@{sender.username}" if sender.username else "",
                    "phone": getattr(sender, "phone", None) or "",
                    "price": p["price"], "currency": p["currency"], "rooms": p["rooms"], "area": p["area"],
                    "district": p["district"], "owner_said": p["owner_said"], "contacts": p["contacts_in_text"],
                    "text": text, "link": message_link(chat, msg.id),
                }
                n += 1
            print(f"[+] {title}: квартир {n}")
    agents = {a for a, posts in by_author.items() if len(posts) > MAX_LISTINGS_PER_AUTHOR}
    out = [l for l in found.values() if int(l["author_id"]) not in agents]
    if agents:
        print(f"Отсеяно как агенты (больше {MAX_LISTINGS_PER_AUTHOR} разных квартир): {len(agents)} авторов, "
              f"{len(found) - len(out)} объявлений.")
    return out


def post(url, secret, payload):
    body = json.dumps({**payload, "secret": secret}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "X-Leads-Secret": secret})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace") or "{}")


def send(url, secret, listings):
    new, dup, failed = [], 0, 0
    for l in listings:
        try:
            j = post(url, secret, l)
            if not j.get("ok"):
                raise RuntimeError(str(j)[:200])
            if j.get("duplicate"):
                dup += 1
            else:
                new.append({k: l[k] for k in ("district", "rooms", "price", "currency")})
        except Exception as e:
            failed += 1
            print(f"[!] Кабинет не принял {l['id']}: {type(e).__name__}")
    print(f"Новых квартир в кабинете: {len(new)}, уже были: {dup}, не отправлено: {failed}.")
    if new:
        # Одно сообщение в общий чат за запуск: сколько новых, по районам и планировкам
        try:
            j = post(url, secret, {"type": "summary", "listings": new})
            print("Сводка отправлена в чат." if j.get("sent") else "Сводку некуда отправить: в группе ещё не написали /listings.")
        except Exception as e:
            print(f"[!] Сводка не отправилась: {type(e).__name__}")
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int)
    ap.add_argument("--hours", type=int)
    ap.add_argument("--config", default="config.ini")
    ap.add_argument("--dry", action="store_true", help="только показать, не отправлять")
    args = ap.parse_args()
    cfg = read_config(args.config)
    span = timedelta(hours=args.hours) if args.hours else timedelta(days=args.days or 3)
    listings = asyncio.run(collect(cfg, datetime.now(timezone.utc) - span))
    print(f"Найдено квартир от собственников: {len(listings)}.")
    url = cfg.get("output", "listings_url", fallback="").strip()
    secret = cfg.get("output", "webhook_secret", fallback="").strip()
    if args.dry or not url or not secret:
        for l in listings:
            print(f"- {l['district'] or '?'} | {l['rooms'] or '?'} | {l['price']} {l['currency']} | {l['link']}")
        return
    if send(url, secret, listings):
        sys.exit(1)


if __name__ == "__main__":
    main()
