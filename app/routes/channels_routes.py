from flask import Blueprint, jsonify, request, session
from datetime import datetime
from app.services.channel_service import _enriquecer_mensajes_batch, nombre_usuario_canal, canales_usuario

channels_bp = Blueprint('channels', __name__)


def _fa():
    import flask_app as fa
    return fa


@channels_bp.route('/<slug>/api/canales')
def api_canales(slug):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    if tipo == 'rector':
        rector = fa.get_rector(slug)
        conn = fa.conectar(slug)
        rows = conn.execute('''
            SELECT c.*,
                (SELECT mensaje FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_mensaje,
                (SELECT usuario_tipo FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_tipo,
                (SELECT usuario_id FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_id,
                (SELECT fecha FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultima_fecha,
                (SELECT COUNT(*) FROM mensajes_canal mc
                 LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=mc.id AND ml.usuario_tipo='rector' AND ml.usuario_id=?
                 WHERE mc.canal_id=c.id AND ml.id IS NULL) as no_leidos
            FROM canales c WHERE c.activo=1 ORDER BY ultima_fecha DESC''', (rector['id'],)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    return jsonify(canales_usuario(slug, tipo, uid))


@channels_bp.route('/<slug>/api/canales/<int:cid>/mensajes')
def api_canales_mensajes(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify([])
    conn = fa.conectar(slug)
    canal = conn.execute('SELECT * FROM canales WHERE id=? AND activo=1', (cid,)).fetchone()
    if not canal:
        conn.close()
        return jsonify([])
    if tipo != 'rector':
        miembro = conn.execute('SELECT 1 FROM canal_miembros WHERE canal_id=? AND usuario_tipo=? AND usuario_id=?',
                              (cid, tipo, uid)).fetchone()
        if not miembro:
            conn.close()
            return jsonify([])
    mensajes = conn.execute('''
        SELECT m.*, COALESCE(ml.id,0) as leido
        FROM mensajes_canal m
        LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=m.id AND ml.usuario_tipo=? AND ml.usuario_id=?
        WHERE m.canal_id=? AND m.eliminado=0 ORDER BY m.id ASC''', (tipo, uid, cid)).fetchall()
    result = [dict(r) for r in mensajes]
    _enriquecer_mensajes_batch(conn, result)
    conn.close()
    return jsonify(result)


@channels_bp.route('/<slug>/api/canales/<int:cid>/mensajes/nuevos')
def api_canales_mensajes_nuevos(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    ultimo_id = request.args.get('ultimo_id', 0, type=int)
    conn = fa.conectar(slug)
    canal = conn.execute('SELECT * FROM canales WHERE id=? AND activo=1', (cid,)).fetchone()
    if not canal:
        conn.close()
        return jsonify({'ok': False, 'error': 'Canal no encontrado'})
    if tipo != 'rector':
        miembro = conn.execute('SELECT 1 FROM canal_miembros WHERE canal_id=? AND usuario_tipo=? AND usuario_id=?',
                              (cid, tipo, uid)).fetchone()
        if not miembro:
            conn.close()
            return jsonify({'ok': False, 'error': 'No eres miembro'})
    mensajes = conn.execute('''
        SELECT m.*, COALESCE(ml.id,0) as leido
        FROM mensajes_canal m
        LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=m.id AND ml.usuario_tipo=? AND ml.usuario_id=?
        WHERE m.canal_id=? AND m.id > ? AND m.eliminado=0 ORDER BY m.id ASC''',
        (tipo, uid, cid, ultimo_id)).fetchall()
    result = [dict(r) for r in mensajes]
    _enriquecer_mensajes_batch(conn, result)
    conn.close()
    return jsonify({'ok': True, 'mensajes': result})


@channels_bp.route('/<slug>/api/canales/<int:cid>/enviar', methods=['POST'])
def api_canales_enviar(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'})
    mensaje = request.form.get('mensaje', '').strip()
    responde_a = request.form.get('responde_a', type=int)
    tiene_archivos = 0
    conn = fa.conectar(slug)
    canal = conn.execute('SELECT * FROM canales WHERE id=? AND activo=1', (cid,)).fetchone()
    if not canal:
        conn.close()
        return jsonify({'ok': False, 'error': 'Canal no encontrado'})
    if tipo != 'rector':
        miembro = conn.execute('SELECT 1 FROM canal_miembros WHERE canal_id=? AND usuario_tipo=? AND usuario_id=?',
                              (cid, tipo, uid)).fetchone()
        if not miembro:
            conn.close()
            return jsonify({'ok': False, 'error': 'No eres miembro'})
    mid = conn.execute(
        'INSERT INTO mensajes_canal (canal_id,usuario_tipo,usuario_id,mensaje,responde_a,tiene_archivos) VALUES (?,?,?,?,?,?)',
        (cid, tipo, uid, mensaje, responde_a, tiene_archivos)).lastrowid
    archivos_subidos = []
    if request.files:
        for key in request.files:
            f = request.files[key]
            if f and f.filename:
                from app.services.file_service import guardar_archivo_mensaje
                fid, err = guardar_archivo_mensaje(slug, cid, f, tipo, uid, fa.app.root_path)
                if fid:
                    conn.execute('UPDATE mensajes_archivos SET mensaje_id=? WHERE id=?', (mid, fid))
                    archivos_subidos.append(fid)
                    tiene_archivos = 1
    if tiene_archivos:
        conn.execute('UPDATE mensajes_canal SET tiene_archivos=1 WHERE id=?', (mid,))
    conn.execute('INSERT OR REPLACE INTO canal_actividad (canal_id, usuario_tipo, usuario_id, estado, ultima_vista) VALUES (?,?,?,?,?)',
                (cid, tipo, uid, 'online', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'mensaje_id': mid, 'archivos': archivos_subidos})


@channels_bp.route('/<slug>/api/canales/<int:cid>/leer', methods=['POST'])
def api_canales_leer(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'Error CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False})
    conn = fa.conectar(slug)
    mids = [r['id'] for r in conn.execute('SELECT id FROM mensajes_canal WHERE canal_id=?', (cid,)).fetchall()]
    if mids:
        ph = ','.join('?' * len(mids))
        conn.execute(f'INSERT OR IGNORE INTO mensajes_leidos (mensaje_id,usuario_tipo,usuario_id) SELECT id,?,? FROM mensajes_canal WHERE canal_id=? AND id IN ({ph})',
                    (tipo, uid, cid) + tuple(mids))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@channels_bp.route('/<slug>/api/canales/<int:cid>/reaccionar', methods=['POST'])
def api_canales_reaccionar(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    mensaje_id = request.form.get('mensaje_id', type=int)
    reaccion = request.form.get('reaccion', '').strip()
    if not mensaje_id or reaccion not in ('👍', '✅', '❓', '📌', '❤'):
        return jsonify({'ok': False, 'error': 'Reacción inválida'}), 400
    conn = fa.conectar(slug)
    existing = conn.execute(
        'SELECT id FROM mensajes_reacciones WHERE mensaje_id=? AND usuario_tipo=? AND usuario_id=? AND reaccion=?',
        (mensaje_id, tipo, uid, reaccion)).fetchone()
    if existing:
        conn.execute('DELETE FROM mensajes_reacciones WHERE id=?', (existing['id'],))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'activo': False})
    conn.execute('INSERT OR IGNORE INTO mensajes_reacciones (mensaje_id,usuario_tipo,usuario_id,reaccion) VALUES (?,?,?,?)',
                (mensaje_id, tipo, uid, reaccion))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'activo': True})


@channels_bp.route('/<slug>/api/canales/<int:cid>/fijar', methods=['POST'])
def api_canales_fijar(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    mensaje_id = request.form.get('mensaje_id', type=int)
    if not mensaje_id:
        return jsonify({'ok': False, 'error': 'mensaje_id requerido'}), 400
    conn = fa.conectar(slug)
    existing = conn.execute('SELECT id FROM mensajes_fijados WHERE canal_id=? AND mensaje_id=?',
                           (cid, mensaje_id)).fetchone()
    if existing:
        conn.execute('DELETE FROM mensajes_fijados WHERE id=?', (existing['id'],))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'fijado': False})
    conn.execute('INSERT INTO mensajes_fijados (canal_id,mensaje_id,fijado_por_tipo,fijado_por_id) VALUES (?,?,?,?)',
                (cid, mensaje_id, tipo, uid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'fijado': True})


@channels_bp.route('/<slug>/api/canales/<int:cid>/fijados')
def api_canales_fijados(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify([])
    conn = fa.conectar(slug)
    rows = conn.execute(
        '''SELECT m.id, m.mensaje, m.usuario_tipo, m.usuario_id, m.fecha, m.editado,
                  f.fecha as fijado_en, f.fijado_por_tipo, f.fijado_por_id
           FROM mensajes_fijados f
           JOIN mensajes_canal m ON m.id=f.mensaje_id
           WHERE f.canal_id=? AND m.eliminado=0
           ORDER BY f.id DESC''', (cid,)).fetchall()
    result = [dict(r) for r in rows]
    for m in result:
        m['autor_nombre'] = nombre_usuario_canal(conn, m['usuario_tipo'], m['usuario_id'])
    conn.close()
    return jsonify(result)


@channels_bp.route('/<slug>/api/canales/<int:cid>/biblioteca')
def api_canales_biblioteca(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({})
    conn = fa.conectar(slug)
    archivos = [dict(r) for r in conn.execute(
        'SELECT * FROM mensajes_archivos WHERE canal_id=? ORDER BY fecha DESC LIMIT 50', (cid,)).fetchall()]
    enlaces = [dict(r) for r in conn.execute(
        'SELECT * FROM canal_enlaces WHERE canal_id=? ORDER BY fecha DESC LIMIT 50', (cid,)).fetchall()]
    conn.close()
    return jsonify({'archivos': archivos, 'enlaces': enlaces})


@channels_bp.route('/<slug>/api/canales/<int:cid>/buscar')
def api_canales_buscar(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify([])
    q = request.args.get('q', '').strip()
    autor = request.args.get('autor', '').strip()
    desde = request.args.get('desde', '').strip()
    hasta = request.args.get('hasta', '').strip()
    conn = fa.conectar(slug)
    sql = 'SELECT m.* FROM mensajes_canal m WHERE m.canal_id=? AND m.eliminado=0'
    params = [cid]
    if q:
        sql += ' AND m.mensaje LIKE ?'
        params.append(f'%{q}%')
    if autor:
        sql += ' AND (SELECT nombre FROM profesores WHERE id=m.usuario_id AND m.usuario_tipo=\'profesor\') LIKE ?'
        params.append(f'%{autor}%')
    if desde:
        sql += ' AND m.fecha >= ?'
        params.append(desde)
    if hasta:
        sql += ' AND m.fecha <= ?'
        params.append(hasta + ' 23:59:59')
    sql += ' ORDER BY m.id DESC LIMIT 100'
    rows = conn.execute(sql, params).fetchall()
    result = [dict(r) for r in rows]
    _enriquecer_mensajes_batch(conn, result)
    conn.close()
    return jsonify(result)


@channels_bp.route('/<slug>/api/canales/<int:cid>/editar/<int:mid>', methods=['POST'])
def api_canales_editar(slug, cid, mid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    conn = fa.conectar(slug)
    msg = conn.execute('SELECT * FROM mensajes_canal WHERE id=? AND canal_id=?', (mid, cid)).fetchone()
    if not msg:
        conn.close()
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    if msg['usuario_tipo'] != tipo or msg['usuario_id'] != uid:
        conn.close()
        return jsonify({'ok': False, 'error': 'No puedes editar este mensaje'}), 403
    if msg['eliminado']:
        conn.close()
        return jsonify({'ok': False, 'error': 'Mensaje eliminado'}), 400
    try:
        creado = datetime.strptime(msg['fecha'], '%Y-%m-%d %H:%M:%S') if msg['fecha'] else datetime.min
    except (ValueError, TypeError):
        creado = datetime.min
    TIEMPO_EDICION_SEGUNDOS = 300
    if (datetime.now() - creado).total_seconds() > TIEMPO_EDICION_SEGUNDOS:
        conn.close()
        return jsonify({'ok': False, 'error': 'Tiempo de edición expirado'}), 400
    nuevo_texto = request.form.get('mensaje', '').strip()
    if not nuevo_texto:
        conn.close()
        return jsonify({'ok': False, 'error': 'Mensaje vacío'}), 400
    viejo_texto = msg['mensaje']
    conn.execute('UPDATE mensajes_canal SET mensaje=?, editado=editado+1, editado_en=? WHERE id=?',
                (nuevo_texto, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), mid))
    conn.commit()
    fa.audit_log(slug, uid, 'update', 'mensajes_canal', mid,
                 valor_anterior={'mensaje': viejo_texto},
                 valor_nuevo={'mensaje': nuevo_texto})
    conn.close()
    return jsonify({'ok': True})


@channels_bp.route('/<slug>/api/canales/<int:cid>/eliminar/<int:mid>', methods=['DELETE', 'POST'])
def api_canales_eliminar(slug, cid, mid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    conn = fa.conectar(slug)
    msg = conn.execute('SELECT * FROM mensajes_canal WHERE id=? AND canal_id=?', (mid, cid)).fetchone()
    if not msg:
        conn.close()
        return jsonify({'ok': False, 'error': 'No encontrado'}), 404
    if msg['usuario_tipo'] != tipo or msg['usuario_id'] != uid:
        conn.close()
        return jsonify({'ok': False, 'error': 'No puedes eliminar este mensaje'}), 403
    conn.execute('UPDATE mensajes_canal SET eliminado=1 WHERE id=?', (mid,))
    conn.commit()
    fa.audit_log(slug, uid, 'delete', 'mensajes_canal', mid,
                 valor_anterior={'mensaje': msg['mensaje'][:200]})
    conn.close()
    return jsonify({'ok': True})


@channels_bp.route('/<slug>/api/canales/<int:cid>/lecturas')
def api_canales_lecturas(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify([])
    conn = fa.conectar(slug)
    miembros = conn.execute(
        'SELECT usuario_tipo, usuario_id FROM canal_miembros WHERE canal_id=?', (cid,)).fetchall()
    total_msg = conn.execute(
        'SELECT COUNT(*) as c FROM mensajes_canal WHERE canal_id=? AND eliminado=0', (cid,)).fetchone()['c']
    ult_vistas = {}
    for row in conn.execute(
        'SELECT usuario_tipo, usuario_id, ultima_vista FROM canal_actividad WHERE canal_id=?',
        (cid,)).fetchall():
        ult_vistas[f"{row['usuario_tipo']}_{row['usuario_id']}"] = row['ultima_vista']
    leidos_por_miembro = {}
    for row in conn.execute(
        '''SELECT ml.usuario_tipo, ml.usuario_id, COUNT(DISTINCT mc.id) as c
           FROM mensajes_leidos ml
           JOIN mensajes_canal mc ON ml.mensaje_id=mc.id
           WHERE mc.canal_id=? AND mc.eliminado=0
           GROUP BY ml.usuario_tipo, ml.usuario_id''',
        (cid,)).fetchall():
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
    table_map = {'profesor': 'profesores', 'estudiante': 'alumnos', 'rector': 'rectores', 'directora': 'directoras'}
    for t, ids in tipo_ids.items():
        if not ids:
            continue
        ph2 = ','.join('?' * len(ids))
        rows = conn.execute(f'SELECT id, nombre FROM {table_map[t]} WHERE id IN ({ph2})', list(ids)).fetchall()
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
    conn.close()
    return jsonify(result)


@channels_bp.route('/<slug>/api/canales/<int:cid>/escribiendo', methods=['POST'])
def api_canales_escribiendo(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False})
    conn = fa.conectar(slug)
    conn.execute('INSERT OR REPLACE INTO canal_actividad (canal_id,usuario_tipo,usuario_id,estado,ultima_vista) VALUES (?,?,?,?,?)',
                (cid, tipo, uid, 'typing', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@channels_bp.route('/<slug>/api/canales/<int:cid>/actividad')
def api_canales_actividad(slug, cid):
    fa = _fa()
    fa.require_colegio(slug)
    conn = fa.conectar(slug)
    rows = conn.execute(
        'SELECT ca.* FROM canal_actividad ca WHERE ca.canal_id=?', (cid,)).fetchall()
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
    conn.close()
    return jsonify(result)


@channels_bp.route('/<slug>/api/canales/<int:cid>/enlaces', methods=['POST'])
def api_canales_guardar_enlace(slug, cid):
    fa = _fa()
    if not fa.validar_csrf():
        return jsonify({'ok': False, 'error': 'CSRF'}), 403
    fa.require_colegio(slug)
    tipo, uid = fa.get_usuario_actual(slug)
    if not tipo:
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    url = request.form.get('url', '').strip()
    titulo = request.form.get('titulo', '').strip()
    if not url:
        return jsonify({'ok': False, 'error': 'URL requerida'}), 400
    conn = fa.conectar(slug)
    conn.execute('INSERT INTO canal_enlaces (canal_id,titulo,url,agregado_por_tipo,agregado_por_id) VALUES (?,?,?,?,?)',
                (cid, titulo or url, url, tipo, uid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@channels_bp.route('/<slug>/api/comunicaciones')
def api_comunicaciones(slug):
    fa = _fa()
    fa.require_colegio(slug)
    prof = fa.get_profesor(slug)
    if prof:
        return jsonify(fa.comunicaciones_pendientes(slug, 'profesor', prof['id']))
    aid = session.get(f'alumno_id_{slug}')
    if aid:
        return jsonify(fa.comunicaciones_pendientes(slug, 'estudiante', aid))
    return jsonify([])


@channels_bp.route('/<slug>/api/comunicaciones/count')
def api_comunicaciones_count(slug):
    fa = _fa()
    fa.require_colegio(slug)
    prof = fa.get_profesor(slug)
    if prof:
        return jsonify({'pendientes': len(fa.comunicaciones_pendientes(slug, 'profesor', prof['id']))})
    aid = session.get(f'alumno_id_{slug}')
    if aid:
        return jsonify({'pendientes': len(fa.comunicaciones_pendientes(slug, 'estudiante', aid))})
    return jsonify({'pendientes': 0})
