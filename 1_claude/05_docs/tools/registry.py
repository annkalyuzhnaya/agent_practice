"""Реестр заявок и документов: сводка шины для человека и для страницы «Документы».

  python tools/registry.py export     собрать hub/docs/registry.md и .cache/page.json
  python tools/registry.py show       напечатать реестр в терминал

.cache/page.json — готовые записи коллекций страницы (requests, docs, checks, meta): имена, разделы, хэши,
короткая сводка изменений. Полного текста документов там нет. Нужна только стандартная библиотека Python.
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import handoff

ROOT = Path(__file__).resolve().parent.parent
HUB = ROOT / "hub"
STORE = HUB / "docs" / "store"
CHECKS = HUB / "docs" / "checks"
PAGE = ROOT / ".cache" / "page.json"
REGISTRY = HUB / "docs" / "registry.md"
LINE_MAX, LINES_PER_SECTION, PAIRS = 140, 3, 5


def safe_id(prefix, name):
    """Идентификатор записи страницы: латиница/цифры; иначе — хэш имени."""
    return name if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name) else prefix + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def keyed(parsed):
    out, seen = {}, {}
    for s in parsed["sections"]:
        n = seen[s["path"]] = seen.get(s["path"], 0) + 1
        out[s["path"] if n == 1 else f"{s['path']} #{n}"] = s
    return out


def lines_of(s):
    lines = list(s.get("paragraphs", []))
    for t in s.get("tables", []):
        lines += [" | ".join(str(c) for c in row) for row in t]
    lines += [" | ".join(str(c) for c in row) for row in s.get("rows", [])]
    return lines


def cut(text):
    text = " ".join(str(text).split())
    return text if len(text) <= LINE_MAX else text[:LINE_MAX - 1] + "…"


def change_summary(folder, a, b):
    pa = json.loads((folder / f"v{a}.json").read_text(encoding="utf-8"))
    pb = json.loads((folder / f"v{b}.json").read_text(encoding="utf-8"))
    ka, kb = keyed(pa), keyed(pb)
    changed = []
    for k in ka:
        if k in kb and ka[k]["text_hash"] != kb[k]["text_hash"]:
            delta = [l for l in difflib.unified_diff(lines_of(ka[k]), lines_of(kb[k]), lineterm="", n=0)][2:]
            delta = [l for l in delta if not l.startswith("@@")]
            changed.append({"section": k, "lines": [l[0] + " " + cut(l[1:]) for l in delta[:LINES_PER_SECTION]],
                            "more": max(0, len(delta) - LINES_PER_SECTION)})
    return {"from": a, "to": b, "changed": changed,
            "added": [k for k in kb if k not in ka], "removed": [k for k in ka if k not in kb],
            "same": sum(1 for k in ka if k in kb and ka[k]["text_hash"] == kb[k]["text_hash"])}


def collect():
    requests, docs, checks = [], [], []
    for path in sorted(handoff.HANDOFF.glob("*.md")) if handoff.HANDOFF.exists() else []:
        meta, body = handoff.read(path)
        what = re.search(r"\*\*Что сделать\.\*\*\s*(.+)", body)
        requests.append({"id": safe_id("r", path.stem), "file": path.name, "title": handoff.title_of(body, path.stem),
                         "what": cut(what.group(1)) if what else "", "stage": meta.get("stage", "принято"),
                         "status": meta.get("status", "new"), "needs": meta.get("needs", ""), "source": meta.get("from", ""),
                         "date": meta.get("date", ""), "due": meta.get("due", ""), "check": meta.get("check", ""),
                         "doc": meta.get("doc", ""), "version": meta.get("version", ""),
                         "asks": [cut(q) for q in re.findall(r"^\[РЕШИТЬ\]\s*(.+)$", body, re.M)]})
    for folder in sorted(p for p in STORE.iterdir() if p.is_dir()) if STORE.exists() else []:
        mpath = folder / "manifest.json"
        if not mpath.exists():
            continue
        man = json.loads(mpath.read_text(encoding="utf-8"))
        vs = [v["v"] for v in man["versions"]]
        pairs = list(zip(vs, vs[1:]))[-PAIRS:]
        cur = man.get("current") or {}
        docs.append({"id": safe_id("d", man["id"]), "name": man["id"], "type": man.get("type", ""),
                     "current": cur.get("v", 0), "currentBy": cur.get("by", ""), "currentDate": cur.get("date", ""),
                     "versions": [{"v": v["v"], "ts": v["ts"], "source": v["source"], "note": v.get("note", ""),
                                   "sha": v["sha"], "sections": v.get("sections", 0)} for v in man["versions"]],
                     "changes": [change_summary(folder, a, b) for a, b in pairs]})
    for path in sorted(CHECKS.glob("*.json")) if CHECKS.exists() else []:
        rep = json.loads(path.read_text(encoding="utf-8"))
        checks.append({"id": safe_id("c", path.stem), "file": path.name, "ts": rep["ts"], "before": rep["before"],
                       "after": rep["after"], "mode": rep.get("mode", ""), "allow": rep["allow"], "same": rep["same"],
                       "touched": [{"kind": t["kind"], "section": t["section"], "allowed": t["allowed"]} for t in rep["touched"]],
                       "unused_allow": rep.get("unused_allow", []), "ok": rep["ok"]})
    meta = {"generatedAt": datetime.now().isoformat(timespec="seconds"),
            "counts": {"requests": len(requests), "open": sum(1 for r in requests if r["status"] != "done"),
                       "docs": len(docs), "checks": len(checks), "failed": sum(1 for c in checks if not c["ok"])}}
    return {"requests": requests, "docs": docs, "checks": checks, "meta": meta}


def markdown(data):
    out = [f"# Реестр документов и заявок", "", f"Собран: {data['meta']['generatedAt']} (tools/registry.py). Руками не править.", "",
           "## Заявки", "", "| Заявка | Этап | Проверка | Документ, версия | Откуда | Дата | Ждёт решения |", "|---|---|---|---|---|---|---|"]
    for r in data["requests"]:
        check = {"ok": "пройдена", "fail": "НЕ ПРОЙДЕНА"}.get(r["check"], "—")
        ver = f"{r['doc']} v{r['version']}" if r["version"] else (r["doc"] or "—")
        out.append(f"| {r['title']} | {r['stage']}{' (закрыта)' if r['status'] == 'done' else ''} | {check} | {ver} | "
                   f"{r['source']} | {r['date']} | {len(r['asks']) or '—'} |")
    out += ["", "## Документы и версии", "", "| Документ | Тип | Версий | Действующая | Последняя версия | Примечание |", "|---|---|---|---|---|---|"]
    for d in data["docs"]:
        last = d["versions"][-1] if d["versions"] else {}
        cur = f"v{d['current']} ({d['currentBy']})" if d["current"] else "не назначена — решает человек"
        out.append(f"| {d['name']} | {d['type']} | {len(d['versions'])} | {cur} | v{last.get('v', '')} от {last.get('ts', '')[:10]} | {last.get('note', '')} |")
    out += ["", "## Проверки целостности", "", "| Когда | До → после | Разрешено менять | Итог | Задето вне разрешённого |", "|---|---|---|---|---|"]
    for c in data["checks"]:
        bad = [t["section"] for t in c["touched"] if not t["allowed"]]
        out.append(f"| {c['ts'][:16].replace('T', ' ')} | {c['before']} → {c['after']} | {', '.join(c['allow']) or '—'} | "
                   f"{'соблюдена' if c['ok'] else 'НАРУШЕНА'} | {'; '.join(bad) or '—'} |")
    return "\n".join(out) + "\n"


def main():
    handoff.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["export", "show"])
    args = ap.parse_args()
    data = collect()
    if args.cmd == "show":
        print(markdown(data))
        return
    if not HUB.exists():
        sys.exit("Нет папки hub/ — сначала: python tools/setup.py")
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(markdown(data), encoding="utf-8", newline="\n")
    PAGE.parent.mkdir(exist_ok=True)
    PAGE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    c = data["meta"]["counts"]
    print(f"Реестр: заявок {c['requests']} (открытых {c['open']}), документов {c['docs']}, проверок {c['checks']} (не пройдено {c['failed']})")
    print("Файлы: hub/docs/registry.md (для человека), .cache/page.json (записи для страницы «Документы»)")


if __name__ == "__main__":
    main()
