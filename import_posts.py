"""Импорт постов, скопированных вручную (Facebook-группы и любые другие места).

Скопируйте посты из группы в текстовый файл, разделяя их строкой из трёх дефисов:

    Ищем 2+1 в Махмутларе до 150к евро
    https://www.facebook.com/groups/123/posts/456
    ---
    Куплю виллу в Каргыджаке...
    https://www.facebook.com/groups/123/posts/789

Ссылку на пост добавлять желательно (по ней Асель откроет пост), но не обязательно.

Запуск:  python import_posts.py facebook.txt --group "Русские в Алании"
"""
import argparse
import hashlib
import re
from datetime import datetime

from filters import is_buy_request
from parser import make_lead, read_config
from storage import load_output

URL = re.compile(r"https?://\S+")


def split_posts(raw):
    for block in re.split(r"^\s*-{3,}\s*$", raw, flags=re.M):
        block = block.strip()
        if not block:
            continue
        m = URL.search(block)
        link = m.group(0) if m else ""
        text = URL.sub("", block).strip() if m else block
        yield text, link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--group", default="", help="название группы")
    ap.add_argument("--source", default="facebook")
    ap.add_argument("--config", default="config.ini")
    ap.add_argument("--all", action="store_true", help="сохранить все посты, без фильтра")
    args = ap.parse_args()

    cfg = read_config(args.config)
    store = load_output(cfg)
    raw = open(args.file, encoding="utf-8").read()
    total = skipped = 0
    for text, link in split_posts(raw):
        total += 1
        if not args.all and not is_buy_request(text):
            skipped += 1
            continue
        key = link or hashlib.sha1(" ".join(text.split()).encode()).hexdigest()[:16]
        store.add(make_lead(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"), source=args.source, chat=args.group,
            author="", author_profile="", text=text, link=link, uid=f"{args.source}:{key}",
        ))
    store.save()
    print(f"Постов: {total}, не заявки: {skipped}, новых заявок: {store.added}")


if __name__ == "__main__":
    main()
