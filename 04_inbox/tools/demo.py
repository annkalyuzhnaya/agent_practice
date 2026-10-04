"""Учебный набор (синтетика) кейса «Входящие».

  python tools/demo.py load    разложить демо-данные по шине hub/ (существующие файлы не трогает)
  python tools/demo.py clean   убрать демо-файлы из шины

Все демо-файлы начинаются с demo_ — их легко отличить от своих. Эталон разбора — demo/пример_результата/.
Нужна только стандартная библиотека Python.
"""
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
SRC = ROOT / "demo" / "hub"


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def cmd_load(_):
    if not HUB.exists():
        sys.exit("Шина hub/ не создана — сначала выполните: python tools/setup.py")
    copied = 0
    for src in SRC.rglob("*"):
        if src.is_file():
            dst = HUB / src.relative_to(SRC)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
                copied += 1
    print(f"Учебный набор разложен по hub/: файлов {copied}. Теперь напишите агенту «разбери входящие».")


def cmd_clean(_):
    removed = 0
    if HUB.exists():
        for path in list(HUB.rglob("demo_*")):
            if path.is_file():
                path.unlink()
                removed += 1
    print(f"Удалено демо-файлов: {removed}. Строки, которые агент успел внести по учебному набору в общие файлы "
          f"(inbox/mail.md, tasks.md, journal.md), а также разбор в inbox/triage/ и черновики в inbox/drafts/ "
          f"проверьте вручную.")


def main():
    utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load").set_defaults(fn=cmd_load)
    sub.add_parser("clean").set_defaults(fn=cmd_clean)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
