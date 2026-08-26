// career-radar service worker - cache shell + last data for offline viewing
const CACHE = "radar-v1";
const SHELL = ["./", "./index.html", "./match.js", "./manifest.webmanifest", "./data/latest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  // network-first for data, cache-first for shell
  if (url.pathname.endsWith("latest.json")) {
    e.respondWith(fetch(e.request).then(r => {
      const clone = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, clone));
      return r;
    }).catch(() => caches.match(e.request)));
  } else {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
