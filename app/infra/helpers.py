from flask import session, g
from app.infra.database import conectar, get_colegio
from app.exceptions import ForbiddenError, NotFoundError


def get_profesor(slug):
    cache_key = f'_prof_{slug}'
    if hasattr(g, cache_key):
        return getattr(g, cache_key)
    pid = session.get(f'profesor_id_{slug}')
    if not pid:
        setattr(g, cache_key, None)
        return None
    conn = conectar(slug)
    p = conn.execute('SELECT * FROM profesores WHERE id=? AND activo=1', (pid,)).fetchone()
    conn.close()
    if not p:
        session.pop(f'profesor_id_{slug}', None)
        session.pop(f'rol_{slug}', None)
    setattr(g, cache_key, p)
    return p


def get_directora(slug):
    cache_key = f'_direc_{slug}'
    if hasattr(g, cache_key):
        return getattr(g, cache_key)
    did = session.get(f'directora_id_{slug}')
    if not did:
        setattr(g, cache_key, None)
        return None
    conn = conectar(slug)
    d = conn.execute('SELECT * FROM directoras WHERE id=? AND activo=1', (did,)).fetchone()
    conn.close()
    if not d:
        session.pop(f'directora_id_{slug}', None)
    setattr(g, cache_key, d)
    return d


def get_rector(slug):
    cache_key = f'_rector_{slug}'
    if hasattr(g, cache_key):
        return getattr(g, cache_key)
    rid = session.get(f'rector_id_{slug}')
    if not rid:
        setattr(g, cache_key, None)
        return None
    conn = conectar(slug)
    r = conn.execute('SELECT * FROM rectores WHERE id=? AND activo=1', (rid,)).fetchone()
    conn.close()
    if not r:
        session.pop(f'rector_id_{slug}', None)
    setattr(g, cache_key, r)
    return r


def get_usuario_actual(slug):
    prof = get_profesor(slug)
    if prof:
        return ('profesor', prof['id'])
    aid = session.get(f'alumno_id_{slug}')
    if aid:
        return ('estudiante', aid)
    direc = get_directora(slug)
    if direc:
        return ('directora', direc['id'])
    rector = get_rector(slug)
    if rector:
        return ('rector', rector['id'])
    return (None, None)


def require_colegio(slug):
    colegio = get_colegio(slug)
    if not colegio:
        raise NotFoundError('Colegio', slug)
    if not colegio['activo']:
        raise ForbiddenError('El colegio está inactivo')
    return colegio


def get_sesion_jornada_materia(slug):
    return (session.get(f'jornada_{slug}'), session.get(f'materia_{slug}'))


def get_materias_profesor(slug, pid):
    conn = conectar(slug)
    rows = conn.execute(
        'SELECT materia, jornada FROM asignaciones_materia WHERE profesor_id=? ORDER BY jornada, materia',
        (pid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cursos_profesor(slug, pid, materia, jornada):
    conn = conectar(slug)
    rows = conn.execute(
        'SELECT curso FROM asignaciones_curso WHERE profesor_id=? AND materia=? AND jornada=? ORDER BY curso',
        (pid, materia, jornada)
    ).fetchall()
    conn.close()
    return [r['curso'] for r in rows]


def get_cursos_cache(slug, jornada=None):
    from app.infra.database import _cache_get, _cache_set, conectar
    key = f'cursos_{slug}_{jornada or "all"}'
    cached = _cache_get(key)
    if cached:
        return cached
    conn = conectar(slug)
    if jornada:
        rows = conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 AND jornada=? ORDER BY curso', (jornada,)).fetchall()
    else:
        rows = conn.execute('SELECT DISTINCT curso FROM alumnos WHERE activo=1 ORDER BY curso').fetchall()
    conn.close()
    val = [r['curso'] for r in rows]
    _cache_set(key, val, ttl=60)
    return val


def get_materias_cache(slug, jornada=None):
    from app.infra.database import _cache_get, _cache_set, conectar
    key = f'mats_{slug}_{jornada or "all"}'
    cached = _cache_get(key)
    if cached:
        return cached
    conn = conectar(slug)
    if jornada:
        rows = conn.execute('SELECT DISTINCT materia FROM asignaciones_materia WHERE jornada=? ORDER BY materia', (jornada,)).fetchall()
    else:
        rows = conn.execute('SELECT DISTINCT materia FROM asignaciones_materia ORDER BY materia').fetchall()
    conn.close()
    val = [r['materia'] for r in rows]
    _cache_set(key, val, ttl=60)
    return val


def get_jornadas_cache(slug):
    from app.infra.database import _cache_get, _cache_set, conectar
    key = f'jorn_{slug}'
    cached = _cache_get(key)
    if cached:
        return cached
    conn = conectar(slug)
    rows = conn.execute('SELECT DISTINCT jornada FROM alumnos WHERE activo=1 ORDER BY jornada').fetchall()
    conn.close()
    val = [r['jornada'] for r in rows]
    _cache_set(key, val, ttl=60)
    return val
