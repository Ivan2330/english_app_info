import { useState } from "react";
import { Link } from "react-router-dom";
import { createLead } from "../api/leads.js";

/**
 * Блок «Пробний урок» — градієнтна плашка з формою.
 * Використовується на головній, на цінах і на сторінці «Про школу».
 */
export default function BookingForm({
  eyebrow = "Перший крок",
  title = "Пробний урок — безкоштовно і без картки",
  text = "40 хвилин: визначимо рівень, поговоримо англійською, покажемо план і формат. Не сподобається — просто не продовжуєте.",
  bullets = ["Без оплати", "Онлайн, з телефона теж", "Швидка відповідь"],
  source = "site/cta",
}) {
  const [form, setForm] = useState({ name: "", phone: "", goal: "Загальний рівень" });
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const onChange = (e) =>
    setForm((s) => ({ ...s, [e.target.name]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) {
      setError("Заповніть ім'я та контакт");
      return;
    }
    setSending(true);
    setError("");
    try {
      await createLead({
        kind: "trial",
        name: form.name.trim(),
        phone: form.phone.trim(),
        comment: `Ціль: ${form.goal}`,
        source,
      });
      setDone(true);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Помилка відправки");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="book">
      <div className="book__content">
        <p className="kicker kicker--lime">{eyebrow}</p>
        <h2 className="book__title">{title}</h2>
        <p className="book__text">{text}</p>
        <ul className="book__bullets">
          {bullets.map((b) => <li key={b}>{b}</li>)}
        </ul>
      </div>

      <div className="book__form">
        {done ? (
          <div className="book__ok">
            <span className="book__ok-icon" aria-hidden="true">✓</span>
            <h3>Готово!</h3>
            <p>Заявку прийнято. Координатор напише вам і підбере зручний час.</p>
          </div>
        ) : (
          <form onSubmit={submit} noValidate>
            <label className="book__field">
              <span>Ім'я</span>
              <input
                name="name"
                value={form.name}
                onChange={onChange}
                placeholder="Як до вас звертатись?"
                autoComplete="name"
                required
              />
            </label>

            <label className="book__field">
              <span>Телефон або Telegram</span>
              <input
                name="phone"
                value={form.phone}
                onChange={onChange}
                placeholder="+380 __ ___ __ __"
                autoComplete="tel"
                inputMode="tel"
                required
              />
            </label>

            <label className="book__field">
              <span>Ціль навчання</span>
              <select name="goal" value={form.goal} onChange={onChange}>
                <option>Загальний рівень</option>
                <option>Робота та кар'єра</option>
                <option>IELTS / TOEFL</option>
                <option>Тільки розмовна</option>
                <option>Школа / НМТ</option>
                <option>Для компанії</option>
                <option>Ще не визначився</option>
              </select>
            </label>

            {error ? <p className="book__error">{error}</p> : null}

            <button type="submit" className="btn btn-lime btn--full" disabled={sending}>
              {sending ? "Надсилаємо…" : "Записатись на пробний урок"}
            </button>
            <p className="book__fine">
              Натискаючи, ви погоджуєтесь із{" "}
              <Link to="/privacy">політикою конфіденційності</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
