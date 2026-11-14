import { useState } from "react";
import { Link } from "react-router-dom";
import { createQuoteRequest } from "../api/quotes.js";

/**
 * Форма «порахуйте мені» для дитячих і корпоративних програм.
 *
 * Ціни тут НЕ показуються — свідомо: Іван рахує сам і відписує особисто.
 * Користувач бачить лише «Ми розрахуємо і напишемо вам».
 *
 * kind = "kids"      → вік, формат, кількість уроків
 * kind = "corporate" → кількість людей, ціль, формат, термін, компанія
 */
const KIDS_LESSONS = [
  { value: 8, label: "8 — місяць" },
  { value: 16, label: "16 — 2 місяці" },
  { value: 32, label: "32 — семестр" },
  { value: 64, label: "64 — навчальний рік" },
  { value: 96, label: "96 — рік інтенсивно" },
];

const KIDS_FORMATS = [
  { value: "individual", label: "Індивідуально" },
  { value: "pair", label: "У парі (брат/сестра чи друг)" },
  { value: "group", label: "У міні-групі" },
];

const CORP_FORMATS = [
  { value: "group", label: "Групи" },
  { value: "individual", label: "Індивідуально для співробітників" },
];

const CORP_MONTHS = [
  { value: 3, label: "3 місяці (мінімум)" },
  { value: 6, label: "6 місяців" },
  { value: 12, label: "12 місяців" },
];

export default function QuoteForm({ kind, source }) {
  const isKids = kind === "kids";

  const [form, setForm] = useState({
    name: "", phone: "", company: "",
    age: "", format: isKids ? "individual" : "group", lessons: 16,
    people: "", goal: "", months: 3, comment: "",
  });
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const onChange = (e) => setForm((s) => ({ ...s, [e.target.name]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.phone.trim()) {
      setError("Заповніть ім'я та контакт");
      return;
    }
    if (isKids && !form.age) { setError("Вкажіть вік дитини"); return; }
    if (!isKids && (!form.people || !form.goal.trim())) {
      setError("Вкажіть кількість людей і ціль навчання");
      return;
    }

    setSending(true);
    setError("");
    try {
      await createQuoteRequest({
        kind,
        name: form.name.trim(),
        phone: form.phone.trim(),
        company: isKids ? undefined : form.company.trim() || undefined,
        comment: form.comment.trim() || undefined,
        source: source || `site/quote-${kind}`,
        params: isKids
          ? { age: Number(form.age), format: form.format, lessons: Number(form.lessons) }
          : {
              people: Number(form.people), format: form.format,
              months: Number(form.months), goal: form.goal.trim(),
            },
      });
      setDone(true);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Помилка відправки. Спробуйте ще раз.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="book quote">
      <div className="book__content">
        <p className="kicker kicker--lime">{isKids ? "Для дітей 5–12 років" : "Для компаній"}</p>
        <h3 className="book__title">
          {isKids ? "Порахуємо програму для вашої дитини" : "Порахуємо навчання для вашої команди"}
        </h3>
        <p className="book__text">
          {isKids
            ? "Вартість залежить від віку, формату й кількості занять. Вкажіть параметри — ми розрахуємо й напишемо вам."
            : "Умови для компанії рахуємо окремо: кількість груп, графік, тривалість контракту. Вкажіть параметри — ми розрахуємо й напишемо вам."}
        </p>
        <ul className="book__bullets">
          <li>Без оплати й зобов'язань</li>
          <li>Відповідаємо особисто</li>
          {!isKids && <li>Договір, рахунок і закривні документи</li>}
        </ul>
      </div>

      <div className="book__form">
        {done ? (
          <div className="book__ok">
            <span className="book__ok-icon" aria-hidden="true">✓</span>
            <h3>Дякуємо!</h3>
            <p>Ми розрахуємо і напишемо вам.</p>
          </div>
        ) : (
          <form onSubmit={submit} noValidate>
            {isKids ? (
              <div className="quote__row">
                <label className="book__field">
                  <span>Вік дитини</span>
                  <input name="age" type="number" min="3" max="17" inputMode="numeric"
                         value={form.age} onChange={onChange} placeholder="5–12" />
                </label>
                <label className="book__field">
                  <span>Кількість уроків</span>
                  <select name="lessons" value={form.lessons} onChange={onChange}>
                    {KIDS_LESSONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </label>
              </div>
            ) : (
              <>
                <label className="book__field">
                  <span>Компанія</span>
                  <input name="company" value={form.company} onChange={onChange}
                         placeholder="Назва (необов'язково)" autoComplete="organization" />
                </label>
                <div className="quote__row">
                  <label className="book__field">
                    <span>Скільки людей</span>
                    <input name="people" type="number" min="1" inputMode="numeric"
                           value={form.people} onChange={onChange} placeholder="12" />
                  </label>
                  <label className="book__field">
                    <span>Термін</span>
                    <select name="months" value={form.months} onChange={onChange}>
                      {CORP_MONTHS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </label>
                </div>
                <label className="book__field">
                  <span>Ціль</span>
                  <input name="goal" value={form.goal} onChange={onChange}
                         placeholder="Наприклад: розмовна англійська для відділу продажів" />
                </label>
              </>
            )}

            <label className="book__field">
              <span>Формат</span>
              <select name="format" value={form.format} onChange={onChange}>
                {(isKids ? KIDS_FORMATS : CORP_FORMATS).map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>

            <div className="quote__row">
              <label className="book__field">
                <span>Ім'я</span>
                <input name="name" value={form.name} onChange={onChange}
                       placeholder="Як до вас звертатись?" autoComplete="name" />
              </label>
              <label className="book__field">
                <span>Телефон або Telegram</span>
                <input name="phone" value={form.phone} onChange={onChange}
                       placeholder="+380 __ ___ __ __" autoComplete="tel" />
              </label>
            </div>

            {error ? <p className="book__error">{error}</p> : null}

            <button type="submit" className="btn btn-lime btn--full" disabled={sending}>
              {sending ? "Надсилаємо…" : "Отримати розрахунок"}
            </button>
            <p className="book__fine">
              Натискаючи, ви погоджуєтесь із <Link to="/privacy">політикою конфіденційності</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
