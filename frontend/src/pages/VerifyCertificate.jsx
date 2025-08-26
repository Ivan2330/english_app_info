// src/pages/VerifyCertificate.jsx
import { useState } from "react";
import { verifyCertificate } from "../api/certificates.js";


export default function VerifyCertificate() {
  const [code, setCode] = useState("");
  const [state, setState] = useState({ loading: false, data: null, error: null, touched: false });

  async function onCheck(e) {
    e.preventDefault();
    const trimmed = code.trim();
    setState((s) => ({ ...s, touched: true }));
    if (!trimmed) return;

    setState({ loading: true, data: null, error: null, touched: true });
    try {
      const res = await verifyCertificate(trimmed);
      setState({ loading: false, data: res, error: null, touched: true });
    } catch (err) {
      console.error(err);
      setState({ loading: false, data: null, error: "Помилка перевірки", touched: true });
    }
  }

  const d = state.data;
  const isEmpty = state.touched && !code.trim();

  function StatusBadge({ status }) {
    if (status === "valid") return <span className="vc-badge vc-badge--valid">Дійсний</span>;
    if (status === "revoked") return <span className="vc-badge vc-badge--revoked">Анулований</span>;
    return <span className="vc-badge vc-badge--invalid">Невалідний</span>;
  }

  return (
    <section className="vc">
      <div className="container">
        <header className="vc__header">
          <h1 className="vc__title">Перевірити сертифікат</h1>
          <p className="vc__lead">Введіть публічний код із вашого сертифіката, щоб перевірити його статус.</p>
        </header>

        <form className="vc-form" onSubmit={onCheck} noValidate>
          <div className={`vc-field ${isEmpty ? "vc-field--error" : ""}`}>
            <label htmlFor="cert-code" className="vc-label">Публічний код</label>
            <div className="vc-input-wrap">
              <input
                id="cert-code"
                className="vc-input"
                placeholder="Напр., PA-ENG-2025-ABCD"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                aria-label="Код сертифіката"
                autoComplete="off"
              />
              {code && (
                <button
                  type="button"
                  className="vc-clear"
                  aria-label="Очистити поле"
                  onClick={() => setCode("")}
                >
                  ✕
                </button>
              )}
            </div>
            {isEmpty && <p className="vc-hint vc-hint--error">Введіть код сертифіката</p>}
            {!isEmpty && <p className="vc-hint">Код без пробілів. Регістр не важливий.</p>}
          </div>

          <button type="submit" className="vc-btn" disabled={state.loading}>
            {state.loading ? "Перевіряємо…" : "Перевірити"}
          </button>
        </form>

        {/* повідомлення про помилку мережі/бекенду */}
        {state.error && (
          <div role="alert" className="vc-alert vc-alert--error">
            {state.error}
          </div>
        )}

        {/* результат перевірки */}
        {d && (
          <div className="vc-card" role="status" aria-live="polite">
            <div className="vc-card__head">
              <h2 className="vc-card__title">Статус сертифіката</h2>
              <StatusBadge status={d.status} />
            </div>

            {d.status === "invalid" && (
              <p className="vc-note">Код не знайдено. Перевірте правильність введення.</p>
            )}

            {d.status !== "invalid" && (
              <div className="vc-grid">
                <div className="vc-row">
                  <span className="vc-key">Серійний номер</span>
                  <span className="vc-val">{d.serial_number ?? "—"}</span>
                </div>
                <div className="vc-row">
                  <span className="vc-key">Студент</span>
                  <span className="vc-val">{d.student_full_name ?? "—"}</span>
                </div>
                <div className="vc-row">
                  <span className="vc-key">Курс</span>
                  <span className="vc-val">{d.course_title ?? "—"}</span>
                </div>
                {d.level_cefr && (
                  <div className="vc-row">
                    <span className="vc-key">Рівень</span>
                    <span className="vc-val">{d.level_cefr}</span>
                  </div>
                )}
                {d.issued_at && (
                  <div className="vc-row">
                    <span className="vc-key">Видано</span>
                    <span className="vc-val">
                      {new Date(d.issued_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
                {d.valid_until && (
                  <div className="vc-row">
                    <span className="vc-key">Дійсний до</span>
                    <span className="vc-val">
                      {new Date(d.valid_until).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>
            )}

            {d.pdf_url && d.status === "valid" && (
              <div className="vc-actions">
                <a className="vc-btn vc-btn--ghost" href={d.pdf_url} target="_blank" rel="noreferrer">
                  Відкрити PDF
                </a>
              </div>
            )}

            {d.status === "revoked" && (
              <div className="vc-alert vc-alert--warn">
                Сертифікат анульовано. Якщо ви вважаєте це помилкою — зверніться до адміністраторів.
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
