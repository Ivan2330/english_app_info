import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageHero from "../components/PageHero.jsx";
import { verifyCertificate } from "../api/certificates.js";
import { useReveal } from "../lib/motion.js";
import { API_URL } from "../config.js";

/**
 * Перевірка сертифіката.
 *
 * Головне рішення сторінки: **автоперевірка з параметра `?code=`**.
 * У QR-коді на сертифікаті зашите саме таке посилання, тож людина
 * наводить камеру й одразу бачить результат. Переписувати номер із PDF
 * руками не хоче ніхто — без цього більшість просто не перевірить документ.
 *
 * Друге: результат показаний не таблицею «ключ — значення», а карткою,
 * схожою на сам сертифікат. Той, хто перевіряє, тримає документ перед очима
 * і звіряє його з екраном; схожа розкладка робить звірку миттєвою.
 */

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

const KIND_LABEL = {
  level: "Підвищення рівня",
  course: "Завершення курсу",
  club: "Speaking Club",
  corporate: "Корпоративна програма",
  intensive: "Інтенсив",
};

/** Абсолютна адреса файлу.
 *
 *  Бекенд віддає відносний шлях «/static/certificates/…». На проді сайт
 *  і API на одному домені, а в розробці — ні: без цієї склейки посилання
 *  вело б на порт фронта, де файлу немає. Плюс атрибут `download`
 *  працює лише в межах одного походження. */
function pdfHref(url) {
  if (!url) return url;
  return url.startsWith("http") ? url : `${API_URL}${url}`;
}

function fmtDate(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("uk-UA", {
    day: "numeric", month: "long", year: "numeric",
  });
}

