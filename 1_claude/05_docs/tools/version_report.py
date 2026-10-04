"""Локальный HTML-отчёт сравнения двух версий документа из хранилища. Открывается с диска двойным щелчком.

  python tools/version_report.py reglament              # две последние версии
  python tools/version_report.py reglament 1 3          # конкретные версии
  python tools/version_report.py reglament --out отчёт.html

По умолчанию файл кладётся в hub/docs/out/ГГГГ-ММ-ДД_сравнение_<id>_v<a>-v<b>.html.
Отчёт содержит текст изменённых разделов — это локальный файл; наружу его отправляет только человек.
"""
import argparse
import difflib
import html
from datetime import date
from pathlib import Path

import doclib
import versions

CSS = """
:root{--bg:#f5f2ec;--surface:#fffdf8;--ink:#1e2226;--muted:#6a6f76;--line:#e0dacd;--accent:#2d5b4e;--soft:#e7efe9;
--warn:#a85a14;--warn-soft:#f6ead9;--danger:#a3312c;--danger-soft:#f6e1de;--ok:#2f6b3c;--ok-soft:#e2f0e4}
@media (prefers-color-scheme: dark){:root{--bg:#15181a;--surface:#1e2225;--ink:#e9e6e0;--muted:#9aa1a8;--line:#31363b;
--accent:#84c9b2;--soft:#22302c;--warn:#e0a25c;--warn-soft:#33291c;--danger:#e58a84;--danger-soft:#3a2220;--ok:#8fce9d;--ok-soft:#1f3024}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:20px 16px 64px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:26px 0 8px}
.sub{color:var(--muted);font-size:13px}
.kpis{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:120px}
.kpi b{display:block;font-size:22px}
table{border-collapse:collapse;width:100%;background:var(--surface);border:1px solid var(--line);border-radius:10px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top;overflow-wrap:anywhere}
th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
code{font-size:12px;color:var(--muted)}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;background:var(--soft)}
.tag.ch{background:var(--warn-soft);color:var(--warn)}.tag.add{background:var(--ok-soft);color:var(--ok)}
.tag.del{background:var(--danger-soft);color:var(--danger)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:10px}
.line{padding:3px 8px;border-radius:6px;margin:3px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.minus{background:var(--danger-soft);color:var(--danger);text-decoration:line-through}
.plus{background:var(--ok-soft);color:var(--ok)}
.same{color:var(--muted)}
"""


def esc(v):
    return html.escape(str(v))


def build(doc_id, a=None, b=None):
    man = versions.load_manifest(doc_id)
    a, b = versions.pair(man, a, b)
    pa, pb = versions.load_version(doc_id, a), versions.load_version(doc_id, b)
    diff = doclib.compare(pa, pb, "text_hash")
    ka, kb = doclib.keyed(pa), doclib.keyed(pb)
    va = next(x for x in man["versions"] if x["v"] == a)
    vb = next(x for x in man["versions"] if x["v"] == b)
    cur = (man.get("current") or {}).get("v")
    out = [f"<!doctype html><html lang='ru'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
           f"<title>Сравнение версий: {esc(doc_id)} v{a} → v{b}</title><style>{CSS}</style><div class='wrap'>",
           f"<h1>{esc(doc_id)}: что изменилось между v{a} и v{b}</h1>",
           f"<div class='sub'>Тип: {esc(man['type'])} · v{a} от {esc(va['ts'])} ({esc(va['source'])}) → v{b} от {esc(vb['ts'])} ({esc(vb['source'])})"
           f" · действующая: {('v' + str(cur)) if cur else 'не назначена — решает человек'} · отчёт от {date.today().isoformat()}</div>",
           "<div class='kpis'>"]
    for label, n in (("изменено", len(diff["changed"])), ("добавлено", len(diff["added"])),
                     ("удалено", len(diff["removed"])), ("без изменений", len(diff["same"]))):
        out.append(f"<div class='kpi'><b>{n}</b>{label}</div>")
    out.append("</div><h2>Разделы</h2><table><tr><th>Раздел</th><th>Статус</th><th>Хэш v%d</th><th>Хэш v%d</th></tr>" % (a, b))
    order = list(kb) + [k for k in ka if k not in kb]
    state = {**{k: ("изменён", "ch") for k in diff["changed"]}, **{k: ("добавлен", "add") for k in diff["added"]},
             **{k: ("удалён", "del") for k in diff["removed"]}}
    for k in order:
        label, cls = state.get(k, ("без изменений", ""))
        out.append(f"<tr><td>{esc(k)}</td><td><span class='tag {cls}'>{label}</span></td>"
                   f"<td><code>{esc(ka[k]['text_hash']) if k in ka else '—'}</code></td>"
                   f"<td><code>{esc(kb[k]['text_hash']) if k in kb else '—'}</code></td></tr>")
    out.append("</table>")
    if diff["changed"] or diff["added"] or diff["removed"]:
        out.append("<h2>Изменения по строкам</h2>")
    for k in diff["changed"]:
        out.append(f"<div class='card'><b>{esc(k)}</b> <span class='tag ch'>изменён</span>")
        for line in difflib.ndiff(doclib.section_lines(ka[k]), doclib.section_lines(kb[k])):
            if line.startswith("- "):
                out.append(f"<div class='line minus'>{esc(line[2:])}</div>")
            elif line.startswith("+ "):
                out.append(f"<div class='line plus'>{esc(line[2:])}</div>")
            elif line.startswith("  "):
                out.append(f"<div class='line same'>{esc(line[2:])}</div>")
        out.append("</div>")
    for k in diff["added"]:
        out.append(f"<div class='card'><b>{esc(k)}</b> <span class='tag add'>добавлен</span>")
        out += [f"<div class='line plus'>{esc(l)}</div>" for l in doclib.section_lines(kb[k])]
        out.append("</div>")
    for k in diff["removed"]:
        out.append(f"<div class='card'><b>{esc(k)}</b> <span class='tag del'>удалён</span>")
        out += [f"<div class='line minus'>{esc(l)}</div>" for l in doclib.section_lines(ka[k])]
        out.append("</div>")
    out.append("<p class='sub'>Сравнение по содержанию разделов (text_hash). Какая версия действующая — решает человек.</p></div></html>")
    return "\n".join(out), a, b, diff


def main():
    doclib.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("a", nargs="?", type=int)
    ap.add_argument("b", nargs="?", type=int)
    ap.add_argument("--out")
    args = ap.parse_args()
    text, a, b, diff = build(args.id, args.a, args.b)
    out = Path(args.out) if args.out else doclib.HUB / "docs" / "out" / f"{date.today().isoformat()}_сравнение_{args.id}_v{a}-v{b}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Отчёт сравнения v{a} → v{b}: изменено {len(diff['changed'])}, добавлено {len(diff['added'])}, "
          f"удалено {len(diff['removed'])}, без изменений {len(diff['same'])}")
    print(f"Файл: {out} — откройте двойным щелчком")


if __name__ == "__main__":
    main()
