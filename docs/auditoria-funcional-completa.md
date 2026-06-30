# Auditoría Funcional Completa de LUMINI

**Fecha:** 29 de junio de 2026
**Versión del documento:** 1.0
**Propósito:** Documentación oficial del estado actual del sistema

---

## 1. Resumen General

### 1.1 ¿Qué es LUMINI?

LUMINI es un **ecosistema integral para la gestión, operación y comunicación de instituciones educativas**. Es una plataforma web monolítica que unifica en un solo sistema los procesos académicos, administrativos y de comunicación que las instituciones educativas normalmente manejan con 3 a 7 herramientas desconectadas (WhatsApp, Excel, papel, correo, etc.).

### 1.2 Objetivo

Proveer una plataforma unificada donde cada actor institucional —desde la dirección hasta los estudiantes— encuentre las herramientas que necesita para su día a día, eliminando la fragmentación de herramientas externas y garantizando trazabilidad completa de todas las acciones.

### 1.3 Tipo de instituciones que puede administrar

Diseñado originalmente para **colegios de educación básica y media**, con capacidad de adaptarse a:
- Colegios privados y públicos
- Institutos técnicos
- Universidades (con limitaciones en el modelo actual plano)

Actualmente el modelo está orientado a una estructura plana (cursos con materias), sin soporte para jerarquías académicas complejas (facultades, programas, departamentos).

### 1.4 Estado actual del proyecto

- **Estado:** Versión de desarrollo activo con funcionalidades base operativas.
- **Estabilidad:** Funcional pero con código legacy y migraciones en curso.
- **Documentación:** Existe documentación técnica y funcional en `/docs/`.
- **Backups:** Sistema automático de backups diarios implementado.
- **Base de datos:** SQLite con esquema en evolución (SCHEMA_VERSION = 10).

### 1.5 Versión estimada

**v0.9-beta** — Pre-lanzamiento. La mayoría de las funcionalidades core están implementadas pero con código no refactorizado, tablas legacy coexistiendo con tablas nuevas, y módulos de comunicación avanzada (Fase 5) ya integrados.

---

## 2. Arquitectura

### 2.1 Vista general

| Capa | Tecnología |
|------|-----------|
| **Backend** | Python 3 + Flask (monolítico, ~4.490 líneas en `flask_app.py`) |
| **Frontend** | HTML5 + CSS3 + JavaScript vanilla (sin frameworks JS) |
| **Base de datos** | SQLite (WAL mode, foreign keys activas) |
| **Templates** | Jinja2 (33 templates, ~9.938 líneas) |
| **Servidor** | Flask development / Gunicorn (producción) |
| **Email** | SendGrid API |
| **PDF** | ReportLab + PyPDF |
| **Hash** | bcrypt |
| **Imágenes** | Pillow |

### 2.2 Backend

- **Archivo principal:** `flask_app.py` (~4.490 líneas, monolítico)
- **Patrón:** Toda la lógica en un solo archivo (sin blueprints, sin módulos separados)
- **Helpers:** Funciones auxiliares dentro del mismo archivo
- **Migraciones:** Sistema interno de versiones de esquema (v6 a v10) dentro del mismo archivo
- **CSRF:** Implementación manual con tokens de sesión
- **Sesiones:** Flask sesiones con cookie firmada, duración 4 horas

### 2.3 Frontend

- **Tema oscuro por defecto** con soporte para tema claro (vía `localStorage`)
- **Diseño:** CSS custom con variables, diseño system unificado, sidebar fija
- **Sin frameworks CSS:** Todo el CSS es inline en los templates (no hay archivos `.css` separados)
- **Sin frameworks JS:** JavaScript vanilla, sin React/Vue/Angular
- **Íconos:** Font Awesome 6.5.0 vía CDN
- **Tipografía:** Inter (Google Fonts)
- **PWA:** Service worker básico + manifest.json para instalación
- **Responsive:** Diseño adaptativo con media queries
- **Actualización en tiempo real:** Polling cada 30s para notificaciones y comunicaciones

### 2.4 Base de datos

**Estrategia multi-tenant:**
- **`master.db`** (base maestra): Registro de instituciones (`colegios` tabla)
- **`colegios_db/{slug}.db`** (una base por institución): Datos específicos de cada institución
- **Ubicación:** `colegios_db/` (gitignored, excluida del repositorio)

**Configuración:**
- `PRAGMA journal_mode=WAL` para mejor concurrencia
- `PRAGMA foreign_keys=ON` para integridad referencial
- Timeout de conexión: 30s

### 2.5 Autenticación

