import { useLocation, Link } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { createLead } from "../api/leads.js";
import { fetchPackageBySlug, fetchPackages } from "../api/packages.js";
import { money, lessonsWord, TRACK, FORMAT, AUDIENCE } from "../lib/labels.js";
import BonusLessons from "../components/BonusLessons.jsx";

// Окрема рекламна пропозиція; базові ціни каталогу не змінюємо.
const TRIAL_PROMO_RATES = { 16: 450, 24: 430, 48: 400, 64: 350 };
const TRIAL_PROMO_END = Date.parse("2026-10-21T00:00:00+03:00");

/* ===== Icons ===== */
function IconUser() {
  return (
    <svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5Zm0 2c-4.418 0-8 2.239-8 5v1h16v-1c0-2.761-3.582-5-8-5Z" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
function IconPhone() {
  return (
    <svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6.6 10.8c1.2 2.4 3.2 4.4 5.6 5.6l1.9-1.9a1 1 0 0 1 1.05-.24c1.15.38 2.39.59 3.65.59a1 1 0 0 1 1 1V19a2 2 0 0 1-2 2C10.28 21 3 13.72 3 4a2 2 0 0 1 2-2h2.15a1 1 0 0 1 1 1c0 1.26.21 2.5.59 3.65a1 1 0 0 1-.24 1.05L6.6 10.8Z" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
function IconAt() {
  return (
    <svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 20a8 8 0 1 1 6.32-3.1M15 13.5a3 3 0 1 1-3-3h.5a2.5 2.5 0 0 1 2.5 2.5v2a1.5 1.5 0 0 0 3 0V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ===== Helpers ===== */
function parseContact(raw) {
  const v = (raw || "").trim();
  if (!v) return { email: undefined, telegram: undefined };
  if (v.includes("@") && v.includes(".")) return { email: v, telegram: undefined };
  if (v.startsWith("@")) return { email: undefined, telegram: v };
  return { email: undefined, telegram: v };
}

export default function Contacts() {
  const location = useLocation();
  const preselectedSlug = location?.state?.selectedPackage || "";
  const formRef = useRef(null);

  const [form, setForm] = useState({ name: "", phone: "", contact: "" });
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  // Обраний на сторінці цін пакет — підвантажуємо, щоб показати людині,
  // на що саме вона записується. Раніше сюди їхав тільки сирий slug у коментар.
  const [pkg, setPkg] = useState(null);
  const [ladder, setLadder] = useState([]);
  const [promoActive, setPromoActive] = useState(() => Date.now() < TRIAL_PROMO_END);

  useEffect(() => {
    if (!promoActive) return;
    const timer = setTimeout(() => setPromoActive(false), Math.min(TRIAL_PROMO_END - Date.now(), 2147483647));
    return () => clearTimeout(timer);
  }, [promoActive]);

  const displayedLadder = ladder.map((p) => {
    if (!promoActive) return p;
    const rate = TRIAL_PROMO_RATES[p.lessons_count];
    return {
      ...p,
      price_per_lesson: rate,
      not_true_price: p.total_price,
      discount_money: p.total_price - rate * p.lessons_count,
    };
  });

  useEffect(() => {
    if (!preselectedSlug) return;
    let cancelled = false;
    fetchPackageBySlug(preselectedSlug)
      .then((data) => !cancelled && setPkg(data))
      .catch(() => !cancelled && setPkg(null));
    return () => { cancelled = true; };
  }, [preselectedSlug]);

  // Приклад знижок беремо з живого каталогу, а не з тексту в коді:
  // інакше при кожній зміні цін цей блок починає брехати.
  useEffect(() => {
    let cancelled = false;
    fetchPackages({
      family: "subscription", audience: "adults", track: "general", format: "individual",
    })
      .then((data) => {
        if (cancelled) return;
        const withDiscount = data
          .filter((p) => Object.hasOwn(TRIAL_PROMO_RATES, p.lessons_count))
          .sort((a, b) => a.lessons_count - b.lessons_count);
        setLadder(withDiscount.slice(0, 4));
      })
      .catch(() => !cancelled && setLadder([]));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => { setResult(null); }, [form.name, form.phone, form.contact]);

  function onChange(e) {
    const { name, value } = e.target;
    setForm((s) => ({ ...s, [name]: value }));
  }

  function scrollToForm(e) {
    e?.preventDefault?.();
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!form.name.trim()) {
      setResult({ ok: false, error: "Вкажіть, будь ласка, ім'я" });
      return;
    }
    if (!(form.phone?.trim() || form.contact?.trim())) {
      setResult({ ok: false, error: "Вкажіть хоча б один контакт: телефон або Telegram/email" });
      return;
    }

    const { email, telegram } = parseContact(form.contact);

    setSending(true);
    setResult(null);
    try {
      const data = await createLead({
        kind: "trial",
        name: form.name.trim(),
        phone: form.phone?.trim() || undefined,
        email,
        telegram,
        // Аудиторію передаємо окремим полем — щоб у адмінці можна було
        // фільтрувати заявки, а не вичитувати їх із тексту коментаря.
        audience: pkg?.audience || undefined,
        comment: pkg
          ? `Обрано: ${pkg.name} — ${pkg.lessons_count} ${lessonsWord(pkg.lessons_count)}, ${money(pkg.total_price, pkg.currency)} (${pkg.slug})`
          : preselectedSlug
          ? `Цікавить пакет: ${preselectedSlug}`
          : undefined,
        source: "site/contacts",
      });
      setResult({ ok: true, id: data?.id });
      setForm({ name: "", phone: "", contact: "" });
    } catch (err) {
      console.error(err);
      setResult({ ok: false, error: err?.response?.data?.detail || "Помилка відправки" });
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="contact">
      <div className="container contact__inner">
        <header className="contact__head contact__head--span">
          <p className="kicker">Prime Academy</p>
          <h1 className="section-title">Запис на безкоштовний пробний урок</h1>
          <p className="section-subtitle">
            40 хвилин із викладачем по відеозв'язку: діагностика рівня та персональний план.
          </p>
          <p className="contact__hint">
            Заповнення займає ~10 секунд. <strong>Потрібно лише ім'я та один контакт.</strong>
          </p>
        </header>

        <div className="combo">
          <aside className="promo card">
            {/* Якщо людина прийшла зі сторінки цін — показуємо, що саме вона обрала */}
            {pkg ? (
              <>
                <div className="promo__head">
                  <span className="badge-deadline">Ваш вибір</span>
                  <h3 className="promo__title">{pkg.name}</h3>
                  <p className="promo__subtitle">
                    {TRACK[pkg.track]?.label}
                    {pkg.format && FORMAT[pkg.format] ? ` · ${FORMAT[pkg.format].label}` : ""}
                    {pkg.audience && AUDIENCE[pkg.audience] ? ` · ${AUDIENCE[pkg.audience].label}` : ""}
                  </p>
                </div>

                <div className="chosen">
                  <div className="chosen__price">{money(pkg.total_price, pkg.currency)}</div>
                  {pkg.discount_percent ? (
                    <div className="chosen__old">
                      <s>{money(pkg.not_true_price, pkg.currency)}</s>
                      <span className="chosen__disc">-{pkg.discount_percent}%</span>
                    </div>
                  ) : null}

                  <ul className="chosen__list">
                    {pkg.lessons_count ? (
                      <li>
                        <strong>{pkg.lessons_count}</strong> {lessonsWord(pkg.lessons_count)} по{" "}
                        {pkg.lesson_duration_min} хв
                      </li>
                    ) : null}
                    {pkg.price_per_lesson ? (
                      <li>
                        {money(pkg.price_per_lesson, pkg.currency)} за урок
                        {pkg.price_per_person ? " з людини" : ""}
                      </li>
                    ) : null}
                    {pkg.duration_hint ? <li>Триває {pkg.duration_hint}</li> : null}
                    {pkg.group_size_max && pkg.format === "group" ? (
                      <li>Група до {pkg.group_size_max} людей</li>
                    ) : null}
                  </ul>

                  {pkg.chast_enabled ? (
                    <p className="chosen__chast">
                      Можна частинами: {money(Math.round(pkg.total_price / pkg.chast_max_parts), pkg.currency)} ×{" "}
                      {pkg.chast_max_parts} без переплати
                    </p>
                  ) : null}
                </div>

                <div className="promo__foot">
                  <div className="promo__note">
                    Нічого платити зараз не треба. Спершу безкоштовний пробний урок —
                    там і підтвердимо, що це справді ваш формат.
                  </div>
                  <a href="#contact-form" className="btn btn-cta promo__cta" onClick={scrollToForm}>
                    Записатись
                  </a>
                </div>
              </>
            ) : (
              <>
                <div className="promo__head">
                  <span className="badge-deadline">{promoActive ? "Для тих, хто прийшов із реклами · до 20 жовтня" : "Як влаштована ціна"}</span>
                  <h3 className="promo__title">Чим більший пакет — тим дешевший урок</h3>
                  <p className="promo__subtitle">
                    {promoActive ? <>
                      Тимчасова додаткова знижка для тих, хто прийшов із реклами
                      та подав заявку на безкоштовний пробний урок до <strong>20 жовтня 2026 року включно</strong>.
                      Ціни тут нижчі, ніж у розділі <Link to="/packages">«Ціни»</Link>, завдяки цій пропозиції.
                    </> : <>
                      Знижка закладена в сам розмір пакета. Ніяких прихованих доплат
                      за матеріали чи «вступний внесок».
                    </>}
                  </p>
                </div>

                <div className="promo__audience">
                  <strong>Для дорослих · індивідуальні заняття</strong>
                  <span>У картках нижче — ціна за один урок у пакеті</span>
                </div>

                {ladder.length > 0 ? (
                  <div className="promo__list">
                    {displayedLadder.map((p) => (
                      <div className="tier" key={p.id}>
                        <div className="tier__name">
                          {p.lessons_count} {lessonsWord(p.lessons_count)}
                        </div>
                        <div className="tier__save">{promoActive ? "Додаткова економія" : "Економія"} {money(p.discount_money, p.currency)}{promoActive ? " на пакеті" : ""}</div>
                        <div className="tier__price">
                          <s>{money(Math.round(p.not_true_price / p.lessons_count), p.currency)}</s>
                          <span>{money(p.price_per_lesson, p.currency)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                <BonusLessons />

                <div className="promo__foot">
                  <div className="promo__note">
                    {promoActive && "Перекреслено звичайну ціну уроку у відповідному пакеті."}
                  </div>
                  <div className="promo__other">
                    <h4>Шукаєте навчання для дитини чи інший формат?</h4>
                    <p>
                      Для дітей і підлітків, занять у парі чи групі є окремі пропозиції.
                      На безкоштовному пробному уроці підберемо навчання під вашу ціль,
                      розрахуємо вартість і розповімо про доступні додаткові знижки.
                    </p>
                  </div>
                  <a href="#contact-form" className="btn btn-cta promo__cta" onClick={scrollToForm}>
                    Записатись на пробний
                  </a>
                </div>
              </>
            )}
          </aside>

          {/* ===== FORM ===== */}
          <form id="contact-form" ref={formRef} className="form card" onSubmit={onSubmit} noValidate>
            <div className="form__row">
              <label className="field">
                <span className="field__label">Ім'я *</span>
                <span className="input-wrap">
                  <IconUser />
                  <input
                    className="field__input"
                    name="name"
                    value={form.name}
                    onChange={onChange}
                    placeholder="Ваше ім'я"
                    autoComplete="name"
                    required
                  />
                </span>
              </label>

              <label className="field">
                <span className="field__label">Телефон</span>
                <span className="input-wrap">
                  <IconPhone />
                  <input
                    className="field__input"
                    name="phone"
                    value={form.phone}
                    onChange={onChange}
                    placeholder="+380 00 000 00 00"
                    autoComplete="tel"
                    inputMode="tel"
                  />
                </span>
              </label>
            </div>

            <label className="field">
              <span className="field__label">Контакт (Telegram або email)</span>
              <span className="input-wrap">
                <IconAt />
                <input
                  className="field__input"
                  name="contact"
                  value={form.contact}
                  onChange={onChange}
                  placeholder="@username або name@example.com"
                  autoComplete="off"
                />
              </span>
            </label>

            {pkg ? (
              <p className="form__chosen">
                До заявки додамо ваш вибір: <strong>{pkg.name}</strong>
              </p>
            ) : null}

            <div className="form__footer">
              <div className="form__note">
                Натискаючи «Записатись», ви погоджуєтесь із{" "}
                <Link to="/privacy">умовами обробки даних</Link>.
              </div>
              <button className="btn btn-cta" type="submit" disabled={sending}>
                {sending ? "Надсилаємо…" : "Записатись на пробний урок"}
              </button>
            </div>

            <p
              className={result?.ok ? "form__success" : result ? "form__error" : "sr-only"}
              role="status"
              aria-live="polite"
            >
              {result?.ok
                ? "Дякуємо! Заявку отримано — ми звʼяжемось найближчим часом."
                : result
                ? result.error
                : ""}
            </p>
          </form>
        </div>

        {/* Прямі контакти. Сторінка називається «Контакти», а самих
            контактів на ній не було — лише форма. Частина людей не хоче
            лишати заявку й чекати: їм треба написати просто зараз.

            Плюс monobank перевіряє наявність контактів на сайті при
            підключенні інтернет-еквайрингу. */}
        {/* Поки з контактів лишаємо тільки Instagram: це єдиний канал,
            де нам справді відповідають швидко. Телефон і пошту повернемо,
            коли зʼявиться координатор на корпоративних заявках — зараз
            вони створювали б очікування, яке нема кому закрити. */}
        <div className="contact__direct contact__head--span">
          <h2>Або напишіть в Instagram</h2>
          <p className="contact__direct-lead">
            Відповідаємо в директ — зазвичай швидше, ніж на заявку.
          </p>
          <a
            className="contact__ig"
            href="https://instagram.com/___prime_academy__"
            target="_blank"
            rel="noreferrer noopener"
          >
            <span className="contact__ig-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none"
                   stroke="currentColor" strokeWidth="1.8"
                   strokeLinecap="round" strokeLinejoin="round">
                <rect x="2.5" y="2.5" width="19" height="19" rx="5.5" />
                <circle cx="12" cy="12" r="4.2" />
                <circle cx="17.6" cy="6.4" r="1.1" fill="currentColor" stroke="none" />
              </svg>
            </span>
            <span className="contact__ig-text">
              <b>@___prime_academy__</b>
              <small>Написати в директ</small>
            </span>
            <span className="contact__ig-arrow" aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </section>
  );
}
