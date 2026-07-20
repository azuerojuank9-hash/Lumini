from datetime import datetime
from app.repositories.channel_repository import (
    get_canales_para_rector, get_canales_para_usuario, get_canal, es_miembro,
    get_mensajes_canal, get_mensajes_nuevos, insertar_mensaje,
    actualizar_tiene_archivos, actualizar_actividad, marcar_mensajes_leidos,
    get_mensaje, actualizar_mensaje, soft_delete_mensaje,
    crear_reaccion, eliminar_reaccion, get_reaccion_existente,
    get_mensaje_fijado, insertar_fijado, eliminar_fijado, get_mensajes_fijados,
    get_archivos_biblioteca, get_enlaces_biblioteca, buscar_mensajes,
    get_miembros_canal, get_total_mensajes, get_actividad_canal,
    get_lecturas_por_miembro, get_actividad_estados, set_estado_actividad,
    guardar_enlace,
)

REACCIONES_VALIDAS = ('👍', '✅', '❓', '📌', '❤')
TIEMPO_EDICION_SEGUNDOS = 300
TABLE_MAP = {'profesor': 'profesores', 'estudiante': 'alumnos', 'rector': 'rectores', 'directora': 'directoras'}


def list_canales(slug, tipo, uid, conn, fa):
    if tipo == 'rector':
        rector = fa.get_rector(slug)
        return [dict(r) for r in get_canales_para_rector(conn, rector['id'])]
    return [dict(r) for r in get_canales_para_usuario(conn, tipo, uid, tipo, uid, tipo, uid)]


def verificar_acceso_canal(conn, cid, tipo, uid):
    if tipo == 'rector':
        return True
    return bool(es_miembro(conn, cid, tipo, uid))


def obtener_mensajes(conn, cid, tipo, uid):
    result = [dict(r) for r in get_mensajes_canal(conn, cid, tipo, uid)]
    _enriquecer_mensajes_batch(conn, result)
    return result


def obtener_mensajes_nuevos(conn, cid, tipo, uid, ultimo_id):
    result = [dict(r) for r in get_mensajes_nuevos(conn, cid, tipo, uid, ultimo_id)]
    _enriquecer_mensajes_batch(conn, result)
    return result


