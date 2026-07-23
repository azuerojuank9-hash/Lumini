import os
import sqlite3

base = r"C:\Users\PC\OneDrive\Documentos\GitHub\Lumini"
tdb = os.path.join(base, 'colegios_db', 'testcolegio.db')
print(f'DB exists: {os.path.exists(tdb)}, size: {os.path.getsize(tdb) if os.path.exists(tdb) else 0}')
sdb = sqlite3.connect(tdb)
sdb.row_factory = sqlite3.Row
tables = [r[0] for r in sdb.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f'Tables ({len(tables)}): {tables}')
for t in ['profesores', 'rectores', 'estudiantes', 'directoras', 'materias', 'cursos', 'horarios']:
    if t in tables:
        rows = sdb.execute(f"SELECT * FROM {t}").fetchall()
        print(f'\n{t}: {len(rows)} rows')
        for r in rows[:5]:
            for k in r.keys():
                v = r[k]
                if k in ['password', 'clave']:
                    v = f'{str(v)[:30]}...'
                print(f'  {k}: {v}')
            print('---')
sdb.close()

# Also check config
if 'configuracion' in tables:
    cfg = sdb.execute("SELECT * FROM configuracion").fetchall()
    for c in cfg:
        print(f'config: {dict(c)}')
