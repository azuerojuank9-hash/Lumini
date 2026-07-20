from dataclasses import dataclass, field


@dataclass
class StudentDTO:
    id: int
    nombre: str
    curso: str
    jornada: str
    activo: bool = True
    password: str | None = None
    email: str | None = None
    pin: str | None = None
    codigo: str | None = None


@dataclass
class StudentSummaryDTO:
    id: int
    nombre: str
    promedio: float | None = None
    estado: str = 'activo'
    alertas: list = field(default_factory=list)
