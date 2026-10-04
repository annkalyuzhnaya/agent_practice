"""Страница «Дайджест»: один самодостаточный файл hub/page/digest.html, собранный из файлов рабочей папки.

  python tools/page.py            собрать страницу из всех выпусков, отметок, очереди и предложений
  python tools/page.py --out файл  собрать в другой файл (путь от папки кейса)

Страница ничего не записывает и никуда не обращается: кнопки отметок копируют готовую фразу для чата.
Открывается двойным щелчком в браузере или в панели предпросмотра Hermes Desktop. Только стандартная библиотека.
"""
import argparse
import json
import re

import digestlib as dl
from issue import top_flags

PAGE = dl.HUB / "page" / "digest.html"
TOPICS = dl.DIGEST / "topics.md"
MODELS = dl.HUB / "models.json"

CSS = """
:root{--bg:#f6f5f1;--card:#fff;--ink:#1d1d1b;--mute:#6b6a65;--line:#e2e0d8;--acc:#1f5f8b;--top:#fdf3d7;--ok:#2e7d4f}
@media (prefers-color-scheme:dark){:root{--bg:#191a1c;--card:#232528;--ink:#ecebe6;--mute:#a09f99;--line:#383a3e;--acc:#7db7e0;--top:#3a3320;--ok:#7cc79a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:20px 16px 60px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 10px}
.sub,.meta{color:var(--mute);font-size:14px}.bar{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
select,button{font:inherit;font-size:14px;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
button{cursor:pointer}button:hover{border-color:var(--acc)}
.item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.item.top{background:var(--top)}.item h3{font-size:16px;margin:0 0 4px}.item p{margin:6px 0}
.score{display:inline-block;min-width:26px;text-align:center;border-radius:6px;background:var(--acc);color:var(--bg);font-weight:600;margin-right:8px}
.mark{color:var(--ok);font-weight:600}.acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}a{color:var(--acc);word-break:break-all}
ul{padding-left:20px}li{margin:4px 0}.toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:var(--ink);color:var(--bg);
padding:8px 14px;border-radius:8px;font-size:14px;opacity:0;transition:opacity .2s;max-width:90vw}.toast.on{opacity:1}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
"""

JS = """
const D = JSON.parse(document.getElementById('data').textContent);
const $ = (id) => document.getElementById(id);
function el(tag, cls, text){const e=document.createElement(tag); if(cls) e.className=cls; if(text!==undefined) e.textContent=text; return e;}
function opt(sel, value, label){const o=el('option','',label); o.value=value; sel.appendChild(o);}
function say(text){const t=$('toast'); t.textContent=text; t.classList.add('on'); setTimeout(()=>t.classList.remove('on'),2600);}
function copy(phrase){
  const done=()=>say('Скопировано: «'+phrase+'» — вставьте в чат Hermes или отправьте боту');
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(phrase).then(done,()=>say('Напишите в чат: '+phrase));}
  else say('Напишите в чат: '+phrase);
}
function list(title, rows){
  if(!rows||!rows.length) return null;
  const box=el('div'); box.appendChild(el('h2','',title)); const ul=el('ul'); rows.forEach(r=>ul.appendChild(el('li','',r))); box.appendChild(ul); return box;
}
function table(title, head, rows){
  if(!rows.length) return null;
  const box=el('div'); box.appendChild(el('h2','',title)); const t=el('table'); const tr=el('tr'); head.forEach(h=>tr.appendChild(el('th','',h))); t.appendChild(tr);
  rows.forEach(r=>{const x=el('tr'); r.forEach(c=>x.appendChild(el('td','',c))); t.appendChild(x);}); box.appendChild(t); return box;
}
function render(){
  const issue=D.issues.find(i=>i.date===$('issue').value); const out=$('out'); out.textContent='';
  if(!issue){out.appendChild(el('p','sub','Выпусков пока нет. Напишите в чат: «дайджест».')); return;}
  const topic=$('topic').value, score=+$('score').value, mark=$('mark').value;
  $('sub').textContent='Выпуск '+issue.date+' · позиций: '+issue.items.length+' · статус: '+(issue.status||'—');
  const shown=issue.items.filter(i=>(!topic||i.topic===topic)&&i.score>=score&&(!mark||(mark==='нет'?!i.mark:i.mark===mark)));
  shown.forEach(i=>{
    const card=el('div','item'+(i.top?' top':'')); const h=el('h3'); h.appendChild(el('span','score',String(i.score)));
    h.appendChild(document.createTextNode(i.n+'. '+i.title+(i.top?' · ТОП-3':''))); card.appendChild(h);
    card.appendChild(el('p','meta',[i.source,i.pub,i.topic].filter(Boolean).join(' · ')));
    if(i.summary) card.appendChild(el('p','',i.summary));
    [['Почему важно: ',i.why],['Что сделать: ',i.action],['Оговорка: ',i.note]].forEach(([k,v])=>{if(v){const p=el('p'); p.appendChild(el('b','',k)); p.appendChild(document.createTextNode(v)); card.appendChild(p);}});
    if(/^https?:\\/\\//i.test(i.url)){const p=el('p'); const a=el('a','',i.url); a.href=i.url; a.rel='noopener'; a.target='_blank'; p.appendChild(a); card.appendChild(p);}
    if(i.mark) card.appendChild(el('p','mark','Отмечено: '+i.mark));
    else if(issue.date===D.issues[0].date){const acts=el('div','acts'); ['в базу','в задачи','не интересно'].forEach(m=>{const b=el('button','',m); b.onclick=()=>copy(m+' '+i.n); acts.appendChild(b);}); card.appendChild(acts);}
    out.appendChild(card);
  });
  if(!shown.length) out.appendChild(el('p','sub','Под выбранные фильтры ничего не попало.'));
  [list('Что остаётся человеку',issue.human),list('Пропущено',issue.skipped),list('Не удалось открыть',issue.failed)].forEach(b=>b&&out.appendChild(b));
}
function init(){
  $('built').textContent='Собрано '+D.built+' из файлов hub/. Отметки — фразой в чат; после них попросите «обнови страницу».';
  D.issues.forEach(i=>opt($('issue'),i.date,'Выпуск '+i.date));
  opt($('topic'),'','Все темы'); [...new Set(D.issues.flatMap(i=>i.items.map(x=>x.topic)).filter(Boolean))].sort().forEach(t=>opt($('topic'),t,t));
  [['1','Оценка: любая'],['4','Оценка 4–5'],['5','Только 5']].forEach(([v,l])=>opt($('score'),v,l));
  [['','Отметка: любая'],['нет','Без отметки'],['в базу','В базу'],['в задачи','В задачи'],['не интересно','Не интересно']].forEach(([v,l])=>opt($('mark'),v,l));
  ['issue','topic','score','mark'].forEach(id=>$(id).onchange=render); render();
  const extra=$('extra');
  [table('Очередь «посмотри это»',['Дата','Что','Ссылка','Статус'],D.queue),
   table('Предложения по темам и источникам',['Дата','Вид','Название','Предложение','Решение'],D.topics),
   table('Кто что исполнял',['Роль','Модель'],D.models)].forEach(b=>b&&extra.appendChild(b));
}
init();
"""


