"""User repository — SQL queries for users across all roles.

No business logic here, only data access.
"""

from app.models.schema import conectar, conectar_master


def find_profesor_by_username(slug, usuario):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM profesores WHERE usuario=? AND activo=1',
            (usuario,)
        ).fetchone()
    finally:
        conn.close()


def find_profesor_by_id(slug, pid):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM profesores WHERE id=? AND activo=1',
            (pid,)
        ).fetchone()
    finally:
        conn.close()


def find_rector_by_username(slug, usuario):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM rectores WHERE usuario=? AND activo=1',
            (usuario,)
        ).fetchone()
    finally:
        conn.close()


def find_rector_by_id(slug, rid):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM rectores WHERE id=? AND activo=1',
            (rid,)
        ).fetchone()
    finally:
        conn.close()


def find_directora_by_username(slug, usuario):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM directoras WHERE usuario=? AND activo=1',
            (usuario,)
        ).fetchone()
    finally:
        conn.close()


def find_directora_by_id(slug, did):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT * FROM directoras WHERE id=? AND activo=1',
            (did,)
        ).fetchone()
    finally:
        conn.close()


def find_alumno_by_nombre(slug, nombre, jornada=None):
    conn = conectar(slug)
    try:
        if jornada:
            return conn.execute(
                'SELECT * FROM alumnos WHERE LOWER(nombre)=? AND jornada=? AND activo=1',
                (nombre, jornada)
            ).fetchone()
        return conn.execute(
            'SELECT * FROM alumnos WHERE LOWER(nombre)=? AND activo=1',
            (nombre,)
        ).fetchone()
    finally:
        conn.close()


def username_exists_profesor(slug, usuario):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT 1 FROM profesores WHERE usuario=?', (usuario,)
        ).fetchone() is not None
    finally:
        conn.close()


def username_exists_rector(slug, usuario):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT 1 FROM rectores WHERE usuario=?', (usuario,)
        ).fetchone() is not None
    finally:
        conn.close()


def username_exists_directora(slug, usuario):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT 1 FROM directoras WHERE usuario=?', (usuario,)
        ).fetchone() is not None
    finally:
        conn.close()


def create_profesor(slug, nombre, usuario, password_hash, email, pregunta, respuesta):
    conn = conectar(slug)
    try:
        cur = conn.execute(
            '''INSERT INTO profesores
               (nombre,usuario,password,email,pregunta_secreta,respuesta_secreta)
               VALUES (?,?,?,?,?,?)''',
            (nombre, usuario, password_hash, email, pregunta, respuesta)
        )
        pid = cur.lastrowid
        conn.commit()
        return pid
    finally:
        conn.close()


def create_rector(slug, nombre, usuario, password_hash, jornada, email, pregunta, respuesta):
    conn = conectar(slug)
    try:
        conn.execute(
            '''INSERT INTO rectores
               (nombre, usuario, password, jornada, email, pregunta_secreta, respuesta_secreta)
               VALUES (?,?,?,?,?,?,?)''',
            (nombre, usuario, password_hash, jornada, email, pregunta, respuesta)
        )
        conn.commit()
    finally:
        conn.close()


def create_directora(slug, nombre, usuario, password_hash, curso, jornada, email, pregunta, respuesta):
    conn = conectar(slug)
    try:
        conn.execute(
            '''INSERT INTO directoras
               (nombre,usuario,password,curso,jornada,email,pregunta_secreta,respuesta_secreta)
               VALUES (?,?,?,?,?,?,?,?)''',
            (nombre, usuario, password_hash, curso, jornada, email, pregunta, respuesta)
        )
        conn.commit()
    finally:
        conn.close()


def update_profesor_password(slug, pid, password_hash):
    conn = conectar(slug)
    try:
        conn.execute(
            'UPDATE profesores SET password=? WHERE id=?',
            (password_hash, pid)
        )
        conn.commit()
    finally:
        conn.close()


def update_rector_password(slug, rid, password_hash):
    conn = conectar(slug)
    try:
        conn.execute(
            'UPDATE rectores SET password=? WHERE id=?',
            (password_hash, rid)
        )
        conn.commit()
    finally:
        conn.close()


def update_directora_password(slug, did, password_hash):
    conn = conectar(slug)
    try:
        conn.execute(
            'UPDATE directoras SET password=? WHERE id=?',
            (password_hash, did)
        )
        conn.commit()
    finally:
        conn.close()


def get_all_colegios():
    conn = conectar_master()
    try:
        return conn.execute(
            'SELECT * FROM colegios ORDER BY creado DESC'
        ).fetchall()
    finally:
        conn.close()


def create_colegio(slug, nombre, logo, num_periodos, vencimiento, codigo, pri_col, sec_col):
    conn = conectar_master()
    try:
        conn.execute(
            '''INSERT INTO colegios
               (slug,nombre,logo,num_periodos,vencimiento,codigo_registro,
                codigo_profesores,codigo_directoras,codigo_rectores,primary_color,secondary_color)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (slug, nombre, logo, num_periodos, vencimiento, codigo, codigo, codigo, codigo, pri_col, sec_col)
        )
        conn.commit()
    finally:
        conn.close()


def find_colegio_by_slug(slug):
    conn = conectar_master()
    try:
        return conn.execute(
            'SELECT * FROM colegios WHERE slug=?', (slug,)
        ).fetchone()
    finally:
        conn.close()


def toggle_colegio_activo(slug):
    conn = conectar_master()
    try:
        actual = conn.execute(
            'SELECT activo FROM colegios WHERE slug=?', (slug,)
        ).fetchone()
        if actual:
            conn.execute(
                'UPDATE colegios SET activo=? WHERE slug=?',
                (0 if actual['activo'] else 1, slug)
            )
            conn.commit()
    finally:
        conn.close()


def update_colegio(slug, nombre, num_periodos, vencimiento, codigo, pri_col, sec_col):
    conn = conectar_master()
    try:
        conn.execute(
            '''UPDATE colegios SET nombre=?, num_periodos=?, vencimiento=?, codigo_registro=?,
               codigo_profesores=?, codigo_directoras=?, codigo_rectores=?, primary_color=?, secondary_color=?
               WHERE slug=?''',
            (nombre, num_periodos, vencimiento, codigo, codigo, codigo, codigo, pri_col, sec_col, slug)
        )
        conn.commit()
    finally:
        conn.close()


def delete_colegio(slug):
    conn = conectar_master()
    try:
        conn.execute('DELETE FROM colegios WHERE slug=?', (slug,))
        conn.commit()
    finally:
        conn.close()


def get_parent_by_email_pin(slug, email, pin):
    conn = conectar(slug)
    try:
        return conn.execute(
            'SELECT id, nombre, email FROM padres WHERE email=? AND pin=? AND activo=1',
            (email, pin)
        ).fetchone()
    finally:
        conn.close()


def get_children_for_parent(slug, padre_id):
    conn = conectar(slug)
    try:
        return conn.execute(
            '''SELECT a.id, a.nombre, a.curso, a.jornada
               FROM alumno_padre ap
               JOIN alumnos a ON a.id=ap.alumno_id
               WHERE ap.padre_id=?''',
            (padre_id,)
        ).fetchall()
    finally:
        conn.close()
