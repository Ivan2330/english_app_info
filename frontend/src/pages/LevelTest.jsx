import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PageHero from "../components/PageHero.jsx";
import { createLead } from "../api/leads.js";
import { useReveal } from "../lib/motion.js";
import {
  TRACKS,
  STARTER_QUESTIONS,
  CONFIDENT_QUESTIONS,
  QUESTIONS_PER_RUN,
  SHOW_RESULT,
  estimateBand,
} from "../lib/leveltest.js";

/**
 * ПОВНИЙ ТЕСТ РІВНЯ
 *
 * Три екрани: розвилка → питання → контакт.
 *
 * ЧОМУ РОЗВИЛКА ОКРЕМИМ ЕКРАНОМ
 * =============================
 * Вибір набору — не «перше питання тесту», а рішення про те, скільки часу
 * людина витратить. Змішати його з питаннями означало б поставити людину
 * перед вибором до того, як вона зрозуміла, у що втягується.
 *
 * ЧОМУ МОЖНА ПОВЕРНУТИСЬ НАЗАД
 * ============================
 * Короткий тест на головній без «назад» обходиться: три питання, помилився —
 * пройшов ще раз. На 25 питаннях випадковий промах по сусідній кнопці
 * коштує всього проходження, і людина просто закриє вкладку.
 * Відповіді зберігаються в масиві за індексом, а не додаються в кінець.
 *
 * ЧОМУ ПРОГРЕС ПОКАЗАНИЙ ЧИСЛОМ, А НЕ ЛИШЕ СМУЖКОЮ
 * ================================================
 * «12 з 25» дає оцінку часу, що лишився. Смужка сама по собі на довгому
 * тесті читається як «ще довго» й підвищує відсоток тих, хто кидає.
 */

const BANKS = {
  starter: STARTER_QUESTIONS,
  confident: CONFIDENT_QUESTIONS,
};

