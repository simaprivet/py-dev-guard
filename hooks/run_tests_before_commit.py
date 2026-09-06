#!/usr/bin/env python3
"""PreToolUse-хук: перед git commit запускает pytest, блокирует коммит при упавших тестах."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 120
NO_TESTS_COLLECTED = 5

payload = json.load(sys.stdin)
command = payload.get("tool_input", {}).get("command", "")

if not re.search(r"\bgit\s+(\S+\s+)*commit\b", command):
    sys.exit(0)

project_root = Path.cwd().resolve()


def candidate_pythons(root: Path):
    for venv_name in (".venv", "venv"):
        yield root / venv_name / "bin" / "python"
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        yield Path(venv, "bin", "python")
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            yield Path(found)


def has_pytest(python_bin: Path) -> bool:
    try:
        check = subprocess.run(
            [str(python_bin), "-c", "import pytest"],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return check.returncode == 0


python_bin = None
for candidate in candidate_pythons(project_root):
    if candidate.exists() and has_pytest(candidate):
        python_bin = candidate
        break

if python_bin is None:
    sys.exit(0)  # pytest не установлен ни в одном найденном интерпретаторе — не мешаем коммиту

try:
    result = subprocess.run(
        [str(python_bin), "-m", "pytest", "-q"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
except subprocess.TimeoutExpired:
    print(
        f"Заблокировано хуком run_tests_before_commit: pytest не уложился в {TIMEOUT_SECONDS} с — коммит остановлен",
        file=sys.stderr,
    )
    sys.exit(2)

if result.returncode in (0, NO_TESTS_COLLECTED):
    sys.exit(0)

output = (result.stdout + result.stderr).strip()
print(
    "Заблокировано хуком run_tests_before_commit: тесты pytest не прошли — коммит остановлен\n\n"
    + output,
    file=sys.stderr,
)
sys.exit(2)