- **Administrador global:** Contraseña única desde variable de entorno (`ADMIN_PASSWORD`)
- **Profesores:** Login con usuario + contraseña (bcrypt), registro con código de invitación
- **Estudiantes:** Login por nombre + PIN (opcional), sin contraseña
- **Directoras:** Login con usuario + contraseña
- **Rectores:** Login con usuario + contraseña
- **Sesiones:** Variables de sesión por rol (`rol_{slug}`, `profesor_id_{slug}`, `rector_id_{slug}`, etc.)

### 2.6 Sesiones

- Duración: 4 horas (configurable vía `permanent_session_lifetime`)
- Cookie: HttpOnly, SameSite=Lax, Secure (configurable)
- Sesión persistente multi-rol (un mismo navegador puede tener varias sesiones)
- Almacenamiento: Cookies firmadas del lado del servidor (Flask default)

### 2.7 Permisos

Se implementó un sistema RBAC (Role-Based Access Control) con:
- **6 roles base:** admin, rector, authority, teacher, student, guardian
- **Permisos granulares** con notación de puntos (`academic.grades.write`)
- **Herencia por jerarquía:** roles superiores heredan permisos de inferiores
- **Decorador `@requiere_permiso`** para proteger rutas

### 2.8 Auditoría

- **Tabla `audit_log`** en cada base de institución
- Registra: usuario, acción, tabla, registro_id, valor_anterior, valor_nuevo, IP, user_agent
- Índices por tabla, usuario y fecha
- Función helper `audit_log()` para uso desde cualquier ruta
- Vista para el rector con paginación y filtro por tabla

### 2.9 Migraciones

- **Sistema interno** de versiones de esquema (no usa Alembic ni Flask-Migrate)
- Versión actual: **SCHEMA_VERSION = 10**
- Migraciones: v6 (usuarios), v7 (roles_base + roles_instancia), v8 (usuarios_roles + password_resets), v9 (config_institucion), v10 (audit_log + estructura_academica + curso_nuevo + materias + curso_materias)
- Las tablas legacy coexisten con las nuevas (migración en curso)
- Además hay un sistema de migración legacy en `migrar_db()` que altera tablas existentes

### 2.10 Backups

- Sistema automático diario (cada 24h) vía `threading.Timer`
- Copia `master.db` y todas las bases en `colegios_db/`
- Directorio: `backups/` (con fecha en el nombre)
- Primer backup a los 30s de iniciar la aplicación

### 2.11 Configuración institucional

- Tabla `config_institucion` por institución
- Configurable: tipo de evaluación, escala, período, jornadas, roles personalizados, acuse de recibo
- Gestionable desde el panel de Rector

---

## 3. Módulos Implementados

### 3.1 Administrador Global

Panel superadmin para gestionar todas las instituciones del sistema.

**Funcionalidad:**
- CRUD completo de instituciones educativas
- Activar/desactivar instituciones
- Gestión de códigos de invitación por rol (profesores, directoras, rectores)
- Generación automática de códigos de acceso
- Visualización de profesores por institución

### 3.2 Rector (Director General)

Máxima autoridad de cada institución. Panel de control completo.

**Funcionalidad:**
- Dashboard con KPIs institucionales
- Gestión de profesores (listar)
- Gestión de estudiantes (listar)
- Gestión de cursos (vista resumen)
- Gestión de horarios (ver todos los cursos)
- Reportes (estadísticas generales)
- Configuración institucional (perfil, configuración académica, períodos)
- Comunicaciones oficiales (CRUD completo)
- Canales de conversación (CRUD)
- Solicitudes de modificación de notas (aprobar/rechazar)
- Auditoría (visión completa del log)
- Gestión de múltiples rectores (sólo rector principal)

### 3.3 Coordinador Académico (Directora)

Rol de coordinación/gestión de cursos específicos.

**Funcionalidad:**
- Dashboard del curso a cargo
- Vista consolidada de notas por materia
- Generación de boletines PDF (individual o por curso)
- Envío masivo de boletines por email (vía SendGrid)
- Gestión de correos de acudientes
- Creación de directoras desde el panel

### 3.4 Docentes (Profesores)

Rol principal de gestión académica diaria.

**Funcionalidad:**
- Selección de materia/jornada al iniciar sesión
- Dashboard con KPIs: total alumnos, horario de hoy, asistencia hoy, notas pendientes, alertas
- CRUD de actividades por período
- Registro de notas inline (edición directa en tabla)
- Evaluaciones y autoevaluaciones por estudiante
- Solicitudes de modificación de notas
- Agenda de compromisos/trabajos
- Registro de asistencia diaria
- Observaciones por estudiante
- Vista de archivados (alumnos y profesores)
- Gestión de cursos propios (agregar/quitar)
- Transferencia de cursos a otros profesores
- Horarios (vista y edición)
- Cambio de contraseña

### 3.5 Estudiantes

Portal del estudiante para consulta de información académica.

