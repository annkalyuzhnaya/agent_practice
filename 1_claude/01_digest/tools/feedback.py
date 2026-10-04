"""Отметки человека по позициям выпуска: «в базу», «в задачи», «не интересно» — журнал hub/digest/marks.md.

  python tools/feedback.py add --id g-20261002-2 --mark task [--note "текст"]
        записать отметку (kb | task | skip); для task — дописать строку в hub/tasks.md
  python tools/feedback.py stats [--days 30] [--date ГГГГ-ММ-ДД]
        сводка отметок по темам и источникам и подсказки для «ухода за темами»

Скрипт профиль не меняет: правку тем и источников предлагает агент, решает человек.
"""
import argparse
import re
from collections import defaultdict
from datetime import date, timedelta

import digestlib as dl

NAMES = {"kb": "в базу", "task": "в задачи", "skip": "не интересно"}
HEADER = ("# Отметки по выпускам\n\nЧто человек решил по позициям дайджеста. Агенты только дописывают строки.\n\n"
          "| Дата | ID | Заголовок | Тема | Источник | Отметка | Что сделано |\n|---|---|---|---|---|---|---|\n")
TASKS = dl.HUB / "tasks.md"


def rows():
    out = []
    if dl.MARKS.exists():
        for line in dl.MARKS.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 6 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
                out.append(dict(zip(("date", "id", "title", "topic", "source", "mark", "done"), cells + [""])))
    return out


def find_item(item_id):
    m = re.fullmatch(r"g-(\d{4})(\d{2})(\d{2})-(\d+)", item_id)
    if not m:
        raise SystemExit("ID позиции — вида g-ГГГГММДД-N (он показан на странице и в отчёте агента).")
    issue = dl.parse_issue(dl.latest_issue("-".join(m.groups()[:3])))
    for item in issue["items"]:
        if item["id"] == item_id:
            return issue, item
    raise SystemExit(f"В выпуске {issue['date']} нет позиции {item_id} (всего позиций: {len(issue['items'])}).")


def cmd_add(args):
    issue, item = find_item(args.id)
    mark = NAMES[args.mark]
    if any(r["id"] == args.id and r["mark"] == mark for r in rows()):
        print(f"Отметка «{mark}» по {args.id} уже записана — не дублирую.")
        return
    cell = lambda s: (s or "").replace("|", "/")
    done = args.note or ""
    if args.mark == "task":
        what = dl.plain(item["action"]) or f"Разобрать публикацию «{item['title']}»"
        what = (what[:1].upper() + what[1:]).rstrip(".")
        dl.append_line(TASKS, f"| {dl.today()} | {cell(what)} | владелец | срок не назван | новое | hub/digest/{issue['date']}.md | |")
        done = (done + "; " if done else "") + "строка в hub/tasks.md"
    elif args.mark == "kb" and not done:
        done = "заметку в hub/kb/публикации/ пишет агент"
    elif args.mark == "skip" and not done:
        done = "учтётся при уходе за темами"
    dl.append_line(dl.MARKS, f"| {dl.today()} | {args.id} | {cell(item['title'])} | {cell(item['topic'])} | {cell(item['source'])} | {mark} | {cell(done)} |", HEADER)
    print(f"Записано: {args.id} «{item['title'][:60]}» — {mark}" + (f" ({done})" if done else ""))


def table(title, stat):
    print(f"\n{title}:")
    if not stat:
        print("  отметок нет")
    for name, c in sorted(stat.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"  {name or '(не указано)'}: в базу {c['в базу']}, в задачи {c['в задачи']}, не интересно {c['не интересно']}")


def cmd_stats(args):
    day = dl.iso(args.date) if args.date else date.today()
    since = (day - timedelta(days=args.days)).isoformat()
    data = [r for r in rows() if r["date"] >= since]
    topics, sources = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    for r in data:
        topics[r["topic"]][r["mark"]] += 1
        sources[r["source"]][r["mark"]] += 1
    print(f"Отметки за {args.days} дн. (с {since}): {len(data)}")
    table("По темам", topics)
    table("По источникам", sources)
    hints = []
    for kind, stat in (("тема", topics), ("источник", sources)):
        for name, c in stat.items():
            useful = c["в базу"] + c["в задачи"]
            if c["не интересно"] >= 3 and useful == 0:
                hints.append(f"{kind} «{name}»: {c['не интересно']} раз «не интересно» и ни одной полезной отметки — предложить убрать или сузить")
            elif c["не интересно"] >= 2 and c["не интересно"] > 2 * useful:
                hints.append(f"{kind} «{name}»: «не интересно» заметно чаще полезного — предложить уточнить формулировку")
            elif useful >= 3 and c["не интересно"] == 0:
                hints.append(f"{kind} «{name}»: {useful} полезных отметок подряд — предложить поднять приоритет")
    profile = dl.read_profile()
    marked = {dl.norm_title(t) for t in topics}
    for t in profile["topics"]:
        if len(data) >= 5 and not any(dl.norm_title(t) in m or m in dl.norm_title(t) for m in marked if m):
            hints.append(f"тема «{t}»: за период ни одной отметки — спросить владельца, нужна ли она")
    print("\nПодсказки для ухода за темами (решает человек):")
    for h in hints or ["оснований менять профиль нет"]:
        print("  - " + h)


def main():
    dl.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--id", required=True)
    p.add_argument("--mark", required=True, choices=sorted(NAMES))
    p.add_argument("--note")
    p.set_defaults(fn=cmd_add)
    p = sub.add_parser("stats")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--date")
    p.set_defaults(fn=cmd_stats)
    args = ap.parse_args()
    dl.need_hub()
    args.fn(args)


if __name__ == "__main__":
    main()
