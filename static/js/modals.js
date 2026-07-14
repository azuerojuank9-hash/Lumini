(function(){
'use strict';

window.openModal = function(id) {
  var el = document.getElementById(id);
  if (!el) return;
  el.style.display = 'flex';
  el.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  var firstInput = el.querySelector('input, button, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (firstInput) firstInput.focus();
};

window.closeModal = function(id) {
  var el = document.getElementById(id);
  if (!el) return;
  el.style.display = 'none';
  el.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
};

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay').forEach(function(m) {
      if (m.style.display === 'flex' || m.style.display === '') {
        m.style.display = 'none';
        m.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
      }
    });
  }
});

document.addEventListener('click', function(e) {
  var overlay = e.target.closest('.modal-overlay');
  if (overlay && e.target === overlay) {
    overlay.style.display = 'none';
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }
});
})();
