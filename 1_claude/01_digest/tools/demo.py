"""Учебный набор (синтетика) для обкатки Обозревателя без интернета.

  python tools/demo.py load    разложить учебные данные в hub/ (свои файлы не трогает)
  python tools/demo.py clean   убрать учебные данные из hub/ и всё, что агент собрал по ним

Что кладёт load:
  - образец профиля — только если свой профиль ещё не заполнен;
  - пакет из 10 учебных публикаций → hub/digest/raw/demo_пакет_10источников.md;
  - строку «(демо)» в память «уже видел» (публикация S06 уже была в прошлом выпуске);
  - строку «(демо)» в очередь «посмотри это».
Учебные файлы начинаются с demo_, учебные строки помечены «(демо)» — их легко отличить от своих.
"""
import argparse
import re
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


def demo_hosts():
    """Адреса сайтов учебного пакета: по ним узнаём всё, что агент создал из учебных публикаций."""
    return sorted({u.split("/")[2] for u in dl.URL_RE.findall(PACKET.read_text(encoding="utf-8"))})


def drop_lines(path, bad):
    """Убрать из файла строки, для которых bad(строка) истинно. Возвращает число убранных."""
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [x for x in lines if not bad(x)]
    if len(kept) != len(lines):
        path.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    return len(lines) - len(kept)


def cmd_clean(_):
    dl.need_hub()
    removed = 0
    hosts = demo_hosts()

    def demo_text(text):
        return "(демо)" in text or any(h in text for h in hosts)

    for path in list(dl.HUB.rglob("demo_*")):
        if path.is_file():
            path.unlink()
            removed += 1
    # Выпуски, карточки, данные страницы и заметки, собранные из учебных публикаций.
    days = set()
    made = [p for p in dl.DIGEST.glob("*.md") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)]
    made += list(dl.CARDS.glob("*")) + list(dl.DIGEST.glob("page_*.json")) + list((dl.HUB / "kb").rglob("*.md"))
    for path in made:
        if path.is_file() and demo_text(path.read_text(encoding="utf-8", errors="ignore")):
            if path.parent == dl.DIGEST and path.suffix == ".md":
                days.add(path.stem)
            path.unlink()
            removed += 1
    for path in LINE_FILES:
        removed += drop_lines(path, demo_text)
    # Задачи и строки бортжурнала, которые ссылаются на учебный выпуск.
    removed += drop_lines(dl.HUB / "tasks.md",
                          lambda x: demo_text(x) or any(f"digest/{d}.md" in x for d in days))
    removed += drop_lines(dl.HUB / "journal.md",
                          lambda x: x.startswith("|") and ("учебн" in x or any(d in x for d in days)))
    if dl.PROFILE.exists() and MARK in dl.PROFILE.read_text(encoding="utf-8"):
        shutil.copy2(dl.ROOT / "presets" / "hub" / "profile.md", dl.PROFILE)
        removed += 1
        print("Учебный профиль заменён пустой заготовкой — заполните свой: «настрой профиль».")
    print(f"Удалено учебных объектов: {removed} — вместе с выпуском, карточкой, заметками, задачами и строками "
          f"бортжурнала, собранными по учебному набору. Предложения по темам в hub/digest/topics.md не тронуты.")


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
