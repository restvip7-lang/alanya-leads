"""Определение заявок на ПОКУПКУ недвижимости в Алании и извлечение параметров."""
import re

# Слова, говорящие о намерении купить (RU / EN / TR)
BUY_PATTERNS = [
    r"\bкуплю\b", r"\bкупим\b", r"\bхочу\s+купить", r"\bхотим\s+купить",
    r"\bищу\s+(?:квартир|апартамент|виллу|дом|жиль|недвижим|\d\+\d)",
    r"\bищем\s+(?:квартир|апартамент|виллу|дом|жиль|недвижим|\d\+\d)",
    r"\bрассмотр\w*\s+(?:покупк|вариант)", r"\bинтересует\s+покупк",
    r"\bв\s+покупку\b", r"\bпод\s+покупку\b", r"\bна\s+покупку\b",
    r"\bприобрести\b", r"\bприобрету\b",
    r"\bwant\s+to\s+buy\b", r"\blooking\s+to\s+buy\b", r"\bwill\s+buy\b",
    r"\blooking\s+for\s+(?:an?\s+)?(?:apartment|flat|villa|house|property|\d\+\d)",
    r"\bsatın\s+almak\s+istiyorum\b", r"\balmak\s+istiyorum\b", r"\bsatılık\s+arıyorum\b",
]

# Признаки, что это объявление продавца/аренда, а не заявка покупателя
EXCLUDE_PATTERNS = [
    r"\bпродам\b", r"\bпродаю\b", r"\bпродается\b", r"\bпродаётся\b", r"\bв\s+продаже\b",
    r"\bсдам\b", r"\bсдаю\b", r"\bсдается\b", r"\bсдаётся\b",
    r"\bаренд\w*", r"\bсниму\b", r"\bснять\b", r"\bпосуточно\b", r"\bдолгосрок\w*",
    r"\bfor\s+sale\b", r"\bfor\s+rent\b", r"\bto\s+rent\b", r"\brent(?:al)?\b",
    r"\bsatılık\b(?!\s+arıyorum)", r"\bkiralık\b",
]

REAL_ESTATE_HINTS = [
    r"квартир", r"апартамент", r"вилл", r"\bдом\b", r"пентхаус", r"дуплекс", r"недвижим",
    r"\b\d\s*\+\s*\d\b", r"студи", r"apartment", r"flat", r"villa", r"penthouse",
    r"duplex", r"property", r"daire", r"konut",
]

# Каноническое название района -> варианты написания
DISTRICTS = {
    "Махмутлар": ["Махмутлар", "Mahmutlar"],
    "Оба": ["Оба", "Oba"],
    "Кестель": ["Кестель", "Kestel"],
    "Тосмур": ["Тосмур", "Tosmur"],
    "Джикджилли": ["Джикджилли", "Cikcilli", "Cıkcıllı"],
    "Авсаллар": ["Авсаллар", "Avsallar"],
    "Конаклы": ["Конаклы", "Konaklı", "Konakli"],
    "Каргыджак": ["Каргыджак", "Kargıcak", "Kargicak"],
    "Тюрклер": ["Тюрклер", "Türkler", "Turkler"],
    "Паяллар": ["Паяллар", "Payallar"],
    "Демирташ": ["Демирташ", "Demirtaş", "Demirtas"],
    "Инжекум": ["Инжекум", "İncekum", "Incekum"],
    "Окурджалар": ["Окурджалар", "Okurcalar"],
    "Клеопатра": ["Клеопатра", "Kleopatra", "Cleopatra"],
    "Сарай": ["Сарай", "Saray"],
    "Тепе": ["Тепе", "Tepe"],
    "Бекташ": ["Бекташ", "Bektaş", "Bektas"],
    "Хаджет": ["Хаджет", "Hacet"],
    "Газипаша": ["Газипаша", "Gazipaşa", "Gazipasa"],
    "Центр": ["центр Алании", "Alanya center", "Alanya merkez"],
}

