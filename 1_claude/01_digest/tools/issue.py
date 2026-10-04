"""Работа с готовым выпуском дайджеста (hub/digest/ГГГГ-ММ-ДД.md).

  python tools/issue.py check [ГГГГ-ММ-ДД]    проверка формы: разделы, поля позиций, оценки, ссылки, повторы, даты
  python tools/issue.py card  [ГГГГ-ММ-ДД]    карточка выпуска для пересылки коллегам → hub/digest/cards/ГГГГ-ММ-ДД.html
  python tools/issue.py json  [ГГГГ-ММ-ДД] [--out файл]   документы выпуска для страницы «Дайджест» (коллекция digest)

Без даты берётся последний выпуск. Проверка формы не заменяет проверяющего агента: она не открывает ссылки
и не судит о смысле. Код возврата check: 0 — ошибок нет, 1 — есть ошибки.
"""
import argparse
import html
import json
import sys
from datetime import timedelta

import digestlib as dl

NEED_SECTIONS = ["ТОП-3", "Публикации", "Пропущено", "Что остаётся человеку"]
NEED_FIELDS = [("тема", "topic"), ("TL;DR", "tldr"), ("почему важно для меня", "why"), ("что сделать", "action")]
WATER = ("важная тема", "важно для отрасли", "актуальная тема", "интересный материал", "стоит прочитать", "полезно знать",
         "это важно", "может быть полезно", "актуально")


def top_flags(issue):
    """Какие позиции названы в ТОП-3 (по вхождению заголовка в строку ТОП-3)."""
    tops = [dl.norm_title(t) for t in issue["top3"]]
    for item in issue["items"]:
        key = dl.norm_title(item["title"])
        item["top"] = any(key and key in t for t in tops)
    return sum(i["top"] for i in issue["items"])


def cmd_check(args):
    issue = dl.parse_issue(dl.latest_issue(args.date))
    errors, warns = [], []
    meta = issue["meta"]
    for key in ("type", "date", "agent", "status", "sources"):
        if key not in meta:
            errors.append(f"в шапке нет поля {key}")
    for need in NEED_SECTIONS:
        if not any(s.lower().startswith(need.lower()) for s in issue["sections"]):
            errors.append(f"нет раздела «{need}»")
    for head in issue["bad_heads"]:
        errors.append(f"заголовок позиции не по форме «### [оценка N] Заголовок — источник, дата, ссылка»: {head[:80]}")

    items = issue["items"]
    main = [i for i in items if not i["out_of_period"]]
    if len(main) > 10:
        errors.append(f"позиций {len(main)} — больше 10")
    if items and not issue["top3"]:
        errors.append("раздел «ТОП-3» пуст")
    if len(issue["top3"]) > 3:
        errors.append(f"в ТОП-3 строк: {len(issue['top3'])}")
    named = top_flags(issue)
    if issue["top3"] and named < len(issue["top3"]):
        warns.append(f"в ТОП-3 {len(issue['top3'])} строк, а по заголовку с позициями совпало {named} — проверьте, что ТОП-3 взят из выпуска")
    if not issue["human"]:
        errors.append("раздел «Что остаётся человеку» пуст")

    profile = dl.read_profile()
    issue_day = dl.iso(issue["date"])
    since = issue_day - timedelta(days=max(profile["days"], 1)) if issue_day else None
    if meta.get("period"):
        start = dl.iso(meta["period"].replace("..", " ").split()[0])
        since = start or since
    _, seen = dl.read_seen()
    urls = {}
    for item in items:
        tag = f"«{item['title'][:50]}»"
        for label, key in NEED_FIELDS:
            if not item[key]:
                errors.append(f"{tag}: нет поля «{label}»")
        if item["score"] < 3:
            errors.append(f"{tag}: оценка {item['score']} — позиции с оценкой 1–2 идут только строкой в «Пропущено»")
        key = dl.norm_url(item["url"])
        if key in urls:
            errors.append(f"{tag}: ссылка повторяется (уже у {urls[key]})")
        urls[key] = tag
        was = seen.get(key)
        if was and was[0] < issue["date"]:
            errors.append(f"{tag}: уже было в выпуске {was[0]} (память «уже видел»)")
        pub = dl.iso(item["pub"])
        if pub is None:
            warns.append(f"{tag}: дата публикации не указана — скажите об этом в оговорке")
        elif issue_day and pub > issue_day:
            errors.append(f"{tag}: дата публикации {item['pub']} позже даты выпуска")
        elif since and pub < since and not item["out_of_period"]:
            errors.append(f"{tag}: публикация {item['pub']} старше периода — место в «Вне периода, но важно»")
        if profile["topics"] and item["topic"] and not any(
                dl.norm_title(item["topic"]) in dl.norm_title(t) or dl.norm_title(t) in dl.norm_title(item["topic"])
                for t in profile["topics"]):
            warns.append(f"{tag}: темы «{item['topic']}» нет в профиле")
        why = item["why"].lower()
        if item["why"] and (len(item["why"]) < 25 or any(w in why for w in WATER)):
            warns.append(f"{tag}: «почему важно» похоже на общие слова — нужна связь с задачами владельца")
        if item["top"] and item["score"] < 4:
            warns.append(f"{tag}: в ТОП-3 позиция с оценкой {item['score']}")
    best = sorted((i["score"] for i in items), reverse=True)[:3]
    tops = sorted((i["score"] for i in items if i["top"]), reverse=True)
    if tops and best[:len(tops)] != tops:
        warns.append("ТОП-3 составлен не из позиций с наивысшей оценкой — обоснуйте или поправьте")

    print(f"Выпуск {dl.rel(issue['path'])}: позиций {len(items)}, в ТОП-3 {len(issue['top3'])}, "
          f"пропущено {len(issue['skipped'])}, не удалось открыть {len(issue['failed'])}")
    for e in errors:
        print("  ОШИБКА: " + e)
    for w in warns:
        print("  замечание: " + w)
    print("Форма в порядке." if not errors else f"Ошибок: {len(errors)}. Исправьте выпуск и повторите проверку.")
    sys.exit(1 if errors else 0)


