import json
import logging

from app.infra.database import conectar

app_logger = logging.getLogger(__name__)


def crear_notificacion(slug, usuario_tipo, usuario_id, titulo, mensaje='', tipo='info', link=''):
    conn = conectar(slug)
    conn.execute(
        'INSERT INTO notificaciones (usuario_tipo,usuario_id,titulo,mensaje,tipo,link) VALUES (?,?,?,?,?,?)',
        (usuario_tipo, usuario_id, titulo, mensaje, tipo, link))
    conn.commit()
    conn.close()


def notificaciones_no_leidas(slug, usuario_tipo, usuario_id, conn=None):
    cerrar = conn or conectar(slug)
    c = cerrar.execute(
        'SELECT COUNT(*) as c FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? AND leida=0',
        (usuario_tipo, usuario_id)).fetchone()['c']
    if not conn:
        cerrar.close()
    return c


def generar_destinatarios(slug, comunicacion_id):
    try:
        conn = conectar(slug)
    except Exception as e:
        app_logger.error(f'generar_destinatarios: error conectando DB {slug}: {e}')
        return
    try:
        cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
        if 'leido' not in cols_cl:
            conn.execute('ALTER TABLE comunicaciones_leidas ADD COLUMN leido INTEGER DEFAULT 0')
            conn.commit()
            cols_cl = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
    except Exception as e:
        app_logger.error(f'generar_destinatarios: error migrando columna leido: {e}')
    if 'leido' not in cols_cl:
        conn.close()
        app_logger.error('generar_destinatarios: columna leido no disponible en comunicaciones_leidas, abortando')
        return
    com = conn.execute('SELECT * FROM comunicaciones WHERE id=?', (comunicacion_id,)).fetchone()
    if not com:
        conn.close()
        app_logger.warning(f'generar_destinatarios: comunicacion {comunicacion_id} no encontrada')
        return
    if com['estado'] != 'publicado':
        conn.close()
        return
    dest_tipo = com['destinatario_tipo']
    try:
        val_arr = json.loads(com['destinatario_valor']) if com['destinatario_valor'] else []
    except (json.JSONDecodeError, TypeError) as e:
        app_logger.warning(f'generar_destinatarios: error parseando destinatario_valor="{com["destinatario_valor"]}": {e}')
        val_arr = []
    if not isinstance(val_arr, list):
        app_logger.warning(f'generar_destinatarios: destinatario_valor no es un array, ignorando: {type(val_arr).__name__}')
        val_arr = []
    destinatarios = []
    if dest_tipo == 'todo_colegio':
        for r in conn.execute('SELECT id FROM profesores WHERE activo=1').fetchall():
            destinatarios.append(('profesor', r['id']))
        for r in conn.execute('SELECT id FROM directoras WHERE activo=1').fetchall():
            destinatarios.append(('directora', r['id']))
        for r in conn.execute('SELECT id FROM alumnos WHERE activo=1').fetchall():
            destinatarios.append(('estudiante', r['id']))
    elif dest_tipo == 'profesores':
        if val_arr:
            for v in val_arr:
                if isinstance(v, str) and v.startswith('prof_'):
                    try:
                        destinatarios.append(('profesor', int(v.split('_')[1])))
                    except (ValueError, IndexError):
                        app_logger.warning(f'generar_destinatarios: valor prof_ invalido: {v}')
        else:
            for r in conn.execute('SELECT id FROM profesores WHERE activo=1').fetchall():
                destinatarios.append(('profesor', r['id']))
    elif dest_tipo == 'directores':
        if val_arr:
            for v in val_arr:
                if isinstance(v, str) and v.startswith('dir_'):
                    try:
                        destinatarios.append(('directora', int(v.split('_')[1])))
                    except (ValueError, IndexError):
                        app_logger.warning(f'generar_destinatarios: valor dir_ invalido: {v}')
        else:
            for r in conn.execute('SELECT id FROM directoras WHERE activo=1').fetchall():
                destinatarios.append(('directora', r['id']))
    elif dest_tipo == 'estudiantes':
        for r in conn.execute('SELECT id FROM alumnos WHERE activo=1').fetchall():
            destinatarios.append(('estudiante', r['id']))
    elif dest_tipo == 'grado':
        if val_arr:
            cursos_grado = {}
            for row in conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1').fetchall():
                c = row['curso']
                grade_num = ''.join(filter(str.isdigit, c))
                cursos_grado.setdefault(grade_num, []).append(c)
            for grado in val_arr:
                for curso in cursos_grado.get(str(grado), []):
                    for r in conn.execute('SELECT id FROM alumnos WHERE activo=1 AND curso=?', (curso,)).fetchall():
                        destinatarios.append(('estudiante', r['id']))
    elif dest_tipo == 'cursos':
        if val_arr:
            for curso in val_arr:
                for r in conn.execute('SELECT id FROM alumnos WHERE activo=1 AND curso=?', (curso,)).fetchall():
                    destinatarios.append(('estudiante', r['id']))
    for tipo, uid in destinatarios:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO comunicaciones_leidas (comunicacion_id,usuario_tipo,usuario_id,leido) VALUES (?,?,?,0)',
                (comunicacion_id, tipo, uid))
        except Exception as e_insert:
            app_logger.error(f'generar_destinatarios: error insertando destinatario tipo={tipo} uid={uid}: {e_insert}')
    conn.commit()
    conn.close()


def comunicaciones_pendientes(slug, usuario_tipo, usuario_id, conn=None):
    cerrar = conn or conectar(slug)
    cols_cl = [r[1] for r in cerrar.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
    if 'leido' not in cols_cl:
        if not conn:
            cerrar.close()
        return []
    rows = cerrar.execute(
        '''SELECT c.*, cl.leido, cl.fecha_lectura
           FROM comunicaciones c
           JOIN comunicaciones_leidas cl ON cl.comunicacion_id=c.id
           WHERE cl.usuario_tipo=? AND cl.usuario_id=? AND COALESCE(cl.leido,0)=0
           AND c.estado='publicado' AND c.activo=1
           ORDER BY c.fecha_publicacion DESC''',
        (usuario_tipo, usuario_id)).fetchall()
    if not conn:
        cerrar.close()
    return [dict(r) for r in rows]
