(function(){
'use strict';

var NotificationManager = {
  swRegistration: null,

  init: function() {
    if (!('Notification' in window) || !('serviceWorker' in navigator)) return;
    if (Notification.permission === 'granted') {
      this.setupPush();
    }
  },

  requestPermission: function() {
    return Notification.requestPermission().then(function(permission) {
      if (permission === 'granted') {
        NotificationManager.setupPush();
      }
      return permission;
    });
  },

  setupPush: function() {
    navigator.serviceWorker.ready.then(function(reg) {
      NotificationManager.swRegistration = reg;
    });
  },

  subscribe: function() {
    if (!this.swRegistration) return Promise.reject('SW not ready');
    return this.swRegistration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: null
    }).then(function(sub) {
      return sub.toJSON();
    });
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

window.NotificationManager = NotificationManager;
})();
