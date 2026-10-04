"""Учебные примеры для кейса «База знаний»: вымышленные документы и эталонный результат.

  python tools/demo.py load     положить учебный набор в hub/ (10 документов, словарь памяти); своё не перезаписывается
  python tools/demo.py result   дополнительно положить эталонный результат (заметка, противоречие, журнал вопросов) —
                                чтобы сразу посмотреть страницу и карту, не проходя сценарий
  python tools/demo.py clean    убрать всё учебное: файлы demo_* и строки с пометкой demo_ в служебных таблицах

Все данные набора вымышлены. Файлы набора называются demo_… — по этой пометке они и убираются.
Заметки, которые агент создал сам по учебным документам, clean не трогает — он их перечислит.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
DEMO = ROOT / "demo" / "hub"
RESULT = ROOT / "demo" / "пример_результата" / "hub"
MARK = "demo_"
TABLES = ("_противоречия.md", "_вопросы.md", "_уход.md", "journal.md")


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def copy_tree(src_root, overwrite):
    copied = skipped = rows = 0
    for src in sorted(src_root.rglob("*")):
        if src.is_dir():
            continue
        dst = HUB / src.relative_to(src_root)
        if src.name in TABLES:  # общие таблицы не заменяем: дописываем учебные строки, которых ещё нет
            have = dst.read_text(encoding="utf-8") if dst.exists() else ""
            new = [ln for ln in src.read_text(encoding="utf-8").splitlines() if MARK in ln and ln not in have]
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                rows += len(new)
            elif new:
                dst.write_text(have.rstrip("\n") + "\n" + "\n".join(new) + "\n", encoding="utf-8", newline="\n")
                rows += len(new)
            continue
        if dst.exists() and not overwrite:
            skipped += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied, skipped, rows


def need_hub():
    if not HUB.exists():
        sys.exit("Папки hub/ нет — сначала выполните: python tools/setup.py")


def load():
    need_hub()
    copied, skipped, _ = copy_tree(DEMO, overwrite=False)
    print(f"Учебный набор: положено файлов {copied}" + (f", уже было {skipped}" if skipped else ""))
    print("Дальше — в чате: «разбери входящее», затем вопросы из demo/README.md.")


def result():
    need_hub()
    load()
    copied, _, rows = copy_tree(RESULT, overwrite=True)
    print(f"Эталонный результат: файлов {copied}, строк в служебных таблицах {rows}")
    print("Посмотреть карту: python tools/kb_map.py; проверить связи: python tools/kb_lint.py check")


def clean():
    need_hub()
    removed = 0
    for path in sorted(HUB.rglob(MARK + "*")):
        if path.is_file() and ".secrets" not in path.parts:
            path.unlink()
            removed += 1
    rows = 0
    for name in TABLES:
        for path in HUB.rglob(name):
            lines = path.read_text(encoding="utf-8").splitlines()
            kept = [ln for ln in lines if MARK not in ln]
            if len(kept) != len(lines):
                rows += len(lines) - len(kept)
                path.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    left = []
    for path in sorted(HUB.rglob("*.md")):
        if ".secrets" in path.parts or ".obsidian" in path.parts:
            continue
        if MARK in path.read_text(encoding="utf-8", errors="replace"):
            left.append(path.relative_to(ROOT).as_posix())
    attach = HUB / "kb" / "входящее" / "вложения"
    if attach.exists() and not any(attach.iterdir()):
        attach.rmdir()
    print(f"Убрано учебных файлов: {removed}; строк в служебных таблицах: {rows}")
    if left:
        print("Остались файлы со ссылками на учебные документы (созданы не набором — решите сами, нужны ли они):")
        for item in left:
            print("  " + item)


def main():
    utf8()
    cmd = sys.argv[1:2]
    if cmd == ["load"]:
        load()
    elif cmd == ["result"]:
        result()
    elif cmd == ["clean"]:
        clean()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
