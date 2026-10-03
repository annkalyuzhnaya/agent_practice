"""Проверка целостности «до/после»: изменились ТОЛЬКО разрешённые разделы/листы.

  python tools/integrity_diff.py до.docx после.docx --allow "Сроки" --allow "Приложение"
  python tools/integrity_diff.py до.xlsx после.xlsx --allow "Свод"

--allow — подстрока пути раздела (без учёта регистра). --text сравнивает только содержание,
игнорируя оформление. Код возврата: 0 — целостность соблюдена, 1 — задето лишнее.
"""
import argparse
import sys

import doclib


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--text", action="store_true")
    args = ap.parse_args()

    diff = doclib.compare(doclib.parse(args.before), doclib.parse(args.after),
                          "text_hash" if args.text else "xml_hash")
    allowed = [a.lower() for a in args.allow]
    is_allowed = lambda key: any(a in key.lower() for a in allowed)

    touched = [("изменён", k) for k in diff["changed"]] + [("добавлен", k) for k in diff["added"]] + \
              [("удалён", k) for k in diff["removed"]]
    violations = [(kind, k) for kind, k in touched if not is_allowed(k)]
    unused = [a for a in args.allow if not any(a.lower() in k.lower() for _, k in touched)]

    print(f"Без изменений: {len(diff['same'])} разд.")
    for kind, k in touched:
        print(f"  {'OK ' if is_allowed(k) else 'НАРУШЕНИЕ'} {kind}: {k}")
    for a in unused:
        print(f"  ВНИМАНИЕ: разрешённый раздел «{a}» не изменился — правка не применилась?")
    if violations:
        print(f"ИТОГ: ЦЕЛОСТНОСТЬ НАРУШЕНА — задето разделов вне разрешённых: {len(violations)}")
        sys.exit(1)
    print("ИТОГ: целостность соблюдена — вне разрешённых разделов изменений нет")


if __name__ == "__main__":
    main()
