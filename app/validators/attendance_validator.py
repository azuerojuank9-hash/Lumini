"""Attendance data validators."""
from app.exceptions import ValidationError

ESTADOS_VALIDOS = {'P', 'A', 'T', 'E', 'X', 'S'}


class AttendanceValidator:

    @staticmethod
    def validar_estado(estado: str) -> str:
        estado = estado.strip().upper()
        if estado not in ESTADOS_VALIDOS:
            raise ValidationError(f'Estado de asistencia no válido: {estado}')
        return estado

    @staticmethod
    def validar_fecha(fecha: str):
        if not fecha:
            raise ValidationError('La fecha es obligatoria')
        from datetime import datetime
        try:
            return datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError('Formato de fecha inválido (use AAAA-MM-DD)')

    @staticmethod
    def validar_asistencia_batch(alumno_id, estado, fecha):
        return alumno_id, AttendanceValidator.validar_estado(estado), AttendanceValidator.validar_fecha(fecha)
