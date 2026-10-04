# Сторонние навыки в паке: происхождение и лицензии

Навыки в `skills/` скопированы из открытых плагинов и распространяются на условиях их лицензий (тексты — в `licenses/`).

| Навык | Откуда | Лицензия | Изменения |
|---|---|---|---|
| `memory-management`, `task-management`, `update` | плагин Productivity 1.3.1, Anthropic — github.com/anthropics/knowledge-work-plugins (`productivity`) | Apache-2.0 | без изменений |
| `start` | тот же плагин | Apache-2.0 | `dashboard.html` перенесён внутрь папки навыка; в `SKILL.md` поправлена одна строка с путём к нему |
| `build-dashboard`, `data-visualization`, `validate-data` | плагин Data, Anthropic — github.com/anthropics/knowledge-work-plugins (`data`) | Apache-2.0 | без изменений |
| `internal-comms`, `skill-creator` | github.com/anthropics/skills | Apache-2.0 | без изменений |
| `tavily-cli`, `tavily-search`, `tavily-extract`, `tavily-research` | плагин Tavily 1.0.0 — github.com/tavily-ai/skills | MIT, © 2026 Alpha AI Technologies Inc dba Tavily | без изменений |

Не скопированы (лицензия не разрешает распространение либо файла лицензии нет) — их ставят из каталога, см. `README.md`:
`docx`, `xlsx`, `pdf`, `pptx` (Anthropic, все права защищены), `schedule`, `doc-coauthoring`, навыки Desktop Commander
(`obsidian-vault`, `knowledge-base`), официальный плагин `telegram`.
