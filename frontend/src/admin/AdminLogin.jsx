import { useState } from "react";
import { adminLogin, adminMe } from "../api/admin.js";

export default function AdminLogin({ onSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminLogin(email.trim().toLowerCase(), password);
      onSuccess(await adminMe());
    } catch (err) {
      // Не уточнюємо, що саме не так — пошта чи пароль. Така підказка
      // дозволяє перебором з'ясувати, які адреси існують у системі.
      const status = err?.response?.status;
      setError(
        status === 401 ? "Невірна пошта або пароль"
          : status === 429 ? err.response.data.detail      // «Забагато невдалих спроб…»
          : !err?.response ? "Немає звʼязку із сервером. Перевірте інтернет."
          : "Не вдалося увійти. Спробуйте ще раз."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="adm-login">
      <form className="adm-login__box" onSubmit={submit}>
        <h1>Вхід для персоналу</h1>
        <p className="adm-login__sub">Робочий простір Prime Academy</p>

        <label>
          <span>Електронна пошта</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            required
          />
        </label>

        <label>
          <span>Пароль</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && <p className="adm-login__err" role="alert">{error}</p>}

        <button type="submit" disabled={busy}>
          {busy ? "Входимо…" : "Увійти"}
        </button>
        <p className="adm-login__help">
          Немає акаунта або забули пароль? Попросіть власника школи створити акаунт
          чи скинути пароль у розділі «Команда».
        </p>
      </form>
    </div>
  );
}
