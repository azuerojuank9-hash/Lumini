def get_archivo(conn, fid):
    return conn.execute('SELECT * FROM mensajes_archivos WHERE id=?', (fid,)).fetchone()


def eliminar_archivo(conn, fid):
    conn.execute('DELETE FROM mensajes_archivos WHERE id=?', (fid,))


def get_max_tamano_archivo(conn, slug):
    cfg = conn.execute(
        'SELECT max_tamano_archivo FROM config_institucion WHERE slug=?', (slug,)).fetchone()
    return cfg['max_tamano_archivo'] if cfg else 10485760
