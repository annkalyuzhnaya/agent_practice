"""Создание шины hub/ внутри папки кейса «Входящие» из заготовок presets/hub/.

  python tools/setup.py           создать hub/ (существующие файлы не перезаписываются)
  python tools/setup.py status    показать состояние: среда, шаги настройки

Нужна только стандартная библиотека Python.
"""
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
PRESETS = ROOT / "presets" / "hub"
FOLDERS = ["inbox/new", "inbox/done", "inbox/triage", "inbox/drafts", "memory", "handoff"]
MARKS = {"сделано": "[x]", "отложено": "[~]", "недоступно в этой среде": "[-]"}


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def deploy():
    created = 0
    for folder in FOLDERS:
        (HUB / folder).mkdir(parents=True, exist_ok=True)
    for src in PRESETS.rglob("*"):
        if src.is_file() and src.name != ".gitkeep":
            dst = HUB / src.relative_to(PRESETS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
                created += 1
    return created


def steps():
    path = HUB / "setup.md"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d+\..+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3)))
    return rows


def mark_step0():
    path = HUB / "setup.md"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| 0.") and "не начат" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            cells[2], cells[3] = "сделано", date.today().isoformat()
            if len(cells) > 4 and not cells[4]:
                cells[4] = "шина создана скриптом; таблицу возможностей заполняет мастер"
            lines[i] = "| " + " | ".join(cells) + " |"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            return


def status():
    print(f"Папка кейса: {ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    if not HUB.exists():
        print("Шина hub/ не создана — выполните: python tools/setup.py")
        return
    print(f"Шина: {HUB}")
    print("Бот Telegram: " + ("файл настроек есть" if (HUB / ".secrets" / "telegram.json").exists() else "не настроен"))
    new = [p for p in (HUB / "inbox" / "new").glob("*") if p.is_file()]
    print(f"Необработанных файлов в hub/inbox/new: {len(new)}")
    for name, need, state in steps():
        print(f"  {MARKS.get(state, '[ ]')} {name} — {need}: {state}")


def main():
    utf8()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        status()
        return
    if not PRESETS.exists():
        sys.exit("Нет папки presets/hub — запускайте скрипт из папки кейса.")
    created = deploy()
    mark_step0()
    print(f"Шина готова: {HUB}")
    print(f"Новых файлов из заготовок: {created} (существующие не тронуты)")
    print("Дальше: напишите агенту «настрой входящие» или загрузите учебный набор — python tools/demo.py load")


if __name__ == "__main__":
    main()
