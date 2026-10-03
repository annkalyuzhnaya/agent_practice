"""Шина в папке ассистента: структура папок, заготовки, пресет Obsidian, проверка среды.
Запускается установкой (tools/install.py из папки-исходника) и повторно — чтобы досоздать недостающее.

  python tools/setup.py           развернуть (существующие файлы не перезаписываются)
  python tools/setup.py status    только показать состояние

Дальше настройку ведёт ассистент в чате (формы с вариантами) по playbooks/12_setup.md; инструкция для человека — SETUP.md.
"""
import importlib.util
import shutil
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
PRESET = ROOT / "presets" / "hub"

FOLDERS = ["inbox/new", "inbox/done", "inbox/triage", "inbox/drafts", "digest", "meetings", "plan", "handoff",
           "docs/in", "docs/out", "docs/templates", "docs/store"]
LIBS = {"docx": "python-docx", "openpyxl": "openpyxl"}


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def deploy():
    """Создать папки и скопировать заготовки, которых ещё нет. Возвращает список созданного."""
    made = []
    for folder in FOLDERS:
        path = HUB / folder
        if not path.exists():
            path.mkdir(parents=True)
            made.append(f"hub/{folder}/")
    for src in sorted(PRESET.rglob("*")):
        rel = src.relative_to(PRESET)
        dst = HUB / rel
        if src.is_dir():
            if not dst.exists():
                dst.mkdir(parents=True)
                made.append(f"hub/{rel.as_posix()}/")
        elif src.name != ".gitkeep" and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            made.append(f"hub/{rel.as_posix()}")
    return made


def fts5():
    try:
        sqlite3.connect(":memory:").execute("create virtual table t using fts5(x)")
        return True
    except sqlite3.Error:
        return False


def steps():
    """Шаги из hub/setup.md: (название, обязательность, статус). Понимает и старый вид таблицы без колонки «Обязательность»."""
    path = HUB / "setup.md"
    if not path.exists():
        return []
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[0][:1].isdigit():
            continue
        if cells[1] in ("обязательный", "необязательный") and len(cells) >= 3:
            found.append((cells[0], cells[1], cells[2]))
        else:
            found.append((cells[0], "обязательный" if cells[0][:1] in "01" else "необязательный", cells[1]))
    return found


def mark_step0():
    path = HUB / "setup.md"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells[0].startswith("0.") or "не начат" not in cells:
            continue
        head = cells[:cells.index("не начат")]
        lines[i] = "| " + " | ".join(head + ["сделано", date.today().isoformat(), "tools/setup.py"]) + " |"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        return


def status():
    missing = [pip for mod, pip in LIBS.items() if importlib.util.find_spec(mod) is None]
    print(f"Python: {sys.version.split()[0]}")
    print("Библиотеки документов: " + ("есть" if not missing else "НЕТ — выполните: pip install -r requirements.txt"))
    print("Поиск по базе (FTS5): " + ("есть" if fts5() else "НЕТ — поиск будет чтением файлов"))
    print("Обсидиан-пресет: " + ("на месте (откройте папку hub как хранилище)" if (HUB / ".obsidian").exists() else "не развёрнут"))
    secret = HUB / ".secrets" / "telegram.json"
    print("Telegram: " + ("файл настроек есть" if secret.exists() else "не настроен (необязательно)"))
    found = steps()
    if found:
        marks = {"сделано": "[x]", "отложено": "[~]", "недоступно в этой среде": "[-]"}
        print("\nШаги настройки ([x] сделано, [~] отложено, [ ] не начат):")
        for name, need, state in found:
            print(f"  {marks.get(state, '[ ]')} {name} — {need}, {state}")
        todo = [s for s in found if s[2] == "не начат"]
        must = [s for s in todo if s[1] == "обязательный"]
        if must:
            print(f"\nСледующий шаг (обязательный): {must[0][0]}. Напишите ассистенту в чат: «настрой ассистента».")
        elif todo:
            print(f"\nОбязательное готово — ассистентом можно пользоваться. Не начато: {len(todo)}. Напишите в чат: «продолжи настройку».")
        else:
            print("\nНастройка пройдена. Памятка «как пользоваться» — GUIDE.md; в чате — слово «помощь».")
    return missing


def main():
    utf8()
    if sys.argv[1:] == ["status"]:
        status()
        return
    if (ROOT / "tools" / "install.py").exists():
        print("Это папка-исходник: шина hub/ здесь не создаётся. Установите ассистента в отдельную папку:")
        print("  python tools/install.py")
        return
    made = deploy()
    print(f"Создано: {len(made)}" + (":" if made else " (всё уже на месте)"))
    for item in made:
        print("  " + item)
    mark_step0()
    missing = status()
    if missing:
        print("\nДля работы с Word и Excel установите библиотеки: pip install -r requirements.txt")


if __name__ == "__main__":
    main()
