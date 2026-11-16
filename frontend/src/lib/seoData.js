/**
 * SEO кожного маршруту: title, description, чи індексувати.
 *
 * Єдине джерело для трьох місць:
 *   1) useRouteSeo() у браузері: оновлює теги при переході між сторінками (SPA);
 *   2) scripts/prerender.mjs при збірці: пише ці самі теги в початковий HTML
 *      кожного маршруту, щоб їх бачили краулери й сканери посилань, які не виконують JS
 *      (Telegram, Facebook, Viber, частина пошукових ботів);
 *   3) scripts/prerender.mjs: генерує sitemap.xml з усіх індексованих маршрутів.
 *
 * Файл без імпортів, тому його читає й браузер, і Node.
 * title до ~60 символів, description до ~155: довше Google обрізає.
 * Лише перевірені факти (див. CLAUDE.md): пробний 40 хв без картки, групи до 6, урок групи 90 хв.
 */
export const SITE = "https://my-prime-academy.com";
export const SITE_NAME = "Prime Academy";
export const OG_IMAGE = `${SITE}/og-image.jpg`;

export const ROUTES = {
  "/": {
    title: "Prime Academy — онлайн школа англійської мови",
    description: "Індивідуальні уроки, заняття в парі та міні-групи до 6 людей. Підготовка до IELTS, TOEFL і НМТ, англійська для роботи та подорожей. Перший пробний урок безкоштовний.",
    priority: 1.0,
  },
  "/trial": {
    title: "Безкоштовний пробний урок англійської онлайн | Prime Academy",
    description: "40 хвилин із викладачем по відеозв'язку: діагностика рівня й персональний план. Без оплати й без картки. Індивідуально, в парі або в групі до 6 людей.",
    priority: 0.9,
  },
  "/packages": {
    title: "Ціни на уроки англійської: пакети й оплата | Prime Academy",
    description: "Індивідуальні уроки, пара й міні-групи до 6 людей. Пакети від 6 уроків, ціна за урок зрозуміла наперед, доступна Покупка Частинами monobank.",
    priority: 0.9,
  },
  "/programs": {
    title: "Програми англійської: розмовна, бізнес, IELTS, НМТ | Prime Academy",
    description: "Загальна й розмовна англійська, для роботи й IT, підготовка до IELTS і НМТ, англійська для подорожей. Оберіть напрям під свою ціль.",
    priority: 0.9,
  },
  "/about": {
    title: "Про школу Prime Academy: як ми вчимо англійську",
    description: "Рівні CEFR від A1 до C1, формати занять, гарантія рівня на індивідуальному курсі, сертифікат із перевіркою за номером.",
    priority: 0.7,
  },
  "/contacts": {
    title: "Контакти Prime Academy: запис на пробний урок",
    description: "Телефон, пошта й Instagram школи. Залиште заявку на безкоштовний пробний урок: напишемо вам протягом 15 хвилин у робочий час.",
    priority: 0.8,
  },
  "/level-test": {
    title: "Тест рівня англійської онлайн, безкоштовно | Prime Academy",
    description: "Перевірте рівень англійської за 25 питань і дізнайтесь, з чого почати. Викладач бачить відповіді до пробного уроку.",
    priority: 0.8,
  },
  "/guarantee": {
    title: "Гарантія результату | Prime Academy",
    description: "Умови гарантії: що саме ми гарантуємо, для яких курсів вона діє і що потрібно від вас.",
    priority: 0.5,
  },
  "/verify-certificate": {
    title: "Перевірка сертифіката Prime Academy за номером",
    description: "Введіть номер сертифіката або відскануйте QR-код, щоб переконатись, що документ справжній.",
    priority: 0.3,
  },
  "/offer": {
    title: "Публічна оферта | Prime Academy",
    description: "Договір публічної оферти Prime Academy: умови навчання, оплати, перенесення занять і повернення коштів.",
    priority: 0.4,
  },
  "/privacy": {
    title: "Політика конфіденційності | Prime Academy",
    description: "Які дані ми збираємо, навіщо, кому передаємо і як ви можете ними керувати, включно з cookie.",
    priority: 0.3,
  },
  // Службові сторінки: не індексуємо, не кладемо в sitemap
  "/thanks": { title: "Дякуємо за заявку | Prime Academy", description: "Заявку прийнято.", noindex: true },
  "/checkout": { title: "Оформлення замовлення | Prime Academy", description: "Оформлення замовлення.", noindex: true },
  "/payment/result": { title: "Результат оплати | Prime Academy", description: "Результат оплати.", noindex: true },
};

export const NOT_FOUND = { title: "Сторінку не знайдено | Prime Academy", description: "Такої сторінки немає.", noindex: true };
export const ADMIN = { title: "Кабінет | Prime Academy", description: "Службова сторінка.", noindex: true };

export function metaFor(pathname) {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (path === "/admin" || path.startsWith("/admin/")) return { path, ...ADMIN };
  return { path, ...(ROUTES[path] || NOT_FOUND) };
}

export function canonicalFor(path) {
  return `${SITE}${path === "/" ? "/" : path}`;
}
