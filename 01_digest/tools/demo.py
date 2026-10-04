"""Учебный набор (синтетика) для обкатки Обозревателя без интернета.

  python tools/demo.py load    разложить учебные данные в hub/ (свои файлы не трогает)
  python tools/demo.py clean   убрать учебные данные из hub/

Что кладёт load:
  - образец профиля — только если свой профиль ещё не заполнен;
  - пакет из 10 учебных публикаций → hub/digest/raw/demo_пакет_10источников.md;
  - строку «(демо)» в память «уже видел» (публикация S06 уже была в прошлом выпуске);
  - строку «(демо)» в очередь «посмотри это».
Учебные файлы начинаются с demo_, учебные строки помечены «(демо)» — их легко отличить от своих.
"""
import argparse
import shutil

import digestlib as dl

DEMO = dl.ROOT / "demo"
PACKET = DEMO / "digest_10источников.md"
SAMPLE = DEMO / "профиль_образец.md"
MARK = "<!-- демо-профиль -->"
EMPTY = "профиль не заполнен"
SEEN_LINE = "- 2026-09-22 | https://events.example/conf/ai-office-2026 | (демо) Конференция «ИИ в офисе — 2026»: открыта регистрация"
QUEUE_LINE = ("| 2026-10-01 | ссылка | (демо) посмотри, что там про экономию времени | "
              "https://metrics-lab.example/blog/time-saved | чат, владелец | новое |")
LINE_FILES = [dl.SEEN, dl.QUEUE, dl.MARKS]


def cmd_load(_):
    dl.need_hub()
    done = []
    profile = dl.PROFILE.read_text(encoding="utf-8") if dl.PROFILE.exists() else EMPTY
    if EMPTY in profile:
        shutil.copy2(SAMPLE, dl.PROFILE)
        done.append("образец профиля → hub/profile.md")
    elif MARK not in profile:
        done.append("свой профиль не тронут (учебный образец — demo/профиль_образец.md)")
    target = dl.RAW / "demo_пакет_10источников.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(PACKET, target)
        done.append("пакет публикаций → " + dl.rel(target))
    for path, line in ((dl.SEEN, SEEN_LINE), (dl.QUEUE, QUEUE_LINE)):
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if line not in text:
            dl.append_line(path, line)
            done.append(f"строка «(демо)» → {dl.rel(path)}")
    print("Учебный набор разложен:" if done else "Учебный набор уже на месте.")
    for item in done:
        print("  " + item)
    print("Дальше — в чате: «собери дайджест по учебному пакету, дата выпуска 2026-10-02».")


def cmd_clean(_):
    dl.need_hub()
    removed = 0
    for path in list(dl.HUB.rglob("demo_*")):
        if path.is_file():
            path.unlink()
            removed += 1
    for path in LINE_FILES:
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            kept = [x for x in lines if "(демо)" not in x]
            if len(kept) != len(lines):
                path.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
                removed += len(lines) - len(kept)
    if dl.PROFILE.exists() and MARK in dl.PROFILE.read_text(encoding="utf-8"):
        shutil.copy2(dl.ROOT / "presets" / "hub" / "profile.md", dl.PROFILE)
        removed += 1
        print("Учебный профиль заменён пустой заготовкой — заполните свой: «настрой профиль».")
    print(f"Удалено учебных объектов: {removed}. Выпуски, карточки и строки, которые агент успел создать по учебному набору "
          f"(hub/digest/2026-10-02.md, записи в seen.md, tasks.md, journal.md), проверьте и уберите вручную.")


def main():
    dl.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load").set_defaults(fn=cmd_load)
    sub.add_parser("clean").set_defaults(fn=cmd_clean)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
