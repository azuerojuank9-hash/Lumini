/* ============================================================
   LUMINI Shared UI — v2.0
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

  // ── Sidebar Toggle (hamburger) ──────────────────────────────
  document.addEventListener('click', function(e) {
    const btn = e.target.closest('#sidebar-toggle, .hamburger, [data-toggle="sidebar"]');
    if (btn) {
      const sidebar = document.querySelector('.sidebar');
      if (sidebar) {
        sidebar.classList.toggle('open');
      }
    }
  });

  // ── Smooth scroll for anchor links ─────────────────────────
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

  // ── Auto-close alerts after 5s ─────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.alert-auto').forEach(function(el) {
      setTimeout(function() { el.style.opacity = '0'; setTimeout(function() { el.remove(); }, 300); }, 5000);
    });
  });

  // ── Tooltip initializer ────────────────────────────────────
  document.querySelectorAll('[data-tooltip]').forEach(function(el) {
    if (!el.getAttribute('aria-label')) {
      el.setAttribute('aria-label', el.getAttribute('data-tooltip'));
    }
  });

})();
