# LUMINI — Mapa Legacy vs Nueva Arquitectura

> Documento de referencia para identificar qué pertenece al sistema legacy, qué a la nueva arquitectura, y en qué estado está cada transición.
>
> Actualizado: 27 de junio de 2026 — Post-P0.4

---

## 1. Base de datos

### Master DB (`master.db`)

| Tabla | Estado | Notas |
|-------|--------|-------|
| `colegios` | Legacy | Nombre pendiente de migrar a `instituciones`. Tiene columna `schema_version` agregada en P0.1. |

### Per-Instance DB (`{slug}.db`)

#### Tablas Legacy (NO migrar — se mantienen)

| Tabla | Propósito | Dependencias |
|-------|-----------|-------------|
| `profesores` | Docentes (login legacy) | Rutas de profesor, canales, asignaciones |
| `alumnos` | Estudiantes (login legacy) | Rutas de estudiante, notas, asistencia |
| `rectores` | Rectores (login legacy) | Rutas de rector |
| `directoras` | Directoras (login legacy) | Rutas de directora |
| `asignaciones_materia` | Asignación materia a profesor | Login legacy de profesor |
| `asignaciones_curso` | Asignación curso a profesor | Login legacy de profesor |
| `asistencia` | Asistencia (con `aid` legacy) | Rutas de profesor |
| `actividades` | Actividades legacy (con `profesor_id`) | Libreta de notas |
| `notas` | Notas legacy (con `aid` y `actividad_id`) | Libreta de notas |
| `evaluaciones` | Evaluaciones legacy (con `aid`) | Libreta de notas |
| `observaciones` | Observaciones legacy (con `aid`) | Libreta de notas |
| `compromisos` | Compromisos legacy | — |
| `horarios_curso` | Horarios legacy (con texto, no FK) | Vista de horarios |
| `comunicaciones` | Comunicados legacy (`rector_id`) | Centro de comunicaciones |
| `comunicaciones_leidas` | Lectura de comunicados | Centro de comunicaciones |
| `canales` | Canales legacy (`slug`, `rector_id`, `curso`/`materia` texto) | Sistema de canales |
| `canal_miembros` | Miembros legacy (`usuario_tipo`+`usuario_id` texto) | Sistema de canales |
| `mensajes_canal` | Mensajes legacy | Sistema de canales |
| `mensajes_leidos` | Lectura legacy | Sistema de canales |
| `notificaciones` | Notificaciones legacy | Badge, campana |

#### Tablas Nuevas (Arquitectura P0) — Versiones 6-10

| Tabla | Versión | Propósito | Estado |
|-------|---------|-----------|--------|
| `schema_meta` | 6 | Control de versiones de esquema | ✅ Operativa |
| `usuarios` | 6 | Usuarios unificados (futuro reemplazo de profesores/alumnos/rectores/directoras) | 🗄 Creada, vacía |
| `roles_base` | 7 | Definiciones de roles del sistema (6 roles) | ✅ Datos sembrados |
| `roles_instancia` | 7 | Roles personalizados por institución | 🗄 Creada, vacía |
| `usuarios_roles` | 8 | Asignación de roles a usuarios | 🗄 Creada, vacía |
| `password_resets` | 8 | Tokens de recuperación de contraseña | 🗄 Creada, vacía |
| `config_institucion` | 9 | Configuración institucional (escala, períodos, roles, jornadas) | ✅ Datos sembrados |
| `audit_log` | 10 | Registro de auditoría | 🗄 Creada, vacía |
| `estructura_academica` | 10 | Nodos jerárquicos (facultades, programas) | 🗄 Creada, vacía |
| `curso_nuevo` | 10 | Cursos con FK a estructura (futuro reemplazo de curso texto) | 🗄 Creada, vacía |
| `materias` | 10 | Catálogo de materias | 🗄 Creada, vacía |
| `curso_materias` | 10 | Asignación materia-curso-docente | 🗄 Creada, vacía |

**Leyenda**: ✅ Operativa / 🗄 Creada sin datos / ❌ Pendiente

---

## 2. Autenticación y Sesiones

