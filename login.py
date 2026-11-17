"""Получить строку сессии Telegram для облачного запуска (GitHub Actions).

Запустите один раз на своём компьютере:  python login.py
Введите api_id и api_hash (с my.telegram.org), телефон и код из Telegram.
Скрипт напечатает длинную строку: её нужно вставить в секрет TG_SESSION в GitHub.

ВНИМАНИЕ: эта строка даёт полный доступ к вашему аккаунту Telegram. Никому её не отправляйте,
не вставляйте в чаты и файлы репозитория, только в секреты GitHub.
Если строка утекла: Telegram → Настройки → Устройства → завершите сеанс «alanya-leads».
"""
from telethon.sessions import StringSession
from telethon.sync import TelegramClient


def main():
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()
    with TelegramClient(StringSession(), api_id, api_hash,
                        device_model="alanya-leads", app_version="1.0") as client:
        me = client.get_me()
        print(f"\nВошли как {me.first_name} (@{me.username or '-'}).")
        print("\nСкопируйте строку ниже целиком в секрет TG_SESSION:\n")
        print(client.session.save())
        print()


if __name__ == "__main__":
    main()
