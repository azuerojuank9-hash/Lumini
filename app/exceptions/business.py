class BusinessError(Exception):
    status_code: int = 400
    message: str = 'Error de negocio'

    def __init__(self, message: str = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class PeriodClosedError(BusinessError):
    status_code = 400
    message = 'El período académico está cerrado'


class InvalidGradeError(BusinessError):
    status_code = 400
    message = 'La nota ingresada no es válida'

    def __init__(self, grade: float = None):
        msg = f'La nota {grade} no es válida (debe estar entre 0 y 10)' if grade is not None else self.message
        super().__init__(msg)


class StudentNotActiveError(BusinessError):
    status_code = 400
    message = 'El estudiante no está activo'


class ActivityNotFoundError(BusinessError):
    status_code = 404
    message = 'Actividad no encontrada'

    def __init__(self, activity_id: int = None):
        msg = f'Actividad {activity_id} no encontrada' if activity_id else self.message
        super().__init__(msg)


class CourseNotFoundError(BusinessError):
    status_code = 404
    message = 'Curso no encontrado'

    def __init__(self, course: str = None):
        msg = f'Curso "{course}" no encontrado' if course else self.message
        super().__init__(msg)


class MaxCapacityError(BusinessError):
    status_code = 400
    message = 'Se ha alcanzado la capacidad máxima'


class DuplicateAssignmentError(BusinessError):
    status_code = 409
    message = 'La asignación ya existe'
