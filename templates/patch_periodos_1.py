#!/usr/bin/env python3
"""Patch completo: periodos configurables por colegio"""
import sqlite3, os

# 1. Agregar columna num_periodos a master.db
print("=== Actualizando master.db ===")
c = sqlite3.connect('/home/juankamilo097/master.db')
try:
    c.execute("ALTER TABLE colegios ADD COLUMN num_periodos INTEGER DEFAULT 4")
    print("OK - columna num_periodos agregada")
except Exception as e:
    print(f"Ya existe o error: {e}")
# Actualizar institucion-educativa-compartir a 3 periodos
c.execute("UPDATE colegios SET num_periodos=3 WHERE slug='institucion-educativa-compartir'")
c.commit()
print("OK - institucion-educativa-compartir tiene 3 periodos")
c.close()

# 2. Agregar columna periodo a actividades y evaluaciones en cada colegio
DB_FOLDER = '/home/juankamilo097/colegios_db'
for f in os.listdir(DB_FOLDER):
    if not f.endswith('.db'): continue
    path = os.path.join(DB_FOLDER, f)
    c = sqlite3.connect(path)
    for tabla in ['actividades', 'evaluaciones']:
        try:
            c.execute(f"ALTER TABLE {tabla} ADD COLUMN periodo INTEGER DEFAULT 1")
            print(f"OK - {f}: periodo agregado a {tabla}")
        except Exception as e:
            print(f"  {f}/{tabla}: {e}")
    c.commit()
    c.close()

# 3. Parchear flask_app.py
print("\n=== Parcheando flask_app.py ===")
with open('/home/juankamilo097/flask_app.py', 'r') as f:
    code = f.read()

# Parchear init_master_db para incluir num_periodos
old_init = """def init_master_db():
    c = conectar_master()
    c.execute(\'\'\'CREATE TABLE IF NOT EXISTS colegios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL,
        logo_url TEXT DEFAULT \\'\\', activo INTEGER DEFAULT 1,
        creado TEXT DEFAULT (date(\\'now\\'))
    )\'\'\')
    # Agregar logo_url si no existe (migración)
    try: c.execute(\\'ALTER TABLE colegios ADD COLUMN logo_url TEXT DEFAULT ""\\')
    except: pass
    c.commit(); c.close()"""

new_init = """def init_master_db():
    c = conectar_master()
    c.execute(\'\'\'CREATE TABLE IF NOT EXISTS colegios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL, nombre TEXT NOT NULL,
        logo_url TEXT DEFAULT \\'\\', activo INTEGER DEFAULT 1,
        num_periodos INTEGER DEFAULT 4,
        creado TEXT DEFAULT (date(\\'now\\'))
    )\'\'\')
    for col, default in [('logo_url','""'), ('num_periodos','4')]:
        try: c.execute(f\\'ALTER TABLE colegios ADD COLUMN {col} TEXT DEFAULT {default}\\')
        except: pass
    c.commit(); c.close()"""

if old_init in code:
    code = code.replace(old_init, new_init)
    print("OK - init_master_db actualizado")
else:
    print("WARN - init_master_db no encontrado, agregando migracion manual")
    # Agregar al inicio de init_master_db existente
    code = code.replace(
        "    try: c.execute('ALTER TABLE colegios ADD COLUMN logo_url TEXT DEFAULT \"\"')\n    except: pass",
        "    try: c.execute('ALTER TABLE colegios ADD COLUMN logo_url TEXT DEFAULT \"\"')\n    except: pass\n    try: c.execute('ALTER TABLE colegios ADD COLUMN num_periodos INTEGER DEFAULT 4')\n    except: pass"
    )
    print("OK - migracion de num_periodos agregada")

# Parchear crear_colegio para guardar num_periodos
old_crear = """                    cm.execute('INSERT INTO colegios (slug,nombre,logo_url) VALUES (?,?,?)', (slug,nombre,logo_url))"""
new_crear = """                    num_periodos = int(request.form.get('num_periodos', 4))
                    cm.execute('INSERT INTO colegios (slug,nombre,logo_url,num_periodos) VALUES (?,?,?,?)', (slug,nombre,logo_url,num_periodos))"""

if old_crear in code:
    code = code.replace(old_crear, new_crear)
    print("OK - crear_colegio actualizado")

# Parchear editar_colegio para guardar num_periodos
old_editar = """            slug_e   = request.form.get('slug')
            nombre_n = request.form.get('nombre_nuevo','').strip()
            logo_n   = request.form.get('logo_nuevo','').strip()
            cm = conectar_master()
            cm.execute('UPDATE colegios SET nombre=?, logo_url=? WHERE slug=?',(nombre_n,logo_n,slug_e))"""
new_editar = """            slug_e   = request.form.get('slug')
            nombre_n = request.form.get('nombre_nuevo','').strip()
            logo_n   = request.form.get('logo_nuevo','').strip()
            num_p    = int(request.form.get('num_periodos_nuevo', 4))
            cm = conectar_master()
            cm.execute('UPDATE colegios SET nombre=?, logo_url=?, num_periodos=? WHERE slug=?',(nombre_n,logo_n,num_p,slug_e))"""

