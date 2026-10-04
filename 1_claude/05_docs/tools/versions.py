"""Версионное типизированное хранилище документов: hub/docs/store/<id>/.

  python tools/versions.py add файл.docx --id reglament --type регламент --note "правка сроков"
  python tools/versions.py list
  python tools/versions.py diff reglament            # две последние версии
  python tools/versions.py diff reglament 1 3        # конкретные версии
  python tools/versions.py current reglament 2 --by "владелец, в чате 2026-10-02"

Каждая версия = копия файла + разобранная структура (JSON) + запись в manifest.json с таймстемпом.
«Действующую» версию назначает только человек: команда current выполняется после его явного решения
(в чате или кнопкой на странице «Документы»), в --by пишется, кто и где решил.
"""
import argparse
import difflib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import doclib

STORE = doclib.HUB / "docs" / "store"


def load_manifest(doc_id, store=None):
    path = (store or STORE) / doc_id / "manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"id": doc_id, "type": "", "versions": []}


def save_manifest(man, store=None):
    path = (store or STORE) / man["id"] / "manifest.json"
    path.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")


def add_version(src, doc_id=None, doc_type=None, note=None, ts=None, store=None):
    """Положить файл новой версией. Возвращает (manifest, номер версии или None, если файл не изменился)."""
    src = Path(src)
    store = store or STORE
    doc_id = doc_id or src.stem
    man = load_manifest(doc_id, store)
    digest = doclib.file_sha(src)
    if man["versions"] and man["versions"][-1]["sha"] == digest:
        return man, None
    v = len(man["versions"]) + 1
    ts = ts or datetime.now().isoformat(timespec="seconds")
    folder = store / doc_id
    folder.mkdir(parents=True, exist_ok=True)
    name = f"v{v}_{ts[:10]}{src.suffix.lower()}"
    shutil.copy2(src, folder / name)
    parsed = doclib.parse(src)
    (folder / f"v{v}.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    man["type"] = doc_type or man["type"] or parsed["type"]
    man["versions"].append({"v": v, "ts": ts, "file": name, "source": src.name, "sha": digest,
                            "sections": len(parsed["sections"]), "note": note or ""})
    save_manifest(man, store)
    return man, v


def load_version(doc_id, v, store=None):
    path = (store or STORE) / doc_id / f"v{v}.json"
    if not path.exists():
        sys.exit(f"{doc_id}: версии v{v} нет в хранилище")
    return json.loads(path.read_text(encoding="utf-8"))


def pair(man, a=None, b=None):
    if len(man["versions"]) < 2:
        sys.exit(f"{man['id']}: для сравнения нужно минимум две версии")
    return a or man["versions"][-2]["v"], b or man["versions"][-1]["v"]


def cmd_add(args):
    man, v = add_version(args.file, args.id, args.type, args.note)
    if v is None:
        print(f"{man['id']}: файл совпадает с v{man['versions'][-1]['v']}, новая версия не создана")
    else:
        ver = man["versions"][-1]
        print(f"{man['id']}: сохранена v{v} от {ver['ts']} ({ver['sections']} разд.)")
        if not man.get("current"):
            print("   действующая версия не назначена — это решает человек (versions.py current ... --by ...)")


def cmd_list(_):
    folders = sorted(p for p in STORE.iterdir() if p.is_dir()) if STORE.exists() else []
    if not folders:
        print("Хранилище пусто")
        return
    for folder in folders:
        man = load_manifest(folder.name)
        cur = (man.get("current") or {}).get("v")
        print(f"{man['id']}  [{man['type']}]  действующая: {'v' + str(cur) if cur else 'не назначена'}")
        for ver in man["versions"]:
            mark = "*" if ver["v"] == cur else " "
            print(f"  {mark}v{ver['v']}  {ver['ts']}  {ver['source']}  {ver['note']}")
        if cur:
            print(f"   (* действующая: {man['current'].get('by', '')}, {man['current'].get('date', '')})")


def cmd_diff(args):
    man = load_manifest(args.id)
    a, b = pair(man, args.a, args.b)
    pa, pb = load_version(args.id, a), load_version(args.id, b)
    diff = doclib.compare(pa, pb, "text_hash")
    ka, kb = doclib.keyed(pa), doclib.keyed(pb)
    print(f"{args.id}: v{a} -> v{b}. Изменено {len(diff['changed'])}, добавлено {len(diff['added'])}, "
          f"удалено {len(diff['removed'])}, без изменений {len(diff['same'])}")
    for k in diff["added"]:
        print(f"\n+ ДОБАВЛЕН РАЗДЕЛ: {k}")
    for k in diff["removed"]:
        print(f"\n- УДАЛЁН РАЗДЕЛ: {k}")
    for k in diff["changed"]:
        print(f"\n~ ИЗМЕНЁН: {k}")
        delta = difflib.unified_diff(doclib.section_lines(ka[k]), doclib.section_lines(kb[k]), lineterm="", n=0)
        for line in list(delta)[2:args.max_lines + 2]:
            if not line.startswith("@@"):
                print("   " + line)


def cmd_current(args):
    man = load_manifest(args.id)
    if not any(ver["v"] == args.v for ver in man["versions"]):
        sys.exit(f"{args.id}: версии v{args.v} нет. Есть: " + (", ".join(f"v{x['v']}" for x in man["versions"]) or "ни одной"))
    if not args.by.strip():
        sys.exit("Укажите в --by, кто и где принял решение (например: \"владелец, в чате 2026-10-02\")")
    old = (man.get("current") or {}).get("v")
    man["current"] = {"v": args.v, "by": args.by.strip(), "date": datetime.now().isoformat(timespec="seconds")}
    save_manifest(man)
    print(f"{args.id}: действующая версия — v{args.v}" + (f" (была v{old})" if old and old != args.v else "") + f". Решение: {args.by.strip()}")


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("file")
    p.add_argument("--id")
    p.add_argument("--type")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_add)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("diff")
    p.add_argument("id")
    p.add_argument("a", nargs="?", type=int)
    p.add_argument("b", nargs="?", type=int)
    p.add_argument("--max-lines", type=int, default=40)
    p.set_defaults(fn=cmd_diff)
    p = sub.add_parser("current")
    p.add_argument("id")
    p.add_argument("v", type=int)
    p.add_argument("--by", required=True)
    p.set_defaults(fn=cmd_current)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
