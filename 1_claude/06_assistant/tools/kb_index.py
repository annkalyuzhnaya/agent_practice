"""Локальная база знаний: полнотекстовый индекс (SQLite FTS5) по всей шине hub/.

  python tools/kb_index.py build              # пересобрать индекс
  python tools/kb_index.py search "сроки согласования" -n 8

Индексируются .md/.txt в hub/ (по разделам-заголовкам), кроме черновиков, разборов, планов и заявок,
и разобранные версии документов из hub/docs/store/. Данные не покидают компьютер; индекс лежит в .cache/kb.sqlite.
"""
import argparse
import json
import re
import sqlite3

import doclib

DB = doclib.ROOT / ".cache" / "kb.sqlite"
# пересказы первоисточников: в индекс не берём, чтобы ответы ссылались на оригинал
DERIVED = ("hub/inbox/drafts/", "hub/inbox/triage/", "hub/plan/", "hub/handoff/", "hub/journal.md",
           "hub/kb/_шаблоны/", "hub/.obsidian/", "hub/.secrets/", "hub/Главная.md", "hub/setup.md",
           "hub/routines.md", "hub/artifacts.md", "hub/accounts.md")
WORD = re.compile(r"[0-9A-Za-zА-Яа-яЁё]{3,}")


def md_chunks(text):
    """(заголовок, текст) по заголовкам markdown."""
    heading, buf = "", []
    for line in text.splitlines():
        if line.startswith("#"):
            if "".join(buf).strip():
                yield heading, "\n".join(buf)
            heading, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        yield heading, "\n".join(buf)


def cmd_build(_):
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("drop table if exists chunks")
    con.execute("create virtual table chunks using fts5(path, heading, body, tokenize='unicode61 remove_diacritics 2')")
    files = 0
    for path in sorted(doclib.HUB.rglob("*")):
        rel = path.relative_to(doclib.ROOT).as_posix()
        if rel.startswith(DERIVED):
            continue
        if path.suffix.lower() in (".md", ".txt"):
            rows = [(rel, h, b) for h, b in md_chunks(path.read_text(encoding="utf-8", errors="replace"))]
        elif path.suffix == ".json" and path.parent.parent.name == "store" and path.name != "manifest.json":
            parsed = json.loads(path.read_text(encoding="utf-8"))
            rows = [(f"{rel} ({parsed['file']})", key, "\n".join(doclib.section_lines(s)))
                    for key, s in doclib.keyed(parsed).items()]
        else:
            continue
        con.executemany("insert into chunks values (?,?,?)", rows)
        files += 1
    con.commit()
    total = con.execute("select count(*) from chunks").fetchone()[0]
    print(f"Индекс собран: файлов {files}, фрагментов {total}")


def stem(word):
    """Грубое усечение окончания — чтобы «сроки» находили «сроков»."""
    w = word.lower()
    return w[:-2] if len(w) > 5 else w[:-1] if len(w) > 4 else w


def cmd_search(args):
    if not DB.exists():
        cmd_build(args)
    terms = [f'"{stem(w)}"*' for w in WORD.findall(args.query)]
    if not terms:
        raise SystemExit("Пустой запрос")
    con = sqlite3.connect(DB)
    rows = con.execute(
        "select path, heading, snippet(chunks, 2, '[', ']', ' … ', 30) from chunks "
        "where chunks match ? order by bm25(chunks, 2.0, 4.0, 1.0) limit ?",
        (" OR ".join(terms), args.n)).fetchall()
    if not rows:
        print("Ничего не найдено")
    for path, heading, snip in rows:
        print(f"[{path} § {heading or '—'}]\n   {' '.join(snip.split())}\n")


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").set_defaults(fn=cmd_build)
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("-n", type=int, default=6)
    p.set_defaults(fn=cmd_search)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
