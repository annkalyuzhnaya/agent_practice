"""Память «уже видел» — hub/digest/seen.md. Сравнивает ссылки без учёта http/https, www, рекламных меток и хвостового «/».

  python tools/seen.py check ССЫЛКА [ССЫЛКА ...]     новая или уже была (и когда)
  python tools/seen.py add --url ССЫЛКА --title "Заголовок" [--date ГГГГ-ММ-ДД]
  python tools/seen.py sync [ГГГГ-ММ-ДД]             дописать в память все ссылки выпуска (по умолчанию — последнего)
  python tools/seen.py stats                         сколько записей, повторы, записи по месяцам

Файл только дополняется: существующие строки скрипт не меняет и не удаляет.
"""
import argparse
import re
from collections import Counter

import digestlib as dl

HEADER = "# Уже видел\n\nПамять Обозревателя: что уже попадало в выпуски. Формат строки: `- дата | ссылка | заголовок`.\n\n"


def add(url, title, day):
    _, index = dl.read_seen()
    key = dl.norm_url(url)
    if key in index:
        return False
    dl.append_line(dl.SEEN, f"- {day} | {url} | {title.replace('|', '/')}", HEADER)
    return True


def cmd_check(args):
    _, index = dl.read_seen()
    new = 0
    for url in args.urls:
        hit = index.get(dl.norm_url(url))
        if hit:
            print(f"уже видел  {url}  — {hit[0]}, «{hit[2]}»")
        else:
            new += 1
            print(f"новая      {url}")
    print(f"Итого: новых {new}, уже виденных {len(args.urls) - new}")


def cmd_add(args):
    added = add(args.url, args.title, args.date or dl.today())
    print("Записано в память." if added else "Эта ссылка уже есть в памяти — не дублирую.")


def cmd_sync(args):
    issue = dl.parse_issue(dl.latest_issue(args.date))
    added = skipped = 0
    for item in issue["items"]:
        if add(item["url"], item["title"], issue["date"]):
            added += 1
        else:
            skipped += 1
    # ссылки из «Пропущено» тоже запоминаем: иначе слабые материалы вернутся в следующем выпуске
    for line in issue["skipped"]:
        for url in dl.URL_RE.findall(line):
            title = re.sub(r"\s*\(\s*\)", "", dl.URL_RE.sub("", line)).strip(" —-:;,.()")[:120] or "пропущено"
            if add(url, f"(пропущено) {title}", issue["date"]):
                added += 1
            else:
                skipped += 1
    print(f"Выпуск {dl.rel(issue['path'])}: дописано в память {added}, уже были {skipped}")


def cmd_stats(_):
    rows, index = dl.read_seen()
    print(f"Записей: {len(rows)}; разных ссылок: {len(index)}; повторов: {len(rows) - len(index)}")
    for month, n in sorted(Counter(d[:7] for d, _, _ in rows).items()):
        print(f"  {month}: {n}")


def main():
    dl.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("urls", nargs="+")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("add")
    p.add_argument("--url", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--date")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("sync")
    p.add_argument("date", nargs="?")
    p.set_defaults(fn=cmd_sync)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    args = ap.parse_args()
    dl.need_hub()
    args.fn(args)


if __name__ == "__main__":
    main()
