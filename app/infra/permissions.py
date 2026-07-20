from functools import wraps
from flask import redirect, url_for
from app.infra.database import conectar
from app.infra.helpers import get_usuario_actual
from app.exceptions import ForbiddenError, ValidationError


def obtener_roles_usuario(slug, usuario_id):
    conn = conectar(slug)
    rows = conn.execute('''
        SELECT r.codigo, ri.nombre as rol_nombre, ri.jerarquia,
               ur.entidad_tipo, ur.entidad_id
        FROM usuarios_roles ur
        JOIN roles_instancia ri ON ri.id = ur.rol_id
        JOIN roles_base r ON r.codigo = ri.codigo
        WHERE ur.usuario_id = ? AND ri.activo = 1
    ''', (usuario_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


PERMISOS_POR_CODIGO = {
    'admin':     ['*'],
    'rector':    ['*'],
    'authority': ['people.teachers.view', 'people.students.view',
        'structure.courses.manage', 'structure.subjects.manage',
        'academic.grades.view', 'academic.grades.write', 'academic.grades.approve',
        'academic.grades.history', 'academico.periodos.cerrar',
        'academico.periodos.abrir', 'academico.notas.aprobar',
        'academico.notas.modificar_cerrado',
        'academic.attendance.view',
        'academic.observations.view', 'academic.observations.write',
        'academic.evaluations.create', 'academic.evaluations.edit',
        'communication.communicados.view', 'communication.communicados.create',
        'communication.channels.read', 'communication.channels.send',
        'reports.grades', 'reports.attendance', 'reports.export',
        'audit.log.view'],
    'teacher': ['people.students.view',
        'academic.grades.view', 'academic.grades.write',
        'academic.attendance.view', 'academic.attendance.write',
        'academic.observations.view', 'academic.observations.write',
        'academic.evaluations.create', 'academic.evaluations.edit',
        'academic.activities.create', 'academic.activities.edit',
        'communication.communicados.view',
        'communication.channels.read', 'communication.channels.send'],
    'student': ['academic.grades.view', 'academic.attendance.view',
        'communication.communicados.view',
        'communication.channels.read', 'communication.channels.send'],
    'guardian': ['academic.grades.view', 'academic.attendance.view',
        'communication.communicados.view',
        'communication.channels.read'],
}


NIVELES_ROL = {'admin': 0, 'rector': 1, 'authority': 2, 'teacher': 3, 'student': 4, 'guardian': 5}


def _permisos_para_rol(codigo):
    permisos = set()
    nivel = NIVELES_ROL.get(codigo, 99)
    for rc, rn in NIVELES_ROL.items():
        if rn >= nivel:
            permisos.update(PERMISOS_POR_CODIGO.get(rc, []))
    return list(permisos)


def tiene_permiso(slug, usuario_id, permiso, entidad_tipo=None, entidad_id=None):
    roles = obtener_roles_usuario(slug, usuario_id)
    for rol in roles:
        if rol['codigo'] in ('admin', 'rector'):
            return True
        if permiso not in _permisos_para_rol(rol['codigo']) and '*' not in _permisos_para_rol(rol['codigo']):
            continue
        if entidad_tipo and rol['entidad_tipo']:
            if rol['entidad_tipo'] != entidad_tipo or rol['entidad_id'] != entidad_id:
                continue
        return True
    return False


def requiere_permiso(permiso, obtener_entidad=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            slug = kwargs.get('slug')
            if not slug:
                raise ValidationError('Slug no proporcionado')
            usuario_tipo, usuario_id = get_usuario_actual(slug)
            if not usuario_id:
                return redirect(url_for('auth.login', slug=slug))
            if obtener_entidad:
                e_tipo, e_id = obtener_entidad(kwargs)
            else:
                e_tipo, e_id = None, None
            if not tiene_permiso(slug, usuario_id, permiso, e_tipo, e_id):
                raise ForbiddenError()
            return f(*args, **kwargs)
        return wrapper
    return decorator
