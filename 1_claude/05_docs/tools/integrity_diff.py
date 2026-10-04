"""Проверка целостности «до/после»: изменились ТОЛЬКО разрешённые разделы/листы.

  python tools/integrity_diff.py до.docx после.docx --allow "Сроки" --allow "Приложение"
  python tools/integrity_diff.py до.xlsx после.xlsx --allow "Свод"
  python tools/integrity_diff.py до.docx после.docx --allow "Сроки" --save     # отчёт в hub/docs/checks/

--allow — подстрока пути раздела (без учёта регистра). --text сравнивает только содержание,
игнорируя оформление. --save кладёт отчёт (JSON: имена, разделы, хэши — без текста документа)
в hub/docs/checks/, откуда его берёт страница «Документы».
Код возврата: 0 — целостность соблюдена, 1 — задето лишнее.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import doclib

CHECKS = doclib.HUB / "docs" / "checks"


def check(before, after, allow, text=False):
    """Сравнить два файла и вернуть отчёт-словарь (без текста документа)."""
    mode = "text_hash" if text else "xml_hash"
    pa, pb = doclib.parse(before), doclib.parse(after)
    diff = doclib.compare(pa, pb, mode)
    ka, kb = doclib.keyed(pa), doclib.keyed(pb)
    allowed = [a.lower() for a in allow]
    is_allowed = lambda key: any(a in key.lower() for a in allowed)
    touched = []
    for kind, keys in (("изменён", diff["changed"]), ("добавлен", diff["added"]), ("удалён", diff["removed"])):
        for k in keys:
            touched.append({"kind": kind, "section": k, "allowed": is_allowed(k),
                            "hash_before": ka[k][mode] if k in ka else "", "hash_after": kb[k][mode] if k in kb else ""})
    unused = [a for a in allow if not any(a.lower() in t["section"].lower() for t in touched)]
    return {"ts": datetime.now().isoformat(timespec="seconds"),
            "before": Path(before).name, "after": Path(after).name,
            "before_sha": doclib.file_sha(before), "after_sha": doclib.file_sha(after),
            "mode": "содержание" if text else "содержание и оформление",
            "allow": list(allow), "same": len(diff["same"]), "touched": touched, "unused_allow": unused,
            "ok": all(t["allowed"] for t in touched)}


def print_report(rep):
    print(f"Без изменений: {rep['same']} разд.")
    for t in rep["touched"]:
        print(f"  {'OK ' if t['allowed'] else 'НАРУШЕНИЕ'} {t['kind']}: {t['section']}")
    for a in rep["unused_allow"]:
        print(f"  ВНИМАНИЕ: разрешённый раздел «{a}» не изменился — правка не применилась?")
    bad = [t for t in rep["touched"] if not t["allowed"]]
    if bad:
        print(f"ИТОГ: ЦЕЛОСТНОСТЬ НАРУШЕНА — задето разделов вне разрешённых: {len(bad)}")
    else:
        print("ИТОГ: целостность соблюдена — вне разрешённых разделов изменений нет")


def save(rep):
    CHECKS.mkdir(parents=True, exist_ok=True)
    name = Path(rep["after"]).stem
    stem = name if name.startswith(rep["ts"][:10]) else f"{rep['ts'][:10]}_{name}"
    path, n = CHECKS / f"{stem}.json", 1
    while path.exists():
        n += 1
        path = CHECKS / f"{stem}_{n}.json"
    path.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--save", action="store_true", help="сохранить отчёт в hub/docs/checks/")
    args = ap.parse_args()

    rep = check(args.before, args.after, args.allow, args.text)
    print_report(rep)
    if args.save:
        print(f"Отчёт сохранён: {save(rep).relative_to(doclib.ROOT).as_posix()}")
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
