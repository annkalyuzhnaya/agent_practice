"""Типизированный поиск по структуре документов хранилища (уровень L5).

  python tools/doc_search.py "срок согласования"                 по действующим (или последним) версиям всех документов
  python tools/doc_search.py "срок" --doc reglament --v 1        в конкретной версии
  python tools/doc_search.py "бюджет" --type xlsx --all-versions с указанием, в каких версиях найдено

Ищет не по сплошному тексту, а по разделам: ответ — «документ, версия, дата, раздел, строка». Слова сравниваются
по грубой основе (окончания отбрасываются). Нужна только стандартная библиотека Python.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "hub" / "docs" / "store"


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def stem(word):
    w = word.lower().replace("ё", "е")
    return w[:-2] if len(w) > 5 else w[:-1] if len(w) > 4 else w


def stems(text):
    return {stem(w) for w in re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", str(text))}


def lines_of(s):
    lines = list(s.get("paragraphs", []))
    for t in s.get("tables", []):
        lines += [" | ".join(str(c) for c in row) for row in t]
    lines += [" | ".join(str(c) for c in row) for row in s.get("rows", [])]
    return lines


def search(query, doc=None, kind=None, version=None, all_versions=False, store=None):
    want = stems(query)
    hits = []
    store = store or STORE
    for folder in sorted(p for p in store.iterdir() if p.is_dir()) if store.exists() else []:
        mpath = folder / "manifest.json"
        if not mpath.exists():
            continue
        man = json.loads(mpath.read_text(encoding="utf-8"))
        if doc and doc.lower() not in man["id"].lower():
            continue
        if kind and kind.lower() not in (man.get("type", "") + " " + Path(man["versions"][-1]["file"]).suffix).lower():
            continue
        cur = (man.get("current") or {}).get("v")
        if all_versions:
            picked = man["versions"]
        elif version:
            picked = [v for v in man["versions"] if v["v"] == version]
        else:
            picked = [v for v in man["versions"] if v["v"] == (cur or man["versions"][-1]["v"])]
        for ver in picked:
            parsed = json.loads((folder / f"v{ver['v']}.json").read_text(encoding="utf-8"))
            for s in parsed["sections"]:
                title_hit = want <= stems(s["path"])
                for line in ([""] if title_hit else []) + lines_of(s):
                    if title_hit and not line or want <= stems(line) | stems(s["title"]) and want & stems(line):
                        hits.append({"doc": man["id"], "type": man.get("type", ""), "v": ver["v"], "ts": ver["ts"],
                                     "current": ver["v"] == cur, "section": s["path"], "line": line or "(совпадение в заголовке раздела)"})
    return hits


def main():
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--doc")
    ap.add_argument("--type")
    ap.add_argument("--v", type=int)
    ap.add_argument("--all-versions", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    hits = search(args.query, args.doc, args.type, args.v, args.all_versions)
    if not hits:
        print("Ничего не найдено. В хранилище ищутся только сохранённые версии (versions.py add).")
        sys.exit(1)
    for h in hits[:args.limit]:
        mark = "действующая" if h["current"] else "не действующая"
        print(f"{h['doc']} [{h['type']}] v{h['v']} от {h['ts'][:10]} ({mark}) — {h['section']}")
        print(f"   {h['line'][:300]}")
    if len(hits) > args.limit:
        print(f"… и ещё {len(hits) - args.limit} (поднимите --limit)")


if __name__ == "__main__":
    main()
