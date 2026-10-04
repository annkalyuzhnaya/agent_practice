"""Шаг 0 настройки: создаёт шину hub/ в папке кейса из заготовок presets/hub/ и показывает состояние.

  python tools/setup.py           создать недостающее (существующие файлы не перезаписываются)
  python tools/setup.py status    что настроено и что осталось

Нужна только стандартная библиотека Python. Содержимое hub/.secrets/ не читается — проверяется только наличие файла.
"""
import importlib.util
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
PRESETS = ROOT / "presets" / "hub"
FOLDERS = ["handoff", "inbox/new", "docs/in", "docs/out", "docs/templates", "docs/store", "docs/checks"]
LIBS = {"docx": "python-docx", "openpyxl": "openpyxl"}
MARKS = {"сделано": "[x]", "отложено": "[~]", "недоступно в этой среде": "[-]"}


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def deploy():
    created = []
    for src in sorted(PRESETS.rglob("*")):
        if src.is_dir() or src.name == ".gitkeep":
            continue
        dst = HUB / src.relative_to(PRESETS)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            created.append(dst.relative_to(ROOT).as_posix())
    for name in FOLDERS:
        folder = HUB / name
        if not folder.exists():
            folder.mkdir(parents=True)
            created.append(f"hub/{name}/")
    return created


def steps():
    path = HUB / "setup.md"
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0][:1].isdigit():
                rows.append(cells)
    return rows


def mark_step0():
    path = HUB / "setup.md"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and cells[0].startswith("0.") and cells[2] != "сделано":
            cells[2], cells[3], cells[4] = "сделано", date.today().isoformat(), "tools/setup.py"
            lines[i] = "| " + " | ".join(cells) + " |"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def status():
    print(f"Папка кейса: {ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    missing = [pkg for mod, pkg in LIBS.items() if importlib.util.find_spec(mod) is None]
    if missing:
        print("Библиотеки Word/Excel: НЕТ " + ", ".join(missing) + " — выполните: pip install -r requirements.txt")
        print("   (без них работают заявки, реестр и мост Telegram; сборка и проверка документов — нет)")
    else:
        print("Библиотеки Word/Excel: есть (python-docx, openpyxl)")
    print("Telegram-бот: " + ("файл настроек есть" if (HUB / ".secrets" / "telegram.json").exists() else "не подключён (необязательно)"))
    if not HUB.exists():
        print("Шина hub/: не создана — выполните: python tools/setup.py")
        return
    new = [p for p in (HUB / "handoff").glob("*.md")] if (HUB / "handoff").exists() else []
    store = [p for p in (HUB / "docs" / "store").iterdir() if p.is_dir()] if (HUB / "docs" / "store").exists() else []
    print(f"Шина hub/: есть. Заявок: {len(new)}, документов в хранилище версий: {len(store)}")
    rows = steps()
    if rows:
        print("Шаги настройки (hub/setup.md):")
        for cells in rows:
            print(f"  {MARKS.get(cells[2], '[ ]')} {cells[0]} — {cells[2]}" + (f" ({cells[1]})" if cells[2] == "не начат" else ""))
        todo = [c[0] for c in rows if c[2] == "не начат"]
        print("Дальше: скажите Claude «продолжи настройку»" if todo else "Настройка завершена.")


def main():
    utf8()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status()
        return
    if not PRESETS.exists():
        sys.exit("Нет папки presets/hub — запускайте из папки кейса: python tools/setup.py")
    created = deploy()
    mark_step0()
    if created:
        print("Создано:")
        for name in created:
            print("  " + name)
    else:
        print("Шина уже на месте — ничего не перезаписано.")
    print()
    status()
    print("\nУчебные примеры: python tools/demo.py load   (убрать: python tools/demo.py clean)")


if __name__ == "__main__":
    main()
