#!/usr/bin/env python3
"""PostToolUse-хук: проверяет синтаксис .py-файла после Edit/Write/NotebookEdit."""

import ast
import json
import sys

payload = json.load(sys.stdin)
tool_input = payload.get("tool_input", {})
file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

if not file_path.endswith(".py"):
    sys.exit(0)

try:
    with open(file_path) as f:
        source = f.read()
    ast.parse(source)
except SyntaxError as e:
    reason = f"Синтаксическая ошибка в {file_path}:\n{e}"
    print(json.dumps({
        "decision": "block",
        "reason": reason,
        "systemMessage": f"⚠️ Синтаксическая ошибка: {file_path}",
    }))
