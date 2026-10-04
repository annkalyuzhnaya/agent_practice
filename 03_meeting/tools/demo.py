"""Учебный набор кейса «Подготовка к встрече» (все данные вымышленные).

  python tools/demo.py load     положить на шину вводные «до встречи»: письма, досье, прошлое мемо, строки календаря и задач
  python tools/demo.py after    положить заметки «после встречи» (вторая половина упражнения)
  python tools/demo.py clean    убрать учебные файлы (demo_*) и строки с пометкой «(учебный пример)»
  python tools/demo.py status   что из учебного набора сейчас лежит на шине

Учебная дата — 6 октября 2026 года: встреча с ООО «Северный контур» назначена на 7 октября.
Ничего не перезаписывает. Нужна только стандартная библиотека Python.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
DEMO = ROOT / "demo"
MARK = "(учебный пример)"
ROWS = {"calendar.md": DEMO / "rows" / "calendar.md", "tasks.md": DEMO / "rows" / "tasks.md"}


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def need_hub():
    if not HUB.exists():
        sys.exit("Нет папки hub/ — сначала выполните: python tools/setup.py")


def copy_tree(src):
    added = []
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            continue
        target = HUB / path.relative_to(src)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        added.append(target.relative_to(ROOT).as_posix())
    return added


def add_rows(name, source):
    target = HUB / name
    if not target.exists() or not source.exists():
        return 0
    text = target.read_text(encoding="utf-8")
    rows = [l for l in source.read_text(encoding="utf-8").splitlines() if l.startswith("|") and MARK in l and l not in text]
    if rows:
        target.write_text(text.rstrip("\n") + "\n" + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return len(rows)


def cmd_load():
    need_hub()
    added = copy_tree(DEMO / "hub")
    rows = {name: add_rows(name, src) for name, src in ROWS.items()}
    print(f"Учебный набор на шине: файлов добавлено {len(added)}, строк календаря {rows['calendar.md']}, строк задач {rows['tasks.md']}.")
    for name in added:
        print(f"  + {name}")
    print("Учебная дата — 6 октября 2026. Проверка: python tools/meetings.py upcoming --today 2026-10-06\n"
          "Дальше напишите агенту: «подготовь бриф к встрече с Северным контуром, сегодня 6 октября 2026».")


def cmd_after():
    need_hub()
    added = copy_tree(DEMO / "after")
    print("Заметки «после встречи» положены: " + (", ".join(added) if added else "уже лежат на шине."))
    print("Дальше напишите агенту: «встреча с Северным контуром прошла, заметки во входящих — оформи мемо».")


def demo_files():
    return sorted(p for p in HUB.rglob("demo_*") if p.is_file() and ".secrets" not in p.parts) if HUB.exists() else []


def cmd_clean():
    need_hub()
    files = demo_files()
    for path in files:
        path.unlink()
    removed = 0
    for name in ROWS:
        target = HUB / name
        if not target.exists():
            continue
        lines = target.read_text(encoding="utf-8").splitlines()
        keep = [l for l in lines if not (l.startswith("|") and MARK in l)]
        removed += len(lines) - len(keep)
        if len(keep) != len(lines):
            target.write_text("\n".join(keep) + "\n", encoding="utf-8", newline="\n")
    print(f"Убрано учебных файлов: {len(files)}; строк в календаре и задачах: {removed}.")
    made = sorted(p.relative_to(ROOT).as_posix() for p in HUB.rglob("*") if p.is_file() and ".secrets" not in p.parts
                  and "северный-контур" in p.name.lower())
    if made:
        print("Остались файлы, которые агент создал по учебному примеру, — их удаляете вы сами, если не нужны:")
        for name in made:
            print(f"  · {name}")
        print("Строки задач из учебного мемо остались в hub/tasks.md — попросите агента: «отмени задачи учебного примера».")


def cmd_status():
    need_hub()
    files = demo_files()
    print(f"Учебных файлов на шине: {len(files)}")
    for path in files:
        print(f"  · {path.relative_to(ROOT).as_posix()}")
    for name in ROWS:
        target = HUB / name
        count = sum(1 for l in target.read_text(encoding="utf-8").splitlines() if l.startswith("|") and MARK in l) if target.exists() else 0
        print(f"Учебных строк в {name}: {count}")


def main():
    utf8()
    commands = {"load": cmd_load, "after": cmd_after, "clean": cmd_clean, "status": cmd_status}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit("Использование: python tools/demo.py load | after | clean | status")
    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
