#!/bin/bash
# Post-edit syntax check for Python files
# Reads hook input JSON from stdin, extracts file_path, runs py_compile

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

if [[ "$FILE_PATH" == *.py ]] && [[ -f "$FILE_PATH" ]]; then
  python -m py_compile "$FILE_PATH" 2>&1 || echo "SYNTAX ERROR in $FILE_PATH"
fi

exit 0
