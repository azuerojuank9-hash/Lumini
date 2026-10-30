def get_notificaciones(conn, usuario_tipo, usuario_id, limite=100):
    return conn.execute(
        'SELECT * FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? ORDER BY fecha_creacion DESC LIMIT ?',
        (usuario_tipo, usuario_id, limite)).fetchall()


def marcar_notificacion_leida(conn, nid, usuario_tipo, usuario_id):
    conn.execute('UPDATE notificaciones SET leida=1 WHERE id=? AND usuario_tipo=? AND usuario_id=?',
                 (nid, usuario_tipo, usuario_id))


def get_notificaciones_no_leidas_count(conn, usuario_tipo, usuario_id):
    return conn.execute(
        'SELECT COUNT(*) as c FROM notificaciones WHERE usuario_tipo=? AND usuario_id=? AND leida=0',
        (usuario_tipo, usuario_id)).fetchone()['c']


def get_columna_leido_exists(conn):
    cols = [r[1] for r in conn.execute('PRAGMA table_info(comunicaciones_leidas)').fetchall()]
    return 'leido' in cols


def add_columna_leido(conn):
    conn.execute('ALTER TABLE comunicaciones_leidas ADD COLUMN leido INTEGER DEFAULT 0')


def get_comunicacion_leida(conn, cid, usuario_tipo, usuario_id):
    return conn.execute(
        'SELECT 1 FROM comunicaciones_leidas WHERE comunicacion_id=? AND usuario_tipo=? AND usuario_id=?',
        (cid, usuario_tipo, usuario_id)).fetchone()


def marcar_comunicacion_leida(conn, cid, usuario_tipo, usuario_id):
    conn.execute(
        '''UPDATE comunicaciones_leidas SET leido=1, fecha_lectura=datetime('now','localtime')
           WHERE comunicacion_id=? AND usuario_tipo=? AND usuario_id=?''',
        (cid, usuario_tipo, usuario_id))


def insertar_comunicacion_leida(conn, cid, usuario_tipo, usuario_id):
    conn.execute(
        '''INSERT INTO comunicaciones_leidas (comunicacion_id,usuario_tipo,usuario_id,leido,fecha_lectura)
           VALUES (?,?,?,1,datetime('now','localtime'))''',
        (cid, usuario_tipo, usuario_id))
