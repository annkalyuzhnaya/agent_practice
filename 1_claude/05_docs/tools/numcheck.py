"""Сверка чисел: каждое число собранного документа должно находиться в источниках.

  python tools/numcheck.py отчёт.docx данные.json выгрузка.xlsx
  python tools/numcheck.py сводка.xlsx данные.json --ignore 2026

Берёт все числа из документа (по разделам/листам) и ищет каждое в источниках (.json, .xlsx, .docx, .md/.txt).
Числа, которых нет ни в одном источнике, печатаются с разделом — их валидатор проверяет вручную:
это либо расчётное значение (пересчитать самому вторым способом), либо выдумка.
Номера разделов в заголовках («1.», «2.3») не проверяются. Код возврата: 0 — все числа найдены, 1 — есть ненайденные.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import doclib

NUM = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)?(?![\w]|[.,]\d)")


def norm(token):
    """'710,0' и '710.00' -> '710'; '3,50' -> '3.5'."""
    t = token.replace(",", ".").lstrip("+")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t or "0"


def numbers(text):
    return [norm(m.group(0)) for m in NUM.finditer(str(text))]


def flatten(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from flatten(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from flatten(v)
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, (int, float)):
        yield norm(repr(value))
    else:
        yield from numbers(value)


def source_numbers(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return set(flatten(json.loads(path.read_text(encoding="utf-8"))))
    if suffix in (".docx", ".xlsx", ".xlsm"):
        found = set()
        for s in doclib.parse(path)["sections"]:
            found.update(flatten(s.get("rows", [])))
            found.update(flatten(doclib.section_lines(s) if "rows" not in s else []))
        return found
    return set(numbers(path.read_text(encoding="utf-8", errors="replace")))


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("document")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--ignore", action="append", default=[], help="число, которое не проверять (например, год)")
    args = ap.parse_args()

    known = set()
    for src in args.sources:
        known |= source_numbers(src)
    ignore = {norm(x) for x in args.ignore}
    total, missing = 0, []
    for key, s in doclib.keyed(doclib.parse(args.document)).items():
        cells = s["rows"] if "rows" in s else doclib.section_lines(s)
        for n in flatten(cells):
            total += 1
            if n not in known and n not in ignore:
                missing.append((key, n))
    print(f"Чисел в документе: {total}; найдено в источниках: {total - len(missing)}; источников: {len(args.sources)}")
    for key, n in missing:
        print(f"  НЕТ В ИСТОЧНИКАХ: {n} — раздел «{key}»")
    if missing:
        print(f"ИТОГ: {len(missing)} чисел не найдено в источниках — проверьте вручную (расчётное значение или ошибка)")
        sys.exit(1)
    print("ИТОГ: все числа документа есть в источниках")


if __name__ == "__main__":
    main()
