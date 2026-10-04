"""Первый запуск кейса «Подготовка к встрече»: создаёт шину hub/ из заготовок и показывает, что настроено.

  python tools/setup.py           создать hub/ (ничего не перезаписывая) и показать состояние
  python tools/setup.py status    только показать состояние

Нужна только стандартная библиотека Python. Профиль, каналы, расписание и страницу настраивает агент в чате («настрой»).
"""
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
PRESETS = ROOT / "presets" / "hub"
FOLDERS = ["meetings", "meetings/print", "inbox/new", "inbox/done", "inbox/drafts", "handoff",
           "kb/контрагенты", "kb/решения", "kb/_шаблоны"]


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def deploy():
    if not PRESETS.exists():
        sys.exit("Нет папки presets/hub — папка кейса скопирована не полностью.")
    created = []
    for folder in FOLDERS:
        (HUB / folder).mkdir(parents=True, exist_ok=True)
    for src in sorted(PRESETS.rglob("*")):
        if src.is_dir() or src.name == ".gitkeep":
            continue
        target = HUB / src.relative_to(PRESETS)
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        created.append(target.relative_to(ROOT).as_posix())
    return created


def mark_step0():
    path = HUB / "setup.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    new = re.sub(r"(\| 0\. [^|]*\|[^|]*\|) не начат \| *\|", rf"\1 сделано | {date.today():%Y-%m-%d} |", text, count=1)
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")


def steps():
    path = HUB / "setup.md"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.match(r"\d+\.", cells[0]):
            out.append((cells[0], cells[1], cells[2]))
    return out


def status():
    print(f"Папка кейса: {ROOT}")
    if not HUB.exists():
        print("Шины hub/ ещё нет — выполните: python tools/setup.py")
        return
    profile = HUB / "profile.md"
    filled = profile.exists() and "профиль не заполнен" not in profile.read_text(encoding="utf-8")
    print(f"Python: {sys.version.split()[0]} — скрипты кейса работают")
    print(f"Профиль: {'заполнен' if filled else 'не заполнен — напишите агенту «настрой»'}")
    print(f"Субагенты и навыки: {'собраны' if (ROOT / '.claude' / 'agents' / 'meeting-archivist.md').exists() else 'не собраны — python tools/build.py'}")
    token = HUB / ".secrets" / "telegram.json"
    print(f"Telegram: {'файл настроек создан (проверка — python tools/tg_bridge.py check)' if token.exists() else 'не подключён'}")
    for name, need, state in steps():
        print(f"  [{'x' if state == 'сделано' else ' '}] {name} — {need}, {state}")
    print("Дальше: откройте эту папку в Claude Code и напишите «настрой» — или сразу «покажи на примере».")


def main():
    utf8()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status()
        return
    if len(sys.argv) > 1:
        sys.exit("Неизвестная команда. Доступно: python tools/setup.py [status]")
    created = deploy()
    mark_step0()
    print(f"Шина готова: hub/. Новых файлов: {len(created)}" + (" (всё уже было на месте)" if not created else ""))
    for name in created:
        print(f"  + {name}")
    status()


if __name__ == "__main__":
    main()
