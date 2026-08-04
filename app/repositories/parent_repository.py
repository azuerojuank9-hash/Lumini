class ParentRepository:
    @staticmethod
    def get_hijos(conn, padre_id):
        return conn.execute(
            'SELECT a.id, a.nombre, a.curso, a.jornada FROM alumno_padre ap JOIN alumnos a ON a.id=ap.alumno_id WHERE ap.padre_id=?',
            (padre_id,)).fetchall()

    @staticmethod
    def get_alumno(conn, alumno_id):
        return conn.execute(
            'SELECT id, nombre, curso, jornada FROM alumnos WHERE id=? AND activo=1',
            (alumno_id,)).fetchone()

    @staticmethod
    def get_asistencia_resumen(conn, alumno_id):
        return conn.execute(
            'SELECT estado, COUNT(*) as cnt FROM asistencia WHERE aid=? AND DATE(fecha)>=DATE("now","-30 days") GROUP BY estado',
            (alumno_id,)).fetchall()

    @staticmethod
    def get_actividades_publicadas_count(conn, curso, jornada):
        return conn.execute(
            'SELECT COUNT(*) as cnt FROM actividades WHERE curso=? AND jornada=? AND estado_act="publicada"',
            (curso, jornada)).fetchone()

    @staticmethod
    def verificar_relacion_padre(conn, padre_id, alumno_id):
        return conn.execute(
            'SELECT id FROM alumno_padre WHERE padre_id=? AND alumno_id=?',
            (padre_id, alumno_id)).fetchone()

    @staticmethod
    def get_actividades_con_notas(conn, alumno_id):
        return conn.execute(
            'SELECT a.id, a.nombre, a.tipo, a.peso, COALESCE(ROUND(AVG(n.val),2),0) as prom FROM actividades a LEFT JOIN notas n ON n.actividad_id=a.id AND n.aid=? WHERE a.curso=(SELECT curso FROM alumnos WHERE id=?) AND a.jornada=(SELECT jornada FROM alumnos WHERE id=?) GROUP BY a.id ORDER BY a.orden',
            (alumno_id, alumno_id, alumno_id)).fetchall()

    @staticmethod
    def get_asistencia_reciente(conn, alumno_id, limite=60):
        return conn.execute(
            'SELECT fecha, estado FROM asistencia WHERE aid=? ORDER BY fecha DESC LIMIT ?',
            (alumno_id, limite)).fetchall()

    @staticmethod
    def get_hijo_ids(conn, padre_id):
        return [r['alumno_id'] for r in conn.execute(
            'SELECT alumno_id FROM alumno_padre WHERE padre_id=?', (padre_id,)).fetchall()]

    @staticmethod
    def get_comunicados_publicos(conn, limite=20):
        return conn.execute(
            'SELECT id, titulo, contenido, fecha_creacion FROM comunicaciones WHERE destinatario_tipo IN ("todo_colegio","estudiantes") AND estado="publicado" ORDER BY fecha_creacion DESC LIMIT ?',
            (limite,)).fetchall()

    @staticmethod
    def get_horario_alumno(conn, alumno_id):
        alumno = conn.execute(
            'SELECT curso, jornada FROM alumnos WHERE id=?', (alumno_id,)).fetchone()
        if not alumno:
            return []
        return conn.execute(
            'SELECT dia, franja, num, materia, profesor FROM horarios_curso WHERE curso=? AND jornada=? ORDER BY dia, franja',
            (alumno['curso'], alumno['jornada'])).fetchall()

    @staticmethod
    def get_observaciones_alumno(conn, alumno_id):
        return conn.execute(
            'SELECT materia, texto, fecha FROM observaciones WHERE aid=? ORDER BY fecha DESC',
            (alumno_id,)).fetchall()
