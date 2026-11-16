/**
 * Звідки прийшла людина (UTM, fbclid): перший і останній дотик, 90 днів.
 *
 * first touch — перший відомий візит; не перезаписується, поки не мине 90 днів.
 * last touch  — оновлюється, коли візит приходить із новою кампанією (utm_* / fbclid)
 *               або із зовнішнього сайту.
 *
 * Це власні дані для заявок і замовлень, вони нікуди стороннім не передаються.
 * Реферер зберігаємо лише як домен (як і власний лічильник відвідувань), а
 * landing_page — лише шлях без параметрів.
 *
 * Лічильник не має права зламати сайт: усе в try/catch.
 */
import { hasAnalyticsConsent } from "./consent.js";

const KEY = "pa_attr";
const DAYS_90 = 90 * 24 * 3600 * 1000;
const PARAMS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid"];

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "null");
    if (raw && typeof raw === "object") return raw;
  } catch { /* порожньо */ }
  return {};
}

function save(state) {
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* приватний режим */ }
}

function cookie(name) {
  const hit = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : "";
}

function externalReferrerHost() {
  try {
    const host = new URL(document.referrer).hostname.replace(/^www\./, "");
    if (!host || host.endsWith("my-prime-academy.com") || host === "localhost" || host === "127.0.0.1") return "";
    return host;
  } catch { return ""; }
}

/** Викликається один раз при завантаженні сторінки (див. main.jsx). */
export function captureAttribution() {
  try {
    const now = Date.now();
    const state = load();
    const q = new URLSearchParams(window.location.search);

    const touch = {};
    for (const key of PARAMS) {
      const v = q.get(key);
      if (v) touch[key] = v.slice(0, 200);
    }
    const referrer = externalReferrerHost();
    const campaign = Object.keys(touch).length > 0;
    if (referrer) touch.referrer = referrer;
    if (campaign || referrer) touch.landing_page = window.location.pathname.slice(0, 300);

    const firstValid = state.first && now - state.first.at < DAYS_90;
    const lastValid = state.last && now - state.last.at < DAYS_90;
    const next = { first: firstValid ? state.first : null, last: lastValid ? state.last : null };

    // Перший візит: фіксуємо навіть «прямий» (тоді в дотику лише landing_page)
    if (!next.first) {
      next.first = { at: now, ...touch, landing_page: touch.landing_page || window.location.pathname.slice(0, 300) };
    }
    // Новий дотик із кампанії чи зовнішнього сайту перекриває останній
    if (campaign || referrer) next.last = { at: now, ...touch };

    save(next);
  } catch { /* атрибуція — не критична */ }
}

function strip(touch) {
  if (!touch) return null;
  const { at, ...rest } = touch;     // eslint-disable-line no-unused-vars
  return Object.keys(rest).length ? rest : null;
}

export function getAttribution() {
  const { first, last } = load();
  return { first_touch: strip(first), last_touch: strip(last) };
}

/** Meta-cookie _fbc, а якщо її ще немає, а fbclid є, збираємо за форматом Meta: fb.1.<мс>.<fbclid>. */
export function getFbc() {
  const fromCookie = cookie("_fbc");
  if (fromCookie) return fromCookie;
  const { first, last } = load();
  // Час і fbclid мають бути з одного й того самого дотику
  const touch = last && last.fbclid ? last : first && first.fbclid ? first : null;
  return touch ? `fb.1.${touch.at}.${touch.fbclid}` : "";
}

export function getFbp() {
  return cookie("_fbp");
}

/**
 * Поля, які додаються до кожної заявки й замовлення.
 * Дані для Meta (fbp, fbc, згода) йдуть лише якщо людина погодилась на cookie:
 * без згоди сервер нічого в Meta не відправить.
 */
export function attributionPayload() {
  const consent = hasAnalyticsConsent();
  const out = {
    attribution: getAttribution(),
    event_source_url: window.location.origin + window.location.pathname,
    meta_consent: consent,
  };
  if (consent) {
    out.fbp = getFbp() || undefined;
    out.fbc = getFbc() || undefined;
  }
  return out;
}

/** Унікальний id події: один і той самий іде в Pixel і в Conversions API (дедуплікація). */
export function newEventId() {
  try {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  } catch { /* старий браузер */ }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}