| Componente | Legacy | Nueva | Estado |
|-----------|--------|-------|--------|
| Login rector | `/<slug>/rector/login` — usuario+password | Pendiente | ✅ Legacy activo |
| Login directora | `/<slug>/directora/login` — usuario+password | Pendiente | ✅ Legacy activo |
| Login profesor | `/<slug>/login` — usuario+password (pestaña) | Pendiente | ✅ Legacy activo |
| Login estudiante | `/<slug>/login` — nombre+pin (pestaña) | Pendiente | ✅ Legacy activo |
| Sesión rector | `session['rector_id_{slug}']` | Pendiente | ✅ Legacy activo |
| Sesión profesor | `session['profesor_id_{slug}']` | Pendiente | ✅ Legacy activo |
| Sesión estudiante | `session['alumno_id_{slug}']` | Pendiente | ✅ Legacy activo |
| Sesión directora | `session['directora_id_{slug}']` | Pendiente | ✅ Legacy activo |
| Recuperación | Preguntas secretas | Email con token (P0.5) | ✅ Legacy activo |
| Fuerza bruta | `login_intentos` por IP | Mismo sistema | ✅ Operativo |

---

## 3. Permisos

| Componente | Legacy | Nueva | Estado |
|-----------|--------|-------|--------|
| Control de acceso | Por ruta (cada función valida su sesión) | RBAC con `tiene_permiso()` | 🗄 Nuevo listo, no integrado |
| Decorador | No existe | `@requiere_permiso()` | 🗄 Definido, no usado |
| Roles | Fijos en código (profesor/alumno/rector/directora) | 6 roles base + personalizables | 🗄 Tablas listas |

---

## 4. Rutas y Templates

| Grupo | Legacy | Nueva | Estado |
|-------|--------|-------|--------|
| Admin global | `/admin` | — | ✅ Legacy |
| Rector | `/rector/*` (16 rutas) | — | ✅ Legacy |
| Directora | `/directora/*` | — | ✅ Legacy |
| Profesor | `/profesor/*` + `index.html` | — | ✅ Legacy |
| Estudiante | `estudiante.html` | — | ✅ Legacy |
| API canales | `/api/canales/*` | — | ✅ Legacy |
| API comunicaciones | `/api/comunicaciones/*` | — | ✅ Legacy |
| Config rector | `rector_configuracion.html` | Expandida con config institucional | ✅ Actualizada |
| Auditoría rector | — | `rector_auditoria.html` | ✅ Nueva |

---

## 5. Funciones Helpers

| Función | Legacy | Nueva | Estado |
|---------|--------|-------|--------|
| `get_profesor()` | ✅ | — | Legacy |
| `get_rector()` | ✅ | — | Legacy |
| `get_directora()` | ✅ | — | Legacy |
| `get_usuario_actual()` | ✅ | — | Legacy (combina 4 tablas) |
| `tiene_permiso()` | — | ✅ | Nueva, no integrada |
| `audit_log()` | — | ✅ | Nueva |
| `config_get()` | — | ✅ | Nueva |
| `config_get_nombre_rol()` | — | ✅ | Nueva |

---

## 6. Próximas migraciones planificadas

| Hito | Tablas involucradas | Estrategia |
|------|---------------------|-----------|
| P0.5 Login | `usuarios`, `password_resets` | Crear login unificado junto a legacy. No desactivar legacy. |
| P0.6 Sesiones | `usuarios_roles` | Sesión unificada `user_id + slug`. Migrar helpers. |
| Futuro | `profesores` → `usuarios` | Script de migración de datos. Mantener tablas legacy 2 versiones. |
| Futuro | `alumnos` → `usuarios` | Script de migración de datos. |
| Futuro | `rectores`, `directoras` → `usuarios` | Script de migración de datos. |
| Futuro | `colegios` → `instituciones` | Renombrar tabla en master.db. |
| Futuro | `aid` en notas/asistencia → `usuario_id` | Migrar FK a nuevo esquema. |

---

## 7. Principios de convivencia

1. **No eliminar tablas legacy** hasta que toda funcionalidad haya sido migrada y probada.
2. **Toda tabla nueva** usa `CREATE TABLE IF NOT EXISTS` — no interfiere con legacy.
3. **Toda función nueva** que interactúa con legacy debe mantener compatibilidad hacia atrás.
4. **El sistema legacy sigue siendo funcional** — no hay presión por migrar.
5. **La migración de datos** es un script manual supervisado, no automático.
