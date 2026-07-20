def get_canales_para_rector(conn, rector_id):
    return conn.execute('''
        SELECT c.*,
            (SELECT mensaje FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_mensaje,
            (SELECT usuario_tipo FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_tipo,
            (SELECT usuario_id FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_id,
            (SELECT fecha FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultima_fecha,
            (SELECT COUNT(*) FROM mensajes_canal mc
             LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=mc.id AND ml.usuario_tipo='rector' AND ml.usuario_id=?
             WHERE mc.canal_id=c.id AND ml.id IS NULL) as no_leidos
        FROM canales c WHERE c.activo=1 ORDER BY ultima_fecha DESC''', (rector_id,)).fetchall()


def get_canales_para_usuario(conn, usuario_tipo, usuario_id):
    return conn.execute('''
        SELECT c.*,
            cm.ultima_vista,
            (SELECT mensaje FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_mensaje,
            (SELECT usuario_tipo FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_tipo,
            (SELECT usuario_id FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultimo_autor_id,
            (SELECT fecha FROM mensajes_canal WHERE canal_id=c.id ORDER BY id DESC LIMIT 1) as ultima_fecha,
            (SELECT COUNT(*) FROM mensajes_canal mc
             LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=mc.id AND ml.usuario_tipo=? AND ml.usuario_id=?
             WHERE mc.canal_id=c.id AND ml.id IS NULL) as no_leidos
        FROM canales c
        JOIN canal_miembros cm2 ON cm2.canal_id=c.id AND cm2.usuario_tipo=? AND cm2.usuario_id=?
        LEFT JOIN canal_actividad cm ON cm.canal_id=c.id AND cm.usuario_tipo=? AND cm.usuario_id=?
        WHERE c.activo=1 ORDER BY ultima_fecha DESC''',
        (usuario_tipo, usuario_id, usuario_tipo, usuario_id, usuario_tipo, usuario_id)).fetchall()


def get_canal(conn, cid):
    return conn.execute('SELECT * FROM canales WHERE id=? AND activo=1', (cid,)).fetchone()


def es_miembro(conn, cid, tipo, uid):
    return conn.execute(
        'SELECT 1 FROM canal_miembros WHERE canal_id=? AND usuario_tipo=? AND usuario_id=?',
        (cid, tipo, uid)).fetchone()


def get_mensajes_canal(conn, cid, tipo, uid):
    return conn.execute('''
        SELECT m.*, COALESCE(ml.id,0) as leido
        FROM mensajes_canal m
        LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=m.id AND ml.usuario_tipo=? AND ml.usuario_id=?
        WHERE m.canal_id=? AND m.eliminado=0 ORDER BY m.id ASC''', (tipo, uid, cid)).fetchall()


def get_mensajes_nuevos(conn, cid, tipo, uid, ultimo_id):
    return conn.execute('''
        SELECT m.*, COALESCE(ml.id,0) as leido
        FROM mensajes_canal m
        LEFT JOIN mensajes_leidos ml ON ml.mensaje_id=m.id AND ml.usuario_tipo=? AND ml.usuario_id=?
        WHERE m.canal_id=? AND m.id > ? AND m.eliminado=0 ORDER BY m.id ASC''',
        (tipo, uid, cid, ultimo_id)).fetchall()


def insertar_mensaje(conn, cid, tipo, uid, mensaje, responde_a, tiene_archivos):
    return conn.execute(
        'INSERT INTO mensajes_canal (canal_id,usuario_tipo,usuario_id,mensaje,responde_a,tiene_archivos) VALUES (?,?,?,?,?,?)',
        (cid, tipo, uid, mensaje, responde_a, tiene_archivos)).lastrowid


def actualizar_tiene_archivos(conn, mid):
    conn.execute('UPDATE mensajes_canal SET tiene_archivos=1 WHERE id=?', (mid,))


def actualizar_actividad(conn, cid, tipo, uid, estado, ahora):
    conn.execute(
        'INSERT OR REPLACE INTO canal_actividad (canal_id, usuario_tipo, usuario_id, estado, ultima_vista) VALUES (?,?,?,?,?)',
        (cid, tipo, uid, estado, ahora))


def marcar_mensajes_leidos(conn, cid, tipo, uid):
    mids = [r['id'] for r in conn.execute(
        'SELECT id FROM mensajes_canal WHERE canal_id=?', (cid,)).fetchall()]
    if mids:
        ph = ','.join('?' * len(mids))
        conn.execute(
            f'INSERT OR IGNORE INTO mensajes_leidos (mensaje_id,usuario_tipo,usuario_id) SELECT id,?,? FROM mensajes_canal WHERE canal_id=? AND id IN ({ph})',
            (tipo, uid, cid) + tuple(mids))


def get_mensaje(conn, mid, cid):
    return conn.execute(
        'SELECT * FROM mensajes_canal WHERE id=? AND canal_id=?', (mid, cid)).fetchone()


