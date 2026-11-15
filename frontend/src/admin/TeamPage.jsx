import { useCallback, useEffect, useState } from "react";
import { createMember, getAudit, getTeam, resetMemberPassword, updateMember } from "../api/workspace.js";
import { errorText } from "../api/apiClientAuth.js";
import { ErrorBox, Field, fmtDate, fmtSize, Hint, Modal } from "./ws/ui.jsx";

const ACTIONS = {
  login: "увійшов", "password.change": "змінив свій пароль",
  "team.create": "створив акаунт", "team.update": "змінив акаунт", "team.reset_password": "скинув пароль",
  "task.create": "створив завдання", "task.update": "змінив завдання", "task.delete": "видалив завдання",
  "report.create": "додав звіт", "report.update": "змінив звіт", "report.delete": "видалив звіт",
  "comment.add": "написав коментар", "comment.delete": "видалив коментар",
  "review.save": "оцінив", "file.upload": "завантажив файл", "file.delete": "видалив файл",
};
const ENTITY = { task: "завдання", report: "звіт", admin_user: "акаунт" };

/** «Команда»: лише для власника. Акаунти, доступ до розділів, журнал дій, місце на диску. */
export default function TeamPage() {
  const [team, setTeam] = useState(null);
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [secret, setSecret] = useState(null);          // {name, email, password} — показуємо один раз
  const [auditShown, setAuditShown] = useState(15);

  const load = useCallback(async () => {
    try {
      setTeam(await getTeam());
      setAudit(await getAudit({ limit: 60 }));
    } catch (e) { setError(errorText(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function patch(m, data) {
    setError("");
    try { await updateMember(m.id, data); load(); } catch (e) { setError(errorText(e)); }
  }

  async function reset(m) {
    if (!window.confirm(`Скинути пароль для ${m.name}? Старий перестане працювати, людину розлогінить.`)) return;
    try {
      const r = await resetMemberPassword(m.id);
      setSecret({ name: m.name, email: m.email, password: r.temporary_password });
      load();
    } catch (e) { setError(errorText(e)); }
  }

  function toggleSection(m, key) {
    const has = m.sections.includes(key);
    patch(m, { sections: has ? m.sections.filter((s) => s !== key) : [...m.sections, key] });
  }

  if (!team) return error ? <ErrorBox text={error} /> : <p className="ws-muted">Завантажуємо…</p>;
  const d = team.disk;
  const usedPct = Math.round((d.used_bytes / d.total_bytes) * 100);

  return (
    <div className="ws-stack ws-gap-l">
      <header className="ws-pagehead ws-pagehead--row">
        <div>
          <h1 className="ws-h1">Команда</h1>
          <p className="ws-muted">Тут ви створюєте акаунти й вирішуєте, хто які розділи бачить. Нотатки відкриті всім завжди.</p>
        </div>
        <button type="button" className="ws-btn ws-btn--primary ws-btn--big" onClick={() => setCreating(true)}>+ Додати людину</button>
      </header>
      <ErrorBox text={error} />

      <div className="ws-members">
        {team.members.map((m) => (
          <section key={m.id} className={`ws-card ws-member${m.is_active ? "" : " is-off"}`}>
            <header>
              <div>
                <b>{m.name}</b> <span className="ws-tag">{m.role === "owner" ? "Власник" : "Адміністратор"}</span>
                {!m.is_active && <span className="ws-tag ws-tag--off">Вимкнено</span>}
                {m.must_change_password && m.is_active && <span className="ws-tag">ще не змінив тимчасовий пароль</span>}
                <p className="ws-muted ws-small">{m.email} · востаннє заходив: {m.last_login_at ? fmtDate(m.last_login_at, true) : "ще ні разу"}</p>
              </div>
              {m.role !== "owner" && (
                <div className="ws-row ws-wrap">
                  <button type="button" className="ws-btn" onClick={() => reset(m)}>Скинути пароль</button>
                  <button type="button" className={`ws-btn${m.is_active ? " ws-btn--danger" : ""}`}
                          onClick={() => (!m.is_active || window.confirm(`Вимкнути акаунт ${m.name}? Людину одразу розлогінить.`))
                            && patch(m, { is_active: !m.is_active })}>
                    {m.is_active ? "Вимкнути акаунт" : "Увімкнути акаунт"}
                  </button>
                </div>
              )}
            </header>
            {m.role === "owner" ? (
              <Hint>Власнику відкриті всі розділи і «Команда».</Hint>
            ) : (
              <div className="ws-switches" role="group" aria-label={`Розділи для ${m.name}`}>
                {team.sections.map((s) => (
                  <label key={s.key} className="ws-switch">
                    <input type="checkbox" checked={m.sections.includes(s.key)} disabled={!m.is_active}
                           onChange={() => toggleSection(m, s.key)} />
                    <span>{s.label}</span>
                  </label>
                ))}
              </div>
            )}
          </section>
        ))}
      </div>

      <section className="ws-card">
        <h2>Місце на диску сервера</h2>
        <div className="ws-meter"><i style={{ width: `${usedPct}%` }} className={usedPct > 85 ? "is-danger" : ""} /></div>
        <p>Вільно <b>{fmtSize(d.free_bytes)}</b> з {fmtSize(d.total_bytes)} · файли кабінету займають {fmtSize(d.files_bytes)}</p>
        <Hint>Одне відео до 300 МБ. Коли вільного місця менше 5 ГБ, варто прибрати старі відео або збільшити диск.</Hint>
      </section>

      <section className="ws-card">
        <h2>Журнал дій</h2>
        <Hint>Хто що робив останнім часом. Паролі й особисті дані сюди не потрапляють.</Hint>
        <ul className="ws-audit">
          {audit.slice(0, auditShown).map((a) => (
            <li key={a.id}>
              <span className="ws-muted ws-small">{fmtDate(a.at, true)}</span>
              <span><b>{a.actor || "система"}</b> {ACTIONS[a.action] || a.action}
                {a.entity_type && a.entity_type !== "admin_user" ? ` (${ENTITY[a.entity_type] || a.entity_type} №${a.entity_id})` : ""}
                {a.summary ? `: ${a.summary}` : ""}</span>
            </li>
          ))}
        </ul>
        {audit.length > auditShown && (
          <button type="button" className="ws-btn" onClick={() => setAuditShown(auditShown + 30)}>Показати ще</button>
        )}
      </section>

      {creating && (
        <NewMember sections={team.sections} onClose={() => setCreating(false)}
                   onCreated={(r) => { setCreating(false); setSecret({ name: r.member.name, email: r.member.email, password: r.temporary_password }); load(); }} />
      )}
      {secret && <Secret {...secret} onClose={() => setSecret(null)} />}
    </div>
  );
}

function NewMember({ sections, onClose, onCreated }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [picked, setPicked] = useState(sections.map((s) => s.key));
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    try { onCreated(await createMember({ name, email, sections: picked })); } catch (err) { setError(errorText(err)); }
  }

  return (
    <Modal title="Новий акаунт" onClose={onClose}>
      <form className="ws-stack" onSubmit={submit}>
        <Field label="Імʼя" hint="Так людину бачитимуть інші в завданнях і коментарях">
          <input className="ws-input" required value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label="Пошта" hint="Це логін для входу">
          <input className="ws-input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <span className="ws-field__label">Які розділи відкрити</span>
        <div className="ws-switches">
          {sections.map((s) => (
            <label key={s.key} className="ws-switch">
              <input type="checkbox" checked={picked.includes(s.key)}
                     onChange={() => setPicked(picked.includes(s.key) ? picked.filter((k) => k !== s.key) : [...picked, s.key])} />
              <span>{s.label}</span>
            </label>
          ))}
        </div>
        <Hint>Пароль створиться автоматично. Ви побачите його один раз — передайте людині особисто.</Hint>
        <ErrorBox text={error} />
        <button type="submit" className="ws-btn ws-btn--primary ws-btn--big">Створити акаунт</button>
      </form>
    </Modal>
  );
}

function Secret({ name, email, password, onClose }) {
  const [copied, setCopied] = useState(false);
  const text = `Вхід у кабінет Prime Academy\nАдреса: ${window.location.origin}/admin\nЛогін: ${email}\nТимчасовий пароль: ${password}`;
  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setCopied(false); }
  }
  return (
    <Modal title={`Тимчасовий пароль для ${name}`} onClose={onClose}>
      <div className="ws-stack">
        <p>Запишіть або скопіюйте зараз — <b>більше цей пароль ніде не покажеться</b>. Після першого входу людина задасть свій.</p>
        <code className="ws-secret">{password}</code>
        <p className="ws-muted ws-small">Логін: {email}</p>
        <button type="button" className="ws-btn ws-btn--primary ws-btn--big" onClick={copy}>
          {copied ? "Скопійовано ✓" : "Скопіювати логін і пароль"}
        </button>
        <Hint>Надсилайте особисто (не в спільний чат).</Hint>
        <button type="button" className="ws-btn" onClick={onClose}>Готово, я зберіг пароль</button>
      </div>
    </Modal>
  );
}
