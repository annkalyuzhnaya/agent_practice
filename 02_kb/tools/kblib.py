"""Общие функции скриптов кейса «База знаний»: пути, чтение заметок, ссылки, служебные таблицы.

Нужна только стандартная библиотека Python. Скрипты ничего не отправляют в сеть (кроме tg_bridge.py — в Telegram).
"""
import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
KB = HUB / "kb"
CACHE = ROOT / ".cache"

CONFLICTS = KB / "_противоречия.md"
CARE = KB / "_уход.md"
QA = KB / "_вопросы.md"
GLOSSARY = HUB / "memory" / "glossary.md"

# подпапка базы → тип заметки по умолчанию
FOLDER_TYPES = {"контрагенты": "контрагент", "проекты": "проект", "решения": "решение",
                "публикации": "публикация", "справки": "справка", "входящее": "входящее"}
# тип заметки → подпапка, где ей место
TYPE_FOLDERS = {"контрагент": "контрагенты", "проект": "проекты", "решение": "решения", "протокол": "решения",
                "публикация": "публикации", "справка": "справки", "заметка": "справки", "регламент": "справки",
                "вопросы-ответы": "справки"}

LINK = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
DONE_MARK = "Оформлено:"


def utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def need_hub():
    if not HUB.exists():
        sys.exit("Папки hub/ нет — сначала выполните: python tools/setup.py (или напишите в чат «настрой»).")


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def short_id(prefix, *parts):
    """Короткий устойчивый номер записи для страницы: латиница и цифры."""
    return prefix + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]


def frontmatter(text):
    """(шапка как словарь, остальной текст). Понимает `ключ: значение` и списки `[a, b]`."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    meta = {}
    for line in text[3:end].splitlines():
        if ":" not in line or line.startswith((" ", "\t", "#")):
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
            # ссылки [[имя]] в списке распадаются на «[имя]» — вернём имя
            value = [v.strip("[]") for v in value]
        else:
            value = value.strip("\"'")
        meta[key.strip()] = value
    return meta, text[end + 4:].lstrip("\n")


def md_chunks(text):
    """(заголовок, текст) по заголовкам markdown."""
    heading, buf = "", []
    for line in text.splitlines():
        if line.startswith("#"):
            if "".join(buf).strip():
                yield heading, "\n".join(buf)
            heading, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        yield heading, "\n".join(buf)


def docx_text(path):
    """Текст Word-файла как markdown: абзацы, заголовки по стилю. Таблицы — построчно через « | »."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""
    out = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", para, flags=re.S))
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').strip()
        if not text:
            continue
        style = re.search(r'<w:pStyle w:val="([^"]+)"', para)
        name = style.group(1).lower() if style else ""
        if name.startswith(("heading", "заголовок")) or name in ("1", "2", "3", "title"):
            text = "## " + text
        out.append(text)
    return "\n\n".join(out)


def text_of(path):
    """Текст файла базы: .md/.txt как есть, .docx — извлечённый."""
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    return read(path)


def is_service(path):
    """Служебные файлы базы: шаблоны и файлы с именем на «_»."""
    rel = path.relative_to(KB).parts
    return path.name.startswith("_") or rel[0].startswith("_")


def summary_of(body):
    """Короткая суть заметки: текст раздела «Суть» или первый содержательный абзац, до 220 знаков."""
    chunks = list(md_chunks(body))
    pick = next((b for h, b in chunks if h.lower().startswith("суть")), None)
    if pick is None:
        pick = next((b for h, b in chunks if b.strip()), "")
    lines = [ln.strip(" -*>") for ln in pick.splitlines()
             if ln.strip() and not ln.lower().startswith(("связано", "**связано")) and not ln.startswith("|")]
    text = LINK.sub(lambda m: m.group(1), " ".join(lines))
    text = re.sub(r"\s+", " ", text.replace("**", "")).strip()
    return text[:217] + "…" if len(text) > 220 else text


def notes():
    """Все заметки базы (без служебных файлов). Каждая — словарь с полями для проверок и карты."""
    found = []
    if not KB.exists():
        return found
    for path in sorted(KB.rglob("*.md")):
        if is_service(path):
            continue
        text = read(path)
        meta, body = frontmatter(text)
        folder = path.relative_to(KB).parts[0] if len(path.relative_to(KB).parts) > 1 else ""
        title = next((ln.lstrip("# ").strip() for ln in body.splitlines() if ln.startswith("# ")), path.stem)
        inbox = folder == "входящее"
        found.append({
            "path": path, "rel": path.relative_to(ROOT).as_posix(), "stem": path.stem, "folder": folder,
            "type": "входящее" if inbox else (meta.get("type") or FOLDER_TYPES.get(folder) or "заметка"),
            "has_meta": bool(meta), "meta": meta, "date": str(meta.get("date") or ""), "title": title,
            "tags": meta.get("tags") if isinstance(meta.get("tags"), list) else [],
            "sources": meta.get("sources") or meta.get("source") or "",
            "summary": summary_of(body), "inbox": inbox, "processed": DONE_MARK in text,
            "links": sorted({m.strip() for m in LINK.findall(text) if m.strip()}),
        })
    return found


def all_stems():
    """Имена всех .md в хранилище hub/ (без расширения): на них может вести ссылка [[имя]]."""
    stems = set()
    for path in HUB.rglob("*.md"):
        if ".secrets" in path.parts or ".obsidian" in path.parts:
            continue
        stems.add(path.stem)
        stems.add(path.relative_to(HUB).with_suffix("").as_posix())
    return stems


def table_rows(path, min_cells=2):
    """Строки таблицы markdown-файла как списки ячеек (без заголовка и разделителя)."""
    if not path.exists():
        return []
    rows, seen_sep = [], False
    for line in read(path).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            seen_sep = False if not line else seen_sep
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            seen_sep = True
            continue
        if seen_sep and len(cells) >= min_cells and any(cells):
            rows.append(cells)
    return rows


def conflicts():
    """Строки журнала противоречий: дата, факт, версия А, версия Б, какая новее, статус."""
    out = []
    for cells in table_rows(CONFLICTS, 6):
        date, fact, a, b, newer, status = (cells + [""] * 6)[:6]
        given = cells[6].strip("` ") if len(cells) > 6 else ""  # колонка «ID» (её добавляет сверка без скриптов и кейс 6)
        out.append({"id": given if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{1,30}", given) else short_id("c", date, fact), "date": date, "fact": fact, "a": a, "b": b, "newer": newer,
                    "status": status, "open": "открыто" in status.lower()})
    return out


def glossary():
    """Словарь памяти: {сокращение в нижнем регистре: расшифровка} из таблиц hub/memory/*glossary*.md."""
    terms = {}
    folder = HUB / "memory"
    for path in sorted(folder.glob("*glossary*.md")) if folder.exists() else []:
        for cells in table_rows(path, 2):
            term, meaning = cells[0].strip("*` "), cells[1].strip()
            if term and meaning:
                terms[term.lower()] = meaning
    return terms
