(function(){
'use strict';

window.showToast = function(message, type, duration) {
  type = type || 'info';
  duration = duration || 3500;
  var c = document.getElementById('toast-container');
  if (!c) {
    c = document.createElement('div');
    c.id = 'toast-container';
    c.className = 'toast-container';
    document.body.appendChild(c);
  }
  var t = document.createElement('div');
  t.className = 'toast toast-' + type + ' toast-enter';
  var iconMap = { success: 'check-circle', error: 'alert-triangle', info: 'info', warning: 'alert-circle' };
  var iconName = iconMap[type] || 'info';
  var body = message == null ? '' : String(message);
  var iconTag = body.match(/^<i\s+data-lucide=["']([A-Za-z0-9-]+)["'][^>]*>\s*<\/i>\s*/);
  if (iconTag) {
    iconName = iconTag[1];
    body = body.slice(iconTag[0].length);
  }
  var iconSpan = document.createElement('span');
  iconSpan.className = 'toast-icon';
  var iconEl = document.createElement('i');
  iconEl.setAttribute('data-lucide', iconName);
  iconEl.setAttribute('width', '16');
  iconEl.setAttribute('height', '16');
  iconEl.setAttribute('aria-hidden', 'true');
  iconSpan.appendChild(iconEl);
  var msgEl = document.createElement('span');
  msgEl.className = 'toast-message';
  msgEl.textContent = body;
  t.appendChild(iconSpan);
  t.appendChild(msgEl);
  t.insertAdjacentHTML('beforeend', '<button class="toast-close btn-icon-sm btn-ghost" onclick="this.closest(\'.toast\').remove()" aria-label="Cerrar"><i data-lucide="x" width="12" height="12"></i></button>');
  c.appendChild(t);
  if (window.lucide) lucide.createIcons({ attrs: { 'aria-hidden': 'true' } }, t);
  setTimeout(function() {
    t.classList.remove('toast-enter');
    t.classList.add('toast-exit');
    setTimeout(function() { t.remove(); }, 300);
  }, duration);
};

var LuminiNotify = {
  swRegistration: null,
  init: function() {
    if (!('Notification' in window) || !('serviceWorker' in navigator)) return;
    if (Notification.permission === 'granted') this.setupPush();
  },
  requestPermission: function() {
    return Notification.requestPermission().then(function(permission) {
      if (permission === 'granted') LuminiNotify.setupPush();
      return permission;
    });
  },
  setupPush: function() {
    navigator.serviceWorker.ready.then(function(reg) { LuminiNotify.swRegistration = reg; });
  },
  subscribe: function() {
    if (!this.swRegistration) return Promise.reject('SW not ready');
    return this.swRegistration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: null
    }).then(function(sub) { return sub.toJSON(); });
  },
  unsubscribe: function() {
    if (!this.swRegistration) return Promise.reject('SW not ready');
    return this.swRegistration.pushManager.getSubscription().then(function(sub) {
      if (sub) return sub.unsubscribe();
    });
  },
  isSupported: function() {
    return 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
  }
};
window.LuminiNotify = LuminiNotify;
})();
