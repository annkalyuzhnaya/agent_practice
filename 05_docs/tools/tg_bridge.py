"""Мост Telegram ↔ шина для кейса «Документ-инженер». Бот разговаривает только с владельцем.

  python tools/tg_bridge.py init                 создать заготовку hub/.secrets/telegram.json (токен вписывает владелец)
  python tools/tg_bridge.py check                проверить токен
  python tools/tg_bridge.py whoami               узнать свой номер (owner_id)
  python tools/tg_bridge.py pull                 забрать сообщения владельца: текст → заявка в hub/handoff/, файл → hub/docs/in/
  python tools/tg_bridge.py send --text "Готово: проверка пройдена, версия 3"       написать владельцу
  python tools/tg_bridge.py send-file --file hub/docs/out/файл.docx --confirmed      отправить владельцу готовый файл

Правила: принимаются сообщения только из личного чата владельца (owner_id); писать бот может только владельцу.
Файлы принимаются: .docx, .xlsx, .xlsm, .json, .md, .txt до 20 МБ; остальные вложения не скачиваются.
Файл наружу уходит только из hub/docs/out/ и только с флагом --confirmed — его ставят после явного «да» владельца
на отправку именно этого файла. Нужна только стандартная библиотека Python.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

import handoff

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
CONFIG = HUB / ".secrets" / "telegram.json"
OFFSET = ROOT / ".cache" / "tg_offset.txt"
DOCS_IN = HUB / "docs" / "in"
DOCS_OUT = HUB / "docs" / "out"
MAX_FILE = 20 * 1024 * 1024
ALLOWED = {".docx", ".xlsx", ".xlsm", ".json", ".md", ".txt"}
TEMPLATE = {"token": "", "owner_id": 0}


def config():
    if not CONFIG.exists():
        sys.exit("Нет hub/.secrets/telegram.json — выполните: python tools/tg_bridge.py init")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not cfg.get("token"):
        sys.exit("В hub/.secrets/telegram.json не вписан токен бота (поле token). Его вписывает владелец.")
    return cfg


def call(method, request):
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        # адрес запроса содержит токен — в сообщение об ошибке его не выводим
        sys.exit(f"Telegram ответил ошибкой {e.code} на {method}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"Нет связи с Telegram ({method}): {e.reason}")
    if not body.get("ok"):
        sys.exit(f"Telegram отказал в {method}: {body.get('description')}")
    return body["result"]


def api(cfg, method, **params):
    url = f"https://api.telegram.org/bot{cfg['token']}/{method}"
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
    return call(method, urllib.request.Request(url, data=data))


def api_upload(cfg, method, fields, field, path):
    """multipart/form-data средствами стандартной библиотеки."""
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8"))
    name = path.name.replace('"', "'")
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
                 f"Content-Type: application/octet-stream\r\n\r\n".encode("utf-8") + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    req = urllib.request.Request(f"https://api.telegram.org/bot{cfg['token']}/{method}", data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return call(method, req)


def updates(cfg, offset=None):
    return api(cfg, "getUpdates", offset=offset, timeout=0, allowed_updates=json.dumps(["message"]))


def who(user):
    if not user:
        return "неизвестно"
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
    return f"{name} (@{user['username']})" if user.get("username") else name or str(user.get("id"))


def cmd_init(_):
    if CONFIG.exists():
        print("hub/.secrets/telegram.json уже есть — не трогаю.")
        return
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Создан hub/.secrets/telegram.json.\n"
          "1. В Telegram откройте @BotFather → /newbot → получите токен.\n"
          "2. Впишите токен в поле token этого файла сами (в чат его не отправляйте).\n"
          "3. Напишите своему боту /start и выполните: python tools/tg_bridge.py whoami")


def cmd_check(_):
    me = api(config(), "getMe")
    print(f"Бот на связи: @{me.get('username')} ({me.get('first_name')})")


def cmd_whoami(_):
    seen = {}
    for upd in updates(config()):
        msg = upd.get("message") or {}
        if (msg.get("chat") or {}).get("type") == "private":
            seen[msg["from"]["id"]] = who(msg.get("from"))
    if not seen:
        print("Боту пока никто не писал (или сообщения уже забраны). Напишите ему /start и повторите.")
    for user_id, name in seen.items():
        print(f"личный чат: {name} — owner_id: {user_id}")


def save_file(cfg, msg, when):
    """Скачать вложение в hub/docs/in/. Вернуть (относительный путь или '', примечание или '')."""
    doc = msg.get("document")
    if not doc:
        other = next((k for k in ("photo", "video", "voice", "audio", "sticker") if msg.get(k)), "")
        return "", (f"вложение типа «{other}» не скачано — принимаются только файлы Word/Excel и данные" if other else "")
    name = Path(doc.get("file_name") or "файл").name
    if Path(name).suffix.lower() not in ALLOWED:
        return "", f"файл «{name}» не скачан — тип не из списка {', '.join(sorted(ALLOWED))}"
    if doc.get("file_size", 0) > MAX_FILE:
        return "", f"файл «{name}» не скачан — больше 20 МБ (ограничение Telegram для ботов); передайте его через папку"
    info = api(cfg, "getFile", file_id=doc["file_id"])
    DOCS_IN.mkdir(parents=True, exist_ok=True)
    target, n = DOCS_IN / f"{when:%Y-%m-%d}_tg_{name}", 1
    while target.exists():  # исходники не перезаписываются
        n += 1
        target = DOCS_IN / f"{when:%Y-%m-%d}_tg_{n}_{name}"
    url = f"https://api.telegram.org/file/bot{cfg['token']}/{info['file_path']}"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            target.write_bytes(resp.read())
    except urllib.error.URLError:
        return "", f"файл «{name}» не удалось скачать — повторите пересылку"
    return target.relative_to(ROOT).as_posix(), ""


def cmd_pull(_):
    cfg = config()
    owner = cfg.get("owner_id")
    if not owner:
        sys.exit("Не задан owner_id: выполните whoami и впишите свой номер в hub/.secrets/telegram.json")
    offset = int(OFFSET.read_text()) if OFFSET.exists() else None
    made = skipped = 0
    last = None
    for upd in updates(cfg, offset):
        last = upd["update_id"]
        msg = upd.get("message")
        if not msg:
            continue
        if msg["chat"].get("type") != "private" or (msg.get("from") or {}).get("id") != owner:
            skipped += 1
            continue
        text = (msg.get("text") or msg.get("caption") or "").strip()
        if text == "/start":
            continue
        when = datetime.fromtimestamp(msg["date"])
        saved, note = save_file(cfg, msg, when)
        questions = []
        if not text:
            questions.append("Файл пришёл без пояснения — что с ним сделать?")
            text = "(пояснения нет)"
        if note:
            questions.append(note[0].upper() + note[1:])
        title = text if len(text) <= 70 else text[:67] + "…"
        path = handoff.create(title if text != "(пояснения нет)" else f"Файл из Telegram {Path(saved).name or ''}".strip(),
                              text, [saved] if saved else [], f"telegram ({when:%H:%M})", "code",
                              when=f"{when:%Y-%m-%d}", questions=questions)
        made += 1
        print(f"  заявка: {path.relative_to(ROOT).as_posix()}" + (f"; файл: {saved}" if saved else ""))
    if last is not None:
        OFFSET.parent.mkdir(exist_ok=True)
        OFFSET.write_text(str(last + 1))
    print(f"Новых заявок из Telegram: {made}" + (f"; пропущено чужих сообщений: {skipped}" if skipped else ""))


def owner_chat(cfg):
    if not cfg.get("owner_id"):
        sys.exit("Не задан owner_id.")
    return cfg["owner_id"]


def cmd_send(args):
    cfg = config()
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    if not text or not text.strip():
        sys.exit("Пустой текст.")
    chat_id = owner_chat(cfg)
    for start in range(0, len(text), 4000):
        api(cfg, "sendMessage", chat_id=chat_id, text=text[start:start + 4000], disable_web_page_preview="true")
    print(f"Отправлено владельцу: {len(text)} знаков")


def cmd_send_file(args):
    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        sys.exit(f"Нет файла: {args.file}")
    try:
        path.resolve().relative_to(DOCS_OUT.resolve())
    except ValueError:
        sys.exit("Отправлять можно только готовые файлы из hub/docs/out/.")
    if path.stat().st_size > 50 * 1024 * 1024:
        sys.exit("Файл больше 50 МБ — Telegram не примет его от бота.")
    if not args.confirmed:
        sys.exit("Файл уходит наружу только после явного «да» владельца на отправку именно этого файла (флаг --confirmed).")
    cfg = config()
    api_upload(cfg, "sendDocument", {"chat_id": owner_chat(cfg), "caption": (args.caption or "")[:1000]}, "document", path)
    print(f"Файл отправлен владельцу: {path.name}")


def main():
    handoff.utf8()
    parser = argparse.ArgumentParser(description="Мост Telegram ↔ шина (кейс «Документ-инженер»)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("init", cmd_init), ("check", cmd_check), ("whoami", cmd_whoami), ("pull", cmd_pull)):
        sub.add_parser(name).set_defaults(fn=fn)
    send = sub.add_parser("send")
    send.add_argument("--chat", default="me", choices=["me"], help="бот пишет только владельцу")
    group = send.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--text-file")
    send.set_defaults(fn=cmd_send)
    sf = sub.add_parser("send-file")
    sf.add_argument("--file", required=True)
    sf.add_argument("--caption")
    sf.add_argument("--confirmed", action="store_true")
    sf.set_defaults(fn=cmd_send_file)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