PROPERTY_TYPES = [
    (r"\b(\d)\s*\+\s*(\d)\b", None),
    (r"пентхаус|penthouse", "пентхаус"),
    (r"дуплекс|duplex", "дуплекс"),
    (r"вилл|villa", "вилла"),
    (r"студи|studio", "студия"),
    (r"\bдом\b|house|müstakil", "дом"),
    (r"квартир|апартамент|apartment|flat|daire", "квартира"),
    (r"земл|участ|land|arsa", "участок"),
]

_buy = [re.compile(p, re.I) for p in BUY_PATTERNS]
_excl = [re.compile(p, re.I) for p in EXCLUDE_PATTERNS]
_hint = [re.compile(p, re.I) for p in REAL_ESTATE_HINTS]

CURRENCY = r"(€|евро|eur|euro|\$|usd|долл\w*|tl|₺|лир\w*)"
_budget_re = re.compile(
    r"(?:до|бюджет\w*|budget|up\s+to|max\.?|около|в\s+пределах)?\s*:?\s*"
    r"(?:" + CURRENCY + r"\s*)?"
    r"(\d[\d\s.,]*\d|\d)\s*(k|к|тыс\.?|тысяч|млн|million|m)?\s*"
    r"(?:" + CURRENCY + r")?",
    re.I,
)


def is_buy_request(text: str) -> bool:
    if not text or len(text) < 10:
        return False
    if not any(p.search(text) for p in _buy):
        return False
    if any(p.search(text) for p in _excl):
        return False
    return any(p.search(text) for p in _hint) or re.search(r"\bкуплю\b", text, re.I) is not None


def extract_budget(text: str):
    """Возвращает (сумма_числом, валюта, исходный_фрагмент) или (None, '', '')."""
    best = None
    for m in _budget_re.finditer(text):
        cur = m.group(1) or m.group(4)
        mult = (m.group(3) or "").lower()
        raw = m.group(2)
        if not cur and not mult:
            continue  # голые числа (этаж, 2+1, год) пропускаем
        num_s = re.sub(r"[\s]", "", raw).replace(",", ".")
        if num_s.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", num_s):
            num_s = num_s.replace(".", "")
        try:
            num = float(num_s)
        except ValueError:
            continue
        if mult in ("k", "к", "тыс", "тыс.", "тысяч"):
            num *= 1_000
        elif mult in ("млн", "million", "m"):
            num *= 1_000_000
        if num < 1000:
            continue
        c = (cur or "").lower()
        if c in ("€", "евро", "eur", "euro"):
            c = "EUR"
        elif c in ("$", "usd") or c.startswith("долл"):
            c = "USD"
        elif c in ("tl", "₺") or c.startswith("лир"):
            c = "TRY"
        else:
            c = ""
        cand = (int(num), c, m.group(0).strip())
        if best is None or cand[0] > best[0]:
            best = cand
    return best or (None, "", "")


def extract_type(text: str) -> str:
    found = []
    for pat, name in PROPERTY_TYPES:
        for m in re.finditer(pat, text, re.I):
            val = f"{m.group(1)}+{m.group(2)}" if name is None else name
            if val not in found:
                found.append(val)
    return ", ".join(found)


def extract_districts(text: str) -> str:
    found = []
    for name, variants in DISTRICTS.items():
        if any(re.search(r"(?<!\w)" + re.escape(v), text, re.I) for v in variants):
            found.append(name)
    return ", ".join(found)


def extract_contacts(text: str) -> str:
    """Только контакты, которые автор сам опубликовал в тексте."""
    phones = re.findall(r"\+?\d[\d\s\-()]{8,}\d", text)
    usernames = re.findall(r"(?<!\w)@[A-Za-z0-9_]{5,}", text)
    return ", ".join(dict.fromkeys([p.strip() for p in phones] + usernames))


def parse_lead(text: str) -> dict:
    amount, cur, raw = extract_budget(text)
    return {
        "budget": amount,
        "currency": cur,
        "budget_raw": raw,
        "property_type": extract_type(text),
        "districts": extract_districts(text),
        "contacts_in_text": extract_contacts(text),
    }
