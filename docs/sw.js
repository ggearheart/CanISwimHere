// Service worker for "Can I Swim Here?" — uses relative URLs so it works under
// any base path (local dev or GitHub Pages project subfolder).
const CACHE = 'caniswim-v8';
const DATA_CACHE = 'caniswim-data-v1';
const SHELL = [
  './',
  './index.html',
  './manifest.json',
  './waterboards-logo.png',
  './hab-marker.png',
  './icon-192.png',
  './icon-512.png',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE && k !== DATA_CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = e.request.url;
  const isData = url.includes('stations.json') || url.includes('hazards.json') || url.includes('blooms.json') || url.includes('pfd_stations.json') || url.includes('data.ca.gov') || url.includes('waterservices.usgs.gov');
  const isShell = url.includes('index.html') || url.endsWith('/');

  if (isData) {
    e.respondWith(
      fetch(e.request.clone())
        .then(res => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(DATA_CACHE).then(c => {
              c.put(e.request, clone);
              c.put('cached-at', new Response(Date.now().toString()));
            });
          }
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(e.request, { cacheName: DATA_CACHE });
          if (cached) {
            const body = await cached.clone().text();
            return new Response(body, { headers: { 'Content-Type': 'application/json', 'X-From-Cache': 'true' } });
          }
          return new Response('{"stations":[]}', { headers: { 'Content-Type': 'application/json', 'X-From-Cache': 'true' } });
        })
    );
  } else if (isShell) {
    e.respondWith(
      fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      }).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
        if (res.ok) { const clone = res.clone(); caches.open(CACHE).then(c => c.put(e.request, clone)); }
        return res;
      }))
    );
  }
});

self.addEventListener('message', e => {
  if (e.data === 'get-cached-at') {
    caches.open(DATA_CACHE).then(c => c.match('cached-at')).then(r => {
      r ? r.text().then(ts => e.source.postMessage({ type: 'cached-at', ts: Number(ts) }))
        : e.source.postMessage({ type: 'cached-at', ts: null });
    });
  }
});
