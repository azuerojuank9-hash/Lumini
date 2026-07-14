(function(){
'use strict';

window.filterTable = function(input, tableId) {
  var q = input.value.toLowerCase();
  var table = document.getElementById(tableId);
  if (!table) return;
  var rows = table.querySelectorAll('tbody tr');
  var count = 0;
  rows.forEach(function(r) {
    var match = false;
    r.querySelectorAll('td').forEach(function(c) {
      if (c.textContent.toLowerCase().includes(q)) match = true;
    });
    r.style.display = match ? '' : 'none';
    if (match) count++;
  });
  var c = document.getElementById(tableId + '-count');
  if (c) c.textContent = count + ' registro(s)';
};

window.sortTable = function(tableId, col) {
  var table = document.getElementById(tableId);
  if (!table) return;
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var header = table.querySelectorAll('th')[col];
  var asc = header.classList.contains('sort-asc');
  table.querySelectorAll('th').forEach(function(h) {
    h.classList.remove('sort-asc', 'sort-desc');
  });
  header.classList.add(asc ? 'sort-desc' : 'sort-asc');
  rows.sort(function(a, b) {
    var av = (a.querySelectorAll('td')[col] || {}).textContent || '';
    var bv = (b.querySelectorAll('td')[col] || {}).textContent || '';
    var an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) { av = an; bv = bn; }
    if (av < bv) return asc ? 1 : -1;
    if (av > bv) return asc ? -1 : 1;
    return 0;
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
};

window.toggleAllRows = function(cb, tableId) {
  document.querySelectorAll('#' + tableId + ' .row-checkbox').forEach(function(r) { r.checked = cb.checked; });
  document.querySelectorAll('#' + tableId + ' tbody tr').forEach(function(r) { r.classList.toggle('selected', cb.checked); });
};

window.toggleRow = function(row) {
  var cb = row.querySelector('.row-checkbox');
  if (cb) { cb.checked = !cb.checked; row.classList.toggle('selected', cb.checked); }
};
})();
