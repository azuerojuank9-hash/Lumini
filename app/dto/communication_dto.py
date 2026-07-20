from dataclasses import dataclass, field


@dataclass
class MessageDTO:
    id: int
    canal_id: int
    usuario_tipo: str
    usuario_id: int
    mensaje: str
    fecha: str
    autor_nombre: str = ''
    editado: bool = False
    eliminado: bool = False
    responde_a: int | None = None
    tiene_archivos: bool = False
    archivos: list = field(default_factory=list)
    reacciones: dict = field(default_factory=dict)


@dataclass
class ChannelDTO:
    id: int
    nombre: str
    tipo: str
    activo: bool = True
    ultimo_mensaje: str | None = None
    ultima_fecha: str | None = None
    no_leidos: int = 0


@dataclass
class NotificationDTO:
    id: int
    mensaje: str
    tipo: str
    fecha: str
    leido: bool = False
    enlace: str | None = None


@dataclass
class CommunicationDTO:
    id: int
    asunto: str
    mensaje: str
    fecha: str
    autor: str
    leido: bool = False
    adjuntos: list = field(default_factory=list)
