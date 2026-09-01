#!/usr/bin/env python3
"""PreToolUse-хук: блокирует запись в файлы, попадающие под .gitignore репозитория."""

import json
import subprocess
import sys
from pathlib import Path

payload = json.load(sys.stdin)
tool_input = payload.get("tool_input", {})
file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

if not file_path:
    sys.exit(0)

project_root = Path.cwd().resolve()
path = Path(file_path)
try:
    rel = path.resolve().relative_to(project_root)
except ValueError:
    sys.exit(0)  # путь вне репозитория — не наша забота

rel_str = str(rel)

ignored = subprocess.run(["git", "check-ignore", "-q", rel_str], cwd=project_root)
if ignored.returncode == 0:
    print(f"Заблокировано хуком protect_gitignored: {rel_str} в .gitignore — запись запрещена", file=sys.stderr)
    sys.exit(2)
