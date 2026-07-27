import json
from pathlib import Path

src = Path('.vscode/tasks.json')
out = Path('scripts/legacy_powershell_tasks.json')

data = json.loads(src.read_text(encoding='utf-8'))
legacy = {}
for task in data.get('tasks', []):
    if str(task.get('command', '')).lower() != 'powershell':
        continue
    label = task.get('label', '')
    args = task.get('args', [])
    script = args[2] if len(args) > 2 else ''
    legacy[label] = script

out.write_text(json.dumps(legacy, indent=2), encoding='utf-8')
print(f'WROTE={out} COUNT={len(legacy)}')
