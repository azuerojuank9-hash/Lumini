from app.exceptions.business import (
    ActivityNotFoundError,
    BusinessError,
    CourseNotFoundError,
    DuplicateAssignmentError,
    InvalidGradeError,
    MaxCapacityError,
    PeriodClosedError,
    StudentNotActiveError,
)
from app.exceptions.database import (
    ConfigNotFoundError,
    ConnectionError,
    DatabaseError,
    IntegrityError,
    MigrationError,
    NotFoundError,
)
from app.exceptions.permissions import (
    ForbiddenError,
    InsufficientPermissionsError,
    PermissionError,
    RoleNotFoundError,
    UnauthorizedError,
)
from app.exceptions.validation import (
    DuplicateEntryError,
    InvalidEmailError,
    InvalidPasswordError,
    InvalidSlugError,
    MissingFieldError,
    ValidationError,
)

__all__ = [
    'ValidationError', 'InvalidSlugError', 'InvalidEmailError',
    'InvalidPasswordError', 'MissingFieldError', 'DuplicateEntryError',
    'PermissionError', 'UnauthorizedError', 'ForbiddenError',
    'RoleNotFoundError', 'InsufficientPermissionsError',
    'DatabaseError', 'ConnectionError', 'NotFoundError', 'MigrationError',
    'IntegrityError', 'ConfigNotFoundError',
    'BusinessError', 'PeriodClosedError', 'InvalidGradeError',
    'StudentNotActiveError', 'ActivityNotFoundError', 'CourseNotFoundError',
    'MaxCapacityError', 'DuplicateAssignmentError',
]