if old_editar in code:
    code = code.replace(old_editar, new_editar)
    print("OK - editar_colegio actualizado")

# Parchear vista_estudiante completa
old_est = code[code.find('# ── ESTUDIANTE'):code.find('# ── STATIC')]
new_est = """# ── ESTUDIANTE ────────────────────────────────────────────────────────────────
@app.route('/<slug>/estudiante')
def vista_estudiante(slug):
    require_colegio(slug)
    if session.get(f'rol_{slug}') != 'estudiante': return redirect(url_for('login', slug=slug))
    aid     = session.get(f'alumno_id_{slug}')
    colegio = get_colegio(slug)
    num_periodos = colegio['num_periodos'] if colegio and colegio['num_periodos'] else 4
    periodo_sel  = request.args.get('periodo', 1, type=int)  # 0 = general

    c = conectar(slug)
    alumno = c.execute('SELECT * FROM alumnos WHERE id=?',(aid,)).fetchone()

    MESES = {'01':'Enero','02':'Febrero','03':'Marzo','04':'Abril','05':'Mayo','06':'Junio',
             '07':'Julio','08':'Agosto','09':'Septiembre','10':'Octubre','11':'Noviembre','12':'Diciembre'}
    historial_raw = c.execute('SELECT fecha,estado FROM asistencia WHERE aid=? ORDER BY fecha',(aid,)).fetchall()
    historial_meses = {}
    asist_stats = {'P':0,'A':0,'T':0,'total':0}
    for h in historial_raw:
        est = h['estado']
        asist_stats[est] = asist_stats.get(est,0) + 1
        asist_stats['total'] += 1
        if h['fecha']:
            p2 = h['fecha'].split('-')
            if len(p2) >= 2:
                label = f"{MESES.get(p2[1],p2[1])} {p2[0]}"
                historial_meses.setdefault(label,[]).append({'fecha':h['fecha'],'estado':h['estado']})

    if periodo_sel == 0:
        notas_raw = c.execute(
            \'\'\'SELECT ac.materia, ac.nombre as act_nombre, n.val, COALESCE(ac.periodo,1) as periodo
               FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
               WHERE n.aid=? ORDER BY ac.materia, ac.orden\'\'\', (aid,)
        ).fetchall()
        evals_raw = c.execute('SELECT materia,evaluacion,autoevaluacion FROM evaluaciones WHERE aid=?',(aid,)).fetchall()
    else:
        notas_raw = c.execute(
            \'\'\'SELECT ac.materia, ac.nombre as act_nombre, n.val, COALESCE(ac.periodo,1) as periodo
               FROM notas n JOIN actividades ac ON ac.id=n.actividad_id
               WHERE n.aid=? AND COALESCE(ac.periodo,1)=? ORDER BY ac.materia, ac.orden\'\'\', (aid, periodo_sel)
        ).fetchall()
        evals_raw = c.execute(
            'SELECT materia,evaluacion,autoevaluacion FROM evaluaciones WHERE aid=? AND COALESCE(periodo,1)=?',
            (aid, periodo_sel)
        ).fetchall()

    evals_map = {e['materia']: dict(e) for e in evals_raw}
    observaciones = c.execute('SELECT materia,texto,fecha FROM observaciones WHERE aid=? ORDER BY fecha DESC',(aid,)).fetchall()
    c.close()

    notas_periodo = {}
    for nr in notas_raw:
        mat = nr['materia']
        if mat not in notas_periodo:
            notas_periodo[mat] = {'actividades':[], 'evaluacion':None, 'autoevaluacion':None, 'promedio':0}
        notas_periodo[mat]['actividades'].append({'nombre':nr['act_nombre'],'val':nr['val']})

    for mat, ev in evals_map.items():
        if mat not in notas_periodo:
            notas_periodo[mat] = {'actividades':[], 'evaluacion':None, 'autoevaluacion':None, 'promedio':0}
        notas_periodo[mat]['evaluacion']     = ev.get('evaluacion')
        notas_periodo[mat]['autoevaluacion'] = ev.get('autoevaluacion')

    all_vals = []
    for mat, data in notas_periodo.items():
        vals = [a['val'] for a in data['actividades']]
        if data['evaluacion'] is not None: vals.append(data['evaluacion'])
        if data['autoevaluacion'] is not None: vals.append(data['autoevaluacion'])
        data['promedio'] = round(sum(vals)/len(vals),2) if vals else 0
        all_vals.extend(vals)

    promedio_general = round(sum(all_vals)/len(all_vals),2) if all_vals else 0

    return render_template('estudiante.html',
        alumno=alumno, colegio=colegio, slug=slug,
        notas_periodo=notas_periodo,
        promedio_general=promedio_general,
        periodo_sel=periodo_sel,
        num_periodos=num_periodos,
        historial_meses=historial_meses,
        asist_stats=asist_stats,
        observaciones=[dict(o) for o in observaciones])

"""

code = code[:code.find('# ── ESTUDIANTE')] + new_est + code[code.find('# ── STATIC'):]
print("OK - vista_estudiante actualizada")

with open('/home/juankamilo097/flask_app.py', 'w') as f:
    f.write(code)

print("\n=== Todo listo ===")
