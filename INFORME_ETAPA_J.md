# ETAPA J — Informe de validación manual / preparación para evaluación (SOLO LECTURA)

Fecha: 2026-08-12 · Baseline: 420 PASS / 36/36 smoke (ETAPA I) · Sin modificaciones · Sin commit
Alcance: flujos de profesor, rector, notas, autosave, borrado de notas, dashboard, alertas, asistencia, acciones rápidas, gráficos, exportación, responsive y CSRF.

Cada hallazgo indica: archivo:línea · problema · comprobación manual · ¿corregir antes de la evaluación?
(✓ = verificado por lectura directa de código en esta revisión; los demás provienen de trazado de agentes sobre el mismo código).

---

## CRÍTICO — corregir ANTES de la evaluación

### C1. Autosave pierde cambios tecleados durante una petición en vuelo (pérdida silenciosa de notas) ✓
- `templates/index.html:4027-4043` (esp. `4034-4035`: `_undoSnapshot=resp.snapshot; _batchChanges={}`)
- `ejecutarBatchSave` captura `cambios=Object.values(_batchChanges)` al iniciar el POST. Mientras la respuesta viaja, las pulsaciones nuevas entran a `_batchChanges` y arman un nuevo timer (600 ms). Cuando responde la petición vieja, `_batchChanges={}` borra los cambios nuevos; el timer pendiente dispara `ejecutarBatchSave` con lista vacía → `marcarSaved()`. El valor nuevo jamás se envía.
- Comprobar: DevTools → Network → Slow 3G; editar celda A (lanza POST) y, antes de que responda, editar celda B. La barra dice "Todo guardado", B pierde el `dirty`, pero al recargar B no está en BD.
- **Corregir: SÍ.** (Merge de cambios pendientes en la respuesta, o encolar peticiones en secuencia.)

### C2. Respuestas fuera de orden + DELETE/INSERT desordenados pueden dejar la nota borrada ✓
- `templates/index.html:4031-4035` (sin secuencia/nonce) + `app/routes/teacher.py:706-715`
- Dos POST solapados a `/notas/batch` para la misma `(aid, actividad_id)`: gana el que llega último al servidor. Peor caso: vaciar la celda encola `val:null` (DELETE, teacher.py:709-711); si ese DELETE llega después de un INSERT con el valor nuevo, la nota queda borrada mientras la UI muestra el valor como guardado.
- Comprobar: red lenta; escribir 3 → esperar guardado → borrar celda (DELETE) y escribir 4 antes de que el DELETE resuelva → recargar: nota ausente.
- **Corregir: SÍ.** (Misma solución que C1: serializar/envíos cancelables.)

### C3. Vacío/NaN = borrado real de la nota sin confirmación ni deshacer ✓
- `templates/index.html:3991-3996` (`num=val?parseFloat(val):null` → payload `val:null`) + `app/routes/teacher.py:691-696,709-715`
- Cualquier celda vacía (`''`) o NaN en columnas dinámicas (`type="text"`, index.html:3573/4255) se traduce a DELETE a los 600 ms, aun cuando el profesor solo esté reescribiendo el valor. No hay confirmación y el deshacer está roto (C4), por lo que la eliminación es irreversible en la práctica.
- Comprobar: borrar una celda con nota y esperar >600 ms antes de escribir el nuevo valor; recargar → nota eliminada.
- **Corregir: SÍ.** (Al menos: solo borrar con confirmación/gesto explícito, o pausar el guardado hasta que el input pierda foco.)

### C4. Deshacer tras borrado es imposible (doble fallo) ✓
- `app/routes/teacher.py:763-767` (solo `UPDATE notas SET val=?`) + `templates/index.html:4131-4138` (`mostrarDeshacer` sin ningún llamador)
- (a) El toast "DESHACER" nunca aparece: ninguna función llama `mostrarDeshacer`; `_undoSnapshot` (index.html:4034) se descarta. (b) Aun invocando la ruta, con `val_anterior is not None` solo hace UPDATE; si la fila fue borrada (DELETE), el UPDATE afecta 0 filas y responde `status:'ok'` — el JS diría "Cambio deshecho" con la nota todavía ausente.
- Comprobar: borrar una nota (celda vacía) → no hay opción de deshacer. Por consola: `POST /<slug>/notas/batch {val:null}` y luego `POST /<slug>/notas/deshacer` con el valor anterior → fila sigue inexistente y responde ok.
- **Corregir: SÍ.** (`notas/deshacer` debe hacer INSERT/REPLACE cuando la fila no existe; y conectar el toast de deshacer al guardado en lote.)

