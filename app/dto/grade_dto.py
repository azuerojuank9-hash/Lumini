from dataclasses import dataclass, field


@dataclass
class GradeDTO:
    aid: int
    actividad_id: int
    val: float
    actividad_nombre: str | None = None


@dataclass
class EvaluationDTO:
    aid: int
    evaluacion: float | None = None
    autoevaluacion: float | None = None


@dataclass
class GradeStatsDTO:
    promedio_curso: float | None = None
    notas_pendientes: int = 0
    aprobados: int = 0
    reprobados: int = 0


@dataclass
class GradeReportDTO:
    estudiante: str
    curso: str
    materia: str
    periodo: int
    promedio: float | None = None
    notas: list = field(default_factory=list)
    evaluacion: float | None = None
    autoevaluacion: float | None = None
