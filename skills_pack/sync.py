"""Раскладывает навыки пака по кейсам.

  python skills_pack/sync.py            разложить по manifest.json
  python skills_pack/sync.py --check    только показать расхождения

Единый источник — skills_pack/skills/. В каждом кейсе копия лежит в pack/skills/ (руками её не правят):
так папка кейса остаётся самодостаточной — её можно скопировать без остального репозитория.
Сборка кейса (tools/build.py) подключает pack/skills/ в .claude/skills/ и в плагин Cowork.
"""
import filecmp
import json
import shutil
import sys
from pathlib import Path

PACK = Path(__file__).resolve().parent
ROOT = PACK.parent
SKIP = shutil.ignore_patterns("__pycache__")


def same(a, b):
    if not b.exists():
        return False
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__"])
    stack = [cmp]
    while stack:
        c = stack.pop()
        if c.left_only or c.right_only or c.diff_files or c.funny_files:
            return False
        stack.extend(c.subdirs.values())
    return True


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    check = "--check" in sys.argv[1:]
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    stale = 0
    for case, skills in manifest.items():
        if case.startswith("_"):
            continue
        if not (ROOT / case).exists():
            print(f"{case}: папки кейса нет — пропущено")
            continue
        dst = ROOT / case / "pack"
        wanted = {name: PACK / "skills" / name for name in skills}
        missing = [n for n, p in wanted.items() if not p.exists()]
        if missing:
            sys.exit(f"{case}: в паке нет навыков: {', '.join(missing)}")
        differs = [n for n, p in wanted.items() if not same(p, dst / "skills" / n)]
        extra = [p.name for p in (dst / "skills").iterdir() if p.is_dir() and p.name not in wanted] if (dst / "skills").exists() else []
        if check:
            if differs or extra:
                stale += 1
                print(f"{case}: расходится — обновить: {differs or '—'}, лишние: {extra or '—'}")
            else:
                print(f"{case}: совпадает")
            continue
        if (dst / "skills").exists():
            shutil.rmtree(dst / "skills")
        for name, src in wanted.items():
            shutil.copytree(src, dst / "skills" / name, ignore=SKIP)
        if (dst / "licenses").exists():
            shutil.rmtree(dst / "licenses")
        shutil.copytree(PACK / "licenses", dst / "licenses")
        shutil.copy2(PACK / "THIRD_PARTY.md", dst / "THIRD_PARTY.md")
        print(f"{case}: {len(wanted)} навыков → {dst.relative_to(ROOT).as_posix()}/skills")
    if check and stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
