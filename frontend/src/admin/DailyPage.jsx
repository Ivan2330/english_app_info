import { useCallback, useContext, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  createDailyReport, getDailyMine, getDailyReport, getDailyReports, getDailySettings, getDailyWeek,
  getPeople, setDailyVisibility, updateDailyReport,
} from "../api/workspace.js";
import { errorText } from "../api/apiClientAuth.js";
import Markdown from "./ws/Markdown.jsx";
import { Comments } from "./ws/Discussion.jsx";
import { AdminContext, Empty, ErrorBox, Field, fmtDate, Hint, Modal } from "./ws/ui.jsx";

const MOODS = [
  { v: 1, label: "Дуже важко" }, { v: 2, label: "Важко" }, { v: 3, label: "Нормально" },
  { v: 4, label: "Добре" }, { v: 5, label: "Легко" },
];
const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];

function shortDate(iso) {
  const [, m, d] = iso.split("-");
  return `${d}.${m}`;
}

/**
 * «Звіт дня». Один звіт на людину на день; правити можна до кінця наступного дня.
 * Хто чиї звіти бачить, вирішує власник (перемикач угорі). Перевіряє це бекенд,
 * сторінка лише показує те, що їй віддали.
 */
export default function DailyPage() {
  const me = useContext(AdminContext);
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "mine";
  const [settings, setSettings] = useState(null);
  const [openId, setOpenId] = useState(null);

  useEffect(() => { getDailySettings().then(setSettings).catch(() => {}); }, []);
  const isOwner = me?.role === "owner";
  const tabs = [
    { v: "mine", label: "Мій звіт" },
    { v: "feed", label: "Стрічка" },
    ...(isOwner ? [{ v: "week", label: "Тиждень" }] : []),
  ];

  return (
    <div className="ws-stack ws-gap-l">
      <header className="ws-pagehead ws-pagehead--row">
        <div>
          <h1 className="ws-h1">Звіт дня</h1>
          <p className="ws-muted">
            Що зроблено, скільки годин, що заважало і план на завтра. Один звіт на день,
            виправити можна до кінця наступного дня.
          </p>
        </div>
      </header>

      {settings && <VisibilityBar settings={settings} onChange={setSettings} />}

      <div className="ws-seg" role="tablist">
        {tabs.map((t) => (
          <button key={t.v} type="button" role="tab" aria-selected={tab === t.v} className={tab === t.v ? "is-on" : ""}
                  onClick={() => setParams({ tab: t.v }, { replace: true })}>{t.label}</button>
        ))}
      </div>

      {tab === "mine" && <MyReport onSaved={() => me.refreshCounters?.()} />}
      {tab === "feed" && <Feed onOpen={setOpenId} showAuthorFilter={isOwner || settings?.visibility === "all"} />}
      {tab === "week" && isOwner && <Week onOpen={setOpenId} />}

      {openId && <ReportModal id={openId} onClose={() => { setOpenId(null); me.refreshCounters?.(); }} />}
    </div>
  );
}

/* ================================================================ видимість */

function VisibilityBar({ settings, onChange }) {
  const [error, setError] = useState("");
  async function choose(v) {
    setError("");
    try { onChange(await setDailyVisibility(v)); } catch (e) { setError(errorText(e)); }
  }
  if (!settings.can_change) {
    return <p className="ws-muted">Хто бачить звіти: <b>{settings.label}</b>.</p>;
  }
  return (
    <div className="ws-card ws-daily-vis">
      <span className="ws-field__label">Хто бачить звіти</span>
      <div className="ws-seg">
        {Object.entries(settings.options).map(([v, label]) => (
          <button key={v} type="button" className={settings.visibility === v ? "is-on" : ""} onClick={() => choose(v)}>
            {label}
          </button>
        ))}
      </div>
      <Hint>Перемикання не змінює самі звіти, лише хто може їх читати. Змінити може тільки власник.</Hint>
      <ErrorBox text={error} />
    </div>
  );
}

/* ================================================================ мій звіт */

function emptyForm(report) {
  return {
    done: report?.done || "", hours: report?.hours ?? "", links: (report?.links || []).join("\n"),
    blockers: report?.blockers || "", plan: report?.plan || "", mood: report?.mood ?? null,
  };
}

