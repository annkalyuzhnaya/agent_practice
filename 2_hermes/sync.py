"""Переносит в кейсы трека Hermes то, что не зависит от среды: скрипты, учебные данные, заготовки hub/.

  python 2_hermes/sync.py            скопировать по таблице SHARED
  python 2_hermes/sync.py --check    только показать расхождения

Единый источник — кейс трека Claude. Копия нужна, чтобы папка кейса Hermes оставалась самодостаточной:
её можно скопировать без остального репозитория. Скопированное руками не правят — правят источник.
Файлы из KEEP у кейса Hermes свои (в них описана среда) и при переносе не трогаются.
"""
import filecmp
import shutil
import sys
from pathlib import Path

TRACK = Path(__file__).resolve().parent
ROOT = TRACK.parent
SOURCES = [ROOT / "1_claude", ROOT]  # где лежат кейсы трека Claude: новая раскладка, затем прежняя

# кейс: (что переносится, что в перенесённых папках остаётся своим)
SHARED = {
    "01_digest": (
        ["tools/digestlib.py", "tools/seen.py", "tools/issue.py", "tools/feedback.py", "tools/fetch_feeds.py",
         "tools/evals.py", "tools/demo.py", "demo", "presets/hub"],
        ["presets/hub/setup.md", "presets/hub/accounts.md", "presets/hub/routines.md", "presets/hub/models.md",
         "presets/hub/artifacts.md"],
    ),
}
JUNK = {"__pycache__", ".gitkeep"}


def files(src, item):
    path = src / item
    found = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    return [p.relative_to(src).as_posix() for p in found if not JUNK & set(p.parts) and p.name not in JUNK]


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    check = "--check" in sys.argv[1:]
    stale = 0
    for case, (items, keep) in SHARED.items():
        src = next((s / case for s in SOURCES if (s / case).exists()), None)
        if src is None:
            sys.exit(f"{case}: не найден кейс трека Claude (искал в 1_claude/ и в корне)")
        dst = TRACK / case
        wanted = [rel for item in items for rel in files(src, item) if rel not in keep]
        differs = [rel for rel in wanted
                   if not (dst / rel).exists() or not filecmp.cmp(src / rel, dst / rel, shallow=False)]
        if check:
            stale += bool(differs)
            print(f"{case}: " + (f"расходится — {', '.join(differs)}" if differs else "совпадает"))
            continue
        for rel in differs:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, dst / rel)
        print(f"{case}: файлов {len(wanted)}, обновлено {len(differs)} (источник: {src.relative_to(ROOT).as_posix()})")
    if check and stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
