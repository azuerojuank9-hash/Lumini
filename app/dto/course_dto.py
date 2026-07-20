from dataclasses import dataclass


@dataclass
class CourseDTO:
    nombre: str
    jornada: str
    activo: bool = True
    total_estudiantes: int = 0


@dataclass
class AssignmentDTO:
    profesor_id: int
    materia: str
    jornada: str
    curso: str
    profesor_nombre: str | None = None
