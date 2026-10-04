"""Скрипты кейса «Подготовка к встрече». Только стандартная библиотека Python.

  python tools/meetings.py upcoming [--days 3]        встречи ближайших дней: есть ли бриф; прошедшие без мемо
  python tools/meetings.py tasks [--party "название"] [--tg]   контроль задач из мемо: просрочено / на неделе / позже
  python tools/meetings.py check ФАЙЛ                 проверка брифа или мемо: разделы, объём, источники, пометки
  python tools/meetings.py print ФАЙЛ [--out ФАЙЛ]    печатная версия на одну страницу A4 (HTML, открывается в браузере)
  python tools/meetings.py tg ФАЙЛ_БРИФА              текст «завтра встреча» для Telegram: заголовок и 5 строк «Главного»
  python tools/meetings.py eval ФАЙЛ [--cases demo/evals.json]   приёмка на учебном наборе: что обязано быть в тексте

Общий ключ --today ГГГГ-ММ-ДД подменяет сегодняшнюю дату (для учебного набора: --today 2026-10-06).
Скрипты только читают шину; пишет один `print` — файл в hub/meetings/print/.
"""
import argparse
import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
MEETINGS = HUB / "meetings"
DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

BRIEF_SECTIONS = ["Главное", "Кто это", "История отношений", "Интересы сторон", "Повестка", "Вопросы",
                  "Карта возражений", "Что нельзя обещать", "Не подтверждено"]
MEMO_SECTIONS = ["Участники", "Решения", "Договорённости", "Открытые вопросы", "Задачи", "Сверка с брифом",
                 "Следующий контакт"]
BRIEF_WORDS = 500


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def need_hub():
    if not HUB.exists():
        sys.exit("Нет папки hub/ — сначала выполните: python tools/setup.py")


def parse_day(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"Дата «{text}» не в формате ГГГГ-ММ-ДД")


