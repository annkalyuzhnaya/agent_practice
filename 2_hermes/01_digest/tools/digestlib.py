"""Общие функции скриптов кейса «Обозреватель»: пути, профиль, память «уже видел», разбор файла выпуска.
Только стандартная библиотека Python.
"""
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
DIGEST = HUB / "digest"
SEEN = DIGEST / "seen.md"
RAW = DIGEST / "raw"
QUEUE = DIGEST / "queue.md"
MARKS = DIGEST / "marks.md"
CARDS = DIGEST / "cards"
PROFILE = HUB / "profile.md"
CACHE = ROOT / ".cache"

URL_RE = re.compile(r"https?://[^\s<>\"'|)\]]+")
TRACKING = ("utm_", "fbclid", "gclid", "yclid", "ysclid", "from", "ref", "source")
HEAD_RE = re.compile(
    r"^###\s*\[оценка\s*(?P<score>[1-5])(?P<flag>[^\]]*)\]\s*(?P<title>.+?)\s+—\s+(?P<source>[^—]+?),\s*"
    r"(?P<pub>\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}|дата не указана)\s*,\s*(?P<url>https?://\S+)\s*$")


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def need_hub():
    if not HUB.exists():
        sys.exit("Рабочей папки hub/ ещё нет. Выполните: python tools/setup.py (или напишите в чате «настрой»).")


def rel(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def norm_url(url):
    """Привести ссылку к виду для сравнения: без http/https, www, меток рекламы, якоря и хвостового «/»."""
    url = url.strip().rstrip(".,;:!?»”")
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(TRACKING[:1]) and k.lower() not in TRACKING[1:]]
    path = parts.path.rstrip("/")
    return urlunsplit(("", host, path, urlencode(sorted(query)), "")).lstrip("/")


def norm_title(title):
    """Заголовок для сравнения: только буквы и цифры в нижнем регистре."""
    return " ".join(re.findall(r"[0-9a-zа-яё]+", title.lower()))


def iso(text):
    """«29.09.2026» или «2026-09-29» → дата; иначе None."""
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    return None


def read_seen():
    """Память «уже видел»: список (дата, ссылка, заголовок) и словарь нормализованная ссылка → запись."""
    rows = []
    if SEEN.exists():
        for line in SEEN.read_text(encoding="utf-8").splitlines():
            if not line.startswith("- "):
                continue
            cells = [c.strip() for c in line[2:].split("|")]
            if len(cells) >= 2 and cells[1].startswith("http"):
                rows.append((cells[0], cells[1], cells[2] if len(cells) > 2 else ""))
    return rows, {norm_url(u): (d, u, t) for d, u, t in rows}


def append_line(path, line, header=""):
    """Дописать строку в общий файл, ничего в нём не меняя."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else header
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + line + "\n", encoding="utf-8", newline="\n")


def read_profile(path=None):
    """Темы, «не интересно», источники и период из hub/profile.md."""
    path = Path(path) if path else PROFILE
    out = {"topics": [], "skip": [], "sources": [], "days": 7, "filled": False}
    if not path.exists():
        return out
    text = path.read_text(encoding="utf-8")
    out["filled"] = "профиль не заполнен" not in text
    section = ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            section = s[3:].lower()
            continue
        if s.startswith("<!--") or s.startswith(">"):
            continue
        m = re.search(r"Период дайджеста по умолчанию:\s*(\d+)", s)
        if m:
            out["days"] = int(m.group(1))
        if s.lower().startswith("**не интересно"):
            tail = s.split(":", 1)[1].replace("**", "").strip() if ":" in s else ""
            out["skip"] += [x.strip() for x in re.split(r"[;,]", tail) if x.strip()]
            section = "не интересно"
            continue
        item = re.match(r"^(?:\d+[.)]|[-*])\s+(.*)$", s)
        if not item or not item.group(1).strip():
            continue
        value = item.group(1).strip()
        if section.startswith("темы"):
            out["topics"].append(value)
        elif section == "не интересно":
            out["skip"].append(value)
        elif section.startswith("источники"):
            url = URL_RE.search(value)
            name = value.split("—")[0].split(" - ")[0].strip() if ("—" in value or " - " in value) else value
            out["sources"].append({"name": URL_RE.sub("", name).strip(" :—-") or value, "url": url.group(0) if url else "",
                                   "line": value})
    return out


def latest_issue(day=None):
    """Путь к файлу выпуска: по дате или самый свежий hub/digest/ГГГГ-ММ-ДД.md."""
    if day:
        path = DIGEST / f"{day}.md"
        if not path.exists():
            sys.exit(f"Нет выпуска {rel(path)}")
        return path
    files = sorted(p for p in DIGEST.glob("*.md") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))
    if not files:
        sys.exit("В hub/digest/ пока нет ни одного выпуска. Попросите в чате: «дайджест».")
    return files[-1]


def parse_issue(path):
    """Разобрать файл выпуска в словарь: шапка, ТОП-3, позиции, «пропущено», «не удалось открыть»."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    issue = {"path": path, "date": path.stem[:10], "meta": {}, "title": "", "top3": [], "items": [], "skipped": [],
             "failed": [], "human": [], "sections": [], "bad_heads": []}
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            if ":" in lines[i]:
                k, v = lines[i].split(":", 1)
                issue["meta"][k.strip()] = v.strip()
            i += 1
        i += 1
    section, item = "", None
    for line in lines[i:]:
        s = line.rstrip()
        if s.startswith("# ") and not issue["title"]:
            issue["title"] = s[2:].strip()
        elif s.startswith("## "):
            section, item = s[3:].strip(), None
            issue["sections"].append(section)
        elif s.startswith("### "):
            m = HEAD_RE.match(s)
            if not m:
                issue["bad_heads"].append(s)
                item = None
                continue
            item = {"score": int(m.group("score")), "title": m.group("title").strip(), "source": m.group("source").strip(),
                    "pub": m.group("pub"), "url": m.group("url").rstrip(".,;"), "fields": {},
                    "out_of_period": section.lower().startswith("вне периода") or "вне периода" in m.group("flag").lower()}
            issue["items"].append(item)
        elif item is not None and re.match(r"^\s*[-*]\s+[^:]{2,40}:", s):
            key, value = re.sub(r"^\s*[-*]\s+", "", s).split(":", 1)
            item["fields"][key.strip().lower()] = value.strip()
        elif re.match(r"^\s*(\d+[.)]|[-*])\s+", s):
            text = re.sub(r"^\s*(\d+[.)]|[-*])\s+", "", s).strip()
            low = section.lower()
            if low.startswith("топ-3"):
                issue["top3"].append(text)
            elif low.startswith("пропущено"):
                issue["skipped"].append(text)
            elif low.startswith("не удалось открыть"):
                issue["failed"].append(text)
            elif low.startswith("что остаётся человеку"):
                issue["human"].append(text)
        elif s.strip() and section.lower().startswith("что остаётся человеку"):
            issue["human"].append(s.strip())
    for n, it in enumerate(issue["items"], 1):
        f = it["fields"]
        it["id"] = f"g-{issue['date'].replace('-', '')}-{n}"
        it["topic"] = f.get("тема", "")
        it["tldr"] = f.get("tl;dr", "")
        it["why"] = f.get("почему важно для меня", f.get("почему важно", ""))
        it["action"] = f.get("что сделать", "")
        it["note"] = f.get("оговорка", "")
    return issue


def plain(text):
    """Убрать разметку markdown из строки (для Telegram и карточек)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return re.sub(r"\[\[(.+?)\]\]", r"\1", text)


def today():
    return date.today().isoformat()