---

## ALTO — corregir ANTES de la evaluación (comportamiento visible o pérdida parcial)

### A1. Observación de asistencia nunca se guarda ✓
- `templates/asistencia.html:218-224` (`guardarObservacion`) + `app/routes/attendance.py:107-108`
- El JS envía `aid + observacion + fecha + _csrf_token` pero NO envía `estado`; el backend exige `if aid is None or not estado: return ('', 400)`. El `SyntaxError` del `.json()` es tragado por `.catch(function(){})`. El docente escribe la observación (input línea 155) y "se guarda" sin feedback, pero no persiste.
- Comprobar: abrir `/<slug>/asistencia`, escribir observación, Tab, recargar → desapareció.
- **Corregir: SÍ.** (Enviar `estado` actual, o relajar el backend cuando venga `observacion`.)

### A2. Asistencia: marcar presente no da feedback y fallos son silenciosos ✓
- `templates/asistencia.html:204-217` + `app/routes/attendance.py:131`
- El backend responde `{'status':'ok'}`; el JS comprueba `if(d.ok)` → `d.ok` es `undefined` → el botón nunca se activa, no hay toast y las tarjetas de estadísticas no cambian. `.catch(function(){})` traga 403 (CSRF expirado) y 400 (fecha inválida): el docente cree que registró asistencia cuando no fue así.
- Comprobar: marcar P → el botón no se ilumina y "Presentes" sigue en 0 hasta recargar.
- **Corregir: SÍ.** (Leer `d.status==='ok'`; mostrar error real.)

### A3. Guardar Evaluación escribe en el período 1 y con el curso equivocado ✓
- `templates/index.html:4010` (body solo `aid`+`campo`) + `app/routes/teacher.py:905` (`periodo` default 1) y `912-914` (`curso = cursos_prof[0]`)
- Editar "Evaluación" estando en período 2 guarda en período 1 y recalcula stats con el primer curso del profesor. Visible para el evaluador en cuanto pruebe dos períodos o dos cursos.
- Comprobar: profesor con 2 cursos; en el 2.º curso y período 2 editar Evaluación → en BD `evaluaciones.periodo=1` y promedio mostrado del 1.er curso.
- **Corregir: SÍ.** (Enviar `periodo` y `curso` en el body.)

### A4. Plantilla aplicada siempre con jornada "mañana" → invisible para docentes de tarde ✓
- `templates/index.html:5568` (body solo `plantilla_id/curso/materia`) + `app/routes/teacher.py:3270` (`jornada = data.get('jornada') or 'mañana'`)
- La actividad creada desde plantilla queda con `jornada='mañana'`; el gradebook filtra por la jornada de sesión (teacher.py:185), así que el docente de tarde ve el toast "Actividad creada" pero la columna no aparece (dato invisible).
- Comprobar: sesión con jornada tarde; aplicar plantilla → toast ok, sin columna nueva; revisar `actividades.jornada='mañana'`.
- **Corregir: SÍ.** (Enviar la jornada de sesión o usar `get_sesion_jornada_materia`.)

### A5. Vaciar el campo Evaluación es un no-op que la UI reporta como "guardado" ✓
- `templates/index.html:4010` (envía `''`) + `app/routes/teacher.py:922` (`ev_final = ev if ev is not None else old_eval`)
- `'' → None → old_eval` conserva el valor viejo; la UI quita `dirty` y marca guardado. Al recargar reaparece el valor. No hay forma de borrar una evaluación.
- Comprobar: borrar Evaluación, esperar, recargar → el valor anterior vuelve.
- **Corregir: SÍ.** (Tratar vacío como borrado con `NULL`.)

### A6. Errores de "Período cerrado"/"Fuera de rango" se tragan y el dato se descarta en silencio ✓
- `app/routes/teacher.py:703-705` y `730-731` (`status:'ok'` + lista `errors`) + `templates/index.html:4032-4039`
- La UI nunca lee `resp.errors`: limpia `_batchChanges`, quita `dirty`, marca "Todo guardado". El ítem rechazado se pierde sin mensaje ni reintento; el input conserva el valor que en BD no existe.
- Comprobar: teclear 6 (fuera de rango 0–5) o escribir en período cerrado → barra "Todo guardado", recargar → nota ausente, sin aviso.
- **Corregir: SÍ.** (Leer `resp.errors`, marcar la celda en rojo y no limpiarla.)