def table_rows(path):
    """Строки markdown-таблицы файла (без заголовка и разделителя) списками ячеек."""
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", s):
            rows.append([dl.plain(c.strip()) for c in s.strip("|").split("|")])
    return rows[1:]


def marks():
    found = {}
    for row in table_rows(dl.MARKS):
        if len(row) >= 6 and row[1]:
            found[row[1]] = row[5].lower()
    return found


def models():
    names = {"editor": "редактор", "scout": "разведчик", "checker": "проверяющий", "cron": "расписание"}
    try:
        data = json.loads(MODELS.read_text(encoding="utf-8")).get("roles", {})
    except (OSError, ValueError):
        return []
    return [[names[k], f"{(data.get(k) or {}).get('provider') or '—'} / {data[k]['model']}" if (data.get(k) or {}).get("model") else "основная модель"]
            for k in names]


def collect():
    marked = marks()
    issues = []
    files = sorted((p for p in dl.DIGEST.glob("*.md") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)), reverse=True)
    for path in files:
        issue = dl.parse_issue(path)
        top_flags(issue)
        issues.append({
            "date": issue["date"], "status": issue["meta"].get("status", ""),
            "human": [dl.plain(x) for x in issue["human"]], "skipped": [dl.plain(x) for x in issue["skipped"]],
            "failed": [dl.plain(x) for x in issue["failed"]],
            "items": [{"n": n, "id": i["id"], "title": i["title"], "url": i["url"], "score": i["score"], "source": i["source"],
                       "pub": i["pub"], "topic": i["topic"], "summary": dl.plain(i["tldr"]), "why": dl.plain(i["why"]),
                       "action": dl.plain(i["action"]), "note": dl.plain(i["note"]), "top": i["top"], "mark": marked.get(i["id"], "")}
                      for n, i in enumerate(issue["items"], 1)]})
    queue = [[r[0], r[2], r[3], r[5]] for r in table_rows(dl.QUEUE) if len(r) >= 6]
    topics = [[r[0], r[1], r[2], r[4], r[6]] for r in table_rows(TOPICS) if len(r) >= 7]
    return {"built": dl.today(), "issues": issues, "queue": queue, "topics": topics, "models": models()}


def main():
    dl.utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    args = ap.parse_args()
    dl.need_hub()
    data = collect()
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = ("<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>Дайджест</title><style>{CSS}</style></head><body><div class=\"wrap\"><h1>Дайджест</h1><p class=\"sub\" id=\"sub\"></p>"
            "<div class=\"bar\"><select id=\"issue\" aria-label=\"Выпуск\"></select><select id=\"topic\" aria-label=\"Тема\"></select>"
            "<select id=\"score\" aria-label=\"Оценка\"></select><select id=\"mark\" aria-label=\"Отметка\"></select></div>"
            "<div id=\"out\"></div><div id=\"extra\"></div><p class=\"sub\" id=\"built\"></p></div><div class=\"toast\" id=\"toast\"></div>"
            f"<script type=\"application/json\" id=\"data\">{payload}</script><script>{JS}</script></body></html>\n")
    out = dl.ROOT / args.out if args.out else PAGE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8", newline="\n")
    count = sum(len(i["items"]) for i in data["issues"])
    print(f"Страница «Дайджест»: {dl.rel(out)} — выпусков {len(data['issues'])}, позиций {count}. Откройте файл в браузере "
          "или в панели предпросмотра Hermes Desktop.")


if __name__ == "__main__":
    main()