export default function LevelTest() {
  const [track, setTrack] = useState(null);      // null | "starter" | "confident"
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState([]);    // індекс питання → індекс відповіді
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  /* Питання йдуть у порядку зростання складності, без перемішування:
     легкий початок утримує початківця, а різкий стрибок на другому
     питанні — найдешевший спосіб його втратити. */
  const questions = useMemo(
    () => (track ? BANKS[track].slice(0, QUESTIONS_PER_RUN) : []),
    [track]
  );

  const total = questions.length;
  const isForm = track && step >= total;
  const current = questions[step];

  /* Обовʼязково з залежностями. `[data-reveal]` у global.css має
     `opacity: 0` доти, доки хук не повісить `.is-in`; кожен екран тесту
     монтує новий вузол, тож без переходу по `track`/`step` наступний
     екран лишився б прозорим — сторінка виглядала б порожньою. */
  useReveal([track, step, isForm, done]);

  const correctCount = answers.reduce(
    (n, a, i) => (a === questions[i]?.correct ? n + 1 : n),
    0
  );

  function start(id) {
    setTrack(id);
    setStep(0);
    setAnswers([]);
    setDone(false);
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function pick(optionIndex) {
    setAnswers((prev) => {
      const next = [...prev];
      next[step] = optionIndex;
      return next;
    });
    setStep((s) => s + 1);
  }

  function back() {
    setStep((s) => Math.max(0, s - 1));
  }

  function restart() {
    setTrack(null);
    setStep(0);
    setAnswers([]);
    setName("");
    setPhone("");
    setDone(false);
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function submit(e) {
    e.preventDefault();
    if (!phone.trim()) {
      setError("Вкажіть номер телефону або Telegram");
      return;
    }
    setSending(true);
    setError("");

    try {
      /* Викладачу потрібні не бали, а конкретні промахи: видно, що саме
         людина плутає — часи, прийменники чи порядок слів. Тому в заявку
         їде розбивка по кожному питанню з позначкою правильності. */
      const summary = questions
        .map((q, i) => {
          const given = answers[i];
          const ok = given === q.correct;
          const mark = ok ? "+" : "−";
          const chosen = given == null ? "— пропущено" : q.options[given];
          const right = ok ? "" : `   правильно: ${q.options[q.correct]}\n`;
          return `${mark} ${i + 1}. [${q.level}] ${q.q}\n   відповідь: ${chosen}\n${right}`;
        })
        .join("\n");

      const band = estimateBand(track, correctCount, total);

      await createLead({
        kind: "trial",
        name: name.trim() || "Тест рівня",
        phone: phone.trim(),
        comment:
          `ПОВНИЙ ТЕСТ РІВНЯ · набір «${TRACKS[track].title}»\n` +
          `Правильних: ${correctCount} з ${total}\n` +
          `Орієнтовно: ${band}\n\n${summary}`,
        source: "site/level-test",
      });
      setDone(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Не вдалося надіслати. Спробуйте ще раз.");
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHero
        crumb="Тест рівня"
        title="Перевірити рівень англійської"
        lead="Два набори питань на вибір. Займе 8–12 хвилин, реєстрація не потрібна."
      />

      <section className="sec sec--tight">
        <div className="container lt">
          {/* ================= РОЗВИЛКА ================= */}
          {!track && !done && (
            <div className="lt__pick" data-reveal>
              <p className="lt__pick-lead">
                Оберіть те, що ближче до вашої ситуації. Питання в наборах різні —
                так тест не буде ні надто важким, ні надто нудним.
              </p>

              <div className="lt__tracks">
                {Object.values(TRACKS).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className="lt__track"
                    onClick={() => start(t.id)}
                  >
                    <span className="lt__track-range">{t.range}</span>
                    <span className="lt__track-title">{t.title}</span>
                    <span className="lt__track-hint">{t.hint}</span>
                    <span className="lt__track-meta">
                      {QUESTIONS_PER_RUN} питань · ≈{t.minutes} хв
                    </span>
                  </button>
                ))}
              </div>

              <p className="lt__note">
                Не вгадали з набором — нічого страшного: це видно з відповідей,
                і викладач врахує. Пройти другий можна одразу після першого.
              </p>
            </div>
          )}

          {/* ================= ПИТАННЯ ================= */}
          {track && !isForm && (
            <div className="lt__run" data-reveal>
              <div className="lt__bar" aria-hidden="true">
                <i style={{ width: `${(step / total) * 100}%` }} />
              </div>

              <div className="lt__runhead">
                <p className="lt__counter">
                  Питання <b>{step + 1}</b> з {total}
                </p>
                <span className="lt__level">{current.level}</span>
              </div>

              <div className="lt__q" key={step}>
                <h2 className="lt__qtext">{current.q}</h2>

                <div className="lt__options">
                  {current.options.map((o, i) => (
                    <button
                      key={o}
                      type="button"
                      className={
                        "lt__option" + (answers[step] === i ? " is-picked" : "")
                      }
                      onClick={() => pick(i)}
                    >
                      <b>{String.fromCharCode(65 + i)}</b>
                      <span>{o}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="lt__nav">
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={back}
                  disabled={step === 0}
                >
                  ← Назад
                </button>
                <button type="button" className="lt__quit" onClick={restart}>
                  Почати спочатку
                </button>
              </div>
            </div>
          )}

          {/* ================= КОНТАКТ ================= */}
          {isForm && !done && (
            <div className="lt__final" data-reveal>
              <div className="lt__badge" aria-hidden="true">✓</div>
              <h2 className="lt__ftitle">Відповіді записано</h2>

              {/* Результат за замовчуванням не показуємо — SHOW_RESULT.
                  Рівень називає викладач на пробному, побачивши, ЩО саме
                  людина плутає. Число без розбору однаково нічого не дає. */}
              {SHOW_RESULT ? (
                <p className="lt__score">
                  Правильних: <b>{correctCount}</b> з {total} —{" "}
                  {estimateBand(track, correctCount, total)}
                </p>
              ) : (
                <p className="lt__lead">
                  Бал сам по собі нічого не каже: важливо, <b>де саме</b> ви
                  помилились — у часах, прийменниках чи порядку слів. Викладач
                  розбере ваші відповіді на безкоштовному пробному уроці
                  й назве рівень за CEFR.
                </p>
              )}

              <form className="lt__form" onSubmit={submit} noValidate>
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
                  {sending ? "Надсилаємо…" : "Розібрати відповіді на пробному уроці"}
                </button>

                <p className="lt__fine">
                  Безкоштовно й без картки. Відповіді бачить лише викладач.{" "}
                  <Link to="/privacy">Як ми обробляємо дані</Link>
                </p>
              </form>

              <button type="button" className="lt__quit" onClick={back}>
                ← Повернутись до останнього питання
              </button>
            </div>
          )}

          {/* ================= УСПІХ ================= */}
          {done && (
            <div className="lt__final" data-reveal>
              <div className="lt__badge lt__badge--ok" aria-hidden="true">✓</div>
              <h2 className="lt__ftitle">Готово</h2>
              <p className="lt__lead">
                Заявку прийнято. Координатор звʼяжеться з вами й підбере зручний
                час. Ваші відповіді вже у викладача — пробний урок почнеться
                не з нуля, а з ваших конкретних прогалин.
              </p>
              <div className="lt__after">
                <Link className="btn btn-cta" to="/packages">Подивитись пакети</Link>
                <button type="button" className="btn btn-ghost" onClick={restart}>
                  Пройти другий набір
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
