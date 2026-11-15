import { useState } from "react";
import { changePassword } from "../api/workspace.js";
import { errorText } from "../api/apiClientAuth.js";
import { ErrorBox, Field, Hint } from "./ws/ui.jsx";

/**
 * Зміна пароля. `forced` — перший вхід із тимчасовим паролем: поки людина
 * не задасть свій, бекенд віддає 403 на всі розділи, тож іншого екрана тут і немає.
 */
export default function ChangePassword({ admin, forced = false, onDone, onLogout }) {
  const min = admin?.password_min_length || 10;
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const mismatch = repeat && next !== repeat;

  async function submit(e) {
    e.preventDefault();
    if (next !== repeat) return setError("Новий пароль і повтор не збігаються.");
    setBusy(true);
    setError("");
    try {
      const me = await changePassword(current, next);
      setDone(true);
      setCurrent(""); setNext(""); setRepeat("");
      onDone?.(me);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const form = (
    <form className="ws-card ws-stack ws-narrow" onSubmit={submit}>
      <h1 className="ws-h1">{forced ? `Вітаємо, ${admin.name}!` : "Змінити пароль"}</h1>
      {forced && (
        <p>Ви увійшли з тимчасовим паролем. Придумайте свій — після цього відкриються всі розділи.</p>
      )}
      <Field label={forced ? "Тимчасовий пароль" : "Поточний пароль"}>
        <input className="ws-input" type="password" autoComplete="current-password" required
               value={current} onChange={(e) => setCurrent(e.target.value)} />
      </Field>
      <Field label="Новий пароль" hint={`Не коротше ${min} символів. Найпростіше — кілька слів через пробіл.`}>
        <input className="ws-input" type="password" autoComplete="new-password" required minLength={min}
               value={next} onChange={(e) => setNext(e.target.value)} />
      </Field>
      <Field label="Новий пароль ще раз">
        <input className="ws-input" type="password" autoComplete="new-password" required
               value={repeat} onChange={(e) => setRepeat(e.target.value)} />
      </Field>
      {mismatch && <Hint>Паролі поки не збігаються.</Hint>}
      <ErrorBox text={error} />
      {done && !forced && <p className="ws-ok">Пароль змінено. На інших пристроях потрібно буде увійти знову.</p>}
      <button type="submit" className="ws-btn ws-btn--primary ws-btn--big" disabled={busy || next.length < min || mismatch}>
        {busy ? "Зберігаємо…" : "Зберегти новий пароль"}
      </button>
      {forced && <button type="button" className="ws-btn ws-btn--ghost" onClick={onLogout}>Вийти</button>}
    </form>
  );

  return forced ? <div className="adm-login ws">{form}</div> : form;
}
