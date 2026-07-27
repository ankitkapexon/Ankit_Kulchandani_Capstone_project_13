import json
from pathlib import Path

TASKS_PATH = Path('.vscode/tasks.json')

data = json.loads(TASKS_PATH.read_text(encoding='utf-8'))
count = 0
for task in data.get('tasks', []):
    if str(task.get('command', '')).lower() != 'powershell':
        continue
    label = task.get('label', '')
    task['command'] = '.\\.venv\\Scripts\\python.exe'
    task['args'] = ['scripts/task_runner.py', 'run-label', '--label', label]
    count += 1

TASKS_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')
print(f'MIGRATED={count}')
