"""Парсер: docx/xlsx -> типизированная структура (разделы/листы, таблицы, хэши).

  python tools/parser.py файл.docx              # оглавление с хэшами
  python tools/parser.py файл.docx --json       # полная структура в stdout
  python tools/parser.py файл.xlsx --out x.json # полная структура в файл
"""
import argparse
import json
from pathlib import Path

import doclib


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    parsed = doclib.parse(args.file)
    if args.out:
        Path(args.out).write_text(json.dumps(parsed, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"Структура сохранена: {args.out}")
    elif args.json:
        print(json.dumps(parsed, ensure_ascii=False, indent=1, default=str))
    else:
        print(f"{parsed['file']} ({parsed['type']}), разделов: {len(parsed['sections'])}")
        for key, s in doclib.keyed(parsed).items():
            size = f"строк {len(s['rows'])}" if "rows" in s else f"абз. {len(s['paragraphs'])}, табл. {len(s['tables'])}"
            print(f"  {'  ' * max(s['level'] - 1, 0)}{key}  [{size}]  {s['text_hash']}")


if __name__ == "__main__":
    main()