def table(path):
    """Строки первой таблицы markdown-файла как списки ячеек (без шапки и разделителя)."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) or not any(cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def body(path):
    """Текст файла без шапки (frontmatter)."""
    text = path.read_text(encoding="utf-8-sig")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            text = text[end + 4:]
    return text.lstrip("\n")


def sections(text):
    """{заголовок второго уровня: текст раздела} в порядке появления."""
    out, name, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if name is not None:
                out[name] = "\n".join(buf).strip()
            name, buf = m.group(1), []
        elif name is not None:
            buf.append(line)
    if name is not None:
        out[name] = "\n".join(buf).strip()
    return out


def find_section(secs, title):
    for name, text in secs.items():
        if name.lower().startswith(title.lower()):
            return text
    return None


def bullets(text):
    return [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", l).strip() for l in (text or "").splitlines()
            if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", l)]


def links(cell):
    return re.findall(r"\[\[([^\]|]+)", cell)


# ---------- календарь ----------

def calendar():
    out = []
    for cells in table(HUB / "calendar.md"):
        cells += [""] * (6 - len(cells))
        m = re.match(r"(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2}))?", cells[0])
        if not m:
            continue
        refs = links(cells[5])
        brief = next((r for r in refs if "бриф" in r.lower()), "")
        memo = next((r for r in refs if "мемо" in r.lower()), "")
        out.append({"day": parse_day(m.group(1)), "time": m.group(2) or "", "party": cells[1], "goal": cells[2],
                    "people": cells[3], "status": cells[4], "brief": brief, "memo": memo})
    return sorted(out, key=lambda x: (x["day"], x["time"]))


def file_state(ref, day, kind):
    """Есть ли файл: по ссылке из календаря или по дате встречи в имени."""
    if ref:
        return ("есть", ref) if (MEETINGS / f"{ref}.md").exists() else ("ссылка есть, файла нет", ref)
    found = sorted(p.stem for p in MEETINGS.glob(f"*{day:%Y-%m-%d}*_{kind}.md")) if MEETINGS.exists() else []
    return ("файл есть, ссылка в календарь не вписана", found[0]) if found else ("нет", "")


def cmd_upcoming(args):
    need_hub()
    today = args.today
    last = today + timedelta(days=args.days - 1)
    items = calendar()
    soon = [m for m in items if today <= m["day"] <= last and m["status"] != "отменена"]
    past = [m for m in items if today - timedelta(days=14) <= m["day"] < today and m["status"] != "отменена"]
    print(f"Сегодня {today:%Y-%m-%d} ({DAYS[today.weekday()]}). Встречи до {last:%Y-%m-%d} включительно: {len(soon)}")
    missing = 0
    for m in soon:
        state, ref = file_state(m["brief"], m["day"], "бриф")
        missing += state != "есть"
        mark = "бриф есть" if state == "есть" else "БЕЗ БРИФА" if state == "нет" else f"бриф: {state}"
        print(f"  {m['day']:%Y-%m-%d} {m['time'] or '--:--'} · {m['party']} · {m['status'] or 'статус не указан'} · {mark}"
              + (f" [[{ref}]]" if ref else ""))
        if m["goal"]:
            print(f"      цель: {m['goal']}")
    waiting = [(m, file_state(m["memo"], m["day"], "мемо")) for m in past]
    waiting = [(m, s) for m, s in waiting if s[0] != "есть"]
    if waiting:
        print(f"Прошли без мемо (за 14 дней): {len(waiting)}")
        for m, (state, _) in waiting:
            print(f"  {m['day']:%Y-%m-%d} {m['time'] or '--:--'} · {m['party']} · мемо: {state}")
    print(f"Итог: без брифа — {missing}; без мемо — {len(waiting)}.")


# ---------- задачи ----------

def tasks():
    out = []
    for cells in table(HUB / "tasks.md"):
        cells += [""] * (7 - len(cells))
        m = re.match(r"\d{4}-\d{2}-\d{2}", cells[3])
        out.append({"created": cells[0], "what": cells[1], "who": cells[2], "due": parse_day(m.group(0)) if m else None,
                    "due_text": cells[3], "status": cells[4].lower(), "source": cells[5], "id": cells[6]})
    return out


def cmd_tasks(args):
    need_hub()
    today = args.today
    items = [t for t in tasks() if "мемо" in t["source"].lower()]
    if args.party:
        key = args.party.lower().replace(" ", "-")
        items = [t for t in items if key in t["source"].lower().replace(" ", "-") or args.party.lower() in t["what"].lower()]
    live = [t for t in items if t["status"] in ("новое", "в работе", "предложено")]
    closed = [t for t in items if t["status"] in ("сделано", "отменено")]
    week = today + timedelta(days=7)
    groups = [("Просрочено", [t for t in live if t["due"] and t["due"] < today and t["status"] != "предложено"]),
              ("Срок в ближайшие 7 дней", [t for t in live if t["due"] and today <= t["due"] <= week]),
              ("Позже", [t for t in live if t["due"] and t["due"] > week]),
              ("Без срока", [t for t in live if not t["due"]]),
              ("Ждут вашего подтверждения (предложено)", [t for t in live if t["status"] == "предложено" and t["due"] and t["due"] < today])]
    head = "Задачи из встреч" + (f" · {args.party}" if args.party else "") + f" на {today:%d.%m.%Y}"
    print(head + f": открыто {len(live)}, закрыто {len(closed)}")
    for title, rows in groups:
        if not rows:
            continue
        print(f"\n{title} — {len(rows)}")
        for t in sorted(rows, key=lambda x: x["due"] or date.max):
            late = f" (на {(today - t['due']).days} дн.)" if title == "Просрочено" else ""
            due = f"{t['due']:%d.%m}" if t["due"] else "срок не назван"
            src = "" if args.tg else f" · {t['source']}"
            print(f"  • {t['what']} — {t['who'] or 'ответственный не назван'}, {due}{late}{src}")
    if not live:
        print("Открытых задач из встреч нет.")
    if args.tg:
        print("\nОтметить выполненное — на странице «Встречи» или словом в чате.")


# ---------- проверка брифа и мемо ----------

def kind_of(path, text):
    name = path.stem.lower()
    if "мемо" in name or re.search(r"^#\s*Мемо", text, re.M):
        return "мемо"
    return "бриф"


def cmd_check(args):
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"Нет файла: {path}")
    text = body(path)
    secs = sections(text)
    kind = kind_of(path, text)
    problems, notes = [], []
    wanted = MEMO_SECTIONS if kind == "мемо" else BRIEF_SECTIONS
    for title in wanted:
        found = find_section(secs, title)
        if found is None:
            problems.append(f"нет раздела «{title}»")
        elif not found.strip():
            problems.append(f"раздел «{title}» пуст")
    decide = len(re.findall(r"\[РЕШИТЬ", text))
    if kind == "бриф":
        words = len(re.findall(r"[0-9A-Za-zА-Яа-яЁё%]+", text))
        if words > BRIEF_WORDS:
            problems.append(f"объём {words} слов — больше {BRIEF_WORDS}: бриф не поместится на страницу")
        else:
            notes.append(f"объём {words} слов (предел {BRIEF_WORDS})")
        five = bullets(find_section(secs, "Главное"))
        if len(five) != 5:
            problems.append(f"в «Главном» {len(five)} строк, а нужно ровно 5")
        if len(bullets(find_section(secs, "Вопросы"))) < 5:
            problems.append("в «Вопросах» меньше 5 вопросов")
        refs = len(re.findall(r"\[[^\]\[]*(?:§|\.md|письмо|мемо|решени|досье|вводные|https?://)[^\]\[]*\]", text, re.I))
        if refs < 5:
            problems.append(f"ссылок на источники всего {refs} — фактам не на что опереться")
        else:
            notes.append(f"ссылок на источники: {refs}")
        if "предположени" not in text.lower():
            problems.append("интересы участников не помечены как предположения")
        objections = find_section(secs, "Карта возражений") or ""
        rows = [l for l in objections.splitlines() if l.strip().startswith("|")]
        if len(rows) < 5:  # шапка, разделитель и минимум три возражения
            problems.append("в карте возражений меньше трёх строк")
    else:
        block = find_section(secs, "Задачи") or ""
        rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in block.splitlines() if l.strip().startswith("|")]
        rows = [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
        if not rows:
            problems.append("в «Задачах» нет таблицы «Что | Кто | Срок»")
        for r in rows:
            r += [""] * (3 - len(r))
            if not r[1]:
                problems.append(f"у задачи «{r[0][:40]}» не указан ответственный")
            if not (re.match(r"\d{4}-\d{2}-\d{2}", r[2]) or "срок не назван" in r[2].lower()):
                problems.append(f"у задачи «{r[0][:40]}» срок «{r[2]}» — нужна дата ГГГГ-ММ-ДД или «срок не назван»")
        notes.append(f"задач в мемо: {len(rows)}")
    notes.append(f"пометок [РЕШИТЬ]: {decide}")
    print(f"Проверка ({kind}): {path.name}")
    for n in notes:
        print(f"  · {n}")
    if problems:
        print(f"ЗАМЕЧАНИЯ — {len(problems)}:")
        for p in problems:
            print(f"  ✗ {p}")
        sys.exit(1)
    print("ПРИНЯТО по форме. Соответствие фактов источникам проверяет человек или субагент meeting-checker.")


# ---------- приёмка на учебном наборе ----------

def cmd_eval(args):
    path, cases = Path(args.file), Path(args.cases)
    for p in (path, cases):
        if not p.exists():
            sys.exit(f"Нет файла: {p}")
    raw = body(path)
    kind = kind_of(path, raw)
    text = re.sub(r"\s+", " ", raw.lower())
    spec = json.loads(cases.read_text(encoding="utf-8")).get(kind)
    if not spec:
        sys.exit(f"В {cases.name} нет набора проверок для типа «{kind}»")
    passed = 0
    print(f"Приёмка на учебном наборе ({kind}): {path.name}")
    for case in spec:
        ok = any(all(part.lower() in text for part in variant) for variant in case["any"])
        if case.get("absent"):
            ok = not ok
        passed += ok
        print(f"  {'✓' if ok else '✗'} {case['name']}")
    total = len(spec)
    print(f"Итог: {passed} из {total} ({round(100 * passed / total)}%). Порог приёмки — {args.threshold}%.")
    if 100 * passed / total < args.threshold:
        sys.exit(1)


# ---------- текст для Telegram ----------

def brief_title(text, path):
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else path.stem


def cmd_tg(args):
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"Нет файла: {path}")
    text = body(path)
    five = bullets(find_section(sections(text), "Главное"))
    if not five:
        sys.exit("В брифе нет раздела «Главное» — выжимку собрать не из чего.")
    m = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    when = ""
    if m:
        gap = (parse_day(m.group(1)) - args.today).days
        when = {0: "Сегодня", 1: "Завтра"}.get(gap, f"{parse_day(m.group(1)):%d.%m}")
    title = re.sub(r"^Бриф:\s*", "", brief_title(text, path))
    out = [f"{when + ' встреча' if when else 'Встреча'}: {title}. Бриф готов.", ""]
    out += [f"{i}. {re.sub(r'[*`]', '', line)}" for i, line in enumerate(five[:5], 1)]
    decide = len(re.findall(r"\[РЕШИТЬ", text))
    if decide:
        out += ["", f"Нужно ваше решение до встречи: {decide} вопр. — они в брифе с пометкой [РЕШИТЬ]."]
    out += ["", "Полный бриф — в чате с агентом или на странице «Встречи»."]
    print("\n".join(out))


# ---------- печатная версия ----------

def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"<span class='ref'>\1</span>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"(\[РЕШИТЬ[^\]]*\])", r"<mark>\1</mark>", text)
    return text


def to_html(text):
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif re.match(r"^#{1,3}\s", line):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{inline(line.lstrip('#').strip())}</h{level}>")
            i += 1
        elif line.strip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            out.append("<table>" + "".join(
                "<tr>" + "".join(f"<{'th' if n == 0 else 'td'}>{inline(c)}</{'th' if n == 0 else 'td'}>" for c in r) + "</tr>"
                for n, r in enumerate(rows)) + "</table>")
        elif re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line):
            tag = "ol" if re.match(r"^\s*\d+[.)]\s+", line) else "ul"
            items = []
            while i < len(lines) and (re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", lines[i]) or (lines[i].startswith("  ") and lines[i].strip())):
                if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", lines[i]):
                    items.append(re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{inline(line.lstrip('> ').strip())}</blockquote>")
            i += 1
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3}\s|\||\s*(?:[-*•]|\d+[.)])\s+|>)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


PRINT_CSS = """
@page{size:A4;margin:11mm 13mm}
*{box-sizing:border-box}
body{font:10.5pt/1.32 "Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;color:#1e2226;margin:0 auto;max-width:186mm;padding:8mm 0}
h1{font-size:15pt;margin:0 0 2mm;border-bottom:1.5pt solid #2d5b4e;padding-bottom:1.5mm}
h2{font-size:9pt;text-transform:uppercase;letter-spacing:.05em;color:#2d5b4e;margin:3mm 0 1mm}
h3{font-size:10.5pt;margin:2mm 0 1mm}
p{margin:0 0 1.2mm}
ul,ol{margin:0 0 1.2mm;padding-left:5mm}
li{margin:0 0 .5mm}
table{border-collapse:collapse;width:100%;margin:1mm 0 1.5mm;font-size:9.5pt}
th,td{border:.5pt solid #b9b3a6;padding:.8mm 1.5mm;text-align:left;vertical-align:top}
th{background:#eef2ee}
mark{background:#f6ead9;color:#7a3f0c;padding:0 .6mm}
code{font-family:inherit;background:#f1efe9;padding:0 .5mm}
.ref{color:#6a6f76;font-size:9pt}
blockquote{margin:0 0 1.2mm;padding-left:3mm;border-left:2pt solid #b9b3a6;color:#4a4f55}
.foot{margin-top:3mm;padding-top:1.5mm;border-top:.5pt solid #b9b3a6;color:#6a6f76;font-size:8pt}
.cols{column-count:2;column-gap:7mm}
.cols h2{break-after:avoid}
.cols table,.cols li{break-inside:avoid}
@media screen{body{padding:10mm 4mm}}
@media print{.hint{display:none}}
.hint{background:#eef2ee;padding:2mm 3mm;border-radius:2mm;font-size:9pt;margin-bottom:4mm}
"""


def cmd_print(args):
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"Нет файла: {path}")
    text = body(path)
    title = brief_title(text, path)
    rest = re.sub(r"^#\s+.+\n", "", text, count=1, flags=re.M)
    out = Path(args.out) if args.out else MEETINGS / "print" / f"{path.stem}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    words = len(re.findall(r"[0-9A-Za-zА-Яа-яЁё%]+", text))
    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{PRINT_CSS}</style></head><body>
<div class="hint">Печать: Ctrl+P → «Сохранить как PDF» или принтер. Эта подсказка на бумагу не попадёт.</div>
<h1>{inline(title)}</h1>
<div class="cols">
{to_html(rest)}
</div>
<div class="foot">Подготовлено агентом по материалам владельца · {args.today:%d.%m.%Y} · факты без источника — в разделе «Не подтверждено» · не для передачи контрагенту</div>
</body></html>
"""
    out.write_text(page, encoding="utf-8", newline="\n")
    try:
        shown = out.resolve().relative_to(ROOT)
    except ValueError:
        shown = out
    print(f"Печатная версия: {shown}")
    if words > BRIEF_WORDS + 150:
        print(f"Внимание: в тексте {words} слов — на одну страницу A4 может не поместиться. Сократите или печатайте на двух.")


def main():
    utf8()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--today", type=parse_day, default=date.today(), help="считать сегодняшним днём ГГГГ-ММ-ДД")
    parser = argparse.ArgumentParser(description="Скрипты кейса «Подготовка к встрече»")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("upcoming", parents=[common])
    p.add_argument("--days", type=int, default=3, help="сколько дней смотреть, считая сегодня (по умолчанию 3)")
    p.set_defaults(fn=cmd_upcoming)
    p = sub.add_parser("tasks", parents=[common])
    p.add_argument("--party", help="только задачи по этому контрагенту")
    p.add_argument("--tg", action="store_true", help="короткий вид для Telegram")
    p.set_defaults(fn=cmd_tasks)
    p = sub.add_parser("check", parents=[common])
    p.add_argument("file")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("print", parents=[common])
    p.add_argument("file")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_print)
    p = sub.add_parser("tg", parents=[common])
    p.add_argument("file")
    p.set_defaults(fn=cmd_tg)
    p = sub.add_parser("eval", parents=[common])
    p.add_argument("file")
    p.add_argument("--cases", default=str(ROOT / "demo" / "evals.json"))
    p.add_argument("--threshold", type=int, default=80)
    p.set_defaults(fn=cmd_eval)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
