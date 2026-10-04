"""Формальная проверка шины кейса «Входящие» и контроль «на что не ответили».

  python tools/inbox_check.py                         проверить hub/ этого кейса
  python tools/inbox_check.py --hub demo/пример_результата --today 2026-10-05
  python tools/inbox_check.py --days 2                порог «без ответа дольше N дней» (по умолчанию 2)

Что проверяет:
  - форматы таблиц inbox/mail.md и tasks.md, дубли писем, адреса почты в обзоре;
  - главное правило: среди задач нет «Ответить…»;
  - у каждого письма «ответ: нужен» есть файл черновика, в черновиках нет [РЕШИТЬ], основной ответ — 2–5 предложений;
  - письма без ответа дольше N дней, письма в черновиках почты, просроченные и сегодняшние задачи.
Ничего не меняет и не отправляет. Код возврата 1 — есть нарушения. Нужна только стандартная библиотека Python.
"""
import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIL_HEAD = ["Дата", "От кого", "Тема", "Суть", "Адресация", "Ответ", "Черновик", "Статус", "Задача", "ID"]
TASK_HEAD = ["Дата", "Что", "Кто", "Срок", "Статус", "Источник", "ID"]
MAIL_STATUS = {"новое", "ответ утверждён", "отправлено", "в черновиках почты", "игнор", "без ответа"}
TASK_STATUS = {"предложено", "новое", "в работе", "сделано", "отменено"}
ADDRESSING = {"лично", "в числе получателей", "в копии", "рассылка"}


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def table(path, head):
    """Строки первой таблицы файла со знакомой шапкой: (список словарей, ошибка)."""
    if not path.exists():
        return [], f"нет файла {path.name}"
    rows, found = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not found:
            if cells == head:
                found = True
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        if len(cells) != len(head):
            rows.append({"_bad": line.strip()})
            continue
        rows.append(dict(zip(head, cells)))
    return rows, None if found else f"в {path.name} нет шапки: | {' | '.join(head)} |"


def day(text):
    m = re.match(r"\d{4}-\d{2}-\d{2}", text or "")
    return date.fromisoformat(m.group(0)) if m else None


