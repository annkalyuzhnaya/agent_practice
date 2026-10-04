"""Рабочая папка Обозревателя: создаёт hub/ внутри папки кейса из заготовок presets/hub/ и показывает состояние.

  python tools/setup.py           развернуть (существующие файлы не перезаписываются)
  python tools/setup.py status    только показать состояние

Дальше настройку ведёт агент в чате (формы с вариантами) по playbooks/02_setup.md; инструкция для человека — SETUP.md.
Только стандартная библиотека Python.
"""
import re
import shutil
import sys
from datetime import date

import digestlib as dl

PRESET = dl.ROOT / "presets" / "hub"
FOLDERS = ["digest", "digest/raw", "digest/cards", "kb/публикации", "handoff"]


def deploy():
    """Создать папки и скопировать заготовки, которых ещё нет. Возвращает список созданного."""
    made = []
    for folder in FOLDERS:
        path = dl.HUB / folder
        if not path.exists():
            path.mkdir(parents=True)
            made.append(f"hub/{folder}/")
    for src in sorted(PRESET.rglob("*")):
        rel = src.relative_to(PRESET)
        dst = dl.HUB / rel
        if src.is_dir():
            if not dst.exists():
                dst.mkdir(parents=True)
                made.append(f"hub/{rel.as_posix()}/")
        elif src.name != ".gitkeep" and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            made.append(f"hub/{rel.as_posix()}")
    return made


def steps():
    """Шаги из hub/setup.md: (название, обязательность, статус)."""
    path = dl.HUB / "setup.md"
    found = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0][:1].isdigit() and cells[1] in ("обязательный", "необязательный"):
                found.append((cells[0], cells[1], cells[2]))
    return found


def mark_step0():
    path = dl.HUB / "setup.md"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0].startswith("0.") and "не начат" in cells:
            head = cells[:cells.index("не начат")]
            lines[i] = "| " + " | ".join(head + ["сделано", date.today().isoformat(), "tools/setup.py"]) + " |"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            return


def status():
    print(f"Python: {sys.version.split()[0]} (скриптам кейса хватает стандартной библиотеки)")
    if not dl.HUB.exists():
        print("Рабочая папка hub/: не создана — выполните python tools/setup.py")
        return
    profile = dl.read_profile()
    with_feed = sum(bool(s["url"]) for s in profile["sources"])
    print("Профиль: " + (f"заполнен — тем {len(profile['topics'])}, источников {len(profile['sources'])} (с адресом: {with_feed}), "
                         f"период {profile['days']} дн." if profile["filled"] else "НЕ заполнен — напишите в чате «настрой»"))
    issues = [p for p in dl.DIGEST.glob("*.md") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)]
    rows, _ = dl.read_seen()
    print(f"Выпусков: {len(issues)}" + (f" (последний {max(p.stem for p in issues)})" if issues else "") + f"; в памяти «уже видел»: {len(rows)}")
    secret = dl.HUB / ".secrets" / "telegram.json"
    print("Telegram: " + ("файл настроек есть — проверка: python tools/tg_bridge.py check" if secret.exists() else "не настроен (необязательно)"))
    print("Tavily (усиленный поиск): " + ("команда tvly найдена" if shutil.which("tvly") else "не установлен (необязательно; базовый путь — встроенный веб-поиск)"))
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
            print(f"\nОбязательное готово — можно просить «дайджест». Не начато: {len(todo)}. Напишите в чат: «продолжи настройку».")
        else:
            print("\nНастройка пройдена. Памятка — GUIDE.md; в чате — слово «помощь».")


def main():
    dl.utf8()
    if sys.argv[1:] == ["status"]:
        status()
        return
    made = deploy()
    print(f"Создано: {len(made)}" + (":" if made else " (всё уже на месте)"))
    for item in made:
        print("  " + item)
    mark_step0()
    status()


if __name__ == "__main__":
    main()
