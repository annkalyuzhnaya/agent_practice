"""Учебный набор (синтетика) для обкатки стенда.

  python tools/demo.py load    # разложить демо-данные по шине hub/ (существующие файлы не трогает)
  python tools/demo.py clean   # убрать демо-данные из шины

Все демо-файлы начинаются с demo_ — их легко отличить от своих.
"""
import argparse
import json
import shutil

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font

import doclib

SRC = doclib.ROOT / "demo" / "hub"

SECTIONS = [
    ("1. Общие положения", ["Регламент определяет порядок согласования документов направления.",
                            "Действие регламента распространяется на всех сотрудников и подрядчиков направления."]),
    ("2. Роли участников", ["Инициатор готовит документ и отвечает за полноту комплекта.",
                            "Согласующий проверяет документ в пределах своей компетенции."]),
    ("3. Сроки согласования", ["Срок согласования документа составляет 5 рабочих дней.",
                               "Срочные документы согласуются за 2 рабочих дня по решению руководителя."]),
    ("4. Порядок эскалации", ["При нарушении срока инициатор уведомляет руководителя направления.",
                              "Повторное нарушение выносится на еженедельное совещание."]),
    ("5. Отчётность", ["Ежемесячный отчёт формируется до 5-го числа по шаблону отчёта направления."]),
]


def make_reglament(path):
    doc = Document()
    doc.add_heading("Регламент согласования документов", 0)
    doc.add_paragraph("Версия для обкатки стенда. Все данные синтетические.")
    for title, paragraphs in SECTIONS:
        doc.add_heading(title, 1)
        for text in paragraphs:
            doc.add_paragraph(text)
        if title.startswith("2."):
            t = doc.add_table(rows=1, cols=2)
            t.style = "Table Grid"
            t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Роль", "Зона ответственности"
            for role, zone in [("Инициатор", "Комплект документа"), ("Согласующий", "Экспертиза"),
                               ("Руководитель", "Решение по спорным вопросам")]:
                cells = t.add_row().cells
                cells[0].text, cells[1].text = role, zone
    doc.save(str(path))


def make_report_template(path):
    doc = Document()
    doc.add_heading("Отчёт направления «{{направление}}» за {{период}}", 0)
    doc.add_heading("1. Итоги периода", 1)
    doc.add_paragraph("Выполнено задач: {{выполнено}} из {{всего}}. Ответственный: {{ответственный}}.")
    doc.add_heading("2. Задачи", 1)
    t = doc.add_table(rows=2, cols=3)
    t.style = "Table Grid"
    for cell, text in zip(t.rows[0].cells, ["Задача", "Статус", "Срок"]):
        cell.text = text
    for cell, text in zip(t.rows[1].cells, ["{{rows:задачи}}{{задача}}", "{{статус}}", "{{срок}}"]):
        cell.text = text
    doc.add_heading("3. Риски и решения", 1)
    doc.add_paragraph("{{риски}}")
    doc.save(str(path))


TASKS = [
    {"задача": "Пилот агента-обозревателя", "статус": "выполнено", "срок": "2026-09-12", "часы": 14},
    {"задача": "Обновление регламента согласования", "статус": "в работе", "срок": "2026-10-09", "часы": 6},
    {"задача": "Практикум для руководителей", "статус": "выполнено", "срок": "2026-09-26", "часы": 22},
    {"задача": "Договор с подрядчиком по обучению", "статус": "просрочено", "срок": "2026-09-30", "часы": 3},
]


def make_export(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Задачи"
    ws.append(["Задача", "Статус", "Срок", "Часы"])
    for t in TASKS:
        ws.append([t["задача"], t["статус"], t["срок"], t["часы"]])
    ws2 = wb.create_sheet("Бюджет")
    ws2.append(["Статья", "План", "Факт"])
    for row in [["Обучение", 400, 380], ["Лицензии", 250, 250], ["Подрядчики", 600, 710]]:
        ws2.append(row)
    wb.save(str(path))


def make_summary_template(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Свод"
    ws["A1"] = "Сводка за {{период}}"
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    ws.append(["Задача", "Статус", "Часы"])
    for c in ws[3]:
        c.font = Font(bold=True)
    ws.append(["{{rows:задачи}}{{задача}}", "{{статус}}", "{{часы}}"])
    wb.save(str(path))


def cmd_load(_):
    copied = 0
    for src in SRC.rglob("*"):
        if src.is_file():
            dst = doclib.HUB / src.relative_to(SRC)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
                copied += 1
    docs_in = doclib.HUB / "docs" / "in"
    templates = doclib.HUB / "docs" / "templates"
    for folder in (docs_in, templates):
        folder.mkdir(parents=True, exist_ok=True)
    make_reglament(docs_in / "demo_регламент.docx")
    make_export(docs_in / "demo_выгрузка.xlsx")
    make_report_template(templates / "demo_шаблон_отчёта.docx")
    make_summary_template(templates / "demo_шаблон_сводки.xlsx")
    data = {"направление": "Цифровые сервисы", "период": "сентябрь 2026", "ответственный": "А. Иванова (условно)",
            "выполнено": sum(t["статус"] == "выполнено" for t in TASKS), "всего": len(TASKS), "задачи": TASKS,
            "риски": "Перерасход по подрядчикам: факт 710 при плане 600. Требуется решение руководителя."}
    (docs_in / "demo_данные_отчёта.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (docs_in / "demo_правка_сроков.md").write_text(
        "Срок согласования документа составляет 3 рабочих дня.\n"
        "Срочные документы согласуются за 1 рабочий день по решению руководителя.\n"
        "Срок исчисляется со дня, следующего за днём поступления полного комплекта.\n", encoding="utf-8")
    print(f"Демо-набор разложен по hub/: текстовых файлов {copied}, офисных 4 (+ данные и правка)")


def cmd_clean(_):
    removed = 0
    for path in list(doclib.HUB.rglob("demo_*")):
        if path.is_file():
            path.unlink()
            removed += 1
    store = doclib.HUB / "docs" / "store"
    if store.exists():
        for folder in store.glob("demo_*"):
            shutil.rmtree(folder)
            removed += 1
    print(f"Удалено демо-объектов: {removed}. Записи, которые агенты успели внести в общие файлы "
          f"(tasks.md, calendar.md, journal.md, digest/seen.md), проверьте вручную.")


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load").set_defaults(fn=cmd_load)
    sub.add_parser("clean").set_defaults(fn=cmd_clean)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
