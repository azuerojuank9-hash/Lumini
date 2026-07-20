from dataclasses import dataclass


@dataclass
class ActivityDTO:
    id: int
    nombre: str
    profesor_id: int
    materia: str
    jornada: str
    curso: str
    orden: int
    periodo: int
    activa: bool = True
    ponderacion: float | None = None
