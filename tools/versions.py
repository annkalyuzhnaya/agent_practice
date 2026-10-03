"""Версионное типизированное хранилище документов: hub/docs/store/<id>/.

  python tools/versions.py add файл.docx --id reglament --type регламент --note "правка сроков"
  python tools/versions.py list
  python tools/versions.py diff reglament            # две последние версии
  python tools/versions.py diff reglament 1 3        # конкретные версии

Каждая версия = копия файла + разобранная структура (JSON) + запись в manifest.json с таймстемпом.
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


def load_manifest(doc_id):
    path = STORE / doc_id / "manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"id": doc_id, "type": "", "versions": []}


def cmd_add(args):
    src = Path(args.file)
    doc_id = args.id or src.stem
    man = load_manifest(doc_id)
    digest = doclib.file_sha(src)
    if man["versions"] and man["versions"][-1]["sha"] == digest:
        print(f"{doc_id}: файл совпадает с v{man['versions'][-1]['v']}, новая версия не создана")
        return
    v = len(man["versions"]) + 1
    ts = datetime.now().isoformat(timespec="seconds")
    folder = STORE / doc_id
    folder.mkdir(parents=True, exist_ok=True)
    name = f"v{v}_{ts[:10]}{src.suffix.lower()}"
    shutil.copy2(src, folder / name)
    parsed = doclib.parse(src)
    (folder / f"v{v}.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    man["type"] = args.type or man["type"] or parsed["type"]
    man["versions"].append({"v": v, "ts": ts, "file": name, "source": src.name, "sha": digest, "note": args.note or ""})
    (folder / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{doc_id}: сохранена v{v} от {ts} ({len(parsed['sections'])} разд.)")


def cmd_list(_):
    if not STORE.exists():
        print("Хранилище пусто")
        return
    for folder in sorted(p for p in STORE.iterdir() if p.is_dir()):
        man = load_manifest(folder.name)
        print(f"{man['id']}  [{man['type']}]")
        for ver in man["versions"]:
            print(f"   v{ver['v']}  {ver['ts']}  {ver['source']}  {ver['note']}")


def cmd_diff(args):
    man = load_manifest(args.id)
    if len(man["versions"]) < 2:
        sys.exit(f"{args.id}: для сравнения нужно минимум две версии")
    a = args.a or man["versions"][-2]["v"]
    b = args.b or man["versions"][-1]["v"]
    load = lambda v: json.loads((STORE / args.id / f"v{v}.json").read_text(encoding="utf-8"))
    pa, pb = load(a), load(b)
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
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
