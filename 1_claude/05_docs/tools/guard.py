"""Сторож папки документов (уровень L5): проверка перед выдачей и хук Claude Code.

  python tools/guard.py check hub/docs/out/2026-10-02_регламент.docx --before hub/docs/in/регламент.docx --allow "Сроки"
  python tools/guard.py hook        читает событие PreToolUse из stdin; код 2 = запретить запись

check — «выходной контроль» готового файла: лежит в hub/docs/out, имя начинается с даты, не осталось меток {{...}},
целостность относительно исходника соблюдена. Код возврата 0 — можно показывать человеку, 1 — нельзя.

hook — подключается в .claude/settings.json (см. LEVELS.md, L5). Запрещает инструментам Write/Edit:
  - любую запись в hub/.secrets/ и hub/docs/store/ (версии кладёт только tools/versions.py);
  - перезапись существующих файлов в hub/docs/in/, hub/docs/templates/, hub/docs/out/.
Хук не видит запись через командную строку (Bash) — это ограничение, а не гарантия.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
DOCS = HUB / "docs"


def utf8():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def inside(path, folder):
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False


def verdict(path):
    """Причина запрета записи или пустая строка."""
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    if inside(path, HUB / ".secrets"):
        return "hub/.secrets/ заполняет только владелец"
    if inside(path, DOCS / "store"):
        return "хранилище версий меняет только tools/versions.py (add / current)"
    for name, why in (("in", "исходники не правятся — результат кладётся в hub/docs/out/"),
                      ("templates", "шаблоны меняет человек"),
                      ("out", "готовые файлы не перезаписываются — сохраните под новым именем")):
        if inside(path, DOCS / name) and path.exists():
            return why
    return ""


def cmd_hook(_):
    try:
        event = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # непонятное событие не блокируем
    target = (event.get("tool_input") or {}).get("file_path") or ""
    if event.get("tool_name") in ("Write", "Edit", "MultiEdit", "NotebookEdit") and target:
        why = verdict(target)
        if why:
            print(f"Сторож документов: запись в {target} запрещена — {why}.", file=sys.stderr)
            sys.exit(2)
    sys.exit(0)


def cmd_check(args):
    import doclib
    import integrity_diff
    path = Path(args.file)
    problems, notes = [], []
    if not path.exists():
        sys.exit(f"Нет файла: {path}")
    if not inside(path, DOCS / "out"):
        problems.append("файл лежит не в hub/docs/out/")
    if not re.match(r"\d{4}-\d{2}-\d{2}_", path.name):
        problems.append("имя не начинается с даты ГГГГ-ММ-ДД_")
    marks = set()
    for s in doclib.parse(path)["sections"]:
        for line in [s["title"]] + doclib.section_lines(s):
            marks.update(re.findall(r"\{\{[^}]*\}\}", str(line)))
    if marks:
        problems.append("остались незаполненные метки: " + ", ".join(sorted(marks)))
    if args.before:
        rep = integrity_diff.check(args.before, path, args.allow)
        bad = [t["section"] for t in rep["touched"] if not t["allowed"]]
        if bad:
            problems.append("задеты разделы вне разрешённых: " + "; ".join(bad))
        notes += [f"разрешённый раздел «{a}» не изменился" for a in rep["unused_allow"]]
        notes.append(f"без изменений: {rep['same']} разд.")
    else:
        notes.append("целостность не проверялась (нет --before)")
    for n in notes:
        print(f"  примечание: {n}")
    for p in problems:
        print(f"  СТОП: {p}")
    print("ИТОГ: " + ("выдавать нельзя" if problems else "выходной контроль пройден"))
    sys.exit(1 if problems else 0)


def main():
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("file")
    p.add_argument("--before")
    p.add_argument("--allow", action="append", default=[])
    p.set_defaults(fn=cmd_check)
    sub.add_parser("hook").set_defaults(fn=cmd_hook)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
