/**
 * Власний лічильник відвідувань.
 *
 * Google Analytics лишається, але покладатися тільки на нього не можна:
 * трафік іде з Instagram, де аудиторія молодша й активніше блокує лічильники.
 * Цей запит іде на свій же домен, тож блокувальники його не ріжуть.
 *
 * Правило номер один: лічильник ніколи не має вплинути на сайт.
 * Тому `keepalive`, повне ігнорування помилок і жодного await у компонентах.
 */

import { API_URL } from "../config.js";

/** Реферер беремо один раз за сесію: далі ним стане наша ж сторінка. */
let initialReferrer = typeof document !== "undefined" ? document.referrer : "";
let lastPath = null;

export function trackVisit(path) {
  // Подвійний виклик на той самий шлях буває при швидкій навігації туди-назад
  if (path === lastPath) return;
  lastPath = path;

  let utm = {};
  try {
    const p = new URLSearchParams(window.location.search);
    utm = {
      utm_source: p.get("utm_source") || undefined,
      utm_medium: p.get("utm_medium") || undefined,
      utm_campaign: p.get("utm_campaign") || undefined,
    };
  } catch {
    /* параметрів немає — не біда */
  }

  const body = JSON.stringify({ path, referrer: initialReferrer, ...utm });
  initialReferrer = "";   // далі реферером буде наш же сайт

  try {
    fetch(`${API_URL}/api/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      // Запит має долетіти, навіть якщо людина одразу закриває вкладку
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* лічильник не має права зламати сторінку */
  }
}
