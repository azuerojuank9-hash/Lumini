# LUMINI — Arquitectura Funcional v2.0

> **Identidad**: Ecosistema integral para la gestión, operación y comunicación de instituciones educativas.
>
> LUMINI no es un LMS. No es un chat. No es un ERP.
> Es el sistema operativo de la institución educativa.

---

## Índice

1. [Visión del Producto](#1-visión-del-producto)
2. [Arquitectura de Módulos](#2-arquitectura-de-módulos)
3. [Modelo de Datos](#3-modelo-de-datos)
   - 3.1 Modelo de Institución
   - 3.2 Modelo de Usuario
   - 3.3 Modelo de Roles
   - 3.4 Modelo de Configuración
4. [Sistema de Permisos](#4-sistema-de-permisos)
5. [Mapa de Navegación por Rol](#5-mapa-de-navegación-por-rol)
6. [Estrategia de Migración](#6-estrategia-de-migración)
7. [Riesgos y Oportunidades](#7-riesgos-y-oportunidades)
8. [Recomendaciones](#8-recomendaciones)

---

## 1. Visión del Producto

### 1.1 Declaración de identidad

**LUMINI** es un ecosistema integral para la gestión, operación y comunicación de instituciones educativas. Proporciona una plataforma unificada donde cada actor institucional — desde la dirección hasta los estudiantes — encuentra las herramientas que necesita para su día a día, sin depender de aplicaciones externas ni procesos manuales.

### 1.2 Problema que resuelve

Las instituciones educativas operan con un promedio de 3 a 7 herramientas desconectadas:

| Área | Herramienta típica | Problema |
|------|-------------------|----------|
| Comunicación interna | WhatsApp, Telegram | Sin trazabilidad, mezcla asuntos personales con institucionales |
| Notas y evaluación | Excel, papel | Doble digitación, errores, sin historial |
| Comunicados oficiales | Correo, circulares | Sin control de lectura, sin destinatarios inteligentes |
| Asistencia | Papel, Excel | Sin consolidación automática |
| Observaciones | Papel, cuaderno | Sin línea de tiempo por estudiante |
| Reportes | Excel, procesador de texto | Hecho a mano cada período |

**LUMINI elimina la fragmentación.** Todo ocurre dentro de un mismo ecosistema con trazabilidad completa.

### 1.3 Principios rectores

1. **Integración**: cada módulo se conecta con los demás. No hay silos de información.
2. **Trazabilidad**: cada acción queda registrada con quién, cuándo y qué cambió.
3. **Configurabilidad**: la institución define su propia estructura, roles, escalas y períodos.
4. **Escalabilidad vertical**: funciona para un colegio de 100 estudiantes y para una universidad de 10,000.
5. **Neutralidad institucional**: no impone nombres ni estructuras. Cada institución adapta el sistema a su realidad.
6. **Profesionalismo**: la experiencia de usuario debe transmitir orden, seriedad y modernidad.

### 1.4 Criterios de aprobación de nuevas funcionalidades

Toda nueva funcionalidad debe responder afirmativamente estas seis preguntas:

1. **Problema**: ¿Qué problema institucional real resuelve?
2. **Integración**: ¿Cómo se conecta con el resto del ecosistema?
3. **Universalidad**: ¿Funciona tanto en colegios como en universidades?
4. **Escalabilidad**: ¿Crece bien con la institución?
5. **Trazabilidad**: ¿Genera registros auditable?
6. **Productividad**: ¿Ahorra tiempo o reduce errores comparado con el método anterior?

Si no cumple los seis criterios, no se implementa.

---

## 2. Arquitectura de Módulos

```
LUMINI
│
├── NÚCLEO (Core) ─── P0
│   ├── Institución
│   │   ├── Registro y configuración inicial
│   │   ├── Branding (logo, colores, nombre)
│   │   ├── Estados (activo, trial, suspendido, vencido)
│   │   └── Plan y suscripción (futuro)
│   │
│   ├── Identidad y Acceso
│   │   ├── Autenticación unificada (email + password)
│   │   ├── Recuperación de acceso (email con token)
│   │   ├── Sesión persistente multi-rol
│   │   └── Bloqueo por fuerza bruta
│   │
│   ├── Roles y Permisos
│   │   ├── Roles base del sistema (6 roles)
│   │   ├── Personalización de nombres por institución
│   │   ├── Jerarquía de roles configurable
│   │   └── Permisos granulares por rol
│   │
│   ├── Auditoría
│   │   ├── Log de cambios (tabla, registro, campo, valor anterior, valor nuevo)
│   │   ├── Log de acceso (inicio de sesión, cierre, IP, agente)
│   │   └── Log de acciones (crear, editar, eliminar, publicar)
│   │
│   └── Notificaciones (motor interno)
│       ├── Generación de notificaciones desde cualquier módulo
│       ├── Destinatarios por rol, entidad o usuario
│       ├── Estados (no leída, leída, archivada)
│       └── Canales de entrega (in-app, email futuro, push futuro)
│
├── GESTIÓN INSTITUCIONAL ─── P1
│   ├── Personas
│   │   ├── Docentes (perfil, carga académica, estado)
│   │   ├── Estudiantes (perfil, historial, estado, acudientes)
│   │   └── Personal administrativo (perfil, roles delegados)
│   │
│   ├── Estructura Académica
│   │   ├── Sedes / Campus (opcional)
│   │   ├── Facultades / Departamentos (opcional)
│   │   ├── Programas / Carreras (opcional)
│   │   ├── Cohortes / Promociones (opcional)
│   │   ├── Cursos / Grupos (obligatorio)
│   │   └── Materias / Asignaturas (obligatorio)
│   │   └── [Modo plano o jerárquico según configuración]
│   │
│   └── Administración
│       ├── Gestión de usuarios (crear, editar, activar, archivar)
│       ├── Códigos de acceso por rol
│       └── Parámetros institucionales
│
├── GESTIÓN ACADÉMICA ─── P1/P2
│   ├── Desempeño
│   │   ├── Evaluaciones (rúbrica, tipo, peso, período)
│   │   ├── Actividades / Trabajos
│   │   ├── Notas (escala configurable)
│   │   ├── Promedios ponderados
│   │   └── Créditos académicos (opcional)
│   │
│   ├── Seguimiento
│   │   ├── Asistencia (por fecha, QR futuro)
│   │   ├── Observaciones (línea de tiempo por estudiante)
│   │   ├── Compromisos / Actas de acuerdo
│   │   └── Alertas tempranas (bajo rendimiento, inasistencias)
│   │
│   └── Planificación
│       ├── Horarios (vista tabla + calendario)
│       ├── Calendario académico (eventos, evaluaciones, feriados)
│       └── Distribución de carga académica
│
├── COMUNICACIÓN INSTITUCIONAL ─── P1
│   ├── Comunicados Oficiales
│   │   ├── Redacción con editor
│   │   ├── Prioridades (baja, normal, alta, urgente)
│   │   ├── Destinatarios inteligentes (por rol, curso, materia)
│   │   ├── Estados (borrador, programado, publicado, archivado)
│   │   ├── Acuse de recibo (leído / no leído por destinatario)
│   │   └── Plantillas reutilizables
│   │
│   └── Conversaciones
│       ├── Canales por tipo (institucional, curso, materia)
│       ├── Mensajería con polling en tiempo real
│       ├── Indicador de leídos por mensaje
│       ├── Menciones (@usuario)
│       └── Búsqueda de mensajes
│
├── ANALÍTICA Y REPORTES ─── P2/P3
│   ├── Dashboards
│   │   ├── Rector: KPIs institucionales
│   │   ├── Autoridad académica: comparativas entre cursos
│   │   ├── Docente: desempeño de sus grupos
│   │   └── Estudiante: progreso personal
│   │
│   ├── Reportes
│   │   ├── Actas académicas (PDF)
│   │   ├── Rendimiento por período (Excel, CSV)
│   │   ├── Asistencia consolidada
│   │   └── Historial de cambios
│   │
│   └── Exportación
│       ├── Por período o rango de fechas
│       └── Por curso, materia o estudiante
│
├── BIENESTAR ─── P4 (futuro, opcional)
│   ├── Encuestas de clima
│   ├── Reportes de convivencia
│   └── Canal de ayuda / denuncias
│
├── BIBLIOTECA DIGITAL ─── P4 (futuro, opcional)
│   ├── Repositorio de materiales por materia
│   ├── Control de versiones
│   └── Recursos compartidos
│
└── CALIDAD ─── P4 (futuro, opcional)
    ├── Indicadores de gestión
    ├── Planes de mejora
    └── Auto-evaluación institucional
```

---

## 3. Modelo de Datos

### 3.1 Modelo de Institución

```sql
-- Tabla: instituciones (reemplaza a "colegios" en master.db)
CREATE TABLE instituciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT UNIQUE NOT NULL,              -- identificador URL
    nombre      TEXT NOT NULL,                     -- nombre legal
    nombre_corto TEXT DEFAULT '',                   -- nombre comercial (opcional)
    activo      INTEGER DEFAULT 1,
    tipo        TEXT DEFAULT 'colegio',             -- colegio, universidad, instituto, centro
    creado      TEXT DEFAULT (date('now')),
    vencimiento TEXT,
    plan        TEXT DEFAULT 'basic',               -- basic, professional, enterprise (futuro)

    -- Branding
    logo        TEXT DEFAULT '',
    primary_color   TEXT DEFAULT '#7C3AED',
    secondary_color TEXT DEFAULT '#6D28D9',

    -- Configuración (referencia a tabla config)
    config_id   INTEGER,

    -- Códigos de acceso legacy
    codigo_registro     TEXT DEFAULT '',
    codigo_profesores   TEXT DEFAULT '',
    codigo_directoras   TEXT DEFAULT '',
    codigo_rectores     TEXT DEFAULT ''
);
```

### 3.2 Modelo de Usuario

**Cambio fundamental**: Unificar las 4 tablas actuales (`profesores`, `alumnos`, `directoras`, `rectores`) en una sola tabla `usuarios` con asignación de roles flexible.

```sql
-- Tabla: usuarios (en cada base de institución: slug.db)
CREATE TABLE usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL,                     -- institución a la que pertenece
    email       TEXT NOT NULL,                     -- único por institución
    password_hash TEXT,                            -- NULL para estudiantes sin email (migración)
    nombre      TEXT NOT NULL,
    apellido    TEXT DEFAULT '',
    tipo_documento TEXT DEFAULT '',                -- CC, CE, TI, Pasaporte
    documento   TEXT DEFAULT '',
    telefono    TEXT DEFAULT '',
    avatar      TEXT DEFAULT '',
    activo      INTEGER DEFAULT 1,
    creado      TEXT DEFAULT (datetime('now','localtime')),
    actualizado TEXT DEFAULT (datetime('now','localtime')),
    ultimo_acceso TEXT,
    UNIQUE(slug, email)
);

-- Índice para búsqueda
CREATE INDEX idx_usuarios_slug ON usuarios(slug);
CREATE INDEX idx_usuarios_nombre ON usuarios(slug, nombre, apellido);
```

### 3.3 Modelo de Roles

**Roles base del sistema** (definidos en código, no configurables en nombre pero sí en display):

| Código | Nivel | Propósito |
|--------|-------|-----------|
| `admin` | 0 | Administrador global del sistema (multi-institución) |
| `rector` | 1 | Máxima autoridad de la institución |
| `authority` | 2 | Autoridades académicas (coordinadores, decanos, directores de programa) |
| `teacher` | 3 | Docentes / Profesores / Instructores |
| `student` | 4 | Estudiantes / Alumnos / Participantes |
| `guardian` | 5 | Acudientes / Padres / Representantes |

```sql
-- Tabla: roles_instancia (personalización de nombres por institución)
CREATE TABLE roles_instancia (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL,                     -- institución
    codigo      TEXT NOT NULL,                     -- admin, rector, authority, teacher, student, guardian
    nombre      TEXT NOT NULL,                     -- nombre personalizado (ej. "Decano", "Instructor")
    jerarquia   INTEGER NOT NULL DEFAULT 1,        -- orden jerárquico dentro de la institución
    activo      INTEGER DEFAULT 1,
    UNIQUE(slug, codigo)
);
```

```sql
-- Tabla: usuarios_roles (asignación de roles a usuarios)
CREATE TABLE usuarios_roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    rol_id      INTEGER NOT NULL REFERENCES roles_instancia(id),

    -- Alcance del rol: NULL = global (ej. rector), o específico
    entidad_tipo TEXT DEFAULT NULL,                -- 'sede', 'facultad', 'programa', 'curso', 'materia'
    entidad_id  INTEGER DEFAULT NULL,

    -- Metadata
    asignado_por INTEGER,                          -- usuario_id que asignó el rol
    creado      TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(usuario_id, rol_id, entidad_tipo, entidad_id)
);

CREATE INDEX idx_usuarios_roles_usuario ON usuarios_roles(usuario_id);
CREATE INDEX idx_usuarios_roles_entidad ON usuarios_roles(entidad_tipo, entidad_id);
```

#### Ejemplos de asignación de roles

| Persona | Usuario | Rol | Alcance | Significado |
|---------|---------|-----|---------|-------------|
| María López | maria@email.com | `rector` | NULL | Rectora de toda la institución |
| Carlos Ruiz | carlos@email.com | `authority` | `programa` = 1 | Coordinador del programa de Ingeniería |
| Ana Gil | ana@email.com | `teacher` | `curso` = 5, `materia` = 12 | Docente de Matemáticas en 1°A |
| Pedro Sol | pedro@email.com | `student` | `curso` = 5 | Estudiante de 1°A |

#### Tabla: estructura_academica (soporte para jerarquía configurable)

```sql
CREATE TABLE estructura_academica (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL,                     -- institución
    nivel       INTEGER NOT NULL,                  -- 0=sede/1=facultad/2=programa/3=cohorte
    nombre      TEXT NOT NULL,
    nombre_tipo TEXT NOT NULL,                     -- personalizable: 'Sede', 'Facultad', 'Campus', etc.
    padre_id    INTEGER DEFAULT NULL,              -- NULL para nivel raíz
    activo      INTEGER DEFAULT 1,
    UNIQUE(slug, nivel, nombre)
);
```

```sql
-- Tabla: cursos (simplificada, cada curso se vincula a un nodo de estructura)
CREATE TABLE cursos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL,
    estructura_id INTEGER REFERENCES estructura_academica(id),
    nombre      TEXT NOT NULL,                     -- "1°A", "10-01", "Grupo A"
    jornada     TEXT DEFAULT 'Mañana',
    activo      INTEGER DEFAULT 1
);
```

```sql
-- Tabla: materias
CREATE TABLE materias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL,
    nombre      TEXT NOT NULL,
    activo      INTEGER DEFAULT 1,
    UNIQUE(slug, nombre)
);
```

```sql
-- Tabla: curso_materias (asignación de materias a cursos)
CREATE TABLE curso_materias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    curso_id    INTEGER NOT NULL REFERENCES cursos(id),
    materia_id  INTEGER NOT NULL REFERENCES materias(id),
    docente_id  INTEGER REFERENCES usuarios(id),
    UNIQUE(curso_id, materia_id)
);
```

### 3.4 Modelo de Configuración

```sql
-- Tabla: config_institucion (en cada base de institución)
CREATE TABLE config_institucion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,

    -- ＝＝＝ Académico ＝＝＝
    tipo_evaluacion      TEXT DEFAULT 'numerica',   -- numerica, conceptual, porcentaje, letras
    escala_min           REAL DEFAULT 1.0,
    escala_max           REAL DEFAULT 10.0,
    nota_minima_aprobar  REAL DEFAULT 6.0,
    decimales_notas      INTEGER DEFAULT 1,
    creditos_activo      INTEGER DEFAULT 0,

    -- ＝＝＝ Períodos ＝＝＝
    num_periodos         INTEGER DEFAULT 4,
    periodos_json        TEXT,                      -- [{"nombre":"Semestre 1","inicio":"...","fin":"..."}]

    -- ＝＝＝ Estructura ＝＝＝
    jerarquia_activa     INTEGER DEFAULT 0,         -- 0=plano, 1=jerárquico
    niveles_json         TEXT,                      -- nombres de niveles jerárquicos

    -- ＝＝＝ Roles personalizados ＝＝＝
    roles_json           TEXT,                      -- {"rector":"Rector","authority":"Coordinador","teacher":"Docente",...}

    -- ＝＝＝ Comunicación ＝＝＝
    acuse_recibo         INTEGER DEFAULT 1,
    firmas_activas       INTEGER DEFAULT 0,

    -- ＝＝＝ Privacidad ＝＝＝
    mostrar_notas_entre_estudiantes INTEGER DEFAULT 0,
    acudiente_ver_notas  INTEGER DEFAULT 1,

    -- ＝＝＝ Sistema ＝＝＝
    idioma               TEXT DEFAULT 'es',
    huso_horario         TEXT DEFAULT 'America/Bogota',
    formato_fecha        TEXT DEFAULT 'DD/MM/YYYY',
    updated_at           TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 4. Sistema de Permisos

### 4.1 Filosofía

RBAC (Role-Based Access Control) con granularidad fina. Cada permiso se define como un string con notación de puntos:

```
<módulo>.<submódulo>.<acción>
```

### 4.2 Catálogo de permisos base

```
# ＝＝＝ Institución ＝＝＝
institution.view
institution.edit

# ＝＝＝ Personas ＝＝＝
people.teachers.view
people.teachers.create
people.teachers.edit
people.teachers.archive

people.students.view
people.students.create
people.students.edit
people.students.archive
people.students.transfer

people.staff.view
people.staff.create
people.staff.edit
people.staff.archive

# ＝＝＝ Estructura ＝＝＝
structure.sedes.manage
structure.faculties.manage
structure.programs.manage
structure.courses.manage
structure.subjects.manage

# ＝＝＝ Académico ＝＝＝
academic.grades.view
academic.grades.write
academic.grades.approve       # cierre de período
academic.grades.history       # ver historial de cambios

academic.attendance.view
academic.attendance.write

academic.observations.view
academic.observations.write

academic.evaluations.create
academic.evaluations.edit

academic.activities.create
academic.activities.edit

# ＝＝＝ Comunicación ＝＝＝
communication.communicados.view
communication.communicados.create
communication.communicados.edit
communication.communicados.publish
communication.communicados.archive
communication.communicados.read_receipt   # ver acuse de recibo

communication.channels.create
communication.channels.delete
communication.channels.manage_members
communication.channels.send
communication.channels.read

# ＝＝＝ Reportes ＝＝＝
reports.attendance
reports.grades
reports.consolidated
reports.audit
reports.export

# ＝＝＝ Configuración ＝＝＝
config.academic.edit          # escalas, períodos
config.roles.edit             # personalizar nombres de roles
config.branding.edit          # colores, logo
config.users.manage           # crear/editar cualquier usuario

# ＝＝＝ Auditoría ＝＝＝
audit.log.view
audit.log.export
```

### 4.3 Permisos por defecto por rol

| Rol | Permisos asignados |
|-----|-------------------|
| **admin** | Todos (acceso global multi-institución) |
| **rector** | Todos los permisos de su institución excepto `institution.edit` y `config.users.manage` (esos son solo admin) |
| **authority** | `*.view`, `academic.grades.write` (solo en cursos asignados), `academic.observations.write`, `communication.*.view`, `reports.*` (solo su programa/facultad) |
| **teacher** | `academic.grades.view+write` (solo sus materias), `academic.attendance.*`, `academic.observations.write`, `academic.evaluations.*`, `academic.activities.*`, `communication.channels.*` (solo sus canales), `communication.communicados.view` |
| **student** | `academic.grades.view` (propias), `academic.attendance.view` (propia), `communication.channels.read+send` (canales donde es miembro), `communication.communicados.view` (recibidos) |
| **guardian** | `academic.grades.view` (de sus estudiantes a cargo), `academic.attendance.view`, `communication.communicados.view`, `communication.channels.read` (solo lectura en canales de curso) |

### 4.4 Evaluación de permisos

```python
def tiene_permiso(slug, usuario_id, permiso, entidad_tipo=None, entidad_id=None):
    """
    Evalúa si un usuario tiene un permiso específico.
    - entidad_tipo/entidad_id: opcional, para permisos con alcance
    """
    roles = obtener_roles_usuario(slug, usuario_id)
    for rol in roles:
        if entidad_tipo and rol.entidad_tipo:
            # Verificar alcance: si el rol está limitado a una entidad,
            # solo aplica si coinciden
            if rol.entidad_tipo != entidad_tipo or rol.entidad_id != entidad_id:
                continue
        if permiso in rol.permisos or '*' in rol.permisos:
            return True
    return False
```

Los roles de nivel superior (menor número de jerarquía) heredan permisos de los roles inferiores automáticamente. Por ejemplo, un `rector` tiene todos los permisos que tiene un `authority`, más los suyos propios.

---

## 5. Mapa de Navegación por Rol

### 5.1 Convención de íconos

Cada sección usa un ícono descriptivo (SVG inline o Unicode) consistente en todo el sistema.

### 5.2 Administrador Global

```
/admin
├── Dashboard
│   ├── Total instituciones activas
│   ├── Alertas (vencimientos próximos, cuentas sin actividad)
│   └── Últimas instituciones registradas
│
├── Instituciones
│   ├── Lista (buscar, filtrar por estado)
│   ├── Crear nueva
│   ├── [Institución]
│   │   ├── Datos generales (nombre, slug, logo, colores)
│   │   ├── Plan / Vencimiento
│   │   ├── Códigos de acceso
│   │   ├── Estadísticas (usuarios activos, DB size)
│   │   └── Acciones: activar, suspender, eliminar
│   └── Configuración global
│       ├── Parámetros por defecto para nuevas instituciones
│       └── Plantillas de configuración
│
├── Usuarios (multi-institución)
│   └── Búsqueda global por email, nombre o institución
│
└── Logs del Sistema
    ├── Accesos
    ├── Errores
    └── Acciones administrativas
```

### 5.3 Rector / Dirección General

```
/panel-rector
├── Dashboard
│   ├── KPIs: estudiantes activos, docentes, cursos, comunicados pendientes
│   ├── Alertas: estudiantes con bajo rendimiento global, inasistencias críticas
│   ├── Últimos accesos
│   └── Gráfico: rendimiento por programa/curso (si jerarquía activa)
│
├── Gestión Institucional
│   ├── Personas
│   │   ├── Docentes → lista, crear, editar, archivar, reasignar
│   │   ├── Estudiantes → lista, crear, editar, archivar, transferir
│   │   └── Personal → lista, roles delegados
│   │
│   └── Estructura
│       ├── [Sedes] → (opcional, si jerarquía activa)
│       ├── [Facultades] → (opcional)
│       ├── [Programas] → (opcional)
│       ├── Cursos → crear, editar, ver detalle
│       └── Materias → crear, editar, activar/archivar
│
├── Gestión Académica
│   ├── Desempeño
│   │   ├── Vista general por período
│   │   ├── Por curso (promedios, aprobados/reprobados)
│   │   └── Por estudiante (historial completo)
│   │
│   ├── Seguimiento
│   │   ├── Asistencia consolidada
│   │   └── Observaciones recientes
│   │
│   └── Horarios
│       ├── Distribución general
│       └── Calendario académico
│
├── Comunicación
│   ├── Comunicados Oficiales
│   │   ├── Redactar (editor, prioridad, destinatarios, programar)
│   │   ├── Bandeja de enviados (con estado de lectura)
│   │   ├── Borradores
│   │   ├── Archivados
│   │   └── Plantillas
│   │
│   └── Conversaciones
│       ├── Canales de la institución
│       ├── Crear canal (tipo, nombre, miembros)
│       └── Ver actividad
│
├── Analítica
│   ├── Reportes
│   │   ├── Rendimiento (por período, curso, materia)
│   │   ├── Asistencia consolidada
│   │   └── Comunicación (tasa de lectura, canales activos)
│   │
│   └── Auditoría
│       ├── Cambios en notas
│       ├── Inicios de sesión
│       └── Acciones de usuarios
│
└── Configuración
    ├── Datos de la institución (nombre, logo, colores)
    ├── Configuración académica (escala, períodos, jornadas)
    ├── Roles (personalizar nombres)
    ├── Códigos de acceso
    ├── Administradores delegados
    └── Preferencias (idioma, formato)
```

### 5.4 Autoridad Académica (Coordinador / Decano / Director de Programa)

```
/panel-autoridad
├── Dashboard
│   ├── Resumen de su(s) programa(s)/curso(s) a cargo
│   ├── Alertas: estudiantes con bajo rendimiento
│   ├── Pendientes: comunicados sin leer, observaciones sin revisar
│   └── Comparativa: rendimiento entre materias
│
├── Académico
│   ├── Desempeño
│   │   ├── Notas del programa/curso (vista consolidada)
│   │   ├── Por materia
│   │   └── Por estudiante
│   │
│   ├── Seguimiento
│   │   ├── Asistencia por curso
│   │   ├── Observaciones (línea de tiempo)
│   │   └── Compromisos activos
│   │
│   └── Horarios del programa/curso
│
├── Comunicación
│   ├── Bandeja de Comunicados
│   ├── Reenviar comunicado a estudiantes/docentes
│   └── Conversaciones de sus cursos
│
├── Reportes
│   ├── Generar actas
│   └── Exportar boletines
│
└── Gestión (limitada a su ámbito)
    ├── Ver docentes asignados
    ├── Ver estudiantes
    └── Crear observaciones
```

### 5.5 Docente

```
/panel-docente
├── Dashboard
│   ├── Clases de hoy (tarjeta: curso, materia, hora, aula)
│   ├── Pendientes: tomar asistencia, registrar notas
│   ├── Comunicados no leídos (con badge)
│   ├── Conversaciones con mensajes nuevos
│   └── Alertas: estudiantes con bajo rendimiento en sus materias
│
├── Mis Cursos
│   ├── [Curso - Materia]
│   │   ├── Desempeño
│   │   │   ├── Notas (libreta inline editable)
│   │   │   ├── Evaluaciones (crear, editar)
│   │   │   └── Actividades (crear, editar)
│   │   │
│   │   ├── Seguimiento
│   │   │   ├── Asistencia (marcar por fecha)
│   │   │   └── Observaciones (agregar por estudiante)
│   │   │
│   │   └── Comunicación
│   │       ├── Conversación del curso
│   │       └── Enviar comunicado al curso
│   │
│   └── [Otro Curso - Materia] (similar)
│
├── Comunicación
│   ├── Comunicados Oficiales (recibidos)
│   └── Conversaciones (todos sus canales)
│
├── Horario (vista semanal)
│
└── Perfil
    ├── Datos personales
    ├── Cambiar contraseña
    └── Preferencias
```

### 5.6 Estudiante

```
/panel-estudiante
├── Mi Progreso
│   ├── Promedio general (con indicador visual)
│   ├── Créditos cursados / total (si aplica)
│   ├── Próximas evaluaciones (lista ordenada por fecha)
│   ├── Comunicados no leídos (prioridad visible con color)
│   ├── Conversaciones con mensajes nuevos
│   └── Horario de hoy
│
├── Mis Materias
│   ├── [Materia]
│   │   ├── Notas (desglose por evaluación/actividad)
│   │   ├── Asistencia (porcentaje + detalle)
│   │   ├── Observaciones (solo lectura)
│   │   └── Conversación de la materia
│   │
│   └── [Otra Materia] (similar)
│
├── Comunicación
│   ├── Bandeja de Comunicados (recibidos, con estado leído/no leído)
│   └── Conversaciones (canales donde participa)
│
├── Horario (vista semanal)
│
├── Progreso (gráfico de rendimiento por período)
│
└── Perfil
    ├── Datos personales
    ├── Cambiar contraseña
    └── Preferencias
```

### 5.7 Acudiente (P2)

```
/panel-acudiente
├── Dashboard
│   ├── Estudiantes a cargo (tarjetas con resumen)
│   ├── Alertas: inasistencias, bajo rendimiento
│   └── Comunicados no leídos
│
├── [Estudiante]
│   ├── Notas (solo lectura, desglose completo)
│   ├── Asistencia
│   ├── Observaciones
│   ├── Comunicados recibidos
│   └── Conversaciones del curso (solo lectura, sin enviar)
│
├── [Otro Estudiante] (similar, si tiene más de uno)
│
└── Perfil
    ├── Datos personales
    ├── Cambiar contraseña
    └── Preferencias de notificación
```

---

## 6. Estrategia de Migración

### 6.1 Filosofía

No romper la base de datos existente. Cada migración agrega tablas y columnas nuevas sin eliminar las actuales hasta que todo el código se haya actualizado.

### 6.2 Fases de migración

#### Fase 1 — Tablas nuevas junto a las existentes

```python
def migrar_p0(slug):
    conn = conectar(slug)
    c = conn.cursor()
    # Crear tablas nuevas (no reemplazar, crear al lado)
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (... )''')
    c.execute('''CREATE TABLE IF NOT EXISTS roles_instancia (... )''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios_roles (... )''')
    c.execute('''CREATE TABLE IF NOT EXISTS config_institucion (... )''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (... )''')
    # etc.
    conn.commit()
    conn.close()
```

#### Fase 2 — Migración de datos

Un script `migrate_users.py` que:
1. Lee de `profesores`, `alumnos`, `directoras`, `rectores`
2. Crea registros en `usuarios` con rol correspondiente en `usuarios_roles`
3. Genera email automático para quienes no tengan (`usuario + @institucion.slug + .lumini`)
4. Mantienen las tablas viejas como respaldo

#### Fase 3 — Actualización de código

- Toda nueva funcionalidad usa las tablas nuevas
- La funcionalidad existente sigue funcionando con las tablas viejas
- Progresivamente se refactoriza el código legacy

#### Fase 4 — Deprecación

- Las tablas viejas se marcan como `_legacy` en schema
- Se eliminan en una versión mayor

### 6.3 Compatibilidad hacia atrás

Durante la migración, los helpers tipo `get_profesor()` deben seguir funcionando. Se agregan nuevos helpers como:

```python
def get_usuario_actual_v2(slug):
    """Nuevo helper que usa `usuarios` + `usuarios_roles`."""
    ...

def get_rol_actual(slug):
    """Devuelve el rol activo del usuario autenticado."""
    ...
```

---

## 7. Riesgos y Oportunidades

### 7.1 Riesgos

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|-------------|------------|
| Migración de usuarios existentes pierde datos | Alto | Baja | Mantener tablas legacy 2 versiones. Pruebas con copia de DB real. |
| Usuarios sin email no pueden migrar a nuevo login | Alto | Media | Generar email automático. Enviar credenciales por mensaje interno. |
| Cambio de nombres (Avisos → Comunicados) confunde | Medio | Alta | Redirecciones. Tooltips "Antes llamado..." durante 1 mes. |
| Modelo jerárquico no es útil para colegios pequeños | Bajo | Media | Hacerlo opcional. Default: modelo plano (como ahora). |
| Sistema de permisos agrega complejidad al código | Medio | Media | Implementar por etapas. Primero permisos hardcodeados, luego configurables. |
| Crecimiento de SQLite con muchas instituciones | Medio | Baja | Una DB por institución. Si una crece demasiado, migrar a PostgreSQL. |

### 7.2 Oportunidades

| Oportunidad | Valor | Esfuerzo |
|-------------|-------|----------|
| Unificar tablas de usuarios elimina código duplicado en autenticación | Alto | Medio |
| Dashboard del estudiante mejora experiencia del 80% de usuarios | Alto | Medio |
| Evaluación configurable abre mercado universitario | Alto | Bajo |
| Roles personalizables permiten vender a institutos técnicos | Alto | Bajo |
| Auditoría desde el inicio evita tener que agregarla después | Medio | Bajo |
| Acudiente como rol nativo es diferenciador frente a competidores | Alto | Medio |

---

## 8. Recomendaciones

### 8.1 Orden de implementación

```
FASE 0 — CIMIENTOS
├── 0.1: Modelo de datos (usuarios, roles, configuración, estructura)
│     Crear tablas nuevas junto a las existentes. Sin migrar datos aún.
│
├── 0.2: Sistema de permisos básico
│     Implementar helper tiene_permiso(). Hardcodear permisos por rol.
│     Integrar en rutas existentes.
│
├── 0.3: Configuración institucional
│     Formulario para que el rector configure: escala, períodos, nombres de roles.
│     Aplicar configuración en vistas de notas.
│
├── 0.4: Auditoría
│     Tabla audit_log. Implementar en notas (crear, editar, eliminar).
│     Vista para rector.
│
├── 0.5: Login unificado
│     Email + password para todos los roles.
│     Recovery por email.
│     Mantener PIN como legacy.
│
└── 0.6: Refactor sesiones
│     Helper unificado get_usuario_actual_v2().
│     Sesión unificada en lugar de 4 variables separadas.
│
FASE 1 — MÓDULOS FUNCIONALES (posterior)
```

### 8.2 Qué NO hacer en P0

- No rediseñar el frontend (excepto lo mínimo necesario)
- No migrar datos legacy todavía
- No crear el rol acudiente
- No implementar jerarquía académica completa (solo el modelo de datos)
- No crear dashboards nuevos
- No agregar reportes exportables

### 8.3 Principios de implementación

1. **Una tabla nueva nunca rompe una existente** — siempre CREATE IF NOT EXISTS
2. **Cada cambio debe funcionar con datos reales existentes** — probar con copia de DB
3. **Cada función nueva debe tener su prueba manual documentada**
4. **No hay feature sin permiso asociado** — toda acción sensible pasa por `tiene_permiso()`
5. **No hay feature sin log de auditoría** — toda escritura en datos sensibles genera registro

### 8.4 Stack técnico (sin cambios)

- Backend: Flask (Python 3)
- Base de datos: SQLite (una por institución)
- Frontend: HTML + CSS + JavaScript vanilla
- Sin frameworks JS externos
- Sin librerías CSS externas
- Estilos: variables CSS para tema institucional
- Autenticación: sesiones Flask (cookies firmadas)
- CSRF: token por sesión

### 8.5 Validación del diseño

Antes de implementar, validar con:

1. **Un colegio pequeño** (200 estudiantes, 15 docentes, 1 rector)
2. **Un colegio grande** (2000 estudiantes, 100 docentes, 4 coordinadores)
3. **Una universidad** (5000 estudiantes, 5 facultades, 20 programas, 300 docentes)
4. **Un instituto técnico** (300 estudiantes, 3 programas cortos, instructores)

Cada validación debe responder: ¿La configuración actual permite modelar esta institución?

---

*Documento generado el 27 de junio de 2026.*
*Versión 2.0 — Pendiente de aprobación para inicio de implementación.*
