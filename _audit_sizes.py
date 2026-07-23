import os
root = 'C:/Users/PC/OneDrive/Documentos/GitHub/Lumini'
for r, d, fs in os.walk(root):
    if any(skip in r for skip in ['__pycache__', '.venv', 'tests', '.agents', 'node_modules']):
        continue
    for f in fs:
        if not f.endswith('.py'):
            continue
        fp = os.path.join(r, f)
        try:
            with open(fp, encoding='utf-8') as fh:
                lines = sum(1 for _ in fh)
            if lines > 300:
                print(f'{os.path.relpath(fp, root)}: {lines} lines')
        except Exception:
            pass
