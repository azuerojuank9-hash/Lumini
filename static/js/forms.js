(function(){
'use strict';

document.addEventListener('input', function(e) {
  var field = e.target.closest('.form-input, .form-select, .form-textarea');
  if (!field) return;
  var group = field.closest('.form-group');
  if (!group) return;
  var errorEl = group.querySelector('.form-error');
  if (errorEl) {
    if (field.value.trim()) {
      errorEl.classList.remove('visible');
      field.classList.remove('error');
    }
  }
  if (field.value !== (field.defaultValue || '')) {
    group.classList.add('form-dirty');
  } else {
    group.classList.remove('form-dirty');
  }
});

document.addEventListener('submit', function(e) {
  var form = e.target.closest('form');
  if (!form) return;
  var firstError = null;
  form.querySelectorAll('[required]').forEach(function(f) {
    if (!f.value || !f.value.trim()) {
      f.classList.add('error');
      var group = f.closest('.form-group');
      if (group) {
        var err = group.querySelector('.form-error');
        if (err) { err.textContent = 'Este campo es obligatorio'; err.classList.add('visible'); }
      }
      if (!firstError) firstError = f;
    }
  });
  if (firstError) {
    e.preventDefault();
    firstError.focus();
  }
});

window.validateForm = function(formId) {
  var form = document.getElementById(formId);
  if (!form) return true;
  var valid = true;
  form.querySelectorAll('[required]').forEach(function(f) {
    if (!f.value || !f.value.trim()) {
      f.classList.add('error');
      valid = false;
    } else {
      f.classList.remove('error');
    }
  });
  return valid;
};

window.clearForm = function(formId) {
  var form = document.getElementById(formId);
  if (!form) return;
  form.reset();
  form.querySelectorAll('.form-error.visible').forEach(function(e) { e.classList.remove('visible'); });
  form.querySelectorAll('.error').forEach(function(e) { e.classList.remove('error'); });
};
})();
