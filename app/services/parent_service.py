from app.infra.grades import _promedio_ponderado
from app.repositories.parent_repository import ParentRepository


class ParentService:
    @staticmethod
    def _get_notas_context(conn, alumno_id, periodo=1):
        from app.services.student_service import get_notas_context
        alumno = ParentRepository.get_alumno(conn, alumno_id)
        if not alumno:
            return None, None, None, None
        return get_notas_context(conn, alumno, periodo, _promedio_ponderado)

    @staticmethod
    def get_dashboard_data(conn, padre_id):
        hijos = ParentRepository.get_hijos(conn, padre_id)
        resultado = []
        for h in hijos:
            _, _, _, promedio_general = ParentService._get_notas_context(conn, h['id'])
            asistencias = ParentRepository.get_asistencia_resumen(conn, h['id'])
            act_count = ParentRepository.get_actividades_publicadas_count(conn, h['curso'], h['jornada'])
            resultado.append({
                'id': h['id'], 'nombre': h['nombre'], 'curso': h['curso'], 'jornada': h['jornada'],
                'promedio': round(promedio_general, 2) if promedio_general is not None else None,
                'asistencia': [dict(a) for a in asistencias],
                'actividades': act_count['cnt'],
            })
        return resultado

    @staticmethod
    def verificar_relacion(conn, padre_id, alumno_id):
        return ParentRepository.verificar_relacion_padre(conn, padre_id, alumno_id) is not None

    @staticmethod
    def get_notas_alumno(conn, alumno_id):
        from app.repositories.student_repository import get_notas_estudiante
        notas_pm, evals_map, proms_pm, promedio_general = ParentService._get_notas_context(conn, alumno_id)
        acts = ParentRepository.get_actividades_con_notas(conn, alumno_id)
        materias = []
        for mat, notas in (notas_pm or {}).items():
            ev = evals_map.get(mat, {}) if evals_map else {}
            materias.append({
                'materia': mat,
                'actividades': notas,
                'evaluacion': ev.get('evaluacion') if ev.get('evaluacion') is not None else None,
                'autoevaluacion': ev.get('autoevaluacion') if ev.get('autoevaluacion') is not None else None,
                'nota_final': proms_pm.get(mat) if proms_pm else None,
            })
        return {
            'actividades': [dict(a) for a in acts],
            'materias': materias,
            'promedio_general': promedio_general,
        }

    @staticmethod
    def get_asistencia_alumno(conn, alumno_id, limite=60):
        rows = ParentRepository.get_asistencia_reciente(conn, alumno_id, limite)
        return [dict(r) for r in rows]

    @staticmethod
    def get_comunicados(conn, padre_id):
        rows = ParentRepository.get_comunicados_publicos(conn)
        return [dict(r) for r in rows]

    @staticmethod
    def get_horario_alumno(conn, alumno_id):
        rows = ParentRepository.get_horario_alumno(conn, alumno_id)
        return [dict(r) for r in rows]

    @staticmethod
    def get_observaciones_alumno(conn, alumno_id):
        rows = ParentRepository.get_observaciones_alumno(conn, alumno_id)
        return [dict(r) for r in rows]

    @staticmethod
    def get_historial_alumno(conn, alumno_id):
        alumno = ParentRepository.get_alumno(conn, alumno_id)
        if not alumno:
            return {'periodos': {}, 'totales': {}}
        rows = conn.execute(
            '''SELECT DISTINCT COALESCE(ac.periodo,1) as periodo FROM notas n
               JOIN actividades ac ON ac.id=n.actividad_id WHERE n.aid=?
               UNION
               SELECT DISTINCT COALESCE(periodo,1) FROM evaluaciones WHERE aid=?''',
            (alumno_id, alumno_id)).fetchall()
        periodos = {}
        for r in rows:
            p = int(r['periodo'])
            _, _, proms_pm, _ = ParentService._get_notas_context(conn, alumno_id, p)
            periodos[p] = [{'materia': m, 'promedio': v} for m, v in (proms_pm or {}).items()
                           if v is not None]
        totales = {}
        for p, mats in periodos.items():
            vals = [m['promedio'] for m in mats]
            totales[p] = round(sum(vals) / len(vals), 2) if vals else None
        return {'periodos': periodos, 'totales': totales}
