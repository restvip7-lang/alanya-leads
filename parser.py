"""Сбор заявок на покупку недвижимости в Алании из Telegram-чатов.

Запуск:  python parser.py            (берёт настройки из config.ini)
         python parser.py --days 7   (за последние 7 дней)
"""
import argparse
import asyncio
import configparser
import csv
import os
from datetime import datetime, timedelta, timezone

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from telethon import TelegramClient

from filters import is_buy_request, parse_lead

HEADERS = [
    "Дата", "Чат", "Автор", "Профиль автора", "Бюджет", "Валюта", "Бюджет (как в тексте)",
    "Тип", "Район", "Контакты в тексте", "Текст", "Ссылка", "_id",
]


def load_config(path="config.ini"):
    cfg = configparser.ConfigParser()
    if not cfg.read(path, encoding="utf-8"):
        raise SystemExit(f"Не найден {path}. Скопируйте config.example.ini в config.ini и заполните.")
    tg = cfg["telegram"]
    chats = [c.strip() for c in cfg["sources"]["chats"].splitlines() if c.strip()]
    return {
        "api_id": int(tg["api_id"]),
        "api_hash": tg["api_hash"],
        "chats": chats,
        "days": cfg.getint("sources", "days", fallback=3),
        "output": cfg.get("output", "file", fallback="leads.xlsx"),
    }


def open_workbook(path):
    if os.path.exists(path):
        wb = load_workbook(path)
        ws = wb.active
        seen = {row[-1] for row in ws.iter_rows(min_row=2, values_only=True) if row and row[-1]}
        return wb, ws, seen
    wb = Workbook()
    ws = wb.active
    ws.title = "Заявки"
    ws.append(HEADERS)
    for c in ws[1]:
        c.font = Font(bold=True)
    widths = [17, 22, 18, 22, 11, 8, 18, 14, 16, 20, 80, 36, 1]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.column_dimensions["M"].hidden = True
    ws.freeze_panes = "A2"
    return wb, ws, set()


class CsvSheet:
    """Тот же интерфейс, что у openpyxl, но пишет CSV (удобно хранить в git)."""
    def __init__(self, path):
        self.path, self.rows = path, []
        self.seen = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig", newline="") as f:
                self.seen = {r["_id"] for r in csv.DictReader(f)}

    def append(self, row):
        self.rows.append(row)

    def save(self):
        new = not os.path.exists(self.path)
        with open(self.path, "a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(HEADERS)
            w.writerows(self.rows)


def message_link(chat, msg_id):
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{msg_id}"
    return f"https://t.me/c/{chat.id}/{msg_id}"


async def collect(cfg, days):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    is_csv = cfg["output"].lower().endswith(".csv")
    if is_csv:
        ws = wb = CsvSheet(cfg["output"])
        seen = ws.seen
    else:
        wb, ws, seen = open_workbook(cfg["output"])
    added = 0
    async with TelegramClient("alanya_session", cfg["api_id"], cfg["api_hash"]) as client:
        for chat_ref in cfg["chats"]:
            try:
                chat = await client.get_entity(chat_ref)
            except Exception as e:
                print(f"[!] Не удалось открыть {chat_ref}: {e}")
                continue
            title = getattr(chat, "title", None) or chat_ref
            n = 0
            async for msg in client.iter_messages(chat, offset_date=None):
                if msg.date < since:
                    break
                text = msg.message or ""
                if not is_buy_request(text):
                    continue
                uid = f"{chat.id}:{msg.id}"
                if uid in seen:
                    continue
                sender = await msg.get_sender()
                name = " ".join(filter(None, [getattr(sender, "first_name", None),
                                              getattr(sender, "last_name", None)])) \
                    or getattr(sender, "title", "") or ""
                profile = f"@{sender.username}" if getattr(sender, "username", None) else ""
                lead = parse_lead(text)
                ws.append([
                    msg.date.astimezone().strftime("%Y-%m-%d %H:%M"), title, name, profile,
                    lead["budget"], lead["currency"], lead["budget_raw"], lead["property_type"],
                    lead["districts"], lead["contacts_in_text"], text,
                    message_link(chat, msg.id), uid,
                ])
                if not is_csv:
                    ws.cell(ws.max_row, 11).alignment = Alignment(wrap_text=True, vertical="top")
                seen.add(uid)
                n += 1
            print(f"[+] {title}: новых заявок {n}")
            added += n
    os.makedirs(os.path.dirname(cfg["output"]) or ".", exist_ok=True)
    wb.save() if is_csv else wb.save(cfg["output"])
    print(f"Готово. Добавлено {added} заявок в {cfg['output']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, help="за сколько дней собирать")
    ap.add_argument("--config", default="config.ini")
    args = ap.parse_args()
    cfg = load_config(args.config)
    asyncio.run(collect(cfg, args.days or cfg["days"]))


if __name__ == "__main__":
    main()
