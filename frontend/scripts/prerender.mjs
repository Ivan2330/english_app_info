/**
 * Після `vite build`: SEO-теги в початковому HTML кожного маршруту + sitemap.xml.
 *
 *   node scripts/prerender.mjs [папка збірки]      (за замовчуванням ./dist)
 *
 * ЧОМУ ТАК, А НЕ ПОВНИЙ ПРЕРЕНДЕР (SSR/headless-браузер у збірці):
 *   Сайт — SPA, тексти малюються JS. Googlebot виконує JS, але Telegram, Viber, Facebook
 *   і частина інших краулерів ні: вони беруть title / description / og-теги з ПЕРШОГО HTML.
 *   Повний пререндер потребує headless-браузера в Docker-збірці (сотні МБ, повільно, крихко).
 *   Тут лише «шапка»: для кожного маршруту копія index.html зі своїми title, description,
 *   canonical, og:* і robots. Тіло сторінки малює React, як і раніше.
 *
 *   Кожен маршрут пишеться файлом <маршрут>.html (/trial → dist/trial.html), а nginx віддає його
 *   через `try_files $uri $uri.html /index.html`. Не директорією з index.html: для директорії
 *   nginx робить 301 на /trial/, а canonical у нас без слеша. Невідомі адреси лишаються на /index.html.
 *
 * Дані беруться з src/lib/seoData.js: те саме джерело, що й у браузері (useRouteSeo).
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.resolve(process.argv[2] || path.join(root, "dist"));
const { ROUTES, SITE, canonicalFor } = await import(pathToFileURL(path.join(root, "src/lib/seoData.js")).href);

const esc = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

function replaceOnce(html, re, replacement, what) {
  if (!re.test(html)) throw new Error(`prerender: у index.html не знайдено ${what}`);
  return html.replace(re, () => replacement);
}

export function render(base, route, meta) {
  let html = base;
  html = replaceOnce(html, /<title>[\s\S]*?<\/title>/, `<title>${esc(meta.title)}</title>`, "<title>");
  html = replaceOnce(html, /<meta\s+name="description"[\s\S]*?\/>/, `<meta name="description" content="${esc(meta.description)}" />`, "meta description");
  html = replaceOnce(html, /<link rel="canonical"[^>]*\/>/, `<link rel="canonical" href="${canonicalFor(route)}" />`, "canonical");
  html = replaceOnce(html, /<meta property="og:url"[^>]*\/>/, `<meta property="og:url" content="${canonicalFor(route)}" />`, "og:url");
  html = replaceOnce(html, /<meta property="og:title"[^>]*\/>/, `<meta property="og:title" content="${esc(meta.title)}" />`, "og:title");
  html = replaceOnce(html, /<meta\s+property="og:description"[\s\S]*?\/>/, `<meta property="og:description" content="${esc(meta.description)}" />`, "og:description");
  if (meta.noindex) {
    html = html.replace("</head>", `    <meta name="robots" content="noindex, nofollow" />\n  </head>`);
  }
  return html;
}

export function sitemap(date) {
  const urls = Object.entries(ROUTES)
    .filter(([, m]) => !m.noindex)
    .map(([route, m]) => `  <url><loc>${canonicalFor(route)}</loc><lastmod>${date}</lastmod><priority>${(m.priority ?? 0.5).toFixed(1)}</priority></url>`);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join("\n")}\n</urlset>\n`;
}

const base = await readFile(path.join(dist, "index.html"), "utf8");
let written = 0;
for (const [route, meta] of Object.entries(ROUTES)) {
  const html = render(base, route, meta);
  if (route === "/") {
    await writeFile(path.join(dist, "index.html"), html);
  } else {
    const parts = route.split("/").filter(Boolean);
    const file = path.join(dist, ...parts.slice(0, -1), `${parts[parts.length - 1]}.html`);
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, html);
  }
  written += 1;
}
const today = new Date().toISOString().slice(0, 10);
await writeFile(path.join(dist, "sitemap.xml"), sitemap(today));
console.log(`prerender: ${written} маршрутів, sitemap.xml (${SITE})`);