def enviar_mensaje(conn, cid, tipo, uid, mensaje, responde_a, tiene_archivos):
    mid = insertar_mensaje(conn, cid, tipo, uid, mensaje, responde_a, tiene_archivos)
    actualizar_actividad(conn, cid, tipo, uid, 'online', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return mid


def marcar_leidos(conn, cid, tipo, uid):
    marcar_mensajes_leidos(conn, cid, tipo, uid)


def editar_mensaje(conn, mid, cid, tipo, uid, nuevo_texto):
    msg = get_mensaje(conn, mid, cid)
    if not msg:
        return None, 'No encontrado'
    if msg['usuario_tipo'] != tipo or msg['usuario_id'] != uid:
        return None, 'No puedes editar este mensaje'
    if msg['eliminado']:
        return None, 'Mensaje eliminado'
    try:
        creado = datetime.strptime(msg['fecha'], '%Y-%m-%d %H:%M:%S') if msg['fecha'] else datetime.min
    except (ValueError, TypeError):
        creado = datetime.min
    if (datetime.now() - creado).total_seconds() > TIEMPO_EDICION_SEGUNDOS:
        return None, 'Tiempo de edición expirado'
    if not nuevo_texto:
        return None, 'Mensaje vacío'
    actualizar_mensaje(conn, mid, nuevo_texto, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return msg['mensaje'], None


def eliminar_mensaje(conn, mid, cid, tipo, uid):
    msg = get_mensaje(conn, mid, cid)
    if not msg:
        return None, 'No encontrado'
    if msg['usuario_tipo'] != tipo or msg['usuario_id'] != uid:
        return None, 'No puedes eliminar este mensaje'
    soft_delete_mensaje(conn, mid)
    return msg['mensaje'][:200], None


def toggle_reaccion(conn, mensaje_id, tipo, uid, reaccion):
    if reaccion not in REACCIONES_VALIDAS:
        return None
    existing = get_reaccion_existente(conn, mensaje_id, tipo, uid, reaccion)
    if existing:
        eliminar_reaccion(conn, existing['id'])
        return False
    crear_reaccion(conn, mensaje_id, tipo, uid, reaccion)
    return True


def toggle_fijado(conn, cid, mensaje_id, tipo, uid):
    existing = get_mensaje_fijado(conn, cid, mensaje_id)
    if existing:
        eliminar_fijado(conn, existing['id'])
        return False
    insertar_fijado(conn, cid, mensaje_id, tipo, uid)
    return True


def obtener_fijados(conn, cid):
    rows = get_mensajes_fijados(conn, cid)
    result = [dict(r) for r in rows]
    for m in result:
        m['autor_nombre'] = nombre_usuario_canal(conn, m['usuario_tipo'], m['usuario_id'])
    return result


def obtener_biblioteca(conn, cid):
    archivos = [dict(r) for r in get_archivos_biblioteca(conn, cid)]
    enlaces = [dict(r) for r in get_enlaces_biblioteca(conn, cid)]
    return {'archivos': archivos, 'enlaces': enlaces}


def buscar(conn, cid, q, autor, desde, hasta):
    rows = buscar_mensajes(conn, cid, q, autor, desde, hasta)
    result = [dict(r) for r in rows]
    _enriquecer_mensajes_batch(conn, result)
    return result


def obtener_lecturas(conn, cid):
    miembros = get_miembros_canal(conn, cid)
    total_msg = get_total_mensajes(conn, cid)
    ult_vistas = {}
    for row in get_actividad_canal(conn, cid):
        ult_vistas[f"{row['usuario_tipo']}_{row['usuario_id']}"] = row['ultima_vista']
    leidos_por_miembro = {}
    for row in get_lecturas_por_miembro(conn, cid):
        leidos_por_miembro[f"{row['usuario_tipo']}_{row['usuario_id']}"] = row['c']
    seen = set()
    tipo_ids = {'profesor': set(), 'estudiante': set(), 'rector': set(), 'directora': set()}
    for m in miembros:
        key = (m['usuario_tipo'], m['usuario_id'])
        if key not in seen:
            seen.add(key)
            if m['usuario_tipo'] in tipo_ids:
                tipo_ids[m['usuario_tipo']].add(m['usuario_id'])
    name_map = {}
    for t, ids in tipo_ids.items():
        if not ids:
            continue
        ph2 = ','.join('?' * len(ids))
        rows = conn.execute(f'SELECT id, nombre FROM {TABLE_MAP[t]} WHERE id IN ({ph2})', list(ids)).fetchall()
        for r in rows:
            name_map[(t, r['id'])] = r['nombre']
    result = {}
    for m in miembros:
        key = f"{m['usuario_tipo']}_{m['usuario_id']}"
        result[key] = {
            'nombre': name_map.get((m['usuario_tipo'], m['usuario_id']), 'Desconocido'),
            'tipo': m['usuario_tipo'],
            'total': total_msg,
            'leidos': leidos_por_miembro.get(key, 0),
            'ultima_vista': ult_vistas.get(key),
        }
    return result


def obtener_actividad(conn, cid):
    rows = get_actividad_estados(conn, cid)
    result = {}
    now = datetime.now()
    for r in rows:
        estado = r['estado']
        ult_vista = datetime.strptime(r['ultima_vista'], '%Y-%m-%d %H:%M:%S') if r['ultima_vista'] else None
        if estado == 'typing' and ult_vista and (now - ult_vista).total_seconds() > 8:
            estado = 'online'
        if ult_vista and (now - ult_vista).total_seconds() > 120:
            estado = 'offline'
        nombre = nombre_usuario_canal(conn, r['usuario_tipo'], r['usuario_id'])
        key = f"{r['usuario_tipo']}_{r['usuario_id']}"
        result[key] = {'estado': estado, 'nombre': nombre, 'ultima_vista': r['ultima_vista']}
    return result


def set_typing(conn, cid, tipo, uid):
    set_estado_actividad(conn, cid, tipo, uid, 'typing', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def crear_enlace(conn, cid, url, titulo, tipo, uid):
    if not url:
        return False
    guardar_enlace(conn, cid, url, titulo, tipo, uid)
    return True


def _enriquecer_mensajes_batch(conn, mensajes):
    if not mensajes:
        return
    mids = [m['id'] for m in mensajes]
    ph = ','.join('?' * len(mids))
    arch_rows = conn.execute(
        f'SELECT * FROM mensajes_archivos WHERE mensaje_id IN ({ph}) ORDER BY id', mids).fetchall()
    arch_by_mid = {}
    for r in arch_rows:
        arch_by_mid.setdefault(r['mensaje_id'], []).append(dict(r))
    reac_rows = conn.execute(
        f'SELECT mensaje_id, reaccion, usuario_tipo, usuario_id FROM mensajes_reacciones WHERE mensaje_id IN ({ph})',
        mids).fetchall()
    reac_by_mid = {}
    for r in reac_rows:
        reac_by_mid.setdefault(r['mensaje_id'], {}).setdefault(r['reaccion'], []).append(
            {'tipo': r['usuario_tipo'], 'id': r['usuario_id']})
    seen = set()
    tipo_ids = {'profesor': set(), 'estudiante': set(), 'rector': set(), 'directora': set()}
    for m in mensajes:
        key = (m['usuario_tipo'], m['usuario_id'])
        if key not in seen:
            seen.add(key)
            if m['usuario_tipo'] in tipo_ids:
                tipo_ids[m['usuario_tipo']].add(m['usuario_id'])
    name_map = {}
    for t, ids in tipo_ids.items():
        if not ids:
            continue
        ph2 = ','.join('?' * len(ids))
        rows = conn.execute(f'SELECT id, nombre FROM {TABLE_MAP[t]} WHERE id IN ({ph2})', list(ids)).fetchall()
        for r in rows:
            name_map[(t, r['id'])] = r['nombre']
    reply_ids = set(m['responde_a'] for m in mensajes if m.get('responde_a'))
    reply_info = {}
    if reply_ids:
        ph3 = ','.join('?' * len(reply_ids))
        padres = conn.execute(
            f'SELECT id, mensaje, usuario_tipo, usuario_id FROM mensajes_canal WHERE id IN ({ph3})',
            list(reply_ids)).fetchall()
        for p in padres:
            reply_info[p['id']] = {
                'id': p['id'],
                'mensaje': p['mensaje'][:120],
                'autor_nombre': name_map.get((p['usuario_tipo'], p['usuario_id']),
                                             nombre_usuario_canal(conn, p['usuario_tipo'], p['usuario_id']))
            }
    for m in mensajes:
        m['archivos'] = arch_by_mid.get(m['id'], [])
        m['reacciones'] = reac_by_mid.get(m['id'], {})
        m['autor_nombre'] = name_map.get((m['usuario_tipo'], m['usuario_id']), 'Desconocido')
        if m.get('responde_a') and m['responde_a'] in reply_info:
            m['responde_a_info'] = reply_info[m['responde_a']]


def nombre_usuario_canal(conn, tipo, uid):
    table = TABLE_MAP.get(tipo)
    if not table:
        return 'Desconocido'
    r = conn.execute(f'SELECT nombre FROM {table} WHERE id=?', (uid,)).fetchone()
    return r['nombre'] if r else 'Desconocido'


def canales_usuario(slug, usuario_tipo, usuario_id):
    from app.infra.database import conectar
    conn = conectar(slug)
    rows = conn.execute('''
        SELECT c.*,
            (SELECT mensaje FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_mensaje,
            (SELECT usuario_tipo FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_tipo,
            (SELECT usuario_id FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_id,
            (SELECT fecha FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultima_fecha,
            (SELECT COUNT(*) FROM mensajes_canal mc
             LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=mc.id AND ml.usuario_tipo=? AND ml.usuario_id=?
             WHERE mc.canal_id=c.id AND ml.id IS NULL) as no_leidos
        FROM canales c
        JOIN canal_miembros cm ON cm.canal_id=c.id
        WHERE cm.usuario_tipo=? AND cm.usuario_id=? AND c.activo=1
        ORDER BY ultima_fecha DESC''', (usuario_tipo, usuario_id, usuario_tipo, usuario_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def agregar_miembro_canal(conn, canal_id, usuario_tipo, usuario_id):
    sql = 'INSERT OR IGNORE INTO canal_miembros (canal_id, usuario_tipo, usuario_id) VALUES (?,?,?)'
    conn.execute(sql, (canal_id, usuario_tipo, usuario_id))


def asignar_miembros_auto(conn, slug, canal_id, tipo, curso='', materia=''):
    from app.infra.helpers import get_rector
    if tipo in ('institucional', 'rectoria', 'profesores'):
        for p in conn.execute('SELECT id FROM profesores WHERE activo=1').fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['id'])
    if tipo == 'institucional':
        for a in conn.execute('SELECT id FROM alumnos WHERE activo=1').fetchall():
            agregar_miembro_canal(conn, canal_id, 'estudiante', a['id'])
    elif tipo == 'director_curso' and curso:
        for d in conn.execute('SELECT id FROM directoras WHERE curso=? AND activo=1', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'directora', d['id'])
        for p in conn.execute('SELECT DISTINCT profesor_id FROM asignaciones_curso WHERE curso=?', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['profesor_id'])
    elif tipo == 'curso' and curso:
        for p in conn.execute('SELECT DISTINCT profesor_id FROM asignaciones_curso WHERE curso=?', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['profesor_id'])
        for a in conn.execute('SELECT id FROM alumnos WHERE curso=? AND activo=1', (curso,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'estudiante', a['id'])
    elif tipo == 'materia' and materia:
        for p in conn.execute('SELECT DISTINCT profesor_id FROM asignaciones_materia WHERE materia=?', (materia,)).fetchall():
            agregar_miembro_canal(conn, canal_id, 'profesor', p['profesor_id'])
        for cr in conn.execute('SELECT DISTINCT curso FROM actividades WHERE materia=?', (materia,)).fetchall():
            for a in conn.execute('SELECT id FROM alumnos WHERE curso=? AND activo=1', (cr['curso'],)).fetchall():
                agregar_miembro_canal(conn, canal_id, 'estudiante', a['id'])
    rector = get_rector(slug)
    if rector:
        agregar_miembro_canal(conn, canal_id, 'rector', rector['id'])
