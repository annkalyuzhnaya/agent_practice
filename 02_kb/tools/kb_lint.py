"""Уход за базой знаний: битые ссылки, заметки без связей, возможные дубли, неразобранное входящее.

  python tools/kb_lint.py check            показать список проблем
  python tools/kb_lint.py check --write    то же + записать список в hub/kb/_уход.md
  python tools/kb_lint.py summary --days 7 сводка недели: что добавлено, какие противоречия открыты
  python tools/kb_lint.py summary --out .cache/week.txt   сводка в файл (для отправки ботом)

Скрипт ничего не исправляет и не удаляет: он только показывает. Что делать с каждым пунктом, решает человек.
Пункты, которые человек решил оставить, перечислены в hub/kb/_уход.md в разделе «Оставить как есть» — их скрипт не показывает.
"""
import argparse
import re
import sys
from datetime import date, datetime, timedelta

import kblib

KEEP_HEAD = "## Оставить как есть"
WORD = re.compile(r"[A-Za-zА-Яа-яЁё]{4,}")


def keep_list():
    """Пункты, которые человек велел не трогать: строки «- вид | заметка | цель» под заголовком «Оставить как есть»."""
    if not kblib.CARE.exists():
        return [], set()
    text = kblib.read(kblib.CARE)
    if KEEP_HEAD not in text:
        return [], set()
    lines = [ln.strip() for ln in text.split(KEEP_HEAD, 1)[1].splitlines() if ln.strip().startswith("- ")]
    keys = {tuple(p.strip(" `") for p in ln[2:].split("|")) for ln in lines}
    return lines, keys


def tokens(title):
    return {w.lower()[:6] for w in WORD.findall(title)}


def find():
    """Список проблем: словари {id, kind, note, target, text, advice}."""
    notes = kblib.notes()
    stems = kblib.all_stems()
    by_stem = {n["stem"]: n for n in notes}
    items = []

    def add(kind, note, target, text, advice):
        items.append({"id": kblib.short_id("k", kind, note, target), "kind": kind, "note": note, "target": target,
                      "text": text, "advice": advice})

    incoming = {n["stem"]: 0 for n in notes}
    for n in notes:
        for link in n["links"]:
            name = link.split("/")[-1]
            if link not in stems and name not in stems:
                add("битая ссылка", n["stem"], link, f"ссылка [[{link}]] никуда не ведёт",
                    "исправить имя в ссылке или создать заметку с таким именем")
            elif name in incoming and name != n["stem"]:
                incoming[name] += 1

    main = [n for n in notes if not n["inbox"]]
    for n in main:
        out = [l for l in n["links"] if l.split("/")[-1] in by_stem and l.split("/")[-1] != n["stem"]]
        if not out and not incoming[n["stem"]]:
            add("без связей", n["stem"], "", "на заметку никто не ссылается и она ни на что не ссылается",
                "добавить блок «Связано: [[…]]» или пометку «связей пока нет»")
        if not n["has_meta"] or not n["meta"].get("type"):
            add("нет шапки", n["stem"], "", "у заметки нет шапки с типом (type)", "дописать шапку по шаблону из kb/_шаблоны")
        else:
            want = kblib.TYPE_FOLDERS.get(str(n["meta"].get("type")).lower())
            if want and n["folder"] and n["folder"] != want:
                add("не в своей папке", n["stem"], want, f"тип «{n['meta']['type']}», а лежит в «{n['folder']}»",
                    f"перенести в kb/{want}/ (в Obsidian — перетаскиванием, ссылки обновятся сами)")
        agent = str(n["meta"].get("agent") or "")
        if n["has_meta"] and agent and agent != "человек" and not n["sources"]:
            add("нет источника", n["stem"], "", "заметку создал агент, а источник (sources) не указан",
                "дописать источник или пометить факты «не подтверждено»")

    for i, a in enumerate(main):
        for b in main[i + 1:]:
            ta, tb = tokens(a["title"]), tokens(b["title"])
            na, nb = set(re.findall(r"\d+", a["title"])), set(re.findall(r"\d+", b["title"]))
            if not ta or not tb or (na and nb and na != nb):  # разные даты и номера в заголовках — разные документы
                continue
            same = len(ta & tb) / len(ta | tb)
            if same >= 0.6 or (a["type"] == b["type"] == "контрагент" and (ta <= tb or tb <= ta)):
                add("возможный дубль", a["stem"], b["stem"], f"похожие заголовки: «{a['title']}» и «{b['title']}»",
                    "объединить в одну заметку или подтвердить, что это разные темы")

    for n in notes:
        if n["inbox"] and not n["processed"]:
            add("не разобрано", n["stem"], "", "файл во входящем ещё не оформлен в заметку",
                "сказать Библиотекарю «разбери входящее»")

    keys = keep_list()[1]
    return [it for it in items if (it["kind"], it["note"], it["target"]) not in keys], notes


