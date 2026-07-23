from app.repositories.parent_repository import ParentRepository


class ParentService:
    @staticmethod
    def get_dashboard_data(conn, padre_id):
        hijos = ParentRepository.get_hijos(conn, padre_id)
        resultado = []
        for h in hijos:
            notas = ParentRepository.get_promedio_alumno(conn, h['id'], h['curso'])
            asistencias = ParentRepository.get_asistencia_resumen(conn, h['id'])
            act_count = ParentRepository.get_actividades_publicadas_count(conn, h['curso'], h['jornada'])
            resultado.append({
                'id': h['id'], 'nombre': h['nombre'], 'curso': h['curso'], 'jornada': h['jornada'],
                'promedio': round(notas['prom'], 2),
                'asistencia': [dict(a) for a in asistencias],
                'actividades': act_count['cnt'],
            })
        return resultado

    @staticmethod
    def verificar_relacion(conn, padre_id, alumno_id):
        return ParentRepository.verificar_relacion_padre(conn, padre_id, alumno_id) is not None

    @staticmethod
    def get_notas_alumno(conn, alumno_id):
        acts = ParentRepository.get_actividades_con_notas(conn, alumno_id)
        return [dict(a) for a in acts]

    @staticmethod
    def get_asistencia_alumno(conn, alumno_id, limite=60):
        rows = ParentRepository.get_asistencia_reciente(conn, alumno_id, limite)
        return [dict(r) for r in rows]

    @staticmethod
    def get_comunicados(conn, padre_id):
        rows = ParentRepository.get_comunicados_publicos(conn)
        return [dict(r) for r in rows]