### A7. Colores de gráficos inválidos para canvas (barras/puntos invisibles) ✓
- `templates/rector_panel.html:998` (`backgroundColor:'rgba(var(--accent-rgb),.6)'`) · `templates/index.html:4897` (`rgba(var(--accent-rgb),.7)` + `borderColor:'var(--accent)'`) · `templates/index.html:5741-5742`
- La API de canvas NO resuelve `var()` de CSS. Las barras "Promedio por curso" del rector y los puntos del scatter del drawer salen negros/invisibles en tema oscuro. En `dashboard.html:680-685` ya existe el helper correcto (`getComputedStyle` + `rgba()`) que se copia en cada llamada.
- Comprobar: rector → "Promedio por curso" (barras negras); profesor → drawer de alumno con >1 nota (puntos negros); Analítica comparativa (barras negras).
- **Corregir: SÍ.** (Resolver colores como en dashboard.html.)

### A8. CSRF: 6 rutas POST con cambio de estado NO validan token (sin guard global) ✓
- No existe `before_request` global de CSRF (solo `after_request` de cabeceras en `app/handlers.py:22`). La protección es por ruta.
- Sin `validar_csrf()` en `app/routes/teacher.py`: `plantillas/crear` (3231), `plantillas/aplicar` (3254), `plantillas/eliminar` (3280), `planificacion/copiar` (3296), `comunicados/<cid>/leer` (3082), y las read-only `observaciones_json` (1873), `observaciones/sugerir` (2089), `validar` (2293), `ai/ask` (3465). El frontend SÍ manda el token; el backend lo ignora.
- Comprobar: sesión de profesor, `fetch('/<slug>/plantillas/aplicar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plantilla_id:1,curso:'1A'})})` sin token → responde 200 `{"status":"ok"}` (debería ser 403). Comparar con `/notas/batch` (sí da 403).
- **Corregir: SÍ.** (Añadir `validar_csrf()` a las 4 rutas con cambio de estado; las read-only al menos por coherencia.)

### A9. "Acciones rápidas" (bulk de actividades): sin UI conectada y eliminar sin protección de período ✓
- `templates/index.html:5041-5061` (`toggleActSelect`/`ejecutarAccionMasiva`/`massDeleteBtn`): ninguna función ni elemento del DOM las llama (`massDeleteBtn` no existe). El backend `/actividades/masiva` (teacher.py:2236-2290) está completo pero solo alcanzable desde consola.
- Si se conectara: el branch `eliminar` (teacher.py:2252-2255) borra notas+actividades sin comprobar `periodo_cerrado` (a diferencia de `borrar_actividad`, teacher.py:370) y sin `confirm()` ni auditoría (index.html:5051-5061).
- Comprobar: revisar el menú de acciones rápidas en el UI → no existe. Por consola: `{accion:'eliminar',ids:[...]}` en período cerrado → 200.
- **Corregir: SÍ.** (Conectar el UI de acciones masivas, añadir `periodo_cerrado` + `confirm()` en `eliminar`, y auditar.)

---

## MEDIO — corregir idealmente antes de la evaluación (falla parcial o inconsistencia visible)

### M1. Coma decimal truncada: "3,5" se guarda como 3 ✓
- `templates/index.html:3991` (`parseFloat`) sobre columnas dinámicas `type="text"` (3573/4255). El usuario hispano escribe coma y el valor se trunca; la UI sigue mostrando "3,5" hasta recargar.
- Comprobar: crear actividad nueva, escribir "3,5", recargar → 3.
- **Corregir: SÍ.** (Reemplazar `,` por `.` antes de `parseFloat`.)

### M2. Reordenar columnas desalinea las notas del body ✓
- `templates/index.html:4194-4207` (solo mueve `td.td-eval`/`td.td-locked`) vs. columnas servidas por el servidor (index.html:1188, `<td class="">` sin esas clases). El encabezado se mueve pero las celdas de notas no: se teclea bajo un encabezado y el valor va a otra actividad (el input conserva su `data-actid`).
- Comprobar: arrastrar una columna de actividad → encabezado movido, notas del body no; escribir una nota → se guarda en la actividad original.
- **Corregir: SÍ.** (Reordenar todas las celdas de la columna, no solo las de eval.)

