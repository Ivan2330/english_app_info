/**
 * Згода на cookie. Дві категорії:
 *   necessary — завжди (сесія кабінету, збереження вибору в самому банері);
 *   analytics — Google Analytics 4 і Meta Pixel (+ відправка даних у Meta з сервера).
 *
 * Вибір лежить у localStorage під ключем pa_consent. Поки людина не вибрала,
 * жоден лічильник не вантажиться і нічого не йде в Meta.
 */

const KEY = "pa_consent";
const listeners = new Set();

function read() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "null");
    if (raw && typeof raw.analytics === "boolean") return raw;
  } catch { /* сховище недоступне — вважаємо, що вибору немає */ }
  return null;
}

/** null — людина ще не вибирала; true / false — вибір зроблено. */
export function getAnalyticsConsent() {
  const saved = read();
  return saved ? saved.analytics : null;
}

export function hasAnalyticsConsent() {
  return getAnalyticsConsent() === true;
}

export function setAnalyticsConsent(analytics) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ analytics: !!analytics, at: new Date().toISOString() }));
  } catch { /* не вдалося зберегти — вибір діє до перезавантаження */ }
  listeners.forEach((fn) => fn(!!analytics));
}

/** Підписка на зміну вибору (банер, футер «Налаштування cookie»). Повертає функцію відписки. */
export function onConsentChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
