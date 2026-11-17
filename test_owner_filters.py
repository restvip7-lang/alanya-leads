from owner_filters import is_owner_listing, parse_listing, text_key

OWNER = [
    "Продаю свою квартиру 2+1 в Махмутларе, 110 м², 3 этаж, вид на море. Цена 145 000 €. Агентам не беспокоить. +90 555 111 22 33",
    "Продам квартиру 1+1 в Оба от собственника, 55 м2, мебель остаётся, 98 000 евро. Пишите @olga_owner",
    "Собственник продаёт апартаменты 1+1 в Тосмуре, 120к€, без комиссии",
    "Selling my 2+1 flat in Kestel, 95 sqm, 160.000 EUR, no agents please",
    "Sahibinden satılık daire 3+1, Alanya Oba, 6.500.000 TL",
    "Продается квартира 3+1 в Джикджилли, 150 кв.м, 210 000 $, без посредников",
]
NOT_OWNER = [
    "Агентство Sun Homes предлагает квартиры 1+1 в Махмутларе от 85 000 €. Рассрочка!",
    "Продажа квартир от застройщика в Оба, 1+1 и 2+1, ID 2345",
    "Продам виллу 4+1 в Каргыджаке, 650 000 €",
    "Сдам квартиру 1+1 в Махмутларе, 700 € в месяц",
    "Куплю квартиру 2+1 в Оба до 150 000 €",
    "Продам диван и холодильник, 300 €",
    "Продаю квартиру 2+1 в Махмутларе",  # нет цены: не понятно, что продаётся
    "Новые объекты: 1+1 — 80 000 €, 2+1 — 120 000 €, 3+1 — 180 000 €, Махмутлар, продажа",
    "Продам участок земли под застройку в Авсалларе, 90 000 €",
    "For sale: 1+1 apartment in Oba, 99.000 EUR. Our agency will help with the deal",
]


def test_owner_listings_pass():
    for t in OWNER:
        assert is_owner_listing(t), t


def test_agencies_and_others_rejected():
    for t in NOT_OWNER:
        assert not is_owner_listing(t), t


def test_agency_by_author_name():
    t = OWNER[1]
    assert is_owner_listing(t, "Ольга")
    assert not is_owner_listing(t, "Alanya Real Estate")
    assert not is_owner_listing(t, "Мария | Недвижимость Алании")


def test_parse_listing():
    p = parse_listing(OWNER[0])
    assert (p["rooms"], p["area"], p["district"], p["price"], p["currency"]) == ("2+1", 110, "Махмутлар", 145000, "EUR")
    assert p["owner_said"]
    assert parse_listing(OWNER[3])["district"] == "Кестель"
    assert parse_listing(OWNER[5])["area"] == 150


def test_same_text_in_two_chats_same_key():
    assert text_key("Продам 1+1, 90 000 €!") == text_key("продам 1+1 90000 €")


def test_dup_keys():
    from filters import dup_keys
    from owner_filters import listing_dup_keys
    a = "Куплю квартиру 2+1 в Махмутларе, бюджет до 150 000 €, рассмотрю вторичку"
    b = "🔥 куплю квартиру 2+1 в Махмутларе бюджет до 150000 € рассмотрю вторичку!!"
    assert dup_keys(a, 1) == dup_keys(b, 1)            # тот же человек, другой чат и смайлики
    assert dup_keys(a, 1)[-1] == dup_keys(b, 2)[-1]    # тот же текст от другого человека
    assert dup_keys("Куплю 1+1", 1) == [dup_keys("Куплю 1+1", 1)[0]]  # короткий текст склеиваем только у одного автора
    p = parse_listing(OWNER[0])
    k1 = listing_dup_keys(OWNER[0], 5, p)
    k2 = listing_dup_keys("Продаю 2+1 Махмутлар, 145000 евро, звоните", 5, parse_listing("Продаю 2+1 Махмутлар, 145000 евро"))
    assert k1[-1] == k2[-1] == "flat:5:Махмутлар:2+1:145000"


def test_same_request_other_language_is_duplicate():
    from parser import make_lead
    tr = "Alanya'da vatandaşlık için daire arıyorum. Sadece 2+1, bölge: Kleopatra veya Oba. Satın almak istiyorum"
    ru = "Куплю апартаменты в Алании, только 2+1, районы: Клеопатра или Оба, бюджет до 130 000 €"
    a = make_lead(date="", source="telegram", chat="c", author="Nikola", author_profile="", text=tr, link="", uid="1", author_id=7)
    b = make_lead(date="", source="telegram", chat="c", author="Nikola", author_profile="", text=ru, link="", uid="2", author_id=7)
    assert set(a["dup_keys"]) & set(b["dup_keys"])
