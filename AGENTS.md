# AGENTS.md — Lumini v2 Architecture Migration

## Objective
Migrate monolithic `flask_app.py` (~9300 lines) into modular Blueprints, services, and repositories while keeping all 298 tests passing end-to-end.

**Status**: ✅ DONE — `flask_app.py` is now a **172-line entry point** (98% reduction).

## Architecture
```
flask_app.py          → 172 lines: app creation, imports, blueprint registration, main
app/
  handlers.py         → error handlers (400/403/404/413/500)
  filters.py          → template filters
  backup.py           → backup scheduler
  infra/
    __init__.py
    config.py         → constants (DB_FOLDER, JORNADAS, SCHEMA_VERSION, etc.)
    security.py       → CSRF, brute-force, password hash, image validation
    database.py       → conectar, init_db, migrar_db, schema migrations (v6–v20), cache
    helpers.py        → get_profesor, get_directora, get_rector, get_usuario_actual, etc.
    permissions.py    → roles, permisos, tiene_permiso, requiere_permiso
    grades.py         → _promedio_simple, _promedio_ponderado, calcular_stats_*
    audit.py          → audit_log, auditar_nota, periodo_cerrado
    dashboard.py      → _dashboard_profesor_data, _dashboard_rector_data, _estadisticas_desc
    attendance.py     → _asistencia_stats, _asistencia_alertas
    notifications.py  → crear_notificacion, generar_destinatarios, comunicaciones_pendientes
    pdf.py            → generar_pdf_alumno
    mail.py           → enviar_correo (SendGrid)
    excel.py          → _excel_armar_wb (OpenPyXL)
  routes/
    rector_routes.py, directora_routes.py, admin_routes.py, parent_routes.py,
    student_routes.py, notifications_routes.py, teacher.py, observations.py,
    courses.py, attendance.py, channels_routes.py, files_routes.py,
    auth.py, main_routes.py
  services/
    rector_service.py, parent_service.py, student_service.py,
    notification_service.py, channel_service.py, file_service.py
  repositories/
    rector_repository.py, parent_repository.py, student_repository.py,
    notification_repository.py
```

## Key Facts
- All functions re-exported from `flask_app.py` for test compatibility
- `_fa()` pattern in route files: `import flask_app as fa; fa.conectar(slug)`
- `298 passed` after every change
- No template, schema, route path, or permission changes

## Test Commands
```powershell
cd C:\Users\PC\OneDrive\Documentos\GitHub\Lumini
& "C:\Users\PC\AppData\Local\Python\bin\python.exe" -m pytest --tb=short -q
```
298 passed (≈110s)
