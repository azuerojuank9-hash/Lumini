# Lumini — Base de Datos

## Esquema

La base de datos usa SQLite con WAL mode.

### Base de datos maestra (`master.db`)
- `colegios` — registro de colegios
- `schema_meta` — versión del esquema

### Bases de datos por colegio (`colegios_db/{slug}.db`)
- `alumnos` — estudiantes
- `profesores` — docentes
- `directoras` — coordinadoras
- `rectores` — administradores del colegio
- `notas` — calificaciones
- `actividades` — tareas/exámenes
- `asistencia` — registro de asistencia
- `asignaciones_curso` — profesor -> curso/materia/jornada
- `canales` / `mensajes_canal` / `canal_miembros` — mensajería
- `notificaciones` — sistema de notificaciones
- `observaciones` — observaciones de estudiantes
- `auditoria_notas` / `auditoria_log` — auditoría
- `periodos_estado` — estado de periodos académicos
- `evaluaciones` — evaluaciones/autoevaluaciones
- `configuracion` — configuración del colegio

## Migraciones

Las migraciones se manejan secuencialmente (v6 a v20 actualmente)
en `app/infra/database.py`.

## Cache

Cache en memoria con TTL configurable (`_cache`, `_cache_lock`, `_CACHE_TTL`).