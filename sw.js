/* 🛜 離線支援：把工具外殼存進瀏覽器快取，沒網路也能打開畫面（免費複製貼上那條路照常用）。
   策略：HTML 走「網路優先」——有網路永遠拿最新（自動更新偵測照常運作），沒網路才退回快取。
        圖示/設定/CDN 走「快取優先」。ver.txt 完全不攔，保持每次連線即時比對版本。
   ⚠️ 每次部署若想讓離線快取也更新，把下面 CACHE 後面的版本號改成跟 ver.txt 一樣。 */
const CACHE = "ebn-2026062121";
const SHELL = [
  "./evidence.html", "./search.html", "./lawyer.html", "./share.html",
  "./finance.html", "./finance-law.js", "./receipt.html", "./union.html", "./jianshi.html", "./plan.html", "./roster.html", "./meeting.html", "./gongwen.html", "./activity.html",
  "./icon-evidence.png", "./icon-search.png", "./icon-lawyer.png",
  "./evidence.webmanifest", "./search.webmanifest", "./lawyer.webmanifest", "./finance.webmanifest", "./receipt.webmanifest", "./jianshi.webmanifest", "./plan.webmanifest", "./roster.webmanifest", "./meeting.webmanifest", "./gongwen.webmanifest", "./activity.webmanifest",
  "https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js",
  "https://cdn.jsdelivr.net/gh/davidshimjs/qrcodejs@master/qrcode.min.js"
];

self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => Promise.allSettled(SHELL.map(u => c.add(u)))));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.endsWith("/ver.txt") || url.pathname.endsWith("ver.txt")) return; // 版本檔不攔，永遠走網路
  if (url.pathname.endsWith("/laws.json") || url.pathname.endsWith("laws.json")) return; // 法規檔不攔，永遠拿最新官方版

  // HTML / 導覽：網路優先，失敗退快取（離線也能開）
  if (req.mode === "navigate" || req.destination === "document") {
    e.respondWith(
      fetch(req).then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); return r; })
        .catch(() => caches.match(req).then(m => m ||
          caches.match(url.pathname.indexOf("lawyer") >= 0 ? "./lawyer.html"
            : url.pathname.indexOf("search") >= 0 ? "./search.html" : "./evidence.html")))
    );
    return;
  }

  // 其他靜態資源（圖示/設定/CDN）：快取優先，沒有才上網抓並順手存起來
  e.respondWith(
    caches.match(req).then(m => m || fetch(req).then(r => {
      const cp = r.clone(); caches.open(CACHE).then(c => c.put(req, cp)); return r;
    }).catch(() => m))
  );
});
