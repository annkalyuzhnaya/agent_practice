"""Рабочая папка hub/ кейса «База знаний»: структура, заготовки, пресет Obsidian, проверка среды.

  python tools/setup.py           развернуть (существующие файлы не перезаписываются)
  python tools/setup.py status    только показать состояние

hub/ создаётся внутри папки кейса из presets/hub/. Дальше настройку ведёт агент в чате (формы с вариантами)
по playbooks/12_setup.md; инструкция для человека — SETUP.md. Нужна только стандартная библиотека Python.
"""
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
PRESET = ROOT / "presets" / "hub"

FOLDERS = ["kb/контрагенты", "kb/решения", "kb/публикации", "kb/проекты", "kb/справки", "kb/входящее",
           "memory/people", "memory/context", "handoff"]


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
    """Шаги из hub/setup.md: (название, обязательность, статус)."""
    path = HUB / "setup.md"
    if not path.exists():
        return []
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0][:1].isdigit() and cells[1] in ("обязательный", "необязательный"):
            found.append((cells[0], cells[1], cells[2]))
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
    if not HUB.exists():
        print("Папка hub/ ещё не создана. Выполните: python tools/setup.py")
        return
    kb = HUB / "kb"
    notes = [p for p in kb.rglob("*.md") if not p.name.startswith("_") and "_шаблоны" not in p.parts]
    inbox = [p for p in notes if "входящее" in p.parts]
    print(f"Python: {sys.version.split()[0]}")
    print("Поиск по базе (FTS5): " + ("есть" if fts5() else "НЕТ — поиск будет чтением файлов"))
    print(f"Заметок в базе: {len(notes) - len(inbox)}; во входящем: {len(inbox)}")
    print("Obsidian-пресет: " + ("на месте (откройте папку hub как хранилище)" if (HUB / ".obsidian").exists() else "не развёрнут"))
    print("Словарь памяти: " + ("есть (hub/memory/glossary.md)" if (HUB / "memory" / "glossary.md").exists() else "нет"))
    print("Telegram: " + ("файл настроек есть" if (HUB / ".secrets" / "telegram.json").exists() else "не настроен (необязательно)"))
    found = steps()
    if found:
        marks = {"сделано": "[x]", "отложено": "[~]", "недоступно в этой среде": "[-]"}
        print("\nШаги настройки ([x] сделано, [~] отложено, [-] недоступно, [ ] не начат):")
        for name, need, state in found:
            print(f"  {marks.get(state, '[ ]')} {name} — {need}, {state}")
        todo = [s for s in found if s[2] == "не начат"]
        must = [s for s in todo if s[1] == "обязательный"]
        if must:
            print(f"\nСледующий шаг (обязательный): {must[0][0]}. Напишите в чат: «настрой».")
        elif todo:
            print(f"\nОбязательное готово — базой можно пользоваться. Не начато: {len(todo)}. Напишите в чат: «продолжи настройку».")
        else:
            print("\nНастройка пройдена. Памятка «как пользоваться» — GUIDE.md; в чате — слово «помощь».")


def main():
    utf8()
    if sys.argv[1:] == ["status"]:
        status()
        return
    if not PRESET.exists():
        sys.exit("Нет папки presets/hub/ — папка кейса скопирована не целиком.")
    made = deploy()
    print(f"Создано: {len(made)}" + (":" if made else " (всё уже на месте)"))
    for item in made:
        print("  " + item)
    mark_step0()
    status()
    print("\nУчебные примеры (по желанию): python tools/demo.py load")


if __name__ == "__main__":
    main()
