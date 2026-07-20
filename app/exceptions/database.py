class DatabaseError(Exception):
    message: str = 'Error de base de datos'

    def __init__(self, message: str = None, original: Exception = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.original = original


class ConnectionError(DatabaseError):
    message = 'Error de conexión a la base de datos'


class NotFoundError(DatabaseError):
    message = 'Recurso no encontrado'

    def __init__(self, entity: str = None, entity_id=None):
        if entity:
            msg = f'{entity} no encontrado' + (f' (id={entity_id})' if entity_id else '')
        else:
            msg = self.message
        super().__init__(msg)


class MigrationError(DatabaseError):
    message = 'Error durante la migración de esquema'


class IntegrityError(DatabaseError):
    message = 'Error de integridad de datos'


class ConfigNotFoundError(DatabaseError):
    message = 'Configuración no encontrada'

    def __init__(self, key: str = None):
        msg = f'Configuración "{key}" no encontrada' if key else self.message
        super().__init__(msg)
