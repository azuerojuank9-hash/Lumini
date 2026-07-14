(function(){
'use strict';

window.setAttendance = function(alumnoId, fecha, estado, csrf) {
  var payload = { alumno_id: alumnoId, fecha: fecha, estado: estado, _csrf_token: csrf };
  fetch('/api/v1/attendance', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(function(r) { return r.json(); }).then(function(data) {
    if (data.success) {
      var badge = document.querySelector('[data-attendance="' + alumnoId + '-' + fecha + '"]');
      if (badge) {
        var clsMap = { 'presente': 'badge-success', 'ausente': 'badge-danger', 'tardanza': 'badge-warning' };
        badge.className = 'badge ' + (clsMap[estado] || 'badge-neutral');
        badge.textContent = estado;
      }
      if (window.showToast) window.showToast('Asistencia actualizada', 'success');
    } else {
      if (window.showToast) window.showToast(data.error || 'Error al actualizar asistencia', 'error');
    }
  }).catch(function() {
    if (window.showToast) window.showToast('Error de conexión', 'error');
  });
};

window.markBulkAttendance = function(cursoId, fecha, estado, csrf) {
  if (!confirm('¿Marcar a todos como ' + estado + '?')) return;
  fetch('/api/v1/attendance/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ curso_id: cursoId, fecha: fecha, estado: estado, _csrf_token: csrf })
  }).then(function(r) { return r.json(); }).then(function(data) {
    if (data.success) {
      location.reload();
    } else {
      alert(data.error || 'Error');
    }
  });
};
})();
