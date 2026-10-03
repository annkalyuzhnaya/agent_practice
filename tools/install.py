"""Установка ассистента из папки-исходника в отдельную папку ассистента.

  python tools/install.py                      показать, куда можно установить (или обновить уже установленное)
  python tools/install.py "путь"               установить или обновить в указанной папке
  python tools/install.py "путь" --with-data   заодно скопировать данные hub/ из исходника (если в папке ассистента их ещё нет)
  python tools/install.py "путь" --greeted     отметить, что приветствие уже показано (мастер показал его перед установкой)
  python tools/install.py where                показать, куда ассистент установлен

Исходник — это правила и скрипты; он не хранит личных данных. Папка ассистента — место, где система живёт:
туда копируются правила, скрипты, агенты и навыки и там создаётся шина hub/ с данными владельца.
Повторный запуск обновляет системные файлы и никогда не трогает hub/.
"""
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET_FILE = ROOT / ".install-target"          # где живёт ассистент, установленный из этого исходника
MARKER = "install.json"                         # признак папки ассистента
HOME_NAME = "Личный ассистент"

# системные файлы: при обновлении заменяются целиком
DIRS = ["playbooks", "tools", "artifacts", "demo/hub", "presets/hub", ".claude/agents", ".claude/skills"]
FILES = ["SETUP.md", "GUIDE.md", "requirements.txt", "dist/personal-hq.plugin", ".claude/settings.json"]
SKIP = shutil.ignore_patterns("__pycache__", "build.py", "install.py", ".gitkeep")


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def is_home(path):
    return (path / MARKER).exists()


def saved_target():
    if TARGET_FILE.exists():
        path = Path(TARGET_FILE.read_text(encoding="utf-8").strip())
        if is_home(path):
            return path
    return None


def suggestions():
    docs = Path.home() / "Documents"
    first = (docs if docs.exists() else Path.home()) / HOME_NAME
    return [first, ROOT.parent / HOME_NAME]


def version():
    for line in (ROOT / "tools" / "build.py").read_text(encoding="utf-8").splitlines():
        if line.startswith("VERSION"):
            return line.split('"')[1]
    return "?"


def install(home, with_data, greeted=False, demo=False):
    home = home.expanduser().resolve()
    if home == ROOT or ROOT in home.parents:
        sys.exit("Папка ассистента должна быть отдельной: выберите место вне папки-исходника.")
    if home.exists() and any(home.iterdir()) and not is_home(home) and not (home / "hub").exists():
        sys.exit(f"Папка «{home}» не пуста и не похожа на папку ассистента. Укажите пустую или новую папку.")
    if not (ROOT / ".claude" / "skills").exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")], check=True)

    update = is_home(home)
    home.mkdir(parents=True, exist_ok=True)
    for rel in DIRS:
        dst = home / rel
        if dst.exists():
            # саму папку может держать синхронизация диска или открытая сессия — тогда чистим содержимое и пишем поверх
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(ROOT / rel, dst, ignore=SKIP, dirs_exist_ok=True)
    for rel in FILES:
        dst = home / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    shutil.copy2(ROOT / "presets" / "home" / "CLAUDE.md", home / "CLAUDE.md")

    copied = False
    if with_data and (ROOT / "hub").exists() and not (home / "hub").exists():
        shutil.copytree(ROOT / "hub", home / "hub", ignore=shutil.ignore_patterns(".cache"))
        copied = True

    (home / MARKER).write_text(json.dumps({
        "source": str(ROOT), "version": version(), "updated": date.today().isoformat(),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    TARGET_FILE.write_text(str(home) + "\n", encoding="utf-8", newline="\n")

    print(("Обновлено" if update else "Установлено") + f": {home}  (версия {version()})")
    if copied:
        print("Данные hub/ скопированы из исходника. Прежняя папка hub в исходнике не тронута — удалите её сами, когда убедитесь, что всё на месте.")
    print()
    subprocess.run([sys.executable, str(home / "tools" / "setup.py")], check=True)
    if greeted:
        checklist = home / "hub" / "setup.md"
        text = checklist.read_text(encoding="utf-8")
        if "Приветствие: не показано" in text:
            checklist.write_text(text.replace("Приветствие: не показано", f"Приветствие: показано {date.today().isoformat()}"),
                                 encoding="utf-8", newline="\n")
    if demo:
        done = subprocess.run([sys.executable, str(home / "tools" / "demo.py"), "load"], cwd=str(home))
        if done.returncode == 0:
            print("Учебные примеры загружены (файлы demo_*). Убрать: скажите ассистенту «убери учебные примеры».")
        else:
            print("Учебные примеры не загружены: нет библиотек для Word и Excel. Установите их "
                  "(pip install -r requirements.txt) и выполните в папке ассистента: python tools/demo.py load")
    print(f"\nДальше: откройте в Claude новую сессию в папке «{home}» и напишите: настрой ассистента")


def main():
    utf8()
    flags = ("--with-data", "--greeted", "--demo", "--no-demo")
    args = [a for a in sys.argv[1:] if a not in flags]
    with_data = "--with-data" in sys.argv[1:]
    greeted = "--greeted" in sys.argv[1:]
    demo = "--demo" in sys.argv[1:]
    target = saved_target()
    if args == ["where"]:
        print(f"Ассистент установлен: {target}" if target else "Ассистент из этого исходника ещё не установлен.")
        return
    if args:
        install(Path(args[0]), with_data, greeted, demo)
        return
    if target:
        install(target, with_data, greeted, demo)
        return
    if sys.stdin.isatty():
        home = ask_path()
        if not demo and "--no-demo" not in sys.argv[1:]:
            demo = ask_demo()
        install(home, with_data, greeted, demo)
        return
    print("Ассистент ещё не установлен. Укажите папку, в которой он будет жить, например:")
    for path in suggestions():
        print(f'  python tools/install.py "{path}"')
    if (ROOT / "hub").exists():
        print("В исходнике есть папка hub с данными — чтобы перенести их, добавьте --with-data.")
    print("Чтобы сразу положить учебные примеры (письма, заметки, документы), добавьте --demo.")
    sys.exit(2)


def ask_demo():
    """Запуск в терминале: спросить, класть ли учебные примеры."""
    print("Загрузить учебные примеры (8 писем, заметки, документы), чтобы было на чём попробовать?")
    print("  1. Да  (советую для обучения)\n  2. Нет, начну со своих материалов")
    try:
        return input("> ").strip().lower() in ("", "1", "да", "y", "yes")
    except EOFError:
        return False


def ask_path():
    """Запуск в терминале без пути: предложить варианты и дать вписать свой."""
    options = suggestions()
    print("Где будет жить ассистент? Это отдельная папка для ваших писем, заметок и планов.")
    for number, path in enumerate(options, 1):
        print(f"  {number}. {path}" + ("  (советую)" if number == 1 else ""))
    print("Введите номер варианта или свой путь к новой папке. Пустой ввод — вариант 1.")
    while True:
        try:
            answer = input("> ").strip().strip('"')
        except EOFError:
            sys.exit(2)
        if not answer:
            return options[0]
        if answer.isdigit():
            if 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]
            print(f"Такого варианта нет. Введите число от 1 до {len(options)} или путь.")
            continue
        return Path(answer).expanduser()


if __name__ == "__main__":
    main()
