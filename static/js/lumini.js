/* ============================================================
   LUMINI Shared UI
   ============================================================ */
(function() {
  'use strict';

  // ── Theme ──────────────────────────────────────────────────
  const STORAGE_KEY = 'theme';
  const currentTheme = localStorage.getItem(STORAGE_KEY) || 'dark';

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    const btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.innerHTML = theme === 'light'
        ? '<i class="fas fa-moon"></i>'
        : '<i class="fas fa-sun"></i>';
    }
  }

  applyTheme(currentTheme);

  document.addEventListener('click', function(e) {
    const btn = e.target.closest('#theme-toggle');
    if (btn) {
      const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      applyTheme(next);
    }
  });

  // ── Sidebar Toggle ─────────────────────────────────────────
  document.addEventListener('click', function(e) {
    const btn = e.target.closest('#sidebar-toggle, .hamburger, [data-toggle="sidebar"]');
    if (btn) {
      const sidebar = document.querySelector('.sidebar');
      if (sidebar) sidebar.classList.toggle('open');
    }
  });

  // ── Smooth scroll ──────────────────────────────────────────
  document.addEventListener('click', function(e) {
    const a = e.target.closest('a[href^="#"]');
    if (a) {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  });

  // ── Auto-close alerts ──────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.alert-auto').forEach(function(el) {
      setTimeout(function() {
        el.style.opacity = '0';
        setTimeout(function() { el.remove(); }, 300);
      }, 5000);
    });
  });

  // ── Tooltip init ───────────────────────────────────────────
  document.querySelectorAll('[data-tooltip]').forEach(function(el) {
    if (!el.getAttribute('aria-label')) {
      el.setAttribute('aria-label', el.getAttribute('data-tooltip'));
    }
  });

  // ── Empty State: agregar botón de acción ───────────────────
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.empty-state').forEach(function(el) {
      if (el.querySelector('.empty-action')) return;

      var text = el.textContent.toLowerCase().trim();
      var link = null;

      if (text.indexOf('comunicado') >= 0 || text.indexOf('aviso') >= 0) {
        link = window.location.pathname.replace(/\/+$/, '') + '/comunicaciones';
      } else if (text.indexOf('tarea') >= 0 || text.indexOf('asignacion') >= 0) {
        link = window.location.pathname.replace(/\/+$/, '') + '/tareas';
      } else if (text.indexOf('mensaje') >= 0 || text.indexOf('chat') >= 0 || text.indexOf('conversacion') >= 0) {
        link = window.location.pathname.replace(/\/+$/, '') + '/canales';
      } else if (text.indexOf('archivo') >= 0) {
        link = window.location.pathname.replace(/\/+$/, '') + '/archivos';
      } else if (text.indexOf('evento') >= 0 || text.indexOf('calendario') >= 0) {
        link = window.location.pathname.replace(/\/+$/, '') + '/calendario';
      }

      if (link) {
        var btn = document.createElement('a');
        btn.className = 'empty-action';
        btn.href = link;
        btn.innerHTML = '<i class="fas fa-arrow-right"></i> Ir';
        el.appendChild(btn);
      }
    });
  });

  // ── Animar números en .dval ────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.dval').forEach(function(el) {
      var val = parseFloat(el.textContent.replace(/[^0-9.-]/g, ''));
      if (isNaN(val) || val === 0) return;

      var duration = 600;
      var start = 0;
      var startTime = null;

      function step(timestamp) {
        if (!startTime) startTime = timestamp;
        var progress = Math.min((timestamp - startTime) / duration, 1);
        el.textContent = Math.floor(progress * val);
        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          el.textContent = val;
        }
      }
      requestAnimationFrame(step);
    });
  });

})();