def body(text):
    """Основной ответ черновика: без шапки и без раздела «Варианты»."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        text = parts[2] if len(parts) == 3 else text
    return text.split("## Варианты")[0].strip()


def sentences(text):
    return len([s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()])


def incoming(hub):
    files = [p for p in (hub / "inbox" / "new").glob("*") if p.is_file()] if (hub / "inbox" / "new").exists() else []
    messages = 0
    for p in files:
        if p.suffix.lower() == ".md":
            n = len(re.findall(r"^\*\*От:\*\*", p.read_text(encoding="utf-8"), flags=re.M))
            messages += n or 1
        else:
            messages += 1
    return len(files), messages


def main():
    utf8()
    ap = argparse.ArgumentParser(description="Проверка шины кейса «Входящие»")
    ap.add_argument("--hub", default=str(ROOT / "hub"))
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--days", type=int, default=2)
    args = ap.parse_args()
    hub = Path(args.hub)
    if not hub.is_absolute():
        hub = ROOT / hub
    if not hub.exists():
        sys.exit(f"Нет папки {hub} — создайте шину: python tools/setup.py")
    today = date.fromisoformat(args.today)
    errors, warns = [], []

    files, messages = incoming(hub)
    mail, err = table(hub / "inbox" / "mail.md", MAIL_HEAD)
    if err:
        errors.append(err)
    tasks, err = table(hub / "tasks.md", TASK_HEAD)
    if err:
        errors.append(err)

    seen, stale, in_drafts, need = set(), [], [], 0
    for r in mail:
        if "_bad" in r:
            errors.append(f"mail.md: строка с другим числом колонок: {r['_bad'][:80]}")
            continue
        label = f"{r['От кого']} — {r['Тема']}"
        key = (r["Дата"], r["От кого"], r["Тема"])
        if key in seen:
            errors.append(f"mail.md: дубль письма: {label}")
        seen.add(key)
        if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", " ".join(r.values())):
            errors.append(f"mail.md: адрес почты в обзоре: {label}")
        if r["Статус"] not in MAIL_STATUS:
            errors.append(f"mail.md: неизвестный статус «{r['Статус']}»: {label}")
        if r["Адресация"] not in ADDRESSING:
            errors.append(f"mail.md: неизвестная адресация «{r['Адресация']}»: {label}")
        needed = r["Ответ"].startswith("нужен")
        if not needed and not r["Ответ"].startswith("не предполагается"):
            errors.append(f"mail.md: колонка «Ответ» должна начинаться с «нужен» или «не предполагается»: {label}")
        if not needed and r["Ответ"].strip() == "не предполагается":
            warns.append(f"mail.md: не названа причина, почему ответ не нужен: {label}")
        if needed:
            need += 1
            m = re.search(r"\[\[(.+?)\]\]", r["Черновик"])
            if not m:
                errors.append(f"нет черновика для письма, ждущего ответа: {label}")
            else:
                f = hub / "inbox" / "drafts" / (m.group(1) + ".md")
                if not f.exists():
                    errors.append(f"файл черновика не найден: inbox/drafts/{f.name}")
                else:
                    text = f.read_text(encoding="utf-8")
                    if "[РЕШИТЬ" in text:
                        errors.append(f"в черновике осталась пометка [РЕШИТЬ]: {f.name}")
                    n = sentences(body(text))
                    if not 2 <= n <= 5:
                        warns.append(f"основной ответ не 2–5 предложений (сейчас {n}): {f.name}")
            d = day(r["Дата"])
            if r["Статус"] in ("новое", "ответ утверждён") and d and (today - d).days > args.days:
                stale.append(f"{label} (письмо от {d.isoformat()}, {(today - d).days} дн., статус «{r['Статус']}»)")
        if r["Статус"] == "в черновиках почты":
            in_drafts.append(label)
        if r["Статус"] == "отправлено" and not r["ID"]:
            errors.append(f"mail.md: «отправлено» без ID страницы — отправка возможна только по кнопке: {label}")

    overdue, due_today, opened = [], [], 0
    for r in tasks:
        if "_bad" in r:
            errors.append(f"tasks.md: строка с другим числом колонок: {r['_bad'][:80]}")
            continue
        if r["Статус"] not in TASK_STATUS:
            errors.append(f"tasks.md: неизвестный статус «{r['Статус']}»: {r['Что']}")
        if re.match(r"(ответить|написать ответ|дать ответ)\b", r["Что"].lower()):
            errors.append(f"tasks.md: «ответить на письмо» — не задача (главное правило): {r['Что']}")
        if not day(r["Срок"]) and r["Срок"] != "срок не назван":
            warns.append(f"tasks.md: срок не дата и не «срок не назван»: {r['Что']}")
        if r["Статус"] in ("новое", "в работе"):
            opened += 1
            d = day(r["Срок"])
            if d and d < today:
                overdue.append(f"{r['Что']} (срок {r['Срок']})")
            elif d == today:
                due_today.append(f"{r['Что']} (срок {r['Срок']})")

    triages = sorted((hub / "inbox" / "triage").glob("*.md")) if (hub / "inbox" / "triage").exists() else []
    if triages:
        text = triages[-1].read_text(encoding="utf-8")
        for section in ("Сегодня", "На неделе", "Делегировать", "Замечания безопасности"):
            if section not in text:
                warns.append(f"в разборе {triages[-1].name} нет раздела «{section}»")

    def block(title, items):
        print(f"\n{title}: {len(items)}")
        for x in items:
            print(f"  - {x}")

    print(f"Проверка шины: {hub}")
    print(f"Дата: {today.isoformat()}; порог «без ответа»: {args.days} дн.")
    print(f"Необработанных файлов в inbox/new: {files} (сообщений: {messages})")
    print(f"Писем в обзоре: {len(mail)}, ждут ответа: {need}; задач открыто: {opened}; разборов: {len(triages)}")
    block(f"Без ответа дольше {args.days} дн.", stale)
    block("В черновиках почты — ждут отправки владельцем", in_drafts)
    block("Задачи просрочены", overdue)
    block("Задачи на сегодня", due_today)
    block("Замечания", warns)
    block("Нарушения", errors)
    print("\nИтог: " + ("есть нарушения" if errors else "нарушений нет"))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
