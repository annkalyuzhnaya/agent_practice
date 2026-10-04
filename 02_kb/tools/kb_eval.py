"""Проверка поиска по базе: «вопрос → ожидаемый источник» (уровень L5).

  python tools/kb_eval.py                          вопросы из demo/evals.json
  python tools/kb_eval.py --file hub/kb/_evals.json -n 5

Файл вопросов — список: {"question": "...", "expect": ["имя_файла", ...]} — имена заметок без расширения.
Для вопроса, на который в базе ответа нет, укажите "expect": [] — такой вопрос не проверяется поиском,
его проверяют на ответе агента: он должен сказать «в базе нет».
Вопрос засчитан, если хотя бы один ожидаемый источник есть среди первых N результатов поиска.
Это проверка поиска, а не ответа: что агент ответил по найденному, проверяет Проверяющий (playbooks/02_kb.md).
"""
import argparse
import json
import sqlite3
import sys

import kb_index
import kblib


def main():
    kblib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default="demo/evals.json")
    ap.add_argument("-n", type=int, default=5)
    args = ap.parse_args()
    kblib.need_hub()
    path = kblib.Path(args.file) if kblib.Path(args.file).is_absolute() else kblib.ROOT / args.file
    if not path.exists():
        sys.exit(f"Нет файла вопросов: {args.file}")
    cases = json.loads(kblib.read(path))
    kb_index.cmd_build(args)
    con = sqlite3.connect(kb_index.DB)
    passed = checked = 0
    for case in cases:
        expect = case.get("expect") or []
        found = [kblib.Path(r[0]).stem for r in kb_index.find(con, case["question"], args.n)[0]]
        if not expect:
            print(f"[—] {case['question']}\n     источника в базе нет: агент должен ответить «в базе нет» (поиск вернул: {', '.join(dict.fromkeys(found)) or 'ничего'})")
            continue
        checked += 1
        ok = any(e in found for e in expect)
        passed += ok
        print(f"[{'да' if ok else 'НЕТ'}] {case['question']}\n     ждали: {', '.join(expect)}; нашли: {', '.join(dict.fromkeys(found)) or 'ничего'}")
    print(f"\nИтог: {passed} из {checked} вопросов нашли ожидаемый источник в первых {args.n} результатах.")
    if passed < checked:
        sys.exit(1)


if __name__ == "__main__":
    main()
