"""Database Audit — indexes, FKs, slow queries, VACUUM/ANALYZE, missing indexes."""
import sqlite3, os, sys, json

def audit(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    issues = []
    
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    print(f"\n{'='*70}")
    print(f"DATABASE AUDIT: {db_path}")
    print(f"{'='*70}")
    print(f"Tables: {len(tables)}")
    
    # 1. Indexes
    print(f"\n--- INDEXES ---")
    indexes = conn.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name").fetchall()
    idx_by_table = {}
    for idx in indexes:
        tbl = idx['tbl_name']
        if tbl not in idx_by_table:
            idx_by_table[tbl] = []
        idx_by_table[tbl].append(idx['name'])
    for tbl in tables:
        idxs = idx_by_table.get(tbl, [])
        print(f"  {tbl}: {len(idxs)} indexes -> {', '.join(idxs)}")
    
    # 2. FOREIGN KEYS
    print(f"\n--- FOREIGN KEYS ---")
    tables_with_fk = []
    tables_without_fk = []
    for tbl in tables:
        fks = conn.execute(f"PRAGMA foreign_key_list({tbl})").fetchall()
        if fks:
            tables_with_fk.append(tbl)
            print(f"  {tbl}: {len(fks)} FKs")
            for fk in fks:
                print(f"    -> {fk[3]}.{fk[4]} references {fk[2]}.{fk[3]}")
        else:
            tables_without_fk.append(tbl)
    print(f"\n  Tables WITH FKs: {len(tables_with_fk)}")
    print(f"  Tables WITHOUT FKs: {len(tables_without_fk)}")
    for t in tables_without_fk:
        if t.startswith('sqlite_'):
            continue
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        col_hints = [c for c in cols if c.endswith('_id') or c == 'padre_id' or c == 'alumno_id']
        if col_hints:
            issues.append(f"MISSING FK: {t} has columns {col_hints} but no FOREIGN KEY constraint")
    
    # 3. DUPLICATE indexes
    print(f"\n--- DUPLICATE INDEX CHECK ---")
    all_idx_sql = {}
    for idx in indexes:
        sql = idx['sql']
        if sql:
            key = sql.strip()
            if key not in all_idx_sql:
                all_idx_sql[key] = []
            all_idx_sql[key].append(idx['name'])
    for sql, names in all_idx_sql.items():
        if len(names) > 1:
            issues.append(f"DUPLICATE INDEX: {names} share identical SQL")
            print(f"  DUPLICATE: {names}")
    if not any('DUPLICATE INDEX' in i for i in issues):
        print("  No duplicates found.")
    
    # 4. UNIQUE constraints
    print(f"\n--- UNIQUE CONSTRAINTS ---")
    for tbl in tables:
        uniques = conn.execute(f"PRAGMA index_list({tbl})").fetchall()
        for u in uniques:
            if u['unique']:
                print(f"  {tbl}.{u['name']}")
    
    # 5. Table sizes
    print(f"\n--- TABLE SIZES ---")
    for tbl in tables:
        if tbl.startswith('sqlite_'):
            continue
        cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        if cnt > 0:
            print(f"  {tbl}: {cnt} rows")
    
    # 6. Missing recommended indexes (based on common query patterns)
    print(f"\n--- RECOMMENDED INDEXES ---")
    # Check if these exist
    recommended = {
        'notas': ['aid', 'actividad_id'],
        'asistencia': ['aid', 'fecha'],
        'alumno_padre': ['padre_id', 'alumno_id'],
        'entregas': ['actividad_id', 'alumno_id'],
        'comunicaciones_leidas': ['comunicacion_id', 'usuario_id'],
        'observador_registros': ['alumno_id'],
        'canal_miembros': ['canal_id', 'usuario_id'],
        'notificaciones': ['usuario_id'],
        'eventos_calendario': ['curso'],
    }
    for tbl, cols in recommended.items():
        if tbl not in tables:
            continue
        existing = [i['name'] for i in conn.execute(f"PRAGMA index_list({tbl})").fetchall()]
        for col in cols:
            has = False
            for idx_name in existing:
                idx_info = conn.execute(f"PRAGMA index_info({idx_name})").fetchall()
                if any(i[2] == col for i in idx_info):
                    has = True
                    break
            if not has:
                issues.append(f"MISSING INDEX: {tbl}({col}) — frequently queried column without index")
                print(f"  MISSING: {tbl}({col})")
    
    # 7. VACUUM/ANALYZE
    print(f"\n--- VACUUM/ANALYZE CHECK ---")
    page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    freelist = conn.execute("PRAGMA freelist_count").fetchone()[0]
    if page_count > 0:
        pct_free = (freelist / page_count) * 100
        print(f"  Pages: {page_count}, Free pages: {freelist} ({pct_free:.1f}%)")
        if pct_free > 20:
            issues.append(f"VACUUM RECOMMENDED: {pct_free:.1f}% fragmented space")
    else:
        print(f"  Pages: {page_count}")
    
    # Check if ANALYZE has been run
    stats = conn.execute("SELECT name, stat FROM sqlite_stat1").fetchall()
    if stats:
        print(f"  ANALYZE stats present: {len(stats)} entries")
    else:
        issues.append("ANALYZE NOT RUN: No statistics available for query optimizer")
        print(f"  WARNING: No ANALYZE statistics")
    
    # 8. Check for tables without PRIMARY KEY
    print(f"\n--- PRIMARY KEY CHECK ---")
    for tbl in tables:
        if tbl.startswith('sqlite_'):
            continue
        cols = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
        has_pk = any(c['pk'] for c in cols)
        if not has_pk:
            issues.append(f"NO PK: {tbl} has no PRIMARY KEY")
            print(f"  WARNING: {tbl} has no PRIMARY KEY")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Tables: {len(tables)}")
    print(f"Issues found: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    
    return issues

if __name__ == '__main__':
    os.chdir(r'C:\Users\PC\OneDrive\Documentos\GitHub\Lumini')
    sys.path.insert(0, '.')
    os.environ['ENV'] = 'testing'
    from flask_app import init_db
    init_db('testcolegio')
    db_path = os.path.join('colegios_db', 'testcolegio.db')
    audit(db_path)
