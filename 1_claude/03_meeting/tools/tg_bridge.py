"""Мост Telegram ↔ шина кейса «Подготовка к встрече». Бот — почтовый ящик: владелец присылает ему заметки после встречи
и вводные, агент пишет владельцу выжимку брифа накануне и напоминания. Сценарии — playbooks/15_telegram.md.

  python tools/tg_bridge.py init                 создать заготовку hub/.secrets/telegram.json (токен вписывает владелец)
  python tools/tg_bridge.py check                проверить токен
  python tools/tg_bridge.py whoami               кто писал боту: номера пользователей и чатов (для owner_id и списка chats)
  python tools/tg_bridge.py pull                 забрать новые сообщения в hub/inbox/new/
  python tools/tg_bridge.py send --chat me --text "..."            написать владельцу
  python tools/tg_bridge.py send --chat ИМЯ --text-file f.md --confirmed   написать в группу из списка chats

Правила: принимаются сообщения только от владельца (owner_id) и из чатов списка chats; писать можно только владельцу
и в чаты списка; в группу — только с флагом --confirmed, который ставится после согласия владельца с точным текстом.
Нужна только стандартная библиотека Python.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
CONFIG = HUB / ".secrets" / "telegram.json"
OFFSET = ROOT / ".cache" / "tg_offset.txt"
INBOX = HUB / "inbox" / "new"
MAX_FILE = 20 * 1024 * 1024
TEMPLATE = {"token": "", "owner_id": 0, "chats": {}}


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def config():
    if not CONFIG.exists():
        sys.exit("Нет hub/.secrets/telegram.json — выполните: python tools/tg_bridge.py init")
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except ValueError:
        sys.exit("Файл hub/.secrets/telegram.json испорчен (не читается как JSON). Проверьте кавычки и запятые "
                 "или удалите файл и выполните: python tools/tg_bridge.py init")
    if not cfg.get("token"):
        sys.exit("В hub/.secrets/telegram.json не вписан токен бота (поле token). Его вписывает владелец.")
    return cfg


def api(cfg, method, **params):
    url = f"https://api.telegram.org/bot{cfg['token']}/{method}"
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=40) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        # адрес запроса содержит токен — в сообщение об ошибке его не выводим
        sys.exit(f"Telegram ответил ошибкой {e.code} на {method}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"Нет связи с Telegram ({method}): {e.reason}")
    if not body.get("ok"):
        sys.exit(f"Telegram отказал в {method}: {body.get('description')}")
    return body["result"]


def updates(cfg, offset=None):
    return api(cfg, "getUpdates", offset=offset, timeout=0, allowed_updates=json.dumps(["message", "channel_post"]))


def who(user):
    if not user:
        return "неизвестно"
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or user.get("title") or ""
    return f"{name} (@{user['username']})" if user.get("username") else name or str(user.get("id"))


def forwarded_from(msg):
    origin = msg.get("forward_origin")
    if not origin:
        return ""
    return (who(origin.get("sender_user")) if origin.get("sender_user") else
            origin.get("sender_user_name") or who(origin.get("chat") or origin.get("sender_chat")))


def slug(text):
    words = re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", text)[:5]
    return "-".join(words).lower()[:50] or "сообщение"


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
    cfg = config()
    seen = {}
    for upd in updates(cfg):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat:
            seen[chat["id"]] = (chat.get("type"), chat.get("title") or who(msg.get("from")), (msg.get("from") or {}).get("id"))
    if not seen:
        print("Боту пока никто не писал (или сообщения уже забраны). Напишите ему /start и повторите.")
    for chat_id, (kind, title, user_id) in seen.items():
        if kind == "private":
            print(f"личный чат: {title} — owner_id: {user_id}")
        else:
            print(f"{kind}: {title} — номер чата для списка chats: {chat_id}")


def save_file(cfg, msg, stem):
    doc = msg.get("document") or msg.get("voice") or msg.get("audio") or (msg.get("photo") or [None])[-1]
    if not doc or doc.get("file_size", 0) > MAX_FILE:
        return ""
    info = api(cfg, "getFile", file_id=doc["file_id"])
    ext = Path(doc.get("file_name") or info["file_path"]).suffix
    target = INBOX / f"{stem}{ext}"
    url = f"https://api.telegram.org/file/bot{cfg['token']}/{info['file_path']}"
    with urllib.request.urlopen(url, timeout=120) as resp:
        target.write_bytes(resp.read())
    return target.name


def cmd_pull(_):
    cfg = config()
    owner = cfg.get("owner_id")
    if not owner:
        sys.exit("Не задан owner_id: выполните whoami и впишите свой номер в hub/.secrets/telegram.json")
    allowed = {int(v): k for k, v in cfg.get("chats", {}).items()}
    offset = int(OFFSET.read_text()) if OFFSET.exists() else None
    INBOX.mkdir(parents=True, exist_ok=True)
    saved = skipped = 0
    last = None
    for upd in updates(cfg, offset):
        last = upd["update_id"]
        msg = upd.get("message") or upd.get("channel_post")
        if not msg:
            continue
        chat = msg["chat"]
        sender = (msg.get("from") or {}).get("id")
        private = chat.get("type") == "private"
        if not ((private and sender == owner) or chat["id"] in allowed):
            skipped += 1
            continue
        text = msg.get("text") or msg.get("caption") or ""
        if text.strip() == "/start":
            continue
        when = datetime.fromtimestamp(msg["date"])
        fwd = forwarded_from(msg)
        stem = f"{when:%Y-%m-%d}_tg_{when:%H%M}_{msg['message_id']}_{slug(text)}"
        attached = save_file(cfg, msg, stem)
        if private and not fwd:
            kind = "сообщение владельца (заметки или вводные)"
        elif private:
            kind = "переслано владельцем"
        else:
            kind = f"группа «{allowed[chat['id']]}»"
        lines = ["---", "type: входящее", f"date: {when:%Y-%m-%d}", "agent: tg_bridge", "status: новое", "tags: [telegram]",
                 "sources: [Telegram]", "---",
                 f"**Канал:** Telegram, {kind}", f"**Получено:** {when:%Y-%m-%d %H:%M}",
                 f"**Автор:** {fwd or who(msg.get('from') or msg.get('sender_chat'))}"]
        if attached:
            lines.append(f"**Вложение:** {attached}")
        lines += ["", text or "(без текста)"]
        (INBOX / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        saved += 1
    if last is not None:
        OFFSET.parent.mkdir(exist_ok=True)
        OFFSET.write_text(str(last + 1))
    print(f"Новых сообщений на шине: {saved}" + (f"; пропущено чужих: {skipped}" if skipped else ""))


def cmd_send(args):
    cfg = config()
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    if not text or not text.strip():
        sys.exit("Пустой текст.")
    if args.chat == "me":
        chat_id = cfg.get("owner_id")
        if not chat_id:
            sys.exit("Не задан owner_id.")
    else:
        if args.chat not in cfg.get("chats", {}):
            sys.exit(f"Чата «{args.chat}» нет в списке chats. Доступны: {', '.join(cfg.get('chats', {})) or 'нет'}")
        if not args.confirmed:
            sys.exit("Сообщение в группу отправляется только после согласия владельца с точным текстом (флаг --confirmed).")
        chat_id = cfg["chats"][args.chat]
    for start in range(0, len(text), 4000):
        api(cfg, "sendMessage", chat_id=chat_id, text=text[start:start + 4000], disable_web_page_preview="true")
    print(f"Отправлено: {args.chat}, {len(text)} знаков")


def main():
    utf8()
    parser = argparse.ArgumentParser(description="Мост Telegram ↔ шина")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("init", cmd_init), ("check", cmd_check), ("whoami", cmd_whoami), ("pull", cmd_pull)):
        sub.add_parser(name).set_defaults(fn=fn)
    send = sub.add_parser("send")
    send.add_argument("--chat", required=True, help="me или имя из списка chats")
    group = send.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--text-file")
    send.add_argument("--confirmed", action="store_true")
    send.set_defaults(fn=cmd_send)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
