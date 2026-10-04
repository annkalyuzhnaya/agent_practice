"""Локальный поиск по базе знаний: полнотекстовый индекс (SQLite FTS5) по папке hub/.

  python tools/kb_index.py build                      пересобрать индекс
  python tools/kb_index.py search "срок согласования" -n 8
  python tools/kb_index.py text "hub/kb/входящее/файл.docx"   показать текст файла (Word читается без доп. библиотек)

В индекс идут .md, .txt и .docx из hub/ по разделам-заголовкам. Не индексируются: шаблоны, служебные списки
(_уход, _вопросы, _противоречия), заявки, журнал, память hub/memory/ (это словарь владельца, а не факты).
Запрос расширяется по словарю памяти: сокращение из hub/memory/glossary.md ищется вместе с расшифровкой.
Данные не покидают компьютер; индекс лежит в .cache/kb.sqlite — его можно удалить и собрать заново.
"""
import argparse
import re
import sqlite3
import sys

import kblib

DB = kblib.CACHE / "kb.sqlite"
# пересказы и служебное: в индекс не берём, чтобы ответы ссылались на первоисточник
SKIP = ("hub/handoff/", "hub/journal.md", "hub/kb/_", "hub/.obsidian/", "hub/.secrets/", "hub/memory/",
        "hub/Главная.md", "hub/setup.md", "hub/routines.md", "hub/artifacts.md", "hub/accounts.md", "hub/profile.md",
        "hub/inbox/drafts/", "hub/inbox/triage/", "hub/plan/")
WORD = re.compile(r"[0-9A-Za-zА-Яа-яЁё]{2,}")


def cmd_build(_):
    kblib.need_hub()
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    try:
        con.execute("drop table if exists chunks")
        con.execute("create virtual table chunks using fts5(path, heading, body, tokenize='unicode61 remove_diacritics 2')")
    except sqlite3.Error as e:
        sys.exit(f"В этой сборке Python нет поиска FTS5 ({e}). Ищите чтением файлов: плейбук 02_kb.md, режим А.")
    files = 0
    for path in sorted(kblib.HUB.rglob("*")):
        rel = path.relative_to(kblib.ROOT).as_posix()
        if not path.is_file() or rel.startswith(SKIP) or path.suffix.lower() not in (".md", ".txt", ".docx"):
            continue
        text = kblib.text_of(path)
        if path.suffix.lower() == ".md":
            text = kblib.frontmatter(text)[1]
        rows = [(rel, h, b) for h, b in kblib.md_chunks(text)]
        if rows:
            con.executemany("insert into chunks values (?,?,?)", rows)
            files += 1
    con.commit()
    total = con.execute("select count(*) from chunks").fetchone()[0]
    print(f"Индекс собран: файлов {files}, фрагментов {total}")


def stem(word):
    """Грубое усечение окончания — чтобы «сроки» находили «сроков»."""
    w = word.lower()
    return w[:-2] if len(w) > 5 else w[:-1] if len(w) > 4 else w


def expand(query):
    """Дописать к запросу расшифровки сокращений из словаря памяти."""
    terms = kblib.glossary()
    added = [f"{w} = {terms[w.lower()]}" for w in WORD.findall(query) if w.lower() in terms]
    extra = " ".join(terms[w.lower()] for w in WORD.findall(query) if w.lower() in terms)
    return (query + " " + extra).strip(), added


def find(con, question, n):
    """Строки (path, heading, snippet): сначала фрагменты, где есть все слова запроса, затем — где есть хотя бы одно."""
    query, added = expand(question)
    words = [w for w in WORD.findall(query) if len(w) > 2 or w.isupper() or w.isdigit()]
    own = sorted({f'"{stem(w)}"*' for w in WORD.findall(question) if len(w) > 2 or w.isupper() or w.isdigit()})
    terms = sorted({f'"{stem(w)}"*' for w in words})
    rows, seen = [], set()
    for match in ([" AND ".join(own)] if len(own) > 1 else []) + [" OR ".join(terms)]:
        if not match:
            continue
        for row in con.execute(
                "select path, heading, snippet(chunks, 2, '[', ']', ' … ', 30) from chunks "
                "where chunks match ? order by bm25(chunks, 0.3, 2.0, 1.0) limit ?", (match, n)):
            if row[:2] not in seen and len(rows) < n:
                seen.add(row[:2])
                rows.append(row)
    return rows, words, added


def cmd_search(args):
    if not DB.exists():
        cmd_build(args)
    con = sqlite3.connect(DB)
    rows, words, added = find(con, args.query, args.n)
    if not words:
        sys.exit("Пустой запрос")
    if added:
        print("Запрос расширен по словарю памяти: " + "; ".join(added) + "\n")
    if not rows:
        print("Ничего не найдено — в базе этого нет. Не додумывайте ответ.")
    for path, heading, snip in rows:
        print(f"[{path} § {heading or '—'}]\n   {' '.join(snip.split())}\n")
    stems = {stem(w) for w in words if len(w) > 3}
    for row in kblib.conflicts():
        if row["open"] and any(s in row["fact"].lower() for s in stems):
            print(f"ВНИМАНИЕ: по теме есть открытое противоречие — «{row['fact']}»: "
                  f"А: {row['a']} / Б: {row['b']}. Покажите обе версии, не выбирайте молча.")


def cmd_text(args):
    path = (kblib.ROOT / args.file) if not kblib.Path(args.file).is_absolute() else kblib.Path(args.file)
    if not path.exists():
        sys.exit(f"Файла нет: {args.file}")
    print(kblib.text_of(path) or "(текст не извлечён — откройте файл вручную)")


def main():
    kblib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").set_defaults(fn=cmd_build)
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("-n", type=int, default=6)
    p.set_defaults(fn=cmd_search)
    p = sub.add_parser("text")
    p.add_argument("file")
    p.set_defaults(fn=cmd_text)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
