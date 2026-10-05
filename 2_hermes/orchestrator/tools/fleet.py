#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Реестр флота оркестратора: показать, какими командами поднимать ассистентов, и проверить среду.

Только стандартная библиотека. Ключей API не читает и не хранит.

    python tools/fleet.py show     — распечатать флот и точную команду запуска для каждого ассистента
    python tools/fleet.py check    — проверить: есть ли hermes в PATH, существуют ли папки локальных ассистентов

Источник данных — hub/fleet.json (формат — в playbooks/20_fleet.md). Запускать из папки оркестратора.
"""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FLEET = os.path.join(ROOT, "hub", "fleet.json")


def load_fleet():
    if not os.path.exists(FLEET):
        print("Нет hub/fleet.json — флот ещё не заведён. Заполни по playbooks/20_fleet.md.")
        return None
    try:
        with open(FLEET, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"Не читается hub/fleet.json: {e}")
        return None
    items = data.get("assistants", [])
    if not items:
        print("В hub/fleet.json пустой список assistants — добавь ассистентов по playbooks/20_fleet.md.")
    return items


def shq(value: str) -> str:
    """Экранировать значение для одинарных кавычек в команде-примере."""
    return (value or "").replace("'", "'\\''")


def command_for(a: dict) -> str:
    """Строка-пример запуска ассистента (её оркестратор показывает владельцу / выполняет сам)."""
    task = "<задача: что сделать, какой файл результата создать>"
    opts = ""
    if a.get("model"):
        opts += f" --model '{shq(a['model'])}'"
    if a.get("provider"):
        opts += f" --provider '{shq(a['provider'])}'"
    where = a.get("where", "local")
    if where == "remote":
        host = a.get("host", "")
        if host == "folder":
            return "(общая папка) запуск не нужен — читаю свежий файл из синхронизируемой папки"
        if host == "telegram":
            return "(telegram) запуск не нужен — владелец пересылает выпуск в чат"
        path = shq(a.get("path", "<path>"))
        return f"ssh {host} \"cd '{path}' && hermes chat -q '{task}'{opts}\""
    # local
    path = a.get("path", "<path>")
    return f"(cwd={path}) hermes chat -q '{task}'{opts}"


def cmd_show():
    items = load_fleet()
    if not items:
        return 0 if items == [] else 1
    print(f"Флот оркестратора — {len(items)} ассистент(ов):\n")
    for a in items:
        name = a.get("name", "?")
        role = a.get("role", "?")
        where = a.get("where", "local")
        loc = a.get("path", "") if where == "local" else f"{a.get('host', '')}:{a.get('path', '')}"
        model = a.get("model") or "(модель Hermes по умолчанию)"
        print(f"• {name}  [роль: {role} · {where} · {model}]")
        print(f"    где:      {loc}")
        print(f"    читаю:    {a.get('reads', '(не указано)')}")
        print(f"    поднять:  {command_for(a)}")
        if a.get("note"):
            print(f"    заметка:  {a['note']}")
        print()
    print("Запускать локального ассистента — в его папке (cwd=path). Удалённую команду — только после «да» владельца.")
    return 0


def cmd_check():
    items = load_fleet()
    if items is None:
        return 1
    print("Проверка среды оркестратора:\n")
    hermes = shutil.which("hermes")
    print(f"  hermes в PATH: {'да, ' + hermes if hermes else 'НЕ найден — локальных ассистентов не поднять'}")
    print()
    if not items:
        return 0
    print("Ассистенты:")
    ok = True
    for a in items:
        name = a.get("name", "?")
        where = a.get("where", "local")
        if where == "local":
            path = a.get("path", "")
            exists = path and os.path.isdir(path)
            print(f"  • {name}: папка {'есть' if exists else 'НЕ найдена: ' + (path or '(путь пуст)')}")
            ok = ok and bool(exists)
        else:
            host = a.get("host", "")
            print(f"  • {name}: удалённый ({host}) — проверка подключения только после «да» владельца (см. 30_remote.md)")
    print()
    print("Готово." if ok else "Есть незаполненные пути — поправь hub/fleet.json (playbooks/20_fleet.md).")
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "show"
    if cmd == "show":
        return cmd_show()
    if cmd == "check":
        return cmd_check()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
