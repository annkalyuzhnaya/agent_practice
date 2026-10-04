"""Карта базы знаний для страницы «База знаний»: узлы, связи, типы, журналы — одним JSON.

  python tools/kb_map.py                  записать .cache/kb_map.json и показать итог
  python tools/kb_map.py --out путь.json  записать в другой файл
  python tools/kb_map.py --stdout         вывести JSON в консоль

В карту попадают только заголовок, тип, короткая суть (до 220 знаков), дата и ссылки заметки — полных текстов нет.
Номера записей (id) устойчивы: одна и та же заметка всегда получает один и тот же номер.
Что с этим JSON делает агент — в playbooks/13_artifact.md.
"""
import argparse
import json
import sys
from datetime import datetime

import kb_lint
import kblib


def qa_rows():
    out = []
    for cells in kblib.table_rows(kblib.QA, 4):
        when, question, answer, sources, check, origin = (cells + [""] * 6)[:6]
        out.append({"id": kblib.short_id("q", when, question), "date": when, "question": question, "answer": answer[:400],
                    "sources": [s.strip() for s in sources.split(";") if s.strip()], "check": check, "origin": origin})
    return out


def build():
    items, notes = kb_lint.find()
    ids = {n["stem"]: kblib.short_id("n", n["stem"]) for n in notes}
    main = [n for n in notes if not n["inbox"]]
    nodes, links, counts = [], [], {}
    for n in main:
        counts[n["type"]] = counts.get(n["type"], 0) + 1
        targets = sorted({ids[l.split("/")[-1]] for l in n["links"]
                          if l.split("/")[-1] in ids and l.split("/")[-1] != n["stem"]
                          and not next(x for x in notes if x["stem"] == l.split("/")[-1])["inbox"]})
        nodes.append({"id": ids[n["stem"]], "title": n["title"][:120], "type": n["type"], "summary": n["summary"],
                      "file": n["stem"], "date": n["date"][:10], "tags": n["tags"][:6], "links": targets})
        links += [[ids[n["stem"]], t] for t in targets]
    seen, pairs = set(), []
    for a, b in links:  # связь показываем один раз, даже если заметки ссылаются друг на друга
        key = tuple(sorted((a, b)))
        if key not in seen:
            seen.add(key)
            pairs.append([a, b])
    recent = [n["id"] for n in sorted(nodes, key=lambda n: n["date"], reverse=True)[:8]]
    inbox = [{"id": ids[n["stem"]], "title": n["title"][:120], "file": n["stem"], "date": n["date"][:10]}
             for n in notes if n["inbox"] and not n["processed"]]
    conflicts = [{k: r[k] for k in ("id", "date", "fact", "a", "b", "newer", "status")} for r in kblib.conflicts()]
    care = [{k: it[k] for k in ("id", "kind", "note", "target", "text", "advice")} for it in items if it["kind"] != "не разобрано"]
    return {"generated": datetime.now().isoformat(timespec="minutes"), "total": len(nodes), "counts": counts,
            "recent": recent, "inbox": inbox, "nodes": nodes, "links": pairs, "conflicts": conflicts, "care": care,
            "qa": qa_rows()}


def main():
    kblib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=".cache/kb_map.json")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()
    kblib.need_hub()
    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if args.stdout:
        print(text)
        return
    out = kblib.Path(args.out) if kblib.Path(args.out).is_absolute() else kblib.ROOT / args.out
    kblib.write(out, text + "\n")
    open_rows = sum(1 for c in data["conflicts"] if "открыто" in c["status"].lower())
    print(f"Карта записана: {args.out}. Заметок: {data['total']} ({', '.join(f'{k} — {v}' for k, v in sorted(data['counts'].items()))}); "
          f"связей: {len(data['links'])}; во входящем: {len(data['inbox'])}; противоречий открыто: {open_rows}; "
          f"пунктов ухода: {len(data['care'])}; вопросов в журнале: {len(data['qa'])}")
    if sys.stdout.isatty() and not data["nodes"]:
        print("База пуста. Положите учебные примеры: python tools/demo.py load")


if __name__ == "__main__":
    main()
