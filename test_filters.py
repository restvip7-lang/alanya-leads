from filters import is_buy_request, parse_lead

BUY = [
    "Куплю квартиру 2+1 в Махмутларе, бюджет до 150 000 €, рассмотрю вторичку",
    "Ищем квартиру 1+1 в Оба или Тосмуре до 120к евро, без посредников. Пишите @ivan_buyer",
    "Хочу купить виллу в Каргыджаке, бюджет 500k$",
    "Looking to buy a 2+1 apartment in Kestel, budget up to 180.000 EUR",
    "Daire satın almak istiyorum, Alanya merkez, 3+1",
    "Куплю 1+1 недорого, Авсаллар или Конаклы. +90 555 123 45 67",
    "Куплю квартиру в Алании за наличные, рассмотрю варианты до 90 тыс евро",
]
NOT_BUY = [
    "Продам квартиру 2+1 в Махмутларе, 140 000 €",
    "Сдам 1+1 в Оба на долгосрок, 700 евро",
    "Сниму квартиру в Алании на зиму",
    "Satılık daire, Alanya, 3+1",
    "Кто знает хорошего стоматолога в Алании?",
    "Ищу квартиру в аренду в Тосмуре",
    "Куплю USDT, личная встреча, расчет сразу.",
    "Приветствую. Куплю U.S.D.T из рук в руки, предложу хороший курс",
    "Куплю машину в Алании до 10 000 €",
    "Куплю диван в квартиру, недорого",
    "Куплю iPhone 15, Махмутлар",
]

ok = True
for t in BUY:
    r = is_buy_request(t)
    ok &= r
    print("BUY " if r else "MISS", t, "->", parse_lead(t))
for t in NOT_BUY:
    r = is_buy_request(t)
    ok &= not r
    print("FALSE+" if r else "skip ", t)
print("ALL OK" if ok else "FAILURES")
