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
    """
    Sincroniza los destinatarios de un comunicado publicado.

    - Agrega destinatarios nuevos.
    - Retira destinatarios que ya no corresponden.
    - Conserva el estado de lectura de quienes siguen asignados.
    - Aborta ante datos inválidos para evitar borrar asignaciones por error.
    """
    conn = None

    try:
        conn = conectar(slug)

        columnas = [
            r[1] for r in conn.execute(
                'PRAGMA table_info(comunicaciones_leidas)'
            ).fetchall()
        ]

        if not columnas:
            raise RuntimeError(
                'No existe la tabla comunicaciones_leidas.'
            )

        if 'leido' not in columnas:
            conn.execute(
                'ALTER TABLE comunicaciones_leidas '
                'ADD COLUMN leido INTEGER DEFAULT 0'
            )
            conn.commit()

        com = conn.execute(
            'SELECT * FROM comunicaciones WHERE id=?',
            (comunicacion_id,)
        ).fetchone()

        if not com:
            raise ValueError(
                f'No existe el comunicado {comunicacion_id}.'
            )

        if com['estado'] != 'publicado':
            return {
                'ok': True,
                'mensaje': 'El comunicado no está publicado.',
                'destinatarios': 0
            }

        dest_tipo = com['destinatario_tipo']
        valor_original = com['destinatario_valor']

        try:
            val_arr = (
                json.loads(valor_original)
                if valor_original else []
            )
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                'El valor de destinatarios no contiene JSON válido.'
            ) from exc

        if not isinstance(val_arr, list):
            raise ValueError(
                'Los destinatarios deben estar almacenados como una lista.'
            )

        destinatarios = set()

        def agregar_activos(tabla, tipo, ids=None):
            if ids is None:
                filas = conn.execute(
                    f'SELECT id FROM {tabla} WHERE activo=1'
                ).fetchall()
                encontrados = {int(r['id']) for r in filas}
            else:
                ids = set(ids)
                if not ids:
                    return

                marcadores = ','.join('?' for _ in ids)
                filas = conn.execute(
                    f'SELECT id FROM {tabla} '
                    f'WHERE activo=1 AND id IN ({marcadores})',
                    tuple(ids)
                ).fetchall()

                encontrados = {int(r['id']) for r in filas}

                if encontrados != ids:
                    raise ValueError(
                        f'Hay destinatarios inexistentes o inactivos '
                        f'en la tabla {tabla}.'
                    )

            for uid in encontrados:
                destinatarios.add((tipo, uid))

        if dest_tipo == 'todo_colegio':
            agregar_activos('profesores', 'profesor')
            agregar_activos('directoras', 'directora')
            agregar_activos('alumnos', 'estudiante')

        elif dest_tipo == 'profesores':
            if not val_arr:
                agregar_activos('profesores', 'profesor')
            else:
                ids = set()
                for valor in val_arr:
                    if not isinstance(valor, str) or not valor.startswith('prof_'):
                        raise ValueError(
                            f'Destinatario de profesor inválido: {valor}'
                        )
                    try:
                        uid = int(valor[5:])
                    except ValueError as exc:
                        raise ValueError(
                            f'ID de profesor inválido: {valor}'
                        ) from exc
                    if uid <= 0:
                        raise ValueError('ID de profesor inválido.')
                    ids.add(uid)

                agregar_activos('profesores', 'profesor', ids)

        elif dest_tipo == 'directores':
            if not val_arr:
                agregar_activos('directoras', 'directora')
            else:
                ids = set()
                for valor in val_arr:
                    if not isinstance(valor, str) or not valor.startswith('dir_'):
                        raise ValueError(
                            f'Destinatario de director inválido: {valor}'
                        )
                    try:
                        uid = int(valor[4:])
                    except ValueError as exc:
                        raise ValueError(
                            f'ID de director inválido: {valor}'
                        ) from exc
                    if uid <= 0:
                        raise ValueError('ID de director inválido.')
                    ids.add(uid)

                agregar_activos('directoras', 'directora', ids)

        elif dest_tipo == 'estudiantes':
            agregar_activos('alumnos', 'estudiante')

        elif dest_tipo == 'grado':
            if not val_arr:
                raise ValueError(
                    'No se especificaron grados para el comunicado.'
                )

            grados = set()
            for grado in val_arr:
                if not isinstance(grado, (str, int)):
                    raise ValueError(f'Grado inválido: {grado}')
                grado_num = ''.join(
                    filter(str.isdigit, str(grado))
                )
                if not grado_num:
                    raise ValueError(f'Grado inválido: {grado}')
                grados.add(grado_num)

            cursos = conn.execute(
                'SELECT DISTINCT curso FROM alumnos WHERE activo=1'
            ).fetchall()

            cursos_validos = []
            for fila in cursos:
                curso = fila['curso'] or ''
                numero = ''.join(filter(str.isdigit, curso))
                if numero in grados:
                    cursos_validos.append(curso)

            if cursos_validos:
                marcadores = ','.join('?' for _ in cursos_validos)
                filas = conn.execute(
                    f'SELECT id FROM alumnos WHERE activo=1 '
                    f'AND curso IN ({marcadores})',
                    tuple(cursos_validos)
                ).fetchall()

                for fila in filas:
                    destinatarios.add(
                        ('estudiante', int(fila['id']))
                    )

        elif dest_tipo == 'cursos':
            if not val_arr:
                raise ValueError(
                    'No se especificaron cursos para el comunicado.'
                )

            if not all(isinstance(c, str) and c.strip() for c in val_arr):
                raise ValueError('La lista de cursos contiene valores inválidos.')

            cursos = list(set(c.strip() for c in val_arr))
            marcadores = ','.join('?' for _ in cursos)

            filas = conn.execute(
                f'SELECT id FROM alumnos WHERE activo=1 '
                f'AND curso IN ({marcadores})',
                tuple(cursos)
            ).fetchall()

            for fila in filas:
                destinatarios.add(
                    ('estudiante', int(fila['id']))
                )

        elif dest_tipo == 'rector':
            principal = conn.execute(
                'SELECT id FROM rectores '
                'WHERE activo=1 AND es_principal=1 LIMIT 1'
            ).fetchone()

            if principal:
                destinatarios.add(
                    ('rector', int(principal['id']))
                )

        else:
            raise ValueError(
                f'Tipo de destinatario no reconocido: {dest_tipo}'
            )

        # No modificar asignaciones hasta tener la lista validada.
        conn.execute('BEGIN')

        actuales = conn.execute(
            '''
            SELECT usuario_tipo, usuario_id
            FROM comunicaciones_leidas
            WHERE comunicacion_id=?
            ''',
            (comunicacion_id,)
        ).fetchall()

        actuales_set = {
            (r['usuario_tipo'], int(r['usuario_id']))
            for r in actuales
        }

        # Eliminar únicamente los destinatarios que ya no corresponden.
        obsoletos = actuales_set - destinatarios

        for tipo, uid in obsoletos:
            conn.execute(
                '''
                DELETE FROM comunicaciones_leidas
                WHERE comunicacion_id=?
                  AND usuario_tipo=?
                  AND usuario_id=?
                ''',
                (comunicacion_id, tipo, uid)
            )

        # Insertar los nuevos sin alterar el estado de lectura existente.
        nuevos = destinatarios - actuales_set

        for tipo, uid in nuevos:
            conn.execute(
                '''
                INSERT OR IGNORE INTO comunicaciones_leidas
                (comunicacion_id, usuario_tipo, usuario_id, leido)
                VALUES (?, ?, ?, 0)
                ''',
                (comunicacion_id, tipo, uid)
            )

        conn.commit()

        resultado = {
            'ok': True,
            'destinatarios': len(destinatarios),
            'agregados': len(nuevos),
            'retirados': len(obsoletos),
            'mensaje': 'Destinatarios sincronizados correctamente.'
        }

        app_logger.info(
            f'generar_destinatarios: comunicado={comunicacion_id}, '
            f'destinatarios={len(destinatarios)}, '
            f'agregados={len(nuevos)}, retirados={len(obsoletos)}'
        )

        return resultado

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass

        app_logger.exception(
            f'generar_destinatarios: error en comunicado '
            f'{comunicacion_id}: {e}'
        )

        return {
            'ok': False,
            'mensaje': str(e),
            'destinatarios': 0
        }

    finally:
        if conn:
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
