"""
AI Service Layer — Academic Risk Prediction & Recommendations.

Scaffold for future AI integration (OpenAI, custom models, etc.).
All methods log predictions without calling external APIs yet.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class RiskPrediction:
    estudiante_id: int
    nombre: str
    curso: str
    riesgo: str  # 'bajo' | 'medio' | 'alto'
    puntaje: float
    factores: list[str]
    recomendaciones: list[str]
    fecha: str


@dataclass
class AcademicRecommendation:
    estudiante_id: int
    area: str
    sugerencia: str
    prioridad: str  # 'baja' | 'media' | 'alta'
    fundamento: str


class AIService:
    def __init__(self, slug: str, conn):
        self.slug = slug
        self.conn = conn
        self._available = False

    def is_available(self) -> bool:
        return self._available

    def predict_risk(self, estudiante_id: int) -> RiskPrediction:
        """
        Predict academic risk for a student based on current grades and attendance.

        Uses heuristic rules until AI model is connected:
        - < 3.0 promedio -> alto riesgo
        - 3.0-3.5 + >20% inasistencias -> medio riesgo
        - Otherwise -> bajo riesgo
        """
        promedio = self._calc_promedio(estudiante_id)
        inasistencias = self._calc_inasistencias(estudiante_id)
        nombre, curso = self._get_basics(estudiante_id)

        factores = []
        recomendaciones = []

        if promedio is not None and promedio < 3.0:
            riesgo = 'alto'
            factores.append(f'Promedio académico bajo: {promedio:.1f}')
            recomendaciones.append('Implementar plan de nivelación académica inmediata.')
            recomendaciones.append('Asignar tutoría personalizada 2 horas/semana.')
        elif (promedio is not None and promedio < 3.5) or inasistencias > 20:
            riesgo = 'medio'
            if promedio and promedio < 3.5:
                factores.append(f'Promedio académico en seguimiento: {promedio:.1f}')
            if inasistencias > 20:
                factores.append(f'Inasistencias elevadas: {inasistencias:.0f}%')
            recomendaciones.append('Seguimiento quincenal con docente.')
            recomendaciones.append('Refuerzo en áreas con menor rendimiento.')
        else:
            riesgo = 'bajo'
            recomendaciones.append('Continuar con el desempeño actual.')
            recomendaciones.append('Mantener comunicación con acudientes.')

        if inasistencias > 30:
            factores.append('Inasistencias críticas: requiere intervención de coordinación.')

        return RiskPrediction(
            estudiante_id=estudiante_id,
            nombre=nombre,
            curso=curso,
            riesgo=riesgo,
            puntaje=promedio or 0.0,
            factores=factores,
            recomendaciones=recomendaciones,
            fecha=datetime.now(timezone.utc).isoformat(),
        )

    def batch_risk_analysis(self, curso: str | None = None) -> list[RiskPrediction]:
        """Analyze risk for all students, optionally filtered by course."""
        query = 'SELECT id FROM alumnos WHERE activo=1'
        params = []
        if curso:
            query += ' AND curso=?'
            params.append(curso)

        rows = self.conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            try:
                results.append(self.predict_risk(r['id']))
            except Exception as e:
                logger.warning('[AI] Risk prediction failed for student %d: %s', r['id'], e)
        return results

    def generate_observation(self, estudiante_id: int, contexto: str = '') -> str:
        """
        Generate an automatic observation text.

        TODO: Connect to OpenAI for NLG.
        Current: template-based generation.
        """
        nombre, curso = self._get_basics(estudiante_id)
        promedio = self._calc_promedio(estudiante_id)
        prom_str = f'{promedio:.1f}' if promedio is not None else 'N/A'

        if promedio and promedio < 3.0:
            return (f'El estudiante {nombre} del curso {curso} presenta un rendimiento '
                    f'académico por debajo del promedio esperado (promedio actual: {prom_str}). '
                    'Se recomienda seguimiento académico y refuerzo en las áreas de menor desempeño.')
        elif promedio and promedio >= 4.0:
            return (f'El estudiante {nombre} del curso {curso} continúa destacándose '
                    f'académicamente con un promedio de {prom_str}. '
                    'Felicitar y mantener el estímulo.')
        else:
            return (f'El estudiante {nombre} del curso {curso} mantiene un desempeño '
                    f'académico regular (promedio: {prom_str}). Continuar con seguimiento.')

    def recommend_courses(self, estudiante_id: int) -> list[AcademicRecommendation]:
        """Recommend focus areas based on grade patterns."""
        rows = self.conn.execute('''
            SELECT ac.materia, AVG(n.val) as avg_val
            FROM notas n
            JOIN actividades ac ON ac.id=n.actividad_id
            WHERE n.aid=? GROUP BY ac.materia ORDER BY avg_val ASC
        ''', (estudiante_id,)).fetchall()

        recs = []
        for r in rows:
            if r['avg_val'] < 3.0:
                recs.append(AcademicRecommendation(
                    estudiante_id=estudiante_id,
                    area=r['materia'],
                    sugerencia=f'Refuerzo prioritario en {r["materia"]} (promedio: {r["avg_val"]:.1f})',
                    prioridad='alta',
                    fundamento=f'Rendimiento por debajo del mínimo en {r["materia"]}'
                ))
        return recs

    def _calc_promedio(self, estudiante_id: int) -> float | None:
        from flask_app import _promedio_simple
        notas = self.conn.execute('''
            SELECT n.val FROM notas n
            JOIN actividades ac ON ac.id=n.actividad_id
            WHERE n.aid=?
        ''', (estudiante_id,)).fetchall()
        vals = [n['val'] for n in notas]
        return _promedio_simple(vals)

    def _calc_inasistencias(self, estudiante_id: int) -> float:
        rows = self.conn.execute(
            'SELECT COUNT(*) as total, SUM(CASE WHEN estado="A" THEN 1 ELSE 0 END) as faltas '
            'FROM asistencia WHERE aid=?', (estudiante_id,)
        ).fetchone()
        total = rows['total'] or 0
        faltas = rows['faltas'] or 0
        return (faltas / total * 100) if total > 0 else 0.0

    def _get_basics(self, estudiante_id: int):
        row = self.conn.execute(
            'SELECT nombre, curso FROM alumnos WHERE id=?', (estudiante_id,)
        ).fetchone()
        return (row['nombre'], row['curso']) if row else ('Desconocido', '')
