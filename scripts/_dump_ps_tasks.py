import json
from pathlib import Path

src = Path('.vscode/tasks.json')
out = Path('artifacts/ps_tasks_dump.txt')

data = json.loads(src.read_text(encoding='utf-8'))
ps = [t for t in data.get('tasks', []) if str(t.get('command', '')).lower() == 'powershell']

lines = [f'COUNT {len(ps)}']
for t in ps:
    lines.append(f"\n### {t.get('label', '')}")
    args = t.get('args', [])
    lines.append(f"ARGS: {args}")

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text('\n'.join(lines), encoding='utf-8')
print(out)