function MyReport({ onSaved }) {
  const [mine, setMine] = useState(null);
  const [day, setDay] = useState("today");
  const [f, setF] = useState(emptyForm());
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setMine(await getDailyMine()); } catch (e) { setError(errorText(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const slot = mine?.[day];
  const report = slot?.report;
  // Після збереження форма показує збережене; «Збережено ✓» скидається лише при зміні дня
  useEffect(() => { setF(emptyForm(report)); }, [report]);
  useEffect(() => { setSaved(false); setError(""); }, [day]);

  if (!mine) return error ? <ErrorBox text={error} /> : <p className="ws-muted">Завантажуємо…</p>;

  const readOnly = report && !report.editable;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = {
      done: f.done, hours: Number(f.hours || 0), blockers: f.blockers, plan: f.plan,
      links: f.links.split("\n").map((l) => l.trim()).filter(Boolean),
    };
    try {
      if (report) {
        await updateDailyReport(report.id, { ...data, ...(f.mood ? { mood: f.mood } : { clear_mood: true }) });
      } else {
        await createDailyReport({ ...data, date: slot.date, ...(f.mood ? { mood: f.mood } : {}) });
      }
      setSaved(true);
      await load();
      onSaved?.();
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }

  return (
    <div className="ws-stack">
      <div className="ws-seg ws-seg--small" role="group" aria-label="За який день">
        <button type="button" className={day === "today" ? "is-on" : ""} onClick={() => setDay("today")}>
          Сьогодні, {shortDate(mine.today.date)} {mine.today.report ? "✓" : ""}
        </button>
        <button type="button" className={day === "yesterday" ? "is-on" : ""} onClick={() => setDay("yesterday")}>
          Вчора, {shortDate(mine.yesterday.date)} {mine.yesterday.report ? "✓" : ""}
        </button>
      </div>

      <form className="ws-card ws-stack" onSubmit={submit}>
        <h2>{report ? (readOnly ? "Звіт подано" : "Ваш звіт (можна виправити)") : "Новий звіт"} за {shortDate(slot.date)}</h2>
        {report && !readOnly && <Hint>Виправити можна до кінця {shortDate(report.editable_until)}.</Hint>}
        {readOnly && <Hint>Термін редагування цього звіту минув.</Hint>}
        <Field label="Що зроблено" hint="Коротко по пунктах. Можна markdown: - список, **жирний**">
          <textarea className="ws-input" rows={5} required value={f.done} onChange={set("done")} disabled={readOnly}
                    placeholder={"- зняла 2 Reels\n- відповіла на 14 заявок"} />
        </Field>
        <div className="ws-form2">
          <Field label="Скільки годин">
            <input className="ws-input" type="number" min="0" max="24" step="0.5" inputMode="decimal" required
                   value={f.hours} onChange={set("hours")} disabled={readOnly} />
          </Field>
          <Field label="Настрій / навантаження" hint="Необовʼязково. Натисніть ще раз, щоб прибрати">
            <div className="ws-scale ws-scale--5" role="radiogroup" aria-label="Настрій від 1 до 5">
              {MOODS.map((m) => (
                <button key={m.v} type="button" role="radio" aria-checked={f.mood === m.v} title={m.label}
                        className={f.mood === m.v ? "is-on" : ""} disabled={readOnly}
                        onClick={() => setF({ ...f, mood: f.mood === m.v ? null : m.v })}>{m.v}</button>
              ))}
            </div>
          </Field>
        </div>
        <Field label="Посилання" hint="По одному в рядку: пости, документи, таблиці">
          <textarea className="ws-input ws-input--mono" rows={3} value={f.links} onChange={set("links")} disabled={readOnly}
                    placeholder="https://…" />
        </Field>
        <Field label="Що заважало">
          <textarea className="ws-input" rows={2} value={f.blockers} onChange={set("blockers")} disabled={readOnly}
                    placeholder="Якщо нічого, залиште порожнім" />
        </Field>
        <Field label="План на завтра">
          <textarea className="ws-input" rows={3} value={f.plan} onChange={set("plan")} disabled={readOnly} />
        </Field>
        <ErrorBox text={error} />
        {saved && <p className="ws-ok">Збережено ✓</p>}
        {!readOnly && (
          <button type="submit" className="ws-btn ws-btn--primary ws-btn--big" disabled={busy || !f.done.trim()}>
            {busy ? "Зберігаємо…" : report ? "Зберегти зміни" : "Здати звіт"}
          </button>
        )}
      </form>
    </div>
  );
}

/* ================================================================ стрічка */

function Feed({ onOpen, showAuthorFilter }) {
  const [items, setItems] = useState(null);
  const [people, setPeople] = useState([]);
  const [author, setAuthor] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { getPeople().then(setPeople).catch(() => {}); }, []);
  useEffect(() => {
    getDailyReports(author ? { author_id: author } : {}).then((d) => setItems(d.items)).catch((e) => setError(errorText(e)));
  }, [author]);

  if (error) return <ErrorBox text={error} />;
  if (!items) return <p className="ws-muted">Завантажуємо…</p>;

  return (
    <div className="ws-stack">
      {showAuthorFilter && (
        <select className="ws-input ws-input--auto" value={author} onChange={(e) => setAuthor(e.target.value)} aria-label="Чиї звіти">
          <option value="">Усі люди</option>
          {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      )}
      {!items.length ? <Empty title="Звітів поки немає">Перший звіт можна здати на вкладці «Мій звіт».</Empty> : (
        <div className="ws-list">
          {items.map((r) => (
            <button key={r.id} type="button" className="ws-card ws-daily-card" onClick={() => onOpen(r.id)}>
              <span className="ws-task__top">
                <b>{r.author}</b>
                <span className="ws-tag">{fmtDate(r.date)}</span>
                <span className="ws-tag">{r.hours} год</span>
                {r.mood && <span className="ws-tag">настрій {r.mood}/5</span>}
                {r.unread && <span className="ws-new">нове</span>}
                {r.comments_count > 0 && <span className="ws-muted ws-small">коментарів: {r.comments_count}</span>}
              </span>
              <span className="ws-daily-card__done">{r.done.slice(0, 260)}</span>
              {r.blockers && <span className="ws-daily-card__blocker">Заважало: {r.blockers.slice(0, 160)}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ================================================================ тиждень (owner) */

function addDays(iso, n) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function Week({ onOpen }) {
  const [start, setStart] = useState(null);
  const [w, setW] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getDailyWeek(start).then(setW).catch((e) => setError(errorText(e)));
  }, [start]);

  if (error) return <ErrorBox text={error} />;
  if (!w) return <p className="ws-muted">Завантажуємо…</p>;

  return (
    <div className="ws-stack">
      <div className="ws-row ws-wrap">
        <button type="button" className="ws-btn" onClick={() => setStart(addDays(w.start, -7))}>← Попередній</button>
        <b>{fmtDate(w.start)} – {fmtDate(w.end)}</b>
        <button type="button" className="ws-btn" onClick={() => setStart(addDays(w.start, 7))}>Наступний →</button>
      </div>

      <div className="ws-card ws-daily-week">
        <table>
          <thead>
            <tr>
              <th>Хто</th>
              {w.days.map((d, i) => <th key={d} className={i > 4 ? "is-weekend" : ""}>{WEEKDAYS[i]}<small>{shortDate(d)}</small></th>)}
              <th>Годин</th>
            </tr>
          </thead>
          <tbody>
            {w.members.map((m) => (
              <tr key={m.id}>
                <th scope="row">{m.name}</th>
                {m.days.map((d, i) => {
                  const missing = m.missing_workdays.includes(d.date);
                  return (
                    <td key={d.date} className={`${missing ? "is-missing" : ""}${i > 4 ? " is-weekend" : ""}`}>
                      {d.submitted ? (
                        <button type="button" onClick={() => onOpen(d.report_id)} title="Відкрити звіт">✓ {d.hours}</button>
                      ) : missing ? "не здав" : "—"}
                    </td>
                  );
                })}
                <td><b>{m.hours_total}</b></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ws-muted ws-small">Разом за тиждень: {w.hours_total} год. «Не здав» — робочий день до сьогодні включно без звіту.</p>

      <section className="ws-card">
        <h2>Що заважало цього тижня</h2>
        {!w.blockers.length ? <p className="ws-muted">Блокерів немає.</p> : (
          <ul className="ws-lines">
            {w.blockers.map((b) => (
              <li key={b.report_id}>
                <button type="button" className="ws-line" onClick={() => onOpen(b.report_id)}>
                  <b>{b.author} · {shortDate(b.date)}</b><span>{b.text}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/* ================================================================ звіт повністю */

function ReportModal({ id, onClose }) {
  const [r, setR] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { getDailyReport(id).then(setR).catch((e) => setError(errorText(e))); }, [id]);

  return (
    <Modal title={r ? `${r.author} · ${fmtDate(r.date)}` : "Звіт дня"} onClose={onClose} wide>
      {error && <ErrorBox text={error} />}
      {r && (
        <div className="ws-detail">
          <div className="ws-detail__main ws-stack">
            <dl className="ws-facts">
              <div><dt>Годин</dt><dd>{r.hours}</dd></div>
              <div><dt>Настрій / навантаження</dt><dd>{r.mood ? `${r.mood} з 5` : "не вказано"}</dd></div>
            </dl>
            <section className="ws-block"><h3>Що зроблено</h3><Markdown text={r.done} /></section>
            {r.links.length > 0 && (
              <section className="ws-block">
                <h3>Посилання</h3>
                <ul className="ws-daily-links">
                  {r.links.map((l) => <li key={l}><a href={l} target="_blank" rel="noopener noreferrer nofollow">{l}</a></li>)}
                </ul>
              </section>
            )}
            <section className="ws-block"><h3>Що заважало</h3><Markdown text={r.blockers} empty="Нічого не заважало." /></section>
            <section className="ws-block"><h3>План на завтра</h3><Markdown text={r.plan} empty="План не вказано." /></section>
          </div>
          <div className="ws-detail__side">
            <Comments type="daily" id={r.id} />
          </div>
        </div>
      )}
    </Modal>
  );
}