### M3. `irAFecha` pierde el parámetro `curso` ✓
- `templates/asistencia.html:225` (`window.location.href = pathname+'?fecha='+valor`). Al cambiar fecha se salta al primer curso de la lista (los botones día anterior/siguiente sí conservan `curso`).
- Comprobar: en `/<slug>/asistencia?curso=8B`, cambiar fecha → URL sin `curso`.
- **Corregir: SÍ** (conservar query existente).

### M4. Métricas del rector inconsistentes entre panel y GRÁFICOS ✓
- `app/routes/rector_routes.py:127` y `136-140` (promedio = `AVG(val)` simple sobre filas) vs. `app/infra/dashboard.py:908` y `960` (promedio ponderado por estudiante 65/25/10). Un alumno con 10 notas pesa 10× más en el panel. También difiere la distribución (`rector_routes.py:141-162` agrupa por promedio del estudiante vs `dashboard.py:924-936` agrupa valores brutos). El evaluador puede ver "Promedio institucional" distinto en las dos pantallas del mismo colegio.
- Comprobar: colegio con distinto número de notas por alumno; comparar panel rector vs dashboard.
- **Corregir: SÍ** (unificar definición).

### M5. Gráficos recortados a 360 px (grid 380 px sin media query) ✓
- `templates/dashboard.html:143` (`.chart-grid{...minmax(380px,1fr)}`) sin override; `static/css/base.css:3,8` oculta `overflow-x`. A 360 px la mitad derecha de cada gráfico queda inaccesible.
- Comprobar: DevTools a 360 px en `/<slug>/dashboard` → GRÁFICOS recortado.
- **Corregir: SÍ.** (`@media(max-width:480px){.chart-grid{grid-template-columns:1fr;min-width:0}}`)

### M6. Dependencias CDN (Chart.js/lucide) rompen gráficos e iconos sin internet ✓
- Chart.js 4.4.1: `templates/dashboard.html:6`, `index.html:6`, `rector_panel.html:6` (jsdelivr). lucide **sin pin** `@latest`: `templates/base.html:51` (unpkg). Google Fonts: `base.html:15-18`. No hay copia local ni vendor.
- `index.html` no tiene `typeof Chart==='undefined'` (solo dashboard.html:678 y rector_panel.html:989 lo tienen): offline, `new Chart` en 4392/4401/4462/4897/5734 lanza ReferenceError tragado por `.catch()` → todos los gráficos de modales/drawer/analítica simplemente no aparecen; lucide deja todos los iconos en blanco.
- Comprobar: cortar red (o bloquear jsdelivr.net/unpkg) → gráficos de drawer/analítica vacíos e iconos blancos.
- **Corregir: SÍ para sustentación** (descargar Chart.js/lucide a `static/vendor/` y versionar; al menos pin `lucide@0.x`).

### M7. Sin claves foráneas: huérfanos en `entregas`/`solicitudes_modificacion`/`eventos_calendario` al borrar actividad
- `app/infra/database.py:426` (entregas), `:309` (solicitudes_modificacion) y `eventos_calendario` referencian `actividad_id` sin FK (no hay FKs en el esquema; `PRAGMA foreign_keys=ON` en database.py:55 no enforza nada). `borrar_actividad` (teacher.py:355-389) y el `eliminar` masivo borran notas primero pero no estas tablas.
- Comprobar: crear entrega/solicitud/evento para una actividad, borrar la actividad → filas huérfanas que el alumno podría seguir viendo.
- **Corregir: SÍ** (borrar en cascada en el código).

### M8. Fecha "hoy" con zona horaria del servidor (no usa `huso_horario` de config)
- `app/routes/attendance.py:39,47,48` (`datetime.today()`), `attendance_repository.py:87`, `teacher.py:213`. `marcarAsist` (index.html:1756-1762) no envía `fecha`, así que registra el "hoy" del servidor. Cerca de medianoche se registra la fecha equivocada si el servidor no está en America/Bogota.
- Comprobar: servidor en UTC, marcar asistencia a las 00:30 hora local → fecha del día anterior.
- **Corregir: CONDICIONAL** (solo si el deploy real cambia de zona).

### M9. `ejecutarAccionMasiva` sin `confirm()` para `eliminar` y sin auditoría
- `templates/index.html:5051-5061` (relacionado con A9). Un clic (una vez conectado el UI) destruye sin confirmación ni traza.
- Comprobar: (con A9 resuelto) clic en eliminar masivo → no pide confirmación.
- **Corregir: SÍ** (junto con A9).

