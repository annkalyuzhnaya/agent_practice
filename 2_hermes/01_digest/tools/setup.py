"""Рабочая папка Обозревателя: создаёт hub/ внутри папки кейса из заготовок presets/hub/ и показывает состояние.

  python tools/setup.py           развернуть (существующие файлы не перезаписываются); скопированную папку кейса
                                  отметить как проект git — без этого Hermes не подключает навыки .hermes/skills/
  python tools/setup.py status    только показать состояние

Дальше настройку ведёт агент в чате Hermes по playbooks/02_setup.md; инструкция для человека — SETUP.md.
Только стандартная библиотека Python.
"""
import re
import shutil
import subprocess
import sys
from datetime import date

import digestlib as dl

PRESET = dl.ROOT / "presets" / "hub"
MODELS = dl.ROOT / "presets" / "models.json"
FOLDERS = ["digest", "digest/raw", "digest/cards", "kb/публикации", "page"]


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
    if MODELS.exists() and not (dl.HUB / "models.json").exists():
        shutil.copy2(MODELS, dl.HUB / "models.json")
        made.append("hub/models.json")
    return made


def project_root():
    """Ближайшая папка с .git вверх от папки кейса: только из неё Hermes берёт навыки .hermes/skills/."""
    return next((p for p in (dl.ROOT, *dl.ROOT.parents) if (p / ".git").exists()), None)


def make_project():
    """Скопированная папка кейса — не проект git, и навыки из неё Hermes не подключит: отметить её как проект."""
    if project_root() or not shutil.which("git"):
        return []
    try:
        subprocess.run(["git", "init", "-q"], cwd=dl.ROOT, check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    made = [".git/ (git init: без него Hermes не видит навыки папки)"]
    ignore = dl.ROOT / ".gitignore"
    if not ignore.exists():
        ignore.write_text("hub/\n.cache/\n__pycache__/\n", encoding="utf-8", newline="\n")
        made.append(".gitignore (hub/ — личные данные, в git не попадают)")
    return made


def skills_note():
    root = project_root()
    if root == dl.ROOT:
        return "папка кейса — проект git; доверие подтверждается один раз: hermes skills trust (затем новый чат)"
    if root:
        return (f"Hermes ищет навыки в корне проекта git — {root}, а не в папке кейса: скопируйте папку кейса "
                "в отдельное место (SETUP.md, шаг 3). Пока работают правила из AGENTS.md")
    return ("папка кейса — не проект git, навыки не подключатся: выполните в ней git init, затем hermes skills trust "
            "(SETUP.md, шаг 3). Пока работают правила из AGENTS.md")


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
    print("Hermes: " + ("команда hermes найдена — модели под роли: python tools/hermes.py status" if shutil.which("hermes")
                        else "команда hermes не найдена — установка: SETUP.md, шаг 1"))
    print("Навыки кейса: " + skills_note())
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
    made = deploy() + make_project()
    print(f"Создано: {len(made)}" + (":" if made else " (всё уже на месте)"))
    for item in made:
        print("  " + item)
    mark_step0()
    status()


if __name__ == "__main__":
    main()