**Funcionalidad:**
- Dashboard con promedio general y resumen
- Notas desglosadas por materia (actividades, evaluación, autoevaluación, nota final ponderada)
- Asistencia con estadísticas y vista mensual
- Observaciones recibidas
- Horario semanal
- Agenda de compromisos
- Visualización de comunicaciones pendientes

### 3.6 Centro de Avisos (Comunicaciones)

Sistema de comunicados oficiales.

**Funcionalidad:**
- Creación de comunicaciones con editor de texto
- Prioridades (normal, alta, urgente)
- Tipos de destinatario: todo el colegio, profesores, estudiantes, grados, cursos
- Programación de publicaciones futuras
- Estados: borrador, programado, publicado, archivado
- Acuse de recibo por destinatario
- Estadísticas de lectura
- API para consulta de pendientes (polling)

### 3.7 Canales (Chat interno)

Sistema de mensajería interna por canales.

**Funcionalidad:**
- Canales por tipo: institucional, rectoría, profesores, director_curso, curso, materia
- Asignación automática de miembros según tipo
- Mensajes con archivos adjuntos
- Reacciones (👍, ✅, ❓, 📌, ❤)
- Mensajes fijados
- Edición de mensajes (5 min de ventana)
- Eliminación lógica de mensajes
- Indicador de escritura (typing)
- Estado de lectura por mensaje
- Biblioteca del canal (archivos y enlaces)
- Búsqueda en el canal
- Lecturas: quién ha leído qué

### 3.8 Calificaciones

Sistema de notas con ponderación automática.

**Funcionalidad:**
- Creación de actividades por materia, curso, jornada y período
- Registro de notas por actividad
- Evaluación (25%) y autoevaluación (10%) por período
- Promedios ponderados automáticos (actividades 65% + evaluación 25% + autoevaluación 10%)
- Bloqueo de edición cuando el período está cerrado
- Alertas de bajo rendimiento

### 3.9 Horarios

Sistema de gestión horaria.

**Funcionalidad:**
- Vista por curso y jornada
- Edición inline (día, franja, materia, profesor)
- 5 días hábiles (lunes a viernes)
- Vista para el rector (global)
- Vista para el docente (sus materias)
- Vista para el estudiante

### 3.10 Boletines PDF

Generación de reportes académicos.

**Funcionalidad:**
- Generación individual o masiva
- Formato: ReportLab + PyPDF (para combinar múltiples PDFs)
- Colores institucionales (primario, secundario)
- Promedio ponderado por materia
- Promedio general con estado (Aprobado/Reprobado)
- Descarga directa
- Envío por email a acudientes

### 3.11 Solicitudes de Modificación

Flujo de aprobación para cambios de notas.

**Funcionalidad:**
- Creación por parte del docente con motivo
- Campos: nota de actividad, evaluación o autoevaluación
- Revisión por rector (aprobar/rechazar)
- Respuesta con retroalimentación
- Registro en auditoría

### 3.12 Cierre de Períodos

Control de apertura y cierre de períodos académicos.

**Funcionalidad:**
- Apertura y cierre desde configuración del rector
- Bloqueo de edición de notas en períodos cerrados
- Registro de quién y cuándo cerró/abrió
- Trazabilidad en auditoría

### 3.13 Configuración Institucional

Parámetros configurables por institución.

**Funcionalidad:**
- Tipo de evaluación (numérica)
- Escala mínima/máxima (1.0-10.0)
- Nota mínima para aprobar (6.0)
- Decimales de notas (1)
- Número de períodos (4)
- Jornadas personalizables
- Nombres de roles personalizables
- Acuse de recibo

### 3.14 Auditoría

Sistema de trazabilidad de acciones.

**Funcionalidad:**
- Registro automático en notas, evaluaciones, solicitudes, períodos
- Vista para rector con paginación (50 por página)
- Filtro por tabla
- Columnas: usuario, acción, tabla, valores anterior/nuevo, IP, fecha

### 3.15 Recuperación de Contraseña

Sistema de recuperación basado en preguntas secretas.

**Funcionalidad:**
- Para profesores (vía formulario con pregunta secreta)
- Para directoras (vía AJAX)
- Para rectores (vía AJAX)
- Protección contra fuerza bruta
- Migración automática de hash (SHA256 → bcrypt) al iniciar sesión

### 3.16 Reportes

Estadísticas básicas para el rector.

**Funcionalidad:**
- Totales: estudiantes, profesores, cursos, directoras
- Visualización en panel de rector

### 3.17 Backups

Sistema de copias de seguridad automáticas.

**Funcionalidad:**
- Copia diaria de todas las bases de datos
- Almacenamiento en `backups/`
- Nombres con fecha (`master_2026-06-29.db`)

---

## 4. Funciones por Módulo

### 4.1 Administrador Global

