"""Приёмка выпуска на учебном наборе: сравнение с ожидаемым результатом (demo/evals/expected.json).

  python tools/evals.py                                  последний выпуск из hub/digest/
  python tools/evals.py --issue demo/пример_результата/digest/2026-10-02.md
  python tools/evals.py --expected свой_набор.json       свой набор проверочных примеров (уровень L5)

Проверяет не слова, а решения агента: что попало в выпуск, что отсеяно, какие оценки, что в ТОП-3,
не выполнена ли инструкция, вложенная в текст источника. Код возврата: 0 — всё пройдено, 1 — есть провалы.
"""
import argparse
import json
import sys
from pathlib import Path

import digestlib as dl


def main():
    dl.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--issue")
    ap.add_argument("--expected", default="demo/evals/expected.json")
    args = ap.parse_args()

    exp_path = Path(args.expected) if Path(args.expected).is_absolute() else dl.ROOT / args.expected
    if not exp_path.exists():
        sys.exit(f"Нет файла с ожидаемым результатом: {args.expected}")
    exp = json.loads(exp_path.read_text(encoding="utf-8"))
    if args.issue:
        path = Path(args.issue) if Path(args.issue).is_absolute() else dl.ROOT / args.issue
        if not path.exists():
            sys.exit(f"Нет файла выпуска: {args.issue}")
    else:
        dl.need_hub()
        path = dl.latest_issue(exp.get("issue_date"))
    issue = dl.parse_issue(path)
    tops = [dl.norm_title(t) for t in issue["top3"]]
    by_url = {dl.norm_url(i["url"]): i for i in issue["items"]}
    skipped_text = " ".join(issue["skipped"]).lower()
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"  {'пройдено' if ok else 'ПРОВАЛ  '}  {name}" + (f" — {detail}" if detail and not ok else ""))

    print(f"Выпуск: {dl.rel(path)}; набор: {dl.rel(exp_path)}")
    check(f"позиций не больше {exp.get('max_positions', 10)}", len(issue["items"]) <= exp.get("max_positions", 10),
          f"позиций {len(issue['items'])}")
    for pos in exp.get("positions", []):
        item = by_url.get(dl.norm_url(pos["url"]))
        check(f"{pos['key']}: в выпуске", item is not None, "нет позиции с этой ссылкой")
        if item is None:
            continue
        tol = exp.get("score_tolerance", 1)
        check(f"{pos['key']}: оценка {pos['score']}±{tol}", abs(item["score"] - pos["score"]) <= tol, f"поставлено {item['score']}")
        in_top = any(dl.norm_title(item["title"]) in t for t in tops)
        check(f"{pos['key']}: {'в ТОП-3' if pos.get('top') else 'не в ТОП-3'}", in_top == bool(pos.get("top")))
        check(f"{pos['key']}: поля «тема», TL;DR, «почему важно», «что сделать»",
              all(item[k] for k in ("topic", "tldr", "why", "action")))
    for skip in exp.get("skipped", []):
        absent = dl.norm_url(skip["url"]) not in by_url
        check(f"{skip['key']}: не в позициях ({skip['why']})", absent, "попало в выпуск")
        named = dl.norm_url(skip["url"]).lower() in skipped_text or any(h.lower() in skipped_text for h in skip.get("hints", []))
        check(f"{skip['key']}: названо в «Пропущено»", named, "человек не узнает, что материал отсеян")
    for ban in exp.get("forbidden", []):
        check(f"{ban['key']}: не возвращается ({ban['why']})", dl.norm_url(ban["url"]) not in by_url, "попало в выпуск повторно")
    text = path.read_text(encoding="utf-8").lower()
    for phrase in exp.get("must_not_contain", []):
        check(f"в выпуске нет следов вложенной инструкции: «{phrase}»", phrase.lower() not in text)
    check("раздел «Что остаётся человеку» заполнен", bool(issue["human"]))

    passed = sum(results)
    print(f"Итог: {passed} из {len(results)}" + (" — приёмка пройдена." if passed == len(results) else " — есть провалы, выпуск на доработку."))
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
