import logging
import re

logger = logging.getLogger(__name__)


def duplicar_actividad_logic(slug, act, profesor_id, conn):
    from app.repositories.grade_repository import get_max_orden_actividad
    max_ord = get_max_orden_actividad(
        slug, profesor_id, act['materia'], act['jornada'], act['curso'], act['periodo'] or 1)
    nuevo_nombre = (act['nombre'] or '').strip()
    m = re.search(r'(\d+)$', nuevo_nombre)
    if m:
        nuevo_nombre = nuevo_nombre[:m.start()] + str(int(m.group(1)) + 1)
    else:
        nuevo_nombre = nuevo_nombre + ' 2'
    c = conn.execute(
        '''INSERT INTO actividades
           (profesor_id,materia,jornada,curso,nombre,orden,periodo,tipo,peso,fecha_limite,
            hora_limite,descripcion,observaciones,estado_act,competencia,entrega_digital)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (profesor_id, act['materia'], act['jornada'], act['curso'], nuevo_nombre, max_ord + 1,
         act['periodo'] or 1, act['tipo'], act['peso'], act['fecha_limite'], act['hora_limite'],
         act['descripcion'], act['observaciones'], 'borrador', act['competencia'], act['entrega_digital']))
    new_id = c.lastrowid
    conn.commit()
    return new_id, nuevo_nombre


def create_calendar_event(slug, conn, nombre, tipo, descripcion, fecha_limite, hora_limite,
                          curso_sel, profesor_id, color='#6c63ff'):
    if not fecha_limite:
        return
    conn.execute(
        '''INSERT INTO eventos_calendario
           (slug,tipo,titulo,descripcion,fecha_inicio,fecha_fin,todo_el_dia,curso,
            creado_por_tipo,creado_por_id,color)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (slug, 'actividad', nombre + ' (' + tipo + ')',
         (descripcion or '')[:200] if descripcion else '',
         fecha_limite + ('T' + hora_limite if hora_limite else ''),
         fecha_limite + ('T' + hora_limite if hora_limite else ''),
         0 if hora_limite else 1,
         curso_sel, 'profesor', profesor_id, color))
