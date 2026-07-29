var CACHE_NAME = 'lumini-v1';
var STATIC_CACHE = 'lumini-static-v1';
var OFFLINE_URL = '/offline';

var urlsToCache = [
  '/static/manifest.json',
  '/static/css/sidebar.css',
  '/static/js/pwa.js',
  '/offline',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(STATIC_CACHE).then(function(cache) {
      return cache.addAll(urlsToCache);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(names) {
      return Promise.all(
        names.map(function(name) {
          if (name !== STATIC_CACHE && name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', function(e) {
  var req = e.request;
  var url = new URL(req.url);

  if (url.origin !== self.location.origin) {
    return;
  }

  if (req.method !== 'GET') {
    return;
  }

  var path = url.pathname;

  if (path.startsWith('/api/')) {
    return;
  }

  if (path.match(/\.(css|js)$/)) {
    e.respondWith(cacheFirst(req));
    return;
  }

  if (path.match(/\.(webp|png|jpg|jpeg|gif|svg|ico)$/)) {
    e.respondWith(cacheFirst(req));
    return;
  }

  if (path.match(/\.(woff|woff2|ttf|eot)$/)) {
    e.respondWith(cacheFirst(req));
    return;
  }

  if (req.mode === 'navigate') {
    e.respondWith(networkFirst(req));
    return;
  }

  e.respondWith(networkFirst(req));
});

function cacheFirst(req) {
  return caches.match(req).then(function(resp) {
    if (resp) {
      return resp;
    }
    return fetchAndCache(req);
  });
}

function networkFirst(req) {
  return fetch(req).then(function(resp) {
    if (resp && resp.status === 200) {
      var clone = resp.clone();
      caches.open(STATIC_CACHE).then(function(cache) {
        if (req.method === 'GET') {
          cache.put(req, clone);
        }
      });
    }
    return resp;
  }).catch(function() {
    return caches.match(req).then(function(resp) {
      if (resp) {
        return resp;
      }
      return caches.match(OFFLINE_URL);
    });
  });
}

function fetchAndCache(req) {
  return fetch(req).then(function(resp) {
    if (resp && resp.status === 200) {
      var clone = resp.clone();
      caches.open(STATIC_CACHE).then(function(cache) {
        cache.put(req, clone);
      });
    }
    return resp;
  }).catch(function() {
    return caches.match(req);
  });
}