def actualizar_mensaje(conn, mid, nuevo_texto, ahora):
    conn.execute(
        'UPDATE mensajes_canal SET mensaje=?, editado=editado+1, editado_en=? WHERE id=?',
        (nuevo_texto, ahora, mid))


def soft_delete_mensaje(conn, mid):
    conn.execute('UPDATE mensajes_canal SET eliminado=1 WHERE id=?', (mid,))


def crear_reaccion(conn, mensaje_id, tipo, uid, reaccion):
    conn.execute(
        'INSERT OR IGNORE INTO mensajes_reacciones (mensaje_id,usuario_tipo,usuario_id,reaccion) VALUES (?,?,?,?)',
        (mensaje_id, tipo, uid, reaccion))


def eliminar_reaccion(conn, rid):
    conn.execute('DELETE FROM mensajes_reacciones WHERE id=?', (rid,))


def get_reaccion_existente(conn, mensaje_id, tipo, uid, reaccion):
    return conn.execute(
        'SELECT id FROM mensajes_reacciones WHERE mensaje_id=? AND usuario_tipo=? AND usuario_id=? AND reaccion=?',
        (mensaje_id, tipo, uid, reaccion)).fetchone()


def get_mensaje_fijado(conn, cid, mensaje_id):
    return conn.execute(
        'SELECT id FROM mensajes_fijados WHERE canal_id=? AND mensaje_id=?',
        (cid, mensaje_id)).fetchone()


def insertar_fijado(conn, cid, mensaje_id, tipo, uid):
    conn.execute(
        'INSERT INTO mensajes_fijados (canal_id,mensaje_id,fijado_por_tipo,fijado_por_id) VALUES (?,?,?,?)',
        (cid, mensaje_id, tipo, uid))


def eliminar_fijado(conn, fid):
    conn.execute('DELETE FROM mensajes_fijados WHERE id=?', (fid,))


def get_mensajes_fijados(conn, cid):
    return conn.execute(
        '''SELECT m.id, m.mensaje, m.usuario_tipo, m.usuario_id, m.fecha, m.editado,
                  f.fecha as fijado_en, f.fijado_por_tipo, f.fijado_por_id
           FROM mensajes_fijados f
           JOIN mensajes_canal m ON m.id=f.mensaje_id
           WHERE f.canal_id=? AND m.eliminado=0
           ORDER BY f.id DESC''', (cid,)).fetchall()


def get_archivos_biblioteca(conn, cid, limite=50):
    return conn.execute(
        'SELECT * FROM mensajes_archivos WHERE canal_id=? ORDER BY fecha DESC LIMIT ?',
        (cid, limite)).fetchall()


def get_enlaces_biblioteca(conn, cid, limite=50):
    return conn.execute(
        'SELECT * FROM canal_enlaces WHERE canal_id=? ORDER BY fecha DESC LIMIT ?',
        (cid, limite)).fetchall()


def buscar_mensajes(conn, cid, q, autor, desde, hasta, limite=100):
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
    sql += ' ORDER BY m.id DESC LIMIT ?'
    params.append(limite)
    return conn.execute(sql, params).fetchall()


def get_miembros_canal(conn, cid):
    return conn.execute(
        'SELECT usuario_tipo, usuario_id FROM canal_miembros WHERE canal_id=?', (cid,)).fetchall()


def get_total_mensajes(conn, cid):
    return conn.execute(
        'SELECT COUNT(*) as c FROM mensajes_canal WHERE canal_id=? AND eliminado=0', (cid,)).fetchone()['c']


def get_actividad_canal(conn, cid):
    return conn.execute(
        'SELECT usuario_tipo, usuario_id, ultima_vista FROM canal_actividad WHERE canal_id=?',
        (cid,)).fetchall()


def get_lecturas_por_miembro(conn, cid):
    return conn.execute(
        '''SELECT ml.usuario_tipo, ml.usuario_id, COUNT(DISTINCT mc.id) as c
           FROM mensajes_leidos ml
           JOIN mensajes_canal mc ON ml.mensaje_id=mc.id
           WHERE mc.canal_id=? AND mc.eliminado=0
           GROUP BY ml.usuario_tipo, ml.usuario_id''',
        (cid,)).fetchall()


def get_actividad_estados(conn, cid):
    return conn.execute(
        'SELECT ca.* FROM canal_actividad ca WHERE ca.canal_id=?', (cid,)).fetchall()


def set_estado_actividad(conn, cid, tipo, uid, estado, ahora):
    conn.execute(
        'INSERT OR REPLACE INTO canal_actividad (canal_id,usuario_tipo,usuario_id,estado,ultima_vista) VALUES (?,?,?,?,?)',
        (cid, tipo, uid, estado, ahora))


def guardar_enlace(conn, cid, url, titulo, tipo, uid):
    conn.execute(
        'INSERT INTO canal_enlaces (canal_id,titulo,url,agregado_por_tipo,agregado_por_id) VALUES (?,?,?,?,?)',
        (cid, titulo or url, url, tipo, uid))
