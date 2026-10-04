# Практика «Личные агенты» — корень репозитория

Три трека: `1_claude/` — шесть самостоятельных кейсов на Claude (`01_digest` … `06_assistant`), `2_hermes/` — те же
кейсы, собранные для Hermes Agent, `3_custom/` — в планах. Общий пак навыков — `skills_pack/`. Карта — в `README.md`.

- Работать с кейсом — открыть его папку как проект: у кейсов трека 1 свой `CLAUDE.md`, свои `.claude/agents` и
  `.claude/skills`; у кейсов трека 2 — `AGENTS.md` и `.hermes/skills`.
- Источник правил кейса — `playbooks/`. Файлы в `.claude/`, `.hermes/`, `AGENTS.md`, `cowork-plugin/`, `dist/`, `pack/`
  собираются скриптами, руками их не править: `python tools/build.py` в папке кейса; пак — `python skills_pack/sync.py`;
  общие скрипты и учебные данные трека 2 — `python 2_hermes/sync.py`.
- Личных данных в репозитории нет. Папки `hub/` и `.secrets/` в git не попадают; содержимое `.secrets/` не читать.
- `1_claude/06_assistant/tools/install.py` без пути обновляет установленного ассистента владельца — запускать только
  по его просьбе.
