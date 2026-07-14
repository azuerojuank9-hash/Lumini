(function(){
'use strict';
window.LuminiUtils = {
  debounce: function(fn, ms) {
    var timer;
    return function() {
      var ctx = this, args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function() { fn.apply(ctx, args); }, ms);
    };
  },
  throttle: function(fn, ms) {
    var last = 0;
    return function() {
      var now = Date.now();
      if (now - last >= ms) { last = now; fn.apply(this, arguments); }
    };
  },
  formatDate: function(dateStr) {
    if (!dateStr) return '';
    var d = new Date(dateStr);
    return d.toLocaleDateString('es-ES', { day:'2-digit', month:'2-digit', year:'numeric' });
  },
  formatNumber: function(n) {
    return Number(n).toLocaleString('es-ES');
  },
  formatCurrency: function(n) {
    return '$' + Number(n).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },
  getEl: function(id) { return document.getElementById(id); },
  qs: function(sel, ctx) { return (ctx || document).querySelector(sel); },
  qsa: function(sel, ctx) { return (ctx || document).querySelectorAll(sel); },
  on: function(el, evt, fn) {
    if (el) el.addEventListener(evt, fn);
  }
};
})();
