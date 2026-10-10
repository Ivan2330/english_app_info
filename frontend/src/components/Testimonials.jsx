/**
 * Відгуки — СЕКЦІЯ ВИМКНЕНА, компонент лишений навмисно.
 *
 * На сайті стояли порожні картки-плейсхолдери «Відгук #1 · Ім'я · напрямок».
 * Вони не викликають довіри, а прямо повідомляють, що відгуків немає, —
 * це гірше за відсутність секції. Тому блок прибрано з `Home.jsx`
 * до моменту, коли зберуться 5–8 справжніх.
 *
 * ВИГАДАНИХ ВІДГУКІВ НЕ ДОДАВАТИ. Це не питання смаку:
 *   · заборонена оманлива практика за законом про захист прав споживачів;
 *   · порушення правил Google Ads і Meta — аж до блокування рекламного
 *     акаунта, тобто втрати основного каналу трафіку.
 *
 * ЯК ПОВЕРНУТИ
 * ============
 * 1. Заповнити `ITEMS` реальними відгуками (ім'я — з дозволу людини).
 * 2. Розкоментувати секцію в `pages/Home.jsx` — там лишено пояснення.
 * Стилі `.tst*` у `styles/sections.css` на місці, чіпати їх не треба.
 *
 * Два ряди їдуть у протилежні боки й зупиняються на наведення
 * (`.tst-row--a` / `--b`). Менше ніж на п'яти картках рух виглядає
 * як смикання — це друга причина не вмикати секцію завчасно.
 */

/** @type {{name: string, meta: string, text: string[], tags?: string[]}[]} */
const ITEMS = [];

export default function Testimonials() {
  // Порожній масив — секції немає. Захист від випадкового рендеру
  // порожньої каруселі, якщо компонент десь підключать, не заповнивши ITEMS.
  if (ITEMS.length === 0) return null;

  const row = (items, mod) => (
    <div className={`tst-row tst-row--${mod}`}>
      {items.map((t) => (
        <article key={t.name + t.text[0]} className="tst">
          <header className="tst__head">
            <span className="tst__avatar" aria-hidden="true">
              {t.name.trim().charAt(0)}
            </span>
            <span>
              <span className="tst__name">{t.name}</span>
              <span className="tst__meta">{t.meta}</span>
            </span>
          </header>

          <div className="tst__body">
            {t.text.map((p) => <p key={p}>{p}</p>)}
          </div>

          {t.tags?.length ? (
            <div className="tst__tags">
              {t.tags.map((tag) => (
                <span key={tag} className="tst__tag">{tag}</span>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );

  // Дублюємо список у кожному ряду, щоб стрічка замикалася без порожнечі
  // наприкінці циклу анімації.
  const half = Math.ceil(ITEMS.length / 2);
  const a = ITEMS.slice(0, half);
  const b = ITEMS.slice(half);

  return (
    <div className="tst-rows">
      {row([...a, ...a], "a")}
      {row([...b, ...b], "b")}
    </div>
  );
}
