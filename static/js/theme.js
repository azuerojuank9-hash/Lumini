(function(){
'use strict';
var STORAGE_KEY = 'theme';
var currentTheme = localStorage.getItem(STORAGE_KEY) || 'dark';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(STORAGE_KEY, theme);
  var btn = document.getElementById('theme-toggle');
  var icon = btn && btn.querySelector('[data-lucide]');
  if (icon) {
    icon.setAttribute('data-lucide', theme === 'light' ? 'sun' : 'moon');
  } else if (btn) {
    btn.textContent = '';
    var i = document.createElement('i');
    i.setAttribute('data-lucide', theme === 'light' ? 'sun' : 'moon');
    i.setAttribute('aria-hidden', 'true');
    btn.appendChild(i);
  }
  if (window.lucide && lucide.createIcons) lucide.createIcons({ attrs: { 'aria-hidden': 'true' } });
  document.documentElement.style.colorScheme = theme === 'light' ? 'light' : 'dark';
}

window.toggleTheme = function() {
  var h = document.documentElement;
  var next = h.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
  applyTheme(next);
};

applyTheme(currentTheme);
})();