| Aspecto | Detalle |
|---------|---------|
| **Pantallas** | Login admin, Panel admin, Códigos de invitación |
| **Rutas** | `/admin` (GET/POST), `/admin/logout`, `/admin/codigos` (GET/POST), `/admin/codigos/<slug>` (GET/POST), `/admin/profesores/<slug>` (GET) |
| **Tablas** | `colegios` (master.db) |
| **Permisos** | Acceso global por contraseña maestra (`ADMIN_PASSWORD`) |
| **APIs** | API JSON para listar profesores por institución |

### 4.2 Rector

| Aspecto | Detalle |
|---------|---------|
| **Pantallas** | Login, Panel, Horarios, Profesores, Estudiantes, Cursos, Reportes, Configuración, Solicitudes, Auditoría, Comunicaciones, Canales, Gestión de Rectores |
| **Rutas** | ~25 rutas (ver sección 11) |
| **Tablas** | `rectores`, `alumnos`, `profesores`, `horarios_curso`, `comunicaciones`, `comunicaciones_leidas`, `canales`, `canal_miembros`, `audit_log`, `config_institucion`, `periodos_estado`, `solicitudes_modificacion` |
| **Permisos** | `['*']` (todos los permisos en su institución) |
| **APIs** | `/rector/horarios/datos` (JSON) |

### 4.3 Coordinador (Directora)

| Aspecto | Detalle |
|---------|---------|
| **Pantallas** | Login, Panel con tabla de notas, generación de PDF |
| **Rutas** | `/directora/login`, `/directora/registrar_directo`, `/directora/panel`, `/directora/boletin_pdf`, `/directora/logout`, `/directora/enviar_correos`, `/directora/guardar_email`, `/directora/crear_desde_panel` |
| **Tablas** | `directoras`, `alumnos`, `actividades`, `notas`, `evaluaciones` |
| **Permisos** | Acceso a su curso asignado |

### 4.4 Docente

| Aspecto | Detalle |
|---------|---------|
| **Pantallas** | Home (dashboard con alumnos, notas, actividades, agenda), Archivados, Cambiar contraseña, Horarios, Transferir curso |
| **Rutas** | ~20 rutas |
| **Tablas** | `profesores`, `alumnos`, `actividades`, `notas`, `evaluaciones`, `asistencia`, `observaciones`, `compromisos`, `asignaciones_materia`, `asignaciones_curso` |
| **Permisos** | `academic.grades.view/write`, `academic.attendance.*`, `academic.observations.write`, `academic.evaluations.*`, `academic.activities.*`, `communication.channels.*` |

### 4.5 Estudiante

| Aspecto | Detalle |
|---------|---------|
| **Pantallas** | Portal del estudiante (dashboard con notas, asistencia, horario) |
| **Rutas** | `/estudiante` |
| **Tablas** | `alumnos`, `notas`, `evaluaciones`, `asistencia`, `observaciones`, `horarios_curso`, `compromisos` |
| **Permisos** | `academic.grades.view`, `academic.attendance.view`, `communication.*.view` |

---

## 5. Base de Datos

### 5.1 master.db (Base maestra)

| Tabla | Propósito | Campos clave |
|-------|-----------|-------------|
| `colegios` | Registro de instituciones educativas | slug, nombre, logo, activo, vencimiento, num_periodos, códigos de acceso, colors |

### 5.2 {slug}.db (Base por institución)

#### Tablas legacy (activas y en uso)

| Tabla | Propósito | Relaciones |
|-------|-----------|-----------|
| `profesores` | Docentes de la institución | — |
| `alumnos` | Estudiantes | — |
| `directoras` | Coordinadoras académicas | — |
| `rectores` | Directivos institucionales | — |
| `actividades` | Evaluaciones/actividades por materia | FK: profesor_id |
| `notas` | Calificaciones por actividad y alumno | FK: aid, actividad_id |
| `evaluaciones` | Evaluación y autoevaluación por período | FK: aid, profesor_id |
| `asistencia` | Registro diario de asistencia | FK: aid |
| `observaciones` | Observaciones por estudiante | FK: aid |
| `compromisos` | Agenda académica (trabajos) | — |
| `asignaciones_materia` | Materias asignadas a profesores | FK: profesor_id |
| `asignaciones_curso` | Cursos asignados a profesores | FK: profesor_id |
| `horarios_curso` | Horarios semanales | — |

#### Tablas nuevas (Fase de migración)

