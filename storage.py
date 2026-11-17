"""Куда складывать заявки: файл (CSV или Excel) и, по желанию, сайт (webhook)."""
import csv
import json
import os
import urllib.request

FIELDS = [
    ("date", "Дата"), ("source", "Источник"), ("chat", "Чат / группа"), ("author", "Автор"),
    ("author_profile", "Профиль автора"), ("budget", "Бюджет"), ("currency", "Валюта"),
    ("budget_raw", "Бюджет (как в тексте)"), ("property_type", "Тип"), ("districts", "Район"),
    ("contacts", "Контакты в тексте"), ("text", "Текст"), ("link", "Ссылка"), ("id", "_id"),
]
HEADERS = [h for _, h in FIELDS]


class CsvFile:
    def __init__(self, path):
        self.path, self.rows = path, []
        self.seen = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig", newline="") as f:
                self.seen = {r["_id"] for r in csv.DictReader(f)}

    def add(self, lead):
        self.rows.append([lead.get(k, "") for k, _ in FIELDS])

    def save(self):
        if not self.rows:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        new = not os.path.exists(self.path)
        with open(self.path, "a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(HEADERS)
            w.writerows(self.rows)


class XlsxFile:
    def __init__(self, path):
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font
        self.path = path
        if os.path.exists(path):
            self.wb = load_workbook(path)
            self.ws = self.wb.active
            self.seen = {r[-1] for r in self.ws.iter_rows(min_row=2, values_only=True) if r and r[-1]}
            return
        self.wb = Workbook()
        self.ws = self.wb.active
        self.ws.title = "Заявки"
        self.ws.append(HEADERS)
        for c in self.ws[1]:
            c.font = Font(bold=True)
        widths = [17, 10, 22, 18, 22, 11, 8, 18, 14, 16, 20, 80, 36, 1]
        for i, w in enumerate(widths):
            self.ws.column_dimensions[chr(65 + i)].width = w
        self.ws.column_dimensions[chr(64 + len(FIELDS))].hidden = True
        self.ws.freeze_panes = "A2"
        self.seen = set()

    def add(self, lead):
        from openpyxl.styles import Alignment
        self.ws.append([lead.get(k, "") for k, _ in FIELDS])
        self.ws.cell(self.ws.max_row, 12).alignment = Alignment(wrap_text=True, vertical="top")

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.wb.save(self.path)


class Webhook:
    """Отправляет каждую новую заявку POST-запросом с JSON на сайт (например, сайт Асель)."""

    def __init__(self, url, secret):
        self.url, self.secret = url, secret
        self.failed = 0
        self.dup = 0
        self.new = []  # заявки, которых в кабинете ещё не было: для уведомления

    def _post(self, payload):
        body = json.dumps({**payload, "secret": self.secret}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Content-Type": "application/json", "X-Leads-Secret": self.secret,
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")

    def add(self, lead):
        # Пароль и в заголовке, и в теле: Google Apps Script заголовки не видит
        body = json.dumps({**lead, "secret": self.secret}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Content-Type": "application/json", "X-Leads-Secret": self.secret,
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                reply = r.read().decode("utf-8", "replace")
            try:
                j = json.loads(reply)
            except ValueError:
                j = {}
            ok = j.get("ok", True)
            if j.get("duplicate"):
                self.dup += 1
            elif ok:
                self.new.append({k: lead.get(k) for k in
                                 ("property_type", "districts", "budget", "currency", "text")})
            if not ok:
                raise RuntimeError(reply[:200])
        except Exception as e:
            self.failed += 1
            print(f"[!] Сайт не принял заявку {lead.get('id')}: {type(e).__name__}")

    def save(self):
        if self.dup:
            print(f"Из них уже были в кабинете: {self.dup}.")
        if self.failed:
            print(f"[!] Не отправлено на сайт: {self.failed}. Они есть в файле.")
        print(f"Действительно новых в кабинете: {len(self.new)}.")
        if self.new:
            try:
                j = json.loads(self._post({"type": "summary", "leads": self.new}))
                print(f"Уведомление отправлено: {j.get('sent', '?')} получателям.")
            except Exception as e:
                print(f"[!] Уведомление не отправилось: {type(e).__name__}")
        return self.failed


class Storage:
    """Файл + необязательный webhook. Дубли (по id) пропускаются."""

    def __init__(self, path, webhook_url="", webhook_secret=""):
        self.file = CsvFile(path) if path.lower().endswith(".csv") else XlsxFile(path)
        self.webhook = Webhook(webhook_url, webhook_secret) if webhook_url else None
        self.added = 0

    def add(self, lead) -> bool:
        if lead["id"] in self.file.seen:
            return False
        self.file.seen.add(lead["id"])
        self.file.add(lead)
        if self.webhook:
            self.webhook.add(lead)
        self.added += 1
        return True

    def save(self):
        """Возвращает, сколько заявок сайт не принял."""
        self.file.save()
        return self.webhook.save() if self.webhook else 0


def load_output(cfg):
    """Читает секцию [output] из configparser."""
    return Storage(
        cfg.get("output", "file", fallback="data/leads.csv"),
        cfg.get("output", "webhook_url", fallback="").strip(),
        cfg.get("output", "webhook_secret", fallback="").strip(),
    )
