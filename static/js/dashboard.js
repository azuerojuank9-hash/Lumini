(function(){
'use strict';

document.addEventListener('DOMContentLoaded', function() {
  animateCounters();
  initCharts();
});

function animateCounters() {
  document.querySelectorAll('.animate-counter').forEach(function(el) {
    var orig = el.getAttribute('data-val');
    if (!orig) {
      orig = el.textContent.trim();
      el.setAttribute('data-val', orig);
    }
    var val = parseFloat(orig.replace(/[^0-9.-]/g, ''));
    if (isNaN(val) || val === 0 || val < 0) return;
    var duration = 500;
    var start = 0;
    var startTime = null;
    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      el.textContent = Math.floor(progress * val);
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = orig;
    }
    requestAnimationFrame(step);
  });
}

function initCharts() {
  document.querySelectorAll('[data-chart]').forEach(function(el) {
    var type = el.getAttribute('data-chart');
    if (type === 'bar') {
      var bars = el.querySelectorAll('[data-bar]');
      var max = 0;
      bars.forEach(function(b) {
        var v = parseFloat(b.getAttribute('data-bar') || '0');
        if (v > max) max = v;
      });
      if (max > 0) {
        bars.forEach(function(b) {
          var v = parseFloat(b.getAttribute('data-bar') || '0');
          b.style.setProperty('--bar-height', (v / max * 100) + '%');
          b.classList.add('chart-bar-animate');
        });
      }
    }
  });
}

window.LuminiDashboard = {
  animateCounters: animateCounters,
  initCharts: initCharts
};
})();