| Tabla | Propósito | Relaciones |
|-------|-----------|-----------|
| `usuarios` | Usuarios unificados (en migración) | — |
| `roles_base` | Roles del sistema (6 fijos) | — |
| `roles_instancia` | Roles personalizados por institución | — |
| `usuarios_roles` | Asignación de roles a usuarios | FK: usuario_id, rol_id |
| `config_institucion` | Configuración institucional | — |
| `audit_log` | Registro de auditoría | — |
| `estructura_academica` | Jerarquía académica configurable | — |
| `curso_nuevo` | Cursos nuevo modelo | — |
| `materias` | Materias nuevo modelo | — |
| `curso_materias` | Asignación materias-cursos | — |
| `password_resets` | Tokens de recuperación | FK: usuario_id |
| `schema_meta` | Versiones de esquema aplicadas | — |

#### Tablas de comunicación (Fase 5 - Chat/Canales)

| Tabla | Propósito | Relaciones |
|-------|-----------|-----------|
| `comunicaciones` | Comunicados oficiales | FK: rector_id |
| `comunicaciones_leidas` | Registro de lectura de comunicados | FK: comunicacion_id |
| `notificaciones` | Notificaciones del sistema | — |
| `canales` | Canales de chat | FK: rector_id |
| `canal_miembros` | Miembros de cada canal | FK: canal_id |
| `mensajes_canal` | Mensajes en canales | FK: canal_id, responde_a |
| `mensajes_leidos` | Lectura de mensajes | FK: mensaje_id |
| `mensajes_archivos` | Archivos adjuntos | FK: canal_id, mensaje_id |
| `mensajes_reacciones` | Reacciones a mensajes | FK: mensaje_id |
| `mensajes_fijados` | Mensajes fijados | FK: canal_id, mensaje_id |
| `canal_enlaces` | Enlaces guardados | FK: canal_id |
| `canal_actividad` | Estado de actividad en canales | FK: canal_id |

#### Tablas académicas adicionales

| Tabla | Propósito | Relaciones |
|-------|-----------|-----------|
| `periodos_estado` | Estado de apertura/cierre de períodos | — |
| `solicitudes_modificacion` | Solicitudes de cambio de notas | FK: aid, actividad_id, solicitado_por |

---

## 6. Roles

### 6.1 Lista de roles

| Rol (código) | Nivel | Descripción | Pantalla login |
|--------------|-------|-------------|----------------|
| **admin** | 0 | Administrador global del sistema | `/admin` |
| **rector** | 1 | Máxima autoridad institucional | `/{slug}/rector/login` |
| **authority** | 2 | Coordinador académico (directora) | `/{slug}/directora/login` |
| **teacher** | 3 | Docente | `/{slug}/login` (pestaña profesor) |
| **student** | 4 | Estudiante | `/{slug}/login` (pestaña estudiante) |
| **guardian** | 5 | Acudiente | **No implementado como login separado** |

### 6.2 Jerarquía

```
admin (nivel 0) → acceso a TODO
  └── rector (nivel 1) → todos los permisos en su institución
       └── authority (nivel 2) → permisos delegados sobre cursos asignados
            └── teacher (nivel 3) → permisos sobre sus materias y cursos
                 └── student (nivel 4) → solo vista de sus propios datos
                      └── guardian (nivel 5) → NO IMPLEMENTADO
```

### 6.3 Estado de implementación del sistema de roles

- El sistema RBAC está implementado (tablas, permisos, decorador `@requiere_permiso`)
- Pero las rutas legacy **NO usan** el sistema de permisos nuevo (usan verificaciones de sesión directas)
- Los roles `authority` y `guardian` existen en la base de datos pero **no tienen flujo operativo completo**

---

## 7. Sistema de Comunicación

### 7.1 Centro de Avisos (Comunicados)

**Estado:** COMPLETO

- CRUD completo de comunicaciones
- Tipos de destinatario: todo_colegio, profesores, directores, estudiantes, grado, cursos
- Prioridades: normal, alta, urgente
- Estados: borrador, programado, publicado, archivado
- Acuse de recibo (leído/no leído con fecha)
- Estadísticas de lectura (totales, leídos, no leídos)
- API polling (`/api/comunicaciones`, `/api/comunicaciones/count`)
- Marcar como leído vía POST

### 7.2 Canales (Chat)

**Estado:** COMPLETO (Fase 5 implementada)

- 6 tipos de canal: institucional, rectoría, profesores, director_curso, curso, materia
- Asignación automática de miembros
- Mensajes con respuesta en hilo (responde_a)
- Archivos adjuntos (PDF, DOC, XLS, imágenes, etc.)
- Reacciones (👍, ✅, ❓, 📌, ❤)
- Mensajes fijados
- Edición (5 min de ventana)
- Eliminación lógica
- Indicador de escritura (typing)
- Estado online/offline/typing
- Lecturas por mensaje
- Biblioteca del canal (archivos + enlaces)
- Búsqueda por texto, autor, fecha
- API REST completa

### 7.3 Notificaciones

**Estado:** COMPLETO