---

## BAJO — opcional antes de la evaluación (cosmético o código muerto)

- **B1** Eliminación invisible en historial: `app/infra/audit.py:60-62` (valor_nuevo=None → NULL) + `templates/index.html:1652-1656/3969` no muestran qué se eliminó.
- **B2** Código muerto duplicado del autosave legacy: `templates/index.html:1471-1539` (`encolarCambio`/`vaciarBatch`), `1740-1754` (`autoSaveNota/Eval`), indicadores por celda `1460-1469`; nunca conectados a inputs.
- **B3** Ruta `guardar_nota` inalcanzable y con respuestas no-JSON: `app/routes/teacher.py:781-834` (CSRF en texto plano 787, cuerpos vacíos 790-791, sin validación de rango).
- **B4** Bug de default en `guardar_evaluacion_batch`: `teacher.py:1073-1074` (`dict.get(k, type=float)` → default la clase `float` → 500 si falta el campo). Ruta del path legacy muerto.
- **B5** Contador de pendientes no incluye evaluaciones: `templates/index.html:4024` vs `4004` (`contarCambiosPendientes`).
- **B6** Zeros inconsistentes en rector panel: `templates/rector_panel.html:89,95,101,110,116,122,144` muestran `--` donde `132/150` muestran `0`.
- **B7** Exportación con curso vacío genera xlsx solo con cabeceras sin error visible: `teacher.py:1209,1243`.
- **B8** `e.message` crudo en `.catch` de reordenar/deshacer: `templates/index.html:4220`, `4151`.
- **B9** Columna Excel >26 fechas falla: `attendance.py:215` (`chr(64+ci) if ci<=26 else 'A'`).
- **B10** Gráficos vacíos sin estado "Sin datos": `dashboard.py:368/959` (`distribucion` siempre con 5 buckets a 0), `dashboard.py:409` (fabrica 4 períodos null).
- **B11** Duplicar masivo copia `orden=NULL`: `teacher.py:2262-2274`.

---

## Lo que está CORRECTO (verificado, sin hallazgo)

- **notas/batch**: validación de tipo/`bool`, rango por `config_get`, `periodo_cerrado`, CSRF, UPSERT `ON CONFLICT(aid,actividad_id)` consistente con el UNIQUE real, recálculo de stats por estudiante. ✓
- **borrar_actividad / duplicar**: CSRF + propiedad + `periodo_cerrado` (403) + auditoría + borra notas antes de la actividad + `confirm()` en JS. ✓
- **Exportación**: `plantilla_notas`/`exportar_notas` generan xlsx válido con cabeceras N°/Estudiante/AID/actividades/Evaluación/Autoevaluación/Promedio; botón del gradebook pasa `curso` y `periodo` correctos. ✓
- **dashboard_data**: a prueba de datos vacíos (divisiones protegidas, `_estadisticas_desc` con vacío, `pendientes=max(0,...)`); rector con `rendimiento_actividades:[]` ya filtrado en frontend (ETAPA I). ✓
- **Panel rector**: conteos de consultas reales (no mock). ✓
- **CSRF frontend**: los 155 POST/fetch y las 52 formas POST de todos los templates envían token (X-CSRF-Token o `_csrf_token`). Las rutas críticas `/notas/batch`, `/actividades/masiva`, `/archivar_alumno`, `/archivar_profesor`, `/guardar_evaluacion`, asistencia y todas las de rector/admin/auth sí validan. ✓
- **Responsive gradebook**: a 360 px la tabla usa scroll horizontal (`#gradeScroll .tw`), sidebar off-canvas y cards colapsadas; usable. ✓

---

## Orden de corrección recomendado antes de la sustentación
1. C1–C4 (pérdida de datos / deshacer) — los 4 son del flujo de notas, el corazón de la demo.
2. A6 (errores silenciosos) y A5 (evaluación) — mismo flujo, feedback del usuario.
3. A1–A2 (asistencia) y A3–A4 (evaluación/plantillas con período y jornada).
4. A8 (CSRF) y A9 (acciones masivas) — seguridad y coherencia.
5. A7 + M5 + M6 (gráficos y offline) — impresión visual y contingencia de red.
6. M1–M4, M7 (comas, reordenar, fecha, métricas rector, huérfanos).
7. Bajos cuando quede tiempo.
