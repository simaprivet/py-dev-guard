# py-dev-guard

Небольшой личный плагин Claude Code: проверка синтаксиса Python,
ревью диффа сабагентом и защита файлов из `.gitignore` от случайной
записи. Собран из `.claude/` одного проекта (learning-tracker) и
очищен от всего, что специфично именно для него.

## Версия

`0.1.0` — см. `.claude-plugin/plugin.json`.

## Что внутри

- **`skills/check/SKILL.md`** — команда `/check`. Три шага подряд:
  1. синтаксис изменённых `.py`-файлов (`git diff HEAD` +
     `python3 -m py_compile`);
  2. вызов сабагента `reviewer` на текущий дифф;
  3. `git status -sb`.
  `disable-model-invocation: true` — вызывается только вручную, модель
  сама её не предлагает.
- **`agents/reviewer.md`** — сабагент-ревьюер. Только `Read, Grep,
  Glob` (без Bash, без Edit/Write) — ищет баги и краевые случаи в
  переданном ему тексте диффа, ничего не правит и не может изменить
  файлы физически.
- **`hooks/check_python_syntax.py`** (`PostToolUse`, matcher
  `Edit|Write|NotebookEdit`) — после каждой правки `.py`-файла
  проверяет его синтаксис (`ast.parse`); при ошибке возвращает
  `{"decision": "block", "reason": ...}`, чтобы Claude увидел
  причину в контексте.
- **`hooks/protect_gitignored.py`** (`PreToolUse`, тот же matcher) —
  перед записью в файл спрашивает `git check-ignore`; если путь
  попадает под `.gitignore` репозитория — блокирует запись (`exit 2`,
  причина в stderr), сама запись не происходит вообще.
- **`hooks/run_tests_before_commit.py`** (`PreToolUse`, matcher `Bash`)
  — перед выполнением команды, похожей на `git commit`, запускает
  `pytest -q` в корне проекта (из активного venv, если `$VIRTUAL_ENV`
  задан, иначе из `PATH`), с таймаутом 120 с. Если тесты падают —
  блокирует коммит (`exit 2`, вывод pytest в stderr). Если pytest не
  установлен или в проекте нет тестов (код возврата pytest `5`) —
  пропускает коммит молча, чтобы не мешать проектам без тестов.

## Чем плагин отличается от `.claude/` внутри проекта

|  | `.claude/` в проекте | Этот плагин |
|---|---|---|
| Где живёт | `<project>/.claude/` | Отдельный репозиторий, ставится через `/plugin install` в любой проект |
| Когда активен | Только когда Claude Code запущен в этом конкретном проекте | В каждом проекте, где плагин установлен через `/plugin` |
| Пути в хуках | Относительно проекта (`.claude/hooks/x.py`) | Через `${CLAUDE_PLUGIN_ROOT}` — не зависят от того, где физически лежит плагин |
| Манифест | Нет, просто набор файлов | `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` |
| Версионирование | Нет | `claude plugin tag` делает git-тег `py-dev-guard--vX.Y.Z` |

## Установка

Плагин — полноценный marketplace-плагин Claude Code: репозиторий
одновременно является и плагином (`.claude-plugin/plugin.json`), и
marketplace для него самого (`.claude-plugin/marketplace.json`, имя
marketplace — `simaprivet-tools`).

### Из локального пути

```
/plugin marketplace add /home/sima/.claude/skills/py-dev-guard
/plugin install py-dev-guard@simaprivet-tools
```

(или относительный путь до клона репозитория на диске другого
пользователя).

### Из GitHub

```
/plugin marketplace add simaprivet/py-dev-guard
/plugin install py-dev-guard@simaprivet-tools
```

### Проверка, что всё подхватилось

- `/plugin` — в списке установленных плагинов должен быть
  `py-dev-guard`, включённый (enabled).
- Там же в деталях плагина должны быть видны три активных хука
  (`PostToolUse: check_python_syntax.py`, `PreToolUse:
  protect_gitignored.py`, `PreToolUse: run_tests_before_commit.py`).
- Субагент должен быть доступен как `py-dev-guard:reviewer` (виден в
  списке агентов, вызывается из `/check` через Agent).
- Команда `/check` должна появиться в автодополнении слэш-команд как
  `/py-dev-guard:check` (или `/check`, если конфликтов имён нет).

Обновление плагина после изменений в репозитории (свежий клон/пул) —
`/plugin marketplace update simaprivet-tools`. Отключить: `/plugin
uninstall py-dev-guard`. Убрать marketplace целиком: `/plugin
marketplace remove simaprivet-tools`.

## Что намеренно не вошло

- **Скилл `/deploy`** — остался только в самом трекере
  (`.claude/skills/deploy/SKILL.md`). Он жёстко завязан на конкретный
  сервер (IP, systemd-служба, пути) и в общем плагине был бы просто
  нерабочим шаблоном.
- **Защита `data.json` и `deploy/`** — в исходном хуке трекера
  (`protect_files.py`) кроме проверки `.gitignore` были ещё две
  захардкоженные проверки на конкретные пути этого проекта. Сюда
  вошла только generic-часть (`.gitignore`); project-specific часть
  осталась только в `.claude/hooks/protect_files.py` самого трекера.