- Sistema de notificaciones interno
- Creación desde cualquier módulo
- Contador de no leídas (vía API polling)
- Marcar como leída
- Vista unificada para todos los roles

### 7.4 Actualización automática

- Polling cada 30s (implementado en frontend vía `setInterval`)
- Comunicaciones pendientes se refrescan automáticamente
- Notificaciones no leídas con badge en sidebar

---

## 8. Sistema Académico

### 8.1 Notas

- Escala numérica (1.0 a 10.0)
- Edición inline en tabla
- Guardado con AJAX (POST `/guardar_nota`)
- Bloqueo en período cerrado (HTTP 423)
- Soporte para múltiples períodos
- Auditoría automática

### 8.2 Promedios

- Por actividad: promedio simple de notas
- Por materia: ponderado (65% actividades + 25% evaluación + 10% autoevaluación)
- General: promedio de todas las materias
- Visualización de estado: Aprobado (≥3.0) / Reprobado (<3.0)

### 8.3 Evaluaciones y Autoevaluaciones

- Evaluación del docente hacia el estudiante
- Autoevaluación del estudiante
- Por período y materia
- Guardado con upsert (INSERT ON CONFLICT UPDATE)

### 8.4 Actividades

- CRUD por materia, curso, jornada, período
- Orden numérico
- Asociación a un profesor específico

### 8.5 Períodos

- Configurable (default 4)
- Estados: abierto/cerrado
- Control desde panel del rector
- Bloqueo de edición en período cerrado

### 8.6 Boletines

- Generados con ReportLab
- Formato PDF individual o combinado (PyPDF)
- Colores institucionales
- Promedio general con indicador visual
- Envío por email a acudientes (SendGrid)

### 8.7 Alertas

- Estudiantes con bajo rendimiento (< 3.0)
- Inasistencias frecuentes (> 1 falta)
- Notas pendientes de registrar

---

## 9. Seguridad

### 9.1 CSRF

- Implementación manual con `secrets.token_hex(32)`
- Token almacenado en sesión
- Validación en todos los formularios POST
- Header `X-CSRF-Token` para APIs AJAX
- Inyectado en Jinja como `{{ csrf_token() }}`

### 9.2 Rate Limiting

- Protección contra fuerza bruta por IP
- 5 intentos fallidos → bloqueo de 5 minutos
- Contextos separados por endpoint (admin, login, recuperación, rector, directora)
- Purga automática de intentos antiguos (>1h)

### 9.3 Sesiones

- Cookie con HttpOnly, SameSite=Lax
- Secure configurable vía variable de entorno
- Lifetime: 4 horas
- Secret key desde variable de entorno o generada aleatoriamente

### 9.4 Permisos

- Sistema RBAC implementado (aunque no aplicado en todas las rutas legacy)
- Decorador `@requiere_permiso` para nuevas rutas
- Jerarquía de roles con herencia de permisos

### 9.5 Auditoría

- Registro de todas las acciones críticas
- Datos: quién, qué, cuándo, IP, agente
- Valores anterior y nuevo para trazabilidad completa

### 9.6 Protección de rutas

- Función `require_colegio(slug)`: verifica que el slug exista y esté activo
- Verificación de rol en cada ruta (vía session o helper)
- Decorador `@requiere_permiso` para control granular

### 9.7 Backups

- Automáticos diarios
- Ubicación separada (`backups/`)

### 9.8 Contraseñas

- Hash: bcrypt (password nuevo) + SHA256+salt (legacy)
- Migración automática al iniciar sesión
- Recuperación vía pregunta secreta

### 9.9 Limitación de archivos

- `MAX_CONTENT_LENGTH`: 2 MB (global Flask)
- `max_tamano_archivo`: 10 MB (configurable por institución en canales)
- Extensiones permitidas (14 tipos de archivo)

---

## 10. Tecnologías Utilizadas

### 10.1 Backend

| Tecnología | Versión | Propósito |
|-----------|---------|-----------|
| Python | 3.x | Lenguaje principal |
| Flask | 3.x | Framework web |
| Jinja2 | 3.x | Motor de templates |
| gunicorn | 26.x | Servidor WSGI producción |
| python-dotenv | 1.x | Variables de entorno |
| bcrypt | 5.x | Hashing de contraseñas |
| ReportLab | 5.x | Generación de PDFs |
| PyPDF | — | Combinar PDFs |
| SendGrid | 6.x | Envío de emails |
| Pillow | 12.x | Procesamiento de imágenes |
| Werkzeug | 3.x | Utilidades WSGI |
| Blinker | — | Señales (Flask) |

### 10.2 Frontend

| Tecnología | Propósito |
|-----------|-----------|
| HTML5 | Estructura |
| CSS3 (vanilla) | Estilos con variables CSS |
| JavaScript (vanilla) | Interactividad, AJAX, polling |
| Font Awesome 6.5.0 | Íconos (vía CDN) |
| Google Fonts (Inter) | Tipografía |
| Service Worker | PWA básica |
| Manifest.json | PWA instalable |

