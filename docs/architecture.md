# Lumini — Arquitectura

## Estructura del proyecto

```
lumini/
  config/         # Configuración por ambientes
  app/
    dto/          # Data Transfer Objects
    exceptions/   # Excepciones tipadas
    infra/        # Infraestructura (DB, seguridad, helpers)
    logging/      # Logging profesional
    repositories/ # Acceso a datos
    routes/       # Blueprints Flask
    services/     # Lógica de negocio
    validators/   # Validadores reutilizables
  tests/          # Tests (298 tests)
```

## Infraestructura

- **app.infra.attendance**

- **app.infra.audit**

- **app.infra.config**
  - 

- **app.infra.dashboard**

- **app.infra.database**

- **app.infra.excel**

- **app.infra.grades**

- **app.infra.helpers**

- **app.infra.mail**

- **app.infra.notifications**

- **app.infra.pdf**

- **app.infra.permissions**

- **app.infra.security**

- **app.infra.session**


## Servicios

- **app.services.activity_service**

- **app.services.attendance_service**

- **app.services.auth**
  - Authentication service — login/logout/session logic.

- **app.services.auth_service**
  - Authentication service — login, logout, password recovery, brute-force.

- **app.services.certificates**
  - Certificate generation service — re-exports from existing utils/certificates.py.

- **app.services.channel_service**

- **app.services.course_service**

- **app.services.file_service**

- **app.services.grade_service**

- **app.services.grades**
  - Grade management service.

- **app.services.migration_service**

- **app.services.notification_service**

- **app.services.observation_service**

- **app.services.parent_service**

- **app.services.planning_service**

- **app.services.rector_service**

- **app.services.student_service**

- **app.services.template_service**


## Repositorios

- **app.repositories.attendance_repository**

- **app.repositories.channel_repository**

- **app.repositories.course_repository**

- **app.repositories.database**
  - Database connection utilities — re-exports from flask_app.

- **app.repositories.file_repository**

- **app.repositories.grade_repository**

- **app.repositories.grades**
  - Grade repository — SQL queries for evaluations, activities, etc.

- **app.repositories.migration_repository**

- **app.repositories.notification_repository**

- **app.repositories.observation_repository**

- **app.repositories.parent_repository**

- **app.repositories.planning_repository**

- **app.repositories.rector_repository**

- **app.repositories.student_repository**

- **app.repositories.template_repository**

- **app.repositories.user_repository**
  - User repository — SQL queries for users across all roles.

- **app.repositories.users**
  - User repository — SQL queries for user data.


## Rutas

- **app.routes.admin_routes**

- **app.routes.attendance**

- **app.routes.auth**
  - Authentication routes — login, logout, password recovery for all roles.

- **app.routes.channels_routes**

- **app.routes.courses**

- **app.routes.directora_routes**

- **app.routes.files_routes**

- **app.routes.main_routes**

- **app.routes.notifications_routes**

- **app.routes.observations**

- **app.routes.parent_routes**

- **app.routes.rector_routes**

- **app.routes.student_routes**

- **app.routes.teacher**
  - Teacher routes — activities, grades, history, Excel import/export.


## DTOs

- **app.dto.activity_dto**

- **app.dto.communication_dto**

- **app.dto.course_dto**

- **app.dto.grade_dto**

- **app.dto.student_dto**


## Excepciones

- **app.exceptions.business**

- **app.exceptions.database**

- **app.exceptions.permissions**

- **app.exceptions.validation**


## Validadores

- **app.validators.activity_validator**
  - Activity data validators.

- **app.validators.attendance_validator**
  - Attendance data validators.

- **app.validators.grades_validator**
  - Grade data validators.

- **app.validators.student_validator**
  - Student data validators — reusable validation logic.


## Config

- **base**

- **development**

- **production**

- **testing**