CARD_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1c2430;--muted:#5f6b7a;--line:#dfe3ea;--accent:#2457d6;--s5:#0e7a4d;--s4:#2457d6;--s3:#7a6a0e}
@media (prefers-color-scheme: dark){:root{--bg:#14171c;--card:#1d2128;--text:#e8ebf0;--muted:#9aa5b4;--line:#2e343e;--accent:#8ab0ff;--s5:#5fd3a0;--s4:#8ab0ff;--s3:#d9c765}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:24px 16px 40px}h1{font-size:24px;margin:0 0 4px;text-wrap:balance}
.sub{color:var(--muted);margin:0 0 20px}h2{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:28px 0 10px}
.top{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;padding:12px 16px;margin:0 0 8px}
.item{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:0 0 10px}
.item h3{font-size:17px;margin:0 0 6px}.meta{color:var(--muted);font-size:13px;margin:0 0 8px}
.score{display:inline-block;min-width:26px;text-align:center;font-weight:700;border-radius:6px;padding:0 6px;margin-right:8px;border:1px solid currentColor;font-variant-numeric:tabular-nums}
.s5{color:var(--s5)}.s4{color:var(--s4)}.s3{color:var(--s3)}p{margin:0 0 6px}b{font-weight:600}a{color:var(--accent);overflow-wrap:anywhere}
.foot{color:var(--muted);font-size:13px;border-top:1px solid var(--line);margin-top:28px;padding-top:12px}
"""


def cmd_card(args):
    issue = dl.parse_issue(dl.latest_issue(args.date))
    top_flags(issue)
    e = lambda s: html.escape(dl.plain(s or ""), quote=True)
    parts = [f"<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
             f"<title>Дайджест {e(issue['date'])}</title><style>{CARD_CSS}</style></head><body><div class=\"wrap\">",
             f"<h1>{e(issue['title'] or 'Дайджест ' + issue['date'])}</h1>",
             f"<p class=\"sub\">Выпуск от {e(issue['date'])} · позиций: {len(issue['items'])} · отобрано из открытых источников</p>"]
    if issue["top3"]:
        parts.append("<h2>ТОП-3 — на что обратить внимание</h2>")
        parts += [f"<div class=\"top\">{e(t)}</div>" for t in issue["top3"][:3]]
    parts.append("<h2>Публикации</h2>")
    for item in issue["items"]:
        link = item["url"] if item["url"].lower().startswith(("http://", "https://")) else ""
        parts.append(
            f"<div class=\"item\"><h3><span class=\"score s{item['score']}\">{item['score']}</span>{e(item['title'])}</h3>"
            f"<p class=\"meta\">{e(item['source'])} · {e(item['pub'])}" + (f" · {e(item['topic'])}" if item["topic"] else "") + "</p>"
            + (f"<p>{e(item['tldr'])}</p>" if item["tldr"] else "")
            + (f"<p><b>Почему важно:</b> {e(item['why'])}</p>" if item["why"] else "")
            + (f"<p><b>Что сделать:</b> {e(item['action'])}</p>" if item["action"] else "")
            + (f"<p><a href=\"{html.escape(link, quote=True)}\" rel=\"noopener\">{e(link)}</a></p>" if link else "") + "</div>")
    parts.append("<p class=\"foot\">Оценка 1–5 — релевантность для составителя выпуска, а не качество материала. "
                 "Подготовлено агентом-обозревателем, проверено человеком перед пересылкой. Личных отметок и задач в карточке нет.</p>")
    parts.append("</div></body></html>")
    out = dl.CARDS / f"{issue['date']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    print(f"Карточка выпуска: {dl.rel(out)} — откройте в браузере; пересылайте файлом после просмотра.")


def docs(issue):
    top_flags(issue)
    return [{"id": i["id"], "date": issue["date"], "title": i["title"], "url": i["url"], "score": i["score"],
             "summary": dl.plain(i["tldr"]), "why": dl.plain(i["why"]), "action": dl.plain(i["action"]), "topic": i["topic"],
             "source": i["source"], "pub": i["pub"], "top": i["top"], "mark": ""} for i in issue["items"]]


def cmd_json(args):
    issue = dl.parse_issue(dl.latest_issue(args.date))
    text = json.dumps(docs(issue), ensure_ascii=False, indent=1)
    if args.out:
        out = dl.ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"Документов для страницы: {len(issue['items'])} → {dl.rel(out)}")
    else:
        print(text)


def main():
    dl.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("card", cmd_card), ("json", cmd_json)):
        p = sub.add_parser(name)
        p.add_argument("date", nargs="?")
        if name == "json":
            p.add_argument("--out")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    dl.need_hub()
    args.fn(args)


if __name__ == "__main__":
    main()
