import { useLocation } from "react-router-dom";
import { useState } from "react";
import { createLead } from "../api/leads.js";

export default function Contacts() {
  const location = useLocation();
  const preselected = location?.state?.selectedPackage || "";

  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    telegram: "",
    audience: "",
    preferred_time: "",
    comment: preselected ? `Цікавить пакет: ${preselected}` : "",
  });
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  function onChange(e) {
    const { name, value } = e.target;
    setForm((s) => ({ ...s, [name]: value }));
  }

  async function onSubmit(e) {
    e.preventDefault();

    if (!form.name.trim()) {
      alert("Вкажіть, будь ласка, ім’я");
      return;
    }
    const hasAnyContact =
      (form.phone && form.phone.trim()) ||
      (form.telegram && form.telegram.trim()) ||
      (form.email && form.email.trim());

    if (!hasAnyContact) {
      alert("Вкажіть хоча б один контакт: телефон, Telegram або email.");
      return;
    }

    setSending(true);
    setResult(null);
    try {
      const payload = {
        kind: "trial",
        name: form.name.trim(),
        phone: form.phone || undefined,
        telegram: form.telegram || undefined,
        email: form.email || undefined,
        audience: form.audience || undefined,
        preferred_time: form.preferred_time || undefined,
        comment: form.comment || undefined,
        source: "site",
      };
      const data = await createLead(payload);
      setResult({ ok: true, id: data?.id });
      setForm({
        name: "",
        phone: "",
        email: "",
        telegram: "",
        audience: "",
        preferred_time: "",
        comment: "",
      });
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
        <header className="contact__head">
          <h1 className="section-title">
            Запишись на БЕЗКОШТОВНИЙ пробний урок англійської 💬
          </h1>
          <p className="section-subtitle">
            Дізнайся свій рівень і отримай персональну програму навчання —
            безкоштовно та без зобов’язань.
          </p>
          <p className="contact__hint">
            Вкажи <strong>хоча б один спосіб зв’язку</strong> (телефон / Telegram / email).
            Інші поля — за бажанням.
          </p>
        </header>

        <div className="contact__grid">
          {/* FORM */}
          <form className="form card" onSubmit={onSubmit} noValidate>
            <div className="form__row">
              <label className="field">
                <span className="field__label">Ім’я *</span>
                <input
                  className="field__input"
                  name="name"
                  value={form.name}
                  onChange={onChange}
                  placeholder="Ваше ім’я"
                  required
                  autoComplete="name"
                />
              </label>

              <label className="field">
                <span className="field__label">Телефон</span>
                <input
                  className="field__input"
                  name="phone"
                  value={form.phone}
                  onChange={onChange}
                  placeholder="+380..."
                  autoComplete="tel"
                  inputMode="tel"
                />
              </label>
            </div>

            <div className="form__row">
              <label className="field">
                <span className="field__label">Email</span>
                <input
                  className="field__input"
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={onChange}
                  placeholder="name@example.com"
                  autoComplete="email"
                />
              </label>

              <label className="field">
                <span className="field__label">Telegram</span>
                <input
                  className="field__input"
                  name="telegram"
                  value={form.telegram}
                  onChange={onChange}
                  placeholder="@username"
                />
              </label>
            </div>

            <div className="form__row">
              <label className="field">
                <span className="field__label">Аудиторія</span>
                <select
                  className="field__input field__select"
                  name="audience"
                  value={form.audience}
                  onChange={onChange}
                >
                  <option value="">Обрати...</option>
                  <option value="kids">Діти</option>
                  <option value="adults">Дорослі</option>
                </select>
              </label>

              <label className="field">
                <span className="field__label">Зручний час</span>
                <input
                  className="field__input"
                  name="preferred_time"
                  value={form.preferred_time}
                  onChange={onChange}
                  placeholder="Будні 18:00–20:00"
                />
              </label>
            </div>

            <label className="field">
              <span className="field__label">Коментар</span>
              <textarea
                className="field__textarea"
                name="comment"
                value={form.comment}
                onChange={onChange}
                rows={4}
                placeholder="Побажання щодо графіку, цілей або викладача"
              />
            </label>

            <div className="form__footer">
              <div className="form__note">
                Натискаючи «Записатись», ви погоджуєтесь із умовами обробки даних.
              </div>
              <button className="btn btn-cta" type="submit" disabled={sending}>
                {sending ? "Надсилаємо..." : "📅 Записатись на пробний урок"}
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
                ? `Помилка: ${result.error}`
                : ""}
            </p>
          </form>

          {/* ASIDE */}
          <aside className="contact__aside">
            <div className="contact__card card">
              <h3>Контакти</h3>
              <ul className="contact__list">
                <li><a href="tel:+380991797047">+38 (099) 179-70-47</a></li>
                <li>
                  <a href="https://t.me/IvanKozhevnyk" target="_blank" rel="noreferrer">
                    Telegram
                  </a>
                </li>
              </ul>
              <button
                className="btn btn-ghost"
                onClick={() => window.tidioChatApi?.open?.()}
                type="button"
              >
                Написати у чат
              </button>
            </div>

            <div className="contact__card card">
              <h3>Як проходить пробний урок</h3>
              <ol className="contact__steps">
                <li>Короткий дзвінок з координатором (цілі та графік).</li>
                <li>Діагностика рівня і персональний план навчання.</li>
                <li>Пробний урок 30–60 хв + рекомендації.</li>
              </ol>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
