"""Объявления о ПРОДАЖЕ квартир в Алании от собственников (не агентств) и их параметры."""
import re

from filters import DISTRICTS, dup_keys, extract_budget, extract_contacts, extract_districts, text_key

# Слова продавца (RU / EN / TR)
SALE_PATTERNS = [
    r"\bпрода[мюё]\w*", r"\bпродаж\w*", r"\bв\s+продаже\b", r"\bпродаётся\b", r"\bпродается\b",
    r"\bfor\s+sale\b", r"\bselling\b", r"\bsell\b", r"\bsatılık\b", r"\bsatilik\b", r"\bsatıyorum\b", r"\bsahibinden\b",
]

# Только квартиры: виллы, дома, участки и коммерцию не берём
FLAT_HINTS = [
    r"квартир", r"апартамент", r"пентхаус", r"дуплекс", r"студи", r"\b\d\s*\+\s*\d\b",
    r"apartment", r"\bflat\b", r"penthouse", r"duplex", r"\bdaire\b", r"\brezidans\b",
]
NOT_FLAT = [
    r"\bвилл\w*", r"\bvilla\b", r"\bчастный\s+дом\b", r"\bдом\s+(?:с\s+участком|на\s+участке)", r"\bземл\w*\s+участ\w*",
    r"\bучаст\w*\s+(?:земл|под)", r"\barsa\b", r"\bmüstakil\b", r"\bмагазин\w*", r"\bкоммерческ\w*", r"\bофис\w*",
    r"\bdükkan\b",
]

# Ищут, а не продают; аренда; продажа вещей и валюты
NOT_SALE = [
    r"\bкуплю\b", r"\bищу\b(?!\s+покупател)", r"\bищем\b(?!\s+покупател)", r"\bхочу\s+купить", r"\bwant\s+to\s+buy\b", r"\blooking\s+for\b(?!\s+(?:a\s+)?buyer)",
    r"\balmak\s+istiyorum\b", r"\barıyorum\b",
    r"\bсдам\b", r"\bсдаю\b", r"\bсда[её]тся\b", r"\bаренд\w*", r"\bсниму\b", r"\bпосуточно\b", r"\bдолгосрок\w*",
    r"\bfor\s+rent\b", r"\brent(?:al)?\b", r"\bkiralık\b", r"\bkiralik\b",
    r"\bв\s+месяц\b", r"/\s*мес", r"\bпомесячн\w*", r"\bper\s+month\b", r"\bmonthly\b", r"\baylık\b",
    r"usdt", r"крипт\w*",
]

# Признаки агентства, риелтора или застройщика
AGENCY_PATTERNS = [
    r"агентств\w*", r"агент\b", r"риелтор\w*", r"риэлтор\w*", r"ри[еэ]лт\w*", r"\bкомисси\w*", r"\bкомиссионн\w*",
    r"застройщик\w*", r"девелопер\w*", r"от\s+застройщика", r"\bрассрочк\w*", r"\bновостро\w*", r"\bжк\b",
    r"наш\w*\s+(?:объект|компани|агентств|менеджер|офис)", r"\bподбер[её]м\b", r"\bподбор\s+недвиж\w*",
    r"\bid\s*(?:объекта)?\s*[:#№]?\s*\d+", r"\bартикул\w*", r"\bкод\s+объекта\b", r"\bобъект\s*№\s*\d+",
    r"\bмы\s+(?:поможем|предлагаем|подберём|подберем)", r"\bпредлагаем\b", r"\bуслуг\w*",
    r"real\s*estate", r"\brealty\b", r"\bagency\b", r"\bagent\b", r"\brealtor\w*", r"\bcommission\b",
    r"\bdeveloper\b", r"\binstallment\w*", r"\bemlak\b", r"\bemlakçı\w*", r"\bgayrimenkul\b", r"\btaksit\w*",
    r"\bproperty\s+(?:group|company)\b", r"\bподписывайтесь\b", r"\bнаш\s+канал\b", r"\bпишите\s+в\s+директ\b",
    r"#\w*(?:недвижимость|realestate|emlak)\w*",
]

# Слова собственника: «от собственника», «без посредников», «свою квартиру», sahibinden
OWNER_PATTERNS = [
    r"собственник\w*", r"\bхозя\w*", r"без\s+посредник\w*", r"без\s+комисси\w*", r"\bсвою\s+(?:квартир|апартамент)",
    r"\bмою\s+(?:квартир|апартамент)", r"\bsahibinden\b", r"\bfrom\s+(?:the\s+)?owner\b", r"\bby\s+owner\b",
    r"\bowner\b", r"\bmy\s+(?:apartment|flat)\b",
]

