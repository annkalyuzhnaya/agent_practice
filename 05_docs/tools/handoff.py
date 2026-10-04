"""Заявки на документы: hub/handoff/. Мост Cowork/чат/Telegram/страница → Claude Code.

  python tools/handoff.py new --title "Правка сроков регламента" --text "Обнови раздел 3 ..." --file hub/docs/in/регламент.docx
  python tools/handoff.py list                 новые и незакрытые; --all — все
  python tools/handoff.py stage ФАЙЛ --set собрано|проверено|версия|отклонено [--check ok|fail] [--doc id] [--version N]
  python tools/handoff.py done ФАЙЛ --result-file результат.md      дописать «## Результат» и закрыть (status: done)

Этапы заявки: принято → собрано → проверено → версия (или отклонено). Нужна только стандартная библиотека Python.
"""
import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
HANDOFF = HUB / "handoff"
STAGES = ["принято", "собрано", "проверено", "версия", "отклонено"]
ORDER = ["to", "needs", "status", "stage", "from", "date", "due", "check", "doc", "version"]


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def slug(text):
    words = re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", text)[:6]
    return "-".join(words).lower()[:60] or "заявка"


def read(path):
    """Вернуть (поля заголовка, тело)."""
    text = Path(path).read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        return meta, text
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def write(path, meta, body):
    keys = [k for k in ORDER if k in meta] + [k for k in meta if k not in ORDER]
    head = "\n".join(f"{k}: {meta[k]}" for k in keys)
    Path(path).write_text(f"---\n{head}\n---\n{body}", encoding="utf-8", newline="\n")


def title_of(body, fallback=""):
    m = re.search(r"^#\s*(?:Заявка:\s*)?(.+)$", body, re.M)
    return m.group(1).strip() if m else fallback


def create(title, text, files=(), source="чат", needs="code", due="", when=None, questions=()):
    """Создать заявку и вернуть путь. Используется и мостом Telegram, и сверкой страницы."""
    when = when or date.today().isoformat()
    HANDOFF.mkdir(parents=True, exist_ok=True)
    stem = f"{when}_{slug(title)}"
    path, n = HANDOFF / f"{stem}.md", 1
    while path.exists():
        n += 1
        path = HANDOFF / f"{stem}-{n}.md"
    meta = {"to": "docs", "needs": needs, "status": "new", "stage": "принято", "from": source, "date": when}
    if due:
        meta["due"] = due
    body = [f"# Заявка: {title.strip()}", "", f"**Что сделать.** {text.strip()}", ""]
    body += ["**Файлы.** " + ("; ".join(f"`{f}`" for f in files) if files else "не приложены"), ""]
    if due:
        body += [f"**Срок.** {due}", ""]
    for q in questions:
        body += [f"[РЕШИТЬ] {q}", ""]
    body += [f"**Источник.** {source}, {when}", ""]
    write(path, meta, "\n".join(body))
    return path


def find(name):
    p = Path(name)
    if p.exists():
        return p
    hits = sorted(HANDOFF.glob(f"*{name}*")) if HANDOFF.exists() else []
    if len(hits) != 1:
        sys.exit(f"Заявка «{name}»: найдено {len(hits)} — уточните имя файла (python tools/handoff.py list --all)")
    return hits[0]


def cmd_new(args):
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    path = create(args.title, text, args.file, args.source, args.needs, args.due or "")
    print(f"Заявка принята: {path.relative_to(ROOT).as_posix()} (этап: принято, нужна среда: {args.needs})")


def cmd_list(args):
    files = sorted(HANDOFF.glob("*.md")) if HANDOFF.exists() else []
    shown = 0
    for path in files:
        meta, body = read(path)
        if not args.all and meta.get("status") == "done":
            continue
        shown += 1
        extra = "".join(f"  {k}: {meta[k]}" for k in ("check", "doc", "version") if meta.get(k))
        asks = len(re.findall(r"^\[РЕШИТЬ\]", body, re.M))
        print(f"{meta.get('stage', '?'):<10} {meta.get('status', '?'):<5} needs:{meta.get('needs', '?'):<5} {path.name}"
              f"{extra}{'  [РЕШИТЬ]×' + str(asks) if asks else ''}")
        print(f"           {title_of(body, path.stem)}")
    if not shown:
        print("Незакрытых заявок нет" if files and not args.all else "Заявок нет")


def cmd_stage(args):
    path = find(args.file)
    meta, body = read(path)
    meta["stage"] = args.set
    if args.check:
        meta["check"] = args.check
    if args.doc:
        meta["doc"] = args.doc
    if args.version:
        meta["version"] = str(args.version)
    write(path, meta, body)
    print(f"{path.name}: этап — {args.set}" + (f", проверка: {args.check}" if args.check else "")
          + (f", документ {meta.get('doc', '')} v{args.version}" if args.version else ""))


def cmd_done(args):
    path = find(args.file)
    meta, body = read(path)
    result = Path(args.result_file).read_text(encoding="utf-8").strip() if args.result_file else (args.result or "").strip()
    if not result:
        sys.exit("Нужен текст результата: --result-file или --result")
    meta["status"] = "done"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = body.rstrip() + f"\n\n## Результат (docs, {stamp}, {args.where})\n\n{result}\n"
    write(path, meta, body)
    print(f"{path.name}: закрыта (status: done, этап: {meta.get('stage', '?')})")


def main():
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("--title", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--text-file")
    p.add_argument("--file", action="append", default=[])
    p.add_argument("--from", dest="source", default="чат")
    p.add_argument("--needs", choices=["code", "any"], default="code")
    p.add_argument("--due")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("list")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("stage")
    p.add_argument("file")
    p.add_argument("--set", required=True, choices=STAGES)
    p.add_argument("--check", choices=["ok", "fail"])
    p.add_argument("--doc")
    p.add_argument("--version", type=int)
    p.set_defaults(fn=cmd_stage)
    p = sub.add_parser("done")
    p.add_argument("file")
    p.add_argument("--result-file")
    p.add_argument("--result")
    p.add_argument("--where", default="Claude Code")
    p.set_defaults(fn=cmd_done)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
