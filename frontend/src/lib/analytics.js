/**
 * Google Analytics 4 і Meta Pixel. Стартують ТІЛЬКИ після згоди на cookie.
 *
 * Поки згоди немає, жоден чужий скрипт не вантажиться й жоден запит до
 * google/facebook не йде. Якщо Pixel ID порожній (не задано META_PIXEL_ID на
 * сервері), Pixel просто не вантажиться, нічого не падає.
 *
 * Події (Meta): PageView, ViewContent, Lead, InitiateCheckout. Purchase з
 * браузера НЕ йде: його шле лише бекенд після підтвердженої оплати.
 * Lead і InitiateCheckout мають event_id, ідентичний серверному (Conversions API),
 * щоб Meta зводила браузерну й серверну подію в одну.
 */
import { API_URL } from "../config.js";
import { getAnalyticsConsent, hasAnalyticsConsent, onConsentChange } from "./consent.js";

export const GA_ID = "G-F01N8FPTZH";

let pixelId = "";
let gaLoaded = false;
let pixelLoaded = false;
let lastPath = null;

/* ---------------------------------------------------------------- завантаження */

function loadGa() {
  if (gaLoaded || !GA_ID) return;
  gaLoaded = true;
  window[`ga-disable-${GA_ID}`] = false;
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() { window.dataLayer.push(arguments); };   // eslint-disable-line prefer-rest-params
  window.gtag("js", new Date());
  // send_page_view вимкнено: перегляди шле наш хук на кожну зміну маршруту (SPA)
  window.gtag("config", GA_ID, { send_page_view: false });
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(s);
}

function loadPixel() {
  if (pixelLoaded || !pixelId) return;
  pixelLoaded = true;
  // Стандартний фрагмент Meta Pixel
  /* eslint-disable */
  (function (f, b, e, v, n, t, s) {
    if (f.fbq) return;
    n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
    if (!f._fbq) f._fbq = n;
    n.push = n; n.loaded = !0; n.version = "2.0"; n.queue = [];
    t = b.createElement(e); t.async = !0; t.src = v;
    s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
  })(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
  /* eslint-enable */
  window.fbq("init", pixelId);
}

async function fetchPixelId() {
  try {
    const res = await fetch(`${API_URL}/api/public-config`);
    const data = await res.json();
    return typeof data.meta_pixel_id === "string" ? data.meta_pixel_id.trim() : "";
  } catch {
    return "";
  }
}

async function start() {
  loadGa();
  if (!pixelId) pixelId = await fetchPixelId();
  loadPixel();
  // Людина погодилась уже після відкриття сторінки: показуємо поточну як перший перегляд
  if (lastPath) sendPageView(lastPath);
}

function stop() {
  window[`ga-disable-${GA_ID}`] = true;
  try { window.fbq?.("consent", "revoke"); } catch { /* Pixel не завантажено */ }
  // Cookie, які вже поставили лічильники, прибираємо, наскільки це дозволяє браузер
  for (const name of ["_fbp", "_fbc", "_ga", `_ga_${GA_ID.replace("G-", "")}`]) {
    document.cookie = `${name}=; Max-Age=0; path=/`;
  }
}

/** Викликається один раз при старті застосунку. */
export function initAnalytics() {
  if (hasAnalyticsConsent()) start();
  onConsentChange((allowed) => (allowed ? start() : stop()));
}

/* ---------------------------------------------------------------- події */

function ga(...args) {
  if (hasAnalyticsConsent() && window.gtag) window.gtag(...args);
}

function fb(name, params, eventId) {
  if (!hasAnalyticsConsent() || !window.fbq || !pixelId) return;
  const opts = eventId ? { eventID: eventId } : undefined;
  if (opts) window.fbq("track", name, params || {}, opts);
  else window.fbq("track", name, params || {});
}

function sendPageView(path) {
  ga("event", "page_view", { page_path: path, page_location: window.location.href });
  fb("PageView");
}

/** На кожну зміну маршруту (SPA). Без згоди нічого не робить, але шлях запам'ятовує. */
export function trackPageView(path) {
  if (path === lastPath) return;
  lastPath = path;
  if (getAnalyticsConsent() === true) sendPageView(path);
}

/** Перегляд пакета чи списку пакетів. value — у гривнях. */
export function trackViewContent({ ids, name, value, type = "product" }) {
  fb("ViewContent", {
    content_ids: ids, content_name: name, content_type: type,
    ...(value ? { value, currency: "UAH" } : {}),
  });
  ga("event", "view_item", { items: (ids || []).map((id) => ({ item_id: id })), ...(value ? { value, currency: "UAH" } : {}) });
}

/** Заявка. Один і той самий eventId у Pixel і в Conversions API. Спрацьовує раз на eventId. */
export function trackLead(eventId) {
  if (!eventId) return;
  const key = `pa_lead_${eventId}`;
  try {
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
  } catch { /* приватний режим: без захисту від повтору, але подія одна на виклик */ }
  fb("Lead", {}, eventId);
  ga("event", "generate_lead");
}

/** Натиснули «Оплатити». eventId передається в замовлення, сервер шле ту саму подію в CAPI. */
export function trackInitiateCheckout({ eventId, ids, value }) {
  fb("InitiateCheckout", {
    content_ids: ids, content_type: "product", num_items: 1,
    ...(value ? { value, currency: "UAH" } : {}),
  }, eventId);
  ga("event", "begin_checkout", { ...(value ? { value, currency: "UAH" } : {}), items: (ids || []).map((id) => ({ item_id: id })) });
}
