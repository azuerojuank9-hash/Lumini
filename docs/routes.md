# Lumini — Rutas

| Blueprint | Ruta | Métodos |
|-----------|------|---------|
| admin_routes | `/admin/codigos` | GET, POST |
| admin_routes | `/admin/codigos/<slug>` | GET, POST |
| admin_routes | `/admin/profesores/<slug>` | GET |
| attendance | `/<slug>/asistencia` | GET |
| attendance | `/<slug>/marcar_asistencia` | POST |
| attendance | `/<slug>/asistencia_data` | GET |
| attendance | `/<slug>/asistencia_reporte_excel` | GET |
| auth | `/admin` | GET, POST |
| auth | `/admin/logout` | GET |
| auth | `/<slug>/recuperar` | GET, POST |
| auth | `/<slug>/directora/buscar_usuario_recuperar` | POST |
| auth | `/<slug>/directora/cambiar_password_recuperar` | POST |
| auth | `/<slug>/login` | GET, POST |
| auth | `/<slug>/logout` | GET |
| auth | `/<slug>/cambiar_password` | GET, POST |
| auth | `/<slug>/portal/login` | GET, POST |
| auth | `/<slug>/rector/login` | GET, POST |
| auth | `/<slug>/rector/registrar` | POST |
| auth | `/<slug>/rector/buscar_usuario_recuperar` | POST |
| auth | `/<slug>/rector/cambiar_password_recuperar` | POST |
| auth | `/<slug>/rector/logout` | GET |
| auth | `/<slug>/directora/login` | GET, POST |
| auth | `/<slug>/directora/registrar_directo` | POST |
| auth | `/<slug>/directora/logout` | GET |
| channels_routes | `/<slug>/api/canales` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/mensajes` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/mensajes/nuevos` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/enviar` | POST |
| channels_routes | `/<slug>/api/canales/<int:cid>/leer` | POST |
| channels_routes | `/<slug>/api/canales/<int:cid>/reaccionar` | POST |
| channels_routes | `/<slug>/api/canales/<int:cid>/fijar` | POST |
| channels_routes | `/<slug>/api/canales/<int:cid>/fijados` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/biblioteca` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/buscar` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/editar/<int:mid>` | POST |
| channels_routes | `/<slug>/api/canales/<int:cid>/eliminar/<int:mid>` | DELETE, POST |
| channels_routes | `/<slug>/api/canales/<int:cid>/lecturas` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/escribiendo` | POST |
| channels_routes | `/<slug>/api/canales/<int:cid>/actividad` | GET |
| channels_routes | `/<slug>/api/canales/<int:cid>/enlaces` | POST |
| channels_routes | `/<slug>/api/comunicaciones` | GET |
| channels_routes | `/<slug>/api/comunicaciones/count` | GET |
| courses | `/<slug>/agregar_cursos` | POST |
| courses | `/<slug>/quitar_curso/<curso>` | POST |
| courses | `/<slug>/transferir_curso` | GET, POST |
| directora_routes | `/<slug>/directora` | GET |
| directora_routes | `/<slug>/directora/panel` | GET |
| directora_routes | `/<slug>/directora/boletin_pdf` | GET |
| directora_routes | `/<slug>/directora/enviar_correos` | POST |
| directora_routes | `/<slug>/directora/guardar_email` | POST |
| directora_routes | `/<slug>/directora/crear_desde_panel` | POST |
| files_routes | `/<slug>/api/canales/<int:cid>/archivos/subir` | POST |
| files_routes | `/<slug>/api/archivos/<int:fid>/descargar` | GET |
| files_routes | `/<slug>/api/archivos/<int:fid>/previsualizar` | GET |
| files_routes | `/<slug>/api/archivos/<int:fid>/eliminar` | DELETE, POST |
| main_routes | `/static/<path:filename>` | GET |
| main_routes | `/offline` | GET |
| main_routes | `/` | GET |
| notifications_routes | `/<slug>/notificaciones` | GET |
| notifications_routes | `/<slug>/notificaciones/<int:nid>/leer` | POST |
| notifications_routes | `/<slug>/notificaciones/contar` | GET |
| notifications_routes | `/<slug>/comunicaciones/<int:cid>/leer` | POST |
| observations | `/<slug>/agregar_observacion` | POST |
| observations | `/<slug>/editar_observacion/<int:id_o>` | POST |
| observations | `/<slug>/borrar_observacion/<int:id_o>` | POST |
| parent_routes | `/<slug>/portal/dashboard` | GET |
| parent_routes | `/<slug>/portal/notas/<int:alumno_id>` | GET |
| parent_routes | `/<slug>/portal/asistencia/<int:alumno_id>` | GET |
| parent_routes | `/<slug>/portal/comunicados` | GET |
| rector_routes | `/<slug>/rector` | GET |
| rector_routes | `/<slug>/rector/panel` | GET |
| rector_routes | `/<slug>/rector/horarios` | GET |
| rector_routes | `/<slug>/rector/horarios/datos` | GET |
| rector_routes | `/<slug>/rector/profesores` | GET |
| rector_routes | `/<slug>/rector/estudiantes` | GET |
| rector_routes | `/<slug>/rector/cursos` | GET |
| rector_routes | `/<slug>/rector/reportes` | GET |
| rector_routes | `/<slug>/rector/asistencia` | GET |
| rector_routes | `/<slug>/rector/asistencia_data` | GET |
| rector_routes | `/<slug>/rector/configuracion` | GET, POST |
| rector_routes | `/<slug>/rector/periodos/<int:periodo>/<accion>` | POST |
| rector_routes | `/<slug>/rector/solicitudes` | GET |
| rector_routes | `/<slug>/rector/solicitudes/<int:sid>/<accion>` | POST |
| rector_routes | `/<slug>/rector/auditoria` | GET |
| rector_routes | `/<slug>/rector/comunicaciones` | GET |
| rector_routes | `/<slug>/rector/comunicaciones/nueva` | GET, POST |
| rector_routes | `/<slug>/rector/comunicaciones/<int:cid>/editar` | GET, POST |
| rector_routes | `/<slug>/rector/comunicaciones/<int:cid>` | GET |
| rector_routes | `/<slug>/rector/comunicaciones/<int:cid>/publicar` | POST |
| rector_routes | `/<slug>/rector/comunicaciones/<int:cid>/archivar` | POST |
| rector_routes | `/<slug>/rector/comunicaciones/<int:cid>/eliminar` | POST |
| rector_routes | `/<slug>/rector/comunicaciones/<int:cid>/evento` | GET |
| rector_routes | `/<slug>/rector/canales` | GET |
| rector_routes | `/<slug>/rector/canales/crear` | POST |
| rector_routes | `/<slug>/rector/canales/<int:cid>/eliminar` | POST |
| rector_routes | `/<slug>/rector/canales/<int:cid>/miembros` | GET |
| rector_routes | `/<slug>/rector/gestion-rectores` | GET |
| rector_routes | `/<slug>/rector/gestion-rectores/crear` | GET, POST |
| rector_routes | `/<slug>/rector/gestion-rectores/<int:rid>/editar` | GET, POST |
| rector_routes | `/<slug>/rector/gestion-rectores/<int:rid>/toggle` | POST |
| rector_routes | `/<slug>/rector/gestion-rectores/<int:rid>/eliminar` | POST |
| rector_routes | `/<slug>/rector/gestion-rectores/<int:rid>/hacer-principal` | POST |
| rector_routes | `/<slug>/rector/expediente` | GET |
| rector_routes | `/<slug>/rector/observador` | GET |
| rector_routes | `/<slug>/rector/certificados` | GET |
| rector_routes | `/<slug>/rector/calendario` | GET |
| rector_routes | `/<slug>/rector/mensajes` | GET |
| rector_routes | `/<slug>/api/rector/estudiantes` | GET |
| rector_routes | `/<slug>/api/rector/observador/<int:aid>` | GET, POST |
| student_routes | `/<slug>/estudiante` | GET |
| teacher | `/<slug>/seleccionar` | GET, POST |
| teacher | `/<slug>/` | GET |
| teacher | `/<slug>` | GET |
| teacher | `/<slug>/nueva_actividad` | POST |
| teacher | `/<slug>/borrar_actividad/<int:act_id>` | POST |
| teacher | `/<slug>/actividades/crear` | POST |
| teacher | `/<slug>/actividades/<int:act_id>` | PUT |
| teacher | `/<slug>/actividades/<int:act_id>/estado` | POST |
| teacher | `/<slug>/actividades/<int:act_id>/detalle` | GET |
| teacher | `/<slug>/actividades/<int:act_id>/duplicar` | POST |
| teacher | `/<slug>/actividades/<int:act_id>/historial` | GET |
| teacher | `/<slug>/actividades/<int:act_id>/estadisticas` | GET |
| teacher | `/<slug>/reordenar_actividades` | POST |
| teacher | `/<slug>/notas/batch` | POST |
| teacher | `/<slug>/notas/deshacer` | POST |
| teacher | `/<slug>/guardar_nota` | POST |
| teacher | `/<slug>/historial_notas/<int:aid>` | GET |
| teacher | `/<slug>/historial_curso` | GET |
| teacher | `/<slug>/guardar_evaluacion` | POST |
| teacher | `/<slug>/guardar_nota_batch` | POST |
| teacher | `/<slug>/guardar_evaluacion_batch` | POST |
| teacher | `/<slug>/solicitar_modificacion` | POST |
| teacher | `/<slug>/plantilla_notas` | GET |
| teacher | `/<slug>/exportar_notas` | GET |
| teacher | `/<slug>/importar_notas` | GET |
| teacher | `/<slug>/importar_notas/preview` | POST |
| teacher | `/<slug>/importar_notas/confirmar` | POST |
| teacher | `/<slug>/migrar-excel` | GET |
| teacher | `/<slug>/migrar-excel/analizar` | POST |
| teacher | `/<slug>/migrar-excel/confirmar` | POST |
| teacher | `/<slug>/observaciones_json` | POST |
| teacher | `/<slug>/recalcular/<int:aid>` | GET |
| teacher | `/<slug>/curso/analitica` | GET |
| teacher | `/<slug>/curso/ranking` | GET |
| teacher | `/<slug>/estudiante/<int:aid>/tendencia` | GET |
| teacher | `/<slug>/observaciones/sugerir` | POST |
| teacher | `/<slug>/alertas` | GET |
| teacher | `/<slug>/institucional/dashboard` | GET |
| teacher | `/<slug>/actividades/list` | GET |
| teacher | `/<slug>/actividades/masiva` | POST |
| teacher | `/<slug>/validar` | POST |
| teacher | `/<slug>/sugerencias` | GET |
| teacher | `/<slug>/comparar` | GET |
| teacher | `/<slug>/timeline` | GET |
| teacher | `/<slug>/institucional/centro-control` | GET |
| teacher | `/<slug>/smart-hub` | GET |
| teacher | `/<slug>/notas/pagina` | GET |
| teacher | `/<slug>/analitica/comparar` | GET |
| teacher | `/<slug>/dashboard` | GET |
| teacher | `/<slug>/dashboard_data` | GET |
| teacher | `/<slug>/nuevo_trabajo` | POST |
| teacher | `/<slug>/borrar_trabajo/<int:id_t>` | POST |
| teacher | `/<slug>/registrar` | POST |
| teacher | `/<slug>/archivar_alumno/<int:id>` | POST |
| teacher | `/<slug>/reactivar_alumno/<int:id>` | POST |
| teacher | `/<slug>/eliminar_alumno/<int:id>` | POST |
| teacher | `/<slug>/archivados` | GET |
| teacher | `/<slug>/archivar_profesor/<int:id>` | POST |
| teacher | `/<slug>/archivar_profesor_con_reasignacion` | POST |
| teacher | `/<slug>/reactivar_profesor/<int:id>` | POST |
| teacher | `/<slug>/eliminar_profesor/<int:id>` | POST |
| teacher | `/<slug>/comunicados` | GET |
| teacher | `/<slug>/comunicados/crear` | POST |
| teacher | `/<slug>/comunicados/<int:cid>/leer` | POST |
| teacher | `/<slug>/calendario` | GET |
| teacher | `/<slug>/estudiante/<int:aid>/expediente` | GET |
| teacher | `/<slug>/auditoria` | GET |
| teacher | `/<slug>/config` | GET, POST |
| teacher | `/<slug>/plantillas` | GET |
| teacher | `/<slug>/plantillas/crear` | POST |
| teacher | `/<slug>/plantillas/aplicar` | POST |
| teacher | `/<slug>/plantillas/eliminar/<int:tid>` | POST |
| teacher | `/<slug>/planificacion/copiar` | POST |
| teacher | `/<slug>/migrar/previsualizar` | POST |
| teacher | `/<slug>/migrar/ejecutar` | POST |
| teacher | `/<slug>/horarios` | GET, POST |
| teacher | `/<slug>/home` | GET |
| teacher | `/<slug>/ai/ask` | POST |