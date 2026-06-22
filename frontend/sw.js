// 极简 service worker：让 PWA 可"加到主屏"。仅缓存静态外壳，API 不缓存。
const SHELL = [
  "./index.html",
  "./practice.html",
  "./graph.html",
  "./teacher.html",
  "./bg.js",
  "./api.js",
  "./manifest.json",
  "./icon.svg"
];
self.addEventListener("install", e =>
  e.waitUntil(caches.open("kr-shell-v15").then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", e =>
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== "kr-shell-v15").map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  ));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api")) return; // API 始终走网络
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
