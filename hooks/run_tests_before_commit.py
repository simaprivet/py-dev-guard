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

venv = os.environ.get("VIRTUAL_ENV")
pytest_bin = None
if venv:
    candidate = Path(venv, "bin", "pytest")
    if candidate.exists():
        pytest_bin = str(candidate)
if pytest_bin is None:
    pytest_bin = shutil.which("pytest")

if not pytest_bin:
    sys.exit(0)  # pytest не установлен — не мешаем коммиту

try:
    result = subprocess.run(
        [pytest_bin, "-q"],
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
