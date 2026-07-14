(function(){
'use strict';

var deferredPrompt = null;

document.addEventListener('DOMContentLoaded', function() {
  if ('serviceWorker' in navigator) {
    registerSW();
  }
  handleStandalone();
});

function registerSW() {
  navigator.serviceWorker.register('/static/sw.js', {scope: '/'}).then(function(reg) {
    reg.onupdatefound = function() {
      var installing = reg.installing;
      if (!installing) return;
      installing.onstatechange = function() {
        if (installing.state === 'installed' && navigator.serviceWorker.controller) {
          showUpdateBanner();
        }
      };
    };
  }).catch(function() {
    console.log('[PWA] SW registration failed');
  });
}

function showUpdateBanner() {
  var banner = document.getElementById('update-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'update-banner';
    banner.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:99999;background:var(--bg2);border:1px solid var(--border);border-radius:var(--rmd);padding:12px 20px;box-shadow:0 8px 32px rgba(0,0,0,.4);display:flex;align-items:center;gap:14px;font-size:13px;max-width:90vw;';
    banner.innerHTML = '<span style="color:var(--text);">Nueva versión disponible</span><button onclick="location.reload()" style="background:var(--accent);color:#fff;border:none;border-radius:var(--rsm);padding:8px 16px;font-size:12px;font-weight:600;cursor:pointer;">Actualizar</button>';
    document.body.appendChild(banner);
  }
  banner.style.display = 'flex';
}

function handleStandalone() {
  if (window.matchMedia('(display-mode: standalone)').matches) {
    var themeToggle = document.querySelector('[aria-label="Cambiar tema"]');
    if (themeToggle) themeToggle.style.display = 'none';
    var ham = document.querySelector('.hamburger');
    if (ham) ham.style.display = 'none';
  }
}

window.addEventListener('beforeinstallprompt', function(e) {
  e.preventDefault();
  deferredPrompt = e;
  showInstallButton();
});

window.addEventListener('appinstalled', function() {
  deferredPrompt = null;
  hideInstallButton();
});

function showInstallButton() {
  var container = document.getElementById('pwa-install-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'pwa-install-container';
    container.style.cssText = 'position:fixed;bottom:70px;left:50%;transform:translateX(-50%);z-index:99999;';
    var btn = document.createElement('button');
    btn.id = 'pwa-install-btn';
    btn.textContent = 'Instalar aplicación';
    btn.style.cssText = 'background:var(--accent);color:#fff;border:none;border-radius:var(--rmd);padding:10px 24px;font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,.3);';
    btn.onclick = installApp;
    container.appendChild(btn);
    document.body.appendChild(container);
  }
  container.style.display = 'block';
}

function hideInstallButton() {
  var container = document.getElementById('pwa-install-container');
  if (container) container.style.display = 'none';
}

function installApp() {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  deferredPrompt.userChoice.then(function(choice) {
    deferredPrompt = null;
    hideInstallButton();
  });
}

})();
