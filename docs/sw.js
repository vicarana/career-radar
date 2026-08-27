// career-radar service worker - cache shell + last data for offline viewing
// CACHE must be bumped every time shell files (index.html, match.js,
// pipeline.js, sprint.js, style.css) change, otherwise cache-first below
// serves a permanently stale UI no matter how many times the real files
// change upstream (this bit Vic on 2026-08-27: sidebar/Pipeline/US-Visa
// redesign was live in the repo but browsers kept rendering the old
// top-tab-bar shell from an install months earlier).
const CACHE = "radar-v2";
const SHELL = ["./", "./index.html", "./match.js", "./pipeline.js", "./sprint.js",
  "./style.css", "./manifest.webmanifest", "./data/latest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
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
