#!/usr/bin/env python3
"""Ревью диффа текущей ветки относительно master через `claude -p --output-format json`.

Ничего не правит — только печатает замечания в терминал. Работает как
самостоятельный скрипт: годится и для ручного запуска, и для git-хука/CI,
не только как часть плагина Claude Code.
"""

import json
import shutil
import subprocess
import sys

MAX_DIFF_CHARS = 200_000
TIMEOUT_SECONDS = 300
FETCH_TIMEOUT_SECONDS = 15

REVIEW_PROMPT = """\
Проверь приведённый ниже дифф (git diff) и найди только:
- логические ошибки и необработанные краевые случаи (пустой ввод, None/null,
  границы диапазонов, повторные вызовы);
- забытый отладочный код (print/console.log/debugger/breakpoint,
  закомментированные куски, TODO-заглушки, которые не должны попасть в прод);
- секреты и ключи (токены, пароли, приватные ключи, что-либо похожее на
  креды в коде или конфигах);
- очевидные проблемы безопасности: конкатенация/форматирование строк в SQL
  вместо параметризованных запросов, небезопасная работа с путями файлов
  (path traversal, доверие пользовательскому вводу в путях) и подобное.

Стиль, форматирование, именование и организацию кода не трогай — это вне
задачи, этим занимаются линтеры.

Сам дифф передан в stdin. Ничего не исправляй, только отчитайся списком:
файл:строка — в чём проблема — конкретный вход/сценарий, который её
вызывает. Если находок нет, так и скажи одной строкой.
"""


def run_git(args, timeout=None):
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
    )


def resolve_base_ref():
    try:
        fetch = run_git(["fetch", "--quiet", "origin", "master"], timeout=FETCH_TIMEOUT_SECONDS)
        fetch_ok = fetch.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        fetch_ok = False

    if not fetch_ok:
        print(
            "Предупреждение: git fetch origin master не удался (нет сети?) — "
            "сравниваю с локальной веткой master, дифф может быть устаревшим.",
            file=sys.stderr,
        )

    for candidate in ("origin/master", "master"):
        check = run_git(["rev-parse", "--verify", "--quiet", candidate])
        if check.returncode == 0:
            return candidate
    return None


def fail(message, code=1):
    print(message, file=sys.stderr)
    sys.exit(code)


def main():
    if shutil.which("git") is None:
        fail(
            "git не найден в PATH — установи git или добавь его в PATH, "
            "чтобы запускать это ревью."
        )

    branch_result = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch_result.returncode != 0:
        fail("Не удалось определить текущую ветку — это точно git-репозиторий?")
    current_branch = branch_result.stdout.strip()

    base_ref = resolve_base_ref()
    if base_ref is None:
        fail(
            "Не найдена ветка master (ни локально, ни origin/master) — "
            "сравнивать текущую ветку не с чем."
        )

    diff_result = run_git(["diff", f"{base_ref}...HEAD"])
    if diff_result.returncode != 0:
        fail(f"git diff завершился с ошибкой:\n{diff_result.stderr.strip()}")
    diff_text = diff_result.stdout

    if not diff_text.strip():
        print(f"Диф пуст: {current_branch} не отличается от {base_ref} — нечего ревьюить.")
        sys.exit(0)

    if len(diff_text) > MAX_DIFF_CHARS:
        fail(
            f"Диф слишком большой ({len(diff_text)} символов, лимит "
            f"{MAX_DIFF_CHARS}) — ревью одним запросом сожжёт контекст. "
            "Разбей изменения на более мелкие коммиты/PR или проверь часть "
            "диффа вручную.",
            code=2,
        )

    claude_path = shutil.which("claude")
    if claude_path is None:
        fail(
            "claude не найден в PATH — установи Claude Code или добавь его "
            "в PATH, чтобы запускать это ревью."
        )

    try:
        result = subprocess.run(
            [claude_path, "-p", REVIEW_PROMPT, "--output-format", "json"],
            input=diff_text,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        fail(f"claude не уложился в {TIMEOUT_SECONDS} с — ревью прервано по таймауту.")
    except OSError as e:
        fail(f"Не удалось запустить claude: {e}")

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        fail(f"claude завершился с ошибкой (код {result.returncode}):\n{details}")

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail(
            "Не удалось разобрать JSON-ответ claude. Сырой вывод:\n"
            + result.stdout.strip()
        )

    if parsed.get("is_error"):
        fail(f"claude вернул ошибку: {parsed.get('result') or parsed}")

    print(f"Ревью диффа {current_branch} относительно {base_ref}:\n")
    print(parsed.get("result", "").strip() or "(пустой ответ)")


if __name__ == "__main__":
    main()