### 10.3 Base de datos

| Tecnología | Propósito |
|-----------|-----------|
| SQLite 3 | Motor de base de datos |
| WAL mode | Concurrencia de escritura |

### 10.4 Infraestructura

| Componente | Detalle |
|-----------|---------|
| Servidor | Flask dev / Gunicorn |
| Ambiente | Variables .env |
| Logging | Archivo `lumini.log` + stdout |

---

## 11. Funciones Pendientes

### Prioridad ALTA (Crítico para v1.0)

1. **Refactorizar flask_app.py en módulos separados** — El archivo monolítico de 4.490 líneas es insostenible. Separar en blueprints: admin, auth, docentes, estudiantes, rector, comunicaciones, canales, api.

2. **Migrar completamente al nuevo modelo de usuarios** — Unificar las 4 tablas legacy (profesores, alumnos, directoras, rectores) en `usuarios` con asignación de roles flexible.

3. **Aplicar el sistema de permisos en TODAS las rutas** — Actualmente las rutas legacy no usan `@requiere_permiso`, solo verifican sesión.

4. **Login para acudientes (guardian)** — El rol existe en BD pero no tiene flujo de login ni vista.

5. **Recuperación de contraseña vía email** — Actualmente solo usa preguntas secretas. Falta el flujo con token por email.

6. **Pruebas automatizadas** — No existe ningún test unitario ni de integración.

### Prioridad MEDIA (Para v1.1)

7. **Panel de authority (coordinador)** — El rol existe pero no tiene ruta dedicada (solo directora que es un caso específico).

8. **Exportación a Excel/CSV** — No existe exportación de datos.

9. **Dashboard de administrador global mejorado** — Actualmente es muy básico.

10. **Editor de texto enriquecido** — Las comunicaciones usan texto plano.

11. **Notificaciones push** — Actualmente solo notificaciones in-app.

12. **Multilenguaje** — Solo español.

13. **Logs de acceso** — No se registran inicios de sesión en auditoría.

### Prioridad BAJA (Para v2.0+)

14. **Jerarquía académica completa** — El modelo de datos existe pero no hay UI.

15. **Gestión de sedes/múltiples campus**

16. **Calendario académico** — No hay vista de calendario.

17. **QR para asistencia**

18. **App móvil / PWA avanzada**

19. **Migración a PostgreSQL**

20. **Plan de suscripción/facturación**

21. **Biblioteca digital**

22. **Módulo de bienestar/convivencia**

23. **API pública REST**

---

## 12. Roadmap

### 12.1 Para v1.0 (Corto plazo)

- [ ] Refactorizar `flask_app.py` en blueprints (módulos separados por rol)
- [ ] Completar migración a modelo unificado de usuarios
- [ ] Aplicar permisos RBAC en rutas legacy
- [ ] Login para acudientes
- [ ] Pruebas básicas (al menos 1 test por módulo principal)
- [ ] Recuperación de contraseña por email
- [ ] Mejorar manejo de errores y logging

### 12.2 Para v1.1 (Mediano plazo)

- [ ] Panel de coordinador académico completo
- [ ] Exportación de datos (Excel, CSV)
- [ ] Editor de texto enriquecido en comunicaciones
- [ ] Notificaciones push (Web Push API)
- [ ] Dashboard analítico con gráficos
- [ ] Multilenguaje
- [ ] Optimización de rendimiento (caching, consultas)

### 12.3 Para v2.0 (Largo plazo)

- [ ] Jerarquía académica completa (facultades, programas)
- [ ] API REST pública
- [ ] App móvil nativa
- [ ] Migración a PostgreSQL
- [ ] Sistema de suscripción y facturación
- [ ] Calendario académico interactivo
- [ ] Módulo de biblioteca digital
- [ ] Módulo de bienestar
- [ ] Integración con Google Calendar / Microsoft 365

---

## 13. Estadísticas del Proyecto

### 13.1 Rutas Flask

**Aproximadamente 110+ rutas** distribuidas así:

| Categoría | Cantidad |
|-----------|----------|
| Admin global | 5 |
| Login/Auth general | 5 |
| Recuperación de contraseña | 5 |
| Docente (home, notas, actividades, etc.) | ~25 |
| Estudiante | 1 |
| Directora | 8 |
| Rector (panel, profesores, estudiantes, etc.) | ~20 |
| Comunicaciones | 8 |
| Canales (gestión) | 5 |
| API Canales (mensajes, archivos, reacciones) | ~18 |
| API Comunicaciones/Notificaciones | 4 |
| Gestión de rectores | 6 |
| Estáticos/Error | 5 |