# Собственники пишут «агентам не беспокоить», «без комиссии»: это не признак агентства, убираем до проверки
NO_AGENTS = re.compile(
    r"(?:без|кроме)\s+(?:агент\w*|посредник\w*|комисси\w*|ри[еэ]лтор\w*)|"
    r"(?:агент\w*|ри[еэ]лтор\w*|посредник\w*)\s*(?:,\s*\w+\s*)?(?:просьба\s+)?(?:не\s+беспоко\w*|не\s+пис\w*|не\s+звон\w*|мимо)|"
    r"\bno\s+(?:agents?|agencies|realtors?|commission)\b|\bagents?\s+(?:please\s+)?do\s+not\b|"
    r"\bemlakçı\w*\s+(?:aramasın|rahatsız\s+etmesin)",
    re.I,
)

# В имени автора: так подписываются агентства
AGENCY_NAME = re.compile(
    r"недвиж|realty|real\s*estate|estate|property|propert|homes?\b|group|invest|emlak|gayrimenkul|агент|риелт|риэлт|"
    r"construction|insaat|inşaat|development|consult|броке|broker",
    re.I,
)

_c = lambda ps: [re.compile(p, re.I) for p in ps]
_sale, _flat, _not_flat, _not_sale, _agency, _owner = map(
    _c, (SALE_PATTERNS, FLAT_HINTS, NOT_FLAT, NOT_SALE, AGENCY_PATTERNS, OWNER_PATTERNS))

MIN_PRICE = 30_000          # меньше: аренда или не квартира
MAX_LISTINGS_PER_AUTHOR = 2  # больше разных квартир за один запуск: почти наверняка агент


def is_owner_listing(text: str, author: str = "") -> bool:
    if not text or len(text) < 20:
        return False
    if not any(p.search(text) for p in _sale):
        return False
    if not any(p.search(text) for p in _flat) or any(p.search(text) for p in _not_flat):
        return False
    clean = NO_AGENTS.sub(" ", text)
    if any(p.search(clean) for p in _not_sale) or any(p.search(clean) for p in _agency):
        return False
    if author and AGENCY_NAME.search(author):
        return False
    # В одном посте 3 и больше планировок или цен: это подборка агентства
    if len(set(re.findall(r"\b\d\s*\+\s*\d\b", text))) >= 3:
        return False
    price = extract_budget(text, min_amount=1)[0]
    return price is not None and price >= MIN_PRICE


def extract_rooms(text: str) -> str:
    m = re.search(r"\b(\d)\s*\+\s*(\d)\b", text)
    if m:
        return f"{m.group(1)}+{m.group(2)}"
    if re.search(r"студи|studio|stüdyo", text, re.I):
        return "1+0"
    if re.search(r"пентхаус|penthouse", text, re.I):
        return "пентхаус"
    if re.search(r"дуплекс|duplex|dubleks", text, re.I):
        return "дуплекс"
    return ""


def extract_area(text: str):
    m = re.search(r"(\d{2,3})(?:[.,]\d+)?\s*(?:м²|м2|кв\.?\s*м|квм|m²|m2|sqm|кв\.?\b)", text, re.I)
    return int(m.group(1)) if m and 15 <= int(m.group(1)) <= 500 else None


def parse_listing(text: str) -> dict:
    price, cur, raw = extract_budget(text)
    districts = extract_districts(text)
    return {
        "price": price,
        "currency": cur,
        "price_raw": raw,
        "rooms": extract_rooms(text),
        "area": extract_area(text),
        "district": districts.split(", ")[0] if districts else "",
        "owner_said": bool(NO_AGENTS.search(text)) or any(p.search(text) for p in _owner),
        "contacts_in_text": extract_contacts(text),
    }


def listing_dup_keys(text: str, author_id, p: dict) -> list:
    """Плюс к ключам по тексту: тот же автор, район, планировка и цена = та же квартира, даже если текст переписан."""
    keys = dup_keys(text, author_id)
    if author_id and p.get("price") and p.get("rooms"):
        keys.append(f"flat:{author_id}:{p.get('district')}:{p['rooms']}:{p['price']}")
    return keys


__all__ = ["is_owner_listing", "parse_listing", "text_key", "listing_dup_keys", "DISTRICTS", "MAX_LISTINGS_PER_AUTHOR"]