def cmd_check(args):
    kblib.need_hub()
    items, notes = find()
    kinds = {}
    for it in items:
        kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
    print(f"Заметок в базе: {len([n for n in notes if not n['inbox']])}; во входящем: {len([n for n in notes if n['inbox']])}")
    if not items:
        print("Проблем не найдено.")
    for it in items:
        where = f" → {it['target']}" if it["target"] else ""
        print(f"- {it['kind']}: {it['note']}{where} — {it['text']}. Предлагается: {it['advice']}")
    if kinds:
        print("Итого: " + ", ".join(f"{k} — {v}" for k, v in sorted(kinds.items())))
    if args.write:
        keep = keep_list()[0]
        lines = ["# Уход за базой", "",
                 "Список собирает Библиотекарь (в Claude Code — командой `python tools/kb_lint.py check --write`).",
                 "Ничего не исправляется само: скажите в чате «исправь пункт …» или «оставь как есть».", "",
                 f"Проверено: {date.today().isoformat()}", "",
                 "| Вид | Заметка | Что не так | Что предлагается |", "|---|---|---|---|"]
        for it in items:
            target = f" → [[{it['target']}]]" if it["target"] and it["kind"] != "не в своей папке" else ""
            lines.append(f"| {it['kind']} | [[{it['note']}]]{target} | {it['text']} | {it['advice']} |")
        lines += ["", KEEP_HEAD, "", "Формат строки: `- вид | заметка | цель` (цель — вторая заметка или ссылка; если её нет — пусто)."]
        lines += keep or []
        kblib.write(kblib.CARE, "\n".join(lines) + "\n")
        print("Записано: hub/kb/_уход.md")
    if args.strict and items:
        sys.exit(1)


def note_date(n):
    try:
        return datetime.strptime(n["date"][:10], "%Y-%m-%d").date()
    except ValueError:
        return datetime.fromtimestamp(n["path"].stat().st_mtime).date()


def cmd_summary(args):
    kblib.need_hub()
    items, notes = find()
    since = date.today() - timedelta(days=args.days)
    fresh = [n for n in notes if not n["inbox"] and note_date(n) >= since]
    waiting = [n for n in notes if n["inbox"] and not n["processed"]]
    open_rows = [r for r in kblib.conflicts() if r["open"]]
    care = [it for it in items if it["kind"] != "не разобрано"]
    lines = [f"База знаний: сводка за {args.days} дн. (на {date.today().isoformat()})", "",
             f"Добавлено заметок: {len(fresh)}"]
    lines += [f"  • {n['title']} ({n['type']})" for n in fresh[:15]]
    if len(fresh) > 15:
        lines.append(f"  … и ещё {len(fresh) - 15}")
    lines += ["", f"Открытых противоречий: {len(open_rows)}"]
    lines += [f"  • {r['fact']} — А: {r['a']} / Б: {r['b']}" for r in open_rows[:10]]
    lines += ["", f"Во входящем ждут разбора: {len(waiting)}", f"Пунктов ухода (ссылки, связи, дубли): {len(care)}"]
    if open_rows:
        lines += ["", "Противоречия закрываете только вы: на странице «База знаний» или словами в чате."]
    text = "\n".join(lines) + "\n"
    if args.out:
        out = kblib.Path(args.out) if kblib.Path(args.out).is_absolute() else kblib.ROOT / args.out
        kblib.write(out, text)
        print(f"Сводка записана: {args.out}")
    else:
        print(text, end="")


def main():
    kblib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("--write", action="store_true", help="записать список в hub/kb/_уход.md")
    p.add_argument("--strict", action="store_true", help="код возврата 1, если есть проблемы")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("summary")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_summary)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
