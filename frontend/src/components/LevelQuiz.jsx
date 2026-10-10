import { useState } from "react";
import { Link } from "react-router-dom";
import { QUIZ } from "../lib/content.js";
import { createLead } from "../api/leads.js";

/**
 * Експрес-тест рівня.
 *
 * ВАЖЛИВО: результат користувачу НЕ показуємо.
 * Відповіді разом із контактом їдуть менеджеру й розбираються на пробному уроці.
 * Так тест перестає бути іграшкою «дізнався бал і пішов» і стає джерелом заявок,
 * а розмова на пробному починається з готовими даними про людину.
 */
export default function LevelQuiz() {
  const [step, setStep] = useState(0);          // 0..QUIZ.length-1, далі форма
  const [answers, setAnswers] = useState([]);
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const total = QUIZ.length;
  const isForm = step >= total;

  const pick = (option) => {
    setAnswers((prev) => [...prev, { q: QUIZ[step].q, a: option.label, score: option.value }]);
    setStep((s) => s + 1);
  };

  const restart = () => {
    setStep(0); setAnswers([]); setPhone(""); setName(""); setDone(false); setError("");
  };

  async function submit(e) {
    e.preventDefault();
    if (!phone.trim()) {
      setError("Вкажіть номер телефону або Telegram");
      return;
    }
    setSending(true);
    setError("");
    try {
      const summary = answers
        .map((a, i) => `${i + 1}. ${a.q}\n   → ${a.a} (${a.score})`)
        .join("\n");
      const score = answers.reduce((s, a) => s + a.score, 0);

      await createLead({
        kind: "trial",
        name: name.trim() || "Тест рівня",
        phone: phone.trim(),
        comment: `ЕКСПРЕС-ТЕСТ РІВНЯ (сума балів ${score} з ${total * 3})\n\n${summary}`,
        source: "site/level-quiz",
      });
      setDone(true);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Не вдалося надіслати. Спробуйте ще раз.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="quiz">
      {!done && (
        <div className="quiz__progress" aria-hidden="true">
          {Array.from({ length: total + 1 }).map((_, i) => (
            <i key={i} className={i <= step ? "is-done" : ""} />
          ))}
        </div>
      )}

      {/* --- питання --- */}
      {!isForm && (
        <div className="quiz__step" key={step}>
          <p className="quiz__counter">
            Питання {step + 1} з {total}
          </p>
          <h3 className="quiz__q">{QUIZ[step].q}</h3>
          <div className="quiz__options">
            {QUIZ[step].options.map((o, i) => (
              <button key={o.label} type="button" className="quiz__option" onClick={() => pick(o)}>
                <b>{String.fromCharCode(65 + i)}</b>
                {o.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* --- контакт --- */}
      {isForm && !done && (
        <div className="quiz__step quiz__final">
          <div className="quiz__badge" aria-hidden="true">✓</div>
          <h3 className="quiz__q">Відповіді записано</h3>
          <p className="quiz__lead">
            Рівень за трьома питаннями точно не визначити — і показувати вам випадкову
            літеру було б нечесно. Тому ми зробимо це нормально: викладач розбере
            ваші відповіді на безкоштовному пробному уроці й назве реальний рівень
            за CEFR.
          </p>

          <form className="quiz__form" onSubmit={submit} noValidate>
            <label className="field">
              <span className="field__label">Як до вас звертатись</span>
              <span className="input-wrap">
                <input
                  className="field__input field__input--plain"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ім'я"
                  autoComplete="name"
                />
              </span>
            </label>

            <label className="field">
              <span className="field__label">Телефон або Telegram *</span>
              <span className="input-wrap">
                <input
                  className="field__input field__input--plain"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+380 __ ___ __ __"
                  autoComplete="tel"
                  inputMode="tel"
                  required
                />
              </span>
            </label>

            {error ? <p className="form__error">{error}</p> : null}

            <button type="submit" className="btn btn-cta btn--full" disabled={sending}>
              {sending ? "Надсилаємо…" : "Дізнатись рівень на пробному уроці"}
            </button>
            <p className="quiz__fine">
              Безкоштовно й без картки. Ваші відповіді побачить лише викладач.
            </p>
          </form>

          {/* Вихід на повний тест саме тут: людина вже відповіла на три
              питання, тобто зацікавлена, але ще не готова лишати контакт.

              Починалося це речення з «Не готові лишати контакт?» — і саме
              цим псувало форму над собою: підказувало заперечення, якого
              в людини могло й не бути. Пропонуємо точність, а не привід
              не заповнювати форму. */}
          <p className="quiz__more">
            Хочете точніше? <Link to="/level-test">Пройдіть повний тест</Link>{" "}
            — 25 питань, два набори складності на вибір.
          </p>
        </div>
      )}

      {/* --- успіх --- */}
      {done && (
        <div className="quiz__step quiz__final">
          <div className="quiz__badge quiz__badge--ok" aria-hidden="true">✓</div>
          <h3 className="quiz__q">Готово!</h3>
          <p className="quiz__lead">
            Заявку прийнято. Координатор звʼяжеться з вами й підбере зручний час
            для пробного уроку. Ваші відповіді вже в роботі у викладача.
          </p>
          <button type="button" className="btn btn-ghost" onClick={restart}>
            Пройти ще раз
          </button>
        </div>
      )}
    </div>
  );
}