export default function VerifyCertificate() {
  const [params, setParams] = useSearchParams();
  const [code, setCode] = useState(params.get("code") || "");
  const [state, setState] = useState({ loading: false, data: null, error: null });

  useReveal([state.data]);

  const check = useCallback(async (raw) => {
    const value = (raw ?? "").trim();
    if (!value) return;

    setState({ loading: true, data: null, error: null });
    try {
      const res = await verifyCertificate(value);
      setState({ loading: false, data: res, error: null });
    } catch (err) {
      console.error(err);
      setState({
        loading: false, data: null,
        error: "Не вдалося звʼязатися з сервером. Спробуйте ще раз за хвилину.",
      });
    }
  }, []);

  // Автоперевірка при переході за QR-кодом
  useEffect(() => {
    const fromUrl = params.get("code");
    if (fromUrl) check(fromUrl);
    // навмисно один раз: далі перевірку запускає користувач
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onSubmit(e) {
    e.preventDefault();
    const value = code.trim();
    if (!value) return;
    // Номер в адресі — щоб посиланням на результат можна було поділитися
    setParams(value ? { code: value } : {}, { replace: true });
    check(value);
  }

  const d = state.data;

  return (
    <>
      <PageHero
        crumb="Сертифікат"
        title="Перевірка сертифіката"
        lead="Введіть номер із документа або наведіть камеру на QR-код у ньому. Перевірка відкрита для всіх — роботодавець чи університет можуть зробити це самостійно."
      />

      <section className="sec sec--tight">
        <div className="container">
          <form className="cv-form" onSubmit={onSubmit} data-reveal>
            <label className="cv-form__label" htmlFor="cert-code">
              Номер сертифіката
            </label>
            <div className="cv-form__row">
              <input
                id="cert-code"
                className="cv-form__input"
                placeholder="PA-2026-7K3F9X"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                autoComplete="off"
                spellCheck="false"
              />
              <button type="submit" className="btn btn-cta" disabled={state.loading}>
                {state.loading ? "Перевіряємо…" : "Перевірити"}
              </button>
            </div>
            <p className="cv-form__hint">
              Регістр і дефіси не мають значення — можна вводити як зручно.
            </p>
          </form>

          {state.error && (
            <div className="cv-msg cv-msg--error" role="alert" data-reveal>
              {state.error}
            </div>
          )}

          {/* --- не знайдено --- */}
          {d?.status === "invalid" && (
            <div className="cv-msg cv-msg--invalid" role="status" data-reveal>
              <h3>Сертифіката з таким номером немає</h3>
              {d.looks_valid ? (
                <p>
                  Номер записаний правильно, але в нашій базі його немає.
                  Якщо документ видавали ми — напишіть нам, перевіримо вручну.
                </p>
              ) : (
                /* Контрольний символ не зійшовся — майже напевно одруківка,
                   а не підробка. Кажемо це прямо, щоб людина передивилась
                   номер, а не робила висновок про фальшивий документ. */
                <p>
                  Схоже на помилку в номері: перевірте, чи всі символи переписані
                  правильно. Літери <b>O</b>, <b>I</b> та <b>L</b> у наших номерах
                  не використовуються — там, де вони здаються, зазвичай цифри.
                </p>
              )}
            </div>
          )}

          {/* --- анульований --- */}
          {d?.status === "revoked" && (
            <div className="cv-msg cv-msg--revoked" role="status" data-reveal>
              <h3>Сертифікат анульовано</h3>
              <p>
                Номер <b>{d.serial_number}</b> існує, але документ втратив чинність
                {d.revoked_at ? ` ${fmtDate(d.revoked_at)}` : ""}. Якщо ви вважаєте
                це помилкою — звʼяжіться з нами.
              </p>
            </div>
          )}

          {/* --- дійсний --- */}
          {d?.status === "valid" && (
            <article className="cert" role="status" aria-live="polite" data-reveal>
              <header className="cert__top">
                <div>
                  <p className="cert__kind">{KIND_LABEL[d.kind] || "Сертифікат"}</p>
                  <h2 className="cert__name">{d.student_full_name}</h2>
                  {d.organization && <p className="cert__org">{d.organization}</p>}
                </div>
                <span className="cert__badge">Дійсний</span>
              </header>

              <p className="cert__course">{d.course_title}</p>

              {/* Прогрес рівнів — головне, що підтверджує мовна школа.
                  Шкала показує не лише результат, а й шлях. */}
              {(d.level_from || d.level_to) && (
                <div className="cert__levels">
                  {LEVELS.map((lv) => {
                    const from = LEVELS.indexOf(d.level_from);
                    const to = LEVELS.indexOf(d.level_to);
                    const i = LEVELS.indexOf(lv);
                    const inRange = from >= 0 && to >= 0 && i >= from && i <= to;
                    return (
                      <span
                        key={lv}
                        className={
                          "cert__lv" +
                          (inRange ? " is-on" : "") +
                          (lv === d.level_to ? " is-target" : "")
                        }
                      >
                        {lv}
                      </span>
                    );
                  })}
                </div>
              )}

              <dl className="cert__facts">
                <div><dt>Номер</dt><dd>{d.serial_number}</dd></div>
                {d.lessons_count ? <div><dt>Занять</dt><dd>{d.lessons_count}</dd></div> : null}
                {d.hours ? <div><dt>Годин</dt><dd>{d.hours}</dd></div> : null}
                {d.teacher_name ? <div><dt>Викладач</dt><dd>{d.teacher_name}</dd></div> : null}
                {d.started_at && d.finished_at ? (
                  <div>
                    <dt>Період</dt>
                    <dd>{fmtDate(d.started_at)} — {fmtDate(d.finished_at)}</dd>
                  </div>
                ) : null}
                {d.issued_at ? <div><dt>Видано</dt><dd>{fmtDate(d.issued_at)}</dd></div> : null}
                {d.valid_until ? <div><dt>Дійсний до</dt><dd>{fmtDate(d.valid_until)}</dd></div> : null}
              </dl>

              <footer className="cert__foot">
                <span>{d.issued_by || "Prime Academy"}</span>

                {/* Завантаження з'являється лише після того, як людина побачила
                    картку й звірила дані. Кнопка яскрава: у більшості випадків
                    саме по неї й приходять — переслати роботодавцю чи вкласти
                    у портфоліо. */}
                {d.pdf_url && (
                  <a
                    className="btn btn-cta"
                    href={pdfHref(d.pdf_url)}
                    download={`Prime Academy · ${d.serial_number}.pdf`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    ↓ Завантажити сертифікат
                  </a>
                )}
              </footer>
            </article>
          )}
        </div>
      </section>
    </>
  );
}