### 13.2 Templates

| Métrica | Valor |
|---------|-------|
| Total de templates | 33 |
| Líneas totales en templates | ~9.938 |
| Template más grande | `estudiante.html` (1.181 líneas) |
| Template más pequeño | `error.html` (41 líneas) |

### 13.3 Base de datos

| Métrica | Valor |
|---------|-------|
| Tablas en master.db | 1 (`colegios`) |
| Tablas por institución | ~30+ |
| Tablas legacy | ~12 |
| Tablas nuevas (migración) | ~10 |
| Tablas de comunicación (Fase 5) | ~8 |
| SCHEMA_VERSION actual | 10 |

### 13.4 APIs

| Tipo | Cantidad |
|------|----------|
| API JSON (canales, mensajes) | ~18 endpoints |
| API JSON (notificaciones) | 2 endpoints |
| API JSON (comunicaciones) | 2 endpoints |
| API JSON (admin) | 1 endpoint |

### 13.5 Código

| Archivo | Líneas |
|---------|--------|
| `flask_app.py` | 4.490 |
| Templates (33 archivos) | 9.938 |
| `seed_rector.py` | 80 |
| `static/sw.js` | 6 |
| `static/manifest.json` | 16 |
| `.env` | 6 |
| `requirements.txt` | 8 |
| Archivos legacy (`_legacy/`) | ~500+ |
| Documentación (`docs/`) | ~1.500+ |
| **Total proyecto (excluyendo .venv)** | **~16.000+** |

### 13.6 Archivos

| Tipo | Cantidad |
|------|----------|
| Python (.py) | 2 principales + 8 legacy |
| HTML templates | 33 |
| JavaScript | 1 (sw.js, 6 líneas) |
| CSS | 0 archivos separados (todo inline en templates) |
| Documentación (MD) | 4 archivos |
| Configuración | 3 archivos |
| **Total archivos del proyecto** | **~50+** |

---

## 14. Conclusión

### 14.1 Evaluación del estado del proyecto

LUMINI es un **proyecto funcional y maduro en su núcleo** pero que se encuentra en una **fase de transición crítica** entre un modelo legacy de 4 tablas de usuarios y un nuevo modelo unificado con RBAC, auditoría y configuración institucional.

**Fortalezas del proyecto:**
- Sistema multi-tenant funcional con aislamiento de datos por institución
- Cobertura funcional amplia (académico, comunicación, administración)
- Sistema de comunicación moderno con canales, archivos, reacciones
- Generación de PDFs y envío por email
- Sistema de permisos RBAC ya implementado (aunque no en uso completo)
- Auditoría de acciones críticas implementada
- Backups automáticos
- Protección contra fuerza bruta
- Código CSS/JS sin dependencias externas pesadas
- Diseño visual moderno y consistente (tema oscuro)

**Debilidades del proyecto:**
- Arquitectura monolítica extrema (todo en `flask_app.py`)
- No hay pruebas automatizadas
- Sistema de permisos RBAC no aplicado a rutas legacy
- Migración de tablas de usuarios incompleta (coexisten 2 modelos)
- Autenticación fragmentada (4 formas distintas de login)
- Sin API pública REST
- Sin exportación de datos (Excel/CSV)
- El login de estudiantes por nombre es inseguro (no hay contraseña real)
- No hay registro de intentos de login en auditoría
- Sin tests de ningún tipo
- Las contraseñas de estudiantes (PIN) son débiles
- El acudiente no tiene portal propio

### 14.2 Recomendaciones inmediatas

1. **Refactorizar flask_app.py** en módulos separados (blueprints) como paso previo a cualquier feature nueva. Es el mayor riesgo técnico.

2. **Completar la migración del modelo de usuarios** para eliminar la deuda técnica de las 4 tablas legacy.

3. **Aplicar el sistema de permisos en todas las rutas existentes** antes de agregar nuevas funcionalidades.

4. **Agregar pruebas automatizadas** comenzando por los flujos críticos (login, notas, comunicaciones).

5. **Implementar login seguro para estudiantes** (email + password en lugar de nombre + PIN opcional).

6. **Corregir la seguridad de sesiones** (actualmente `SESSION_COOKIE_SECURE` default false).

### 14.3 Veredicto final

LUMINI es un sistema educativo **funcionalmente rico pero técnicamente endeudado**. Tiene el potencial de ser un producto competitivo en el mercado de software educativo, pero requiere una inversión significativa en refactorización y calidad de código antes de alcanzar una versión 1.0 estable y mantenible. La base funcional es sólida; la deuda técnica es la principal barrera para el crecimiento.

---

*Documento generado el 29 de junio de 2026.*
*Auditoría basada en el código fuente en `C:\Users\PC\OneDrive\Documentos\GitHub\Lumini\`*
